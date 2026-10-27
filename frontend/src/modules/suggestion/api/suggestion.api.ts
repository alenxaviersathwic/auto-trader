import { httpClient } from "../../../core/api/httpClient";
import {
  LatestSuggestions,
  StartSuggestionParams,
  StartSuggestionResult,
  SuggestionRunStatus,
  SuggestionUnderlyings,
} from "../types/suggestion.types";

export const suggestionApi = {
  async run(params?: StartSuggestionParams): Promise<StartSuggestionResult> {
    return httpClient.post("/suggestion/run", params ?? {});
  },

  async stop(underlyings?: string[]): Promise<{ stopped: boolean; state: string }> {
    return httpClient.post("/suggestion/stop", { underlyings });
  },

  async getUnderlyings(): Promise<SuggestionUnderlyings> {
    return httpClient.get("/suggestion/underlyings");
  },

  async getRunStatus(): Promise<SuggestionRunStatus> {
    return httpClient.get("/suggestion/run-status");
  },

  async getLatest(underlying?: string): Promise<LatestSuggestions> {
    return httpClient.get("/suggestion/latest", { params: underlying ? { underlying } : undefined });
  },
};
