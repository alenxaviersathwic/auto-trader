import React from "react";
import { Newspaper } from "lucide-react";
import { useDeskLatest, useDeskLive } from "../hooks/useCommodityDesk";
import { MarketMovesList } from "./MarketMovesList";

/** The news sub-agent under a session manager: sudden moves on this session's underlyings and the news found. */
export const NewsSubAgent: React.FC<{ codes: string[] }> = ({ codes }) => {
  const latest = useDeskLatest();
  const live = useDeskLive();
  const moves = (latest.data?.moves ?? []).filter((m) => codes.includes(m.underlyingCode));
  const checks = (live.data?.newsChecks ?? []).filter((n) => codes.includes(n.code));
  const STEP: Record<string, string> = { SAVING: "recording the move", READING_HEADLINES: "reading the news feeds",
    EXPLAINING: "LLM explaining the move", NO_HEADLINES: "no headline found" };
  return (
    <section className="dk-sub" aria-label="News sub-agent">
      <span className="dk-panel__title">
        <Newspaper size={13} className={checks.length ? "dk-think-icon" : undefined} /> News sub-agent
        <span className="micro text-muted">watches {codes.join(", ")} for sudden moves and finds the news behind them</span>
      </span>
      {checks.map((n) => (
        <div key={n.code} className="df__news" aria-live="polite">
          <span className="df-spin" aria-hidden="true" />
          Working on {n.code} ({n.pct >= 0 ? "+" : ""}
          {n.pct.toFixed(2)}% in 15 min): {STEP[n.step] ?? n.step}
        </div>
      ))}
      <MarketMovesList moves={moves} empty="No sudden move on this session's underlyings in the last few hours." />
    </section>
  );
};
