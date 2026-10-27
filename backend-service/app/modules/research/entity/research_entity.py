from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    Integer,
    Numeric,
    SmallInteger,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.core.db.base_entity import BaseEntity


class ResearchEntity(BaseEntity):
    """
    Primary Research Entity for trading underlyings (indices and commodities).
    Updated in-place whenever the research pipeline evaluates new market intelligence.
    """

    __tablename__ = "research_candidates"

    runId: Mapped[Optional[int]] = mapped_column("run_id", BigInteger, nullable=True)
    underlyingType: Mapped[str] = mapped_column("underlying_type", String(10), nullable=False)
    underlyingCode: Mapped[str] = mapped_column("underlying_code", String(30), nullable=False, unique=True)
    newsStatus: Mapped[str] = mapped_column("news_status", String(20), nullable=False)
    suggested: Mapped[bool] = mapped_column("suggested", Boolean, nullable=False, default=False)
    rank: Mapped[Optional[int]] = mapped_column("rank", SmallInteger, nullable=True)
    direction: Mapped[Optional[str]] = mapped_column("direction", String(10), nullable=True)
    bearishWatch: Mapped[bool] = mapped_column("bearish_watch", Boolean, nullable=False, default=False)
    score: Mapped[Optional[float]] = mapped_column("score", Numeric(5, 1), nullable=True)
    opportunityScore: Mapped[Optional[float]] = mapped_column("opportunity_score", Numeric(5, 1), nullable=True)
    scoreLabel: Mapped[Optional[str]] = mapped_column("score_label", String(8), nullable=True)
    positiveWeight: Mapped[float] = mapped_column("positive_weight", Numeric(8, 3), nullable=False, default=0.0)
    negativeWeight: Mapped[float] = mapped_column("negative_weight", Numeric(8, 3), nullable=False, default=0.0)
    negativeShare: Mapped[float] = mapped_column("negative_share", Numeric(4, 3), nullable=False, default=0.0)
    positiveClaims: Mapped[int] = mapped_column("positive_claims", Integer, nullable=False, default=0)
    negativeClaims: Mapped[int] = mapped_column("negative_claims", Integer, nullable=False, default=0)
    materialNegatives: Mapped[List[int]] = mapped_column("material_negatives", JSONB, nullable=False, default=list)
    independentSources: Mapped[int] = mapped_column("independent_sources", Integer, nullable=False, default=0)
    freshArticleCount: Mapped[int] = mapped_column("fresh_article_count", Integer, nullable=False, default=0)
    newestArticleAt: Mapped[Optional[datetime]] = mapped_column("newest_article_at", DateTime(timezone=True), nullable=True)
    oldestArticleAt: Mapped[Optional[datetime]] = mapped_column("oldest_article_at", DateTime(timezone=True), nullable=True)
    flags: Mapped[List[str]] = mapped_column("flags", JSONB, nullable=False, default=list)
    reasons: Mapped[List[str]] = mapped_column("reasons", JSONB, nullable=False, default=list)
    thesis: Mapped[Optional[str]] = mapped_column("thesis", Text, nullable=True)
    supportingPoints: Mapped[List[Dict[str, Any]]] = mapped_column("supporting_points", JSONB, nullable=False, default=list)
    watchItems: Mapped[List[Dict[str, Any]]] = mapped_column("watch_items", JSONB, nullable=False, default=list)
    latestNews: Mapped[List[Dict[str, Any]]] = mapped_column("latest_news", JSONB, nullable=False, default=list)
    affectNews: Mapped[List[Dict[str, Any]]] = mapped_column("affect_news", JSONB, nullable=False, default=list)
    neutralNews: Mapped[List[Dict[str, Any]]] = mapped_column("neutral_news", JSONB, nullable=False, default=list)
    blogSummary: Mapped[Optional[str]] = mapped_column("blog_summary", Text, nullable=True)
    citations: Mapped[List[int]] = mapped_column("citations", JSONB, nullable=False, default=list)
    briefEmbedding: Mapped[Optional[Any]] = mapped_column("brief_embedding", Vector(768), nullable=True)

    @property
    def scope(self) -> str:
        return self.underlyingType

    @scope.setter
    def scope(self, val: str) -> None:
        self.underlyingType = val

    @property
    def item(self) -> str:
        return self.underlyingCode

    @item.setter
    def item(self, val: str) -> None:
        self.underlyingCode = val

    @property
    def latestScore(self) -> Optional[float]:
        return float(self.score) if self.score is not None else None


class ResearchRun(BaseEntity):
    """
    Research run tracking entity.
    """

    __tablename__ = "research_runs"

    scope: Mapped[List[str]] = mapped_column("scope", JSONB, nullable=False, default=list)
    triggerSource: Mapped[str] = mapped_column("trigger_source", String(20), nullable=False, default="MANUAL")
    triggeredBy: Mapped[Optional[str]] = mapped_column("triggered_by", String(100), nullable=True)
    state: Mapped[str] = mapped_column("state", String(20), nullable=False, default="QUEUED")
    resultKind: Mapped[Optional[str]] = mapped_column("result_kind", String(20), nullable=True)
    params: Mapped[Dict[str, Any]] = mapped_column("params", JSONB, nullable=False, default=dict)
    configVersion: Mapped[int] = mapped_column("config_version", Integer, nullable=False, default=1)
    currentNode: Mapped[Optional[str]] = mapped_column("current_node", String(50), nullable=True)
    progressPct: Mapped[int] = mapped_column("progress_pct", SmallInteger, nullable=False, default=0)
    stats: Mapped[Dict[str, Any]] = mapped_column("stats", JSONB, nullable=False, default=dict)
    resumable: Mapped[bool] = mapped_column("resumable", Boolean, nullable=False, default=False)
    threadId: Mapped[str] = mapped_column("thread_id", String(64), nullable=False)
    startedAt: Mapped[Optional[datetime]] = mapped_column("started_at", DateTime(timezone=True), nullable=True)
    finishedAt: Mapped[Optional[datetime]] = mapped_column("finished_at", DateTime(timezone=True), nullable=True)
    error: Mapped[Optional[str]] = mapped_column("error", Text, nullable=True)


# Aliases for compatibility
ResearchCandidate = ResearchEntity
