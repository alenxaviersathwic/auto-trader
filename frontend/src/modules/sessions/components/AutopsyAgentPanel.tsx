import React from "react";
import { Brain, Check, Play, X } from "lucide-react";
import {
  useApplyGuard,
  useGuards,
  useRejectGuard,
  useResumeSetup,
  useScorecards,
} from "../../learning/hooks/useLearning";
import { TradeAutopsy } from "../../learning/types/learning.types";
import { TAG_LABEL } from "../../learning/types/learningMeta";
import { formatSignedRupee } from "../../opportunities/components/formatters";

const REFRESH_MS = 15000;

interface Props {
  latest: TradeAutopsy | undefined;
}

/**
 * Autopsy agent: what finished trades changed. Scorecards pause losing setups by themselves; guards are rule
 * changes learned from repeated failures, enforced once applied (and mirrored on the Rules page).
 */
export const AutopsyAgentPanel: React.FC<Props> = ({ latest }) => {
  const cards = useScorecards({ page: 0, limit: 20, sortBy: "netPnl", sortDir: "asc" }, REFRESH_MS);
  const guards = useGuards({ page: 0, limit: 20, sortBy: "createdAt", sortDir: "desc" }, REFRESH_MS);
  const apply = useApplyGuard();
  const reject = useRejectGuard();
  const resume = useResumeSetup();
  const scorecards = (cards.data?.list ?? []).filter((c) => c.closedTrades > 0 || c.scoreStatus === "PAUSED");
  const open = (guards.data?.list ?? []).filter((g) => g.guardState !== "REJECTED");
  const busy = apply.isPending || reject.isPending;
  const error = [apply.error, reject.error, resume.error].find(Boolean);

  return (
    <section className="te-panel" aria-label="Autopsy agent">
      <div className="te-panel__head">
        <span className="te-panel__title">
          <Brain size={15} className="text-muted" /> Autopsy agent
        </span>
        <span className="micro text-muted">last 14 days</span>
      </div>

      {latest && (
        <div className="te-row">
          <span className="te-row__main">
            <span className="te-row__title">
              Last: {latest.setup.replace(/_/g, " ")} {latest.rMultiple >= 0 ? "+" : ""}
              {latest.rMultiple.toFixed(1)}R
            </span>
            <span className="te-row__sub">
              {latest.lessons[0] ?? latest.wentRight[0] ?? "No lesson: nothing went wrong."}
              {latest.tags.length > 0 && ` (${latest.tags.map((t) => TAG_LABEL[t] ?? t).join(", ")})`}
            </span>
          </span>
        </div>
      )}

      <span className="label">Setup scorecards</span>
      {scorecards.length === 0 ? (
        <span className="micro text-muted">No closed trades yet. Each exit updates its setup here.</span>
      ) : (
        scorecards.map((c) => (
          <div key={c.setup} className="te-row">
            <span className="te-row__main">
              <span className="te-row__title">
                {c.setup.replace(/_/g, " ")}
                <span className={`te-pill ${c.scoreStatus === "PAUSED" ? "te-pill--red" : "te-pill--green"}`}>
                  {c.scoreStatus}
                </span>
              </span>
              <span className="te-row__sub">
                {c.closedTrades} trades · {c.wins}W/{c.losses}L · avg {c.avgR >= 0 ? "+" : ""}
                {c.avgR.toFixed(2)}R{c.statusReason ? ` · ${c.statusReason}` : ""}
              </span>
            </span>
            <span className="te-row__end">
              <span className={`mono micro ${c.netPnl >= 0 ? "text-green" : "text-red"}`}>{formatSignedRupee(c.netPnl, true)}</span>
              {c.scoreStatus === "PAUSED" && (
                <button
                  type="button"
                  className="te-btn te-btn--ghost te-btn--sm"
                  onClick={() => resume.mutate(c.setup)}
                  disabled={resume.isPending}
                  title="Trade it again; counting restarts from now"
                >
                  <Play size={11} /> Resume
                </button>
              )}
            </span>
          </div>
        ))
      )}

      <span className="label">Learned rules</span>
      {open.length === 0 ? (
        <span className="micro text-muted">
          A rule is proposed when the same mistake repeats 3 times on one setup.
        </span>
      ) : (
        open.map((g) => (
          <div key={g.id} className={`te-guard ${g.guardState === "APPLIED" ? "te-guard--applied" : ""}`}>
            <span className="te-guard__text">{g.text}</span>
            <div className="te-guard__foot">
              <span className="micro text-muted">
                {g.evidence.trades} trades, {formatSignedRupee(g.evidence.netPnl ?? 0)}
              </span>
              {g.guardState === "APPLIED" ? (
                <span className="te-pill te-pill--green">ENFORCED</span>
              ) : (
                <span className="te-chips">
                  <button type="button" className="te-btn te-btn--ghost te-btn--sm" disabled={busy} onClick={() => reject.mutate(g.id)}>
                    <X size={11} /> Reject
                  </button>
                  <button type="button" className="te-btn te-btn--primary te-btn--sm" disabled={busy} onClick={() => apply.mutate(g.id)}>
                    <Check size={11} /> Apply
                  </button>
                </span>
              )}
            </div>
          </div>
        ))
      )}
      {error && <span className="micro text-red">{error instanceof Error ? error.message : "Action failed"}</span>}
    </section>
  );
};
