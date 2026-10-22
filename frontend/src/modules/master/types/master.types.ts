import { BaseFilter } from "../../../core/types/filter.types";

export interface Conversation {
  id: number;
  title: string;
  summary?: string;
  lastMessageAt: string;
  messageCount: number;
  createdByUserId?: number;
  archived: boolean;
  createdAt: string;
  status: string | number;
}
export interface ConversationCreate { title?: string; }
export interface ConversationUpdate { title?: string; archived?: boolean; }
export interface ConversationFilter extends BaseFilter { archived?: boolean; }

export type MessageRole = "user" | "assistant" | "tool" | "system";
export interface MessageBlock { type: string; [key: string]: unknown; }
export interface Message {
  id: number;
  conversationId: number;
  seq: number;
  role: MessageRole;
  content: string;
  blocks?: MessageBlock[];
  runId?: number;
  redacted: boolean;
  model?: string;
  tokensIn?: number;
  tokensOut?: number;
  latencyMs?: number;
  createdAt: string;
}
export interface SendMessageRequest {
  content: string;
  replyToMessageId?: number;
  choice?: string;
}
export interface SendMessageResponse { messageId: number; runId: number; }
export interface MessageFilter extends BaseFilter { conversationId?: number; }

export type RunState = "PENDING" | "RUNNING" | "AWAITING_CONFIRMATION" | "DONE" | "CANCELLED" | "ERROR";
export interface Run {
  id: number;
  conversationId: number;
  userMessageId?: number;
  state: RunState;
  intent?: string;
  threadId: string;
  iterations: number;
  toolCallCount: number;
  clarificationRound: number;
  startedAt: string;
  finishedAt?: string;
  error?: string;
}

export type SseEventType =
  | "run_started" | "thinking" | "tool_call" | "tool_result"
  | "clarification" | "proposal_ready" | "message_delta"
  | "message_complete" | "run_done" | "run_error";
export interface SseEvent { event: SseEventType; data: Record<string, unknown>; }

export type ProposalKind = "CREATE_STRATEGY" | "UPDATE_STRATEGY" | "CREATE_RULE" | "UPDATE_RULE" | "DELETE_STRATEGY" | "DELETE_RULE";
export type ProposalStatus = "PENDING" | "CONFIRMED" | "REJECTED" | "EXPIRED" | "EXECUTED" | "FAILED";
export type ConfirmMode = "ADD_AS_DRAFT" | "ADD_AND_ACTIVATE" | "APPLY";
export interface Complication {
  code: string;
  severity: "INFO" | "WARNING" | "BLOCKER";
  message: string;
}
export interface Proposal {
  id: number;
  conversationId: number;
  messageId?: number;
  kind: ProposalKind;
  targetType?: string;
  targetCode?: string;
  userText: string;
  backTranslation: string;
  payload: Record<string, unknown>;
  diff?: Record<string, unknown>;
  complications: Complication[];
  assumptions: string[];
  structureAnalysis?: Record<string, unknown>;
  validation?: Record<string, unknown>;
  contentHash: string;
  proposalStatus: ProposalStatus;
  expiresAt: string;
  confirmedAt?: string;
  confirmMode?: ConfirmMode;
  resultRefs?: Record<string, unknown>;
  failureReason?: string;
  createdAt: string;
}
export interface ProposalFilter extends BaseFilter {
  conversationId?: number;
  kind?: ProposalKind;
  targetCode?: string;
  proposalStatus?: ProposalStatus;
}
export interface ConfirmProposalRequest {
  mode: ConfirmMode;
  acknowledgedComplicationCodes: string[];
  typedPhrase?: string;
}
export interface RejectProposalRequest { reason?: string; }

export type ToolTier = "READ" | "ANALYZE" | "PROPOSE" | "OPERATE";
export interface ToolPolicy {
  id: number;
  serverName: string;
  toolName: string;
  tier: ToolTier;
  enabled: boolean;
  autoApprove: boolean;
}
export interface ToolServer {
  id: number;
  name: string;
  transport: string;
  url?: string;
  authRef?: string;
  tierCap: ToolTier;
  enabled: boolean;
  lastSeenAt?: string;
  lastError?: string;
  toolCount: number;
  createdAt: string;
}
export interface MasterHealth {
  llmHealthy: boolean;
  llmProvider: string;
  llmModel: string;
  servers: Array<{ name: string; enabled: boolean; lastSeenAt?: string; lastError?: string }>;
  totalTools: number;
}
