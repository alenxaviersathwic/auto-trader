import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { sessionsQueryKeys } from "../../sessions/queryKeys/sessionsQueryKeys";
import {
  adjustTrade,
  createTrade,
  exitTrade,
  getTrade,
  previewTradeSizing,
  searchTrades,
} from "../api/trades.api";
import { tradesQueryKeys } from "../queryKeys/tradesQueryKeys";
import {
  TradeAdjustPayload,
  TradeCreatePayload,
  TradeExitPayload,
  TradeSearchFilter,
} from "../types/trades.types";

export function useTradeSearch(filter: TradeSearchFilter) {
  return useQuery({
    queryKey: tradesQueryKeys.list(filter),
    queryFn: () => searchTrades(filter),
    placeholderData: keepPreviousData,
  });
}

export function useTradeDetail(id: number) {
  return useQuery({
    queryKey: tradesQueryKeys.detail(id),
    queryFn: () => getTrade(id),
    enabled: id > 0,
  });
}

export function usePreviewTradeSizing(
  sessionId: number,
  pickId: number,
  entryAt: number | undefined,
  enabled = true
) {
  return useQuery({
    queryKey: tradesQueryKeys.sizing(sessionId, pickId, entryAt),
    queryFn: () => previewTradeSizing(sessionId, pickId, entryAt),
    enabled: enabled && sessionId > 0 && pickId > 0,
    placeholderData: keepPreviousData,
  });
}

export function useCreateTrade() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TradeCreatePayload) => createTrade(payload),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: tradesQueryKeys.all });
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.detail(created.sessionId) });
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.picks(created.sessionId) });
    },
  });
}

export function useAdjustTrade(tradeId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TradeAdjustPayload) => adjustTrade(tradeId, payload),
    onSuccess: (updated) => {
      queryClient.setQueryData(tradesQueryKeys.detail(tradeId), updated);
      queryClient.invalidateQueries({ queryKey: tradesQueryKeys.lists() });
    },
  });
}

export function useExitTrade(tradeId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload?: TradeExitPayload) => exitTrade(tradeId, payload ?? {}),
    onSuccess: (updated) => {
      queryClient.setQueryData(tradesQueryKeys.detail(tradeId), updated);
      queryClient.invalidateQueries({ queryKey: tradesQueryKeys.lists() });
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.detail(updated.sessionId) });
    },
  });
}

