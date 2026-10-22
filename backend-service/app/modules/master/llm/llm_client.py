from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type, TypeVar
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LlmClient(ABC):
    """Abstract interface for LLM operations."""

    @abstractmethod
    async def generate(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> str:
        """Generates plain text response."""
        pass

    @abstractmethod
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        schema: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.0,
        model: Optional[str] = None,
    ) -> T:
        """Generates structured response parsed into schema."""
        pass

    @abstractmethod
    async def is_healthy(self) -> bool:
        """Checks if the LLM provider service is reachable."""
        pass
