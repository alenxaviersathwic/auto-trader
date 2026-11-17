import { TraderCode } from "../types/trades.types";

/** The traders. Mirrors backend trade_history/service/trader_presets.py. */
export const TRADER_CODES: TraderCode[] = ["FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER", "COMMODITY_DESK_TRADER"];
/** What an old session with no / unknown traders stored means: the original two (never the Commodity Desk). */
export const DEFAULT_TRADER_CODES: TraderCode[] = ["FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER"];
export const DESK_CODE: TraderCode = "COMMODITY_DESK_TRADER";

export interface TraderMeta {
  code: TraderCode;
  name: string;
  tag: string;
  badgeClass: string;
  /** What the trader checks before it takes a trade, in order. */
  checks: string[];
  /** How it manages the position once entered. */
  manages: string;
}

export const TRADER_META: Record<TraderCode, TraderMeta> = {
  FIB_GOLDEN_TRADER: {
    code: "FIB_GOLDEN_TRADER",
    name: "Fib Golden-Pocket Trader",
    tag: "FIB + PA + OI + VOL",
    badgeClass: "badge--cyan",
    checks: [
      "Pullback into the 0.50–0.618 pocket of a 3 ATR swing",
      "Price action: a corrective pullback, then a pin bar, engulfing or inside-bar break at the pocket",
      "Option-chain OI: wall behind the stop, none blocking the target",
      "Volume: quiet pullback, active turn bar",
    ],
    manages:
      "Stop behind 0.786. Locks half the move at 80% progress, then steps the target to the 1.272 and 1.618 extensions.",
  },
  FLOW_MOMENTUM_TRADER: {
    code: "FLOW_MOMENTUM_TRADER",
    name: "Flow & Momentum Trader",
    tag: "FLOW + MOMENTUM",
    badgeClass: "badge--green",
    checks: [
      "Noise-area breakout, FII open drive, late-day momentum",
      "VWAP pullback / range breakout only inside an active breakout",
      "Day type, dealer gamma and 1-minute timing agree",
    ],
    manages:
      "Momentum setups: breakeven at +1.5R, then trail 2R under the peak with no fixed target. Others: step guard.",
  },
  COMMODITY_DESK_TRADER: {
    code: "COMMODITY_DESK_TRADER",
    name: "Commodity Desk",
    tag: "DESK + AGENTS",
    badgeClass: "badge--amber",
    checks: [
      "Session clock: MCX phase (Asia / Europe / US open), EIA and US data releases",
      "Price structure on 1, 5 and 15-minute futures: trend pullback, fresh range break, Fib pocket",
      "Option chain of the traded expiry: PCR, OI walls, ATM liquidity",
      "News: Research Engine read and sudden-move explanations",
      "Code risk gate, then an LLM head trader writes its reasoning and takes one setup or waits",
    ],
    manages:
      "Momentum management: breakeven at +1.5R, then trail 2R under the peak.",
  },
};

const LEGACY: Record<string, TraderCode> = {
  ORB_WAVE_TRADER: "FLOW_MOMENTUM_TRADER",
  FLOW_VWAP_TRADER: "FLOW_MOMENTUM_TRADER",
};

/** Current trader code for a stored one (old three-trader codes map to Flow & Momentum); null when unknown. */
export function normalizeTraderCode(code?: string | null): TraderCode | null {
  if (!code) return null;
  const c = LEGACY[code] ?? code;
  return c === "FIB_GOLDEN_TRADER" || c === "FLOW_MOMENTUM_TRADER" || c === "COMMODITY_DESK_TRADER" ? c : null;
}

/** Trader that owns a strategy name: the Commodity Desk for DESK_* setups, the Fib trader for the Fib golden-pocket
 *  setup, Flow & Momentum otherwise. */
export function traderForStrategy(strategy?: string | null): TraderCode {
  const s = (strategy ?? "").toLowerCase();
  if (s.startsWith("desk_")) return "COMMODITY_DESK_TRADER";
  return s === "fib_golden_pocket" || /fib|golden[ -]pocket|retracement/.test(s)
    ? "FIB_GOLDEN_TRADER"
    : "FLOW_MOMENTUM_TRADER";
}

/** De-duplicated current codes in display order; empty or unknown means the original two traders. */
export function normalizeTraderCodes(codes?: string[] | null): TraderCode[] {
  const wanted = new Set((codes ?? []).map(normalizeTraderCode));
  const out = TRADER_CODES.filter((c) => wanted.has(c));
  return out.length > 0 ? out : [...DEFAULT_TRADER_CODES];
}

/** A session is run by one session manager. The manager's duty is the same for INDEX and COMMODITY sessions (no
 *  commodity manager); the session's opportunities come from the finders whose optionTypes cover its scope. */
export interface SessionManagerMeta {
  traderCode: TraderCode;
  name: string;
  /** How this manager runs a session, in one line. */
  trades: string;
  /** Needs live data (chain, news, LLM): not offered in the backtest. */
  liveOnly?: boolean;
}

/** Order = display order; the first one is the default for new sessions and backtests. */
export const SESSION_MANAGERS: SessionManagerMeta[] = [
  {
    traderCode: "FLOW_MOMENTUM_TRADER",
    name: "Indian Quant Desk",
    trades: "ranks the finders' picks, sizes them to capital, analyses batches; its autopsy learns from its own trades.",
  },
  {
    traderCode: "FIB_GOLDEN_TRADER",
    name: "My Experience",
    trades: "same duty, separate memory: its autopsy learns only from the sessions it runs.",
  },
];

/** Session managers. The scope no longer matters: the manager's duty is the same for every market. */
export const managersFor = (_scope?: string | null): SessionManagerMeta[] => SESSION_MANAGERS;

export const managerFor = (code: TraderCode): SessionManagerMeta =>
  SESSION_MANAGERS.find((m) => m.traderCode === code) ?? SESSION_MANAGERS[0];
