import { BaseFilter } from "../../../core/types/filter.types";

/** Conviction tier stored on a trade. Who manages it is `marketTelemetry.traderCode` (see TraderCode). */
export type TraderProfile = "HIGH_CONVICTION" | "STEP_GUARD";
export type TraderCode = "FIB_GOLDEN_TRADER" | "FLOW_MOMENTUM_TRADER" | "COMMODITY_DESK_TRADER";
export type TradeState = "RUNNING" | "EXITED";
export type BrokerStatus = "SIMULATED" | "PLACED" | "FILLED" | "REJECTED" | "ERROR";

export interface TraderPreset {
  code: string;
  name: string;
  shortLabel: string;
  badgeColor: string;
  methodology: string;
  entryLogic: string;
  trailLogic: string;
  strategies: string[];
  activeTradesCount: number;
  totalTradesCount: number;
  winRatePct: number;
  netPnl: number;
}

export interface TrailEvent {
  at: string;
  action: string;
  oldStop: number;
  newStop: number;
  oldTarget: number;
  newTarget: number;
  ltp: number;
  reason: string;
}

/**
 * Level set stored on a trade, in option-premium prices.
 * source "SETUP_SWING": levels of the real chart swing the Fib setup found; `underlying` holds the swing itself.
 * source "PLAN" (or missing, on older trades): multiples of the planned move; there is no swing.
 */
export interface FibLevels {
  source?: "SETUP_SWING" | "PLAN";
  swingLow?: number;
  swingHigh?: number;
  fib382?: number;
  fib500?: number;
  fib618: number;
  fib786?: number;
  fib100: number;
  fib1272: number;
  fib1618: number;
  underlying?: {
    swingLow: number;
    swingHigh: number;
    fib500: number;
    fib618: number;
    fib786: number;
    fib1272: number;
    fib1618: number;
  } | null;
  depth?: number | null;
  oiConfirm?: boolean | null;
  volumeConfirm?: boolean | null;
  why?: string | null;
}

export interface OAStrikeRow {
  strike: number;
  callOi: number;
  putOi: number;
  /** % change vs the snapshot ~15 min earlier; null when there is no earlier snapshot. */
  callOiChgPct: number | null;
  putOiChgPct: number | null;
  volumeRatio: number;
  role: "ACTIVE_STRIKE" | "CALL_OI_WALL" | "PUT_OI_WALL" | "CHAIN" | string;
}

/** Option-chain OI around a traded strike. Real only when `source` is "CHAIN_SNAPSHOT" (recorded chain). */
export interface OAAnalysis {
  source?: "CHAIN_SNAPSHOT";
  asOf?: string;
  spot?: number;
  pcr: number | null;
  maxPain: number | null;
  putOiSupportWall: number;
  callOiResistanceWall: number;
  oiBuildup: string;
  verdict: string;
  strikes: OAStrikeRow[];
}

export interface MarketTelemetry {
  traderCode?: string;
  traderName?: string;
  volumeRatio?: number;
  candleStructure?: string;
  momentumState?: string;
  atr1m?: number;
  supportLow?: number | null;
  upperWickRatio?: number;
  progressPct?: number;
  liveProgressPct?: number;
  rrNow?: number;
  peakPrice?: number;
  projectedTarget?: number;
  fibLevels?: FibLevels;
  oaAnalysis?: OAAnalysis | null;
  inRunnerMode?: boolean;
  sessionType?: string;
  exitSignal?: string | null;
  exitRecommendation?: string;
  recommendedExitPrice?: number;
}

export interface OptionCandle1m {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
  v?: number;
  oi?: number;
}

export interface ActiveTrade {
  id: number;
  sessionId: number;
  pickId: number;
  opportunityId: number;
  opportunityRef: string;
  userId: number;
  underlyingCode: string;
  optionType: "CE" | "PE";
  strike: number;
  expiry: string;
  instrumentKey: string | null;
  strategy: string | null;
  confidence: number;
  winRatePct: number;
  traderProfile: TraderProfile;
  sessionType: "MANUAL" | "SEMI_AUTO" | "FULL_AUTO";
  routeThroughUpstox: boolean;
  lots: number;
  lotUnits: number;
  quantity: number;
  plannedEntry: number;
  entryAt: number;
  capitalUsed: number;
  initialStop: number;
  initialTarget: number;
  currentStop: number;
  currentTarget: number;
  lastPrice: number;
  peakPrice: number;
  troughPrice: number;
  entryOrderId: string | null;
  exitOrderId: string | null;
  brokerStatus: BrokerStatus;
  brokerError: string | null;
  tradeState: TradeState;
  exitReason: string | null;
  exitPrice: number | null;
  grossPnl: number;
  charges: number;
  netPnl: number;
  pnlPct: number;
  enteredAt: string;
  exitedAt: string | null;
  holdUntil: string;
  trailEvents: TrailEvent[];
  marketTelemetry: MarketTelemetry;
  candles1m: OptionCandle1m[];
  status: "ACTIVE" | "DELETED";
  createdAt: string;
}

export interface TradeLiveSnapshot {
  tradeId: number;
  serverTime: string;
  trade: ActiveTrade;
}

export interface LotSuggestion {
  sessionId: number;
  pickId: number;
  entryAt: number;
  stop: number;
  target: number;
  entryMax: number;
  lotUnits: number;
  suggestedLots: number;
  maxLotsByCash: number;
  maxLotsByRisk: number;
  maxAffordableLots: number;
  quantity: number;
  capitalRequired: number;
  riskAmount: number;
  rewardAmount: number;
  expectedNet: number;
  availableCapital: number;
  remainingLossBudget: number;
  winProbPct: number;
  activeTradesCount: number;
  maxParallelTrades: number;
  canEnter: boolean;
  blockReason: string | null;
}

export interface TradeCreatePayload {
  sessionId: number;
  pickId: number;
  entryAt?: number;
  lots?: number;
  initialStop?: number;
  initialTarget?: number;
}

export interface TradeDirectInsertPayload {
  sessionId?: number;
  opportunityId?: number;
  traderCode: string;
  underlyingCode: string;
  optionType: "CE" | "PE";
  strike: number;
  expiry?: string;
  instrumentKey?: string | null;
  entryAt: number;
  initialStop: number;
  initialTarget: number;
  lots: number;
  strategy?: string;
  confidence?: number;
  swingLow?: number;
  swingHigh?: number;
  oaAnalysis?: OAAnalysis | null;
}

export interface TradeAdjustPayload {
  currentStop?: number;
  currentTarget?: number;
  reason?: string;
}

export interface TradeExitPayload {
  exitPrice?: number;
  reason?: string;
}

export interface TradeSearchFilter extends BaseFilter {
  sessionId?: number;
  underlyingCode?: string;
  tradeState?: TradeState;
  traderProfile?: TraderProfile;
}

