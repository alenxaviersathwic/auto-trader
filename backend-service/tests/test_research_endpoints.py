import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.modules.research.mcp.confirmation_token import confirmation_validator


@pytest_asyncio.fixture(loop_scope="session")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio(loop_scope="session")
async def test_system_status_and_engine_search(client: AsyncClient):
    # 1. System status
    resp = await client.get("/api/v1/system/status")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert "components" in data
    assert any(c["name"] == "Database" for c in data["components"])
    assert any(c["name"] == "pgvector" for c in data["components"])

    # 2. Engines search
    resp_eng = await client.post("/api/v1/system/engines/search", json={"page": 0, "limit": 10})
    assert resp_eng.status_code == 200
    eng_data = resp_eng.json()["data"]
    assert eng_data["totalItems"] >= 1
    assert any(e["code"] == "research" for e in eng_data["list"])


@pytest.mark.asyncio(loop_scope="session")
async def test_research_setup_and_results(client: AsyncClient):
    # Underlyings search
    u_resp = await client.post("/api/v1/research/underlyings/search", json={"page": 0, "limit": 20})
    assert u_resp.status_code == 200
    u_items = u_resp.json()["data"]["list"]
    assert any(u["code"] == "NIFTY" for u in u_items)
    assert any(u["code"] == "CRUDEOIL" for u in u_items)

    # Sources search
    s_resp = await client.post("/api/v1/research/sources/search", json={"page": 0, "limit": 20})
    assert s_resp.status_code == 200
    assert s_resp.json()["data"]["totalItems"] >= 5

    # Risk terms search
    r_resp = await client.post("/api/v1/research/risk-terms/search", json={"page": 0, "limit": 30})
    assert r_resp.status_code == 200
    assert r_resp.json()["data"]["totalItems"] >= 10

    # Config
    c_resp = await client.get("/api/v1/research/config")
    assert c_resp.status_code == 200
    assert c_resp.json()["data"]["version"] == 1

    # Results latest
    res_resp = await client.get("/api/v1/research/results/latest?underlyingType=INDEX")
    assert res_resp.status_code == 200
    data = res_resp.json()["data"]
    assert "suggested" in data
    assert "bearishWatch" in data
    assert "hasNegative" in data
    assert "noCoverage" in data


@pytest.mark.asyncio(loop_scope="session")
async def test_mcp_research_tools_and_gate(client: AsyncClient):
    headers = {"Authorization": "Bearer mcp_research_secret_token_123"}

    # Reset any existing active runs so test starts clean
    from app.core.db.session import async_session_factory
    from sqlalchemy import update
    from app.modules.research.entity.research_run_entity import ResearchRun

    async with async_session_factory() as session:
        await session.execute(
            update(ResearchRun)
            .where(ResearchRun.state.in_(["QUEUED", "RUNNING"]))
            .values(state="CANCELLED")
        )
        await session.commit()

    # 1. READ tool: list_underlyings
    resp = await client.post(
        "/mcp/research/tools/list_underlyings",
        json={"underlyingType": "INDEX"},
        headers=headers,
    )
    assert resp.status_code == 200
    underlyings = resp.json()
    assert any(u["code"] == "NIFTY" for u in underlyings)

    # 2. OPERATE tool without confirmation token -> 403 Forbidden
    bad_resp = await client.post(
        "/mcp/research/tools/run_research",
        json={"scope": ["INDEX"]},
        headers=headers,
    )
    assert bad_resp.status_code == 403
    assert "CONFIRMATION_REQUIRED" in bad_resp.text

    # 3. OPERATE tool with valid single-use confirmation token -> 200 OK
    token = confirmation_validator.mint_token("run_research", {"scope": ["INDEX"]}, nonce="nonce-async-test-101")
    ok_resp = await client.post(
        "/mcp/research/tools/run_research",
        json={"scope": ["INDEX"], "confirmationToken": token},
        headers=headers,
    )
    assert ok_resp.status_code == 200
    assert "runId" in ok_resp.json()

    # 4. Reusing same nonce -> 403 Forbidden (single-use constraint)
    reuse_resp = await client.post(
        "/mcp/research/tools/run_research",
        json={"scope": ["INDEX"], "confirmationToken": token},
        headers=headers,
    )
    assert reuse_resp.status_code == 403
    assert "TOKEN_ALREADY_USED" in reuse_resp.text
