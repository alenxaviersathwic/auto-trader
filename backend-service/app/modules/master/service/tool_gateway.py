import time
from typing import Any, Dict, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging.logger import logger
from app.modules.master.entity.master_tool_call_entity import MasterToolCall
from app.modules.master.mcp.mcp_client import McpClient
from app.modules.master.repository.master_config_repository import MasterConfigRepository
from app.modules.master.repository.tool_call_repository import ToolCallRepository
from app.modules.master.repository.tool_server_repository import ToolServerRepository
from app.modules.master.service.redaction_service import RedactionService

TIER_ORDER = {
    "READ": 1,
    "ANALYZE": 2,
    "PROPOSE": 3,
    "OPERATE": 4,
}

MASTER_LOCAL_TOOLS = {
    "ask_user": {"tier": "READ", "server": "master-local"},
    "get_preferences": {"tier": "READ", "server": "master-local"},
    "save_preference": {"tier": "PROPOSE", "server": "master-local"},
    "submit_proposal": {"tier": "PROPOSE", "server": "master-local"},
}


class ToolGateway:
    """
    Central enforcement gate and audit logger for all tool invocations.
    Guarantees tier caps, disabled tools, and permission policies in code.
    The LLM or prompt cannot bypass these checks.
    """

    def __init__(
        self,
        config_repo: Optional[MasterConfigRepository] = None,
        tool_server_repo: Optional[ToolServerRepository] = None,
        tool_call_repo: Optional[ToolCallRepository] = None,
        mcp_client: Optional[McpClient] = None,
    ):
        self.config_repo = config_repo or MasterConfigRepository()
        self.tool_server_repo = tool_server_repo or ToolServerRepository()
        self.tool_call_repo = tool_call_repo or ToolCallRepository()
        self.mcp_client = mcp_client or McpClient()

    async def invoke_tool(
        self,
        session: AsyncSession,
        run_id: int,
        tool_name: str,
        arguments: Dict[str, Any],
        local_handlers: Optional[Dict[str, Any]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Invokes a tool with permission checking and audit logging.
        Returns (result_dict, status_str).
        status_str is one of: "OK", "ERROR", "DENIED", "TIMEOUT".
        """
        start_time = time.time()
        redacted_args, _ = RedactionService.redact_dict(arguments)

        # 1. Check if tool is master-local
        if tool_name in MASTER_LOCAL_TOOLS:
            server_name = "master-local"
            tool_tier = MASTER_LOCAL_TOOLS[tool_name]["tier"]
            is_local = True
            server_cap = "PROPOSE"
            is_enabled = True
        else:
            server_name = "strategy-rules"
            is_local = False
            # Check server
            server = await self.tool_server_repo.get_by_name(session, server_name)
            if not server or not server.enabled:
                return await self._record_and_return_denied(
                    session, run_id, server_name, tool_name, "READ", redacted_args, "Server is disabled or not found", start_time
                )
            server_cap = server.tierCap

            # Check tool policy
            policy = await self.tool_server_repo.get_policy(session, server_name, tool_name)
            if not policy:
                return await self._record_and_return_denied(
                    session, run_id, server_name, tool_name, "READ", redacted_args, f"Tool '{tool_name}' is not in policy registry", start_time
                )
            if not policy.enabled:
                return await self._record_and_return_denied(
                    session, run_id, server_name, tool_name, policy.tier, redacted_args, f"Tool '{tool_name}' is disabled by administrator", start_time
                )
            tool_tier = policy.tier

        # 2. Check Tier Caps
        master_cap = await self.config_repo.get_key(session, "toolTierCap") or "PROPOSE"
        tier_val = TIER_ORDER.get(tool_tier, 99)
        server_cap_val = TIER_ORDER.get(server_cap, 99)
        master_cap_val = TIER_ORDER.get(master_cap, 99)

        if tier_val > server_cap_val:
            return await self._record_and_return_denied(
                session, run_id, server_name, tool_name, tool_tier, redacted_args, f"Tool tier {tool_tier} exceeds server cap {server_cap}", start_time
            )

        if tier_val > master_cap_val:
            return await self._record_and_return_denied(
                session, run_id, server_name, tool_name, tool_tier, redacted_args, f"Tool tier {tool_tier} exceeds Master cap {master_cap}", start_time
            )

        # 3. Execution
        try:
            if is_local:
                if local_handlers and tool_name in local_handlers:
                    result = await local_handlers[tool_name](session, arguments)
                else:
                    result = {"status": "LOCAL_EXECUTED"}
            else:
                result = await self.mcp_client.call_tool(
                    session=session,
                    server_name=server_name,
                    server_transport="IN_PROCESS",
                    server_url="/mcp/strategy",
                    auth_ref="STRATEGY_MCP_TOKEN",
                    tool_name=tool_name,
                    arguments=arguments,
                    timeout_seconds=15.0,
                )

            duration_ms = int((time.time() - start_time) * 1000)
            summary = self._summarize_result(result)

            call = MasterToolCall(
                runId=run_id,
                serverName=server_name,
                toolName=tool_name,
                tier=tool_tier,
                arguments=redacted_args,
                resultSummary=summary,
                callStatus="OK",
                durationMs=duration_ms,
            )
            await self.tool_call_repo.save(session, call)
            return result, "OK"

        except TimeoutError:
            duration_ms = int((time.time() - start_time) * 1000)
            call = MasterToolCall(
                runId=run_id,
                serverName=server_name,
                toolName=tool_name,
                tier=tool_tier,
                arguments=redacted_args,
                resultSummary={"error": "Tool execution timed out after 15s"},
                callStatus="TIMEOUT",
                durationMs=duration_ms,
            )
            await self.tool_call_repo.save(session, call)
            return {"error": "Tool call timed out"}, "TIMEOUT"

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            duration_ms = int((time.time() - start_time) * 1000)
            call = MasterToolCall(
                runId=run_id,
                serverName=server_name,
                toolName=tool_name,
                tier=tool_tier,
                arguments=redacted_args,
                resultSummary={"error": str(e)},
                callStatus="ERROR",
                durationMs=duration_ms,
            )
            await self.tool_call_repo.save(session, call)
            return {"error": str(e)}, "ERROR"

    async def _record_and_return_denied(
        self,
        session: AsyncSession,
        run_id: int,
        server_name: str,
        tool_name: str,
        tier: str,
        redacted_args: Dict[str, Any],
        reason: str,
        start_time: float,
    ) -> Tuple[Dict[str, Any], str]:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"Tool invocation DENIED for {tool_name}: {reason}")
        call = MasterToolCall(
            runId=run_id,
            serverName=server_name,
            toolName=tool_name,
            tier=tier,
            arguments=redacted_args,
            resultSummary={"deniedReason": reason},
            callStatus="DENIED",
            durationMs=duration_ms,
        )
        await self.tool_call_repo.save(session, call)
        return {"status": "DENIED", "error": f"Tool call denied: {reason}"}, "DENIED"

    def _summarize_result(self, result: Any) -> Dict[str, Any]:
        if not isinstance(result, dict):
            return {"summary": str(result)[:200]}
        summary = {}
        for k, v in list(result.items())[:6]:
            if isinstance(v, list):
                summary[k] = f"List of {len(v)} items"
            elif isinstance(v, dict):
                summary[k] = f"Dict with keys {list(v.keys())[:4]}"
            else:
                summary[k] = str(v)[:100]
        return summary
