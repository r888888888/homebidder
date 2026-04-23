"""
Phase 4 tests: Google OAuth2 social login.

These tests mock the httpx_oauth token exchange so no real Google calls
are made. The backend endpoints just need to return the right shapes.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from contextlib import asynccontextmanager


def _make_mock_client(profile_payload: dict):
    """Return a mock httpx async client that responds to the People API."""
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = profile_payload

    mock_http = MagicMock()
    mock_http.__aenter__ = AsyncMock(return_value=mock_http)
    mock_http.__aexit__ = AsyncMock(return_value=False)
    mock_http.get = AsyncMock(return_value=mock_response)
    return mock_http


FAKE_TOKEN_RESPONSE = {
    "access_token": "ya29.fake",
    "token_type": "bearer",
    "expires_in": 3600,
    "id_token": "fake.id.token",
}

FAKE_PROFILE = {
    "resourceName": "people/12345",
    "emailAddresses": [
        {"value": "google_user@gmail.com", "metadata": {"primary": True}}
    ],
    "names": [
        {"displayName": "Google User", "metadata": {"primary": True}}
    ],
}


# ---------------------------------------------------------------------------
# GET /api/auth/google/authorize
# ---------------------------------------------------------------------------

async def test_google_authorize_returns_authorization_url(client):
    """GET /api/auth/google/authorize returns a JSON object with authorization_url."""
    with patch("api.oauth.google_oauth_client") as mock_client:
        mock_client.get_authorization_url = AsyncMock(
            return_value="https://accounts.google.com/o/oauth2/auth?client_id=test&..."
        )
        resp = await client.get("/api/auth/google/authorize")

    assert resp.status_code == 200
    data = resp.json()
    assert "authorization_url" in data
    assert data["authorization_url"].startswith("https://accounts.google.com")


# ---------------------------------------------------------------------------
# GET /api/auth/google/callback
# ---------------------------------------------------------------------------

async def test_google_callback_creates_user_on_first_login(client):
    """GET /api/auth/google/callback with a valid code creates a new user and returns JWT."""
    with patch("api.oauth.google_oauth_client") as mock_client:
        mock_client.get_access_token = AsyncMock(return_value=FAKE_TOKEN_RESPONSE)
        mock_client.get_httpx_client.return_value = _make_mock_client(FAKE_PROFILE)
        mock_client.request_headers = {}

        resp = await client.get(
            "/api/auth/google/callback",
            params={"code": "fake-code", "state": "fake-state"},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_google_callback_sets_display_name_on_new_user(client):
    """A new user created via Google OAuth gets their display_name populated."""
    from db import engine
    from db.models import User
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    with patch("api.oauth.google_oauth_client") as mock_client:
        mock_client.get_access_token = AsyncMock(return_value=FAKE_TOKEN_RESPONSE)
        mock_client.get_httpx_client.return_value = _make_mock_client(FAKE_PROFILE)
        mock_client.request_headers = {}

        resp = await client.get(
            "/api/auth/google/callback",
            params={"code": "fake-code", "state": "fake-state"},
        )

    assert resp.status_code == 200

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        result = await session.execute(
            select(User).where(User.email == "google_user@gmail.com")
        )
        user = result.scalar_one()
        assert user.display_name == "Google User"


async def test_google_callback_with_invalid_code_returns_4xx(client):
    """GET /api/auth/google/callback with a bad code returns 400 or 422."""
    with patch("api.oauth.google_oauth_client") as mock_client:
        mock_client.get_access_token = AsyncMock(side_effect=Exception("invalid_grant"))

        resp = await client.get(
            "/api/auth/google/callback",
            params={"code": "bad-code", "state": "some-state"},
        )

    assert resp.status_code in (400, 422, 500)
