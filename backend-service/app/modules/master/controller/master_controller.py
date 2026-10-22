from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import get_db
from app.core.exception.app_exceptions import NotFoundException
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import created, success
from app.modules.master.repository.master_config_repository import MasterConfigRepository
from app.modules.master.repository.message_repository import MessageRepository
from app.modules.master.repository.tool_call_repository import ToolCallRepository
from app.modules.master.repository.tool_server_repository import ToolServerRepository
from app.modules.master.schema import (
    ConfirmProposalRequest,
    ConversationCreate,
    ConversationFilter,
    ConversationResponse,
    ConversationUpdate,
    MasterHealthResponse,
    MessageFilter,
    MessageResponse,
    PreferenceFilter,
    PreferenceResponse,
    PreferenceUpdate,
    ProposalFilter,
    ProposalResponse,
    RejectProposalRequest,
    RunResponse,
    SendMessageRequest,
    SendMessageResponse,
    ToolCallFilter,
    ToolCallResponse,
    ToolPolicyFilter,
    ToolResponse,
    ToolServerCreate,
    ToolServerFilter,
    ToolServerResponse,
    ToolServerUpdate,
    ToolUpdate,
)
from app.modules.master.service.conversation_service import ConversationService
from app.modules.master.service.preference_service import PreferenceService
from app.modules.master.service.proposal_service import ProposalService
from app.modules.master.service.run_service import RunService

master_router = APIRouter(prefix="/master", tags=["Master Chat"])

_conv_service = ConversationService()
_run_service = RunService()
_proposal_service = ProposalService()
_pref_service = PreferenceService()
_config_repo = MasterConfigRepository()
_tool_server_repo = ToolServerRepository()
_tool_call_repo = ToolCallRepository()
_message_repo = MessageRepository()


# -------------------------------------------------------------
# Conversations & Messages
# -------------------------------------------------------------

@master_router.post(
    "/conversations",
    response_model=ApiResponse[ConversationResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
async def create_conversation(
    payload: ConversationCreate,
    session: AsyncSession = Depends(get_db),
):
    conv = await _conv_service.create(session, title=payload.title)
    return created(data=conv, message="Conversation created successfully")


@master_router.post(
    "/conversations/search",
    response_model=ApiResponse[PageResult[ConversationResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search conversations with filters and pagination",
)
async def search_conversations(
    filter_obj: ConversationFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _conv_service.search(session, filter_obj)
    return success(data=page_res, message="Conversations retrieved successfully")


@master_router.get(
    "/conversations/{id}",
    response_model=ApiResponse[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="Get one conversation",
)
async def get_conversation(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    conv = await _conv_service.get_by_id(session, id)
    return success(data=conv, message="Conversation retrieved successfully")


@master_router.patch(
    "/conversations/{id}",
    response_model=ApiResponse[ConversationResponse],
    status_code=status.HTTP_200_OK,
    summary="Rename or archive conversation",
)
async def update_conversation(
    id: int,
    payload: ConversationUpdate,
    session: AsyncSession = Depends(get_db),
):
    updated = await _conv_service.update(session, id, title=payload.title, archived=payload.archived)
    return success(data=updated, message="Conversation updated successfully")


@master_router.delete(
    "/conversations/{id}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Soft delete conversation",
)
async def delete_conversation(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    await _conv_service.delete(session, id)
    return success(data={"id": id, "deleted": True}, message="Conversation deleted successfully")


@master_router.post(
    "/conversations/{id}/messages",
    response_model=ApiResponse[SendMessageResponse],
    status_code=status.HTTP_202_ACCEPTED,
    summary="Send user message to Master agent",
)
async def send_message(
    id: int,
    payload: SendMessageRequest,
    session: AsyncSession = Depends(get_db),
):
    result = await _run_service.send_user_message(
        session=session,
        conversation_id=id,
        content=payload.content,
        choice=payload.choice,
    )
    return success(
        data=result,
        message="Message accepted for processing",
        status_code=status.HTTP_202_ACCEPTED,
    )


@master_router.post(
    "/conversations/{id}/messages/search",
    response_model=ApiResponse[PageResult[MessageResponse]],
    status_code=status.HTTP_200_OK,
    summary="Get conversation message history",
)
async def search_messages(
    id: int,
    filter_obj: MessageFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _message_repo.search(session, id, filter_obj)
    return success(data=page_res, message="Messages retrieved successfully")


# -------------------------------------------------------------
# Runs and Server-Sent Events (SSE)
# -------------------------------------------------------------

@master_router.get(
    "/runs/{runId}/events",
    summary="Server-sent events stream for Master run",
)
async def stream_run_events(runId: int):
    return StreamingResponse(
        _run_service.stream_events(runId),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@master_router.get(
    "/runs/{runId}",
    response_model=ApiResponse[RunResponse],
    status_code=status.HTTP_200_OK,
    summary="Get run status and details",
)
async def get_run(
    runId: int,
    session: AsyncSession = Depends(get_db),
):
    run = await _run_service.get_run(session, runId)
    return success(data=run, message="Run retrieved successfully")


@master_router.post(
    "/runs/{runId}/cancel",
    response_model=ApiResponse[RunResponse],
    status_code=status.HTTP_200_OK,
    summary="Cancel active run",
)
async def cancel_run(
    runId: int,
    session: AsyncSession = Depends(get_db),
):
    cancelled = await _run_service.cancel_run(session, runId)
    return success(data=cancelled, message="Run cancelled successfully")


# -------------------------------------------------------------
# Proposals
# -------------------------------------------------------------

@master_router.post(
    "/proposals/search",
    response_model=ApiResponse[PageResult[ProposalResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search proposals with filters",
)
async def search_proposals(
    filter_obj: ProposalFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _proposal_service.search(session, filter_obj)
    return success(data=page_res, message="Proposals retrieved successfully")


@master_router.get(
    "/proposals/{id}",
    response_model=ApiResponse[ProposalResponse],
    status_code=status.HTTP_200_OK,
    summary="Get full proposal details",
)
async def get_proposal(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    prop = await _proposal_service.get_by_id(session, id)
    return success(data=prop, message="Proposal retrieved successfully")


@master_router.post(
    "/proposals/{id}/confirm",
    response_model=ApiResponse[ProposalResponse],
    status_code=status.HTTP_200_OK,
    summary="Human confirmation executing proposal through Strategy module",
)
async def confirm_proposal(
    id: int,
    payload: ConfirmProposalRequest,
    session: AsyncSession = Depends(get_db),
):
    confirmed = await _proposal_service.confirm(
        session=session,
        proposal_id=id,
        mode=payload.mode,
        acknowledged_codes=payload.acknowledgedComplicationCodes,
        typed_phrase=payload.typedPhrase,
    )
    return success(data=confirmed, message="Proposal confirmed and executed successfully")


@master_router.post(
    "/proposals/{id}/reject",
    response_model=ApiResponse[ProposalResponse],
    status_code=status.HTTP_200_OK,
    summary="Reject proposal",
)
async def reject_proposal(
    id: int,
    payload: RejectProposalRequest,
    session: AsyncSession = Depends(get_db),
):
    rejected = await _proposal_service.reject(session, id, payload.reason)
    return success(data=rejected, message="Proposal rejected")


@master_router.post(
    "/proposals/{id}/revalidate",
    response_model=ApiResponse[ProposalResponse],
    status_code=status.HTTP_200_OK,
    summary="Revalidate proposal against current registry and rules",
)
async def revalidate_proposal(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    revalidated = await _proposal_service.revalidate(session, id)
    return success(data=revalidated, message="Proposal revalidated successfully")


# -------------------------------------------------------------
# Tools, Servers, and Audit
# -------------------------------------------------------------

@master_router.post(
    "/tools/search",
    response_model=ApiResponse[PageResult[ToolResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search tool policies",
)
async def search_tools(
    filter_obj: ToolPolicyFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _tool_server_repo.search_policies(session, filter_obj)
    return success(data=page_res, message="Tool policies retrieved successfully")


@master_router.patch(
    "/tools/{id}",
    response_model=ApiResponse[ToolResponse],
    status_code=status.HTTP_200_OK,
    summary="Enable or disable a tool policy",
)
async def update_tool_policy(
    id: int,
    payload: ToolUpdate,
    session: AsyncSession = Depends(get_db),
):
    policy = await _tool_server_repo.get_policy_by_id(session, id)
    if not policy:
        raise NotFoundException(message=f"Tool policy #{id} not found")
    policy.enabled = payload.enabled
    saved = await _tool_server_repo.save_policy(session, policy)
    return success(data=saved, message="Tool policy updated successfully")


@master_router.post(
    "/tool-servers/search",
    response_model=ApiResponse[PageResult[ToolServerResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search registered tool servers",
)
async def search_tool_servers(
    filter_obj: ToolServerFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _tool_server_repo.search(session, filter_obj)
    return success(data=page_res, message="Tool servers retrieved successfully")


@master_router.post(
    "/tool-servers",
    response_model=ApiResponse[ToolServerResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new tool server",
)
async def create_tool_server(
    payload: ToolServerCreate,
    session: AsyncSession = Depends(get_db),
):
    server = ToolServerResponse(
        name=payload.name,
        transport=payload.transport,
        url=payload.url,
        authRef=payload.authRef,
        tierCap=payload.tierCap,
        enabled=True,
    )
    saved = await _tool_server_repo.save(session, server)
    return created(data=saved, message="Tool server registered successfully")


@master_router.put(
    "/tool-servers/{id}",
    response_model=ApiResponse[ToolServerResponse],
    status_code=status.HTTP_200_OK,
    summary="Update tool server registration",
)
async def update_tool_server(
    id: int,
    payload: ToolServerUpdate,
    session: AsyncSession = Depends(get_db),
):
    server = await _tool_server_repo.get_by_id(session, id)
    if not server:
        raise NotFoundException(message=f"Tool server #{id} not found")
    if payload.transport is not None:
        server.transport = payload.transport
    if payload.url is not None:
        server.url = payload.url
    if payload.authRef is not None:
        server.authRef = payload.authRef
    if payload.tierCap is not None:
        server.tierCap = payload.tierCap
    if payload.enabled is not None:
        server.enabled = payload.enabled
    saved = await _tool_server_repo.save(session, server)
    return success(data=saved, message="Tool server updated successfully")


@master_router.post(
    "/tool-servers/{id}/refresh",
    response_model=ApiResponse[ToolServerResponse],
    status_code=status.HTTP_200_OK,
    summary="Refresh server tool list and status",
)
async def refresh_tool_server(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    server = await _tool_server_repo.get_by_id(session, id)
    if not server:
        raise NotFoundException(message=f"Tool server #{id} not found")
    server.lastSeenAt = datetime.now(timezone.utc)
    server.lastError = None
    saved = await _tool_server_repo.save(session, server)
    return success(data=saved, message="Tool server refreshed successfully")


@master_router.post(
    "/tool-calls/search",
    response_model=ApiResponse[PageResult[ToolCallResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search audit log of executed tool calls",
)
async def search_tool_calls(
    filter_obj: ToolCallFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _tool_call_repo.search(session, filter_obj)
    return success(data=page_res, message="Tool call audit logs retrieved successfully")


# -------------------------------------------------------------
# Preferences and Configuration
# -------------------------------------------------------------

@master_router.post(
    "/preferences/search",
    response_model=ApiResponse[PageResult[PreferenceResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search saved user preferences",
)
async def search_preferences(
    filter_obj: PreferenceFilter,
    session: AsyncSession = Depends(get_db),
):
    page_res = await _pref_service.search(session, filter_obj)
    return success(data=page_res, message="Preferences retrieved successfully")


@master_router.put(
    "/preferences/{key}",
    response_model=ApiResponse[PreferenceResponse],
    status_code=status.HTTP_200_OK,
    summary="Set a user preference",
)
async def set_preference(
    key: str,
    payload: PreferenceUpdate,
    session: AsyncSession = Depends(get_db),
):
    pref = await _pref_service.set_key(session, key, payload.value)
    return success(data=pref, message="Preference saved successfully")


@master_router.delete(
    "/preferences/{key}",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Delete a user preference",
)
async def delete_preference(
    key: str,
    session: AsyncSession = Depends(get_db),
):
    await _pref_service.delete_key(session, key)
    return success(data={"key": key, "deleted": True}, message="Preference deleted successfully")


@master_router.get(
    "/config",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Get master agent runtime configuration",
)
async def get_config(
    session: AsyncSession = Depends(get_db),
):
    cfg = await _config_repo.get_all_config(session)
    return success(data=cfg, message="Master config retrieved successfully")


@master_router.put(
    "/config",
    response_model=ApiResponse[Dict[str, Any]],
    status_code=status.HTTP_200_OK,
    summary="Update master agent configuration",
)
async def update_config(
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_db),
):
    for k, v in payload.items():
        await _config_repo.set_key(session, k, v)
    updated = await _config_repo.get_all_config(session)
    return success(data=updated, message="Master config updated successfully")


@master_router.get(
    "/health",
    response_model=ApiResponse[MasterHealthResponse],
    status_code=status.HTTP_200_OK,
    summary="Get LLM and tool server health status",
)
async def get_master_health(
    session: AsyncSession = Depends(get_db),
):
    llm_ok = await _run_service.llm.is_healthy()
    servers_page = await _tool_server_repo.search(session, ToolServerFilter(page=0, limit=10))
    server_list = [
        {"name": s.name, "enabled": s.enabled, "lastSeenAt": s.lastSeenAt, "lastError": s.lastError}
        for s in servers_page.list
    ]
    total_tools = sum(s.toolCount for s in servers_page.list)

    health_info = MasterHealthResponse(
        llmHealthy=llm_ok,
        llmProvider="ollama",
        llmModel=_run_service.llm.default_model,
        servers=server_list,
        totalTools=total_tools,
    )
    return success(data=health_info, message="Master health status retrieved")
