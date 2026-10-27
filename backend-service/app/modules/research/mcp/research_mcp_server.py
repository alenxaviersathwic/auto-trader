import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config.settings import settings
from app.core.db.session import async_session_factory, get_db
from app.core.exception.app_exceptions import NotFoundException
from app.core.logging.logger import logger
from app.core.response.response_helper import success
from app.modules.research.entity.research_entity import ResearchCandidate, ResearchEntity, ResearchRun
from app.modules.research.mcp.confirmation_token import confirmation_validator
from app.modules.research.service.run_service import run_service
from app.modules.research.service.semantic_search_service import SemanticSearchService

RESEARCH_MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "get_latest_results",
        "tier": "READ",
        "description": "Get latest evaluated market research candidates (scores, clearance status, bullish/bearish weights) for INDEX or COMMODITY.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "underlyingType": {
                    "type": "string",
                    "enum": ["INDEX", "COMMODITY"],
                    "default": "INDEX",
                    "description": "Asset class scope: INDEX or COMMODITY",
                }
            },
        },
    },
    {
        "name": "get_candidate",
        "tier": "READ",
        "description": "Get detailed research intelligence for an underlying (e.g. SENSEX, NIFTY, GOLD, CRUDEOIL), including Daily Intelligence Blog Summary, market-affecting catalyst news, latest news today, neutral commentary, clearance thesis, and vector memory status.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "underlyingCode": {"type": "string", "description": "Underlying symbol e.g. NIFTY, SENSEX, GOLD, CRUDEOIL"},
                "runId": {"type": "integer", "description": "Optional specific research run ID"},
            },
            "required": ["underlyingCode"],
        },
    },
    {
        "name": "search_claims",
        "tier": "READ",
        "description": "Search verified source quotes and driver claims for an underlying filtered by stance (BULLISH or BEARISH).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "underlyingCode": {"type": "string", "description": "Optional underlying symbol"},
                "stance": {"type": "string", "enum": ["BULLISH", "BEARISH"], "description": "Filter by stance"},
                "limit": {"type": "integer", "default": 15, "description": "Maximum quotes to return"},
            },
        },
    },
    {
        "name": "list_underlyings",
        "tier": "READ",
        "description": "List all supported trading underlyings across Indices and Commodities with their current evaluation score.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "underlyingType": {"type": "string", "enum": ["INDEX", "COMMODITY"], "description": "Optional scope filter"},
            },
        },
    },
    {
        "name": "semantic_search",
        "tier": "READ",
        "description": "Search evaluated research candidates and their theses.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text"},
                "underlyingCode": {"type": "string", "description": "Optional underlying symbol"},
                "topK": {"type": "integer", "default": 5},
            },
        },
    },
    {
        "name": "get_run_status",
        "tier": "READ",
        "description": "Get progress and state of the latest or specific research engine execution run.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runId": {"type": "integer", "description": "Optional run ID; if omitted, checks active or latest run"},
            },
        },
    },
    {
        "name": "search_runs",
        "tier": "READ",
        "description": "Search past research execution runs.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer", "default": 10},
                "state": {"type": "string", "description": "Optional run state filter (e.g. COMPLETED, RUNNING, FAILED)"},
            },
        },
    },
    {
        "name": "list_sources",
        "tier": "READ",
        "description": "List market news publishers and RSS feeds monitored by the Research Engine.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "run_research",
        "tier": "OPERATE",
        "description": "Trigger a fresh market research pipeline run across Indices and Commodities. Requires confirmation token.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "scope": {"type": "array", "items": {"type": "string"}, "description": "List of scopes: INDEX, COMMODITY"},
                "confirmationToken": {"type": "string", "description": "HMAC confirmation token required for OPERATE tier"},
            },
        },
    },
    {
        "name": "cancel_research_run",
        "tier": "OPERATE",
        "description": "Cancel a currently running research pipeline run. Requires confirmation token.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "runId": {"type": "integer", "description": "ID of the run to cancel"},
                "confirmationToken": {"type": "string", "description": "HMAC confirmation token required for OPERATE tier"},
            },
            "required": ["runId"],
        },
    },
]


class ResearchMcpServer:
    """
    In-process and HTTP MCP server for Research Engine module.
    Provides verified market sentiment, news catalysts, blog briefings, and pipeline controls to AI Master.
    """

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return RESEARCH_MCP_TOOLS

    async def execute_tool(
        self,
        session: AsyncSession,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Executes a research tool call and returns the result dictionary."""
        logger.info(f"Research MCP tool execution requested: {tool_name}")

        if tool_name == "get_latest_results":
            underlying_type = arguments.get("underlyingType", "INDEX")
            return await run_service.get_latest_results(underlying_type, session)

        elif tool_name == "get_candidate":
            code = arguments.get("underlyingCode", "").upper()
            run_id = arguments.get("runId")
            if not code:
                return {"error": "underlyingCode is required"}

            query = select(ResearchCandidate).where(ResearchCandidate.underlyingCode == code)
            if run_id:
                query = query.where(ResearchCandidate.runId == run_id)
            else:
                query = query.order_by(ResearchCandidate.id.desc())

            res = await session.execute(query.limit(1))
            c = res.scalar_one_or_none()
            if not c:
                return {"error": f"Candidate for '{code}' not found"}

            citations = [
                {"statement": sp.get("text", ""), "domain": "Market Intelligence"}
                for sp in (c.supportingPoints or [])
            ]

            return {
                "underlyingCode": c.underlyingCode,
                "underlyingType": c.underlyingType,
                "newsStatus": c.newsStatus,
                "suggested": c.suggested,
                "rank": c.rank,
                "score": float(c.score) if c.score is not None else None,
                "reasons": c.reasons or [],
                "flags": c.flags or [],
                "thesis": c.thesis,
                "supportingPoints": c.supportingPoints or [],
                "watchItems": c.watchItems or [],
                "citations": citations,
                "blogSummary": c.blogSummary,
                "latestNews": c.latestNews or [],
                "affectNews": c.affectNews or [],
                "neutralNews": c.neutralNews or [],
                "hasVectorEmbedding": c.briefEmbedding is not None,
            }

        elif tool_name == "search_claims":
            code = arguments.get("underlyingCode")
            stance = arguments.get("stance")
            limit = min(30, max(1, arguments.get("limit", 15)))

            q = select(ResearchEntity).where(ResearchEntity.status == 1)
            if code:
                q = q.where(ResearchEntity.underlyingCode == code.upper())
            candidates = (await session.execute(q.limit(limit))).scalars().all()
            claims_list = []
            for c in candidates:
                if not stance or stance.upper() == "BULLISH":
                    for sp in c.supportingPoints or []:
                        claims_list.append({
                            "claimId": 1,
                            "underlyingCode": c.underlyingCode,
                            "stance": "BULLISH",
                            "statement": sp.get("text", ""),
                            "quote": sp.get("text", ""),
                            "domain": "Market Intelligence",
                        })
                if not stance or stance.upper() == "BEARISH":
                    for wi in c.watchItems or []:
                        claims_list.append({
                            "claimId": 2,
                            "underlyingCode": c.underlyingCode,
                            "stance": "BEARISH",
                            "statement": wi.get("text", ""),
                            "quote": wi.get("text", ""),
                            "domain": "Risk Monitoring",
                        })
            return {"claims": claims_list[:limit]}

        elif tool_name == "semantic_search":
            top_k = min(10, max(1, arguments.get("topK", 5)))
            q = select(ResearchEntity).where(ResearchEntity.status == 1)
            if arguments.get("underlyingCode"):
                q = q.where(ResearchEntity.underlyingCode == arguments["underlyingCode"].upper())
            items = (await session.execute(q.limit(top_k))).scalars().all()
            return {
                "results": [
                    {
                        "code": u.underlyingCode,
                        "scope": u.underlyingType,
                        "score": float(u.score) if u.score is not None else None,
                        "thesis": u.thesis,
                        "blogSummary": u.blogSummary,
                    }
                    for u in items
                ]
            }

        elif tool_name == "list_underlyings":
            u_type = arguments.get("underlyingType")
            q = select(ResearchEntity).where(ResearchEntity.status == 1)
            if u_type:
                q = q.where(ResearchEntity.underlyingType == u_type.upper())
            items = (await session.execute(q)).scalars().all()
            return {
                "underlyings": [
                    {
                        "code": u.underlyingCode,
                        "name": u.underlyingCode,
                        "underlyingType": u.underlyingType,
                        "newsStatus": u.newsStatus,
                        "score": float(u.score) if u.score is not None else None,
                        "hasVectorEmbedding": u.briefEmbedding is not None,
                    }
                    for u in items
                ]
            }

        elif tool_name == "list_sources":
            return {
                "sources": [
                    {"name": "Economic Times Markets", "sourceType": "RSS", "enabled": True},
                    {"name": "Moneycontrol News", "sourceType": "RSS", "enabled": True},
                    {"name": "Livemint Markets", "sourceType": "RSS", "enabled": True},
                    {"name": "Business Standard Markets", "sourceType": "RSS", "enabled": True},
                    {"name": "Reuters India Business", "sourceType": "RSS", "enabled": True},
                ]
            }

        elif tool_name == "get_run_status":
            run_id = arguments.get("runId")
            if run_id:
                r_res = await session.execute(select(ResearchRun).where(ResearchRun.id == run_id))
                r = r_res.scalar_one_or_none()
            else:
                r_res = await session.execute(
                    select(ResearchRun)
                    .where(ResearchRun.status == 1)
                    .order_by(ResearchRun.id.desc())
                    .limit(1)
                )
                r = r_res.scalar_one_or_none()

            if not r:
                return {"error": "Run not found"}

            return {
                "runId": r.id,
                "state": r.state,
                "currentNode": r.currentNode,
                "progressPct": r.progressPct,
                "stats": r.stats,
                "error": r.error,
                "startedAt": r.startedAt.isoformat() if r.startedAt else None,
                "finishedAt": r.finishedAt.isoformat() if r.finishedAt else None,
            }

        elif tool_name == "search_runs":
            limit = min(20, max(1, arguments.get("limit", 10)))
            state_filter = arguments.get("state")
            q = select(ResearchRun).where(ResearchRun.status == 1)
            if state_filter:
                q = q.where(ResearchRun.state == state_filter)
            q = q.order_by(ResearchRun.id.desc()).limit(limit)

            runs = (await session.execute(q)).scalars().all()
            return {
                "runs": [
                    {
                        "runId": r.id,
                        "scope": r.scope,
                        "state": r.state,
                        "resultKind": r.resultKind,
                        "startedAt": r.startedAt.isoformat() if r.startedAt else None,
                        "finishedAt": r.finishedAt.isoformat() if r.finishedAt else None,
                    }
                    for r in runs
                ]
            }

        elif tool_name == "run_research":
            token = arguments.get("confirmationToken", "")
            args_without_token = {k: v for k, v in arguments.items() if k != "confirmationToken"}
            is_valid, reason = confirmation_validator.validate_token(token, "run_research", args_without_token)
            if not is_valid:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

            run_id = await run_service.start_run(
                scope=arguments.get("scope"),
                params=args_without_token,
                trigger_source="MASTER",
                session=session,
            )
            return {"runId": run_id, "state": "QUEUED"}

        elif tool_name == "cancel_research_run":
            token = arguments.get("confirmationToken", "")
            args_without_token = {k: v for k, v in arguments.items() if k != "confirmationToken"}
            is_valid, reason = confirmation_validator.validate_token(token, "cancel_research_run", args_without_token)
            if not is_valid:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

            run_id = arguments.get("runId")
            if not run_id:
                return {"error": "runId required"}

            await run_service.cancel_run(run_id, session)
            return {"cancelledRunId": run_id, "state": "CANCELLED"}

        else:
            raise NotFoundException(message=f"Tool '{tool_name}' not recognized by Research MCP server")


research_mcp_instance = ResearchMcpServer()
research_mcp_router = APIRouter(prefix="/mcp/research", tags=["Research MCP Server"])


def verify_bearer_token(authorization: Optional[str]) -> None:
    expected_token = getattr(settings, "MCP_RESEARCH_TOKEN", "mcp_research_secret_token_123")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    token = authorization.split(" ")[1]
    if token != expected_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid MCP research token")


@research_mcp_router.get("/tools")
async def list_research_tools():
    """Returns available Research Engine MCP tools and their input schemas."""
    return success(data=research_mcp_instance.get_tool_definitions(), message="Research tools listed successfully")


@research_mcp_router.post("/call")
async def call_research_tool(
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """
    Standardized MCP JSON-RPC call handler for external and internal MCP clients.
    """
    verify_bearer_token(authorization)
    tool_name = payload.get("tool") or payload.get("name")
    arguments = payload.get("arguments") or payload.get("parameters") or {}

    if not tool_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool name is required")

    res = await research_mcp_instance.execute_tool(session, tool_name, arguments)
    return success(data=res, message=f"Tool '{tool_name}' executed successfully")


# --- Compatibility routes for individual endpoints ---
@research_mcp_router.post("/tools/get_latest_results")
async def mcp_get_latest_results(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "get_latest_results", body)


@research_mcp_router.post("/tools/get_candidate")
async def mcp_get_candidate(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "get_candidate", body)


@research_mcp_router.post("/tools/search_runs")
async def mcp_search_runs(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "search_runs", body)


@research_mcp_router.post("/tools/get_run_status")
async def mcp_get_run_status(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "get_run_status", body)


@research_mcp_router.post("/tools/search_claims")
async def mcp_search_claims(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "search_claims", body)


@research_mcp_router.post("/tools/semantic_search")
async def mcp_semantic_search(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "semantic_search", body)


@research_mcp_router.post("/tools/list_underlyings")
async def mcp_list_underlyings(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "list_underlyings", body)


@research_mcp_router.post("/tools/list_sources")
async def mcp_list_sources(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "list_sources", body)


@research_mcp_router.post("/tools/run_research")
async def mcp_run_research(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "run_research", body)


@research_mcp_router.post("/tools/cancel_research_run")
async def mcp_cancel_research_run(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    async with async_session_factory() as session:
        return await research_mcp_instance.execute_tool(session, "cancel_research_run", body)
