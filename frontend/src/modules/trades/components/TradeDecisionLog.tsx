import React from "react";
import { TrailEvent } from "../types/trades.types";
import { formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });

function actionBadge(action: string): string {
  if (action.startsWith("EXIT")) return "badge badge--amber";
  if (action === "TRAIL_BOTH" || action === "TRAIL_TARGET") return "badge badge--cyan";
  if (action === "TRAIL_SL") return "badge badge--green";
  return "badge badge--slate";
}

export const TradeDecisionLog: React.FC<{ events: TrailEvent[] }> = ({ events }) => {
  const ordered = [...events].reverse();
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Time (IST)</th>
            <th>Action</th>
            <th>LTP</th>
            <th>Stop Loss</th>
            <th>Target</th>
            <th>Trader Reasoning</th>
          </tr>
        </thead>
        <tbody>
          {ordered.length === 0 && (
            <tr>
              <td colSpan={6} className="text-muted">No trader decisions logged yet.</td>
            </tr>
          )}
          {ordered.map((ev, idx) => (
            <tr key={`${ev.at}-${idx}`}>
              <td className="mono">{hms(ev.at)}</td>
              <td>
                <span className={actionBadge(ev.action)}>{ev.action}</span>
              </td>
              <td className="mono">{formatRupee(ev.ltp)}</td>
              <td className="mono text-red">
                {ev.oldStop !== ev.newStop
                  ? `${formatRupee(ev.oldStop)} → ${formatRupee(ev.newStop)}`
                  : formatRupee(ev.newStop)}
              </td>
              <td className="mono text-green">
                {ev.oldTarget !== ev.newTarget
                  ? `${formatRupee(ev.oldTarget)} → ${formatRupee(ev.newTarget)}`
                  : formatRupee(ev.newTarget)}
              </td>
              <td className="micro text-secondary">{ev.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

