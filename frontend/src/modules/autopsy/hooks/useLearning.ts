import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  applyGuard,
  getTradeAutopsy,
  rejectGuard,
  resumeSetup,
  searchAutopsies,
  searchGuards,
  searchScorecards,
} from "../api/learning.api";
import { learningQueryKeys } from "../queryKeys/learningQueryKeys";
import { AutopsySearchFilter, GuardSearchFilter, ScorecardSearchFilter } from "../types/learning.types";

export function useAutopsies(filter: AutopsySearchFilter, refetchIntervalMs?: number) {
  return useQuery({
    queryKey: learningQueryKeys.autopsyList(filter),
    queryFn: () => searchAutopsies(filter),
    placeholderData: keepPreviousData,
    refetchInterval: refetchIntervalMs && refetchIntervalMs > 0 ? refetchIntervalMs : false,
  });
}

/** The autopsy is written when the trade exits; 404 before that, so no retries. */
export function useTradeAutopsy(tradeId: number, enabled: boolean) {
  return useQuery({
    queryKey: learningQueryKeys.tradeAutopsy(tradeId),
    queryFn: () => getTradeAutopsy(tradeId),
    enabled: enabled && tradeId > 0,
    retry: false,
  });
}

export function useScorecards(filter: ScorecardSearchFilter, refetchIntervalMs?: number) {
  return useQuery({
    queryKey: learningQueryKeys.scorecardList(filter),
    queryFn: () => searchScorecards(filter),
    placeholderData: keepPreviousData,
    refetchInterval: refetchIntervalMs && refetchIntervalMs > 0 ? refetchIntervalMs : false,
  });
}

export function useGuards(filter: GuardSearchFilter, refetchIntervalMs?: number) {
  return useQuery({
    queryKey: learningQueryKeys.guardList(filter),
    queryFn: () => searchGuards(filter),
    placeholderData: keepPreviousData,
    refetchInterval: refetchIntervalMs && refetchIntervalMs > 0 ? refetchIntervalMs : false,
  });
}

function useInvalidateLearning() {
  const queryClient = useQueryClient();
  return () => queryClient.invalidateQueries({ queryKey: learningQueryKeys.all });
}

export function useApplyGuard() {
  const invalidate = useInvalidateLearning();
  return useMutation({ mutationFn: (id: number) => applyGuard(id), onSuccess: invalidate });
}

export function useRejectGuard() {
  const invalidate = useInvalidateLearning();
  return useMutation({ mutationFn: (id: number) => rejectGuard(id), onSuccess: invalidate });
}

export function useResumeSetup() {
  const invalidate = useInvalidateLearning();
  return useMutation({
    mutationFn: ({ setup, managerCode }: { setup: string; managerCode?: string }) => resumeSetup(setup, managerCode),
    onSuccess: invalidate,
  });
}
