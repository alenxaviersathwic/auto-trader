import React from "react";
import { ChevronRight, ScanSearch } from "lucide-react";
import { OpportunityCardItem, TempView } from "../../opportunity-finder/types/opportunities.types";
import { TraderCode } from "../../trade-history/types/trades.types";
import { useIndexToday } from "./useIndexToday";

const ARROW = { BULLISH: "▲", BEARISH: "▼", MIXED: "◆" } as const;
const WORD = { BULLISH: "bull", BEARISH: "bear", MIXED: "mixed" } as const;

const lvl = (v: number) => Math.round(v).toLocaleString("en-IN");

/** "→ 24,500 › 24,450" for a directional view, "24,550–24,600" for a range. */
const viewShort = (v: TempView | null): string => {
  if (!v) return "--";
  if (v.range) return `${lvl(v.range.support.level)}–${lvl(v.range.resistance.level)}`;
  const [t1, t2] = v.steps;
  return `${v.bias === "BEARISH" ? "↓" : "↑"} ${lvl(t1.level)}${t2 ? ` › ${lvl(t2.level)}` : ""}`;
};

const Row: React.FC<{ card: OpportunityCardItem; trader: TraderCode }> = ({ card, trader }) => {
  const t = useIndexToday(card, trader);
  const now = t.now?.bias;
  return (
    <li className="tt-row">
      <span className="tt-row__code">{card.code}</span>
      <span
        className={`tt-bias tt-bias--${now ? now.toLowerCase() : "none"}`}
        title={t.now ? `Last ${t.now.minutes} min: ${t.now.change >= 0 ? "+" : ""}${Math.round(t.now.change)} pts` : "No last-hour read yet"}
      >
        {now ? `${ARROW[now]} ${WORD[now]}` : "--"}
      </span>
      <span className="tt-row__view mono" title={t.view?.text ?? "No temporary view yet"}>
        {viewShort(t.view)}
      </span>
      <span className={`tt-row__wait ${t.wait.tone ? `tt-tone--${t.wait.tone}` : ""}`}>{t.loading ? "…" : t.wait.short}</span>
    </li>
  );
};

interface Props {
  trader: TraderCode;
  cards: OpportunityCardItem[];
  onOpen: () => void;
}

/** Inside a trader card: index by index, the temporary (last-hour) trend and what this trader is waiting for. Click for the full sheet. */
export const TraderTodayStrip: React.FC<Props> = ({ trader, cards, onOpen }) => (
  <button type="button" className="tt" onClick={onOpen} aria-label="Open today's view across indices">
    <span className="tt__head">
      <ScanSearch size={12} /> Temporary trend · last hour
      <span className="tt__open">
        Open view <ChevronRight size={12} />
      </span>
    </span>
    {cards.length === 0 ? (
      <span className="micro text-muted">Nothing is being scanned today. Start a session to start its scanners.</span>
    ) : (
      <ul className="tt__list">
        {cards.map((c) => (
          <Row key={c.code} card={c} trader={trader} />
        ))}
      </ul>
    )}
  </button>
);
