import hashlib
import math
from typing import List
import httpx
from app.core.config.settings import settings
from app.core.logging.logger import logger


class EmbeddingClient:
    """
    Computes dense vector embeddings using Ollama (nomic-embed-text, 768 dims)
    with a deterministic fallback generator.
    """

    def __init__(self, base_url: str = "", model: str = "", dimension: int = 768):
        self.base_url = (base_url or getattr(settings, "OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or getattr(settings, "EMBEDDING_MODEL", "nomic-embed-text")
        self.dimension = dimension or getattr(settings, "EMBEDDING_DIMENSION", 768)

    async def get_embedding(self, text: str) -> List[float]:
        """
        Computes 768-dim normalized embedding vector.
        """
        if not text.strip():
            return [0.0] * self.dimension

        try:
            payload = {
                "model": self.model,
                "prompt": text,
                "keep_alive": "30m",  # stay loaded; avoids unload/reload churn next to the chat model
            }
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(f"{self.base_url}/api/embeddings", json=payload)
                if resp.status_code == 200:
                    emb = resp.json().get("embedding", [])
                    if len(emb) == self.dimension:
                        return emb
                    elif len(emb) > 0:
                        logger.warning(
                            f"Embedding dimension mismatch: expected {self.dimension}, got {len(emb)}"
                        )
                        # Pad or truncate to maintain schema invariant
                        if len(emb) > self.dimension:
                            return emb[:self.dimension]
                        else:
                            return emb + [0.0] * (self.dimension - len(emb))
        except Exception:
            pass

        # Deterministic pseudo-embedding for testing / offline Ollama
        return self._generate_deterministic_vector(text, self.dimension)

    @staticmethod
    def _generate_deterministic_vector(text: str, dim: int = 768) -> List[float]:
        """Produces a deterministic, unit-normalized vector from sha256 hash seeds."""
        h = hashlib.sha256(text.encode("utf-8")).digest()
        vec = []
        for i in range(dim):
            byte_val = h[i % len(h)]
            val = ((byte_val / 255.0) * 2.0) - 1.0 + (math.sin(i * 0.1) * 0.2)
            vec.append(val)

        norm = math.sqrt(sum(x * x for x in vec))
        if norm > 0:
            vec = [round(x / norm, 6) for x in vec]
        return vec


embedding_client = EmbeddingClient()
