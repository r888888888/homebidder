# Set env vars before any app imports so the DB engine and API key are test-safe.
import os
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key")

import pytest
from httpx import AsyncClient, ASGITransport


@pytest.fixture
async def client():
    from main import app
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
