import { SessionPickSearchFilter, TradingSessionSearchFilter } from "../types/sessions.types";

/**
 * Query Key Factory for the Sessions module.
 */
export const sessionsQueryKeys = {
  all: ["sessions"] as const,
  lists: () => [...sessionsQueryKeys.all, "list"] as const,
  list: (filter: TradingSessionSearchFilter) => [...sessionsQueryKeys.lists(), filter] as const,
  details: () => [...sessionsQueryKeys.all, "detail"] as const,
  detail: (id: number) => [...sessionsQueryKeys.details(), id] as const,
  picks: (id: number) => [...sessionsQueryKeys.all, "picks", id] as const,
  pickList: (id: number, filter: SessionPickSearchFilter) => [...sessionsQueryKeys.picks(id), filter] as const,
};
