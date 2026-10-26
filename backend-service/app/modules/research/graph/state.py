from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ResearchState(BaseModel):
    """
    State object passed between nodes of the Research LangGraph pipeline.
    """

    runId: int
    scope: List[str] = Field(default_factory=lambda: ["INDEX", "COMMODITY"])
    params: Dict[str, Any] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)
    underlyings: List[Dict[str, Any]] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)
    riskTerms: List[Dict[str, Any]] = Field(default_factory=list)
    queries: List[Dict[str, Any]] = Field(default_factory=list)
    fetchedArticles: List[Dict[str, Any]] = Field(default_factory=list)
    chunks: List[Dict[str, Any]] = Field(default_factory=list)
    claims: List[Dict[str, Any]] = Field(default_factory=list)
    candidates: List[Dict[str, Any]] = Field(default_factory=list)
    stats: Dict[str, Any] = Field(default_factory=lambda: {
        "docsFetched": 0,
        "docsKept": 0,
        "docsBlocked": 0,
        "chunksEmbedded": 0,
        "claimsExtracted": 0,
        "claimsReused": 0,
        "claimsVerified": 0,
        "claimsDropped": 0,
        "sweepFindings": 0,
        "llmCalls": 0,
        "durationsByNodeMs": {},
    })
    currentNode: Optional[str] = None
    progressPct: int = 0
    state: str = "RUNNING"
    error: Optional[str] = None
    isCancelled: bool = False
