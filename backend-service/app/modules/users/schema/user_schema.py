from datetime import datetime

from pydantic import BaseModel, Field

from app.core.filter.base_filter import BaseFilter


class UserCreateRequest(BaseModel):
    """Payload for creating a user along with Upstox credentials."""

    name: str = Field(..., min_length=1, max_length=100, description="Display / account name")
    apiKey: str = Field(default="", max_length=100, description="Upstox API Key")
    apiSecret: str = Field(default="", description="Upstox API Secret (will be encrypted)")
    mobile: str = Field(default="", max_length=15, description="Registered mobile number")
    pin: str = Field(default="", description="Upstox 6-digit login PIN (will be encrypted)")
    totpSecret: str = Field(default="", description="TOTP secret key (will be encrypted)")
    autoAuthEnabled: bool = Field(default=True, description="Enable automated daily authentication")


class UserUpdateRequest(BaseModel):
    """
    Payload for updating user & Upstox credentials.
    Blank/null secret fields retain their existing encrypted values.
    """

    name: str | None = Field(default=None, min_length=1, max_length=100)
    apiKey: str | None = Field(default=None, max_length=100)
    apiSecret: str | None = Field(
        default=None, description="Provide new secret to update, or blank to keep existing"
    )
    mobile: str | None = Field(default=None, max_length=15)
    pin: str | None = Field(
        default=None, description="Provide new PIN to update, or blank to keep existing"
    )
    totpSecret: str | None = Field(
        default=None, description="Provide new TOTP secret to update, or blank to keep existing"
    )
    autoAuthEnabled: bool | None = Field(default=None)


class UserAutoAuthPatchRequest(BaseModel):
    """Payload for toggling auto authentication."""

    enabled: bool = Field(..., description="Toggle auto-auth status")


class UpstoxConfigResponse(BaseModel):
    """Upstox configuration response. Plaintext secrets are never returned."""

    apiKey: str = ""
    mobile: str = ""
    hasApiSecret: bool = False
    hasPin: bool = False
    hasTotpSecret: bool = False
    redirectUri: str = ""
    autoAuthEnabled: bool = True
    authStatus: str = "NEVER"
    tokenExpiresAt: datetime | None = None
    lastAuthAt: datetime | None = None
    lastError: str | None = None
    upstoxUserId: str | None = None
    profileName: str | None = None
    email: str | None = None


class UserResponse(BaseModel):
    """Standard user response."""

    id: int
    name: str
    isDefault: bool
    status: str
    createdAt: datetime
    upstox: UpstoxConfigResponse | None = None


class UserSearchFilter(BaseFilter):
    """Search filter for users."""

    authStatus: str | None = None
    isDefault: bool | None = None


class RedirectUrlResponse(BaseModel):
    """Redirect URL response."""

    redirectUri: str


# Type alias for default user response (or null)
DefaultUserResponse = UserResponse | None
