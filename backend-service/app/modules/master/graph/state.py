from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MasterState(BaseModel):
    conversationId: int = 0
    runId: int = 0
    userText: str = ""
    history: List[Dict[str, str]] = Field(default_factory=list)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    intent: str = "ADD_STRATEGY"
    confidence: float = 1.0
    entities: Dict[str, Any] = Field(default_factory=dict)
    spec: Dict[str, Any] = Field(default_factory=dict)
    gaps: List[Dict[str, Any]] = Field(default_factory=list)
    questions: List[Dict[str, Any]] = Field(default_factory=list)
    clarificationRound: int = 0
    definition: Dict[str, Any] = Field(default_factory=dict)
    validation: Dict[str, Any] = Field(default_factory=dict)
    structureAnalysis: Dict[str, Any] = Field(default_factory=dict)
    similar: List[Dict[str, Any]] = Field(default_factory=list)
    conflicts: List[Dict[str, Any]] = Field(default_factory=list)
    backTranslation: str = ""
    complications: List[Dict[str, Any]] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)
    proposalId: Optional[int] = None
    proposalHash: Optional[str] = None
    answerDraft: str = ""
    repairCount: int = 0
    interruptWaiting: bool = False
    stopRequested: bool = False
    events: List[Dict[str, Any]] = Field(default_factory=list)

    model_config = {"extra": "ignore"}
