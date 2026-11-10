import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import {
  ActiveTrade,
  LotSuggestion,
  TradeAdjustPayload,
  TradeCreatePayload,
  TradeExitPayload,
  TradeSearchFilter,
} from "../types/trades.types";

export async function previewTradeSizing(
  sessionId: number,
  pickId: number,
  entryAt?: number
): Promise<LotSuggestion> {
  return httpClient.get("/trades/preview-sizing", {
    params: {
      sessionId,
      pickId,
      ...(entryAt && entryAt > 0 ? { entryAt } : {}),
    },
  });
}

export async function createTrade(payload: TradeCreatePayload): Promise<ActiveTrade> {
  return httpClient.post("/trades", payload);
}

export async function searchTrades(filter: TradeSearchFilter): Promise<PageResult<ActiveTrade>> {
  return httpClient.post("/trades/search", filter);
}

export async function getTrade(id: number): Promise<ActiveTrade> {
  return httpClient.get(`/trades/${id}`);
}

export async function adjustTrade(id: number, payload: TradeAdjustPayload): Promise<ActiveTrade> {
  return httpClient.post(`/trades/${id}/adjust`, payload);
}

export async function exitTrade(id: number, payload: TradeExitPayload = {}): Promise<ActiveTrade> {
  return httpClient.post(`/trades/${id}/exit`, payload);
}

