import { BaseFilter } from "../../../core/types/filter.types";

export type SessionScope = "INDEX" | "COMMODITY";
export type SessionType = "FULL_AUTO" | "SEMI_AUTO" | "MANUAL";
export type SessionStatus = "ACTIVE" | "CLOSED" | "EXPIRED";
/** Entry strictness of a session (which opportunities it accepts). Default LOW. */
export type RiskLevel = "LOW" | "MEDIUM" | "HIGH";

export interface RiskProfile {
  level: RiskLevel;
  setups: string[];
  minRewardRisk: number;
  allowAgainstTrend: boolean;
  summary: string;
}

export interface TradingSession {
  id: number;
  name: string;
  tradeDate: string;
  userId: number;
  capital: number;
  realizedPnl: number;
  currentCapital: number;
  maxLossPercentage: number;
  scope: SessionScope;
  underlyings: string[];
  commodityItems: string[];
  traders?: string[];
  /** Opportunity finders feeding the session (their optionTypes cover its scope). */
  finders?: string[];
  riskLevel: RiskLevel;
  riskProfile?: RiskProfile | null;
  sessionType: SessionType;
  routeThroughUpstox: boolean;
  sessionStatus: SessionStatus;
  /** Trading hours of the session (ISO, UTC): nothing is offered before startAt; the loop closes it at closeAt. */
  startAt: string;
  closeAt: string;
  haltReason: string | null;
  haltedAt: string | null;
  closedAt: string | null;
  status: "ACTIVE" | "DELETED";
  createdAt: string;
  /** Newest tick of the server-side loop; only present on GET /sessions/{id} while a loop is running. */
  loop?: SessionLoop | null;
}

export interface TradingSessionCreatePayload {
  name?: string;
  tradeDate: string;
  userId: number;
  capital: number;
  maxLossPercentage?: number;
  scope: SessionScope;
  underlyings?: string[];
  commodityItems?: string[];
  traders?: string[];
  /** Opportunity finders feeding the session (their optionTypes cover its scope). */
  finders?: string[];
  riskLevel?: RiskLevel;
  sessionType?: SessionType;
  routeThroughUpstox?: boolean;
  /** HH:MM IST. Blank = now if created at/after 09:25, else 09:15. */
  startTime?: string;
  /** HH:MM IST. Blank = 15:45. */
  closeTime?: string;
}

export interface TradingSessionUpdatePayload {
  name?: string;
  capital?: number;
  maxLossPercentage?: number;
  underlyings?: string[];
  commodityItems?: string[];
  traders?: string[];
  /** Opportunity finders feeding the session (their optionTypes cover its scope). */
  finders?: string[];
  riskLevel?: RiskLevel;
  sessionType?: SessionType;
  routeThroughUpstox?: boolean;
  sessionStatus?: SessionStatus;
  startTime?: string;
  closeTime?: string;
}

export interface TradingSessionSearchFilter extends BaseFilter {
  scope?: SessionScope;
  sessionStatus?: SessionStatus;
  sessionType?: SessionType;
  userId?: number;
  tradeDate?: string;
}

// ───────────────────────── MANUAL session loop ─────────────────────────
export type PickState = "OFFERED" | "LOCKED" | "EXPIRED";

/** One trade offered to the trader, sized to the session. Prices are option premium; money fields are rupees. */
/** The timeframes a pick's setup was confirmed on: 15-minute trend, 1-minute trigger (5-minute = the setup). */
export interface PickTimeframes {
  "15m"?: { trend: "UP" | "DOWN" | "FLAT"; source: "15m" | "15m+prev" | "5m-proxy" | "none" };
  "1m"?: { close: number | null; ema9: number | null; trigger: number | null };
}

export interface SessionPick {
  id: number;
  timeframes?: PickTimeframes | null;
  sessionId: number;
  opportunityId: number;
  opportunityRef: string;
  underlyingCode: string;
  optionType: "CE" | "PE";
  strike: number;
  expiry: string;
  instrumentKey: string | null;
  strategy: string | null;
  traderCode?: string | null;
  traderName?: string | null;
  confidence: number;
  entry: number;
  entryMax: number;
  stop: number;
  target: number;
  stopPct: number;
  targetPct: number;
  rewardRisk: number;
  lots: number;
  lotUnits: number;
  quantity: number;
  capitalRequired: number;
  riskAmount: number;
  rewardAmount: number;
  expectedNet: number;
  capitalAtPick: number;
  availableAtPick: number;
  reasons: string[];
  risks: string[];
  pickState: PickState;
  signalAt: string;
  holdUntil: string;
  offeredAt: string;
  expiresAt: string;
  lockedAt: string | null;
  /** The item's live premium when Trade Lock was pressed (null if no quote came back in time). */
  lockedPrice: number | null;
  /** ActiveTrade.id once entered into a Trader loop. */
  tradeId?: number | null;
  /** Win probability the size was scaled by, and the share of free capital this pick uses. */
  winProbPct: number;
  usagePct: number;
  /** Seconds until the opportunity behind this pick expires (0 once LOCKED / EXPIRED). */
  secondsLeft: number;
  /** The session manager's after-the-fact check, written by "Analyse" on its batch. */
  outcomeAnalysis?: PickAnalysis | null;
  createdAt: string;
}

export type ManagerVerdict =
  | "TAKEN_WIN"
  | "TAKEN_LOSS"
  | "TAKEN_RUNNING"
  | "LOCKED_NOT_ENTERED"
  | "MISSED_WINNER"
  | "GOOD_SKIP"
  | "NO_MOVE"
  | "PENDING";

export interface PickAnalysis {
  managerVerdict: ManagerVerdict;
  opportunityOutcome: "TARGET_HIT" | "STOP_HIT" | "EXPIRED" | "PENDING";
  note: string;
  achievedPct: number | null;
  maxGainPct: number | null;
  hitAt: string | null;
  candleError: string | null;
  trade: { tradeId: number; tradeState: string; netPnl: number; exitReason: string | null; verdict: string | null } | null;
  analysedAt: string;
}

export type BatchVerdict = "SUCCESS" | "FAILURE" | "MIXED" | "NO_MOVE" | "PENDING";

/** Every pick one loop pass offered, with the session manager's verdict once analysed. */
export interface SessionBatch {
  batchKey: string;
  batchNo: number;
  offeredAt: string;
  picks: SessionPick[];
  analysedAt: string | null;
  verdict: BatchVerdict | null;
  summary: {
    picks: number;
    locked: number;
    entered: number;
    note?: string;
    hits?: number;
    misses?: number;
    noMove?: number;
    taken?: number;
    pending?: number;
    resolved?: number;
  };
}

/** The session manager's pick of the open offers, and why. */
export interface SessionManagerAdvice {
  pickId: number;
  headline: string;
  reasons: string[];
  cautions: string[];
  alternatives: number;
}

export interface SessionCapital {
  capital: number;
  realizedPnl: number;
  currentCapital: number;
  committedPremium: number;
  availableCapital: number;
  maxLossAmount: number;
  lossUsed: number;
  committedRisk: number;
  remainingLossBudget: number;
  lockedTrades: number;
  activeTradesCount?: number;
  maxParallelTrades?: number;
  activeTradeIds?: number[];
}

export type SessionLoopStateName =
  | "SCHEDULED"
  | "PICK_READY"
  | "WAITING"
  | "HALTED"
  | "SESSION_CLOSED"
  | "UNSUPPORTED_TYPE";

export interface SessionLoop {
  sessionId: number;
  serverTime: string;
  state: SessionLoopStateName;
  message: string;
  /** Open offers, best first: the rows of the session table. Each stays open until its opportunity expires. */
  picks: SessionPick[];
  /** Auto-locked or manually locked picks awaiting entry confirmation. */
  lockedPicks?: SessionPick[];
  capital: SessionCapital;
  scanned: { candidates: number; excluded: Record<string, number> };
  /** Best suggestion right now (only while picks are open). */
  manager?: SessionManagerAdvice | null;
}

export interface SessionPickSearchFilter extends BaseFilter {
  pickState?: PickState;
}
