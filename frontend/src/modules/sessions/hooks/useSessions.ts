import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import {
  createSession,
  deleteSession,
  getSession,
  lockSessionPick,
  searchSessionPicks,
  searchSessions,
  updateSession,
} from "../api/sessions.api";
import { sessionsQueryKeys } from "../queryKeys/sessionsQueryKeys";
import {
  SessionPickSearchFilter,
  TradingSessionCreatePayload,
  TradingSessionSearchFilter,
  TradingSessionUpdatePayload,
} from "../types/sessions.types";

export function useSessionSearch(filter: TradingSessionSearchFilter) {
  return useQuery({
    queryKey: sessionsQueryKeys.list(filter),
    queryFn: () => searchSessions(filter),
    placeholderData: keepPreviousData,
  });
}

export function useSessionDetail(id: number) {
  return useQuery({
    queryKey: sessionsQueryKeys.detail(id),
    queryFn: () => getSession(id),
    enabled: id > 0,
  });
}

export function useCreateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: TradingSessionCreatePayload) => createSession(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.lists() });
    },
  });
}

export function useUpdateSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: TradingSessionUpdatePayload }) =>
      updateSession(id, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.lists() });
    },
  });
}

export function useDeleteSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => deleteSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.lists() });
    },
  });
}

export function useSessionPicks(sessionId: number, filter: SessionPickSearchFilter) {
  return useQuery({
    queryKey: sessionsQueryKeys.pickList(sessionId, filter),
    queryFn: () => searchSessionPicks(sessionId, filter),
    enabled: sessionId > 0,
    placeholderData: keepPreviousData,
  });
}

export function useLockSessionPick(sessionId: number) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (pickId: number) => lockSessionPick(sessionId, pickId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: sessionsQueryKeys.picks(sessionId) });
    },
  });
}
