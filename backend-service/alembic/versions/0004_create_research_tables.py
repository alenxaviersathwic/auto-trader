"""Create tables for research module: underlyings, sources, risk terms, runs, documents, chunks, claims, candidates, and config

Revision ID: 0004_create_research_tables
Revises: 0003_create_master_tables
Create Date: 2026-10-22 16:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0004_create_research_tables"
down_revision: Union[str, None] = "0003_create_master_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 0. Ensure pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    # 1. research_underlyings
    op.create_table(
        "research_underlyings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=30), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("underlying_type", sa.String(length=10), nullable=False),
        sa.Column("group_name", sa.String(length=30), nullable=False),
        sa.Column("exchange", sa.String(length=10), nullable=False),
        sa.Column("aliases", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("keywords", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("heavyweights", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_underlyings_status", "research_underlyings", ["status"])
    op.create_index("idx_research_underlyings_type", "research_underlyings", ["underlying_type"])
    op.execute("CREATE UNIQUE INDEX uq_research_underlyings_code ON research_underlyings (code) WHERE status = 1;")

    # 2. research_sources
    op.create_table(
        "research_sources",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=10), nullable=False),
        sa.Column("base_url", sa.String(length=300), nullable=False),
        sa.Column("feed_url", sa.String(length=400), nullable=True),
        sa.Column("credibility_weight", sa.Numeric(precision=3, scale=2), nullable=False, server_default="0.60"),
        sa.Column("applies_to_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("applies_to_groups", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_fetch_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("ok_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_sources_status", "research_sources", ["status"])
    op.create_index("idx_research_sources_type", "research_sources", ["source_type"])

    # 3. research_risk_terms
    op.create_table(
        "research_risk_terms",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("term", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=30), nullable=False),
        sa.Column("default_severity", sa.SmallInteger(), nullable=False, server_default="3"),
        sa.Column("applies_to_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_risk_terms_status", "research_risk_terms", ["status"])
    op.execute("CREATE UNIQUE INDEX uq_research_risk_terms_term ON research_risk_terms (term) WHERE status = 1;")

    # 4. research_runs
    op.create_table(
        "research_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default='["INDEX","COMMODITY"]'),
        sa.Column("trigger_source", sa.String(length=10), nullable=False, server_default="UI"),
        sa.Column("triggered_by", sa.String(length=60), nullable=True),
        sa.Column("state", sa.String(length=12), nullable=False, server_default="QUEUED"),
        sa.Column("result_kind", sa.String(length=20), nullable=True),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("config_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("current_node", sa.String(length=40), nullable=True),
        sa.Column("progress_pct", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stats", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("resumable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("thread_id", sa.String(length=60), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_runs_status", "research_runs", ["status"])
    op.create_index("idx_research_runs_state", "research_runs", ["state"])
    op.create_index("idx_research_runs_created_at", "research_runs", ["created_at"])

    # 5. research_run_events
    op.create_table(
        "research_run_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("node", sa.String(length=40), nullable=True),
        sa.Column("level", sa.String(length=10), nullable=False, server_default="INFO"),
        sa.Column("message", sa.String(length=500), nullable=False),
        sa.Column("data", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_run_events_run_id", "research_run_events", ["run_id", "seq"])

    # 6. research_queries
    op.create_table(
        "research_queries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("underlying_code", sa.String(length=30), nullable=True),
        sa.Column("query_text", sa.String(length=500), nullable=False),
        sa.Column("provider", sa.String(length=30), nullable=False),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("planned_by", sa.String(length=20), nullable=False, server_default="TEMPLATE"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_queries_run_id", "research_queries", ["run_id"])

    # 7. research_documents
    op.create_table(
        "research_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("url_hash", sa.String(length=64), nullable=False),
        sa.Column("url", sa.String(length=1000), nullable=False),
        sa.Column("canonical_url", sa.String(length=1000), nullable=False),
        sa.Column("domain", sa.String(length=120), nullable=False),
        sa.Column("source_id", sa.BigInteger(), nullable=True),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("language", sa.String(length=8), nullable=True, server_default="en"),
        sa.Column("fetch_status", sa.String(length=10), nullable=False, server_default="OK"),
        sa.Column("duplicate_of_id", sa.BigInteger(), nullable=True),
        sa.Column("first_seen_run_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_documents_domain", "research_documents", ["domain"])
    op.create_index("idx_research_documents_published_at", "research_documents", ["published_at"])
    op.execute("CREATE UNIQUE INDEX uq_research_documents_url_hash ON research_documents (url_hash) WHERE status = 1;")

    # 8. research_run_documents
    op.create_table(
        "research_run_documents",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("research_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("underlying_code", sa.String(length=30), nullable=True),
        sa.Column("query_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_run_docs_run_id", "research_run_documents", ["run_id", "underlying_code"])

    # 9. research_chunks
    op.create_table(
        "research_chunks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("research_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(768), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_chunks_doc_id", "research_chunks", ["document_id"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_research_chunks_embedding ON research_chunks USING hnsw (embedding vector_cosine_ops);")

    # 10. research_claims
    op.create_table(
        "research_claims",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.BigInteger(), sa.ForeignKey("research_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("chunk_id", sa.BigInteger(), nullable=True),
        sa.Column("underlying_code", sa.String(length=30), nullable=False),
        sa.Column("channel", sa.String(length=12), nullable=False, server_default="DIRECT"),
        sa.Column("stance", sa.String(length=10), nullable=False),
        sa.Column("magnitude", sa.SmallInteger(), nullable=False, server_default="1"),
        sa.Column("confidence", sa.Numeric(precision=3, scale=2), nullable=False, server_default="0.80"),
        sa.Column("horizon", sa.String(length=10), nullable=False, server_default="DAYS"),
        sa.Column("catalyst", sa.String(length=20), nullable=False, server_default="OTHER"),
        sa.Column("is_risk_event", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("event_date", sa.Date(), nullable=True),
        sa.Column("statement", sa.String(length=300), nullable=False),
        sa.Column("quote", sa.String(length=500), nullable=False),
        sa.Column("quote_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("origin", sa.String(length=10), nullable=False, server_default="EXTRACT"),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("extraction_version", sa.String(length=30), nullable=False, server_default="v1.0"),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_claims_code", "research_claims", ["underlying_code", "stance"])
    op.create_index("idx_research_claims_doc", "research_claims", ["document_id"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_research_claims_embedding ON research_claims USING hnsw (embedding vector_cosine_ops);")

    # 11. research_candidates
    op.create_table(
        "research_candidates",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), sa.ForeignKey("research_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("underlying_type", sa.String(length=10), nullable=False),
        sa.Column("underlying_code", sa.String(length=30), nullable=False),
        sa.Column("news_status", sa.String(length=20), nullable=False),
        sa.Column("suggested", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("rank", sa.SmallInteger(), nullable=True),
        sa.Column("direction", sa.String(length=10), nullable=True),
        sa.Column("bearish_watch", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("score", sa.Numeric(precision=5, scale=1), nullable=True),
        sa.Column("score_label", sa.String(length=8), nullable=True),
        sa.Column("positive_weight", sa.Numeric(precision=8, scale=3), nullable=False, server_default="0.000"),
        sa.Column("negative_weight", sa.Numeric(precision=8, scale=3), nullable=False, server_default="0.000"),
        sa.Column("negative_share", sa.Numeric(precision=4, scale=3), nullable=False, server_default="0.000"),
        sa.Column("positive_claims", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("negative_claims", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("material_negatives", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("independent_sources", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("fresh_article_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("newest_article_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("oldest_article_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("reasons", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("thesis", sa.Text(), nullable=True),
        sa.Column("supporting_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("watch_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("citations", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="[]"),
        sa.Column("brief_embedding", Vector(768), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_candidates_run_id", "research_candidates", ["run_id", "underlying_type"])
    op.create_index("idx_research_candidates_code", "research_candidates", ["underlying_code"])
    op.execute("CREATE INDEX IF NOT EXISTS idx_research_candidates_brief_embedding ON research_candidates USING hnsw (brief_embedding vector_cosine_ops);")

    # 12. research_config
    op.create_table(
        "research_config",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("weights", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("thresholds", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("limits", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default="{}"),
        sa.Column("note", sa.String(length=200), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_config_version", "research_config", ["version"])


def downgrade() -> None:
    op.drop_table("research_config")
    op.drop_table("research_candidates")
    op.drop_table("research_claims")
    op.drop_table("research_chunks")
    op.drop_table("research_run_documents")
    op.drop_table("research_documents")
    op.drop_table("research_queries")
    op.drop_table("research_run_events")
    op.drop_table("research_runs")
    op.drop_table("research_risk_terms")
    op.drop_table("research_sources")
    op.drop_table("research_underlyings")
