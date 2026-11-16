import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import { BaseFilter } from "../../../core/types/filter.types";
import {
  SessionBatch,
  SessionPick,
  SessionPickSearchFilter,
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

/** Trade Lock: succeeds only while the pick is still OFFERED and its opportunity has not expired (409 otherwise). Returns lockedPrice. */
export async function lockSessionPick(id: number, pickId: number): Promise<SessionPick> {
  return httpClient.post(`/sessions/${id}/picks/${pickId}/lock`);
}

export async function searchSessionPicks(
  id: number,
  filter: SessionPickSearchFilter
): Promise<PageResult<SessionPick>> {
  return httpClient.post(`/sessions/${id}/picks/search`, filter);
}

/** Picks grouped by the loop pass that offered them, newest first. */
export async function searchSessionBatches(id: number, filter: BaseFilter): Promise<PageResult<SessionBatch>> {
  return httpClient.post(`/sessions/${id}/batches/search`, filter);
}

/** Session manager checks one batch against real 1-minute candles and the trades taken from it. */
export async function analyseSessionBatch(id: number, batchKey: string): Promise<SessionBatch> {
  return httpClient.post(`/sessions/${id}/batches/analyse`, { batchKey });
}
