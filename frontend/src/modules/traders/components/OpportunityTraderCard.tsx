import React from "react";
import { Info } from "lucide-react";
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
  /** Opens the "How this finder works" popup. */
  onOpenHowItWorks: () => void;
  /** The finder's profile from the API (markets it works on, drivers); undefined while loading. */
  finder?: OpportunityFinder;
  /** The finder's live working view under its stats (the Commodity Desk shows its sub-agents here). */
  children?: React.ReactNode;
}

/** Compact clickable finder summary card. Clicking the card opens a popup showing how that finder works. */
export const OpportunityTraderCard: React.FC<Props> = ({
  code,
  scorecards,
  autopsies,
  todayCards,
  onOpenToday,
  onOpenHowItWorks,
  finder,
  children,
}) => {
  const meta = TRADER_META[code];
  const updateFinder = useUpdateOpportunityFinder();
  const markets: OptionType[] = finder?.optionTypes ?? [];
  const toggleMarket = (e: React.MouseEvent, t: OptionType) => {
    e.stopPropagation();
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
    <section
      className="te-panel te-panel--clickable"
      aria-label={meta.name}
      onClick={onOpenHowItWorks}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onOpenHowItWorks();
        }
      }}
    >
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
              onClick={(e) => toggleMarket(e, t)}
            >
              {t}
            </button>
          ))}
        </span>
      </div>
      <span className="micro text-secondary">{meta.tagline}</span>

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

      <div onClick={(e) => e.stopPropagation()}>
        <TraderTodayStrip trader={code} cards={todayCards} onOpen={onOpenToday} />
      </div>
      {children}

      <div className="tr-card-foot">
        <span className="micro text-muted">
          {mine.length > 0 ? `${mine.length} active setup${mine.length === 1 ? "" : "s"} (14d)` : `${meta.checks.length} entry checks`}
        </span>
        <span className="tr-card-foot__cta micro">
          <Info size={12} /> How it works
        </span>
      </div>
    </section>
  );
};
