import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import {
  TradingSession,
  TradingSessionCreatePayload,
  TradingSessionSearchFilter,
  TradingSessionUpdatePayload,
} from "../types/sessions.types";

export async function searchSessions(
  filter: TradingSessionSearchFilter
): Promise<PageResult<TradingSession>> {
  return httpClient.post("/sessions/search", filter);
}

export async function getSession(id: number): Promise<TradingSession> {
  return httpClient.get(`/sessions/${id}`);
}

export async function createSession(
  payload: TradingSessionCreatePayload
): Promise<TradingSession> {
  return httpClient.post("/sessions", payload);
}

export async function updateSession(
  id: number,
  payload: TradingSessionUpdatePayload
): Promise<TradingSession> {
  return httpClient.put(`/sessions/${id}`, payload);
}

export async function deleteSession(
  id: number
): Promise<{ id: number; deleted: boolean }> {
  return httpClient.delete(`/sessions/${id}`);
}
