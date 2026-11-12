"""Authentication regressions using a temporary DB and no external services."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import hash_password, verify_password
from app.database import get_db
from app.main import app
from app.models import User


@pytest_asyncio.fixture
async def auth_client(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'auth.db'}")
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as conn:
        await conn.run_sync(User.__table__.create)

    async def temporary_db():
        async with sessions() as session:
            yield session

    previous = app.dependency_overrides.copy()
    app.dependency_overrides[get_db] = temporary_db
    try:
        # ASGITransport does not run the production DB's lifespan startup.
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)
        await engine.dispose()


def test_bcrypt_hash_accepts_short_password_and_rejects_wrong_password():
    # passlib 1.7.4 + bcrypt 5 failed even for short passwords during startup.
    hashed = hash_password("merge-login-test")
    assert hashed != "merge-login-test"
    assert verify_password("merge-login-test", hashed)
    assert not verify_password("wrong-password", hashed)


@pytest.mark.asyncio
async def test_register_login_and_save_uwajima_region(auth_client):
    credentials = {"username": "merge-user", "password": "merge-password"}
    response = await auth_client.post("/api/auth/register", json=credentials)
    assert response.status_code == 201
    assert response.json()["token_type"] == "bearer"

    response = await auth_client.post("/api/auth/login", json=credentials)
    assert response.status_code == 200
    headers = {"Authorization": f"Bearer {response.json()['access_token']}"}
    me = await auth_client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    assert me.json()["username"] == credentials["username"]
    assert "hashed_password" not in me.json()

    settings = {"region": {"municipality_id": "38203", "district_id": "fixture"}}
    saved = await auth_client.put(
        "/api/auth/settings", headers=headers, json={"settings": settings}
    )
    assert saved.status_code == 200
    me = await auth_client.get("/api/auth/me", headers=headers)
    assert me.json()["settings"] == settings


@pytest.mark.asyncio
async def test_duplicate_user_wrong_password_and_invalid_token(auth_client):
    credentials = {"username": "duplicate-user", "password": "merge-password"}
    assert (
        await auth_client.post("/api/auth/register", json=credentials)
    ).status_code == 201
    assert (
        await auth_client.post("/api/auth/register", json=credentials)
    ).status_code == 409
    wrong = {**credentials, "password": "incorrect-password"}
    assert (await auth_client.post("/api/auth/login", json=wrong)).status_code == 401
    invalid = await auth_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer invalid-token"}
    )
    assert invalid.status_code == 401


@pytest.mark.asyncio
async def test_changed_password_replaces_previous_login(auth_client):
    credentials = {"username": "password-user", "password": "old-password"}
    registered = await auth_client.post("/api/auth/register", json=credentials)
    assert registered.status_code == 201
    headers = {"Authorization": f"Bearer {registered.json()['access_token']}"}
    changed = await auth_client.put(
        "/api/auth/change-password",
        headers=headers,
        json={"current_password": "old-password", "new_password": "new-password"},
    )
    assert changed.status_code == 200
    assert (
        await auth_client.post("/api/auth/login", json=credentials)
    ).status_code == 401
    credentials["password"] = "new-password"
    assert (
        await auth_client.post("/api/auth/login", json=credentials)
    ).status_code == 200
