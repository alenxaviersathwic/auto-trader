import React from "react";
import { ListChecks, Settings2 } from "lucide-react";
import { TRADER_META, traderForStrategy } from "../../trade-history/components/traderMeta";
import { useUpdateOpportunityFinder } from "../hooks/useOpportunityFinders";
import { OPTION_TYPES, OpportunityFinder, OptionType } from "../types/opportunityFinder.types";
import { TraderCode } from "../../trade-history/types/trades.types";
import { SetupScorecard, TradeAutopsy } from "../../autopsy/types/learning.types";
import { formatSignedRupee } from "../../opportunity-finder/components/formatters";
import { OpportunityCardItem } from "../../opportunity-finder/types/opportunities.types";
import { TraderTodayStrip } from "./TraderTodayStrip";

interface Props {
  code: TraderCode;
  scorecards: SetupScorecard[];
  autopsies: TradeAutopsy[];
  /** Indices scanned today (shared by both traders). */
  todayCards: OpportunityCardItem[];
  onOpenToday: () => void;
  /** The finder's profile from the API (markets it works on, drivers); undefined while loading. */
  finder?: OpportunityFinder;
  /** The finder's live working view under its stats (the Commodity Desk shows its sub-agents here). */
  children?: React.ReactNode;
}

/** One opportunity finder, all rendered alike: the markets it works on, what it checks before entering, how it
 *  manages the trade, and how its setups did. Only strategy and method differ between finders. */
export const OpportunityTraderCard: React.FC<Props> = ({
  code,
  scorecards,
  autopsies,
  todayCards,
  onOpenToday,
  finder,
  children,
}) => {
  const meta = TRADER_META[code];
  const updateFinder = useUpdateOpportunityFinder();
  const markets: OptionType[] = finder?.optionTypes ?? [];
  const toggleMarket = (t: OptionType) => {
    const next = markets.includes(t) ? markets.filter((m) => m !== t) : [...markets, t];
    if (next.length === 0) return; // a finder always works on at least one market
    updateFinder.mutate({ code, body: { optionTypes: next } });
  };
  const mine = scorecards.filter((c) => traderForStrategy(c.setup) === code);
  const done = autopsies.filter((a) => (a.traderCode ?? traderForStrategy(a.setup)) === code);
  const wins = done.filter((a) => a.outcome === "WIN").length;
  const net = done.reduce((s, a) => s + a.netPnl, 0);
  const avgR = done.length ? done.reduce((s, a) => s + a.rMultiple, 0) / done.length : null;

  return (
    <section className="te-panel" aria-label={meta.name}>
      <div className="te-panel__head">
        <span className="te-panel__title">
          <span className={`badge ${meta.badgeClass} mono`}>{meta.tag}</span> {meta.name}
        </span>
        <span className="tr-markets" role="group" aria-label={`Markets ${meta.name} works on`}>
          {OPTION_TYPES.map((t) => (
            <button
              key={t}
              type="button"
              className={`toggle-chip ${markets.includes(t) ? "toggle-chip--active" : ""}`}
              aria-pressed={markets.includes(t)}
              disabled={!finder || updateFinder.isPending || (markets.includes(t) && markets.length === 1)}
              title={
                markets.includes(t) && markets.length === 1
                  ? "A finder works on at least one market"
                  : `${markets.includes(t) ? "Stop" : "Start"} finding ${t.toLowerCase()} opportunities`
              }
              onClick={() => toggleMarket(t)}
            >
              {t}
            </button>
          ))}
        </span>
      </div>
      {finder?.drivers && <span className="micro text-secondary">{finder.drivers}</span>}

      <div className="tr-stats">
        <div>
          <span className="label">Closed trades</span>
          <span className="mono">{done.length}</span>
        </div>
        <div>
          <span className="label">Win rate</span>
          <span className="mono">{done.length ? `${Math.round((wins / done.length) * 100)}%` : "--"}</span>
        </div>
        <div>
          <span className="label">Avg R</span>
          <span className={`mono ${avgR !== null && avgR < 0 ? "text-red" : ""}`}>
            {avgR === null ? "--" : `${avgR >= 0 ? "+" : ""}${avgR.toFixed(2)}R`}
          </span>
        </div>
        <div>
          <span className="label">Net P&amp;L</span>
          <span className={`mono ${net >= 0 ? "text-green" : "text-red"}`}>{formatSignedRupee(net, true)}</span>
        </div>
      </div>

      <TraderTodayStrip trader={code} cards={todayCards} onOpen={onOpenToday} />
      {children}

      <span className="label">
        <ListChecks size={12} /> Checks before it enters
      </span>
      <ol className="tr-list">
        {meta.checks.map((c) => (
          <li key={c}>{c}</li>
        ))}
      </ol>

      <span className="label">
        <Settings2 size={12} /> How it manages the trade
      </span>
      <p className="micro text-secondary tr-text">{meta.manages}</p>

      <span className="label">Its setups (last 14 days)</span>
      {mine.length === 0 ? (
        <span className="micro text-muted">No closed trades on its setups yet.</span>
      ) : (
        mine.map((c) => (
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
            <span className={`mono micro tr-amt ${c.netPnl >= 0 ? "text-green" : "text-red"}`}>
              {formatSignedRupee(c.netPnl, true)}
            </span>
          </div>
        ))
      )}
    </section>
  );
};
