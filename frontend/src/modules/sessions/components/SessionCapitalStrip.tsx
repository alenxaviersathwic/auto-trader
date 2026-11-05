import React from "react";
import { SessionCapital } from "../types/sessions.types";
import { formatRupee } from "../../opportunities/components/formatters";

/** Capital, current capital and the loss budget the next pick is sized against. */
export const SessionCapitalStrip: React.FC<{ capital: SessionCapital; maxLossPercentage: number }> = ({
  capital: c,
  maxLossPercentage,
}) => {
  const pnlClass = c.realizedPnl > 0 ? "text-green" : c.realizedPnl < 0 ? "text-red" : "";
  const budgetPct = c.maxLossAmount > 0 ? Math.min(100, (c.remainingLossBudget / c.maxLossAmount) * 100) : 0;
  const tone = budgetPct > 50 ? "ok" : budgetPct > 20 ? "warn" : "crit";
  return (
    <div className="sl-strip">
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
        <span className="micro text-muted">{formatRupee(c.committedPremium)} in locked trades</span>
      </div>
      <div className="sl-stat">
        <span className="label">Loss budget left ({maxLossPercentage}%)</span>
        <span className="sl-stat__value">{formatRupee(c.remainingLossBudget)}</span>
        <div className="sl-budget">
          <div className={`sl-budget__fill sl-budget__fill--${tone}`} style={{ width: `${budgetPct}%` }} />
        </div>
      </div>
      <div className="sl-stat">
        <span className="label">Trades locked</span>
        <span className="sl-stat__value">{c.lockedTrades}</span>
        <span className="micro text-muted">no limit</span>
      </div>
    </div>
  );
};
