import React, { useState } from "react";
import { Check, ChevronDown, ChevronUp, Microscope, Play, X } from "lucide-react";
import {
  useApplyGuard,
  useAutopsies,
  useGuards,
  useRejectGuard,
  useResumeSetup,
  useScorecards,
} from "../../../autopsy/hooks/useLearning";
import { TAG_LABEL, VERDICT_META } from "../../../autopsy/types/learningMeta";
import { formatSignedRupee } from "../../../opportunity-finder/components/formatters";
import { managerFor } from "../../../trade-history/components/traderMeta";
import { TraderCode } from "../../../trade-history/types/trades.types";
import { AgentAvatar } from "./AgentAvatar";

const REFRESH_MS = 15000;
const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

interface Props {
  managerCode: TraderCode;
  /** Drawn under its manager with a connector line. */
  nested?: boolean;
  /** Collapsible: starts folded to its one-line status (which says when a rule waits for you). */
  collapsible?: boolean;
}

/**
 * The autopsy sub-agent of one session manager: it reviews every trade its manager's sessions close, keeps that
 * manager's setup scorecards (pausing a losing setup) and proposes rules from repeated mistakes. What it learns only
 * changes this manager's sessions.
 */
export const AutopsySubAgent: React.FC<Props> = ({ managerCode, nested, collapsible }) => {
  const [openState, setOpen] = useState<boolean | null>(null);
  const manager = managerFor(managerCode);
  const last = useAutopsies({ page: 0, limit: 1, sortBy: "createdAt", sortDir: "desc", managerCode }, REFRESH_MS);
  const cards = useScorecards({ page: 0, limit: 20, sortBy: "netPnl", sortDir: "asc", managerCode }, REFRESH_MS);
  const guards = useGuards({ page: 0, limit: 20, sortBy: "createdAt", sortDir: "desc", managerCode }, REFRESH_MS);
  const apply = useApplyGuard();
  const reject = useRejectGuard();
  const resume = useResumeSetup();

  const latest = last.data?.list?.[0];
  const scorecards = (cards.data?.list ?? []).filter((c) => c.closedTrades > 0 || c.scoreStatus === "PAUSED");
  const rules = (guards.data?.list ?? []).filter((g) => g.guardState !== "REJECTED");
  const proposed = rules.filter((g) => g.guardState === "PROPOSED").length;
  const paused = scorecards.filter((c) => c.scoreStatus === "PAUSED").length;
  const busy = apply.isPending || reject.isPending;
  const error = [apply.error, reject.error, resume.error].find(Boolean);
  const tone = proposed > 0 || paused > 0 ? "alert" : latest ? "ready" : "idle";
  const open = !collapsible || (openState ?? false);
  const summary = [
    scorecards.length > 0 && `${scorecards.length} setup${scorecards.length === 1 ? "" : "s"} scored`,
    paused > 0 && `${paused} paused`,
    proposed > 0 && `${proposed} rule${proposed === 1 ? "" : "s"} waiting`,
  ].filter(Boolean).join(" · ");

  return (
    <section className={`ag-sub ${nested ? "ag-sub--nested" : ""}`} aria-label={`${manager.name} autopsy sub-agent`}>
      <header className="ag-sub__head">
        <AgentAvatar icon={<Microscope size={13} />} tone={tone} size="sm" label="Autopsy sub-agent" />
        <div className="ag-sub__id">
          <span className="ag-sub__name">Autopsy</span>
          <span className="ag-eyebrow">sub-agent of {manager.name}</span>
        </div>
        <span className="ag-sub__status">
          {latest ? `last review ${hhmm(latest.createdAt)} · trade #${latest.tradeId}` : "waiting for a closed trade"}
          {!open && summary && <span className="ag-sub__summary">{summary}</span>}
        </span>
        {collapsible && (
          <button
            type="button"
            className="ag-sub__toggle"
            aria-expanded={open}
            aria-label={open ? "Fold the autopsy sub-agent" : "Show the autopsy sub-agent"}
            onClick={() => setOpen(!open)}
          >
            {open ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
          </button>
        )}
      </header>

      {open && latest && (
        <div className="ag-thought">
          <span className={`te-pill te-pill--${VERDICT_META[latest.verdict]?.tone ?? "cyan"}`}>
            {VERDICT_META[latest.verdict]?.label ?? latest.verdict}
          </span>
          <span className="ag-thought__text">
            {latest.setup.replace(/_/g, " ")} {latest.rMultiple >= 0 ? "+" : ""}
            {latest.rMultiple.toFixed(1)}R · {latest.lessons[0] ?? latest.wentRight[0] ?? "nothing went wrong"}
            {latest.tags.length > 0 && ` (${latest.tags.map((t) => TAG_LABEL[t] ?? t).join(", ")})`}
          </span>
        </div>
      )}

      {open && (
      <div className="ag-sub__block">
        <span className="ag-label">Scorecards · 14 days</span>
        {scorecards.length === 0 ? (
          <span className="micro text-muted">Each closed trade updates its setup here.</span>
        ) : (
          scorecards.map((c) => (
            <div key={c.id} className="ag-line">
              <span className={`ag-line__dot ${c.scoreStatus === "PAUSED" ? "ag-line__dot--red" : "ag-line__dot--green"}`} />
              <span className="ag-line__main">
                <strong>{c.setup.replace(/_/g, " ")}</strong>
                <span className="text-muted">
                  {" "}
                  {c.closedTrades} · {c.wins}W/{c.losses}L · {c.avgR >= 0 ? "+" : ""}
                  {c.avgR.toFixed(2)}R
                </span>
              </span>
              <span className={`mono ag-line__amt ${c.netPnl >= 0 ? "text-green" : "text-red"}`}>
                {formatSignedRupee(c.netPnl, true)}
              </span>
              {c.scoreStatus === "PAUSED" && (
                <button
                  type="button"
                  className="te-btn te-btn--ghost te-btn--xs"
                  onClick={() => resume.mutate({ setup: c.setup, managerCode })}
                  disabled={resume.isPending}
                  title={c.statusReason ?? "Paused by its scorecard. Resume: counting restarts from now"}
                >
                  <Play size={10} /> Resume
                </button>
              )}
            </div>
          ))
        )}
      </div>
      )}

      {open && (
      <div className="ag-sub__block">
        <span className="ag-label">Learned rules{proposed > 0 ? ` · ${proposed} waiting for you` : ""}</span>
        {rules.length === 0 ? (
          <span className="micro text-muted">Proposed when the same mistake repeats 3 times on a setup.</span>
        ) : (
          rules.map((g) => (
            <div key={g.id} className={`ag-rule ${g.guardState === "APPLIED" ? "ag-rule--on" : ""}`}>
              <span className="ag-rule__text">{g.text}</span>
              <span className="ag-rule__foot">
                <span className="micro text-muted">
                  {g.evidence.trades} trades · {formatSignedRupee(g.evidence.netPnl ?? 0)}
                </span>
                {g.guardState === "APPLIED" ? (
                  <span className="te-pill te-pill--green">ENFORCED</span>
                ) : (
                  <span className="te-chips">
                    <button type="button" className="te-btn te-btn--ghost te-btn--xs" disabled={busy} onClick={() => reject.mutate(g.id)}>
                      <X size={10} /> Reject
                    </button>
                    <button type="button" className="te-btn te-btn--primary te-btn--xs" disabled={busy} onClick={() => apply.mutate(g.id)}>
                      <Check size={10} /> Apply
                    </button>
                  </span>
                )}
              </span>
            </div>
          ))
        )}
      </div>
      )}
      {error && <span className="micro text-red">{error instanceof Error ? error.message : "Action failed"}</span>}
    </section>
  );
};
