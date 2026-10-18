"""Create users and upstox_configs tables with BaseEntity and partial indexes

Revision ID: 0001_create_users
Revises: 
Create Date: 2026-10-18 23:10:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0001_create_users"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create users table
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial unique index on active user name
    op.create_index(
        "ix_users_name_active",
        "users",
        ["name"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )

    # 2. Create upstox_configs table
    op.create_table(
        "upstox_configs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("api_key", sa.String(length=100), nullable=False, server_default=""),
        sa.Column("api_secret_enc", sa.Text(), nullable=False, server_default=""),
        sa.Column("mobile", sa.String(length=15), nullable=False, server_default=""),
        sa.Column("pin_enc", sa.Text(), nullable=False, server_default=""),
        sa.Column("totp_secret_enc", sa.Text(), nullable=False, server_default=""),
        sa.Column("access_token_enc", sa.Text(), nullable=True),
        sa.Column("redirect_uri", sa.String(length=300), nullable=False, server_default=""),
        sa.Column(
            "auto_auth_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column("token_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("auth_status", sa.String(length=20), nullable=False, server_default="NEVER"),
        sa.Column("last_auth_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.Column("upstox_user_id", sa.String(length=50), nullable=True),
        sa.Column("profile_name", sa.String(length=100), nullable=True),
        sa.Column("email", sa.String(length=150), nullable=True),
        sa.Column("status", sa.SmallInteger(), nullable=False, server_default=sa.text("1")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    # Partial unique index on active user's config
    op.create_index(
        "ix_upstox_configs_user_id_active",
        "upstox_configs",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("status = 1"),
    )


def downgrade() -> None:
    op.drop_index(
        "ix_upstox_configs_user_id_active",
        table_name="upstox_configs",
        postgresql_where=sa.text("status = 1"),
    )
    op.drop_table("upstox_configs")
    op.drop_index(
        "ix_users_name_active",
        table_name="users",
        postgresql_where=sa.text("status = 1"),
    )
    op.drop_table("users")
