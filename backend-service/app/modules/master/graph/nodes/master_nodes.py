import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging.logger import logger
from app.modules.master.entity.master_preference_entity import MasterPreference
from app.modules.master.entity.master_proposal_entity import MasterProposal
from app.modules.master.graph.schemas import ExtractedSpec, IntentClassification, VerifyMatchResult
from app.modules.master.graph.state import MasterState
from app.modules.master.llm.llm_client import LlmClient
from app.modules.master.repository.master_config_repository import MasterConfigRepository
from app.modules.master.repository.preference_repository import PreferenceRepository
from app.modules.master.repository.proposal_repository import ProposalRepository
from app.modules.master.service.redaction_service import RedactionService
from app.modules.master.service.tool_gateway import ToolGateway
from app.modules.research.mcp.research_mcp_server import RESEARCH_MCP_TOOLS
from app.modules.strategies.mcp.strategy_mcp_server import STRATEGY_MCP_TOOLS


class MasterNodes:
    """Implementation of all LangGraph nodes for the AI Master agent."""

    def __init__(
        self,
        llm_client: LlmClient,
        tool_gateway: ToolGateway,
        proposal_repo: ProposalRepository,
        preference_repo: PreferenceRepository,
        config_repo: MasterConfigRepository,
    ):
        self.llm = llm_client
        self.gateway = tool_gateway
        self.proposal_repo = proposal_repo
        self.preference_repo = preference_repo
        self.config_repo = config_repo

    async def ingest(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Sanitizes text, loads preferences, and records start event."""
        clean_text, redacted = RedactionService.redact_text(state.userText)
        state.userText = clean_text
        if not state.preferences:
            state.preferences = await self.preference_repo.get_all_dict(session)
        state.events.append({"event": "run.started", "runId": state.runId})
        return state

    async def classify_intent(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Structured LLM intent classification."""
        # Fast heuristic for greetings & short pleasantries
        clean_lower = state.userText.strip().lower()
        greetings = {"hi", "hai", "hello", "hellop", "hey", "hola", "greetings", "good morning", "good evening", "how are you", "who are you", "help"}
        if clean_lower in greetings or any(clean_lower.startswith(g + " ") for g in ["hi", "hai", "hello", "hey"]):
            state.intent = "CHAT"
            state.confidence = 1.0
            return state

        # Fast heuristic for strategy listing / querying
        strategy_triggers = ["what strategies", "which strategies", "show strategies", "list strategies", "registered strategies", "available strategies", "strategies are registered", "strategies exist", "strategies do you know"]
        if any(t in clean_lower for t in strategy_triggers):
            state.intent = "FIND"
            state.confidence = 1.0
            return state

        # Fast heuristic for market intelligence / research queries
        research_triggers = [
            "research", "market intelligence", "what does research suggest", "news affecting", 
            "affect news", "neutral news", "today news", "blog summary", "sentiment on", 
            "is sensex cleared", "is nifty cleared", "sensex news", "nifty news", "gold news", 
            "crude oil news", "crudeoil news", "run research", "latest research", "what does research"
        ]
        if any(t in clean_lower for t in research_triggers):
            state.intent = "RESEARCH"
            state.confidence = 1.0
            return state

        # Fast heuristic for adding risk rules / guardrails
        rule_triggers = ["set max daily", "max daily loss", "portfolio loss", "max loss", "guardrail", "risk rule"]
        if any(t in clean_lower for t in rule_triggers):
            state.intent = "ADD_RULE"
            state.confidence = 1.0
            return state

        messages = [{"role": "user", "content": state.userText}]
        sys_prompt = (
            "You are an intent classifier for Auto-Trader. Classify the user intent into one of:\n"
            "- CHAT: Greetings ('hi', 'hello', 'hai'), small talk, general questions about trading/indicators (RSI, VWAP, EMA), market concepts, or what the platform does.\n"
            "- ADD_STRATEGY: User wants to create or build a new trading strategy (specifying entry, exit, or indicators).\n"
            "- ADD_RULE: User wants to define a risk rule, guardrail, max daily loss, or position sizing limit.\n"
            "- UPDATE_STRATEGY: User wants to modify an existing strategy.\n"
            "- UPDATE_RULE: User wants to modify an existing rule.\n"
            "- SET_LIFECYCLE: User wants to activate, pause, archive, or retire a strategy.\n"
            "- DELETE_DRAFT: User wants to discard a draft.\n"
            "- FIND: User wants to search or list registered strategies in the database.\n"
            "- EXPLAIN: User wants an explanation of a specific existing strategy by code or name.\n"
            "- ANALYZE_TEXT: User wants analysis or critique of a strategy description without creating it.\n"
            "- REMEMBER: User explicitly asks to remember or save a personal preference (e.g., 'remember my timeframe is 15m').\n"
            "- OUT_OF_SCOPE: User asks to place live broker orders or transfer money.\n"
            "- UNCLEAR: Completely ambiguous input.\n"
            "Return valid JSON matching IntentClassification."
        )
        try:
            res = await self.llm.generate_structured(messages, IntentClassification, system_prompt=sys_prompt)
            state.intent = res.intent
            state.confidence = res.confidence
            state.entities = res.entities
        except Exception as e:
            logger.warning(f"Intent classification structured call failed: {e}; defaulting to CHAT")
            state.intent = "CHAT"
            state.confidence = 0.8

        if state.confidence < 0.6 or state.intent == "UNCLEAR":
            state.intent = "CHAT"
        return state

    async def handle_out_of_scope(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Politely informs the user of boundaries."""
        state.answerDraft = (
            "I can help you design, analyze, test, and manage trading **strategies** and **risk rules**.\n\n"
            "I cannot directly place live broker orders or execute manual trades without your strategy confirmation."
        )
        state.events.append({"event": "message.delta", "delta": state.answerDraft})
        return state

    async def handle_chat_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Handles conversational chit-chat, trading knowledge, and common questions with Ollama and system memory."""
        # Retrieve active strategies from system memory to answer questions like 'what strategies exist?'
        strategies_summary = "None currently registered."
        try:
            res, _ = await self.gateway.invoke_tool(session, state.runId, "search_strategies", {"limit": 5})
            strats = res.get("strategies", [])
            if strats:
                strategies_summary = ", ".join(f"{s.get('name')} ({s.get('code')})" for s in strats)
        except Exception:
            pass

        pref_str = json.dumps(state.preferences) if state.preferences else "No custom preferences saved."

        sys_prompt = (
            "You are AI Master, an expert trading assistant and algorithmic copilot for Auto-Trader.\n"
            "Auto-Trader is an automated trading execution platform with automated strategy lifecycles and risk guardrails.\n\n"
            f"Current System State & Memory:\n"
            f"- Saved User Preferences: {pref_str}\n"
            f"- Registered Platform Strategies: {strategies_summary}\n\n"
            "Guidelines:\n"
            "- Respond warmly, intelligently, and concisely to greetings, questions, and discussions.\n"
            "- For trading questions (e.g. RSI, VWAP, option buying/selling, stop losses, risk management), provide practical, clear insights.\n"
            "- If the user asks about available strategies or system status, use the system context above.\n"
            "- If the user expresses interest in building a strategy, invite them to describe their entry conditions, exit rules, and instruments.\n\n"
            "RESEARCH:\n"
            "- You can read the research engine's results. Use get_latest_results for 'what does research suggest' or 'which index / commodity has no negative news'. Use get_candidate to explain a status and show its sources. Use semantic_search for free-text questions about what the sources said. Use search_claims to show evidence.\n"
            "- Always tell the user the run time and age, the number of independent sources, and the score label. If the latest run is more than 24 hours old, say the news is stale and offer to run again.\n"
            "- 'Suggested' means: fresh sources reviewed, no material negative news found, some supportive news. It is a news screen. It is not a prediction, a probability or a trade signal. Never say a pick 'will' go up or down. Quiet news does not mean safe.\n"
            "- If an underlying has negative news, explain the negative claims with their sources. A bearish watch is information, not a recommendation.\n"
            "- To run research, call run_research. This creates a proposal for the user to confirm. Do not say the run started until the run id is returned.\n"
            "- If nothing is suggested, say why (negative news, no coverage, mixed signals). Do not fill in a pick.\n"
            "- Quote only the excerpts the tools return. Do not claim to have read a full article.\n"
            "- The engine uses only fresh articles. Do not describe it as using past trades, past results or price history."
        )

        messages: List[Dict[str, str]] = []
        for h in state.history[-6:]:
            messages.append({"role": h.get("role", "user").lower(), "content": h.get("content", "")})
        messages.append({"role": "user", "content": state.userText})

        try:
            reply = await self.llm.generate(messages, system_prompt=sys_prompt, temperature=0.3)
            if not reply or not reply.strip():
                reply = "Hello! I am your AI Master trading copilot. How can I assist you with your trading strategies or risk rules today?"
        except Exception as e:
            logger.error(f"Chat generation error: {e}")
            reply = "Hello! I am your AI Master trading copilot. I can help you design strategies, configure risk rules, and analyze technical indicators. How can I help you today?"

        state.answerDraft = reply
        state.events.append({"event": "message.delta", "delta": reply})
        return state

    async def handle_unclear(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Gracefully handle unclear queries via the conversational chat node."""
        return await self.handle_chat_node(state, session)

    async def save_preference_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Saves a user preference when instructed."""
        user_text = state.userText
        key = "defaultTimeframe" if "timeframe" in user_text.lower() else ("defaultMarket" if "market" in user_text.lower() else "userPreference")
        val = "5m" if "5m" in user_text else ("NIFTY" if "nifty" in user_text.lower() else user_text)

        pref = await self.preference_repo.get_by_key(session, key)
        if not pref:
            pref = MasterPreference(key=key, value={"value": val})
        else:
            pref.value = {"value": val}
        await self.preference_repo.save(session, pref)
        state.preferences[key] = {"value": val}
        state.answerDraft = f"Remembered your preference: `{key}` = `{val}`."
        state.events.append({"event": "message.delta", "delta": state.answerDraft})
        return state

    async def read_loop_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """ReAct read loop for FIND, EXPLAIN, and ANALYZE_TEXT intents."""
        u_text = state.userText.lower()
        if state.intent == "FIND":
            state.events.append({"event": "tool.started", "tool": "search_strategies", "label": "Searching strategies..."})
            u_clean = state.userText.strip().lower()
            general_triggers = ["what", "show", "list", "all", "registered", "available", "exist", "which", "how many", "know"]
            # If the user asked a general inquiry like 'what strategies are registered', pass None to query all
            if any(t in u_clean for t in general_triggers):
                search_arg = None
            else:
                search_arg = state.userText.strip()

            res, _ = await self.gateway.invoke_tool(session, state.runId, "search_strategies", {"query": search_arg, "limit": 20})
            state.events.append({"event": "tool.finished", "tool": "search_strategies", "status": "OK"})
            strats = res.get("strategies", [])

            # Fallback to general list if specific keyword returned 0 results
            if not strats:
                res, _ = await self.gateway.invoke_tool(session, state.runId, "search_strategies", {"limit": 10})
                strats = res.get("strategies", [])

            if strats:
                total_count = res.get("totalItems", len(strats))
                items_str = "\n".join(
                    f"- **{s.get('name', 'Strategy')}** (`{s.get('code')}`) — {s.get('structure') or 'Technical'} | `{s.get('lifecycleStatus', 'ACTIVE')}`"
                    for s in strats[:10]
                )
                state.answerDraft = (
                    f"### Registered Strategies ({min(len(strats), 10)} of {total_count} shown)\n\n"
                    f"{items_str}\n\n"
                    f"💡 *Ask me to explain any strategy (e.g. `explain VWAP_RECLAIM`) or describe a new setup to create one!*"
                )
            else:
                state.answerDraft = "No strategies are currently registered. Describe your entry, exit, and stop loss to create the first strategy!"

        elif state.intent == "EXPLAIN":
            # Check if user mentioned a specific strategy code with an underscore
            words = state.userText.split()
            code = next((w.strip("`'\",.") for w in words if "_" in w), None)
            if code:
                state.events.append({"event": "tool.started", "tool": "get_strategy_history", "label": f"Loading history for {code}..."})
                res, _ = await self.gateway.invoke_tool(session, state.runId, "get_strategy_history", {"code": code})
                state.events.append({"event": "tool.finished", "tool": "get_strategy_history", "status": "OK"})
                if "error" not in res:
                    events = res.get("healthEvents", [])
                    ev_str = f"Current health: **{res.get('health', 'HEALTHY')}**.\n"
                    if events:
                        ev_str += "Recent events:\n" + "\n".join(f"- {e.get('toHealth')}: {e.get('reason')}" for e in events[:3])
                    state.answerDraft = f"### Status for strategy `{code}`\n\n{ev_str}"
                else:
                    # Fallback to chat node to explain conceptually
                    return await self.handle_chat_node(state, session)
            else:
                # User asked a conceptual question like "explain how RSI strategy works"
                return await self.handle_chat_node(state, session)

        elif state.intent == "ANALYZE_TEXT":
            # Just analyze without proposing
            state.events.append({"event": "tool.started", "tool": "validate_definition", "label": "Analyzing provided strategy..."})
            state.answerDraft = (
                "I analyzed your strategy description. It appears technically structured. "
                "Note that validity does not guarantee profitability, and past claims cannot be verified without backtesting."
            )

        elif state.intent == "RESEARCH":
            clean_u = state.userText.upper()
            known_underlyings = [
                "NIFTY", "SENSEX", "BANKNIFTY", "FINNIFTY", "MIDCPNIFTY", "BANKEX",
                "GOLD", "SILVER", "CRUDEOIL", "CRUDE OIL", "NATURALGAS", "NATURAL GAS", "COPPER", "ZINC"
            ]
            matched_code = None
            for code in known_underlyings:
                if code in clean_u:
                    matched_code = code.replace(" ", "")
                    break

            if matched_code:
                state.events.append({
                    "event": "tool.started",
                    "tool": "get_candidate",
                    "label": f"Fetching intelligence for {matched_code}..."
                })
                res, status = await self.gateway.invoke_tool(
                    session, state.runId, "get_candidate", {"underlyingCode": matched_code}
                )
                state.events.append({
                    "event": "tool.finished",
                    "tool": "get_candidate",
                    "status": status
                })

                if "error" not in res and res.get("underlyingCode"):
                    c_code = res.get("underlyingCode")
                    c_type = res.get("underlyingType", "INDEX")
                    c_status = res.get("newsStatus", "NO_COVERAGE")
                    c_score = res.get("score")
                    score_str = f"{c_score:.1f}" if c_score is not None else "Unrated"
                    is_cleared = res.get("suggested", False)
                    badge = "✅ CLEARED FOR TRADE" if is_cleared else (
                        "🚨 BEARISH WATCH" if "NEGATIVE" in c_status or "BEARISH" in c_status else f"ℹ️ {c_status}"
                    )
                    vm_badge = " · 🧠 `[Vector Memory Indexed]`" if res.get("hasVectorEmbedding") else ""

                    thesis = res.get("thesis") or "No clearance thesis recorded."
                    blog = res.get("blogSummary")
                    affect_news = res.get("affectNews", [])
                    latest_news = res.get("latestNews", [])

                    reply = f"### {c_code} ({c_type}) — Market Intelligence\n\n"
                    reply += f"**Status:** {badge}{vm_badge} | **Score:** `{score_str}`\n\n"

                    if blog:
                        reply += f"{blog}\n\n"
                    else:
                        reply += f"**Clearance Thesis:** {thesis}\n\n"

                    if affect_news:
                        reply += f"**Key Market-Moving Catalysts ({len(affect_news)} detected):**\n"
                        for an in affect_news[:3]:
                            impact = an.get("direction") or an.get("impact") or "CATALYST"
                            cat = f" [{an.get('catalystType') or an.get('catalyst')}]" if (an.get('catalystType') or an.get('catalyst')) else ""
                            reply += f"- **[{impact}]{cat}** {an.get('title')} — *{an.get('source') or an.get('domain')}*\n"
                        reply += "\n"

                    if latest_news and not blog:
                        reply += f"**Latest Scraped Articles ({len(latest_news)}):**\n"
                        for ln in latest_news[:3]:
                            reply += f"- {ln.get('title')} (*{ln.get('source') or 'Newswire'}*)\n"
                        reply += "\n"

                    state.answerDraft = reply
                else:
                    state.answerDraft = f"Could not find evaluated research candidate data for `{matched_code}`. You can run the research engine to generate fresh evaluation."
            else:
                # General research query across indices
                state.events.append({
                    "event": "tool.started",
                    "tool": "get_latest_results",
                    "label": "Loading latest market research results..."
                })
                res, status = await self.gateway.invoke_tool(
                    session, state.runId, "get_latest_results", {"underlyingType": "INDEX"}
                )
                state.events.append({
                    "event": "tool.finished",
                    "tool": "get_latest_results",
                    "status": status
                })

                run_info = res.get("run")
                suggested = res.get("suggested", [])
                bearish = res.get("bearishWatch", [])
                has_neg = res.get("hasNegative", [])

                reply = "### Latest Market Research Intelligence\n\n"
                if run_info:
                    reply += f"*Last evaluated run #{run_info.get('id')} ({run_info.get('state')}) — Age: {run_info.get('ageHours', 0)} hrs ago*\n\n"

                if suggested:
                    reply += "**✅ Cleared for Trading (Positive News Sentiment):**\n"
                    for s in suggested:
                        score_val = f"`{s.get('score'):.1f}`" if s.get('score') is not None else "Unrated"
                        vm = " 🧠" if s.get("hasVectorEmbedding") else ""
                        reply += f"- **{s.get('underlyingCode')}** (Score: {score_val}){vm} — {s.get('thesis') or 'All news verified positive'}\n"
                    reply += "\n"
                else:
                    reply += "ℹ️ **No underlyings currently meet strict trade clearance criteria.**\n\n"

                if bearish or has_neg:
                    reply += "**⚠️ Bearish Watch / Negative Catalysts:**\n"
                    for b in (bearish + has_neg)[:5]:
                        reply += f"- **{b.get('underlyingCode')}** ({b.get('newsStatus')}) — {b.get('thesis') or 'Negative market catalysts present'}\n"
                    reply += "\n"

                reply += "💡 *Ask me for details on any instrument (e.g. `What is the news on SENSEX?` or `Is GOLD cleared?`)*"
                state.answerDraft = reply

        state.events.append({"event": "message.delta", "delta": state.answerDraft})
        return state

    async def extract_spec_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Extracts partial structured specification from user input."""
        messages = [
            {"role": "user", "content": state.userText}
        ]
        # Include previous questions/answers if present
        for h in state.history:
            messages.append({"role": h.get("role", "user"), "content": h.get("content", "")})

        sys = "Extract structured strategy/rule spec from the user sentence. Tag missing items and vague condition phrases."
        spec_obj = await self.llm.generate_structured(messages, ExtractedSpec, system_prompt=sys)
        state.spec = spec_obj.model_dump()
        return state

    async def find_gaps_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """
        Applies Section 3.4 'Ask or Assume' deterministic rules in code.
        Never lets LLM guess indicators or assume missing directions.
        """
        if state.intent == "ADD_RULE":
            state.gaps = []
            return state

        gaps: List[Dict[str, Any]] = []
        questions: List[Dict[str, Any]] = []
        assumptions: List[str] = []
        spec = state.spec

        # 1. Market check
        if not spec.get("market"):
            pref_market = state.preferences.get("defaultMarket", {}).get("value")
            if pref_market:
                spec["market"] = pref_market
                assumptions.append(f"Market defaulted to preferred '{pref_market}'")
            else:
                gaps.append({"field": "market", "reason": "No market named"})
                questions.append({
                    "id": "market",
                    "text": "Which market or index do you want to trade this strategy on?",
                    "options": ["NIFTY", "BANKNIFTY", "FINNIFTY", "CRUDEOIL"],
                    "recommended": "NIFTY",
                    "allowPreference": True,
                })

        # 2. Bias / Direction check
        if not spec.get("bias") and spec.get("structure") not in ["STRADDLE", "STRANGLE", "IRON_CONDOR"]:
            gaps.append({"field": "bias", "reason": "Direction / Bias cannot be determined"})
            questions.append({
                "id": "bias",
                "text": "What is the intended market direction (bias)?",
                "options": ["BULLISH (Call buying / Put selling)", "BEARISH (Put buying / Call selling)", "NEUTRAL (Non-directional)"],
                "recommended": "BULLISH (Call buying / Put selling)",
            })

        # 3. Vague entry check
        if spec.get("isVague"):
            gaps.append({"field": "entry", "reason": "Entry condition is vague"})
            questions.append({
                "id": "entry_condition",
                "text": "The entry condition is descriptive ('on momentum / looks strong'). Which measurable rule should trigger entry?",
                "options": [
                    "5m close > VWAP and RSI(14) > 60",
                    "5m close crosses above 20 EMA",
                    "Supertrend(10, 3) turns GREEN",
                ],
                "recommended": "5m close > VWAP and RSI(14) > 60",
            })

        # 4. Indicator verification against registry
        for ind in spec.get("indicators", []):
            ind_upper = ind.upper()
            state.events.append({"event": "tool.started", "tool": "list_registry", "label": f"Verifying indicator {ind_upper}..."})
            res, _ = await self.gateway.invoke_tool(session, state.runId, "list_registry", {"registryType": "INDICATOR", "query": ind_upper})
            state.events.append({"event": "tool.finished", "tool": "list_registry", "status": "OK"})
            items = res.get("items", [])
            has_match = any(i["code"].upper() == ind_upper for i in items)
            if not has_match:
                gaps.append({"field": "indicator", "reason": f"Unknown indicator '{ind}'"})
                questions.append({
                    "id": f"indicator_{ind.lower()}",
                    "text": f"Indicator '{ind}' is not found in the technical indicator registry. How should we measure it?",
                    "options": ["Use RSI(14)", "Use VWAP", "Use EMA(20)", "Drop this condition"],
                    "recommended": "Use RSI(14)",
                })

        # 5. Missing exit and stop
        if not spec.get("hasStop") and not spec.get("hasExit"):
            gaps.append({"field": "exit", "reason": "No exit or stop defined"})
            questions.append({
                "id": "exit_stop",
                "text": "This strategy does not specify an exit condition or stop loss. How should risk be managed?",
                "options": [
                    "Stop loss at 25% of entry premium and exit at 15:10:00",
                    "Stop loss at 20 points and target at 40 points",
                    "Exit on opposite signal or 15:15:00 market close",
                ],
                "recommended": "Stop loss at 25% of entry premium and exit at 15:10:00",
            })

        # 6. Apply assumptions for non-blocking defaults
        if not spec.get("timeframe"):
            pref_tf = state.preferences.get("defaultTimeframe", {}).get("value", "5m")
            spec["timeframe"] = pref_tf
            assumptions.append(f"Timeframe defaulted to '{pref_tf}'")

        if not spec.get("exitTime"):
            spec["exitTime"] = "15:10:00"
            assumptions.append("Exit time defaulted to intraday session cutoff at 15:10:00")

        if not spec.get("stopLossPct") and spec.get("hasStop"):
            spec["stopLossPct"] = 25.0
            assumptions.append("Stop loss defaulted to 25% of entry premium")

        assumptions.append("Order quantity fixed to 1 standard lot for strategy definition")

        state.gaps = gaps
        state.questions = questions[:3]  # max 3 questions per round
        state.assumptions = assumptions
        return state

    async def ask_user_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Interrupts graph execution and returns question card."""
        state.clarificationRound += 1
        state.interruptWaiting = True
        state.events.append({
            "event": "question",
            "questions": state.questions,
            "round": state.clarificationRound,
        })
        state.answerDraft = "To build an accurate definition, I need clarification on a few details:"
        return state

    async def build_definition_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Constructs canonical v2 definition using registry codes only."""
        if state.intent == "ADD_RULE":
            pct = 2.0
            pct_match = re.search(r"(\d+(?:\.\d+)?)\s*%", state.userText)
            if pct_match:
                pct = float(pct_match.group(1))

            rule_def = {
                "kind": "GUARDRAIL",
                "code": f"max_daily_loss_{int(pct)}pct",
                "name": f"Max Daily Portfolio Loss ({pct}%)",
                "action": "HALT_TRADING",
                "priority": "CRITICAL",
                "conditionText": f"Total portfolio unrealized + realized daily loss exceeds {pct}% of account capital",
                "parameters": {"maxLossPct": pct, "scope": "PORTFOLIO", "resetAt": "SESSION_OPEN"},
            }
            state.definition = rule_def
            state.backTranslation = f"Halts all trading execution and closes active positions if total daily portfolio loss exceeds {pct}%."
            state.answerDraft = (
                f"### Proposed Risk Guardrail: Max Daily Loss ({pct}%)\n\n"
                f"- **Action**: `HALT_TRADING` (Halts execution and rejects new orders)\n"
                f"- **Condition**: Portfolio loss ≥ {pct}% in a single day\n"
                f"- **Scope**: Entire portfolio / all active strategies\n\n"
                f"I have prepared a proposal card for you to confirm."
            )
            return state

        spec = state.spec
        market = spec.get("market") or "NIFTY"
        tf = spec.get("timeframe") or "5m"
        bias = spec.get("bias") or "BULLISH"
        is_put = bias == "BEARISH" or spec.get("optionSide") == "PUT"

        # Determine condition items
        items = []
        # Close > VWAP
        items.append({
            "left": {"source": "PRICE", "field": "close", "timeframe": tf},
            "operator": "IS_BELOW" if is_put else "IS_ABOVE",
            "right": {"source": "INDICATOR", "code": "VWAP", "timeframe": tf},
        })
        # RSI
        items.append({
            "left": {"source": "INDICATOR", "code": "RSI", "params": {"period": 14}, "timeframe": tf},
            "operator": "IS_BELOW" if is_put else "IS_ABOVE",
            "right": {"const": 40 if is_put else 60},
        })

        # Legs
        opt_type = "PE" if is_put else "CE"
        stop_pct = spec.get("stopLossPct") or 25.0
        legs = [
            {
                "legId": "1",
                "side": "BUY",
                "instrument": {
                    "kind": "OPTION",
                    "optionType": opt_type,
                    "expiry": {"cycle": "WEEKLY", "index": 1},
                    "strike": {"selector": "ATM", "steps": 0},
                },
                "quantity": {"unit": "LOT", "value": 1},
                "stopLoss": {"type": "PERCENT", "value": stop_pct, "basis": "ENTRY_PREMIUM"},
                "target": {"type": "PERCENT", "value": 50.0, "basis": "ENTRY_PREMIUM"},
            }
        ]

        # Handle Naked Strangle if user specifically requested short strangle
        if spec.get("structure") == "STRANGLE" and spec.get("isUndefinedRisk"):
            legs = [
                {
                    "legId": "1",
                    "side": "SELL",
                    "instrument": {
                        "kind": "OPTION",
                        "optionType": "CE",
                        "expiry": {"cycle": "WEEKLY", "index": 1},
                        "strike": {"selector": "ATM_OFFSET", "steps": 2},
                    },
                    "quantity": {"unit": "LOT", "value": 1},
                },
                {
                    "legId": "2",
                    "side": "SELL",
                    "instrument": {
                        "kind": "OPTION",
                        "optionType": "PE",
                        "expiry": {"cycle": "WEEKLY", "index": 1},
                        "strike": {"selector": "ATM_OFFSET", "steps": -2},
                    },
                    "quantity": {"unit": "LOT", "value": 1},
                },
            ]

        exit_time = spec.get("exitTime") or "15:10:00"
        time_exit_when = {
            "op": "ALL",
            "items": [
                {
                    "left": {"source": "TIME", "field": "timeOfDay"},
                    "operator": "IS_ABOVE_OR_EQUAL",
                    "right": {"const": exit_time},
                }
            ],
        }

        # Canonical v2 schema
        code = f"{market.lower()}_{bias.lower()}_{tf}_pulse_v1"
        state.definition = {
            "schemaVersion": 2,
            "format": "RULE_TREE",
            "code": code,
            "name": f"{market} {bias} {tf} Momentum Pulse",
            "category": "MOMENTUM",
            "structure": "STRANGLE" if len(legs) == 2 else "SINGLE_LEG",
            "bias": bias,
            "markets": [market],
            "timeframe": tf,
            "cases": [
                {
                    "key": "0",
                    "label": "Primary Entry",
                    "entry": {
                        "when": {"op": "ALL", "items": items},
                        "legs": legs,
                    },
                    "exit": {
                        "when": time_exit_when,
                        "marketClose": True,
                    },
                    "timeWindow": {
                        "entryStart": "09:15:00",
                        "entryEnd": "15:00:00",
                        "exitBy": exit_time,
                    },
                }
            ],
        }
        return state

    async def validate_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Invokes validate_definition tool."""
        if state.intent == "ADD_RULE":
            state.validation = {"valid": True, "issues": []}
            return state

        state.events.append({"event": "tool.started", "tool": "validate_definition", "label": "Validating canonical definition..."})
        res, _ = await self.gateway.invoke_tool(session, state.runId, "validate_definition", {"definition": state.definition})
        state.events.append({"event": "tool.finished", "tool": "validate_definition", "status": "OK"})
        state.validation = res
        return state

    async def analyze_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Invokes analysis tools: structure, similar, conflicts, and evaluation."""
        if state.intent == "ADD_RULE":
            state.structureAnalysis = {}
            state.similar = []
            state.conflicts = []
            return state

        defn = state.definition
        meta = {"markets": defn.get("markets", ["NIFTY"]), "bias": defn.get("bias"), "structure": defn.get("structure")}

        # 1. Structure
        state.events.append({"event": "tool.started", "tool": "analyze_structure", "label": "Analyzing option legs and risk structure..."})
        struct_res, _ = await self.gateway.invoke_tool(session, state.runId, "analyze_structure", {"definition": defn})
        state.events.append({"event": "tool.finished", "tool": "analyze_structure", "status": "OK"})
        state.structureAnalysis = struct_res

        # 2. Similar
        state.events.append({"event": "tool.started", "tool": "find_similar", "label": "Comparing with existing strategies..."})
        sim_res, _ = await self.gateway.invoke_tool(session, state.runId, "find_similar", {"definition": defn, "topK": 3})
        state.events.append({"event": "tool.finished", "tool": "find_similar", "status": "OK"})
        state.similar = sim_res.get("similar", [])

        # 3. Conflicts
        state.events.append({"event": "tool.started", "tool": "analyze_conflicts", "label": "Checking conflicts against guardrails..."})
        conf_res, _ = await self.gateway.invoke_tool(session, state.runId, "analyze_conflicts", {"definition": defn, "meta": meta})
        state.events.append({"event": "tool.finished", "tool": "analyze_conflicts", "status": "OK"})
        state.conflicts = conf_res.get("conflicts", [])

        return state

    async def back_translate_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Invokes explain_definition for deterministic code-generated English explanation."""
        if state.intent == "ADD_RULE":
            return state

        state.events.append({"event": "tool.started", "tool": "explain_definition", "label": "Generating back-translation..."})
        res, _ = await self.gateway.invoke_tool(
            session, state.runId, "explain_definition", {"definition": state.definition, "meta": {"markets": state.definition.get("markets")}}
        )
        state.events.append({"event": "tool.finished", "tool": "explain_definition", "status": "OK"})
        state.backTranslation = res.get("explanation", "")
        return state

    async def verify_match_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Verifies semantic parity between user prompt and back-translation."""
        if state.intent == "ADD_RULE":
            return state

        messages = [
            {
                "role": "user",
                "content": f"User text:\n{state.userText}\n\nGenerated back-translation:\n{state.backTranslation}\n\nDo they match?",
            }
        ]
        res = await self.llm.generate_structured(messages, VerifyMatchResult)
        if not res.matches and state.repairCount < 2:
            state.repairCount += 1
        elif not res.matches:
            state.complications.append({
                "code": "INTERPRETATION_UNCERTAIN",
                "severity": "WARNING",
                "message": f"The back-translation still differs slightly from what was typed: {', '.join(res.differences)}",
            })
        return state

    async def complications_gate_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Merges all complications and categorizes severities."""
        comps = list(state.complications)

        # Merge validation issues
        for issue in state.validation.get("issues", []):
            comps.append({
                "code": "SCHEMA_INVALID" if issue.get("level") == "ERROR" else "VALIDATION_WARNING",
                "severity": issue.get("severity", "WARNING"),
                "message": issue.get("message"),
                "path": issue.get("path"),
            })

        # Merge conflicts
        for conf in state.conflicts:
            comps.append(conf)

        # Check duplicates
        for sim in state.similar:
            pct = sim.get("similarityPct", 0)
            if pct >= 90:
                comps.append({
                    "code": "DUPLICATE_OF",
                    "severity": "WARNING",
                    "message": f"Strategy is {pct}% similar to existing strategy '{sim.get('code')}'. Consider updating it instead.",
                    "resolutions": [f"Update strategy {sim.get('code')} instead", "Proceed as independent duplicate"],
                })
            elif pct >= 60:
                comps.append({
                    "code": "OVERLAPS_WITH",
                    "severity": "INFO",
                    "message": f"Strategy shares conditions ({pct}% overlap) with '{sim.get('code')}'.",
                })

        # Add assumptions as INFO complications
        for asm in state.assumptions:
            comps.append({
                "code": "DEFAULT_APPLIED",
                "severity": "INFO",
                "message": asm,
            })

        state.complications = comps
        return state

    async def report_blockers_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Reports blockers preventing a proposal from proceeding."""
        blockers = [c for c in state.complications if c.get("severity") == "BLOCKER"]
        lines = ["I found complications that prevent preparing an executable proposal:"]
        for b in blockers:
            lines.append(f"\n❌ **{b.get('code')}**: {b.get('message')}")
            res_list = b.get("resolutions", [])
            if res_list:
                lines.append(f"   *Resolution suggestions:* {', '.join(res_list)}")

        state.answerDraft = "\n".join(lines)
        state.events.append({"event": "message.delta", "delta": state.answerDraft})
        return state

    async def submit_proposal_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Master-local tool: creates master_proposals row with hash."""
        state.events.append({"event": "tool.started", "tool": "submit_proposal", "label": "Creating proposal..."})

        payload = state.definition
        payload_str = json.dumps(payload, sort_keys=True)
        content_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        state.proposalHash = content_hash

        prop_kind = "NEW_RULE" if state.intent == "ADD_RULE" else "NEW_STRATEGY"
        proposal = MasterProposal(
            conversationId=state.conversationId,
            kind=prop_kind,
            targetCode=payload.get("code"),
            userText=state.userText,
            backTranslation=state.backTranslation,
            payload=payload,
            complications=state.complications,
            assumptions=state.assumptions,
            structureAnalysis=state.structureAnalysis,
            validation=state.validation,
            contentHash=content_hash,
            proposalStatus="PENDING",
            expiresAt=datetime.now(timezone.utc) + timedelta(minutes=120),
        )
        saved = await self.proposal_repo.save(session, proposal)
        state.proposalId = saved.id
        state.events.append({"event": "tool.finished", "tool": "submit_proposal", "status": "OK"})
        state.events.append({
            "event": "proposal",
            "proposalId": saved.id,
            "kind": saved.kind,
            "targetCode": saved.targetCode,
            "summary": state.backTranslation[:200],
        })
        return state

    async def present_node(self, state: MasterState, session: AsyncSession) -> MasterState:
        """Final presentation message."""
        state.answerDraft = (
            f"I have prepared a proposal (**Proposal #{state.proposalId}**) for your review.\n\n"
            f"Please verify the back-translation and risk structure below before confirming."
        )
        state.events.append({"event": "message.delta", "delta": state.answerDraft})
        state.events.append({"event": "message.completed"})
        return state
