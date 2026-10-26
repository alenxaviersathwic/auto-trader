from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, status
from sqlalchemy import select
from app.core.config.settings import settings
from app.core.db.session import async_session_factory
from app.modules.research.entity.research_entity import ResearchEntity, ResearchCandidate, ResearchRun
from app.modules.research.mcp.confirmation_token import confirmation_validator
from app.modules.research.service.run_service import run_service
from app.modules.research.service.semantic_search_service import SemanticSearchService

research_mcp_router = APIRouter(prefix="/mcp/research", tags=["Research MCP Server"])


def verify_bearer_token(authorization: Optional[str]) -> None:
    expected_token = getattr(settings, "MCP_RESEARCH_TOKEN", "mcp_research_secret_token_123")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bearer token required")
    token = authorization.split(" ")[1]
    if token != expected_token:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid MCP research token")


# --- READ Tools ---
@research_mcp_router.post("/tools/get_latest_results")
async def mcp_get_latest_results(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    underlying_type = body.get("underlyingType", "INDEX")
    async with async_session_factory() as session:
        return await run_service.get_latest_results(underlying_type, session)


@research_mcp_router.post("/tools/get_candidate")
async def mcp_get_candidate(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    code = body.get("underlyingCode", "").upper()
    run_id = body.get("runId")

    async with async_session_factory() as session:
        query = select(ResearchCandidate).where(ResearchCandidate.underlyingCode == code)
        if run_id:
            query = query.where(ResearchCandidate.runId == run_id)
        else:
            query = query.order_by(ResearchCandidate.id.desc())

        res = await session.execute(query.limit(1))
        c = res.scalar_one_or_none()
        if not c:
            return {"error": f"Candidate for '{code}' not found"}

        citations: List[Dict[str, Any]] = [
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
            "reasons": c.reasons,
            "flags": c.flags,
            "thesis": c.thesis,
            "supportingPoints": c.supportingPoints,
            "watchItems": c.watchItems,
            "citations": citations,
        }


@research_mcp_router.post("/tools/search_runs")
async def mcp_search_runs(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    verify_bearer_token(authorization)
    limit = min(20, max(1, body.get("limit", 10)))
    state_filter = body.get("state")

    async with async_session_factory() as session:
        q = select(ResearchRun).where(ResearchRun.status == 1)
        if state_filter:
            q = q.where(ResearchRun.state == state_filter)
        q = q.order_by(ResearchRun.id.desc()).limit(limit)

        runs = (await session.execute(q)).scalars().all()
        return [
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


@research_mcp_router.post("/tools/get_run_status")
async def mcp_get_run_status(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)
    run_id = body.get("runId")
    if not run_id:
        return {"error": "runId required"}

    async with async_session_factory() as session:
        r_res = await session.execute(select(ResearchRun).where(ResearchRun.id == run_id))
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
        }


@research_mcp_router.post("/tools/search_claims")
async def mcp_search_claims(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    verify_bearer_token(authorization)
    code = body.get("underlyingCode")
    stance = body.get("stance")
    limit = min(30, max(1, body.get("limit", 15)))

    async with async_session_factory() as session:
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
        return claims_list[:limit]


@research_mcp_router.post("/tools/semantic_search")
async def mcp_semantic_search(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    verify_bearer_token(authorization)
    query = body.get("query", "")
    top_k = min(10, max(1, body.get("topK", 5)))

    async with async_session_factory() as session:
        q = select(ResearchEntity).where(ResearchEntity.status == 1)
        if body.get("underlyingCode"):
            q = q.where(ResearchEntity.underlyingCode == body["underlyingCode"].upper())
        items = (await session.execute(q.limit(top_k))).scalars().all()
        return [
            {
                "code": u.underlyingCode,
                "scope": u.underlyingType,
                "score": float(u.score) if u.score is not None else None,
                "thesis": u.thesis,
            }
            for u in items
        ]


@research_mcp_router.post("/tools/list_underlyings")
async def mcp_list_underlyings(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    verify_bearer_token(authorization)
    u_type = body.get("underlyingType")

    async with async_session_factory() as session:
        q = select(ResearchEntity).where(ResearchEntity.status == 1)
        if u_type:
            q = q.where(ResearchEntity.underlyingType == u_type.upper())
        items = (await session.execute(q)).scalars().all()
        return [
            {
                "code": u.underlyingCode,
                "name": u.underlyingCode,
                "underlyingType": u.underlyingType,
                "newsStatus": u.newsStatus,
                "score": float(u.score) if u.score is not None else None,
            }
            for u in items
        ]


@research_mcp_router.post("/tools/list_sources")
async def mcp_list_sources(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> List[Dict[str, Any]]:
    verify_bearer_token(authorization)
    return [
        {"name": "Economic Times Markets", "sourceType": "RSS", "enabled": True},
        {"name": "Moneycontrol News", "sourceType": "RSS", "enabled": True},
        {"name": "Livemint Markets", "sourceType": "RSS", "enabled": True},
        {"name": "Business Standard Markets", "sourceType": "RSS", "enabled": True},
        {"name": "Reuters India Business", "sourceType": "RSS", "enabled": True},
    ]


# --- OPERATE Tools (Gated by Confirmation Token) ---
@research_mcp_router.post("/tools/run_research")
async def mcp_run_research(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)

    # 1. Enforce Confirmation Token Gate
    token = body.get("confirmationToken", "")
    args_without_token = {k: v for k, v in body.items() if k != "confirmationToken"}
    is_valid, reason = confirmation_validator.validate_token(token, "run_research", args_without_token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    # 2. Trigger run
    async with async_session_factory() as session:
        run_id = await run_service.start_run(
            scope=body.get("scope"),
            params=args_without_token,
            trigger_source="MASTER",
            session=session,
        )
        return {"runId": run_id, "state": "QUEUED"}


@research_mcp_router.post("/tools/cancel_research_run")
async def mcp_cancel_research_run(
    body: Dict[str, Any],
    authorization: Optional[str] = Header(None),
) -> Dict[str, Any]:
    verify_bearer_token(authorization)

    token = body.get("confirmationToken", "")
    args_without_token = {k: v for k, v in body.items() if k != "confirmationToken"}
    is_valid, reason = confirmation_validator.validate_token(token, "cancel_research_run", args_without_token)
    if not is_valid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=reason)

    run_id = body.get("runId")
    if not run_id:
        return {"error": "runId required"}

    async with async_session_factory() as session:
        await run_service.cancel_run(run_id, session)
        return {"cancelledRunId": run_id, "state": "CANCELLED"}
