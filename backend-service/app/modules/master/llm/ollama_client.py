import json
import os
import re
from typing import Any, Dict, List, Optional, Type, TypeVar
import httpx
from pydantic import BaseModel
from app.core.logging.logger import logger
from app.modules.master.llm.llm_client import LlmClient, T


class OllamaClient(LlmClient):
    """
    Ollama LLM Client connecting to local or dockerized Ollama service.
    Enforces temperature 0.0 for extractions and supports JSON format.
    """

    def __init__(self, base_url: Optional[str] = None, default_model: Optional[str] = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
        self.default_model = default_model or os.getenv("OLLAMA_MODEL", "qwen3:8b")

    async def _resolve_healthy_url(self) -> Optional[str]:
        """Check configured base_url, or fallback between host.docker.internal and localhost."""
        candidates = [self.base_url, "http://host.docker.internal:11434", "http://localhost:11434"]
        seen = set()
        for url in candidates:
            if not url or url in seen:
                continue
            seen.add(url)
            try:
                async with httpx.AsyncClient(timeout=3.0) as client:
                    resp = await client.get(f"{url}/api/tags")
                    if resp.status_code == 200:
                        self.base_url = url
                        # Inspect available models to ensure default_model is valid
                        data = resp.json()
                        available = [m.get("name", "") for m in data.get("models", [])]
                        # If default_model matches or partial matches (e.g. qwen3:8b)
                        if any(self.default_model in m for m in available):
                            # Already matched
                            pass
                        elif any("qwen" in m.lower() for m in available):
                            # Pick available qwen model
                            for m in available:
                                if "qwen" in m.lower():
                                    self.default_model = m
                                    break
                        elif available:
                            # Pick first non-embedding model
                            for m in available:
                                if "embed" not in m.lower():
                                    self.default_model = m
                                    break
                        return url
            except Exception:
                continue
        return None

    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        prompt_msgs = []
        if system_prompt:
            prompt_msgs.append({"role": "system", "content": system_prompt})
        prompt_msgs.extend(messages)

        use_model = model or self.default_model
        payload = {
            "model": use_model,
            "messages": prompt_msgs,
            "stream": False,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text}")
                data = resp.json()
                return data.get("message", {}).get("content", "").strip()
            except Exception as e:
                logger.error(f"Ollama generate failed: {e}")
                raise e

    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> T:
        prompt_msgs = []
        schema_json = json.dumps(schema.model_json_schema(), indent=2)
        augmented_sys = (
            (system_prompt + "\n\n" if system_prompt else "")
            + f"You must output valid JSON strictly matching this JSON schema:\n{schema_json}\nOutput ONLY valid JSON."
        )
        prompt_msgs.append({"role": "system", "content": augmented_sys})
        prompt_msgs.extend(messages)

        use_model = model or self.default_model
        payload = {
            "model": use_model,
            "messages": prompt_msgs,
            "format": "json",
            "stream": False,
            "options": {"temperature": temperature},
        }

        async with httpx.AsyncClient(timeout=90.0) as client:
            try:
                resp = await client.post(f"{self.base_url}/api/chat", json=payload)
                if resp.status_code != 200:
                    raise RuntimeError(f"Ollama returned {resp.status_code}: {resp.text}")
                data = resp.json()
                content = data.get("message", {}).get("content", "").strip()
                # 1. Remove <think>...</think> reasoning blocks if present (common in Qwen models)
                content = re.sub(r"<think>[\s\S]*?</think>", "", content).strip()
                # 2. Extract from markdown code fences if present
                if "```" in content:
                    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", content)
                    if fenced:
                        content = fenced.group(1).strip()
                # 3. Find the first '{' and last '}' to extract raw JSON
                json_match = re.search(r"\{[\s\S]*\}", content)
                if json_match:
                    content = json_match.group(0).strip()

                try:
                    parsed = json.loads(content)
                    return schema.model_validate(parsed)
                except Exception as parse_err:
                    logger.warning(f"Failed to parse structured JSON from content: {content[:100]}... Error: {parse_err}")
                    # If schema is IntentClassification, return CHAT as fallback
                    if hasattr(schema, "__name__") and schema.__name__ == "IntentClassification":
                        return schema(intent="CHAT", confidence=0.7)  # type: ignore
                    # Try creating an empty/default instance of the schema
                    try:
                        return schema()
                    except Exception:
                        raise parse_err
            except Exception as e:
                logger.error(f"Ollama structured generate failed: {e}")
                # Fallback for intent classification so worker never crashes
                if hasattr(schema, "__name__") and schema.__name__ == "IntentClassification":
                    return schema(intent="CHAT", confidence=0.7)  # type: ignore
                raise e

    async def is_healthy(self) -> bool:
        url = await self._resolve_healthy_url()
        return url is not None
