import React from "react";
import { AlertTriangle, Eye, LogOut } from "lucide-react";
import { ActiveTrade } from "../../trades/types/trades.types";
import { formatSignedRupee } from "../../opportunities/components/formatters";
import { useExitTrade } from "../../trades/hooks/useTrades";
import { TRADER_META, normalizeTraderCode, traderForStrategy } from "../../trades/components/traderMeta";

const px = (n: number): string => `₹${n.toLocaleString("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

interface Props {
  trade: ActiveTrade;
  onOpen: (tradeId: number) => void;
}

/** A running trade, after trading-engine's active-trade card: live P&L, levels, the trader's exit signal, exit. */
export const RunningTradeCard: React.FC<Props> = ({ trade: t, onOpen }) => {
  const exit = useExitTrade(t.id);
  const up = t.netPnl >= 0;
  const signal = t.marketTelemetry?.exitSignal;
  const progress = Math.max(0, Math.min(100, t.marketTelemetry?.liveProgressPct ?? 0));
  const trader = TRADER_META[normalizeTraderCode(t.marketTelemetry?.traderCode) ?? traderForStrategy(t.strategy)];

  return (
    <article className={`te-active ${up ? "" : "te-active--down"} ${signal ? "te-active--exit" : ""}`}>
      <div className="te-active__head">
        <span className="te-active__name">
          {t.underlyingCode} <span>{t.strike}</span> {t.optionType}
        </span>
        <span className={`te-pill ${t.routeThroughUpstox ? "te-pill--green" : "te-pill--purple"}`}>
          {t.routeThroughUpstox ? "UPSTOX" : "SIMULATED"}
        </span>
      </div>
      <span className="micro text-muted">
        {trader.name} · {t.strategy ?? "—"}
      </span>

      <div className={`te-pnl ${up ? "" : "te-pnl--down"}`}>
        <div>
          <div className="te-stat__label">Net P&amp;L after charges</div>
          <div className={`te-pnl__value ${up ? "text-green" : "text-red"}`}>
            {formatSignedRupee(t.netPnl, true)}
          </div>
        </div>
        <div>
          <div className="te-stat__label">Return</div>
          <div className={`te-pnl__ret ${up ? "text-green" : "text-red"}`}>
            {t.pnlPct >= 0 ? "+" : ""}
            {t.pnlPct.toFixed(2)}%
          </div>
        </div>
      </div>

      <div className="te-metrics">
        <div className="te-stat">
          <div className="te-stat__label">Entry · LTP</div>
          <div className="te-tiny-val">
            {px(t.entryAt)} · {px(t.lastPrice)}
          </div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Quantity</div>
          <div className="te-tiny-val">
            {t.quantity} ({t.lots} lot{t.lots === 1 ? "" : "s"})
          </div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Target</div>
          <div className="te-tiny-val text-green">{px(t.currentTarget)}</div>
        </div>
        <div className="te-stat">
          <div className="te-stat__label">Stop</div>
          <div className="te-tiny-val text-red">{px(t.currentStop)}</div>
        </div>
      </div>

      <div className="te-progress" title={`${progress.toFixed(0)}% of the way to target`}>
        <div className="te-progress__fill" style={{ width: `${progress}%` }} />
      </div>

      {signal && (
        <div className="te-signal">
          <AlertTriangle size={13} />
          <span>
            Exit signal ({signal}): {t.marketTelemetry?.exitRecommendation ?? "the trader wants out"}
          </span>
        </div>
      )}
      {exit.isError && (
        <div className="micro text-red">{exit.error instanceof Error ? exit.error.message : "Exit failed"}</div>
      )}

      <div className="te-actionbar">
        <button type="button" className="te-btn te-btn--primary" style={{ flex: 1 }} onClick={() => onOpen(t.id)}>
          <Eye size={14} /> Full monitor
        </button>
        <button
          type="button"
          className="te-btn te-btn--danger"
          onClick={() => exit.mutate({ reason: "MANUAL_EXIT" })}
          disabled={exit.isPending}
        >
          <LogOut size={14} /> {exit.isPending ? "Exiting…" : "Exit"}
        </button>
      </div>
    </article>
  );
};
