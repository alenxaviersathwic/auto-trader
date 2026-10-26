import {
  CandidateSearchFilter,
  ClaimSearchFilter,
  DocumentSearchFilter,
  RiskTermSearchFilter,
  RunSearchFilter,
  SourceSearchFilter,
  UnderlyingSearchFilter,
  UnderlyingType,
} from "../types/research.types";

export const researchQueryKeys = {
  all: ["research"] as const,

  // Results
  latestResults: (type: UnderlyingType) => [...researchQueryKeys.all, "results", "latest", type] as const,
  candidates: () => [...researchQueryKeys.all, "candidates"] as const,
  candidateList: (filter: CandidateSearchFilter) => [...researchQueryKeys.candidates(), "list", filter] as const,
  candidateDetail: (id: number) => [...researchQueryKeys.candidates(), "detail", id] as const,

  // Runs
  runs: () => [...researchQueryKeys.all, "runs"] as const,
  runList: (filter: RunSearchFilter) => [...researchQueryKeys.runs(), "list", filter] as const,
  runDetail: (id: number) => [...researchQueryKeys.runs(), "detail", id] as const,
  runLogs: (id: number, filter: any) => [...researchQueryKeys.runs(), "logs", id, filter] as const,

  // Claims & Docs
  claims: (filter: ClaimSearchFilter) => [...researchQueryKeys.all, "claims", filter] as const,
  documents: (filter: DocumentSearchFilter) => [...researchQueryKeys.all, "documents", filter] as const,
  documentDetail: (id: number) => [...researchQueryKeys.all, "documents", "detail", id] as const,

  // Setup / Admin
  underlyings: (filter: UnderlyingSearchFilter) => [...researchQueryKeys.all, "underlyings", filter] as const,
  sources: (filter: SourceSearchFilter) => [...researchQueryKeys.all, "sources", filter] as const,
  riskTerms: (filter: RiskTermSearchFilter) => [...researchQueryKeys.all, "risk-terms", filter] as const,
  config: () => [...researchQueryKeys.all, "config"] as const,
  health: () => [...researchQueryKeys.all, "health"] as const,
};
