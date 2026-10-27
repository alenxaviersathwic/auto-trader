import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { suggestionApi } from "../api/suggestion.api";
import { suggestionQueryKeys } from "../queryKeys/suggestionQueryKeys";
import { StartSuggestionParams } from "../types/suggestion.types";

export function useSuggestionStatus() {
  return useQuery({
    queryKey: suggestionQueryKeys.runStatus(),
    queryFn: () => suggestionApi.getRunStatus(),
    refetchInterval: (query) => (query.state.data?.isLooping ? 1500 : 5000),
  });
}

export function useLatestSuggestions(isLooping: boolean, underlying?: string) {
  return useQuery({
    queryKey: suggestionQueryKeys.latest(underlying),
    queryFn: () => suggestionApi.getLatest(underlying),
    refetchInterval: isLooping ? 3000 : false,
  });
}

export function useRunSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params?: StartSuggestionParams) => suggestionApi.run(params),
    onSettled: () => queryClient.invalidateQueries({ queryKey: suggestionQueryKeys.all }),
  });
}

export function useStopSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (underlyings?: string[]) => suggestionApi.stop(underlyings),
    onSettled: () => queryClient.invalidateQueries({ queryKey: suggestionQueryKeys.all }),
  });
}

export function useSuggestionUnderlyings(isLooping: boolean) {
  return useQuery({
    queryKey: suggestionQueryKeys.underlyings(),
    queryFn: () => suggestionApi.getUnderlyings(),
    refetchInterval: isLooping ? 3000 : 15000,
  });
}
