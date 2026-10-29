from typing import Any, TypedDict


class UnderlyingState(TypedDict, total=False):
    """Per-underlying subgraph state: one instance per underlying, same code, different config."""

    masterId: int
    params: dict[str, Any]
    research: dict[str, Any]
    code: str
    market: dict[str, Any]
    strategies: list[str]
    strategyNames: list[str]
    memory: list[str]
    hitRate: str
    bias: str
    brief: dict[str, Any]
    briefHash: str
    menu: list[dict[str, Any]]
    answer: dict[str, Any]
    reused: bool
    usedBaseline: bool
    error: str | None
    candidates: list[dict[str, Any]]
    note: str
