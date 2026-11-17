import { PageResult } from "../../../core/types/pagination.types";

export type AgentStance = "BULLISH" | "BEARISH" | "NEUTRAL" | "CAUTION" | "BLOCK";

/** One sub-agent's report (backend commodity_desk/service/agents). */
export interface AgentReport {
  name: string;
  stance: AgentStance;
  score: number;
  summary: string;
  facts: string[];
  data: Record<string, unknown>;
}

export interface DeskCandidate {
  id: string;
  name: string;
  side: "CE" | "PE";
  entry: number;
  stop: number;
  target: number;
  rr: number;
  why: string;
  withStructure?: boolean;
  refusals?: string[];
  warnings?: string[];
}

export interface DeskDecision {
  id: number;
  underlyingCode: string;
  decidedAt: string;
  phase: string;
  spot: number | null;
  decision: "TAKE" | "WAIT";
  source: "LLM" | "CODE";
  setupName: string | null;
  side: "CE" | "PE" | null;
  conviction: number;
  thinking: string;
  watchFor: string;
  agents: Record<"clock" | "structure" | "options" | "news", AgentReport>;
  candidates: DeskCandidate[];
  chosen: DeskCandidate | null;
  outcome: string | null;
  createdAt: string;
}

export interface MarketMoveHeadline {
  title: string;
  url?: string | null;
  source?: string | null;
  publishedAt?: string | null;
  summary?: string | null;
}

export interface MarketMove {
  id: number;
  underlyingCode: string;
  underlyingType: string;
  detectedAt: string;
  direction: "UP" | "DOWN";
  windowMin: number;
  priceFrom: number;
  priceTo: number;
  movePct: number;
  moveAtr: number;
  newsState: "PENDING" | "FOUND" | "UNCLEAR" | "NO_NEWS";
  cause: "NEWS" | "NO_CLEAR_NEWS" | "UNCLEAR" | null;
  summary: string | null;
  headlines: MarketMoveHeadline[];
  source: "LLM" | "CODE" | null;
  createdAt: string;
}

export interface DeskLatest {
  decisions: DeskDecision[];
  moves: MarketMove[];
}

export interface DeskDecisionFilter {
  page: number;
  limit: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  underlyingCode?: string;
  decision?: "TAKE" | "WAIT";
}

export type DeskDecisionPage = PageResult<DeskDecision>;

/** One commodity's desk right now (GET /commodity-desk/live). */
export interface DeskLiveItem {
  code: string;
  passAt: string | null;
  passNo: number;
  passMs: number;
  stances: Partial<Record<"clock" | "structure" | "options" | "news", AgentStance>>;
  allowed: number;
  refused: number;
  thinkingSince: string | null;
  decidedAt: string | null;
  lastDecision: "TAKE" | "WAIT" | null;
  sentAt: string | null;
}

export interface NewsCheck {
  code: string;
  since: string;
  step: "SAVING" | "READING_HEADLINES" | "EXPLAINING" | "NO_HEADLINES";
  direction: "UP" | "DOWN";
  pct: number;
  headlines?: number | null;
}

export interface DeskLive {
  serverTime: string;
  desks: DeskLiveItem[];
  newsChecks: NewsCheck[];
}
