import React from "react";
import { Activity, Ban, CheckCircle2, ShieldAlert } from "lucide-react";
import { IterationResult, OpportunityIteration } from "../types/opportunities.types";

/** Human label + badge colour for each reason a batch ended the way it did. */
export const RESULT_META: Record<IterationResult, { label: string; badge: string; help: string }> = {
  SAVED: { label: "SAVED", badge: "badge--green", help: "Opportunities were saved." },
  DROPPED: { label: "LOW CONF / EDGE", badge: "badge--amber", help: "Picks were made but dropped by the confidence / edge checks." },
  NO_SETUP: { label: "NO SETUP", badge: "badge--slate", help: "No chart setup fired on the last completed 5-minute bar." },
  SETUP_REJECTED: { label: "TF MISMATCH", badge: "badge--amber", help: "A setup fired but the 15m / 5m / 1m timeframes did not agree." },
  NO_CONTRACT: { label: "NO CONTRACT", badge: "badge--amber", help: "A setup was confirmed but no ATM / 1-ITM contract passed the liquidity, delta and R:R filters." },
  BLOCKED_WINDOW: { label: "NO-ENTRY WINDOW", badge: "badge--slate", help: "First 5 minutes, 12:00-13:30 chop or last 25 minutes." },
  MARKET_CLOSED: { label: "MARKET CLOSED", badge: "badge--slate", help: "The exchange is closed for this underlying." },
  NOT_IN_RESEARCH: { label: "NOT IN RESEARCH", badge: "badge--amber", help: "The underlying dropped out of the latest Research run." },
  DATA_ERROR: { label: "DATA ERROR", badge: "badge--red", help: "Market data could not be loaded." },
  ERROR: { label: "ERROR", badge: "badge--red", help: "The iteration failed." },
};

export const ResultBadge: React.FC<{ result: IterationResult }> = ({ result }) => {
  const meta = RESULT_META[result] ?? RESULT_META.ERROR;
  return (
    <span className={`badge ${meta.badge}`} title={meta.help}>
      {meta.label}
    </span>
  );
};

const Counts: React.FC<{ title: string; data?: Record<string, number> }> = ({ title, data }) => {
  const entries = Object.entries(data ?? {});
  if (entries.length === 0) return null;
  return (
    <div className="ss-diag-row">
      <span className="ss-diag-key">{title}</span>
      <span className="ss-diag-chips">
        {entries.map(([k, n]) => (
          <span key={k} className="ss-strike-chip mono">
            {k} ×{n}
          </span>
        ))}
      </span>
    </div>
  );
};

/** Why this batch ended the way it did: pipeline stages from market gate through setups to dropped picks. */
export const BatchDiagnostics: React.FC<{ iteration: OpportunityIteration }> = ({ iteration }) => {
  const d = iteration.details ?? {};
  const meta = RESULT_META[iteration.result] ?? RESULT_META.ERROR;
  const confirmed = d.setupsConfirmed ?? [];
  const rejected = d.setupsRejected ?? [];
  const fired = d.setupsFired ?? [];
  return (
    <div className="ss-diag">
      <div className="ss-diag-head">
        <Activity size={13} />
        <span className="ss-diag-title">Batch diagnostics</span>
        <ResultBadge result={iteration.result} />
        {iteration.durationMs != null && (
          <span className="ss-diag-dim mono">{(iteration.durationMs / 1000).toFixed(1)}s</span>
        )}
      </div>
      <div className="ss-diag-line">{iteration.summary || d.reason || meta.help}</div>

      <div className="ss-diag-row">
        <span className="ss-diag-key">Context</span>
        <span className="ss-diag-chips mono">
          {d.regime && <span className="ss-strike-chip">{d.regime}</span>}
          {d.window && <span className="ss-strike-chip">{d.window}</span>}
          {d.trend15 && (
            <span className="ss-strike-chip">
              15m {d.trend15}
              {d.trend15Source === "5m-proxy" ? " (5m proxy)" : ""}
            </span>
          )}
        </span>
      </div>

      {fired.length > 0 && (
        <div className="ss-diag-row">
          <span className="ss-diag-key">Fired</span>
          <span className="ss-diag-chips">
            {fired.map((s, i) => (
              <span key={i} className={`ss-strike-chip mono ${s.side === "CE" ? "is-ce" : "is-pe"}`}>
                {s.name} {s.side} ·{s.strength}
              </span>
            ))}
          </span>
        </div>
      )}
      {confirmed.length > 0 && (
        <div className="ss-diag-row">
          <span className="ss-diag-key">
            <CheckCircle2 size={11} /> Confirmed
          </span>
          <span className="ss-diag-chips">
            {confirmed.map((s, i) => (
              <span key={i} className={`ss-strike-chip mono ${s.side === "CE" ? "is-ce" : "is-pe"}`}>
                {s.name} {s.side}
              </span>
            ))}
          </span>
        </div>
      )}
      {rejected.length > 0 && (
        <div className="ss-diag-row ss-diag-row--col">
          <span className="ss-diag-key">
            <Ban size={11} /> Rejected
          </span>
          <ul className="ss-diag-list">
            {rejected.map((r, i) => (
              <li key={i}>
                <strong className="mono">
                  {r.name} {r.side}
                </strong>{" "}
                — {r.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {d.menuSize != null && (
        <div className="ss-diag-row">
          <span className="ss-diag-key">Contracts</span>
          <span className="mono">{d.menuSize} candidate(s) on the ranked menu</span>
        </div>
      )}
      <Counts title="Contract filters" data={d.menuDropped} />

      {d.picks != null && (
        <div className="ss-diag-row">
          <span className="ss-diag-key">
            <ShieldAlert size={11} /> Ranking
          </span>
          <span className="mono">
            {d.picks} ranked by {d.source ?? "AI"} → {d.kept ?? 0} kept (needs confidence ≥ {d.confidenceWanted})
          </span>
        </div>
      )}
      <Counts title="Dropped" data={d.dropped} />
    </div>
  );
};
