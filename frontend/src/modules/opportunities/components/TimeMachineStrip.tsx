import React from "react";
import { History } from "lucide-react";
import { TimeMachineOdds } from "../types/opportunities.types";

/** Odds of the pick's own target/stop over its validity window, replayed from the underlying's last ~60 sessions. */
export const TimeMachineStrip: React.FC<{ tm: TimeMachineOdds }> = ({ tm }) => {
  const pct = (x: number) => `${(x * 100).toFixed(1)}%`;
  const h = tm.history;
  const tone = tm.lean === null ? "" : tm.lean >= 0.05 ? "pos" : tm.lean <= -0.05 ? "neg" : "warn";
  return (
    <div className="oc-tm">
      <div className="oc-tm-head">
        <span className="oc-tm-title">
          <History size={12} />
          Time Machine · next {tm.barsAhead * 5} min
        </span>
        <span className="oc-tm-meta mono">
          {tm.replays.toLocaleString("en-IN")} replays · seed {tm.seed}
        </span>
      </div>
      <div className="oc-tm-bar" aria-hidden="true">
        <span className="oc-tm-bar--target" style={{ width: pct(tm.pTarget) }} />
        <span className="oc-tm-bar--stop" style={{ width: pct(tm.pStop) }} />
        <span className="oc-tm-bar--neither" style={{ width: pct(tm.pNeither) }} />
      </div>
      <div className="oc-tm-odds mono">
        <span className="pos">Target first {pct(tm.pTarget)}</span>
        <span className="neg">Stop first {pct(tm.pStop)}</span>
        <span className="oc-tm-muted">Neither {pct(tm.pNeither)}</span>
      </div>
      <div className={`oc-tm-verdict ${tone}`}>{tm.verdict}</div>
      <div className="oc-tm-muted mono">
        Real history ({h.sessions} sessions): {h.target} target · {h.stop} stop · {h.neither} neither
        {h.avgR !== null ? ` · avg ${h.avgR >= 0 ? "+" : ""}${h.avgR.toFixed(2)}R` : ""}
      </div>
    </div>
  );
};
