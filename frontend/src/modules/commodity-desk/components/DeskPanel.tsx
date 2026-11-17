import React, { useEffect, useMemo, useState } from "react";
import { Brain, Newspaper } from "lucide-react";
import { useDeskLatest, useDeskLive } from "../hooks/useCommodityDesk";
import { DeskCommodityView } from "./DeskCommodityView";
import { DeskFlow } from "./DeskFlow";
import { MarketMovesList } from "./MarketMovesList";

interface Props {
  /** Only these commodities (a session's items); all when unset. */
  codes?: string[];
  /** Show the sudden-move list (for these codes, or all moves when unset). */
  showMoves?: boolean;
}

/** The Commodity Desk at work: one tab per commodity with its live working flow, sub-agents and the head trader. */
export const DeskPanel: React.FC<Props> = ({ codes, showMoves = true }) => {
  const latest = useDeskLatest();
  const live = useDeskLive();
  const want = (c: string) => !codes || codes.includes(c);
  const decisions = (latest.data?.decisions ?? []).filter((d) => want(d.underlyingCode));
  const desks = (live.data?.desks ?? []).filter((d) => want(d.code));
  const checks = (live.data?.newsChecks ?? []).filter((n) => want(n.code));
  const moves = (latest.data?.moves ?? []).filter((m) => want(m.underlyingCode));
  const tabs = useMemo(
    () => Array.from(new Set([...desks.map((d) => d.code), ...decisions.map((d) => d.underlyingCode), ...(codes ?? [])])),
    [desks, decisions, codes],
  );
  const [tab, setTab] = useState<string | null>(null);
  useEffect(() => {
    if (tabs.length && (!tab || !tabs.includes(tab))) setTab(tabs[0]);
  }, [tabs, tab]);
  const code = tab ?? tabs[0];
  const decision = decisions.find((d) => d.underlyingCode === code);
  const item = desks.find((d) => d.code === code);
  const thinkingAny = desks.some((d) => d.thinkingSince);

  return (
    <div className="dk-panel">
      <div className="dk-panel__head">
        <span className="dk-panel__title">
          <Brain size={14} className={thinkingAny ? "dk-think-icon" : undefined} /> Commodity Desk
          {thinkingAny && <span className="micro text-cyan">head trader thinking…</span>}
        </span>
      </div>
      {latest.isLoading && live.isLoading ? (
        <span className="micro text-muted">Loading the desk…</span>
      ) : tabs.length === 0 ? (
        <span className="micro text-muted">
          The desk has not run yet. It thinks during commodity scans (MCX hours, 09:00 to the close): start a commodity
          session or scanner.
        </span>
      ) : (
        <>
          <div className="dk-tabs" role="tablist" aria-label="Commodities">
            {tabs.map((c) => {
              const it = desks.find((d) => d.code === c);
              const dec = decisions.find((d) => d.underlyingCode === c);
              return (
                <button key={c} type="button" role="tab" aria-selected={code === c}
                        className={`dk-tab ${code === c ? "dk-tab--active" : ""}`} onClick={() => setTab(c)}>
                  <span className="ticker">{c}</span>
                  <span className={`dk-tab__dot ${it?.thinkingSince ? "dk-tab__dot--think" : dec?.decision === "TAKE" ? "dk-tab__dot--take" : ""}`} />
                </button>
              );
            })}
          </div>
          {code && <DeskFlow code={code} item={item} newsCheck={checks.find((n) => n.code === code)} />}
          {decision ? (
            <DeskCommodityView d={decision} />
          ) : (
            <span className="micro text-muted">No head-trader decision for {code} yet: the first one comes a few seconds after its first scan.</span>
          )}
        </>
      )}
      {showMoves && (
        <div className="dk-panel__moves">
          <span className="label">
            <Newspaper size={12} /> Sudden moves and their news
          </span>
          <MarketMovesList moves={moves} />
        </div>
      )}
    </div>
  );
};
