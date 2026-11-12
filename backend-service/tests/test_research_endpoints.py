"""Research / System API wiring + the MCP confirmation gate.

Rewritten 11 Nov 2026: the previous version targeted endpoints that never existed in this codebase
(/research/underlyings|sources|risk-terms/search, /research/config, research_run_entity) and needed a live
Postgres. Route wiring and the token gate are tested without a database; the DB round-trip is an integration test
that runs only when Postgres is reachable."""
import asyncio

import pytest

from app.main import app
from app.modules.research.mcp.confirmation_token import ConfirmationTokenValidator


def _paths() -> set[str]:
    return set(app.openapi()["paths"])


def test_system_and_research_routes_are_mounted():
    p = _paths()
    for want in ("/api/v1/system/status", "/api/v1/system/engines/search", "/api/v1/research/run",
                 "/api/v1/research/run-status", "/api/v1/research/search", "/api/v1/research/results/latest",
                 ):
        assert want in p, want


def test_mcp_operate_tools_need_a_single_use_confirmation_token():
    v = ConfirmationTokenValidator(secret="test-secret-32-bytes-long-000000")
    args = {"scope": ["INDEX"]}
    ok, why = v.validate_token("", "run_research", args)
    assert not ok and "CONFIRMATION_REQUIRED" in why
    tok = v.mint_token("run_research", args, nonce="n-1")
    assert v.validate_token(tok, "run_research", args)[0]
    ok2, why2 = v.validate_token(tok, "run_research", args)
    assert not ok2 and "TOKEN_ALREADY_USED" in why2
    assert not v.validate_token(v.mint_token("run_research", args, nonce="n-2"), "run_research", {"scope": ["X"]})[0]


def _postgres_up() -> bool:
    from sqlalchemy import text

    from app.core.db.session import async_session_factory

    async def ping():
        async with async_session_factory() as s:
            await s.execute(text("select 1"))

    try:
        asyncio.run(asyncio.wait_for(ping(), 3))
        return True
    except Exception:
        return False


@pytest.mark.skipif(not _postgres_up(), reason="integration: needs the docker Postgres")
def test_research_latest_results_round_trip():
    from httpx import ASGITransport, AsyncClient

    async def go():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
            r = await c.get("/api/v1/research/results/latest")
            assert r.status_code == 200 and r.json()["statusCode"] == 200
            s = await c.get("/api/v1/system/status")
            assert s.status_code == 200

    asyncio.run(go())
