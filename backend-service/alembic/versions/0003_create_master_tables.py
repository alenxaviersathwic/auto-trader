"""Create tables for master chat module: conversations, messages, runs, tool calls, proposals, preferences, tool servers, policies, and configs

Revision ID: 0003_create_master_tables
Revises: 0002_create_strategies_and_rules
Create Date: 2026-10-22 11:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0003_create_master_tables"
down_revision: Union[str, None] = "0002_create_strategies_and_rules"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. master_conversations
    op.create_table(
        "master_conversations",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=150), nullable=False, server_default="New Conversation"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by_user_id", sa.BigInteger(), nullable=True),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_master_conversations_status", "master_conversations", ["status"])
    op.create_index("idx_master_conversations_last_msg", "master_conversations", ["last_message_at"])

    # 2. master_runs
    op.create_table(
        "master_runs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("user_message_id", sa.BigInteger(), nullable=True),
        sa.Column("state", sa.String(length=15), nullable=False, server_default="RUNNING"),
        sa.Column("intent", sa.String(length=25), nullable=True),
        sa.Column("thread_id", sa.String(length=60), nullable=False),
        sa.Column("iterations", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tool_call_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("clarification_round", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.String(length=500), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["master_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_master_runs_conversation_id", "master_runs", ["conversation_id"])
    op.create_index("idx_master_runs_state", "master_runs", ["state"])

    # 3. master_messages
    op.create_table(
        "master_messages",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("blocks", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("run_id", sa.BigInteger(), nullable=True),
        sa.Column("redacted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("model", sa.String(length=80), nullable=True),
        sa.Column("tokens_in", sa.Integer(), nullable=True),
        sa.Column("tokens_out", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["master_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["master_runs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_master_messages_conv_seq", "master_messages", ["conversation_id", "seq"])

    # 4. master_tool_calls
    op.create_table(
        "master_tool_calls",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("run_id", sa.BigInteger(), nullable=False),
        sa.Column("server_name", sa.String(length=60), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("tier", sa.String(length=10), nullable=False),
        sa.Column("arguments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("result_summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("call_status", sa.String(length=10), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["master_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_master_tool_calls_run_id", "master_tool_calls", ["run_id"])
    op.create_index("idx_master_tool_calls_tool_name", "master_tool_calls", ["tool_name"])

    # 5. master_proposals
    op.create_table(
        "master_proposals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("conversation_id", sa.BigInteger(), nullable=False),
        sa.Column("message_id", sa.BigInteger(), nullable=True),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("target_type", sa.String(length=30), nullable=True),
        sa.Column("target_code", sa.String(length=100), nullable=True),
        sa.Column("user_text", sa.Text(), nullable=False),
        sa.Column("back_translation", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("diff", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("complications", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("assumptions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("structure_analysis", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("validation", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("proposal_status", sa.String(length=15), nullable=False, server_default="PENDING"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirm_mode", sa.String(length=25), nullable=True),
        sa.Column("result_refs", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("failure_reason", sa.String(length=500), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["master_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["message_id"], ["master_messages.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_master_proposals_conversation_id", "master_proposals", ["conversation_id"])
    op.create_index("idx_master_proposals_status", "master_proposals", ["proposal_status"])

    # 6. master_preferences
    op.create_table(
        "master_preferences",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("key", sa.String(length=80), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("source_message_id", sa.BigInteger(), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_master_preferences_key_active",
        "master_preferences",
        ["key"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 7. master_tool_servers
    op.create_table(
        "master_tool_servers",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("transport", sa.String(length=10), nullable=False, server_default="HTTP"),
        sa.Column("url", sa.String(length=300), nullable=True),
        sa.Column("auth_ref", sa.String(length=60), nullable=True),
        sa.Column("tier_cap", sa.String(length=10), nullable=False, server_default="PROPOSE"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=300), nullable=True),
        sa.Column("tool_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_master_tool_servers_name_active",
        "master_tool_servers",
        ["name"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 8. master_tool_policies
    op.create_table(
        "master_tool_policies",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("server_name", sa.String(length=60), nullable=False),
        sa.Column("tool_name", sa.String(length=80), nullable=False),
        sa.Column("tier", sa.String(length=10), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_approve", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_master_tool_policies_server_tool_active",
        "master_tool_policies",
        ["server_name", "tool_name"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 9. master_configs
    op.create_table(
        "master_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("config_key", sa.String(length=80), nullable=False),
        sa.Column("config_value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_master_configs_key_active",
        "master_configs",
        ["config_key"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )


def downgrade() -> None:
    op.drop_table("master_configs")
    op.drop_table("master_tool_policies")
    op.drop_table("master_tool_servers")
    op.drop_table("master_preferences")
    op.drop_table("master_proposals")
    op.drop_table("master_tool_calls")
    op.drop_table("master_messages")
    op.drop_table("master_runs")
    op.drop_table("master_conversations")
