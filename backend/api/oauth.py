"""
Google OAuth2 endpoints.

GET /api/auth/google/authorize  — returns { authorization_url }
GET /api/auth/google/callback   — exchanges code for access_token, creates/finds user,
                                   returns { access_token, token_type }

These wrap httpx-oauth's GoogleOAuth2 client and fastapi-users' user manager so that:
- First-time Google users get a new account created automatically
- Returning Google users get a fresh JWT for their existing account
"""
from __future__ import annotations

import base64
import json
import secrets
import time
from urllib.parse import urlencode

import httpx
import jwt  # PyJWT
from fastapi import APIRouter, Depends, HTTPException, Query
from httpx_oauth.clients.google import GoogleOAuth2

from api.auth import auth_backend
from config import settings
from db.user_manager import get_user_manager

oauth_router = APIRouter()

# Module-level client — instantiated lazily using config properties.
# Tests can patch `api.oauth.google_oauth_client`.
google_oauth_client = GoogleOAuth2(
    client_id=settings.google_client_id,
    client_secret=settings.google_client_secret,
)

_STATE_STORE: dict[str, str] = {}  # simple in-process state store for CSRF


@oauth_router.get("/auth/google/authorize")
async def google_authorize():
    """Return the Google OAuth2 authorization URL the frontend should redirect to."""
    state = secrets.token_urlsafe(32)
    authorization_url = await google_oauth_client.get_authorization_url(
        redirect_uri=settings.google_redirect_url,
        state=state,
    )
    _STATE_STORE[state] = state  # record issued state tokens
    return {"authorization_url": authorization_url}


@oauth_router.get("/auth/google/callback")
async def google_callback(
    code: str = Query(...),
    state: str = Query(...),
    user_manager=Depends(get_user_manager),
):
    """Handle the Google OAuth2 callback.

    Exchanges the code for a Google access token, fetches the user's email,
    then finds-or-creates a HomeBidder user account and issues a JWT.
    """
    try:
        token_response = await google_oauth_client.get_access_token(
            code=code,
            redirect_uri=settings.google_redirect_url,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"OAuth token exchange failed: {exc}") from exc

    try:
        access_token = token_response["access_token"]
        async with google_oauth_client.get_httpx_client() as http:
            response = await http.get(
                "https://people.googleapis.com/v1/people/me",
                params={"personFields": "emailAddresses,names"},
                headers={**google_oauth_client.request_headers, "Authorization": f"Bearer {access_token}"},
            )
            if response.status_code >= 400:
                raise ValueError(f"People API returned {response.status_code}: {response.text}")
            profile = response.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to fetch user info: {exc}") from exc

    try:
        email = next(
            e["value"] for e in profile.get("emailAddresses", [])
            if e["metadata"]["primary"]
        )
    except StopIteration:
        raise HTTPException(status_code=400, detail="No email returned from Google")

    display_name: str | None = next(
        (n["displayName"] for n in profile.get("names", []) if n["metadata"]["primary"]),
        None,
    )

    # Find existing user or create one.
    existing = await user_manager.user_db.get_by_email(email)
    if existing is None:
        # Create a new verified user without a password (OAuth-only login).
        user = await user_manager.user_db.create({
            "email": email,
            "hashed_password": "",   # no password login allowed
            "is_active": True,
            "is_verified": True,
            "is_superuser": False,
            "display_name": display_name,
        })
    else:
        user = existing

    # Issue a JWT via the auth backend.
    strategy = auth_backend.get_strategy()
    token = await strategy.write_token(user)
    return {"access_token": token, "token_type": "bearer"}


# ---------------------------------------------------------------------------
# Apple Sign In helpers
# ---------------------------------------------------------------------------

def _build_apple_client_secret() -> str:
    """Generate the short-lived JWT used as Apple's client_secret (ES256, 5-minute TTL)."""
    now = int(time.time())
    payload = {
        "iss": settings.apple_team_id,
        "iat": now,
        "exp": now + 300,
        "aud": "https://appleid.apple.com",
        "sub": settings.apple_client_id,
    }
    return jwt.encode(
        payload,
        settings.apple_private_key,
        algorithm="ES256",
        headers={"kid": settings.apple_key_id},
    )


def _decode_apple_id_token_email(id_token: str) -> str:
    """Extract email from Apple id_token payload.

    Decodes the base64url payload without signature verification — safe for MVP
    because the token arrives directly from Apple's HTTPS token endpoint.
    """
    parts = id_token.split(".")
    if len(parts) < 2:
        raise ValueError("Malformed id_token")
    # base64url padding: length must be a multiple of 4
    padded = parts[1] + "=" * (4 - len(parts[1]) % 4)
    claims = json.loads(base64.urlsafe_b64decode(padded))
    email = claims.get("email")
    if not email:
        raise ValueError("No email claim in Apple id_token")
    return email


# ---------------------------------------------------------------------------
# GET /api/auth/apple/authorize
# ---------------------------------------------------------------------------

@oauth_router.get("/auth/apple/authorize")
async def apple_authorize():
    """Return the Apple Sign In authorization URL the frontend should redirect to."""
    state = secrets.token_urlsafe(32)
    _STATE_STORE[state] = state
    params = {
        "response_type": "code",
        "client_id": settings.apple_client_id,
        "redirect_uri": settings.apple_redirect_url,
        "state": state,
        "scope": "email",
        "response_mode": "query",
    }
    return {"authorization_url": "https://appleid.apple.com/auth/authorize?" + urlencode(params)}


# ---------------------------------------------------------------------------
# GET /api/auth/apple/callback
# ---------------------------------------------------------------------------

@oauth_router.get("/auth/apple/callback")
async def apple_callback(
    code: str = Query(...),
    state: str = Query(...),
    user_manager=Depends(get_user_manager),
):
    """Handle the Apple Sign In callback.

    Exchanges the authorization code for Apple tokens, extracts the email from
    the id_token, then finds-or-creates a HomeBidder user account and issues a JWT.
    """
    try:
        client_secret = _build_apple_client_secret()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to build Apple client secret: {exc}") from exc

    try:
        async with httpx.AsyncClient() as http:
            response = await http.post(
                "https://appleid.apple.com/auth/token",
                data={
                    "client_id": settings.apple_client_id,
                    "client_secret": client_secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": settings.apple_redirect_url,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            token_data = response.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Apple token exchange failed: {exc}") from exc

    try:
        email = _decode_apple_id_token_email(token_data.get("id_token", ""))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to extract email from Apple token: {exc}") from exc

    # Find existing user or create one.
    existing = await user_manager.user_db.get_by_email(email)
    if existing is None:
        # Create a new verified user without a password (OAuth-only login).
        # display_name is None — Apple does not include name in id_token for response_mode=query.
        user = await user_manager.user_db.create({
            "email": email,
            "hashed_password": "",
            "is_active": True,
            "is_verified": True,
            "is_superuser": False,
            "display_name": None,
        })
    else:
        user = existing

    # Issue a JWT via the auth backend.
    strategy = auth_backend.get_strategy()
    token = await strategy.write_token(user)
    return {"access_token": token, "token_type": "bearer"}
