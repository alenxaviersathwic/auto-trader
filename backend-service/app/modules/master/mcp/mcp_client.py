import os
import time
from typing import Any, Dict, Optional
import httpx
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging.logger import logger
from app.modules.research.mcp.research_mcp_server import research_mcp_instance
from app.modules.strategies.mcp.strategy_mcp_server import strategy_mcp_instance


class McpClient:
    """
    Client for interacting with MCP tool servers.
    Supports in-process direct dispatch (zero network latency) and HTTP transport.
    """

    async def call_tool(
        self,
        session: AsyncSession,
        server_name: str,
        server_transport: str,
        server_url: Optional[str],
        auth_ref: Optional[str],
        tool_name: str,
        arguments: Dict[str, Any],
        timeout_seconds: float = 15.0,
    ) -> Dict[str, Any]:
        start_time = time.time()

        # In-process dispatch for fast internal MCP servers
        if server_name == "strategy-rules":
            try:
                return await strategy_mcp_instance.execute_tool(session, tool_name, arguments)
            except Exception as e:
                logger.error(f"In-process strategy MCP tool call {tool_name} failed: {e}", exc_info=True)
                raise e

        if server_name == "research-engine":
            try:
                return await research_mcp_instance.execute_tool(session, tool_name, arguments)
            except Exception as e:
                logger.error(f"In-process research MCP tool call {tool_name} failed: {e}", exc_info=True)
                raise e

        if server_transport == "IN_PROCESS" or not server_url:
            # Fallback in-process check
            try:
                return await research_mcp_instance.execute_tool(session, tool_name, arguments)
            except Exception:
                return await strategy_mcp_instance.execute_tool(session, tool_name, arguments)

        # HTTP dispatch
        auth_token = os.getenv(auth_ref) if auth_ref else None
        headers = {}
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            resp = await client.post(
                f"{server_url}/call",
                json={"tool": tool_name, "arguments": arguments},
                headers=headers,
            )
            if resp.status_code != 200:
                raise RuntimeError(f"HTTP MCP error {resp.status_code}: {resp.text}")
            data = resp.json()
            return data.get("data", data)
