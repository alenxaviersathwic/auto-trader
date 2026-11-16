import { TraderCode } from "../types/trades.types";

/** The two traders. Mirrors backend trades/service/trader_presets.py. */
export const TRADER_CODES: TraderCode[] = ["FIB_GOLDEN_TRADER", "FLOW_MOMENTUM_TRADER"];

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
    tag: "FIB + OI + VOL",
    badgeClass: "badge--cyan",
    checks: [
      "Pullback into the 0.50–0.618 pocket of a 3 ATR swing",
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
      "Noise-area breakout, inside bar, FII open drive, late-day momentum",
      "VWAP pullback / range breakout only inside an active breakout",
      "Day type, dealer gamma and 1-minute timing agree",
    ],
    manages:
      "Momentum setups: breakeven at +1.5R, then trail 2R under the peak with no fixed target. Others: step guard.",
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
  return c === "FIB_GOLDEN_TRADER" || c === "FLOW_MOMENTUM_TRADER" ? c : null;
}

/** Trader that owns a strategy name: the Fib trader for the Fib golden-pocket setup, Flow & Momentum otherwise. */
export function traderForStrategy(strategy?: string | null): TraderCode {
  const s = (strategy ?? "").toLowerCase();
  return s === "fib_golden_pocket" || /fib|golden[ -]pocket|retracement/.test(s)
    ? "FIB_GOLDEN_TRADER"
    : "FLOW_MOMENTUM_TRADER";
}

/** De-duplicated current codes in display order; empty or unknown means both traders. */
export function normalizeTraderCodes(codes?: string[] | null): TraderCode[] {
  const wanted = new Set((codes ?? []).map(normalizeTraderCode));
  const out = TRADER_CODES.filter((c) => wanted.has(c));
  return out.length > 0 ? out : [...TRADER_CODES];
}
