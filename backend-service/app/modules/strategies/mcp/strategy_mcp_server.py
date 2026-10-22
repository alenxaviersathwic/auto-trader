import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.db.session import get_db
from app.core.exception.app_exceptions import BusinessException, NotFoundException
from app.core.logging.logger import logger
from app.core.response.response_helper import success
from app.modules.strategies.repository.registry_repository import RegistryRepository
from app.modules.strategies.repository.rule_repository import RuleRepository
from app.modules.strategies.repository.strategy_repository import StrategyRepository
from app.modules.strategies.schema.rule_schema import RuleFilter
from app.modules.strategies.schema.strategy_schema import StrategyFilter
from app.modules.strategies.service.conflict_analyzer import ConflictAnalyzer
from app.modules.strategies.service.definition_differ import DefinitionDiffer
from app.modules.strategies.service.definition_validator import DefinitionValidator
from app.modules.strategies.service.health_service import HealthService
from app.modules.strategies.service.similarity_service import SimilarityService
from app.modules.strategies.service.strategy_explainer import StrategyExplainer
from app.modules.strategies.service.strategy_service import StrategyService
from app.modules.strategies.service.structure_analyzer import StructureAnalyzer

# Tool Definitions Catalog with Tiers (strictly READ and ANALYZE only)
STRATEGY_MCP_TOOLS: List[Dict[str, Any]] = [
    {
        "name": "list_registry",
        "tier": "READ",
        "description": "List items in a registry (indicators, operators, strike selectors, structures, stop types, etc.). Always check before using any indicator or code name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "registryType": {"type": "string", "description": "e.g. INDICATOR, OPERATOR, STRIKE_SELECTOR, STRUCTURE, STOP_TYPE, TARGET_TYPE"},
                "query": {"type": "string", "description": "Optional search substring"},
                "executableOnly": {"type": "boolean", "default": False},
            },
            "required": ["registryType"],
        },
    },
    {
        "name": "get_registry_item",
        "tier": "READ",
        "description": "Get detailed metadata, parameter limits, and outputs for a specific registry code.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "registryType": {"type": "string"},
                "code": {"type": "string"},
            },
            "required": ["registryType", "code"],
        },
    },
    {
        "name": "search_strategies",
        "tier": "READ",
        "description": "Search existing strategies by market, bias, structure, lifecycle, or query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "market": {"type": "string"},
                "bias": {"type": "string"},
                "structure": {"type": "string"},
                "lifecycleStatus": {"type": "string"},
                "health": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_strategy",
        "tier": "READ",
        "description": "Get full details of a strategy by its code, including current version and definition.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "includeDefinition": {"type": "boolean", "default": True},
            },
            "required": ["code"],
        },
    },
    {
        "name": "get_strategy_history",
        "tier": "READ",
        "description": "Get strategy version history, health events, and performance snapshots with reliability flags.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "search_rules",
        "tier": "READ",
        "description": "Search existing guardrails and trading rules by kind, action, market, or query.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "ruleKind": {"type": "string"},
                "action": {"type": "string"},
                "market": {"type": "string"},
                "limit": {"type": "integer", "default": 10},
            },
        },
    },
    {
        "name": "get_rule",
        "tier": "READ",
        "description": "Get details of a rule by its code, including current definition and evidence.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "validate_definition",
        "tier": "ANALYZE",
        "description": "Validate a strategy or rule definition against the registry. Checks validity, operability, and handler executability.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["STRATEGY", "RULE"], "default": "STRATEGY"},
                "definition": {"type": "object", "description": "Canonical v2 definition dictionary"},
            },
            "required": ["definition"],
        },
    },
    {
        "name": "analyze_structure",
        "tier": "ANALYZE",
        "description": "Deterministic options legs analysis: determines structure type, bias, defined vs undefined risk, credit vs debit, and max loss formula.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "definition": {"type": "object"},
            },
            "required": ["definition"],
        },
    },
    {
        "name": "find_similar",
        "tier": "ANALYZE",
        "description": "Find existing strategies or rules similar to this definition. Detects duplicates (>= 90%) and overlaps (60-89%).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["STRATEGY", "RULE"], "default": "STRATEGY"},
                "definition": {"type": "object"},
                "text": {"type": "string"},
                "topK": {"type": "integer", "default": 5},
            },
            "required": ["definition"],
        },
    },
    {
        "name": "analyze_conflicts",
        "tier": "ANALYZE",
        "description": "Check definition against active guardrails (AVOID, BLOCK, REQUIRE), internal condition contradictions, and invalid time windows.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "kind": {"type": "string", "enum": ["STRATEGY", "RULE"], "default": "STRATEGY"},
                "definition": {"type": "object"},
                "meta": {"type": "object"},
            },
            "required": ["definition"],
        },
    },
    {
        "name": "evaluate_definition",
        "tier": "ANALYZE",
        "description": "Evaluate definition against a synthetic or real context to verify condition evaluation and executability.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "definition": {"type": "object"},
                "context": {"type": "object", "default": {}},
            },
            "required": ["definition"],
        },
    },
    {
        "name": "explain_definition",
        "tier": "ANALYZE",
        "description": "Generate deterministic English description (back-translation) of a strategy or rule definition.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "definition": {"type": "object"},
                "meta": {"type": "object"},
            },
            "required": ["definition"],
        },
    },
    {
        "name": "diff_definitions",
        "tier": "ANALYZE",
        "description": "Compute structured differences and human-readable sentences between two definitions (before and after).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "before": {"type": "object"},
                "after": {"type": "object"},
            },
            "required": ["before", "after"],
        },
    },
]


class StrategyMcpServer:
    """
    In-process and HTTP MCP server for Strategy & Rules module.
    Exposes only READ and ANALYZE tools. Never exposes any write/mutation operations.
    """

    def __init__(self):
        self.registry_repo = RegistryRepository()
        self.strategy_repo = StrategyRepository()
        self.rule_repo = RuleRepository()
        self.strategy_service = StrategyService()
        self.health_service = HealthService()
        self.validator = DefinitionValidator()
        self.similarity_service = SimilarityService()
        self.conflict_analyzer = ConflictAnalyzer()

    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        return STRATEGY_MCP_TOOLS

    async def execute_tool(
        self,
        session: AsyncSession,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Executes a tool call and returns the result dictionary."""
        logger.info(f"Strategy MCP tool execution requested: {tool_name}")

        if tool_name == "list_registry":
            reg_type = arguments.get("registryType", "").upper()
            items = await self.registry_repo.get_all_by_type(session, reg_type)
            query = arguments.get("query", "").lower()
            if query:
                items = [i for i in items if query in i.code.lower() or query in (i.name or "").lower()]
            if arguments.get("executableOnly"):
                items = [i for i in items if i.executable]

            return {
                "items": [
                    {
                        "code": i.code,
                        "name": i.name,
                        "type": i.type,
                        "executable": i.executable,
                        "category": i.category,
                        "schema": i.schema,
                    }
                    for i in items
                ]
            }

        elif tool_name == "get_registry_item":
            item = await self.registry_repo.get_by_type_and_code(
                session, arguments.get("registryType", "").upper(), arguments.get("code", "")
            )
            if not item:
                return {"error": f"Item {arguments.get('code')} not found in {arguments.get('registryType')}"}
            return {
                "code": item.code,
                "name": item.name,
                "type": item.type,
                "executable": item.executable,
                "schema": item.schema,
                "outputs": item.outputs,
                "docUrl": item.docUrl,
            }

        elif tool_name == "search_strategies":
            filter_obj = StrategyFilter(
                query=arguments.get("query"),
                market=arguments.get("market"),
                bias=arguments.get("bias"),
                structure=arguments.get("structure"),
                lifecycleStatus=arguments.get("lifecycleStatus"),
                health=arguments.get("health"),
                limit=min(arguments.get("limit", 10), 20),
            )
            res = await self.strategy_service.search(session, filter_obj)
            return {
                "strategies": [
                    {
                        "id": s.id,
                        "code": s.code,
                        "name": s.name,
                        "structure": s.structure,
                        "bias": s.bias,
                        "markets": s.markets,
                        "lifecycleStatus": s.lifecycleStatus,
                        "health": s.health,
                    }
                    for s in res.list
                ],
                "totalItems": res.totalItems,
            }

        elif tool_name == "get_strategy":
            code = arguments.get("code", "")
            strat = await self.strategy_repo.get_by_code(session, code)
            if not strat:
                return {"error": f"Strategy with code '{code}' not found"}
            res = await self.strategy_service.get_by_id(session, strat.id)
            data = res.model_dump()
            if not arguments.get("includeDefinition", True):
                if "currentVersion" in data and data["currentVersion"]:
                    data["currentVersion"]["definition"] = None
            return data

        elif tool_name == "get_strategy_history":
            code = arguments.get("code", "")
            strat = await self.strategy_repo.get_by_code(session, code)
            if not strat:
                return {"error": f"Strategy '{code}' not found"}
            health_data = await self.health_service.get_strategy_health(session, strat.id)
            versions, _ = await self.strategy_repo.search_versions(session, strat.id)
            return {
                "strategyCode": strat.code,
                "health": health_data.health,
                "healthEvents": [e.model_dump() for e in health_data.events],
                "versions": [
                    {"versionNo": v.versionNo, "createdAt": str(v.createdAt), "changeNote": v.changeNote}
                    for v in versions
                ],
            }

        elif tool_name == "search_rules":
            filter_obj = RuleFilter(
                query=arguments.get("query"),
                ruleKind=arguments.get("ruleKind"),
                action=arguments.get("action"),
                market=arguments.get("market"),
                limit=min(arguments.get("limit", 10), 20),
            )
            rules, total = await self.rule_repo.search(
                session,
                query=filter_obj.query,
                rule_kind=filter_obj.ruleKind,
                action=filter_obj.action,
                limit=filter_obj.limit,
            )
            return {
                "rules": [
                    {
                        "id": r.id,
                        "code": r.code,
                        "name": r.name,
                        "ruleKind": r.ruleKind,
                        "action": r.action,
                        "priority": r.priority,
                        "enabled": r.enabled,
                    }
                    for r in rules
                ],
                "totalItems": total,
            }

        elif tool_name == "get_rule":
            code = arguments.get("code", "")
            rule = await self.rule_repo.get_by_code(session, code)
            if not rule:
                return {"error": f"Rule '{code}' not found"}
            v_curr = await self.rule_repo.get_current_version(session, rule.id)
            return {
                "id": rule.id,
                "code": rule.code,
                "name": rule.name,
                "ruleKind": rule.ruleKind,
                "action": rule.action,
                "priority": rule.priority,
                "enabled": rule.enabled,
                "evidence": rule.evidence,
                "content": v_curr.content if v_curr else {},
            }

        elif tool_name == "validate_definition":
            definition = arguments.get("definition", {})
            val_res = await self.validator.validate(session, definition)
            return {
                "valid": val_res.valid,
                "executable": val_res.executable,
                "issues": [
                    {
                        "path": issue.path,
                        "level": issue.level,
                        "severity": "BLOCKER" if issue.level == "ERROR" else "WARNING",
                        "message": issue.message,
                    }
                    for issue in val_res.issues
                ],
            }

        elif tool_name == "analyze_structure":
            return StructureAnalyzer.analyze(arguments.get("definition", {}))

        elif tool_name == "find_similar":
            kind = arguments.get("kind", "STRATEGY").upper()
            defn = arguments.get("definition", {})
            top_k = arguments.get("topK", 5)
            if kind == "RULE":
                sims = await self.similarity_service.find_similar_rules(session, defn, top_k=top_k)
            else:
                sims = await self.similarity_service.find_similar_strategies(session, defn, top_k=top_k)
            return {"similar": sims}

        elif tool_name == "analyze_conflicts":
            kind = arguments.get("kind", "STRATEGY").upper()
            defn = arguments.get("definition", {})
            meta = arguments.get("meta", {})
            conflicts = await self.conflict_analyzer.analyze_conflicts(session, kind, defn, meta)
            return {"conflicts": conflicts}

        elif tool_name == "evaluate_definition":
            definition = arguments.get("definition", {})
            context = arguments.get("context", {})
            try:
                res = await self.strategy_service.evaluate_transient(session, definition, context)
                return res.model_dump()
            except Exception as e:
                return {
                    "entryMet": False,
                    "exitMet": False,
                    "error": str(e),
                    "conditions": [],
                }

        elif tool_name == "explain_definition":
            defn = arguments.get("definition", {})
            meta = arguments.get("meta", {})
            return {"explanation": StrategyExplainer.explain(defn, meta)}

        elif tool_name == "diff_definitions":
            before = arguments.get("before", {})
            after = arguments.get("after", {})
            return DefinitionDiffer.diff(before, after)

        else:
            raise NotFoundException(message=f"Tool '{tool_name}' not recognized by Strategy MCP server")


strategy_mcp_instance = StrategyMcpServer()
strategy_mcp_router = APIRouter(prefix="/mcp/strategy", tags=["Strategy MCP Server"])


@strategy_mcp_router.get("/tools")
async def list_strategy_tools():
    """Returns available tools and their input schemas."""
    return success(data=strategy_mcp_instance.get_tool_definitions(), message="Tools listed successfully")


@strategy_mcp_router.post("/call")
async def call_strategy_tool(
    payload: Dict[str, Any],
    session: AsyncSession = Depends(get_db),
    authorization: Optional[str] = Header(None),
):
    """
    Executes a read or analyze tool.
    Strictly verifies tool name against allowed tools.
    """
    tool_name = payload.get("tool") or payload.get("name")
    arguments = payload.get("arguments") or payload.get("parameters") or {}

    if not tool_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Tool name is required")

    # Enforce token check if configured in environment
    mcp_secret = os.getenv("STRATEGY_MCP_TOKEN")
    if mcp_secret:
        if not authorization or authorization.replace("Bearer ", "") != mcp_secret:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid Strategy MCP auth token")

    res = await strategy_mcp_instance.execute_tool(session, tool_name, arguments)
    return success(data=res, message=f"Tool '{tool_name}' executed")
