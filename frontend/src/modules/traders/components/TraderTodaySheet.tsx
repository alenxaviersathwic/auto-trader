import React, { useEffect, useState } from "react";
import { ChevronLeft, ChevronRight, Clock, TrendingDown, TrendingUp, X } from "lucide-react";
import { FibWatch, OpportunityCardItem, TempView } from "../../opportunity-finder/types/opportunities.types";
import { TRADER_META } from "../../trade-history/components/traderMeta";
import { TraderCode } from "../../trade-history/types/trades.types";
import { FIB_STAGE, useIndexToday } from "./useIndexToday";

const hhmm = (iso: string): string =>
  new Date(iso).toLocaleTimeString("en-IN", { timeZone: "Asia/Kolkata", hour: "2-digit", minute: "2-digit", hour12: false });
const n0 = (v?: number | null) => (v == null ? "--" : Math.round(v).toLocaleString("en-IN"));

/** 0 -> 1 retracement of the swing, with the 0.50-0.618 pocket shaded, the deepest pullback and price now marked. */
const RetraceBar: React.FC<{ w: FibWatch }> = ({ w }) => {
  if (w.nowDepth == null || w.depth == null) return null;
  const pct = (v: number) => `${Math.max(0, Math.min(100, (v / 0.9) * 100))}%`;
  return (
    <div className="iv-retrace" aria-label={`Retracement now ${w.nowDepth.toFixed(2)}, deepest ${w.depth.toFixed(2)}`}>
      <div className="iv-retrace__track">
        <span className="iv-retrace__pocket" style={{ left: pct(0.5), width: `calc(${pct(0.618)} - ${pct(0.5)})` }} />
        <span className="iv-retrace__inval" style={{ left: pct(0.786) }} />
        <span className="iv-retrace__deep" style={{ left: pct(w.depth) }} title={`deepest pullback ${w.depth.toFixed(2)}`} />
        <span className="iv-retrace__now" style={{ left: pct(w.nowDepth) }} title={`price now ${w.nowDepth.toFixed(2)}`} />
      </div>
      <div className="iv-retrace__ticks">
        <span style={{ left: pct(0) }}>{w.side === "CE" ? "high" : "low"}</span>
        <span style={{ left: pct(0.382) }}>.382</span>
        <span style={{ left: pct(0.5) }}>.5</span>
        <span style={{ left: pct(0.618) }}>.618</span>
        <span style={{ left: pct(0.786) }}>.786</span>
      </div>
    </div>
  );
};

const CONF_TONE = { HIGH: "green", MEDIUM: "blue", LOW: "amber" } as const;

/** The human-style temporary view: what it expects, what happens on a break, where it is wrong. */
const ViewBlock: React.FC<{ v: TempView }> = ({ v }) => {
  const row = (tag: string, cls: string, s: TempView["steps"][number]) => (
    <li key={`${tag}-${s.level}`} className={`tv-step tv-step--${cls}`}>
      <span className="tv-step__tag">{tag}</span>
      <span className="tv-step__lvl mono">{n0(s.level)}</span>
      <span className="tv-step__label">{s.label}</span>
      <span className="tv-step__dist mono">
        {s.distance >= 0 ? "+" : ""}
        {Math.round(s.distance)}
        {s.distanceAtr != null ? ` · ${Math.abs(s.distanceAtr).toFixed(1)} ATR` : ""}
      </span>
      {s.if && <span className="tv-step__if">if {s.if}</span>}
    </li>
  );
  return (
    <div className="tv">
      <div className="tv__top">
        <span className="ag-label">Temporary view</span>
        <span className={`te-pill te-pill--${CONF_TONE[v.confidence]}`}>{v.confidence} confidence</span>
      </div>
      <p className="tv__text">{v.text}</p>
      <ol className="tv__steps">
        {v.range && row("support", "range", v.range.support)}
        {v.range && row("resistance", "range", v.range.resistance)}
        {v.range
          ? v.steps.map((s, i) => row(i === 0 ? "breakdown" : "breakout", i === 0 ? "down" : "up", s))
          : v.steps.map((s, i) => row(i === 0 ? "target" : "next", v.bias === "BEARISH" ? "down" : "up", s))}
        {v.invalidation && row("wrong", "wrong", v.invalidation)}
      </ol>
    </div>
  );
};

/** One index inside the trader's sheet: bias, what this trader waits for, why, and recent scans. */
const IndexBlock: React.FC<{ card: OpportunityCardItem; trader: TraderCode }> = ({ card, trader }) => {
  const t = useIndexToday(card, trader);
  const nb = t.now?.bias;
  return (
    <section className="tts-idx" id={`tts-${card.code}`} aria-label={card.code}>
      <header className="tts-idx__head">
        <span className="tts-idx__code">{card.code}</span>
        <span className="mono text-secondary">{n0(t.spot)}</span>
        {t.hasScan && (
          <span className="tts-idx__bias">
            {nb ? (
              <span className={`iv-bias iv-bias--${nb.toLowerCase()}`} title="The last ~60 minutes">
                {nb === "BULLISH" ? <TrendingUp size={12} /> : nb === "BEARISH" ? <TrendingDown size={12} /> : null}
                {nb}
              </span>
            ) : (
              <span className="iv-bias" title="Scans from before the backend restart have no last-hour read">--</span>
            )}
          </span>
        )}
      </header>
      {t.now && (
        <span className={`tts-now tts-now--${t.now.change >= 0 ? "up" : "down"}`}>
          last {t.now.minutes} min {t.now.change >= 0 ? "+" : ""}
          {Math.round(t.now.change).toLocaleString("en-IN")} pts ({t.now.changePct >= 0 ? "+" : ""}
          {t.now.changePct.toFixed(2)}%)
        </span>
      )}

      {t.view && <ViewBlock v={t.view} />}

      {!t.hasScan ? (
        <span className="micro text-muted">{t.loading ? "Loading the latest scan…" : "No scan for this index yet today."}</span>
      ) : (
        <>
          <div className="tts-wait">
            <span className="ag-label">Waiting for</span>
            {trader === "FIB_GOLDEN_TRADER" ? (
              t.wait.fib.length === 0 ? (
                <span className="micro text-muted">No Fib swing reported by this scan.</span>
              ) : (
                t.wait.fib.map((w) => (
                  <div key={w.side} className="iv-watch">
                    <div className="iv-watch__top">
                      <span className={`te-pill ${w.side === "CE" ? "te-pill--green" : "te-pill--red"}`}>{w.side}</span>
                      <span className={`te-pill ${FIB_STAGE[w.stage].tone ? `te-pill--${FIB_STAGE[w.stage].tone}` : ""}`}>
                        {FIB_STAGE[w.stage].label}
                      </span>
                    </div>
                    <span className="iv-watch__text">{w.text}</span>
                    {w.pocket && (
                      <span className="micro text-muted mono">
                        swing {n0(w.side === "CE" ? w.swingLow : w.swingHigh)} → {n0(w.side === "CE" ? w.swingHigh : w.swingLow)}
                        {" · "}pocket {n0(w.pocket[0])}–{n0(w.pocket[1])} · invalid {n0(w.invalidation)}
                      </span>
                    )}
                    <RetraceBar w={w} />
                  </div>
                ))
              )
            ) : t.wait.flow.length === 0 ? (
              <span className="micro text-muted">{t.wait.idle}</span>
            ) : (
              <ul className="iv-notes">
                {t.wait.flow.map((r) => (
                  <li key={`${r.name}/${r.side}`}>
                    <span className="mono text-muted">{hhmm(r.at)}</span>
                    <strong>
                      {r.name.replace(/_/g, " ")} {r.side}
                    </strong>
                    <span>{r.reason}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {t.now && (
            <details className="tts-more" open>
              <summary>
                Why {t.now.bias.toLowerCase()} (score {t.now.score > 0 ? "+" : ""}
                {t.now.score})
              </summary>
              <ul className="iv-votes">
                {t.now.votes.map((v) => (
                  <li key={v.label}>
                    <span className={`iv-vote iv-vote--${v.vote > 0 ? "up" : v.vote < 0 ? "down" : "flat"}`}>
                      {v.vote > 0 ? `+${v.vote}` : v.vote < 0 ? v.vote : "0"}
                    </span>
                    <span className="iv-votes__label">{v.label}</span>
                    <span className="iv-votes__value">{v.value}</span>
                  </li>
                ))}
              </ul>
            </details>
          )}

          <details className="tts-more">
            <summary>Recent scans</summary>
            <ol className="iv-scans">
              {t.scans.map((s) => (
                <li key={s.id}>
                  <span className="mono text-muted">
                    <Clock size={10} /> {hhmm(s.at)}
                  </span>
                  <span className={`iv-res iv-res--${s.result === "SAVED" ? "ok" : s.result === "NO_SETUP" ? "idle" : "warn"}`}>
                    {s.result.replace(/_/g, " ")}
                  </span>
                  <span className="iv-scans__text">{s.text}</span>
                </li>
              ))}
            </ol>
          </details>
        </>
      )}
    </section>
  );
};

/** One row of the index list: code, price, last-hour bias, the view's levels and what the trader waits for. */
const IndexRow: React.FC<{ card: OpportunityCardItem; trader: TraderCode; onOpen: () => void }> = ({ card, trader, onOpen }) => {
  const t = useIndexToday(card, trader);
  const nb = t.now?.bias;
  const v = t.view;
  const levels = !v
    ? "--"
    : v.range
      ? `${n0(v.range.support.level)} – ${n0(v.range.resistance.level)}`
      : `${v.bias === "BEARISH" ? "↓" : "↑"} ${n0(v.steps[0]?.level)}${v.steps[1] ? ` › ${n0(v.steps[1].level)}` : ""}`;
  return (
    <li>
      <button type="button" className="tts-row" onClick={onOpen} aria-label={`Open ${card.code} analysis`}>
        <span className="tts-row__code">{card.code}</span>
        <span className="tts-row__spot mono">{n0(t.spot)}</span>
        <span className={`tt-bias tt-bias--${nb ? nb.toLowerCase() : "none"}`}>
          {nb === "BULLISH" ? "▲ bull" : nb === "BEARISH" ? "▼ bear" : nb === "MIXED" ? "◆ mixed" : "--"}
        </span>
        <span className="tts-row__view mono" title={v?.text}>{levels}</span>
        {v && <span className={`te-pill te-pill--${CONF_TONE[v.confidence]} tts-row__conf`}>{v.confidence}</span>}
        <span className={`tts-row__wait ${t.wait.tone ? `tt-tone--${t.wait.tone}` : ""}`}>{t.loading ? "…" : t.wait.short}</span>
        <ChevronRight size={14} className="tts-row__go" />
      </button>
    </li>
  );
};

interface Props {
  trader: TraderCode;
  cards: OpportunityCardItem[];
  onClose: () => void;
}

/** One opportunity trader's view of today: every index it scans, the bias there and what it is waiting for. */
export const TraderTodaySheet: React.FC<Props> = ({ trader, cards, onClose }) => {
  const meta = TRADER_META[trader];
  const [selected, setSelected] = useState<string | null>(null);
  const card = cards.find((c) => c.code === selected) ?? null;

  useEffect(() => {
    // Escape steps back from an index to the list first, then closes the sheet
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && (selected ? setSelected(null) : onClose());
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose, selected]);

  return (
    <div className="drawer-overlay open" onClick={onClose}>
      <aside className="drawer iv" role="dialog" aria-modal="true" aria-label={`${meta.name} today`} onClick={(e) => e.stopPropagation()}>
        <header className="drawer-header iv-head">
          <div className="iv-head__id">
            <span className="ag-eyebrow">Temporary trend · last hour · overall trend is in Research Engine</span>
            <h2 className="tts-title">
              <span className={`badge ${meta.badgeClass} mono`}>{meta.tag}</span> {meta.name}
            </h2>
          </div>
          <button type="button" className="sd2-back" onClick={onClose} aria-label="Close">
            <X size={15} />
          </button>
        </header>
        <div className="drawer-body iv-body">
          {cards.length === 0 ? (
            <span className="micro text-muted">No index is being scanned today.</span>
          ) : card ? (
            <>
              <button type="button" className="tts-back" onClick={() => setSelected(null)}>
                <ChevronLeft size={13} /> All indices
              </button>
              <IndexBlock key={card.code} card={card} trader={trader} />
            </>
          ) : (
            <ul className="tts-list" aria-label="Indices">
              {cards.map((c) => (
                <IndexRow key={c.code} card={c} trader={trader} onOpen={() => setSelected(c.code)} />
              ))}
            </ul>
          )}
        </div>
      </aside>
    </div>
  );
};
