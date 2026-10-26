import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { researchApi } from "../api/research.api";
import { researchQueryKeys } from "../queryKeys/researchQueryKeys";
import {
  CandidateSearchFilter,
  ResearchConfig,
  RiskTermSearchFilter,
  RunSearchFilter,
  SourceSearchFilter,
  UnderlyingSearchFilter,
  UnderlyingType,
} from "../types/research.types";

export function useLatestResults(underlyingType: UnderlyingType = "INDEX") {
  return useQuery({
    queryKey: researchQueryKeys.latestResults(underlyingType),
    queryFn: () => researchApi.getLatestResults(underlyingType),
    refetchInterval: 30000,
  });
}

export function useCandidates(filter: CandidateSearchFilter) {
  return useQuery({
    queryKey: researchQueryKeys.candidateList(filter),
    queryFn: () => researchApi.searchCandidates(filter),
  });
}

export function useCandidate(id: number | null) {
  return useQuery({
    queryKey: researchQueryKeys.candidateDetail(id ?? 0),
    queryFn: () => researchApi.getCandidate(id!),
    enabled: Boolean(id && id > 0),
  });
}

export function useResearchRuns(filter: RunSearchFilter) {
  return useQuery({
    queryKey: researchQueryKeys.runList(filter),
    queryFn: () => researchApi.searchRuns(filter),
    refetchInterval: 10000,
  });
}

export function useResearchRun(id: number | null) {
  return useQuery({
    queryKey: researchQueryKeys.runDetail(id ?? 0),
    queryFn: () => researchApi.getRun(id!),
    enabled: Boolean(id && id > 0),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (state === "RUNNING" || state === "QUEUED") {
        return 1500;
      }
      return false;
    },
  });
}

export function useRunLogs(runId: number, filter: { page?: number; limit?: number; level?: string; node?: string }) {
  return useQuery({
    queryKey: researchQueryKeys.runLogs(runId, filter),
    queryFn: () => researchApi.searchRunLogs(runId, filter),
    enabled: Boolean(runId && runId > 0),
    refetchInterval: 5000,
  });
}

export function useUnderlyings(filter: UnderlyingSearchFilter) {
  return useQuery({
    queryKey: researchQueryKeys.underlyings(filter),
    queryFn: () => researchApi.searchUnderlyings(filter),
  });
}

export function useToggleUnderlyingEnabled() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      researchApi.toggleUnderlyingEnabled(id, enabled),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: researchQueryKeys.all });
    },
  });
}

export function useImportUnderlyings() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (formData: FormData) => researchApi.importUnderlyings(formData),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: researchQueryKeys.all });
    },
  });
}

export function useSources(filter: SourceSearchFilter) {
  return useQuery({
    queryKey: researchQueryKeys.sources(filter),
    queryFn: () => researchApi.searchSources(filter),
  });
}

export function useTestSource() {
  return useMutation({
    mutationFn: (id: number) => researchApi.testSource(id),
  });
}

export function useRiskTerms(filter: RiskTermSearchFilter) {
  return useQuery({
    queryKey: researchQueryKeys.riskTerms(filter),
    queryFn: () => researchApi.searchRiskTerms(filter),
  });
}

export function useResearchConfig() {
  return useQuery({
    queryKey: researchQueryKeys.config(),
    queryFn: () => researchApi.getConfig(),
  });
}

export function useUpdateResearchConfig() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: Partial<ResearchConfig>) => researchApi.updateConfig(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: researchQueryKeys.config() });
    },
  });
}

export function useSemanticSearch() {
  return useMutation({
    mutationFn: (payload: {
      query: string;
      scope: "CHUNKS" | "CLAIMS" | "BRIEFS";
      underlyingCode?: string;
      sinceDays?: number;
      topK?: number;
    }) => researchApi.semanticSearch(payload),
  });
}

export function useStartResearchRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: {
      scope?: string[];
      windowHours?: number;
      topN?: number;
      maxDocsPerUnderlying?: number;
    }) => researchApi.startRun(params),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: researchQueryKeys.all });
    },
  });
}

export function useCancelResearchRun() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => researchApi.cancelRun(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: researchQueryKeys.all });
    },
  });
}

export function useRunStatus() {
  return useQuery({
    queryKey: ["research", "runStatus"],
    queryFn: () => researchApi.getRunStatus(),
    refetchInterval: (query) => {
      const state = query.state.data?.state;
      if (state === "RUNNING" || state === "QUEUED") {
        return 1500;
      }
      return 5000;
    },
  });
}

export function useRunEngine() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => researchApi.runEngine(),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["research"] });
      queryClient.invalidateQueries({ queryKey: researchQueryKeys.all });
    },
  });
}
