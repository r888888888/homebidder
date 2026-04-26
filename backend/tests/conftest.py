# Set env vars before any app imports so the DB engine and API key are test-safe.
# These must be set before load_dotenv() runs (which happens on first import of
# main.py). Using setdefault ensures .env cannot override these test values
# (python-dotenv skips vars already present in os.environ).
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_homebidder.db")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32chars!!")
# Use canonical default values for rate-limit settings regardless of .env overrides.
os.environ.setdefault("RATE_LIMIT_ANALYSES_PER_DAY", "5")
os.environ.setdefault("RATE_LIMIT_AUTHENTICATED_PER_DAY", "20")
# Subscription tier monthly limits
os.environ.setdefault("RATE_LIMIT_ANONYMOUS_PER_MONTH", "3")
os.environ.setdefault("RATE_LIMIT_BUYER_PER_MONTH", "5")
os.environ.setdefault("RATE_LIMIT_INVESTOR_PER_MONTH", "30")
os.environ.setdefault("RATE_LIMIT_AGENT_PER_MONTH", "100")
# Stripe — empty keys disable payment features; webhook secret used by mock tests
os.environ.setdefault("STRIPE_SECRET_KEY", "")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_secret")
os.environ.setdefault("STRIPE_INVESTOR_PRICE_ID", "price_investor_test_123")
os.environ.setdefault("STRIPE_AGENT_PRICE_ID", "price_agent_test_456")
# Google OAuth — empty in tests (endpoints use mocked client)
os.environ.setdefault("GOOGLE_CLIENT_ID", "test-google-client-id")
os.environ.setdefault("GOOGLE_CLIENT_SECRET", "test-google-client-secret")
# Apple Sign In — empty private key is fine; httpx.AsyncClient is mocked in tests
os.environ.setdefault("APPLE_CLIENT_ID", "com.example.test.service")
os.environ.setdefault("APPLE_TEAM_ID", "TESTTEAMID1")
os.environ.setdefault("APPLE_KEY_ID", "TESTKEYID1")
os.environ.setdefault("APPLE_PRIVATE_KEY", "")
os.environ.setdefault("APPLE_REDIRECT_URL", "http://localhost:3000/auth/callback/apple")

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client():
    from main import app
    from db import engine, init_db
    from db.models import Base

    # Drop and recreate all tables so each test starts with a clean database.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await init_db()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
