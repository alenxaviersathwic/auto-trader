"""
The head trader: reads every sub-agent's report and the setups the risk gate allows, thinks it through in writing,
and decides TAKE one setup or WAIT. It runs on the local LLM (ai_master/llm/ollama_client.py: queued, thinking off,
JSON-schema output). It is an option BUYER only and may always wait.

Code keeps the final say: the answer must name a setup the risk gate allowed, and a TAKE below MIN_CONVICTION counts
as WAIT. When the model is down or times out, a plain-code decision stands in and says so (source CODE): it takes a
setup only when it agrees with the price structure, has reward:risk >= 2 and nothing is flagged.
"""
from __future__ import annotations

import json
import re
from typing import Any

from app.core.logging.logger import logger

MIN_CONVICTION = 55
TIMEOUT_S = 60.0

SYSTEM = (
    "You are the head trader of an MCX commodity OPTIONS desk in India (crude oil, natural gas, gold, silver). "
    "You only BUY options (CE when you expect the future to rise, PE when you expect it to fall). Your team gives "
    "you reports: session clock, price structure, option chain, news. You decide like an experienced human desk "
    "trader: take a setup only when the reports line up and the risk is clear; otherwise WAIT, and say what you are "
    "waiting for. Never invent prices or news: use only what the reports say. Keep 'thinking' to 3-5 plain "
    "sentences and 'watchFor' to one sentence. Answer with JSON only."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "decision": {"type": "string", "enum": ["TAKE", "WAIT"]},
        "candidateId": {"type": ["string", "null"]},
        "conviction": {"type": "integer", "minimum": 0, "maximum": 100},
        "thinking": {"type": "string"},
        "watchFor": {"type": "string"},
    },
    "required": ["decision", "candidateId", "conviction", "thinking", "watchFor"],
}


def _brief(code: str, reports: dict[str, dict[str, Any]], allowed: list[dict[str, Any]],
           refused: list[dict[str, Any]]) -> str:
    rep = {k: {"stance": r.get("stance"), "facts": r.get("facts", [])[:6]} for k, r in reports.items()}
    cands = [{k: c.get(k) for k in ("id", "name", "side", "entry", "stop", "target", "rr", "why", "warnings")}
             for c in allowed]
    out = {"commodity": code, "reports": rep, "setupsYouMayTake": cands,
           "setupsTheRiskGateRefused": [{"name": c["name"], "side": c["side"], "why": c.get("refusals")} for c in refused]}
    return json.dumps(out, default=str)


def code_decision(reports: dict[str, dict[str, Any]], allowed: list[dict[str, Any]]) -> dict[str, Any]:
    clean = [c for c in allowed if c.get("withStructure") and float(c.get("rr") or 0) >= 2.0 and not c.get("warnings")]
    struct = reports.get("structure") or {}
    if clean:
        c = max(clean, key=lambda x: float(x.get("rr") or 0))
        return {"decision": "TAKE", "candidateId": c["id"], "conviction": 60, "source": "CODE",
                "thinking": (f"Model unavailable, so the code rule decided. {c['name']} {c['side']} agrees with the "
                             f"{struct.get('stance', 'n/a').lower()} price structure, nothing is flagged and reward:risk "
                             f"is {c['rr']}. {c['why']}."),
                "watchFor": f"invalidation at {c['stop']}; target {c['target']}"}
    why = "no setup is on the table" if not allowed else "the setups on the table are against the structure, flagged, or below 2R"
    return {"decision": "WAIT", "candidateId": None, "conviction": 0, "source": "CODE",
            "thinking": f"Model unavailable, so the code rule decided: {why}. Structure: {struct.get('summary', 'n/a')}.",
            "watchFor": "a setup that agrees with the price structure at 2R or better"}


def _clean(text: str) -> str:
    return re.sub(r"<think>.*?</think>", "", text or "", flags=re.S).strip()


async def decide(code: str, reports: dict[str, dict[str, Any]], allowed: list[dict[str, Any]],
                 refused: list[dict[str, Any]]) -> dict[str, Any]:
    """{decision, candidateId, conviction, thinking, watchFor, source (LLM | CODE)}."""
    from app.modules.ai_master.llm.ollama_client import chat, pick_model

    try:
        payload = {"model": await pick_model(fast=False), "format": SCHEMA,
                   "messages": [{"role": "system", "content": SYSTEM},
                                {"role": "user", "content": _brief(code, reports, allowed, refused)}],
                   "options": {"temperature": 0.2, "num_predict": 400}}
        data = await chat(payload, timeout=TIMEOUT_S)
        ans = json.loads(_clean(data.get("message", {}).get("content", "")))
    except Exception as e:  # noqa: BLE001 -- the desk must keep working without the model
        logger.warning(f"[DESK] {code} head trader unavailable ({type(e).__name__}: {e}); code decision")
        return code_decision(reports, allowed)
    ids = {c["id"] for c in allowed}
    decision = str(ans.get("decision") or "WAIT").upper()
    cid = ans.get("candidateId")
    conv = int(ans.get("conviction") or 0)
    out = {"decision": decision, "candidateId": cid, "conviction": max(0, min(100, conv)), "source": "LLM",
           "thinking": str(ans.get("thinking") or "")[:1200], "watchFor": str(ans.get("watchFor") or "")[:300]}
    if decision == "TAKE" and cid not in ids:
        out.update(decision="WAIT", candidateId=None,
                   thinking=out["thinking"] + " [code: the named setup was not one the risk gate allowed - WAIT]")
    elif decision == "TAKE" and conv < MIN_CONVICTION:
        out.update(decision="WAIT", thinking=out["thinking"] + f" [code: conviction {conv} < {MIN_CONVICTION} - WAIT]")
    elif decision != "TAKE":
        out.update(decision="WAIT", candidateId=None)
    return out
