import { useMutation, useQuery, useQueryClient, keepPreviousData } from "@tanstack/react-query";
import {
  createSession,
  deleteSession,
  getSession,
  searchSessions,
  updateSession,
} from "../api/sessions.api";
import { sessionsQueryKeys } from "../queryKeys/sessionsQueryKeys";
import {
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
