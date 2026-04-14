# Set env vars before any app imports so the DB engine and API key are test-safe.
# These must be set before load_dotenv() runs (which happens on first import of
# main.py). Using setdefault ensures .env cannot override these test values
# (python-dotenv skips vars already present in os.environ).
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-32chars!!")
# Use canonical default values for rate-limit settings regardless of .env overrides.
os.environ.setdefault("RATE_LIMIT_ANALYSES_PER_DAY", "5")
os.environ.setdefault("RATE_LIMIT_AUTHENTICATED_PER_DAY", "20")

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
