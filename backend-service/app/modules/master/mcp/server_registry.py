from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.master.entity.master_tool_policy_entity import MasterToolPolicy
from app.modules.master.entity.master_tool_server_entity import MasterToolServer
from app.modules.master.repository.tool_server_repository import ToolServerRepository
from app.modules.research.mcp.research_mcp_server import RESEARCH_MCP_TOOLS
from app.modules.strategies.mcp.strategy_mcp_server import STRATEGY_MCP_TOOLS


class ServerRegistry:
    """Manages MCP tool servers and policies."""

    def __init__(self, repo: Optional[ToolServerRepository] = None):
        self.repo = repo or ToolServerRepository()

    async def ensure_defaults(self, session: AsyncSession) -> None:
        """Seeds default 'strategy-rules' and 'research-engine' servers and their policies if missing."""
        # 1. Strategy & Rules Server
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
        else:
            strat_server.toolCount = len(STRATEGY_MCP_TOOLS)
            await self.repo.save(session, strat_server)

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

        # 2. Research Engine Server
        res_server = await self.repo.get_by_name(session, "research-engine")
        if not res_server:
            res_server = MasterToolServer(
                name="research-engine",
                transport="HTTP",
                url="/mcp/research",
                authRef="MCP_RESEARCH_TOKEN",
                tierCap="OPERATE",  # research server allows up to OPERATE (with confirmation tokens)
                enabled=True,
                toolCount=len(RESEARCH_MCP_TOOLS),
            )
            await self.repo.save(session, res_server)
        else:
            res_server.toolCount = len(RESEARCH_MCP_TOOLS)
            await self.repo.save(session, res_server)

        for tool in RESEARCH_MCP_TOOLS:
            pol = await self.repo.get_policy(session, "research-engine", tool["name"])
            if not pol:
                pol = MasterToolPolicy(
                    serverName="research-engine",
                    toolName=tool["name"],
                    tier=tool["tier"],
                    enabled=True,
                    autoApprove=True if tool["tier"] in ["READ", "ANALYZE"] else False,
                )
                await self.repo.save_policy(session, pol)
