import React from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { opportunitiesApi } from "../api/opportunities.api";
import { opportunitiesQueryKeys } from "../queryKeys/opportunitiesQueryKeys";
import { OpportunityCardItem, StartOpportunityParams } from "../types/opportunities.types";
import { opportunityLoopRunner } from "./opportunityLoopRunner";

/** Live state of the client-side loop (round, which card is iterating). */
export function useOpportunityLoop() {
  return React.useSyncExternalStore(opportunityLoopRunner.subscribe, opportunityLoopRunner.getSnapshot);
}

/**
 * Page cards = API 1 (Research top) merged with API 2 (today's masters):
 * a Research item with a master today shows that master; without one it shows the Research item
 * and a Start button. A master whose underlying has dropped out of Research is still shown (inResearch=false).
 */
export function useOpportunityCards(looping: boolean) {
  const research = useQuery({
    queryKey: opportunitiesQueryKeys.researchTop(),
    queryFn: () => opportunitiesApi.getResearchTop(),
    refetchInterval: 60000,
  });
  const masters = useQuery({
    queryKey: opportunitiesQueryKeys.todayMasters(),
    queryFn: () => opportunitiesApi.getTodayMasters(),
    refetchInterval: looping ? 5000 : 15000,
  });
  const cards = React.useMemo<OpportunityCardItem[]>(() => {
    const byCode = new Map((masters.data?.list ?? []).map((m) => [m.underlyingCode, m]));
    const out: OpportunityCardItem[] = (research.data?.list ?? []).map((r) => ({
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

export function useLatestOpportunities(looping: boolean, underlying?: string) {
  return useQuery({
    queryKey: opportunitiesQueryKeys.latest(underlying),
    queryFn: () => opportunitiesApi.getLatest(underlying),
    refetchInterval: looping ? 5000 : false,
  });
}

/** Start = new session row per card, then the loop iterates them one by one. */
export function useStartOpportunity() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params?: StartOpportunityParams) => opportunitiesApi.start(params),
    onSuccess: (res) => {
      if (res.started) void opportunityLoopRunner.run();
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: opportunitiesQueryKeys.all }),
  });
}

export function useStopCard() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (masterId: number) => opportunitiesApi.stop(masterId),
    onSettled: () => queryClient.invalidateQueries({ queryKey: opportunitiesQueryKeys.all }),
  });
}

export function useStopAll() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => {
      opportunityLoopRunner.stop();
      return opportunitiesApi.stopAll();
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: opportunitiesQueryKeys.all }),
  });
}

export function resumeOpportunityLoop() {
  void opportunityLoopRunner.run();
}

