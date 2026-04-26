"""
Apple Sign-In OAuth tests.

Mocks the Apple token endpoint (httpx POST) — no real Apple calls are made.
"""
from __future__ import annotations

import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_id_token(email: str, sub: str = "apple_sub_123") -> str:
    """Build a minimal fake id_token: header.{base64url(payload)}.sig."""
    payload = {"sub": sub, "email": email}
    encoded = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"fake_header.{encoded}.fake_sig"


FAKE_APPLE_TOKEN_RESPONSE = {
    "access_token": "apple.access.fake",
    "token_type": "bearer",
    "expires_in": 3600,
    "id_token": _make_id_token("apple_user@privaterelay.appleid.com"),
}


def _make_apple_token_mock(response_payload: dict, status_code: int = 200):
    """Return a mock async context manager simulating httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.json.return_value = response_payload
    if status_code >= 400:
        mock_response.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
    else:
        mock_response.raise_for_status = MagicMock()  # no-op

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    mock_client.post = AsyncMock(return_value=mock_response)
    return mock_client


# ---------------------------------------------------------------------------
# GET /api/auth/apple/authorize
# ---------------------------------------------------------------------------

async def test_apple_authorize_returns_authorization_url(client):
    """GET /api/auth/apple/authorize returns a JSON object with authorization_url."""
    resp = await client.get("/api/auth/apple/authorize")

    assert resp.status_code == 200
    data = resp.json()
    assert "authorization_url" in data
    url = data["authorization_url"]
    assert url.startswith("https://appleid.apple.com/auth/authorize")
    assert "response_mode=form_post" in url  # must be form_post when email scope is requested
    assert "scope=email" in url


# ---------------------------------------------------------------------------
# POST /api/auth/apple/callback
# ---------------------------------------------------------------------------

def _patch_callback(mock_client):
    """Return a context manager that patches both the client secret builder and httpx."""
    from contextlib import ExitStack
    stack = ExitStack()
    stack.enter_context(patch("api.oauth._build_apple_client_secret", return_value="fake.client.secret"))
    stack.enter_context(patch("api.oauth.httpx.AsyncClient", return_value=mock_client))
    return stack


async def test_apple_callback_creates_user_on_first_login(client):
    """POST /api/auth/apple/callback with a valid code redirects to frontend with access_token."""
    with _patch_callback(_make_apple_token_mock(FAKE_APPLE_TOKEN_RESPONSE)):
        resp = await client.post(
            "/api/auth/apple/callback",
            data={"code": "fake-code", "state": "fake-state"},
        )

    assert resp.status_code == 303
    location = resp.headers["location"]
    assert "access_token=" in location


async def test_apple_callback_sets_email_from_id_token(client):
    """A new user created via Apple Sign In gets their email set from the id_token."""
    from db import engine
    from db.models import User
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    with _patch_callback(_make_apple_token_mock(FAKE_APPLE_TOKEN_RESPONSE)):
        resp = await client.post(
            "/api/auth/apple/callback",
            data={"code": "fake-code", "state": "fake-state"},
        )

    assert resp.status_code == 303

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == "apple_user@privaterelay.appleid.com")
        )
        user = result.scalar_one()
        assert user.email == "apple_user@privaterelay.appleid.com"
        assert user.is_active is True
        assert user.is_verified is True


async def test_apple_callback_returning_user_gets_token(client):
    """A returning Apple user gets a fresh JWT without creating a duplicate account."""
    with _patch_callback(_make_apple_token_mock(FAKE_APPLE_TOKEN_RESPONSE)):
        r1 = await client.post(
            "/api/auth/apple/callback",
            data={"code": "code1", "state": "s1"},
        )

    with _patch_callback(_make_apple_token_mock(FAKE_APPLE_TOKEN_RESPONSE)):
        r2 = await client.post(
            "/api/auth/apple/callback",
            data={"code": "code2", "state": "s2"},
        )

    assert r1.status_code == 303
    assert r2.status_code == 303
    # Both calls redirect with a token — no duplicate user error
    assert "access_token=" in r1.headers["location"]
    assert "access_token=" in r2.headers["location"]


async def test_apple_callback_with_invalid_code_redirects_with_error(client):
    """POST /api/auth/apple/callback with a bad code redirects to frontend with error param."""
    with _patch_callback(_make_apple_token_mock({}, status_code=400)):
        resp = await client.post(
            "/api/auth/apple/callback",
            data={"code": "bad-code", "state": "some-state"},
        )

    assert resp.status_code == 303
    assert "error=" in resp.headers["location"]
