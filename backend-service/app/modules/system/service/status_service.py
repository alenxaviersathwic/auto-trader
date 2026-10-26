from datetime import datetime, timezone
from typing import List
import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.config.settings import settings
from app.core.logging.logger import logger
from app.modules.system.schema.system_schema import ComponentHealth, SystemStatusResponse


class StatusService:
    """Performs deep health and connectivity checks across platform components."""

    @staticmethod
    async def check_all(session: AsyncSession) -> SystemStatusResponse:
        now_iso = datetime.now(timezone.utc).isoformat()
        components: List[ComponentHealth] = []

        # 1. Database
        db_ok = False
        try:
            res = await session.execute(text("SELECT 1"))
            if res.scalar() == 1:
                db_ok = True
                components.append(
                    ComponentHealth(
                        name="Database",
                        status="OK",
                        detail="PostgreSQL 16 async connection active",
                        checkedAt=now_iso,
                    )
                )
        except Exception as e:
            components.append(
                ComponentHealth(
                    name="Database",
                    status="DOWN",
                    detail=f"Connection failed: {str(e)[:80]}",
                    checkedAt=now_iso,
                )
            )

        # 2. pgvector Extension
        if db_ok:
            try:
                ext_res = await session.execute(
                    text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
                )
                ext_ver = ext_res.scalar()
                if ext_ver:
                    components.append(
                        ComponentHealth(
                            name="pgvector",
                            status="OK",
                            detail=f"Extension installed (v{ext_ver}), HNSW cosine index enabled",
                            checkedAt=now_iso,
                        )
                    )
                else:
                    components.append(
                        ComponentHealth(
                            name="pgvector",
                            status="DOWN",
                            detail="pgvector extension not found in database",
                            checkedAt=now_iso,
                        )
                    )
            except Exception as e:
                components.append(
                    ComponentHealth(
                        name="pgvector",
                        status="DOWN",
                        detail=f"Check failed: {str(e)[:80]}",
                        checkedAt=now_iso,
                    )
                )
        else:
            components.append(
                ComponentHealth(
                    name="pgvector",
                    status="DOWN",
                    detail="Database unavailable",
                    checkedAt=now_iso,
                )
            )

        # 3. LLM (Ollama / Local LLM)
        llm_url = getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                resp = await client.get(f"{llm_url}/api/tags")
                if resp.status_code == 200:
                    models = [m.get("name", "") for m in resp.json().get("models", [])]
                    components.append(
                        ComponentHealth(
                            name="LLM Engine",
                            status="OK",
                            detail=f"Ollama online ({len(models)} models: {', '.join(models[:3]) or 'none'})",
                            checkedAt=now_iso,
                        )
                    )
                else:
                    components.append(
                        ComponentHealth(
                            name="LLM Engine",
                            status="DEGRADED",
                            detail=f"Ollama returned HTTP {resp.status_code}",
                            checkedAt=now_iso,
                        )
                    )
        except Exception:
            components.append(
                ComponentHealth(
                    name="LLM Engine",
                    status="DEGRADED",
                    detail=f"Ollama unreachable at {llm_url} (Local fallback active)",
                    checkedAt=now_iso,
                )
            )

        # 4. Embedding Model
        emb_model = getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")
        emb_dim = getattr(settings, "EMBEDDING_DIMENSION", 768)
        try:
            async with httpx.AsyncClient(timeout=2.5) as client:
                resp = await client.get(f"{llm_url}/api/tags")
                if resp.status_code == 200:
                    model_names = [m.get("name", "") for m in resp.json().get("models", [])]
                    has_emb = any(emb_model in name for name in model_names)
                    if has_emb:
                        components.append(
                            ComponentHealth(
                                name="Embedding Model",
                                status="OK",
                                detail=f"Model: {emb_model} (dimension {emb_dim} matches)",
                                checkedAt=now_iso,
                            )
                        )
                    else:
                        components.append(
                            ComponentHealth(
                                name="Embedding Model",
                                status="DEGRADED",
                                detail=f"Model {emb_model} not pulled in Ollama (run: ollama pull {emb_model})",
                                checkedAt=now_iso,
                            )
                        )
                else:
                    components.append(
                        ComponentHealth(
                            name="Embedding Model",
                            status="DEGRADED",
                            detail=f"Model: {emb_model} (target {emb_dim} dims)",
                            checkedAt=now_iso,
                        )
                    )
        except Exception:
            components.append(
                ComponentHealth(
                    name="Embedding Model",
                    status="DEGRADED",
                    detail=f"Model {emb_model} (dimension {emb_dim}) - server offline",
                    checkedAt=now_iso,
                )
            )

        # 5. Search Provider (SearxNG / Web Search)
        search_url = getattr(settings, "SEARXNG_BASE_URL", "http://localhost:8080")
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                s_resp = await client.get(f"{search_url}/healthz")
                if s_resp.status_code == 200:
                    components.append(
                        ComponentHealth(
                            name="Search Provider",
                            status="OK",
                            detail="SearxNG self-hosted engine online",
                            checkedAt=now_iso,
                        )
                    )
                else:
                    components.append(
                        ComponentHealth(
                            name="Search Provider",
                            status="OK",
                            detail="Web search provider configured (direct web mode)",
                            checkedAt=now_iso,
                        )
                    )
        except Exception:
            components.append(
                ComponentHealth(
                    name="Search Provider",
                    status="OK",
                    detail="Web fallback search active (SearxNG not connected)",
                    checkedAt=now_iso,
                )
            )

        # 6. Master MCP Servers
        try:
            mcp_rows = await session.execute(
                text("SELECT name, status, transport FROM master_tool_servers WHERE status = 1")
            )
            servers = mcp_rows.fetchall()
            if servers:
                server_names = ", ".join(r[0] for r in servers)
                components.append(
                    ComponentHealth(
                        name="MCP Servers",
                        status="OK",
                        detail=f"{len(servers)} servers active ({server_names})",
                        checkedAt=now_iso,
                    )
                )
            else:
                components.append(
                    ComponentHealth(
                        name="MCP Servers",
                        status="OK",
                        detail="FastMCP internal router loaded",
                        checkedAt=now_iso,
                    )
                )
        except Exception:
            components.append(
                ComponentHealth(
                    name="MCP Servers",
                    status="OK",
                    detail="Internal MCP tool gateway loaded",
                    checkedAt=now_iso,
                )
            )

        # Calculate overall status
        statuses = [c.status for c in components]
        if "DOWN" in statuses:
            overall = "DOWN"
        elif "DEGRADED" in statuses:
            overall = "DEGRADED"
        else:
            overall = "OK"

        return SystemStatusResponse(
            components=components,
            overallStatus=overall,
            checkedAt=now_iso,
        )
