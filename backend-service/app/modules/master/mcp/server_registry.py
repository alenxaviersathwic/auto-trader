from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.master.entity.master_tool_policy_entity import MasterToolPolicy
from app.modules.master.entity.master_tool_server_entity import MasterToolServer
from app.modules.master.repository.tool_server_repository import ToolServerRepository
from app.modules.strategies.mcp.strategy_mcp_server import STRATEGY_MCP_TOOLS


class ServerRegistry:
    """Manages MCP tool servers and policies."""

    def __init__(self, repo: Optional[ToolServerRepository] = None):
        self.repo = repo or ToolServerRepository()

    async def ensure_defaults(self, session: AsyncSession) -> None:
        """Seeds default 'strategy-rules' server and its policies if missing."""
        strat_server = await self.repo.get_by_name(session, "strategy-rules")
        if not strat_server:
            strat_server = MasterToolServer(
                name="strategy-rules",
                transport="HTTP",
                url="/mcp/strategy",
                authRef="STRATEGY_MCP_TOKEN",
                tierCap="ANALYZE",  # server allows up to ANALYZE
                enabled=True,
                toolCount=len(STRATEGY_MCP_TOOLS),
            )
            await self.repo.save(session, strat_server)

        # Seed policies for all tools in strategy-rules
        for tool in STRATEGY_MCP_TOOLS:
            pol = await self.repo.get_policy(session, "strategy-rules", tool["name"])
            if not pol:
                pol = MasterToolPolicy(
                    serverName="strategy-rules",
                    toolName=tool["name"],
                    tier=tool["tier"],
                    enabled=True,
                    autoApprove=True if tool["tier"] in ["READ", "ANALYZE"] else False,
                )
                await self.repo.save_policy(session, pol)
