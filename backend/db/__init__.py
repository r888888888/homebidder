from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text
from .models import Base
import logging
import sys
import os

log = logging.getLogger(__name__)

# Allow DATABASE_URL override for tests (set before any import via conftest.py),
# otherwise fall through to the centralised settings object.
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./homebidder.db")

# Ensure the parent directory exists for file-based SQLite URLs (e.g. on a
# freshly-mounted Fly volume where the subdirectory hasn't been created yet).
if DATABASE_URL.startswith("sqlite"):
    # Split on the triple-slash to get the file path portion.
    # sqlite+aiosqlite:////app/data/db/homebidder.db -> /app/data/db/homebidder.db
    # sqlite+aiosqlite:///./homebidder.db            -> ./homebidder.db
    _parts = DATABASE_URL.split("///", 1)
    if len(_parts) == 2:
        _db_dir = os.path.dirname(os.path.abspath(_parts[1]))
        if _db_dir:
            os.makedirs(_db_dir, exist_ok=True)

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Columns added after the initial schema. Each entry is (column_name, DDL_type).
# init_db() will ALTER TABLE to add any that are absent from the live database.
_ANALYSES_MIGRATIONS: list[tuple[str, str]] = [
    ("risk_level",            "VARCHAR(32)"),
    ("investment_rating",     "VARCHAR(32)"),
    ("property_data_json",    "TEXT"),
    ("neighborhood_data_json","TEXT"),
    ("offer_data_json",       "TEXT"),
    ("risk_data_json",        "TEXT"),
    ("investment_data_json",  "TEXT"),
    ("permits_data_json",     "TEXT"),
    ("renovation_data_json",  "TEXT"),
    ("crime_data_json",       "TEXT"),
    ("buyer_context",         "TEXT"),
]

_COMPS_MIGRATIONS: list[tuple[str, str]] = [
    ("pct_over_asking", "FLOAT"),
]


async def _migrate_analyses(conn) -> None:
    """Add any missing columns to the analyses table (SQLite-compatible)."""
    result = await conn.execute(text("PRAGMA table_info(analyses)"))
    existing = {row[1] for row in result.fetchall()}
    for col_name, col_type in _ANALYSES_MIGRATIONS:
        if col_name not in existing:
            await conn.execute(
                text(f"ALTER TABLE analyses ADD COLUMN {col_name} {col_type}")
            )
            log.info("Migration: added analyses.%s", col_name)


async def _migrate_comps(conn) -> None:
    """Add any missing columns to the comps table (SQLite-compatible)."""
    result = await conn.execute(text("PRAGMA table_info(comps)"))
    existing = {row[1] for row in result.fetchall()}
    for col_name, col_type in _COMPS_MIGRATIONS:
        if col_name not in existing:
            await conn.execute(
                text(f"ALTER TABLE comps ADD COLUMN {col_name} {col_type}")
            )
            log.info("Migration: added comps.%s", col_name)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_analyses(conn)
        await _migrate_comps(conn)


async def get_db():
    async with SessionLocal() as session:
        yield session
