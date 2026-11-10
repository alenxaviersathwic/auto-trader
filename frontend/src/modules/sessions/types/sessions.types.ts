import { BaseFilter } from "../../../core/types/filter.types";

export type SessionScope = "INDEX" | "COMMODITY";
export type SessionType = "FULL_AUTO" | "SEMI_AUTO" | "MANUAL";
export type SessionStatus = "ACTIVE" | "CLOSED" | "EXPIRED";

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
export interface SessionPick {
  id: number;
  sessionId: number;
  opportunityId: number;
  opportunityRef: string;
  underlyingCode: string;
  optionType: "CE" | "PE";
  strike: number;
  expiry: string;
  instrumentKey: string | null;
  strategy: string | null;
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
  createdAt: string;
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
}

export interface SessionPickSearchFilter extends BaseFilter {
  pickState?: PickState;
}
