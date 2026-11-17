"""
Local LLM client (Ollama), shared by every module that uses the model: Research Engine (claims, brief),
AI Master chat, the opportunity ranker (when OPPORTUNITY_RANKER=LLM), the trade AI analysis and the index notes.

Tuned for one local model on one machine:
  queue        at most LLM_MAX_CONCURRENCY calls at once; the rest wait their turn instead of making the model
               swap / thrash (the wait counts toward each call's timeout)
  no thinking  think=False by default (qwen3 otherwise writes a long hidden reasoning pass on every call)
  warm model   keep_alive=LLM_KEEP_ALIVE so it is not reloaded after 5 idle minutes
  small ctx    num_ctx=LLM_NUM_CTX; structured calls send the schema only as Ollama's `format` (it constrains the
               output), not pasted into the prompt as well
  fast model   fast=True uses LLM_FAST_MODEL when it is installed, else the default model
  cache        cache_ttl>0 reuses an identical request's answer for that many seconds
  one client   a single pooled HTTP client (no new connection per call)
"""
import asyncio
import hashlib
import json
import re
import time
from typing import Any, Dict, List, Optional, Type

import httpx

from app.core.config.settings import settings
from app.core.logging.logger import logger
from app.modules.ai_master.llm.llm_client import LlmClient, T

_http: Optional[httpx.AsyncClient] = None
_sems: Dict[int, asyncio.Semaphore] = {}  # one per event loop (tests run several loops)
_installed: tuple[float, set[str]] = (0.0, set())
_cache: Dict[str, tuple[float, Any]] = {}
_CACHE_MAX = 256
_TAGS_TTL_S = 300.0
_stats: Dict[str, Any] = {"calls": 0, "cacheHits": 0, "lastModel": None, "lastSeconds": None, "lastWaitSeconds": None}


def _client() -> httpx.AsyncClient:
    global _http
    if _http is None or _http.is_closed:
        _http = httpx.AsyncClient(timeout=None, limits=httpx.Limits(max_connections=8, max_keepalive_connections=4))
    return _http


def _sem() -> asyncio.Semaphore:
    loop_id = id(asyncio.get_running_loop())
    if loop_id not in _sems:
        _sems[loop_id] = asyncio.Semaphore(max(1, int(settings.LLM_MAX_CONCURRENCY)))
    return _sems[loop_id]


def llm_stats() -> Dict[str, Any]:
    """Calls, cache hits and the last call's model / time (system status page)."""
    return dict(_stats)


def _no_think(payload: Dict[str, Any]) -> None:
    """think=False, plus qwen3's soft switch for Ollama versions that ignore the field."""
    payload["think"] = False
    msgs = payload.get("messages") or []
    if "qwen3" in str(payload.get("model", "")).lower() and msgs and "/no_think" not in msgs[-1].get("content", ""):
        msgs[-1] = {**msgs[-1], "content": f"{msgs[-1]['content']}\n/no_think"}


async def chat(payload: Dict[str, Any], timeout: float, cache_ttl: float = 0.0) -> Dict[str, Any]:
    """POST /api/chat with the shared defaults (think, keep_alive, num_ctx) through the queue. Returns Ollama's JSON.
    Raises on HTTP errors and on timeout (queue wait included)."""
    payload = {**payload, "stream": False}
    payload.setdefault("keep_alive", settings.LLM_KEEP_ALIVE)
    payload["options"] = {"num_ctx": settings.LLM_NUM_CTX, **(payload.get("options") or {})}
    if payload.get("think") is None and not settings.LLM_THINK:
        _no_think(payload)
    elif payload.get("think") is False:
        _no_think(payload)

    key = ""
    if cache_ttl > 0:
        key = hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()
        hit = _cache.get(key)
        if hit and hit[0] > time.monotonic():
            _stats["cacheHits"] += 1
            return hit[1]

    started = time.monotonic()

    async def run() -> Dict[str, Any]:
        async with _sem():
            waited = time.monotonic() - started
            resp = await _client().post(f"{settings.OLLAMA_BASE_URL}/api/chat", json=payload,
                                        timeout=max(1.0, timeout - waited))
            if resp.status_code != 200:
                raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text[:300]}")
            data = resp.json()
            _stats.update(calls=_stats["calls"] + 1, lastModel=payload.get("model"),
                          lastSeconds=round(time.monotonic() - started, 2), lastWaitSeconds=round(waited, 2))
            _log_timings(payload.get("model", ""), data, waited)
            return data

    data = await asyncio.wait_for(run(), timeout=timeout)
    if key:
        if len(_cache) >= _CACHE_MAX:
            for k in sorted(_cache, key=lambda k: _cache[k][0])[: _CACHE_MAX // 4]:
                _cache.pop(k, None)
        _cache[key] = (time.monotonic() + cache_ttl, data)
    return data


async def installed_models() -> set[str]:
    """Model names Ollama has (cached a few minutes); empty when it is unreachable."""
    global _installed
    if time.monotonic() - _installed[0] < _TAGS_TTL_S and _installed[1]:
        return _installed[1]
    try:
        resp = await _client().get(f"{settings.OLLAMA_BASE_URL}/api/tags", timeout=3.0)
        names = {m.get("name", "") for m in resp.json().get("models", [])} if resp.status_code == 200 else set()
    except Exception:
        names = set()
    _installed = (time.monotonic(), names)
    return names


def _has(names: set[str], model: str) -> bool:
    return any(n == model or n.split(":")[0] == model or n.startswith(model + ":") or n == model + ":latest"
               for n in names)


async def pick_model(fast: bool = False, requested: Optional[str] = None) -> str:
    """The model to call: `requested`, else LLM_FAST_MODEL for fast tasks when installed, else OLLAMA_MODEL
    (or any installed chat model when that one is missing)."""
    if requested:
        return requested
    names = await installed_models()
    if fast and _has(names, settings.LLM_FAST_MODEL):
        return settings.LLM_FAST_MODEL
    if not names or _has(names, settings.OLLAMA_MODEL):
        return settings.OLLAMA_MODEL
    chat_models = sorted(n for n in names if "embed" not in n.lower())
    return next((n for n in chat_models if "qwen" in n.lower()), chat_models[0] if chat_models else settings.OLLAMA_MODEL)


def _clean_json(content: str) -> str:
    content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
    if "```" in content:
        fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
        if fenced:
            content = fenced.group(1).strip()
    m = re.search(r"\{[\s\S]*\}", content)
    return m.group(0).strip() if m else content


class OllamaClient(LlmClient):
    """LlmClient on the shared, queued, tuned path above."""

    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.default_model = default_model or settings.OLLAMA_MODEL

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
        *,
        fast: bool = False,
        think: Optional[bool] = None,
        num_predict: Optional[int] = None,
        timeout: float = 90.0,
        cache_ttl: float = 0.0,
    ) -> str:
        msgs = ([{"role": "system", "content": system_prompt}] if system_prompt else []) + list(messages)
        payload: Dict[str, Any] = {"model": await pick_model(fast, model), "messages": msgs,
                                   "options": {"temperature": temperature}, "think": think}
        if num_predict is not None:
            payload["options"]["num_predict"] = num_predict
        try:
            data = await chat(payload, timeout, cache_ttl)
        except Exception as e:
            logger.error(f"Ollama generate failed: {type(e).__name__}: {e}")
            raise
        return re.sub(r"<think>[\s\S]*?</think>", "", data.get("message", {}).get("content", "")).strip()

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
        timeout: float = 90.0,
        think: Optional[bool] = None,
        num_predict: Optional[int] = None,
        keep_alive: Optional[str] = None,
        *,
        fast: bool = False,
        cache_ttl: float = 0.0,
    ) -> T:
        json_schema = schema.model_json_schema()
        fields = ", ".join(json_schema.get("properties", {}).keys())
        # Ollama's `format` constrains decoding to the schema, so the prompt only names the fields (pasting the
        # whole schema doubled the prompt and the time to read it)
        sys = (system_prompt + "\n\n" if system_prompt else "") + f"Reply with one JSON object only (fields: {fields})."
        payload: Dict[str, Any] = {"model": await pick_model(fast, model),
                                   "messages": [{"role": "system", "content": sys}, *messages],
                                   "format": json_schema, "options": {"temperature": temperature}, "think": think}
        if num_predict is not None:
            payload["options"]["num_predict"] = num_predict
        if keep_alive is not None:
            payload["keep_alive"] = keep_alive
        try:
            data = await chat(payload, timeout, cache_ttl)
            content = _clean_json(data.get("message", {}).get("content", ""))
            try:
                return schema.model_validate(json.loads(content))
            except Exception as parse_err:
                logger.warning(f"Failed to parse structured JSON: {content[:100]}... Error: {parse_err}")
                if schema.__name__ == "IntentClassification":
                    return schema(intent="CHAT", confidence=0.7)  # type: ignore[call-arg]
                try:
                    return schema()
                except Exception:
                    raise parse_err
        except Exception as e:
            logger.error(f"Ollama structured generate failed: {type(e).__name__}: {e}")
            if schema.__name__ == "IntentClassification":
                return schema(intent="CHAT", confidence=0.7)  # type: ignore[call-arg]
            raise

    async def _resolve_healthy_url(self) -> Optional[str]:
        """The Ollama URL when it answers (callers check this before a call), else None."""
        return self.base_url if await installed_models() else None

    async def is_healthy(self) -> bool:
        return bool(await installed_models())


def _log_timings(model: str, data: Dict[str, Any], waited: float) -> None:
    """Ollama's nanosecond timings: where the time went (queue, model load, reading the prompt, writing)."""
    ns = 1_000_000_000
    try:
        logger.info(
            f"[OLLAMA_TIMING] model={model} queue={waited:.1f}s total={data.get('total_duration', 0) / ns:.1f}s "
            f"load={data.get('load_duration', 0) / ns:.1f}s "
            f"prompt={data.get('prompt_eval_count', 0)}tok/{data.get('prompt_eval_duration', 0) / ns:.1f}s "
            f"answer={data.get('eval_count', 0)}tok/{data.get('eval_duration', 0) / ns:.1f}s"
        )
    except Exception:
        pass
