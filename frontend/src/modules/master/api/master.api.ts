import { httpClient } from "../../../core/api/httpClient";
import { PageResult } from "../../../core/types/pagination.types";
import {
  ConfirmProposalRequest,
  Conversation,
  ConversationCreate,
  ConversationFilter,
  ConversationUpdate,
  MasterHealth,
  Message,
  MessageFilter,
  Proposal,
  ProposalFilter,
  RejectProposalRequest,
  Run,
  SendMessageRequest,
  SendMessageResponse,
  ToolPolicy,
  ToolServer,
} from "../types/master.types";

const BASE = "/master";

// ── Conversations ─────────────────────────────────────────────────────────────
export const searchConversations = (f: ConversationFilter): Promise<PageResult<Conversation>> =>
  httpClient.post(`${BASE}/conversations/search`, f);

export const createConversation = (payload: ConversationCreate): Promise<Conversation> =>
  httpClient.post(`${BASE}/conversations`, payload);

export const getConversation = (id: number): Promise<Conversation> =>
  httpClient.get(`${BASE}/conversations/${id}`);

export const updateConversation = (id: number, payload: ConversationUpdate): Promise<Conversation> =>
  httpClient.patch(`${BASE}/conversations/${id}`, payload);

export const deleteConversation = (id: number): Promise<{ id: number; deleted: boolean }> =>
  httpClient.delete(`${BASE}/conversations/${id}`);

// ── Messages ──────────────────────────────────────────────────────────────────
export const sendMessage = (conversationId: number, payload: SendMessageRequest): Promise<SendMessageResponse> =>
  httpClient.post(`${BASE}/conversations/${conversationId}/messages`, payload);

export const searchMessages = (conversationId: number, filter: MessageFilter): Promise<PageResult<Message>> =>
  httpClient.post(`${BASE}/conversations/${conversationId}/messages/search`, filter);

// ── Runs ──────────────────────────────────────────────────────────────────────
export const getRun = (runId: number): Promise<Run> =>
  httpClient.get(`${BASE}/runs/${runId}`);

export const cancelRun = (runId: number): Promise<Run> =>
  httpClient.post(`${BASE}/runs/${runId}/cancel`);

/** Returns the raw EventSource URL — SSE, not axios */
export const getRunEventsUrl = (runId: number): string =>
  `/api/v1${BASE}/runs/${runId}/events`;

// ── Proposals ─────────────────────────────────────────────────────────────────
export const searchProposals = (filter: ProposalFilter): Promise<PageResult<Proposal>> =>
  httpClient.post(`${BASE}/proposals/search`, filter);

export const getProposal = (id: number): Promise<Proposal> =>
  httpClient.get(`${BASE}/proposals/${id}`);

export const confirmProposal = (id: number, payload: ConfirmProposalRequest): Promise<Proposal> =>
  httpClient.post(`${BASE}/proposals/${id}/confirm`, payload);

export const rejectProposal = (id: number, payload: RejectProposalRequest): Promise<Proposal> =>
  httpClient.post(`${BASE}/proposals/${id}/reject`, payload);

export const revalidateProposal = (id: number): Promise<Proposal> =>
  httpClient.post(`${BASE}/proposals/${id}/revalidate`);

// ── Tool Servers ──────────────────────────────────────────────────────────────
export const searchToolServers = (filter: any): Promise<PageResult<ToolServer>> =>
  httpClient.post(`${BASE}/tool-servers/search`, filter);

export const searchToolPolicies = (filter: any): Promise<PageResult<ToolPolicy>> =>
  httpClient.post(`${BASE}/tools/search`, filter);

// ── Health ────────────────────────────────────────────────────────────────────
export const getMasterHealth = (): Promise<MasterHealth> =>
  httpClient.get(`${BASE}/health`);
