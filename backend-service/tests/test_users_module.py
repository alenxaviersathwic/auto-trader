import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from app.core.db.base_entity import Base
from app.core.db.entity_status import EntityStatus
from app.core.exception.app_exceptions import (
    ConflictException,
    NotFoundException,
    ValidationException,
)
from app.modules.users.entity.user_entity import User
from app.modules.users.entity.upstox_config_entity import UpstoxConfig
from app.modules.users.repository.user_repository import UserRepository
from app.modules.users.schema.user_schema import (
    UserCreateRequest,
    UserSearchFilter,
    UserUpdateRequest,
)
from app.modules.users.service.upstox_service import UpstoxService
from app.modules.users.service.user_service import UserService
from app.core.crypto.secret_cipher import cipher

# In-memory async SQLite engine for unit tests
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def async_session() -> AsyncSession:
    engine = create_async_engine(TEST_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_totp_generator():
    """Verify RFC 6238 TOTP generation produces valid 6-digit string."""
    # Standard Google Authenticator test base32 secret: JBSWY3DPEHPK3PXP
    secret = "JBSWY3DPEHPK3PXP"
    code = UpstoxService.generate_totp(secret)
    assert len(code) == 6
    assert code.isdigit()


@pytest.mark.asyncio
async def test_first_user_is_default_and_secrets_encrypted(async_session: AsyncSession):
    """Verify first user created is default and secrets are encrypted."""
    service = UserService()

    req = UserCreateRequest(
        name="Primary Trader",
        apiKey="test_api_key_1",
        apiSecret="super_secret_api_key_1",
        mobile="9876543210",
        pin="123456",
        totpSecret="JBSWY3DPEHPK3PXP",
        autoAuthEnabled=True,
    )

    user_resp = await service.create_user(
        async_session, req, base_url="http://localhost:8000"
    )

    assert user_resp.name == "Primary Trader"
    assert user_resp.isDefault is True
    assert user_resp.status == "ACTIVE"
    assert user_resp.upstox is not None
    assert user_resp.upstox.apiKey == "test_api_key_1"
    assert user_resp.upstox.mobile == "9876543210"
    assert user_resp.upstox.hasApiSecret is True
    assert user_resp.upstox.hasPin is True
    assert user_resp.upstox.hasTotpSecret is True
    assert user_resp.upstox.redirectUri == f"http://localhost:8000/api/v1/upstox/callback/{user_resp.id}"

    # Verify directly from DB that plaintext secrets are NOT stored
    repo = UserRepository()
    db_user = await repo.get_by_id(async_session, user_resp.id)
    assert db_user is not None
    assert db_user.upstoxConfig is not None
    assert db_user.upstoxConfig.apiSecretEnc != "super_secret_api_key_1"
    assert cipher.decrypt(db_user.upstoxConfig.apiSecretEnc) == "super_secret_api_key_1"
    assert cipher.decrypt(db_user.upstoxConfig.pinEnc) == "123456"


@pytest.mark.asyncio
async def test_second_user_is_not_default(async_session: AsyncSession):
    """Verify second user created has isDefault = False."""
    service = UserService()

    req1 = UserCreateRequest(name="User One", apiKey="k1", apiSecret="s1", mobile="9800000001", pin="1111", totpSecret="T1")
    user1 = await service.create_user(async_session, req1, base_url="http://localhost:8000")
    assert user1.isDefault is True

    req2 = UserCreateRequest(name="User Two", apiKey="k2", apiSecret="s2", mobile="9800000002", pin="2222", totpSecret="T2")
    user2 = await service.create_user(async_session, req2, base_url="http://localhost:8000")
    assert user2.isDefault is False


@pytest.mark.asyncio
async def test_duplicate_name_conflict(async_session: AsyncSession):
    """Verify creating user with existing active name raises ConflictException."""
    service = UserService()

    req1 = UserCreateRequest(name="DuplicateName", apiKey="k1", apiSecret="s1", mobile="9800000001", pin="1111", totpSecret="T1")
    await service.create_user(async_session, req1, base_url="http://localhost:8000")

    req2 = UserCreateRequest(name="DuplicateName", apiKey="k2", apiSecret="s2", mobile="9800000002", pin="2222", totpSecret="T2")
    with pytest.raises(ConflictException) as exc_info:
        await service.create_user(async_session, req2, base_url="http://localhost:8000")

    assert "already exists" in exc_info.value.message


@pytest.mark.asyncio
async def test_make_default_switches_badge(async_session: AsyncSession):
    """Verify set_default_user unsets previous default and sets new default."""
    service = UserService()

    u1 = await service.create_user(async_session, UserCreateRequest(name="User A", apiKey="k", apiSecret="s", mobile="1", pin="1", totpSecret="t"), base_url="http://test")
    u2 = await service.create_user(async_session, UserCreateRequest(name="User B", apiKey="k", apiSecret="s", mobile="2", pin="2", totpSecret="t"), base_url="http://test")

    assert u1.isDefault is True
    assert u2.isDefault is False

    # Switch default to user B
    updated_u2 = await service.set_default_user(async_session, u2.id)
    assert updated_u2.isDefault is True

    # User A is now not default
    updated_u1 = await service.get_user_by_id(async_session, u1.id)
    assert updated_u1.isDefault is False

    # Default user query returns User B
    current_default = await service.get_default_user(async_session)
    assert current_default is not None
    assert current_default.id == u2.id


@pytest.mark.asyncio
async def test_cannot_delete_default_user_while_others_exist(async_session: AsyncSession):
    """Verify deleting default user is blocked while other active users exist."""
    service = UserService()

    u1 = await service.create_user(async_session, UserCreateRequest(name="Default User", apiKey="k", apiSecret="s", mobile="1", pin="1", totpSecret="t"), base_url="http://test")
    u2 = await service.create_user(async_session, UserCreateRequest(name="Other User", apiKey="k", apiSecret="s", mobile="2", pin="2", totpSecret="t"), base_url="http://test")

    with pytest.raises(ValidationException) as exc_info:
        await service.delete_user(async_session, u1.id)
    assert "Cannot delete the default user while other users exist" in exc_info.value.message

    # But non-default user can be deleted
    await service.delete_user(async_session, u2.id)
    deleted_u2 = await service.get_user_by_id(async_session, u2.id)
    assert deleted_u2.status == "DELETED"

    # Now that no other active users exist, default user u1 can be deleted
    await service.delete_user(async_session, u1.id)
    deleted_u1 = await service.get_user_by_id(async_session, u1.id)
    assert deleted_u1.status == "DELETED"


@pytest.mark.asyncio
async def test_update_user_blank_secrets_retain_stored(async_session: AsyncSession):
    """Verify blank secrets in update retain stored values."""
    service = UserService()

    u = await service.create_user(
        async_session,
        UserCreateRequest(name="Original", apiKey="key1", apiSecret="secret123", mobile="9876543210", pin="9999", totpSecret="TOTPSECRET"),
        base_url="http://test",
    )

    # Update with blank secrets
    update_req = UserUpdateRequest(
        name="Updated Name",
        apiKey="key2",
        apiSecret="", # Blank -> keep stored
        pin="",       # Blank -> keep stored
        totpSecret=None, # None -> keep stored
    )
    res = await service.update_user(async_session, u.id, update_req)

    assert res.name == "Updated Name"
    assert res.upstox.apiKey == "key2"
    assert res.upstox.hasApiSecret is True
    assert res.upstox.hasPin is True
    assert res.upstox.hasTotpSecret is True

    # Check decrypt
    repo = UserRepository()
    db_user = await repo.get_by_id(async_session, u.id)
    assert cipher.decrypt(db_user.upstoxConfig.apiSecretEnc) == "secret123"
    assert cipher.decrypt(db_user.upstoxConfig.pinEnc) == "9999"


@pytest.mark.asyncio
async def test_paged_search_and_filtering(async_session: AsyncSession):
    """Verify POST search endpoint with query, status, and pagination."""
    service = UserService()

    for i in range(5):
        await service.create_user(
            async_session,
            UserCreateRequest(name=f"Trader {i}", apiKey=f"key_{i}", apiSecret="s", mobile=f"980000000{i}", pin="1", totpSecret="t"),
            base_url="http://test",
        )

    # Search all
    search_all = await service.search_users(async_session, UserSearchFilter(page=0, limit=2))
    assert search_all.totalItems == 5
    assert search_all.totalPages == 3
    assert len(search_all.list) == 2

    # Query substring search
    search_q = await service.search_users(async_session, UserSearchFilter(query="Trader 3", page=0, limit=10))
    assert search_q.totalItems == 1
    assert search_q.list[0].name == "Trader 3"


@pytest.mark.asyncio
async def test_full_controller_api_endpoints(async_session: AsyncSession):
    """
    Test every API endpoint specified in section 2 through FastAPI test client.
    Verifies universal ApiResponse envelope and camelCase JSON contracts.
    """
    from httpx import ASGITransport, AsyncClient
    from app.main import app
    from app.core.db.session import get_db

    # Override get_db dependency to use the test session
    async def override_get_db():
        yield async_session

    app.dependency_overrides[get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. GET /api/v1/users/default when empty
        res = await client.get("/api/v1/users/default")
        assert res.status_code == 200
        envelope = res.json()
        assert envelope["statusCode"] == 200
        assert envelope["data"] is None

        # 2. POST /api/v1/users (Create user + Upstox config)
        create_payload = {
            "name": "Integration Trader",
            "apiKey": "upstox_key_xyz",
            "apiSecret": "upstox_secret_abc",
            "mobile": "9988776655",
            "pin": "654321",
            "totpSecret": "JBSWY3DPEHPK3PXP",
            "autoAuthEnabled": True,
        }
        create_res = await client.post("/api/v1/users", json=create_payload)
        assert create_res.status_code == 201
        create_env = create_res.json()
        assert create_env["statusCode"] == 201
        created_user = create_env["data"]
        user_id = created_user["id"]
        assert created_user["name"] == "Integration Trader"
        assert created_user["isDefault"] is True
        assert created_user["upstox"]["apiKey"] == "upstox_key_xyz"
        assert created_user["upstox"]["hasApiSecret"] is True
        assert created_user["upstox"]["hasPin"] is True
        assert created_user["upstox"]["hasTotpSecret"] is True
        assert "redirectUri" in created_user["upstox"]

        # 3. GET /api/v1/users/{id}
        get_res = await client.get(f"/api/v1/users/{user_id}")
        assert get_res.status_code == 200
        assert get_res.json()["data"]["id"] == user_id

        # 4. GET /api/v1/users/default now returns the created user
        def_res = await client.get("/api/v1/users/default")
        assert def_res.status_code == 200
        assert def_res.json()["data"]["id"] == user_id

        # 5. GET /api/v1/users/{id}/upstox/redirect-url
        red_res = await client.get(f"/api/v1/users/{user_id}/upstox/redirect-url")
        assert red_res.status_code == 200
        assert "redirectUri" in red_res.json()["data"]

        # 6. POST /api/v1/users/{id}/upstox/authenticate
        auth_res = await client.post(f"/api/v1/users/{user_id}/upstox/authenticate")
        assert auth_res.status_code == 200
        auth_env = auth_res.json()
        assert auth_env["data"]["upstox"]["authStatus"] in ["VALID", "AUTH_FAILED"]

        # 7. PATCH /api/v1/users/{id}/auto-auth
        patch_auth_res = await client.patch(
            f"/api/v1/users/{user_id}/auto-auth", json={"enabled": False}
        )
        assert patch_auth_res.status_code == 200
        assert patch_auth_res.json()["data"]["upstox"]["autoAuthEnabled"] is False

        # 8. PUT /api/v1/users/{id} (Update user, blank secrets)
        put_res = await client.put(
            f"/api/v1/users/{user_id}",
            json={"name": "Integration Trader Updated", "apiKey": "new_key", "mobile": "9988776655", "apiSecret": ""},
        )
        assert put_res.status_code == 200
        assert put_res.json()["data"]["name"] == "Integration Trader Updated"
        assert put_res.json()["data"]["upstox"]["hasApiSecret"] is True

        # 9. POST /api/v1/users/search
        search_res = await client.post(
            "/api/v1/users/search",
            json={"page": 0, "limit": 10, "sortBy": "name", "sortDir": "asc", "status": "ACTIVE"},
        )
        assert search_res.status_code == 200
        search_data = search_res.json()["data"]
        assert search_data["totalItems"] >= 1
        assert len(search_data["list"]) >= 1

        # 10. GET /api/v1/upstox/callback/{userId} (Public OAuth callback)
        callback_res = await client.get(f"/api/v1/upstox/callback/{user_id}?code=test_code_123")
        assert callback_res.status_code in [200, 400]
        assert "auto-trader" in callback_res.text

        # 11. DELETE /api/v1/users/{id}
        del_res = await client.delete(f"/api/v1/users/{user_id}")
        assert del_res.status_code == 200
        assert del_res.json()["data"]["deleted"] is True

    app.dependency_overrides.clear()

