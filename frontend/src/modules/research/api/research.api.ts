import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import {
  CandidateSearchFilter,
  ClaimSearchFilter,
  DocumentSearchFilter,
  LatestResultsResponse,
  ResearchCandidate,
  ResearchClaim,
  ResearchConfig,
  ResearchDocument,
  ResearchRiskTerm,
  ResearchRun,
  ResearchRunEvent,
  ResearchSource,
  ResearchUnderlying,
  RiskTermSearchFilter,
  RunSearchFilter,
  SemanticSearchHit,
  SourceSearchFilter,
  UnderlyingSearchFilter,
  UnderlyingType,
} from "../types/research.types";

export const researchApi = {
  // Direct Research Engine APIs
  async runEngine(): Promise<any> {
    return httpClient.post("/research/run");
  },

  async getRunStatus(): Promise<any> {
    return httpClient.get("/research/run-status");
  },

  async triggerEngine(): Promise<any> {
    return httpClient.post("/research/run");
  },

  async getEngineStatus(): Promise<any> {
    return httpClient.get("/research/run-status");
  },

  // Runs
  async startRun(params: {
    scope?: string[];
    windowHours?: number;
    topN?: number;
    maxDocsPerUnderlying?: number;
  }): Promise<{ runId: number }> {
    return httpClient.post("/research/runs", params);
  },

  async searchRuns(filter: RunSearchFilter): Promise<PageResult<ResearchRun>> {
    return httpClient.post("/research/runs/search", filter);
  },

  async getRun(id: number): Promise<ResearchRun & { summaryByType?: Record<string, any> }> {
    return httpClient.get(`/research/runs/${id}`);
  },

  async cancelRun(id: number): Promise<{ cancelled: boolean }> {
    return httpClient.post(`/research/runs/${id}/cancel`);
  },

  async resumeRun(id: number): Promise<{ resumed: boolean }> {
    return httpClient.post(`/research/runs/${id}/resume`);
  },

  async searchRunLogs(
    id: number,
    filter: { page?: number; limit?: number; level?: string; node?: string }
  ): Promise<PageResult<ResearchRunEvent>> {
    return httpClient.post(`/research/runs/${id}/log/search`, filter);
  },

  // Results
  async getLatestResults(underlyingType: UnderlyingType = "INDEX"): Promise<LatestResultsResponse> {
    return httpClient.get(`/research/results/latest?underlyingType=${underlyingType}`);
  },

  async searchCandidates(filter: CandidateSearchFilter): Promise<PageResult<ResearchCandidate>> {
    return httpClient.post("/research/search", filter);
  },

  async getCandidate(id: number): Promise<ResearchCandidate> {
    return httpClient.get(`/research/candidates/${id}`);
  },

  async searchClaims(filter: ClaimSearchFilter): Promise<PageResult<ResearchClaim>> {
    return httpClient.post("/research/claims/search", filter);
  },

  async searchDocuments(filter: DocumentSearchFilter): Promise<PageResult<ResearchDocument>> {
    return httpClient.post("/research/documents/search", filter);
  },

  async getDocument(id: number): Promise<ResearchDocument & { claims?: ResearchClaim[] }> {
    return httpClient.get(`/research/documents/${id}`);
  },

  async semanticSearch(payload: {
    query: string;
    scope: "CHUNKS" | "CLAIMS" | "BRIEFS";
    underlyingCode?: string;
    sinceDays?: number;
    topK?: number;
  }): Promise<{ query: string; scope: string; hits: SemanticSearchHit[] }> {
    return httpClient.post("/research/search/semantic", payload);
  },

  // Setup / Admin
  async searchUnderlyings(filter: UnderlyingSearchFilter): Promise<PageResult<ResearchUnderlying>> {
    return httpClient.post("/research/underlyings/search", filter);
  },

  async createUnderlying(data: Partial<ResearchUnderlying>): Promise<ResearchUnderlying> {
    return httpClient.post("/research/underlyings", data);
  },

  async updateUnderlying(id: number, data: Partial<ResearchUnderlying>): Promise<ResearchUnderlying> {
    return httpClient.put(`/research/underlyings/${id}`, data);
  },

  async deleteUnderlying(id: number): Promise<{ deleted: boolean }> {
    return httpClient.delete(`/research/underlyings/${id}`);
  },

  async toggleUnderlyingEnabled(id: number, enabled: boolean): Promise<ResearchUnderlying> {
    return httpClient.patch(`/research/underlyings/${id}/enabled?enabled=${enabled}`);
  },

  async importUnderlyings(formData: FormData): Promise<{ importedCount: number; dryRun: boolean }> {
    return httpClient.post("/research/underlyings/import", formData, {
      headers: { "Content-Type": "multipart/form-data" },
    });
  },

  async searchSources(filter: SourceSearchFilter): Promise<PageResult<ResearchSource>> {
    return httpClient.post("/research/sources/search", filter);
  },

  async createSource(data: Partial<ResearchSource>): Promise<ResearchSource> {
    return httpClient.post("/research/sources", data);
  },

  async updateSource(id: number, data: Partial<ResearchSource>): Promise<ResearchSource> {
    return httpClient.put(`/research/sources/${id}`, data);
  },

  async deleteSource(id: number): Promise<{ deleted: boolean }> {
    return httpClient.delete(`/research/sources/${id}`);
  },

  async testSource(id: number): Promise<{
    sourceId: number;
    name: string;
    success: boolean;
    itemCount: number;
    newestItemDate: string | null;
    error: string | null;
    sampleTitles: string[];
  }> {
    return httpClient.post(`/research/sources/${id}/test`);
  },

  async searchRiskTerms(filter: RiskTermSearchFilter): Promise<PageResult<ResearchRiskTerm>> {
    return httpClient.post("/research/risk-terms/search", filter);
  },

  async createRiskTerm(data: Partial<ResearchRiskTerm>): Promise<ResearchRiskTerm> {
    return httpClient.post("/research/risk-terms", data);
  },

  async updateRiskTerm(id: number, data: Partial<ResearchRiskTerm>): Promise<ResearchRiskTerm> {
    return httpClient.put(`/research/risk-terms/${id}`, data);
  },

  async deleteRiskTerm(id: number): Promise<{ deleted: boolean }> {
    return httpClient.delete(`/research/risk-terms/${id}`);
  },

  async getConfig(): Promise<ResearchConfig> {
    return httpClient.get("/research/config");
  },

  async updateConfig(data: Partial<ResearchConfig>): Promise<ResearchConfig> {
    return httpClient.put("/research/config", data);
  },

  async getHealth(): Promise<Record<string, any>> {
    return httpClient.get("/research/health");
  },
};
