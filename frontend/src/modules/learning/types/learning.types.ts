import { BaseFilter } from "../../../core/types/filter.types";

export type AutopsyVerdict =
  | "RAN_TO_TARGET"
  | "PROTECTED_PROFIT"
  | "WON_BUT_GAVE_BACK"
  | "FEES_ATE_PROFIT"
  | "GAVE_BACK_WINNER"
  | "CUT_EARLY"
  | "NEVER_WORKED"
  | "STOPPED_OUT";

/** What one finished trade did and what it taught (backend learning/service/autopsy_agent.py). */
export interface TradeAutopsy {
  id: number;
  tradeId: number;
  sessionId: number;
  setup: string;
  traderCode: string | null;
  underlyingCode: string;
  optionType: "CE" | "PE";
  outcome: "WIN" | "LOSS";
  verdict: AutopsyVerdict;
  rMultiple: number;
  mfeR: number;
  maeR: number;
  givebackPct: number | null;
  netPnl: number;
  plannedTargetPct: number | null;
  tags: string[];
  wentRight: string[];
  wentWrong: string[];
  lessons: string[];
  details: {
    riskPerUnit?: number;
    plannedR?: number | null;
    minutesToCloseAtEntry?: number | null;
    heldMinutes?: number | null;
    exitReason?: string | null;
    grossPnl?: number;
  };
  learning: {
    scorecardBefore?: "ACTIVE" | "PAUSED";
    scorecardAfter?: "ACTIVE" | "PAUSED";
    statusReason?: string | null;
    closedTrades?: number;
    netPnl?: number;
    avgR?: number;
    guardsProposed?: { id: number; text: string; guardState: GuardState }[];
  };
  createdAt: string;
}

export interface SetupScorecard {
  id: number;
  setup: string;
  policy: string | null;
  closedTrades: number;
  wins: number;
  losses: number;
  netPnl: number;
  avgR: number;
  winRatePct: number;
  expectancy: number;
  scoreStatus: "ACTIVE" | "PAUSED";
  statusReason: string | null;
  pausedAt: string | null;
  resumedAt: string | null;
  lastTradeId: number | null;
  updatedAt: string | null;
}

export type GuardState = "PROPOSED" | "APPLIED" | "REJECTED";

export interface SetupGuard {
  id: number;
  setup: string;
  guardType: "WITH_TREND_ONLY" | "NO_LATE_ENTRY" | "EARLIER_BREAKEVEN" | "MIN_TARGET_PCT";
  tag: string;
  params: Record<string, number>;
  text: string;
  evidence: { trades?: number; tradeIds?: number[]; netPnl?: number; windowDays?: number };
  guardState: GuardState;
  decidedAt: string | null;
  ruleId: number | null;
  createdAt: string;
}

export interface AutopsySearchFilter extends BaseFilter {
  sessionId?: number;
  setup?: string;
  outcome?: "WIN" | "LOSS";
}

export interface ScorecardSearchFilter extends BaseFilter {
  scoreStatus?: "ACTIVE" | "PAUSED";
}

export interface GuardSearchFilter extends BaseFilter {
  setup?: string;
  guardState?: GuardState;
}
