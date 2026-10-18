from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db.base_entity import BaseEntity

if TYPE_CHECKING:
    from app.modules.users.entity.user_entity import User


class UpstoxConfig(BaseEntity):
    """
    Upstox configuration and credentials entity.
    One-to-one associated with User.
    Extends BaseEntity (id, createdAt, status).
    Sensitive values are stored encrypted via SecretCipher.
    """

    __tablename__ = "upstox_configs"

    userId: Mapped[int] = mapped_column(
        "user_id",
        BigInteger,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    apiKey: Mapped[str] = mapped_column("api_key", String(100), nullable=False, default="")
    apiSecretEnc: Mapped[str] = mapped_column("api_secret_enc", Text, nullable=False, default="")
    mobile: Mapped[str] = mapped_column("mobile", String(15), nullable=False, default="")
    pinEnc: Mapped[str] = mapped_column("pin_enc", Text, nullable=False, default="")
    totpSecretEnc: Mapped[str] = mapped_column("totp_secret_enc", Text, nullable=False, default="")
    accessTokenEnc: Mapped[str | None] = mapped_column("access_token_enc", Text, nullable=True)
    redirectUri: Mapped[str] = mapped_column(
        "redirect_uri", String(300), nullable=False, default=""
    )
    autoAuthEnabled: Mapped[bool] = mapped_column(
        "auto_auth_enabled", Boolean, nullable=False, default=True
    )
    tokenExpiresAt: Mapped[datetime | None] = mapped_column(
        "token_expires_at", DateTime(timezone=True), nullable=True
    )
    authStatus: Mapped[str] = mapped_column(
        "auth_status", String(20), nullable=False, default="NEVER"
    )
    lastAuthAt: Mapped[datetime | None] = mapped_column(
        "last_auth_at", DateTime(timezone=True), nullable=True
    )
    lastError: Mapped[str | None] = mapped_column("last_error", String(500), nullable=True)
    upstoxUserId: Mapped[str | None] = mapped_column("upstox_user_id", String(50), nullable=True)
    profileName: Mapped[str | None] = mapped_column("profile_name", String(100), nullable=True)
    email: Mapped[str | None] = mapped_column("email", String(150), nullable=True)

    # Reverse relationship
    user: Mapped["User"] = relationship("User", back_populates="upstoxConfig")

    __table_args__ = (
        Index(
            "ix_upstox_configs_user_id_active",
            "user_id",
            unique=True,
            postgresql_where=text("status = 1"),
        ),
    )
