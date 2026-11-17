import React, { useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { Bot, Cpu } from "lucide-react";
import { OpportunityTraderCard } from "../components/OpportunityTraderCard";
import { TraderTodaySheet } from "../components/TraderTodaySheet";
import { useOpportunityCards } from "../../opportunity-finder/hooks/useOpportunities";
import { SessionManagerCard } from "../components/SessionManagerCard";
import { AutopsySubAgent } from "../../sessions/components/agents/AutopsySubAgent";
import { RISK_LEVELS, RISK_META, RISK_NOTE } from "../../sessions/components/riskLevels";
import { useSessionSearch } from "../../sessions/hooks/useSessions";
import { useAutopsies, useScorecards } from "../../autopsy/hooks/useLearning";
import { DESK_CODE, SESSION_MANAGERS, TRADER_CODES } from "../../trade-history/components/traderMeta";
import { useOpportunityFinders } from "../hooks/useOpportunityFinders";
import { DeskPanel } from "../../commodity-desk/components/DeskPanel";
import { TraderCode } from "../../trade-history/types/trades.types";

export type TradersTab = "traders" | "managers";
const REFRESH_MS = 30000;

/** Traders: the opportunity finders (what they check, which markets they work on) and the session managers, whose
 *  duty is the same for every market. */
export const TradersPage: React.FC = () => {
  const { tab = "traders" } = useSearch({ from: "/traders" });
  const navigate = useNavigate({ from: "/traders" });
  const setTab = (t: TradersTab) => navigate({ search: { tab: t }, replace: true });

  const cards = useScorecards({ page: 0, limit: 50, sortBy: "netPnl", sortDir: "asc" }, REFRESH_MS);
  const autopsies = useAutopsies({ page: 0, limit: 200, sortBy: "createdAt", sortDir: "desc" }, REFRESH_MS);
  const sessions = useSessionSearch({ page: 0, limit: 50, sessionStatus: "ACTIVE" });
  const autopsyList = autopsies.data?.list ?? [];
  // Indices with a scanner today: both opportunity traders read the same scans, each for its own setups.
  const { cards: oppCards } = useOpportunityCards(false);
  const todayCards = oppCards.filter((c) => c.master);
  const [openTrader, setOpenTrader] = useState<TraderCode | null>(null);
  const finders = useOpportunityFinders().data ?? [];
  const finderOf = (code: TraderCode) => finders.find((f) => f.code === code);
  // a finder sees only the scanners of the markets in its optionTypes
  const cardsFor = (code: TraderCode) => {
    const types = finderOf(code)?.optionTypes;
    return types ? todayCards.filter((c) => types.includes(c.type as "INDEX" | "COMMODITY")) : todayCards;
  };
  const order = finders.length ? finders.map((f) => f.code) : TRADER_CODES;

  return (
    <div className="te-desk">
      <header className="te-head">
        <div className="te-head__left">
          <h1 className="page-title">Traders</h1>
          <span className="micro text-muted">
            A session is run by one session manager; its opportunities come from the finders that work on its market.
          </span>
        </div>
      </header>

      <div className="te-tabs">
        <div className="te-tabs__list" role="tablist" aria-label="Traders">
          <button
            type="button"
            role="tab"
            aria-selected={tab === "traders"}
            className={`te-tab ${tab === "traders" ? "active" : ""}`}
            onClick={() => setTab("traders")}
          >
            <Bot size={14} /> Opportunity traders
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={tab === "managers"}
            className={`te-tab ${tab === "managers" ? "active" : ""}`}
            onClick={() => setTab("managers")}
          >
            <Cpu size={14} /> Session managers
          </button>
        </div>
      </div>

      {tab === "traders" ? (
        <div className="tr-main">
        <div className="tr-grid">
          {/* every finder rendered the same way; only its strategy, markets and live working view differ */}
          {order.map((code) => (
            <OpportunityTraderCard
              key={code}
              code={code}
              finder={finderOf(code)}
              scorecards={cards.data?.list ?? []}
              autopsies={autopsyList}
              todayCards={cardsFor(code)}
              onOpenToday={() => setOpenTrader(code)}
            >
              {code === DESK_CODE ? <DeskPanel /> : null}
            </OpportunityTraderCard>
          ))}
        </div>
        {openTrader && (
          <TraderTodaySheet trader={openTrader} cards={cardsFor(openTrader)} onClose={() => setOpenTrader(null)} />
        )}
        </div>
      ) : (
        <div className="tr-main">
            <div className="tr-grid">
              {SESSION_MANAGERS.map((m) => (
                <SessionManagerCard key={m.traderCode} manager={m} activeSessions={sessions.data?.list ?? []}>
                  <AutopsySubAgent managerCode={m.traderCode} nested />
                </SessionManagerCard>
              ))}
            </div>
            <section className="te-panel" aria-label="Risk levels">
              <span className="te-panel__title">Risk level (set per session)</span>
              {RISK_LEVELS.map((lv) => (
                <div key={lv} className="te-row">
                  <span className="te-row__main">
                    <span className="te-row__title">
                      <span className={`badge ${RISK_META[lv].badgeClass}`}>{RISK_META[lv].label}</span>
                    </span>
                    <span className="te-row__sub">{RISK_META[lv].takes}</span>
                  </span>
                </div>
              ))}
              <span className="micro text-muted">{RISK_NOTE}</span>
            </section>
        </div>
      )}
    </div>
  );
};
