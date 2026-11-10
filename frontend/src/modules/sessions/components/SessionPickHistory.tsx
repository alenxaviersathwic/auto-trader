import React from "react";
import { useNavigate } from "@tanstack/react-router";
import { ExternalLink, Play } from "lucide-react";
import { SessionPick } from "../types/sessions.types";
import { formatRupee } from "../../opportunities/components/formatters";

const hms = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour12: false });

const STATE_BADGE: Record<SessionPick["pickState"], string> = {
  OFFERED: "badge badge--cyan",
  LOCKED: "badge badge--blue",
  EXPIRED: "badge badge--slate",
};

/** Every pick this session has offered today: what was locked, entered into a Trader loop, or expired. */
export const SessionPickHistory: React.FC<{
  picks: SessionPick[];
  isLoading: boolean;
  onEnterLockedPick?: (pick: SessionPick) => void;
}> = ({ picks, isLoading, onEnterLockedPick }) => {
  const navigate = useNavigate();
  return (
    <div className="card" style={{ padding: 0, overflow: "hidden" }}>
      <table className="data-table">
        <thead>
          <tr>
            <th>Offered</th>
            <th>Option</th>
            <th>State</th>
            <th>Entry / Lock</th>
            <th>Stop</th>
            <th>Target</th>
            <th>Lots</th>
            <th>Risk</th>
            <th>Reward</th>
            <th>Trader</th>
          </tr>
        </thead>
        <tbody>
          {isLoading && (
            <tr>
              <td colSpan={10} className="text-muted">Loading picks...</td>
            </tr>
          )}
          {!isLoading && picks.length === 0 && (
            <tr>
              <td colSpan={10} className="text-muted">Nothing offered yet in this session.</td>
            </tr>
          )}
          {picks.map((p) => (
            <tr key={p.id}>
              <td className="mono">{hms(p.offeredAt)}</td>
              <td className="mono text-primary">
                {p.underlyingCode} {p.strike} {p.optionType}
              </td>
              <td><span className={STATE_BADGE[p.pickState]}>{p.pickState}</span></td>
              <td className="mono">
                {formatRupee(p.lockedPrice ?? p.entry)}
              </td>
              <td className="mono text-red">{formatRupee(p.stop)}</td>
              <td className="mono text-green">{formatRupee(p.target)}</td>
              <td className="mono">{p.lots}</td>
              <td className="mono">{formatRupee(p.riskAmount)}</td>
              <td className="mono">{formatRupee(p.rewardAmount)}</td>
              <td>
                {p.tradeId ? (
                  <button
                    type="button"
                    className="btn btn--ghost"
                    onClick={() => navigate({ to: "/trades/$tradeId", params: { tradeId: String(p.tradeId) } })}
                  >
                    <ExternalLink size={13} />
                    <span>Trade #{p.tradeId}</span>
                  </button>
                ) : p.pickState === "LOCKED" && onEnterLockedPick ? (
                  <button
                    type="button"
                    className="btn btn--primary"
                    onClick={() => onEnterLockedPick(p)}
                  >
                    <Play size={12} />
                    <span>Start Trader</span>
                  </button>
                ) : (
                  <span className="micro text-muted">—</span>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
