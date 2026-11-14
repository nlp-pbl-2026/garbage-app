"""Authentication regressions using a temporary DB and no external services."""

import pytest
import pytest_asyncio
import secrets
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth import hash_password, verify_password
from app.database import get_db
from app.main import app
from app.models import User


@pytest_asyncio.fixture
async def auth_client(tmp_path, monkeypatch):
    monkeypatch.setattr("app.config.SECRET_KEY", secrets.token_urlsafe(32))
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


@pytest.mark.parametrize("password", ["a" * 73, "あ" * 25])
def test_bcrypt_never_truncates_passwords(password):
    with pytest.raises(ValueError, match="72"):
        hash_password(password)
    assert not verify_password(password, hash_password("short-password"))


def test_bcrypt_utf8_boundary():
    password = "あ" * 24  # 72 UTF-8 bytes, fewer than 72 characters.
    assert verify_password(password, hash_password(password))


@pytest.mark.asyncio
@pytest.mark.parametrize("key", ["", "short"])
async def test_missing_or_weak_key_disables_auth_without_disabling_health(
    auth_client, monkeypatch, key
):
    monkeypatch.setattr("app.config.SECRET_KEY", key)
    response = await auth_client.post(
        "/api/auth/register",
        json={"username": "no-key-user", "password": "valid-password"},
    )
    assert response.status_code == 503
    assert (await auth_client.get("/api/health")).status_code == 200
    # The disabled attempt must not leave an account behind.
    monkeypatch.setattr("app.config.SECRET_KEY", secrets.token_urlsafe(32))
    assert (
        await auth_client.post(
            "/api/auth/register",
            json={"username": "no-key-user", "password": "valid-password"},
        )
    ).status_code == 201


@pytest.mark.asyncio
async def test_long_passwords_rejected_at_each_http_boundary(auth_client):
    base = {"username": "long-password-user", "password": "short-password"}
    long = "あ" * 25
    assert (
        await auth_client.post("/api/auth/register", json={**base, "password": long})
    ).status_code == 422
    registered = await auth_client.post("/api/auth/register", json=base)
    headers = {"Authorization": "Bearer " + registered.json()["access_token"]}
    assert (
        await auth_client.post("/api/auth/login", json={**base, "password": long})
    ).status_code == 422
    assert (
        await auth_client.put(
            "/api/auth/change-password",
            headers=headers,
            json={"current_password": base["password"], "new_password": long},
        )
    ).status_code == 422
    assert (await auth_client.post("/api/auth/login", json=base)).status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("subject", ["not-an-integer", "-1", "9" * 30])
async def test_invalid_signed_subject_returns_401(auth_client, subject):
    from datetime import datetime, timedelta
    from jose import jwt
    from app import config

    token = jwt.encode(
        {"sub": subject, "exp": datetime.utcnow() + timedelta(minutes=5)},
        config.SECRET_KEY,
        algorithm=config.ALGORITHM,
    )
    response = await auth_client.get(
        "/api/auth/me", headers={"Authorization": "Bearer " + token}
    )
    assert response.status_code == 401
