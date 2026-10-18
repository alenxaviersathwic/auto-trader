from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.crypto.secret_cipher import cipher
from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.core.pagination.page_result import PageResult
from app.modules.users.entity.upstox_config_entity import UpstoxConfig
from app.modules.users.entity.user_entity import User
from app.modules.users.repository.user_repository import UserRepository
from app.modules.users.schema.user_schema import (
    RedirectUrlResponse,
    UpstoxConfigResponse,
    UserCreateRequest,
    UserResponse,
    UserSearchFilter,
    UserUpdateRequest,
)
from app.modules.users.service.upstox_service import UpstoxService


class UserService:
    """Business service orchestrating User and Upstox configuration lifecycle."""

    def __init__(
        self,
        user_repository: UserRepository | None = None,
        upstox_service: UpstoxService | None = None,
    ):
        self.repo = user_repository or UserRepository()
        self.upstox_service = upstox_service or UpstoxService()

    @staticmethod
    def to_user_response(user: User) -> UserResponse:
        """Transforms User entity into clean UserResponse envelope payload."""
        upstox_resp = None
        if user.upstoxConfig:
            cfg = user.upstoxConfig
            upstox_resp = UpstoxConfigResponse(
                apiKey=cfg.apiKey or "",
                mobile=cfg.mobile or "",
                hasApiSecret=bool(cfg.apiSecretEnc),
                hasPin=bool(cfg.pinEnc),
                hasTotpSecret=bool(cfg.totpSecretEnc),
                redirectUri=cfg.redirectUri or "",
                autoAuthEnabled=cfg.autoAuthEnabled,
                authStatus=cfg.authStatus or "NEVER",
                tokenExpiresAt=cfg.tokenExpiresAt,
                lastAuthAt=cfg.lastAuthAt,
                lastError=cfg.lastError,
                upstoxUserId=cfg.upstoxUserId,
                profileName=cfg.profileName,
                email=cfg.email,
            )

        return UserResponse(
            id=user.id,
            name=user.name,
            isDefault=user.isDefault,
            status=user.status.name,
            createdAt=user.createdAt,
            upstox=upstox_resp,
        )

    async def create_user(
        self,
        session: AsyncSession,
        request: UserCreateRequest,
        base_url: str,
    ) -> UserResponse:
        """
        Creates a new user and initial Upstox config.
        First active user automatically becomes default.
        Generates system redirectUri upon creation.
        """
        # Validate unique name among active users
        existing = await self.repo.get_by_name(session, request.name.strip())
        if existing:
            raise ConflictException(
                message=f"A user with name '{request.name.strip()}' already exists",
                error={"field": "name", "code": "USER_NAME_ALREADY_EXISTS"},
            )

        # Check if first active user
        active_count = await self.repo.count_active_users(session)
        is_first = active_count == 0

        # Encrypt secrets
        api_secret_enc = cipher.encrypt(request.apiSecret) if request.apiSecret else ""
        pin_enc = cipher.encrypt(request.pin) if request.pin else ""
        totp_secret_enc = cipher.encrypt(request.totpSecret) if request.totpSecret else ""

        # Create user
        user = User(
            name=request.name.strip(),
            isDefault=is_first,
            status=EntityStatus.ACTIVE,
        )
        await self.repo.save_user(session, user)

        # Generate system redirectUri
        clean_base = base_url.rstrip("/")
        redirect_uri = f"{clean_base}/api/v1/upstox/callback/{user.id}"

        # Create Upstox config
        upstox_config = UpstoxConfig(
            userId=user.id,
            apiKey=request.apiKey.strip() if request.apiKey else "",
            apiSecretEnc=api_secret_enc,
            mobile=request.mobile.strip() if request.mobile else "",
            pinEnc=pin_enc,
            totpSecretEnc=totp_secret_enc,
            redirectUri=redirect_uri,
            autoAuthEnabled=request.autoAuthEnabled,
            authStatus="NEVER",
            status=EntityStatus.ACTIVE,
        )
        user.upstoxConfig = upstox_config
        session.add(upstox_config)
        await session.flush()
        await session.commit()
        await session.refresh(user)

        return self.to_user_response(user)

    async def search_users(
        self,
        session: AsyncSession,
        filter_obj: UserSearchFilter,
    ) -> PageResult[UserResponse]:
        """Executes paged search for users."""
        if filter_obj.dateFilter:
            if (
                filter_obj.dateFilter.from_ is not None
                and filter_obj.dateFilter.to is not None
                and filter_obj.dateFilter.from_ > filter_obj.dateFilter.to
            ):
                raise ValidationException("Date filter 'from' cannot be after 'to'")

        page_result = await self.repo.search(session, filter_obj)
        user_responses = [self.to_user_response(u) for u in page_result.list]

        return PageResult(
            list=user_responses,
            page=page_result.page,
            limit=page_result.limit,
            totalPages=page_result.totalPages,
            totalItems=page_result.totalItems,
        )

    async def get_user_by_id(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> UserResponse:
        """Retrieves user by id."""
        user = await self.repo.get_by_id(session, user_id, status=None)
        if not user:
            raise NotFoundException(message=f"User with ID {user_id} not found")
        return self.to_user_response(user)

    async def get_default_user(
        self,
        session: AsyncSession,
    ) -> UserResponse | None:
        """Retrieves current default user or None."""
        user = await self.repo.get_default_user(session)
        if not user:
            return None
        return self.to_user_response(user)

    async def update_user(
        self,
        session: AsyncSession,
        user_id: int,
        request: UserUpdateRequest,
    ) -> UserResponse:
        """
        Updates user details.
        Blank/omitted secret fields retain stored values.
        """
        user = await self.repo.get_by_id(session, user_id)
        if not user:
            raise NotFoundException(message=f"User with ID {user_id} not found")

        # Update name if changed
        if request.name is not None and request.name.strip() != user.name:
            existing = await self.repo.get_by_name(session, request.name.strip())
            if existing and existing.id != user.id:
                raise ConflictException(
                    message=f"A user with name '{request.name.strip()}' already exists",
                    error={"field": "name", "code": "USER_NAME_ALREADY_EXISTS"},
                )
            user.name = request.name.strip()

        # Update Upstox credentials
        cfg = user.upstoxConfig
        if cfg:
            if request.apiKey is not None:
                cfg.apiKey = request.apiKey.strip()
            if request.mobile is not None:
                cfg.mobile = request.mobile.strip()
            if request.autoAuthEnabled is not None:
                cfg.autoAuthEnabled = request.autoAuthEnabled

            # Blank secrets keep the stored value!
            if request.apiSecret and request.apiSecret.strip():
                cfg.apiSecretEnc = cipher.encrypt(request.apiSecret.strip())
            if request.pin and request.pin.strip():
                cfg.pinEnc = cipher.encrypt(request.pin.strip())
            if request.totpSecret and request.totpSecret.strip():
                cfg.totpSecretEnc = cipher.encrypt(request.totpSecret.strip())

        await session.flush()
        await session.commit()
        await session.refresh(user)
        return self.to_user_response(user)

    async def delete_user(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> None:
        """
        Soft deletes user.
        Blocked for the default user while others exist.
        """
        user = await self.repo.get_by_id(session, user_id)
        if not user:
            raise NotFoundException(message=f"User with ID {user_id} not found")

        if user.isDefault:
            active_count = await self.repo.count_active_users(session)
            if active_count > 1:
                raise ValidationException(
                    message=(
                        "Cannot delete the default user while other users exist. "
                        "Make another user default first."
                    ),
                    error={"code": "CANNOT_DELETE_DEFAULT_USER"},
                )

        await self.repo.soft_delete(session, user)
        await session.commit()

    async def set_default_user(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> UserResponse:
        """Sets target user as the single default active user."""
        user = await self.repo.get_by_id(session, user_id)
        if not user:
            raise NotFoundException(message=f"User with ID {user_id} not found")

        await self.repo.set_as_default(session, user_id)
        await session.commit()
        await session.refresh(user)
        return self.to_user_response(user)

    async def update_auto_auth(
        self,
        session: AsyncSession,
        user_id: int,
        enabled: bool,
    ) -> UserResponse:
        """Toggles auto-auth status for user."""
        user = await self.repo.get_by_id(session, user_id)
        if not user:
            raise NotFoundException(message=f"User with ID {user_id} not found")

        if user.upstoxConfig:
            user.upstoxConfig.autoAuthEnabled = enabled
            await session.flush()
            await session.commit()
            await session.refresh(user)

        return self.to_user_response(user)

    async def get_redirect_url(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> RedirectUrlResponse:
        """Returns the system redirect URL for registering in Upstox developer console."""
        user = await self.repo.get_by_id(session, user_id)
        if not user:
            raise NotFoundException(message=f"User with ID {user_id} not found")

        redirect_uri = user.upstoxConfig.redirectUri if user.upstoxConfig else ""
        return RedirectUrlResponse(redirectUri=redirect_uri)

    async def authenticate_user(
        self,
        session: AsyncSession,
        user_id: int,
    ) -> UserResponse:
        """Triggers manual / immediate authentication test for the user."""
        user = await self.repo.get_by_id(session, user_id)
        if not user:
            raise NotFoundException(message=f"User with ID {user_id} not found")

        if not user.upstoxConfig:
            raise ValidationException(message="User does not have an Upstox configuration")

        await self.upstox_service.authenticate(user.upstoxConfig)
        await session.flush()
        await session.commit()
        await session.refresh(user)

        return self.to_user_response(user)

    async def handle_oauth_callback(
        self,
        session: AsyncSession,
        user_id: int,
        code: str | None,
    ) -> dict[str, Any]:
        """Handles public OAuth callback from Upstox authorization redirect."""
        user = await self.repo.get_by_id(session, user_id)
        if not user or not user.upstoxConfig:
            raise NotFoundException(message=f"User with ID {user_id} not found")

        res = await self.upstox_service.exchange_code(user.upstoxConfig, code or "")
        await session.flush()
        await session.commit()
        return res
