from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class IntentClassification(BaseModel):
    intent: str = Field(..., description="ADD_STRATEGY, ADD_RULE, UPDATE_STRATEGY, UPDATE_RULE, SET_LIFECYCLE, DELETE_DRAFT, FIND, EXPLAIN, ANALYZE_TEXT, REMEMBER, CHAT, OUT_OF_SCOPE, UNCLEAR")
    confidence: float = Field(default=1.0, description="Confidence score between 0.0 and 1.0")
    entities: Dict[str, Any] = Field(default_factory=dict)


class ExtractedSpec(BaseModel):
    market: Optional[str] = None
    bias: Optional[str] = None
    structure: Optional[str] = None
    optionSide: Optional[str] = None
    timeframe: Optional[str] = None
    entryDescription: str = ""
    indicators: List[str] = Field(default_factory=list)
    hasStop: bool = False
    hasExit: bool = False
    stopLossPct: Optional[float] = None
    exitTime: Optional[str] = None
    targetCode: Optional[str] = None
    isVague: bool = False
    isUndefinedRisk: bool = False
    parameters: Dict[str, Any] = Field(default_factory=dict)


class VerifyMatchResult(BaseModel):
    matches: bool = True
    differences: List[str] = Field(default_factory=list)
