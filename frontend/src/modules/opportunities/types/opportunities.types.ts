export interface StartOpportunityParams {
  confidenceWanted?: number;
  minProfitMargin?: number;
  maxProfitMargin?: number;
  maxStopLossPct?: number;
  validMinutes?: number;
  maxOpportunities?: number;
  maxPerUnderlying?: number;
  loopGapSeconds?: number;
  underlyings?: string[];
  ignoreMarketHours?: boolean;
}

export type MasterState = "RUNNING" | "STOPPED";

/** One card session (opportunity_masters row): created per card each time Start is clicked. */
export interface OpportunityMaster {
  id: number;
  tradeDate: string;
  sessionNo: number;
  underlyingCode: string;
  underlyingType: "INDEX" | "COMMODITY";
  state: MasterState;
  stopReason: string | null;
  params: StartOpportunityParams & { loopGapSeconds?: number };
  researchRunId: number | null;
  researchScore: number | null;
  direction: "BULLISH" | "BEARISH" | null;
  newsStatus: string | null;
  inResearch: boolean;
  iterationsCompleted: number;
  iterationsFailed: number;
  opportunitiesTotal: number;
  lastOpportunityCount: number;
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

export interface StartOpportunityResult {
  started: boolean;
  reason?: "NO_RESEARCH_DATA" | "NO_UNDERLYINGS";
  message?: string;
  masters: OpportunityMaster[];
}

export interface IterateResult {
  master: OpportunityMaster;
  ran: boolean;
  saved: number;
}

export interface Opportunity {
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

export interface LatestOpportunities {
  list: Opportunity[];
  generatedAt: string | null;
}

/** API 1: POST /opportunities/research-top -- best underlyings from the Research Engine. */
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

/** API 2: POST /opportunities/masters/today -- today's newest session per underlying + live counts. */
export interface TodayMaster extends OpportunityMaster {
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
export interface OpportunityCardItem {
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


/** Filter for POST /opportunities/search -- full trade_opportunities history (latestOnly=false = every loop). */
export interface OpportunitySearchFilter {
  page: number;
  limit: number;
  sortBy?: string;
  sortDir?: "asc" | "desc";
  masterId?: number;
  underlyingCode?: string;
  outcome?: string;
  latestOnly?: boolean;
}

export interface OpportunitySearchResult {
  list: Opportunity[];
  page: number;
  limit: number;
  totalPages: number;
  totalItems: number;
}

export type IterationResult =
  | "SAVED"
  | "DROPPED"
  | "NO_SETUP"
  | "SETUP_REJECTED"
  | "NO_CONTRACT"
  | "BLOCKED_WINDOW"
  | "MARKET_CLOSED"
  | "NOT_IN_RESEARCH"
  | "DATA_ERROR"
  | "ERROR";

export interface SetupRef {
  name: string;
  side: "CE" | "PE";
  strength: number;
}

export interface IterationDetails {
  result?: IterationResult;
  reason?: string;
  regime?: string;
  window?: string;
  trend15?: string;
  trend15Source?: string | null;
  setupsFired?: SetupRef[];
  setupsConfirmed?: SetupRef[];
  setupsRejected?: { name: string; side: "CE" | "PE"; reason: string }[];
  menuSize?: number;
  menuDropped?: Record<string, number>;
  picks?: number;
  kept?: number;
  dropped?: Record<string, number>;
  source?: "AI" | "BASELINE";
  confidenceWanted?: number;
}

/** One row per batch (iteration), written even when the batch found nothing. */
export interface OpportunityIteration {
  id: number;
  masterId: number;
  iterationNo: number;
  underlyingCode: string;
  result: IterationResult;
  summary: string | null;
  savedCount: number;
  details: IterationDetails;
  durationMs: number | null;
  createdAt: string;
}

export interface IterationSearchResult {
  list: OpportunityIteration[];
  page: number;
  limit: number;
  totalPages: number;
  totalItems: number;
}

export interface OpportunityCandlePoint {
  t: string;
  o: number;
  h: number;
  l: number;
  c: number;
}

export interface OpportunityCheckItem {
  opportunityId: number;
  masterId: number;
  iterationNo: number;
  ref: string;
  strike: number;
  optionType: "CE" | "PE";
  expiry: string;
  createdAt: string;
  validUntil: string;
  entry: number;
  stop: number;
  target: number;
  exitPrice: number;
  peakPrice: number;
  troughPrice: number;
  pnlPoints: number;
  pnlPct: number;
  maxGainPct: number;
  achievedPct: number;
  targetAchieved: boolean;
  outcome: "PENDING" | "TARGET_HIT" | "STOP_HIT" | "EXPIRED";
  hitAt: string | null;
  candlesChecked: number;
  windowEnded: boolean;
  series?: OpportunityCandlePoint[];
}

export interface BatchCheckSummary {
  iterationNo: number;
  total: number;
  targetHits: number;
  avgAchievedPct: number;
  bestAchievedPct: number;
  items: OpportunityCheckItem[];
}

export interface BatchCheckResult {
  masterId: number;
  iterationNo: number | null;
  checkedAt: string;
  results: OpportunityCheckItem[];
  batches: Record<number, BatchCheckSummary>;
}
