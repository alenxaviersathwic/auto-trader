import React from "react";
import { ActiveTrade } from "../../trade-history/types/trades.types";
import { TradeAutopsy } from "../../autopsy/types/learning.types";
import { VERDICT_META } from "../../autopsy/types/learningMeta";
import { formatSignedRupee } from "../../opportunity-finder/components/formatters";

interface Props {
  trades: ActiveTrade[];
  autopsies: Map<number, TradeAutopsy>;
  onOpen: (tradeId: number) => void;
}

/** Every trade of the session with its result and the autopsy agent's verdict. */
export const SessionTradesPanel: React.FC<Props> = ({ trades, autopsies, onOpen }) => {
  const net = trades.reduce((sum, t) => sum + (t.tradeState === "EXITED" ? t.netPnl : 0), 0);
  return (
    <section className="te-panel" aria-label="Session trades">
      <div className="te-panel__head">
        <span className="te-panel__title">Session trades ({trades.length})</span>
        <span className={`mono micro ${net >= 0 ? "text-green" : "text-red"}`}>
          {formatSignedRupee(net, true)}
        </span>
      </div>
      {trades.length === 0 ? (
        <span className="micro text-muted">No trades in this session yet.</span>
      ) : (
        trades.map((t) => {
          const a = autopsies.get(t.id);
          const done = t.tradeState === "EXITED";
          return (
            <button key={t.id} type="button" className="te-row te-row--click" onClick={() => onOpen(t.id)}>
              <span className="te-row__main">
                <span className="te-row__title">
                  <span className={`te-pill ${t.optionType === "CE" ? "te-pill--green" : "te-pill--red"}`}>
                    {t.optionType}
                  </span>
                  <span className="mono">
                    {t.underlyingCode} {t.strike}
                  </span>
                </span>
                <span className="te-row__sub">
                  ₹{t.entryAt.toFixed(2)} → {done ? `₹${(t.exitPrice ?? t.lastPrice).toFixed(2)}` : "running"}
                </span>
              </span>
              <span className="te-row__end">
                <span className={`mono micro ${t.netPnl >= 0 ? "text-green" : "text-red"}`}>
                  {done ? formatSignedRupee(t.netPnl, true) : "LIVE"}
                </span>
                {a ? (
                  <span className={`te-pill te-pill--${VERDICT_META[a.verdict].tone}`}>
                    {VERDICT_META[a.verdict].label} · {a.rMultiple >= 0 ? "+" : ""}
                    {a.rMultiple.toFixed(1)}R
                  </span>
                ) : done ? (
                  <span className="te-pill">AUTOPSY PENDING</span>
                ) : null}
              </span>
            </button>
          );
        })
      )}
    </section>
  );
};
