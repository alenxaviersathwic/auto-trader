import { BaseEntity } from "../../../core/types/baseEntity.types";
import { BaseFilter } from "../../../core/types/filter.types";

export type UnderlyingType = "INDEX" | "COMMODITY" | "STOCK";

export interface ResearchUnderlying extends BaseEntity {
  code: string;
  name: string;
  underlyingType: UnderlyingType;
  groupName: string;
  exchange: string;
  aliases: string[];
  keywords: string[];
  heavyweights: Array<{ name: string; aliases?: string[]; weightPct?: number }>;
  enabled: boolean;
  sortOrder: number;
}

export type SourceType = "RSS" | "AGENCY" | "SEARCH" | "PAPER";

export interface ResearchSource extends BaseEntity {
  name: string;
  sourceType: SourceType;
  baseUrl: string;
  feedUrl?: string | null;
  credibilityWeight: number;
  appliesToTypes: UnderlyingType[];
  appliesToGroups?: string[] | null;
  enabled: boolean;
  lastFetchAt?: string | null;
  lastError?: string | null;
  okCount: number;
  failCount: number;
}

export type RiskTermCategory =
  | "LEGAL_REGULATORY"
  | "FRAUD"
  | "GEOPOLITICAL"
  | "SELL_OFF"
  | "DOWNGRADE"
  | "DEFAULT"
  | "HALT"
  | "SUPPLY_SHOCK"
  | "OTHER";

export interface ResearchRiskTerm extends BaseEntity {
  term: string;
  category: RiskTermCategory;
  defaultSeverity: number;
  appliesToTypes: UnderlyingType[];
  enabled: boolean;
}

export type RunState = "QUEUED" | "RUNNING" | "COMPLETED" | "PARTIAL" | "FAILED" | "CANCELLED";
export type ResultKind = "SUGGESTED" | "NONE_SUGGESTED";

export interface ResearchRun extends BaseEntity {
  scope: string[];
  triggerSource: string;
  triggeredBy?: string | null;
  state: RunState;
  resultKind?: ResultKind | null;
  params: Record<string, any>;
  configVersion: number;
  currentNode?: string | null;
  progressPct: number;
  stats: Record<string, any>;
  resumable: boolean;
  threadId: string;
  startedAt?: string | null;
  finishedAt?: string | null;
  error?: string | null;
}

export interface ResearchRunEvent {
  id: number;
  runId: number;
  seq: number;
  node: string;
  level: "INFO" | "WARN" | "ERROR";
  message: string;
  data: Record<string, any>;
  createdAt: string;
}

export type NewsStatus =
  | "CLEAR_POSITIVE"
  | "CLEAR_NEUTRAL"
  | "HAS_NEGATIVE"
  | "MIXED"
  | "NO_COVERAGE";

export interface BriefPoint {
  text: string;
  claimIds: number[];
}

export interface ResearchCandidate extends BaseEntity {
  runId: number;
  scope?: string;
  item?: string;
  underlyingType: UnderlyingType;
  underlyingCode: string;
  newsStatus: NewsStatus;
  suggested: boolean;
  rank?: number | null;
  direction?: "BULLISH" | "BEARISH" | null;
  bearishWatch: boolean;
  score?: number | null;
  opportunityScore?: number | null;
  latestScore?: number | null;
  scoreLabel?: "LOW" | "MEDIUM" | "HIGH" | null;
  positiveWeight: number;
  negativeWeight: number;
  negativeShare: number;
  positiveClaims: number;
  negativeClaims: number;
  materialNegatives: number[];
  independentSources: number;
  freshArticleCount: number;
  newestArticleAt?: string | null;
  oldestArticleAt?: string | null;
  flags: string[];
  reasons: string[];
  thesis?: string | null;
  supportingPoints: BriefPoint[];
  watchItems: BriefPoint[];
  verifiedClaims?: any[];
  citations: number[];
  latestNews?: Array<{
    title: string;
    url?: string;
    source?: string;
    publishedAt?: string;
    snippet?: string;
  }>;
  affectNews?: Array<{
    title: string;
    url?: string;
    source?: string;
    publishedAt?: string;
    snippet?: string;
    catalystType?: string;
    direction?: string;
  }>;
  neutralNews?: Array<{
    title: string;
    url?: string;
    source?: string;
    publishedAt?: string;
    snippet?: string;
  }>;
  blogSummary?: string | null;
  hasVectorEmbedding?: boolean;
  resolvedCitations?: Array<{
    claimId: number;
    statement: string;
    quote: string;
    domain: string;
    publishedAt?: string | null;
    url?: string | null;
    stance: string;
  }>;
}

export interface ResearchClaim extends BaseEntity {
  documentId: number;
  chunkId?: number | null;
  underlyingCode: string;
  channel: "DIRECT" | "CONSTITUENT" | "SECTOR" | "MACRO";
  stance: "BULLISH" | "BEARISH" | "NEUTRAL";
  magnitude: number;
  confidence: number;
  horizon: string;
  catalyst: string;
  isRiskEvent: boolean;
  eventDate?: string | null;
  statement: string;
  quote: string;
  quoteVerified: boolean;
  origin: "EXTRACT" | "SWEEP";
  publishedAt?: string | null;
  domain?: string | null;
  url?: string | null;
}

export interface ResearchDocument extends BaseEntity {
  urlHash: string;
  url: string;
  canonicalUrl: string;
  domain: string;
  sourceId?: number | null;
  title: string;
  publishedAt?: string | null;
  fetchedAt: string;
  wordCount: number;
  language?: string | null;
  fetchStatus: string;
  duplicateOfId?: number | null;
  firstSeenRunId: number;
  excerpt?: string;
}

export interface ResearchConfig extends BaseEntity {
  version: number;
  weights: Record<string, any>;
  thresholds: Record<string, any>;
  limits: Record<string, any>;
  note?: string | null;
}

export interface LatestRunInfo {
  id: number;
  state: RunState;
  finishedAt: string | null;
  ageHours: number;
  windowHours: number;
  scope: string[];
}

export interface LatestResultsResponse {
  run: LatestRunInfo | null;
  suggested: ResearchCandidate[];
  bearishWatch: ResearchCandidate[];
  clearNeutral: ResearchCandidate[];
  hasNegative: ResearchCandidate[];
  noCoverage: ResearchCandidate[];
  mixed: ResearchCandidate[];
}

export interface SemanticSearchHit {
  type: "chunk" | "claim" | "candidate";
  id: number;
  text: string;
  similarity: number;
  metadata: Record<string, any>;
}

// Search filters
export interface UnderlyingSearchFilter extends BaseFilter {
  underlyingType?: UnderlyingType;
  enabled?: boolean;
}

export interface SourceSearchFilter extends BaseFilter {
  sourceType?: SourceType;
  enabled?: boolean;
}

export interface RiskTermSearchFilter extends BaseFilter {
  category?: RiskTermCategory;
  enabled?: boolean;
}

export interface RunSearchFilter extends BaseFilter {
  state?: RunState;
  resultKind?: ResultKind;
  triggerSource?: string;
}

export interface CandidateSearchFilter extends BaseFilter {
  runId?: number;
  underlyingType?: UnderlyingType;
  underlyingCode?: string;
  newsStatus?: NewsStatus;
  suggested?: boolean;
  bearishWatch?: boolean;
  minScore?: number;
}

export interface ClaimSearchFilter extends BaseFilter {
  underlyingCode?: string;
  stance?: string;
  catalyst?: string;
  origin?: string;
  quoteVerified?: boolean;
  sinceHours?: number;
  documentId?: number;
}

export interface DocumentSearchFilter extends BaseFilter {
  domain?: string;
  underlyingCode?: string;
  fetchStatus?: string;
}
