import { httpClient } from "../../../core/api/httpClient";
import {
  IterateResult,
  LatestSuggestions,
  ResearchTop,
  StartSuggestionParams,
  StartSuggestionResult,
  SuggestionMaster,
  TodayMasters,
} from "../types/suggestion.types";

/** One iteration = market data + one local-AI call (+ one retry): allow well past the 30s default. */
const ITERATE_TIMEOUT_MS = 8 * 60 * 1000;

export const suggestionApi = {
  /** API 1: top 5 INDEX + top 3 COMMODITY from the Research Engine. */
  async getResearchTop(): Promise<ResearchTop> {
    return httpClient.get("/suggestion/research-top");
  },

  /** API 2: today's newest session (master) per underlying. */
  async getTodayMasters(): Promise<TodayMasters> {
    return httpClient.get("/suggestion/masters/today");
  },

  /** Creates a NEW session row per card (every Research card, or only `underlyings`). */
  async start(params?: StartSuggestionParams): Promise<StartSuggestionResult> {
    return httpClient.post("/suggestion/masters/start", params ?? {});
  },

  async iterate(masterId: number): Promise<IterateResult> {
    return httpClient.post(`/suggestion/masters/${masterId}/iterate`, {}, { timeout: ITERATE_TIMEOUT_MS });
  },

  async stop(masterId: number): Promise<SuggestionMaster> {
    return httpClient.post(`/suggestion/masters/${masterId}/stop`, {});
  },

  async stopAll(): Promise<{ stopped: number; masters: SuggestionMaster[] }> {
    return httpClient.post("/suggestion/masters/stop-all", {});
  },

  async getLatest(underlying?: string): Promise<LatestSuggestions> {
    return httpClient.get("/suggestion/latest", { params: underlying ? { underlying } : undefined });
  },
};
