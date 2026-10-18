
from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.session import get_db
from app.core.pagination.page_result import PageResult
from app.core.response.api_response import ApiResponse
from app.core.response.response_helper import created, success
from app.modules.users.schema.user_schema import (
    RedirectUrlResponse,
    UserAutoAuthPatchRequest,
    UserCreateRequest,
    UserResponse,
    UserSearchFilter,
    UserUpdateRequest,
)
from app.modules.users.service.user_service import UserService

user_router = APIRouter(prefix="/users", tags=["Users"])
oauth_router = APIRouter(tags=["Upstox OAuth"])

_user_service = UserService()


@user_router.post(
    "",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Create user and Upstox configuration",
)
async def create_user(
    request: Request,
    payload: UserCreateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Creates a new user and associated Upstox configuration.
    The first active user automatically becomes default.
    Generates a system redirectUri for Upstox developer console.
    """
    base_url = str(request.base_url)
    user = await _user_service.create_user(session, payload, base_url=base_url)
    return created(data=user, message="User created successfully")


@user_router.post(
    "/search",
    response_model=ApiResponse[PageResult[UserResponse]],
    status_code=status.HTTP_200_OK,
    summary="Search users with pagination and filters",
)
async def search_users(
    filter_obj: UserSearchFilter,
    session: AsyncSession = Depends(get_db),
):
    """
    Paged listing of users supporting query search across name, upstoxUserId,
    and profileName, plus authStatus, isDefault, status, and createdAt dateFilter.
    """
    page_result = await _user_service.search_users(session, filter_obj)
    return success(data=page_result, message="Users fetched successfully")


@user_router.get(
    "/default",
    response_model=ApiResponse[UserResponse | None],
    status_code=status.HTTP_200_OK,
    summary="Get current default trading user",
)
async def get_default_user(
    session: AsyncSession = Depends(get_db),
):
    """Retrieves current active default user used for real-time market data."""
    default_user = await _user_service.get_default_user(session)
    return success(data=default_user, message="Default user retrieved successfully")


@user_router.get(
    "/{id}",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Get single user by ID",
)
async def get_user_by_id(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    """Retrieves user details and Upstox status by user ID."""
    user = await _user_service.get_user_by_id(session, id)
    return success(data=user, message="User retrieved successfully")


@user_router.put(
    "/{id}",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Update user and Upstox credentials",
)
async def update_user(
    id: int,
    payload: UserUpdateRequest,
    session: AsyncSession = Depends(get_db),
):
    """
    Updates user details and credentials.
    Omitted or blank secret fields retain their existing encrypted values.
    """
    updated_user = await _user_service.update_user(session, id, payload)
    return success(data=updated_user, message="User updated successfully")


@user_router.delete(
    "/{id}",
    response_model=ApiResponse[dict],
    status_code=status.HTTP_200_OK,
    summary="Soft delete user",
)
async def delete_user(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    """
    Soft deletes user.
    Blocked if target user is default and other active users exist.
    """
    await _user_service.delete_user(session, id)
    return success(data={"id": id, "deleted": True}, message="User deleted successfully")


@user_router.patch(
    "/{id}/default",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Set user as primary default account",
)
async def set_default_user(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    """Designates target user as the single default active trading account."""
    user = await _user_service.set_default_user(session, id)
    return success(data=user, message="User set as default successfully")


@user_router.patch(
    "/{id}/auto-auth",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Toggle automated daily authentication",
)
async def update_auto_auth(
    id: int,
    payload: UserAutoAuthPatchRequest,
    session: AsyncSession = Depends(get_db),
):
    """Toggles the autoAuthEnabled setting for the user."""
    user = await _user_service.update_auto_auth(session, id, payload.enabled)
    return success(data=user, message="Auto-auth setting updated successfully")


@user_router.post(
    "/{id}/upstox/authenticate",
    response_model=ApiResponse[UserResponse],
    status_code=status.HTTP_200_OK,
    summary="Execute automated Upstox authentication test",
)
async def authenticate_user(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    """Runs immediate automated authentication test using stored TOTP secret and credentials."""
    user = await _user_service.authenticate_user(session, id)
    return success(data=user, message="Authentication process executed")


@user_router.get(
    "/{id}/upstox/redirect-url",
    response_model=ApiResponse[RedirectUrlResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Upstox OAuth redirect URI",
)
async def get_redirect_url(
    id: int,
    session: AsyncSession = Depends(get_db),
):
    """Returns the redirect URL to register in the Upstox developer dashboard."""
    redirect_info = await _user_service.get_redirect_url(session, id)
    return success(data=redirect_info, message="Redirect URL fetched successfully")


# Public OAuth callback endpoint
@oauth_router.get(
    "/upstox/callback/{userId}",
    summary="Public Upstox OAuth callback endpoint",
)
async def upstox_callback(
    userId: int,
    code: str | None = Query(default=None),
    session: AsyncSession = Depends(get_db),
):
    """
    Public OAuth callback handling redirect from Upstox login dialog.
    Exchanges code for access token and updates account auth status.
    """
    res = await _user_service.handle_oauth_callback(session, userId, code)
    is_success = res.get("success", False)
    msg = res.get("message", "Authentication processed")

    # Friendly terminal-themed callback landing page
    status_color = "#10b981" if is_success else "#f43f5e"
    status_title = "Authentication Successful" if is_success else "Authentication Failed"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Upstox Authorization — auto-trader</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
      background-color: #080c14;
      color: #f8fafc;
      display: flex;
      align-items: center;
      justify-content: center;
      min-height: 100vh;
      margin: 0;
    }}
    .card {{
      background: #0e1524;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 12px;
      padding: 36px 44px;
      text-align: center;
      max-width: 480px;
      box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
    }}
    .badge {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 20px;
      font-size: 0.85rem;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.05);
      color: {status_color};
      border: 1px solid {status_color};
      margin-bottom: 20px;
    }}
    h1 {{ font-size: 1.4rem; margin-bottom: 12px; }}
    p {{ color: #94a3b8; font-size: 0.92rem; line-height: 1.6; }}
    .close-hint {{
      margin-top: 24px;
      font-size: 0.8rem;
      color: #64748b;
    }}
  </style>
</head>
<body>
  <div class="card">
    <div class="badge">{status_title}</div>
    <h1>auto-trader &bull; Upstox Connect</h1>
    <p>{msg}</p>
    <div class="close-hint">
      You may now close this browser tab and return to the auto-trader dashboard.
    </div>
  </div>
</body>
</html>
"""
    return HTMLResponse(content=html_content, status_code=200 if is_success else 400)
