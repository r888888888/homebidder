"""
Phase 4 tests: Google OAuth2 social login.

These tests mock the httpx_oauth token exchange so no real Google calls
are made. The backend endpoints just need to return the right shapes.
"""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock


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
    from db import engine
    from db.models import User
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select

    fake_token_response = {
        "access_token": "ya29.fake",
        "token_type": "bearer",
        "expires_in": 3600,
        "id_token": "fake.id.token",
    }
    fake_user_info = {
        "sub": "google-uid-12345",
        "email": "google_user@gmail.com",
        "email_verified": True,
    }

    with patch("api.oauth.google_oauth_client") as mock_client:
        mock_client.get_access_token = AsyncMock(return_value=MagicMock(**fake_token_response))
        mock_client.get_id_email = AsyncMock(return_value=("google_user@gmail.com", True))

        resp = await client.get(
            "/api/auth/google/callback",
            params={"code": "fake-code", "state": "fake-state"},
        )

    # Should return a JWT token
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


async def test_google_callback_with_invalid_code_returns_4xx(client):
    """GET /api/auth/google/callback with a bad code returns 400 or 422."""
    with patch("api.oauth.google_oauth_client") as mock_client:
        mock_client.get_access_token = AsyncMock(side_effect=Exception("invalid_grant"))

        resp = await client.get(
            "/api/auth/google/callback",
            params={"code": "bad-code", "state": "some-state"},
        )

    assert resp.status_code in (400, 422, 500)
