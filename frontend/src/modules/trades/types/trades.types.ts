import { BaseFilter } from "../../../core/types/filter.types";

export type TraderProfile = "HIGH_CONVICTION" | "STEP_GUARD";
export type TradeState = "RUNNING" | "EXITED";
export type BrokerStatus = "SIMULATED" | "PLACED" | "FILLED" | "REJECTED" | "ERROR";

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

export interface MarketTelemetry {
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
  inRunnerMode?: boolean;
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

