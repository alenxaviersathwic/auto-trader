import json
import re
from typing import Any, Dict, List, Optional, Type
from app.modules.master.llm.llm_client import LlmClient, T


class FakeLlmClient(LlmClient):
    """
    Fake scriptable LLM client for deterministic unit testing and golden sentence eval.
    Does not require any live network or running model.
    """

    def __init__(self):
        self.scripted_text_responses: List[str] = []
        self.scripted_structured_responses: List[Any] = []
        self.recorded_calls: List[Dict[str, Any]] = []
        self.healthy: bool = True

    def queue_text(self, text: str) -> None:
        self.scripted_text_responses.append(text)

    def queue_structured(self, response: Any) -> None:
        self.scripted_structured_responses.append(response)

    def clear(self) -> None:
        self.scripted_text_responses.clear()
        self.scripted_structured_responses.clear()
        self.recorded_calls.clear()

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        self.recorded_calls.append({
            "type": "text",
            "messages": messages,
            "system_prompt": system_prompt,
            "temperature": temperature,
        })
        if self.scripted_text_responses:
            return self.scripted_text_responses.pop(0)

        # Default intelligent fallback
        user_content = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        return f"Understood. Processed your request: '{user_content[:80]}'."

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> T:
        self.recorded_calls.append({
            "type": "structured",
            "schema": schema.__name__,
            "messages": messages,
            "system_prompt": system_prompt,
            "temperature": temperature,
        })
        if self.scripted_structured_responses:
            resp = self.scripted_structured_responses.pop(0)
            if isinstance(resp, schema):
                return resp
            elif isinstance(resp, dict):
                return schema.model_validate(resp)

        # Intelligent default parser based on schema type
        user_content = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
        u_lower = user_content.lower()

        schema_name = schema.__name__

        if schema_name == "IntentClassification":
            # Classify intent from prompt
            intent = "ADD_STRATEGY"
            conf = 0.95
            entities = {}

            if any(w in u_lower for w in ["place an order", "buy 100 shares now", "sell market order", "make me rich"]):
                intent = "OUT_OF_SCOPE"
            elif any(w in u_lower for w in ["remember", "save preference", "my default"]):
                intent = "REMEMBER"
            elif any(w in u_lower for w in ["why is", "explain", "how has", "what is"]):
                intent = "EXPLAIN"
            elif any(w in u_lower for w in ["find", "search", "show me", "list"]):
                intent = "FIND"
            elif any(w in u_lower for w in ["is this strategy good", "is this good"]):
                intent = "ANALYZE_TEXT"
            elif any(w in u_lower for w in ["rule", "guardrail", "block when", "avoid when"]):
                intent = "ADD_RULE"
            elif any(w in u_lower for w in ["update", "modify", "change strategy"]):
                intent = "UPDATE_STRATEGY"
            elif any(w in u_lower for w in ["enable", "disable", "suspend", "archive"]):
                intent = "SET_LIFECYCLE"
            elif any(w in u_lower for w in ["delete"]):
                intent = "DELETE_DRAFT"
            elif len(user_content.strip()) < 5:
                intent = "UNCLEAR"
                conf = 0.4

            return schema.model_validate({"intent": intent, "confidence": conf, "entities": entities})

        elif schema_name == "ExtractedSpec":
            # Extract partial spec from user text
            is_rule = "rule" in u_lower or "guardrail" in u_lower
            market = "NIFTY" if "nifty" in u_lower else ("BANKNIFTY" if "banknifty" in u_lower else ("CRUDEOIL" if "crude" in u_lower else None))
            timeframe = "5m" if "5-minute" in u_lower or "5m" in u_lower else ("15m" if "15m" in u_lower else None)
            bias = "BULLISH" if any(w in u_lower for w in ["call", "buy", "long"]) else ("BEARISH" if any(w in u_lower for w in ["put", "short"]) else None)

            # Check indicators
            indicators = []
            if "vwap" in u_lower:
                indicators.append("VWAP")
            if "rsi" in u_lower:
                indicators.append("RSI")
            if "ema" in u_lower:
                indicators.append("EMA")
            if "supertrend" in u_lower:
                indicators.append("SUPERTREND")
            if "madeup_indicator" in u_lower or "magic_indicator" in u_lower:
                indicators.append("MADEUP_INDICATOR")

            # Exit / Stop
            has_stop = "stop" in u_lower or "sl" in u_lower
            has_exit = "exit" in u_lower or "target" in u_lower

            return schema.model_validate({
                "market": market,
                "bias": bias,
                "structure": "STRANGLE" if "strangle" in u_lower else ("IRON_CONDOR" if "iron condor" in u_lower else "SINGLE_LEG"),
                "optionSide": "CALL" if "call" in u_lower else ("PUT" if "put" in u_lower else None),
                "timeframe": timeframe,
                "entryDescription": user_content,
                "indicators": indicators,
                "hasStop": has_stop,
                "hasExit": has_exit,
                "stopLossPct": 25.0 if "25%" in user_content else None,
                "exitTime": "15:10:00" if "15:10" in user_content else None,
                "isVague": any(w in u_lower for w in ["looks strong", "on momentum", "when good", "feels right"]),
                "isUndefinedRisk": "naked" in u_lower or ("sell" in u_lower and not has_stop and "hedge" not in u_lower),
            })

        elif schema_name == "VerifyMatchResult":
            # Compare backtranslation
            return schema.model_validate({
                "matches": True,
                "differences": [],
            })

        # Generic default
        return schema.model_construct()

    async def is_healthy(self) -> bool:
        return self.healthy
