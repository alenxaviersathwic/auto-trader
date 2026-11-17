import React from "react";
import { ExternalLink, TrendingDown, TrendingUp } from "lucide-react";
import { MarketMove } from "../types/commodityDesk.types";

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });

const CAUSE: Record<string, { label: string; badge: string }> = {
  NEWS: { label: "NEWS FOUND", badge: "badge--cyan" },
  NO_CLEAR_NEWS: { label: "NO CLEAR NEWS", badge: "badge--slate" },
  UNCLEAR: { label: "UNCHECKED", badge: "badge--amber" },
};

/** Sudden moves on scanned indices / commodities and what the news sub-agent found for each. */
export const MarketMovesList: React.FC<{ moves: MarketMove[]; empty?: string }> = ({ moves, empty }) =>
  moves.length === 0 ? (
    <span className="micro text-muted">{empty ?? "No sudden move in the last few hours."}</span>
  ) : (
    <ul className="dk-moves">
      {moves.map((m) => {
        const c = m.cause ? CAUSE[m.cause] : null;
        return (
          <li key={m.id} className="dk-move">
            <div className="dk-move__head">
              {m.direction === "UP" ? <TrendingUp size={13} className="text-green" /> : <TrendingDown size={13} className="text-red" />}
              <span className="ticker">{m.underlyingCode}</span>
              <span className={`mono ${m.movePct >= 0 ? "text-green" : "text-red"}`}>
                {m.movePct >= 0 ? "+" : ""}
                {m.movePct.toFixed(2)}%
              </span>
              <span className="mono micro text-muted">
                {m.priceFrom.toLocaleString("en-IN")} → {m.priceTo.toLocaleString("en-IN")} in {m.windowMin} min ·{" "}
                {hhmm(m.detectedAt)}
              </span>
              {m.newsState === "PENDING" ? (
                <span className="badge badge--blue">CHECKING NEWS</span>
              ) : (
                c && <span className={`badge ${c.badge}`}>{c.label}</span>
              )}
            </div>
            {m.summary && <p className="dk-move__summary">{m.summary}</p>}
            {m.headlines.length > 0 && (
              <ul className="dk-move__heads">
                {m.headlines.slice(0, 3).map((h) => (
                  <li key={h.title}>
                    {h.url ? (
                      <a href={h.url} target="_blank" rel="noreferrer">
                        {h.title} <ExternalLink size={10} />
                      </a>
                    ) : (
                      h.title
                    )}
                    {h.source && <span className="text-muted"> · {h.source}</span>}
                  </li>
                ))}
              </ul>
            )}
          </li>
        );
      })}
    </ul>
  );
