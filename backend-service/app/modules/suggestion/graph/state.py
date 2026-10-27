import operator
from typing import Annotated, Any, TypedDict


def merge_dicts(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {**(a or {}), **(b or {})}


class SuggestionState(TypedDict, total=False):
    """Parent graph state. Lists with a reducer are filled in parallel by the per-underlying branches."""

    runId: int
    params: dict[str, Any]
    researchRunId: int | None
    underlyings: list[dict[str, Any]]  # research candidates chosen (top 5 INDEX + top 3 COMMODITY)
    results: Annotated[list[dict[str, Any]], operator.add]  # validated candidates from each branch
    skipped: Annotated[list[dict[str, Any]], operator.add]
    prices: Annotated[dict[str, float], merge_dicts]  # instrumentKey -> latest ltp
    iterated: Annotated[dict[str, str], merge_dicts]  # code -> ISO time this run analysed it
    notes: Annotated[dict[str, str], merge_dicts]  # code -> why it had / had no suggestions
    picks: list[dict[str, Any]]
    savedIds: list[int]
    outcomesResolved: int
    status: str  # OK | NO_RESEARCH | NO_UNDERLYINGS
    aiUsed: Annotated[int, operator.add]
    baselineUsed: Annotated[int, operator.add]


class UnderlyingState(TypedDict, total=False):
    """Per-underlying subgraph state: one instance per underlying, same code, different config."""

    runId: int
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
