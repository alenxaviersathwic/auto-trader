"""Create tables for strategies, rules, registries, performance, health and imports

Revision ID: 0002_create_strategies_and_rules
Revises: 0001_create_users
Create Date: 2026-10-20 11:30:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0002_create_strategies_and_rules"
down_revision: Union[str, None] = "0001_create_users"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. registry_items
    op.create_table(
        "registry_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("registry_type", sa.String(length=30), nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("kind", sa.String(length=10), nullable=False, server_default="BUILT_IN"),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("schema", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("expression", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("handler_key", sa.String(length=80), nullable=True),
        sa.Column("executable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("requires", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_registry_items_type_code_active",
        "registry_items",
        ["registry_type", "code"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 2. strategies
    op.create_table(
        "strategies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("structure", sa.String(length=30), nullable=True),
        sa.Column("bias", sa.String(length=10), nullable=True),
        sa.Column("option_side", sa.String(length=5), nullable=True),
        sa.Column("markets", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("underlying_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("exchange", sa.String(length=10), nullable=True),
        sa.Column("trading_modes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("execution_modes", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("timeframe", sa.String(length=10), nullable=True),
        sa.Column("definition_format", sa.String(length=10), nullable=False, server_default="RULE_TREE"),
        sa.Column("executable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("lifecycle_status", sa.String(length=12), nullable=False, server_default="DRAFT"),
        sa.Column("health", sa.String(length=10), nullable=False, server_default="UNKNOWN"),
        sa.Column("health_override", sa.String(length=10), nullable=True),
        sa.Column("health_override_reason", sa.String(length=255), nullable=True),
        sa.Column("health_override_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_status", sa.String(length=15), nullable=False, server_default="UNTESTED"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("risk_profile", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("references", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("risk_notes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("how_it_works", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("tags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("attributes", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("review_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("current_version_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategies_code_active",
        "strategies",
        ["code"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 3. strategy_versions
    op.create_table(
        "strategy_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("change_note", sa.String(length=300), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_strategy_versions_strat_ver_active",
        "strategy_versions",
        ["strategy_id", "version_no"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 4. strategy_rules
    op.create_table(
        "strategy_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_version_id", sa.BigInteger(), nullable=False),
        sa.Column("rule_id", sa.BigInteger(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("param_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["strategy_version_id"], ["strategy_versions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 5. rules
    op.create_table(
        "rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=80), nullable=False),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("rule_kind", sa.String(length=15), nullable=False),
        sa.Column("rule_type", sa.String(length=25), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=True),
        sa.Column("priority", sa.String(length=8), nullable=False, server_default="MEDIUM"),
        sa.Column("applies_to", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("condition_text", sa.Text(), nullable=False),
        sa.Column("current_version_id", sa.BigInteger(), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("review_by", sa.Date(), nullable=True),
        sa.Column("executable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("review_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("provenance", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rules_code_active",
        "rules",
        ["code"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 6. rule_versions
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("rule_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("content", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("change_note", sa.String(length=300), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["rules.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_rule_versions_rule_ver_active",
        "rule_versions",
        ["rule_id", "version_no"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 7. strategy_performance_snapshots
    op.create_table(
        "strategy_performance_snapshots",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.BigInteger(), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=15), nullable=False),
        sa.Column("domain", sa.String(length=10), nullable=False, server_default="UNKNOWN"),
        sa.Column("period_from", sa.Date(), nullable=True),
        sa.Column("period_to", sa.Date(), nullable=True),
        sa.Column("as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("winning_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("losing_trades", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("win_rate_pct", sa.Numeric(precision=6, scale=2), nullable=False, server_default="0"),
        sa.Column("net_pnl", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("profit_factor", sa.Numeric(precision=8, scale=2), nullable=False, server_default="0"),
        sa.Column("max_drawdown", sa.Numeric(precision=14, scale=2), nullable=False, server_default="0"),
        sa.Column("legacy_health", sa.String(length=10), nullable=True),
        sa.Column("reliability_flags", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 8. health_policies
    op.create_table(
        "health_policies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=60), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("scope", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'\"ALL\"'::jsonb")),
        sa.Column("params", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_health_policies_code_active",
        "health_policies",
        ["code"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 9. strategy_health_events
    op.create_table(
        "strategy_health_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("strategy_id", sa.BigInteger(), nullable=False),
        sa.Column("from_health", sa.String(length=10), nullable=False),
        sa.Column("to_health", sa.String(length=10), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("snapshot_id", sa.BigInteger(), nullable=True),
        sa.Column("triggered_by", sa.String(length=10), nullable=False, server_default="POLICY"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["strategy_id"], ["strategies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # 10. import_batches
    op.create_table(
        "import_batches",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("source_format", sa.String(length=20), nullable=False),
        sa.Column("mode", sa.String(length=10), nullable=False, server_default="SKIP"),
        sa.Column("dry_run", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("total_items", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("skipped_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("errors", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    op.drop_table("import_batches")
    op.drop_table("strategy_health_events")
    op.drop_index("ix_health_policies_code_active", table_name="health_policies", postgresql_where=sa.text("status = 1"))
    op.drop_table("health_policies")
    op.drop_table("strategy_performance_snapshots")
    op.drop_index("ix_rule_versions_rule_ver_active", table_name="rule_versions", postgresql_where=sa.text("status = 1"))
    op.drop_table("rule_versions")
    op.drop_index("ix_rules_code_active", table_name="rules", postgresql_where=sa.text("status = 1"))
    op.drop_table("rules")
    op.drop_table("strategy_rules")
    op.drop_index("ix_strategy_versions_strat_ver_active", table_name="strategy_versions", postgresql_where=sa.text("status = 1"))
    op.drop_table("strategy_versions")
    op.drop_index("ix_strategies_code_active", table_name="strategies", postgresql_where=sa.text("status = 1"))
    op.drop_table("strategies")
    op.drop_index("ix_registry_items_type_code_active", table_name="registry_items", postgresql_where=sa.text("status = 1"))
    op.drop_table("registry_items")
