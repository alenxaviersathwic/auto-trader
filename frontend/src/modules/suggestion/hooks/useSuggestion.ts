import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { suggestionApi } from "../api/suggestion.api";
import { suggestionQueryKeys } from "../queryKeys/suggestionQueryKeys";
import { StartSuggestionParams, SuggestionCardItem } from "../types/suggestion.types";
import { suggestionLoopRunner } from "./suggestionLoopRunner";

/** Live state of the client-side loop (round, which card is iterating). */
export function useSuggestionLoop() {
  return React.useSyncExternalStore(suggestionLoopRunner.subscribe, suggestionLoopRunner.getSnapshot);
}

/**
 * Page cards = API 1 (Research top) merged with API 2 (today's masters):
 * a Research item with a master today shows that master; without one it shows the Research item
 * and a Start button. A master whose underlying has dropped out of Research is still shown (inResearch=false).
 */
export function useSuggestionCards(looping: boolean) {
  const research = useQuery({
    queryKey: suggestionQueryKeys.researchTop(),
    queryFn: () => suggestionApi.getResearchTop(),
    refetchInterval: 60000,
  });
  const masters = useQuery({
    queryKey: suggestionQueryKeys.todayMasters(),
    queryFn: () => suggestionApi.getTodayMasters(),
    refetchInterval: looping ? 5000 : 15000,
  });
  const cards = React.useMemo<SuggestionCardItem[]>(() => {
    const byCode = new Map((masters.data?.list ?? []).map((m) => [m.underlyingCode, m]));
    const out: SuggestionCardItem[] = (research.data?.list ?? []).map((r) => ({
      ...r,
      inResearch: true,
      master: byCode.get(r.code) ?? null,
    }));
    const shown = new Set(out.map((c) => c.code));
    for (const m of masters.data?.list ?? []) {
      if (shown.has(m.underlyingCode)) continue;
      out.push({
        code: m.underlyingCode,
        type: m.underlyingType,
        inResearch: false,
        direction: m.direction,
        newsStatus: m.newsStatus,
        score: m.researchScore,
        master: m,
      });
    }
    return out;
  }, [research.data, masters.data]);
  return {
    cards,
    hasResearch: research.data?.hasResearch ?? true,
    tradeDate: masters.data?.tradeDate ?? "",
    isLoading: research.isLoading || masters.isLoading,
    error: research.error ?? masters.error,
    refetch: () => Promise.all([research.refetch(), masters.refetch()]),
  };
}

export function useLatestSuggestions(looping: boolean, underlying?: string) {
  return useQuery({
    queryKey: suggestionQueryKeys.latest(underlying),
    queryFn: () => suggestionApi.getLatest(underlying),
    refetchInterval: looping ? 5000 : false,
  });
}

/** Start = new session row per card, then the loop iterates them one by one. */
export function useStartSuggestion() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params?: StartSuggestionParams) => suggestionApi.start(params),
    onSuccess: (res) => {
      if (res.started) void suggestionLoopRunner.run();
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: suggestionQueryKeys.all }),
  });
}

export function useStopCard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (masterId: number) => suggestionApi.stop(masterId),
    onSettled: () => queryClient.invalidateQueries({ queryKey: suggestionQueryKeys.all }),
  });
}

export function useStopAll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      suggestionLoopRunner.stop();
      return suggestionApi.stopAll();
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: suggestionQueryKeys.all }),
  });
}

export function resumeSuggestionLoop() {
  void suggestionLoopRunner.run();
}
