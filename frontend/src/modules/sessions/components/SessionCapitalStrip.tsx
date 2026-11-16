import React from "react";
import { SessionCapital } from "../types/sessions.types";
import { formatRupee } from "../../opportunities/components/formatters";

/** Capital, current capital, free cash, and active parallel Trader slots (max 3 open at once). */
export const SessionCapitalStrip: React.FC<{ capital: SessionCapital; maxLossPercentage?: number }> = ({
  capital: c,
}) => {
  const pnlClass = c.realizedPnl > 0 ? "text-green" : c.realizedPnl < 0 ? "text-red" : "";
  const activeCount = c.activeTradesCount ?? 0;
  const maxParallel = c.maxParallelTrades ?? 3;
  return (
    <div className="sl-strip" style={{ gridTemplateColumns: "repeat(4, minmax(0, 1fr))" }}>
      <div className="sl-stat">
        <span className="label">Capital</span>
        <span className="sl-stat__value">{formatRupee(c.capital)}</span>
      </div>
      <div className="sl-stat">
        <span className="label">Current capital</span>
        <span className={`sl-stat__value ${pnlClass}`}>{formatRupee(c.currentCapital)}</span>
        <span className="micro text-muted">Realised {formatRupee(c.realizedPnl)}</span>
      </div>
      <div className="sl-stat">
        <span className="label">Free to trade</span>
        <span className="sl-stat__value">{formatRupee(c.availableCapital)}</span>
        <span className="micro text-muted">{formatRupee(c.committedPremium)} committed</span>
      </div>
      <div className="sl-stat">
        <span className="label">Open Parallel Trades</span>
        <span className={`sl-stat__value mono ${activeCount >= maxParallel ? "text-amber" : "text-green"}`}>
          {activeCount} / {maxParallel} Open
        </span>
        <span className="micro text-muted">{c.lockedTrades} total trades taken (no limit)</span>
      </div>
    </div>
  );
};
