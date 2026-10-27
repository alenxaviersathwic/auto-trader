export interface StartSuggestionParams {
  confidenceWanted?: number;
  minProfitMargin?: number;
  maxSuggestions?: number;
  maxPerUnderlying?: number;
  loopGapSeconds?: number;
  underlyings?: string[];
  ignoreMarketHours?: boolean;
}

export interface StartSuggestionResult {
  started: boolean;
  reason?: "NO_RESEARCH_DATA" | "NO_UNDERLYINGS" | "ALREADY_RUNNING";
  message?: string;
  loopId?: string;
}

export interface SuggestionRunStatus {
  isLooping: boolean;
  loopId: string | null;
  iteration: number;
  active: string[];
  stopReason: string | null;
  researchHasData: boolean;
  state: string;
  currentNode: string | null;
  progressPct: number;
  startedAt: string | null;
  finishedAt: string | null;
  stats: {
    underlyings?: number;
    candidates?: number;
    picked?: number;
    aiUsed?: number;
    baselineUsed?: number;
    outcomesResolved?: number;
    skipped?: { underlying: string; reason: string }[];
  };
  error: string | null;
}

export interface Suggestion {
  id: number;
  ref: string;
  spot: number;
  riskLevel: "LOW" | "MEDIUM" | "HIGH";
  runId: number;
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
  createdAt: string;
}

export interface LatestSuggestions {
  list: Suggestion[];
  generatedAt: string | null;
}

export interface SuggestionUnderlying {
  code: string;
  type: "INDEX" | "COMMODITY";
  direction: "BULLISH" | "BEARISH" | null;
  newsStatus: string | null;
  score: number | null;
  count: number;
  callCount: number;
  putCount: number;
  topConfidence: number;
  active: boolean;
  lastIteratedAt: string | null;
  lastLoop: number | null;
  lastNote: string | null;
}

export interface SuggestionUnderlyings {
  hasResearch: boolean;
  list: SuggestionUnderlying[];
}
