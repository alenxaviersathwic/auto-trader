import { httpClient } from "../../../core/api/httpClient";
import {
  BatchCheckResult,
  IterateResult,
  IterationSearchResult,
  LatestOpportunities,
  OpportunityCheckItem,
  OpportunityMaster,
  OpportunitySearchFilter,
  OpportunitySearchResult,
  ResearchTop,
  StartOpportunityParams,
  StartOpportunityResult,
  TodayMasters,
} from "../types/opportunities.types";

/** One iteration = market data + one local-AI call (+ one retry): allow well past the 30s default. */
const ITERATE_TIMEOUT_MS = 8 * 60 * 1000;

export const opportunitiesApi = {
  /** API 1: top 5 INDEX + top 3 COMMODITY from the Research Engine. */
  async getResearchTop(): Promise<ResearchTop> {
    return httpClient.post("/opportunities/research-top", {});
  },

  /** API 2: today's newest session (master) per underlying. */
  async getTodayMasters(): Promise<TodayMasters> {
    return httpClient.post("/opportunities/masters/today", {});
  },

  /** Creates a NEW session row per card (every Research card, or only `underlyings`). */
  async start(params?: StartOpportunityParams): Promise<StartOpportunityResult> {
    return httpClient.post("/opportunities/masters/start", params ?? {});
  },

  async iterate(masterId: number): Promise<IterateResult> {
    return httpClient.post(`/opportunities/masters/${masterId}/iterate`, {}, { timeout: ITERATE_TIMEOUT_MS });
  },

  async stop(masterId: number): Promise<OpportunityMaster> {
    return httpClient.post(`/opportunities/masters/${masterId}/stop`, {});
  },

  async stopAll(): Promise<{ stopped: number; masters: OpportunityMaster[] }> {
    return httpClient.post("/opportunities/masters/stop-all", {});
  },

  async getLatest(underlying?: string): Promise<LatestOpportunities> {
    return httpClient.get("/opportunities/latest", { params: underlying ? { underlying } : undefined });
  },

  /** Full per-master history across every loop (latestOnly=false) -- used by the batch side sheet. */
  async search(filter: OpportunitySearchFilter): Promise<OpportunitySearchResult> {
    return httpClient.post("/opportunities/search", filter);
  },

  /** Per-batch diagnostics for one session: why a batch was empty, what it dropped. */
  async searchIterations(masterId: number): Promise<IterationSearchResult> {
    return httpClient.post("/opportunities/iterations/search", {
      page: 0,
      limit: 100,
      masterId,
      sortBy: "createdAt",
      sortDir: "desc",
    });
  },

  /** Evaluates target achievement % for one batch (or all batches) over entry -> validUntil. */
  async checkBatch(masterId: number, iterationNo?: number): Promise<BatchCheckResult> {
    return httpClient.post(`/opportunities/masters/${masterId}/check`, {
      iterationNo: iterationNo ?? null,
    });
  },

  /** Evaluates target achievement % for ONE opportunity inside a batch over entry -> validUntil. */
  async checkOpportunity(opportunityId: number): Promise<OpportunityCheckItem> {
    return httpClient.post(`/opportunities/${opportunityId}/check`, {});
  },
};

