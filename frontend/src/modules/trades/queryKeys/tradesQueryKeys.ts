import { TradeSearchFilter } from "../types/trades.types";

export const tradesQueryKeys = {
  all: ["trades"] as const,
  lists: () => [...tradesQueryKeys.all, "list"] as const,
  list: (filter: TradeSearchFilter) => [...tradesQueryKeys.lists(), filter] as const,
  details: () => [...tradesQueryKeys.all, "detail"] as const,
  detail: (id: number) => [...tradesQueryKeys.details(), id] as const,
  sizing: (sessionId: number, pickId: number, entryAt?: number) =>
    [...tradesQueryKeys.all, "sizing", sessionId, pickId, entryAt ?? null] as const,
};

