from datetime import datetime
from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, Field
from app.core.db.entity_status import EntityStatus
from app.core.filter.base_filter import BaseFilter


# Conversations
class ConversationCreate(BaseModel):
    title: Optional[str] = None


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    archived: Optional[bool] = None


class ConversationResponse(BaseModel):
    id: int
    title: str
    summary: Optional[str] = None
    lastMessageAt: datetime
    messageCount: int
    createdByUserId: Optional[int] = None
    archived: bool
    createdAt: datetime
    status: Union[EntityStatus, str] = EntityStatus.ACTIVE

    model_config = {"populate_by_name": True, "from_attributes": True}


class ConversationFilter(BaseFilter):
    archived: Optional[bool] = None


# Messages
class SendMessageRequest(BaseModel):
    content: str = Field(..., max_length=4000)
    replyToMessageId: Optional[int] = None
    choice: Optional[str] = None


class SendMessageResponse(BaseModel):
    messageId: int
    runId: int


class MessageResponse(BaseModel):
    id: int
    conversationId: int
    seq: int
    role: str
    content: str
    blocks: Optional[List[Dict[str, Any]]] = None
    runId: Optional[int] = None
    redacted: bool
    model: Optional[str] = None
    tokensIn: Optional[int] = None
    tokensOut: Optional[int] = None
    latencyMs: Optional[int] = None
    createdAt: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class MessageFilter(BaseFilter):
    conversationId: Optional[int] = None


# Runs
class RunResponse(BaseModel):
    id: int
    conversationId: int
    userMessageId: Optional[int] = None
    state: str
    intent: Optional[str] = None
    threadId: str
    iterations: int
    toolCallCount: int
    clarificationRound: int
    startedAt: datetime
    finishedAt: Optional[datetime] = None
    error: Optional[str] = None

    model_config = {"populate_by_name": True, "from_attributes": True}


# Proposals
class ProposalResponse(BaseModel):
    id: int
    conversationId: int
    messageId: Optional[int] = None
    kind: str
    targetType: Optional[str] = None
    targetCode: Optional[str] = None
    userText: str
    backTranslation: str
    payload: Dict[str, Any]
    diff: Optional[Dict[str, Any]] = None
    complications: List[Dict[str, Any]]
    assumptions: List[str]
    structureAnalysis: Optional[Dict[str, Any]] = None
    validation: Optional[Dict[str, Any]] = None
    contentHash: str
    proposalStatus: str
    expiresAt: datetime
    confirmedAt: Optional[datetime] = None
    confirmMode: Optional[str] = None
    resultRefs: Optional[Dict[str, Any]] = None
    failureReason: Optional[str] = None
    createdAt: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class ProposalFilter(BaseFilter):
    conversationId: Optional[int] = None
    kind: Optional[str] = None
    targetCode: Optional[str] = None
    proposalStatus: Optional[str] = None


class ConfirmProposalRequest(BaseModel):
    mode: str = "ADD_AS_DRAFT"  # ADD_AS_DRAFT, ADD_AND_ACTIVATE, APPLY
    acknowledgedComplicationCodes: List[str] = Field(default_factory=list)
    typedPhrase: Optional[str] = None


class RejectProposalRequest(BaseModel):
    reason: Optional[str] = None


# Tools & Servers
class ToolResponse(BaseModel):
    id: int
    serverName: str
    toolName: str
    tier: str
    enabled: bool
    autoApprove: bool

    model_config = {"populate_by_name": True, "from_attributes": True}


class ToolUpdate(BaseModel):
    enabled: bool


class ToolPolicyFilter(BaseFilter):
    serverName: Optional[str] = None
    tier: Optional[str] = None
    enabled: Optional[bool] = None


class ToolServerResponse(BaseModel):
    id: int
    name: str
    transport: str
    url: Optional[str] = None
    authRef: Optional[str] = None
    tierCap: str
    enabled: bool
    lastSeenAt: Optional[datetime] = None
    lastError: Optional[str] = None
    toolCount: int
    createdAt: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class ToolServerCreate(BaseModel):
    name: str
    transport: str = "HTTP"
    url: Optional[str] = None
    authRef: Optional[str] = None
    tierCap: str = "PROPOSE"


class ToolServerUpdate(BaseModel):
    transport: Optional[str] = None
    url: Optional[str] = None
    authRef: Optional[str] = None
    tierCap: Optional[str] = None
    enabled: Optional[bool] = None


class ToolServerFilter(BaseFilter):
    enabled: Optional[bool] = None


class ToolCallResponse(BaseModel):
    id: int
    runId: int
    serverName: str
    toolName: str
    tier: str
    arguments: Optional[Dict[str, Any]] = None
    resultSummary: Optional[Dict[str, Any]] = None
    callStatus: str
    durationMs: int
    createdAt: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class ToolCallFilter(BaseFilter):
    runId: Optional[int] = None
    serverName: Optional[str] = None
    toolName: Optional[str] = None
    tier: Optional[str] = None
    callStatus: Optional[str] = None


# Preferences
class PreferenceResponse(BaseModel):
    id: int
    key: str
    value: Dict[str, Any]
    sourceMessageId: Optional[int] = None
    createdAt: datetime

    model_config = {"populate_by_name": True, "from_attributes": True}


class PreferenceUpdate(BaseModel):
    value: Any


class PreferenceFilter(BaseFilter):
    pass


# Config & Health
class MasterHealthResponse(BaseModel):
    llmHealthy: bool
    llmProvider: str
    llmModel: str
    servers: List[Dict[str, Any]]
    totalTools: int
