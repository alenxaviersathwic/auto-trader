from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db.base_entity import BaseEntity


class SuggestionRun(BaseEntity):
    """LEGACY: one iteration of the old server-side loop. Replaced by SuggestionMaster; kept for history."""

    __tablename__ = "suggestion_runs"

    loopId: Mapped[str] = mapped_column("loop_id", String(40), nullable=False)
    iteration: Mapped[int] = mapped_column("iteration", Integer, nullable=False, default=1)
    state: Mapped[str] = mapped_column("state", String(20), nullable=False, default="QUEUED")
    params: Mapped[dict[str, Any]] = mapped_column("params", JSONB, nullable=False, default=dict)
    researchRunId: Mapped[int | None] = mapped_column("research_run_id", BigInteger, nullable=True)
    currentNode: Mapped[str | None] = mapped_column("current_node", String(50), nullable=True)
    progressPct: Mapped[int] = mapped_column("progress_pct", SmallInteger, nullable=False, default=0)
    stats: Mapped[dict[str, Any]] = mapped_column("stats", JSONB, nullable=False, default=dict)
    startedAt: Mapped[datetime | None] = mapped_column("started_at", DateTime(timezone=True), nullable=True)
    finishedAt: Mapped[datetime | None] = mapped_column("finished_at", DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column("error", Text, nullable=True)


class SuggestionMaster(BaseEntity):
    """
    One card session: a row is created for every underlying each time Start is clicked.
    The frontend then calls /iterate on each RUNNING master one by one, in a loop; every
    iteration updates the counters here and writes its picks to trade_suggestions.
    """

    __tablename__ = "suggestion_masters"

    tradeDate: Mapped[str] = mapped_column("trade_date", String(10), nullable=False)  # YYYY-MM-DD (IST)
    sessionNo: Mapped[int] = mapped_column("session_no", SmallInteger, nullable=False, default=1)
    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False)
    underlyingType: Mapped[str] = mapped_column("underlying_type", String(10), nullable=False)
    state: Mapped[str] = mapped_column("state", String(12), nullable=False, default="RUNNING")  # RUNNING | STOPPED
    stopReason: Mapped[str | None] = mapped_column("stop_reason", String(40), nullable=True)
    params: Mapped[dict[str, Any]] = mapped_column("params", JSONB, nullable=False, default=dict)
    researchRunId: Mapped[int | None] = mapped_column("research_run_id", BigInteger, nullable=True)
    researchScore: Mapped[float | None] = mapped_column("research_score", Numeric(6, 2), nullable=True)
    direction: Mapped[str | None] = mapped_column("direction", String(10), nullable=True)
    newsStatus: Mapped[str | None] = mapped_column("news_status", String(20), nullable=True)
    inResearch: Mapped[bool] = mapped_column("in_research", Boolean, nullable=False, default=True)
    iterationsCompleted: Mapped[int] = mapped_column("iterations_completed", Integer, nullable=False, default=0)
    iterationsFailed: Mapped[int] = mapped_column("iterations_failed", Integer, nullable=False, default=0)
    suggestionsTotal: Mapped[int] = mapped_column("suggestions_total", Integer, nullable=False, default=0)
    lastSuggestionCount: Mapped[int] = mapped_column("last_suggestion_count", SmallInteger, nullable=False, default=0)
    topConfidence: Mapped[int] = mapped_column("top_confidence", SmallInteger, nullable=False, default=0)
    lastNote: Mapped[str | None] = mapped_column("last_note", Text, nullable=True)
    lastError: Mapped[str | None] = mapped_column("last_error", Text, nullable=True)
    lastDurationMs: Mapped[int | None] = mapped_column("last_duration_ms", Integer, nullable=True)
    startedAt: Mapped[datetime] = mapped_column("started_at", DateTime(timezone=True), nullable=False)
    lastStartedAt: Mapped[datetime | None] = mapped_column("last_started_at", DateTime(timezone=True), nullable=True)
    lastCompletedAt: Mapped[datetime | None] = mapped_column("last_completed_at", DateTime(timezone=True), nullable=True)
    stoppedAt: Mapped[datetime | None] = mapped_column("stopped_at", DateTime(timezone=True), nullable=True)


class TradeSuggestion(BaseEntity):
    """One executable suggestion produced by one iteration of a SuggestionMaster."""

    __tablename__ = "trade_suggestions"

    masterId: Mapped[int] = mapped_column("master_id", BigInteger, nullable=False, index=True)
    iterationNo: Mapped[int] = mapped_column("iteration_no", Integer, nullable=False)
    ref: Mapped[str] = mapped_column("ref", String(48), nullable=False)
    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False)
    underlyingType: Mapped[str] = mapped_column("underlying_type", String(10), nullable=False)
    contractId: Mapped[str] = mapped_column("contract_id", String(60), nullable=False)
    instrumentKey: Mapped[str | None] = mapped_column("instrument_key", String(80), nullable=True)
    optionType: Mapped[str] = mapped_column("option_type", String(2), nullable=False)
    spot: Mapped[float] = mapped_column("spot", Numeric(12, 2), nullable=False, default=0)
    strike: Mapped[float] = mapped_column("strike", Numeric(12, 2), nullable=False)
    expiry: Mapped[str] = mapped_column("expiry", String(10), nullable=False)
    entry: Mapped[float] = mapped_column("entry", Numeric(12, 2), nullable=False)
    stop: Mapped[float] = mapped_column("stop", Numeric(12, 2), nullable=False)
    target: Mapped[float] = mapped_column("target", Numeric(12, 2), nullable=False)
    profitMarginPct: Mapped[float] = mapped_column("profit_margin_pct", Numeric(6, 2), nullable=False)
    rewardRisk: Mapped[float] = mapped_column("reward_risk", Numeric(6, 2), nullable=False)
    confidence: Mapped[int] = mapped_column("confidence", SmallInteger, nullable=False)
    riskLevel: Mapped[str] = mapped_column("risk_level", String(8), nullable=False, default="MEDIUM")
    rank: Mapped[int] = mapped_column("rank", SmallInteger, nullable=False)
    strategy: Mapped[str | None] = mapped_column("strategy", String(100), nullable=True)
    reasons: Mapped[list[str]] = mapped_column("reasons", JSONB, nullable=False, default=list)
    risks: Mapped[list[str]] = mapped_column("risks", JSONB, nullable=False, default=list)
    source: Mapped[str] = mapped_column("source", String(10), nullable=False, default="AI")
    validUntil: Mapped[datetime] = mapped_column("valid_until", DateTime(timezone=True), nullable=False)
    outcome: Mapped[str] = mapped_column("outcome", String(12), nullable=False, default="PENDING")
    resolvedAt: Mapped[datetime | None] = mapped_column("resolved_at", DateTime(timezone=True), nullable=True)
    isLatest: Mapped[bool] = mapped_column("is_latest", Boolean, nullable=False, default=True)


class SuggestionMemory(BaseEntity):
    """Compressed vector memory of past suggestions. PENDING entries are never shown to the AI."""

    __tablename__ = "suggestion_memories"

    suggestionId: Mapped[int | None] = mapped_column("suggestion_id", BigInteger, nullable=True)
    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False)
    direction: Mapped[str] = mapped_column("direction", String(10), nullable=False)
    dayType: Mapped[str | None] = mapped_column("day_type", String(20), nullable=True)
    hourBucket: Mapped[int] = mapped_column("hour_bucket", SmallInteger, nullable=False, default=0)
    summary: Mapped[str] = mapped_column("summary", Text, nullable=False)
    outcome: Mapped[str] = mapped_column("outcome", String(12), nullable=False, default="PENDING")
    embedding: Mapped[Any | None] = mapped_column("embedding", Vector(768), nullable=True)
    briefHash: Mapped[str | None] = mapped_column("brief_hash", String(64), nullable=True)
    lastAiAnswer: Mapped[dict[str, Any] | None] = mapped_column("last_ai_answer", JSONB, nullable=True)
