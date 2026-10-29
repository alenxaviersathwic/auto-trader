export interface StartSuggestionParams {
  confidenceWanted?: number;
  minProfitMargin?: number;
  maxSuggestions?: number;
  maxPerUnderlying?: number;
  loopGapSeconds?: number;
  underlyings?: string[];
  ignoreMarketHours?: boolean;
}

export type MasterState = "RUNNING" | "STOPPED";

/** One card session (suggestion_masters row): created per card each time Start is clicked. */
export interface SuggestionMaster {
  id: number;
  tradeDate: string;
  sessionNo: number;
  underlyingCode: string;
  underlyingType: "INDEX" | "COMMODITY";
  state: MasterState;
  stopReason: string | null;
  params: StartSuggestionParams & { loopGapSeconds?: number };
  researchRunId: number | null;
  researchScore: number | null;
  direction: "BULLISH" | "BEARISH" | null;
  newsStatus: string | null;
  inResearch: boolean;
  iterationsCompleted: number;
  iterationsFailed: number;
  suggestionsTotal: number;
  lastSuggestionCount: number;
  topConfidence: number;
  lastNote: string | null;
  lastError: string | null;
  lastDurationMs: number | null;
  startedAt: string;
  lastStartedAt: string | null;
  lastCompletedAt: string | null;
  stoppedAt: string | null;
  createdAt: string;
}

export interface StartSuggestionResult {
  started: boolean;
  reason?: "NO_RESEARCH_DATA" | "NO_UNDERLYINGS";
  message?: string;
  masters: SuggestionMaster[];
}

export interface IterateResult {
  master: SuggestionMaster;
  ran: boolean;
  saved: number;
}

export interface Suggestion {
  id: number;
  ref: string;
  spot: number;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
  masterId: number;
  iterationNo: number;
  underlyingCode: string;
  underlyingType: "INDEX" | "COMMODITY";
  contractId: string;
  optionType: "CE" | "PE";
  strike: number;
  expiry: string;
  entry: number;
  stop: number;
  target: number;
  profitMarginPct: number;
  rewardRisk: number;
  confidence: number;
  rank: number;
  strategy: string | null;
  reasons: string[];
  risks: string[];
  source: "AI" | "BASELINE";
  validUntil: string;
  ageSeconds: number;
  expired: boolean;
  outcome: "PENDING" | "TARGET_HIT" | "STOP_HIT" | "EXPIRED";
  isLatest: boolean;
  createdAt: string;
}

export interface LatestSuggestions {
  list: Suggestion[];
  generatedAt: string | null;
}

/** API 1: GET /suggestion/research-top -- best underlyings from the Research Engine. */
export interface ResearchTopItem {
  code: string;
  type: "INDEX" | "COMMODITY";
  direction: "BULLISH" | "BEARISH" | null;
  newsStatus: string | null;
  score: number | null;
}

export interface ResearchTop {
  hasResearch: boolean;
  researchRunId: number | null;
  list: ResearchTopItem[];
}

/** API 2: GET /suggestion/masters/today -- today's newest session per underlying + live counts. */
export interface TodayMaster extends SuggestionMaster {
  liveCount: number;
  callCount: number;
  putCount: number;
  liveTopConfidence: number;
}

export interface TodayMasters {
  tradeDate: string;
  list: TodayMaster[];
}

/** A card on the page, merged on the client from API 1 + API 2. */
export interface SuggestionCardItem {
  code: string;
  type: "INDEX" | "COMMODITY";
  inResearch: boolean;
  direction: "BULLISH" | "BEARISH" | null;
  newsStatus: string | null;
  score: number | null;
  master: TodayMaster | null;
}

/** Client-side loop state (the frontend iterates RUNNING cards one by one). */
export interface LoopSnapshot {
  running: boolean;
  round: number;
  currentMasterId: number | null;
  currentCode: string | null;
  lastError: string | null;
}
