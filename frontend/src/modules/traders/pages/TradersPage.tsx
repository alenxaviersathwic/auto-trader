import React, { useState } from "react";
import { useNavigate, useSearch } from "@tanstack/react-router";
import { Bot, Cpu, Play, Square } from "lucide-react";
import { OpportunityTraderCard } from "../components/OpportunityTraderCard";
import { FinderHowItWorksModal } from "../components/FinderHowItWorksModal";
import { TraderTodaySheet } from "../components/TraderTodaySheet";
import {
  resumeOpportunityLoop,
  useOpportunityCards,
  useOpportunityLoop,
  useStartOpportunity,
  useStopAll,
} from "../../opportunity-finder/hooks/useOpportunities";
import { SessionManagerCard } from "../components/SessionManagerCard";
import { AutopsySubAgent } from "../../sessions/components/agents/AutopsySubAgent";
import { RISK_LEVELS, RISK_META, RISK_NOTE } from "../../sessions/components/riskLevels";
import { useAutopsies, useScorecards } from "../../autopsy/hooks/useLearning";
import { DESK_CODE, SESSION_MANAGERS, TRADER_CODES, traderForStrategy } from "../../trade-history/components/traderMeta";
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
  const autopsies = useAutopsies({ page: 0, limit: 100, sortBy: "createdAt", sortDir: "desc" }, REFRESH_MS); // API max is 100
  const autopsyList = autopsies.data?.list ?? [];
  // Indices with a scanner today: both opportunity traders read the same scans, each for its own setups.
  const loop = useOpportunityLoop();
  const { cards: oppCards, hasResearch } = useOpportunityCards(loop.running || !!loop.inOtherTab);
  // every market a finder can scan (Research cards + anything started today); unscanned ones show "no scan yet"
  const todayCards = oppCards;
  const scanning = oppCards.filter((c) => c.master?.state === "RUNNING");
  const notScanning = oppCards.filter((c) => c.master?.state !== "RUNNING").map((c) => c.code);
  const startAll = useStartOpportunity();
  const stopAll = useStopAll();
  // scanners already RUNNING (started from a session or here) but no loop in this tab: pick them up
  React.useEffect(() => {
    if (scanning.length > 0 && !loop.running) resumeOpportunityLoop();
  }, [scanning.length, loop.running]);
  const [openTrader, setOpenTrader] = useState<TraderCode | null>(null);
  const [selectedFinder, setSelectedFinder] = useState<TraderCode | null>(null);
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
        <div className="te-head__right">
          <span className="micro text-muted">
            Finders scanning {scanning.length}/{oppCards.length} markets
            {loop.backend ? " · run by the backend" : loop.inOtherTab ? " · loop runs in another tab" : loop.currentCode ? ` · now ${loop.currentCode}` : ""}
          </span>
          {notScanning.length > 0 ? (
            <button
              type="button"
              className="te-btn te-btn--primary te-btn--xs"
              onClick={() => startAll.mutate({ underlyings: notScanning })}
              disabled={startAll.isPending || !hasResearch}
              title={hasResearch ? `Start: ${notScanning.join(", ")}` : "Run the Research Engine first"}
            >
              <Play size={10} /> {startAll.isPending ? "Starting…" : scanning.length ? "Scan the rest" : "Start all finders"}
            </button>
          ) : null}
          {scanning.length > 0 && (
            <button type="button" className="te-btn te-btn--ghost te-btn--xs" onClick={() => stopAll.mutate()} disabled={stopAll.isPending}>
              <Square size={10} /> Stop
            </button>
          )}
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
          {order.map((code) => (
            <OpportunityTraderCard
              key={code}
              code={code}
              finder={finderOf(code)}
              scorecards={cards.data?.list ?? []}
              autopsies={autopsyList}
              todayCards={cardsFor(code)}
              onOpenToday={() => setOpenTrader(code)}
              onOpenHowItWorks={() => setSelectedFinder(code)}
            />
          ))}
        </div>
        {selectedFinder && (
          <FinderHowItWorksModal
            code={selectedFinder}
            finder={finderOf(selectedFinder)}
            scorecards={(cards.data?.list ?? []).filter((c) => traderForStrategy(c.setup) === selectedFinder)}
            onClose={() => setSelectedFinder(null)}
            onOpenToday={() => setOpenTrader(selectedFinder)}
          >
            {selectedFinder === DESK_CODE ? <DeskPanel /> : null}
          </FinderHowItWorksModal>
        )}
        {openTrader && (
          <TraderTodaySheet trader={openTrader} cards={cardsFor(openTrader)} onClose={() => setOpenTrader(null)} />
        )}
        </div>
      ) : (
        <div className="tr-main">
            <div className="tr-grid">
              {SESSION_MANAGERS.map((m) => (
                <SessionManagerCard key={m.traderCode} manager={m}>
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
