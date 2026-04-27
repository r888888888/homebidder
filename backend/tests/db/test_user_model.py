"""
Tests for the User model and analyses.user_id FK.
Written before implementation (TDD).
"""
import datetime
import pytest


async def test_user_table_exists_after_init_db(client):
    """init_db() must create the users table."""
    from db import engine
    from sqlalchemy import text
    async with engine.begin() as conn:
        result = await conn.execute(
            text("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        )
        row = result.fetchone()
    assert row is not None, "users table not found after init_db"


async def test_analyses_user_id_column_is_nullable(client):
    """Creating an Analysis with user_id=None must succeed (column is nullable)."""
    from db.models import Analysis, Listing
    from db import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with async_session() as session:
        listing = Listing(
            address_input="1 Null User St",
            address_matched="1 NULL USER ST",
        )
        session.add(listing)
        await session.flush()
        analysis = Analysis(
            listing_id=listing.id,
            user_id=None,
            created_at=datetime.datetime.utcnow(),
        )
        session.add(analysis)
        await session.commit()
        assert analysis.user_id is None


