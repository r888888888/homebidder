from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import event, text
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

_engine_kwargs: dict = {"echo": False}

engine = create_async_engine(DATABASE_URL, **_engine_kwargs)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

# Enable FK enforcement for every SQLite connection (no-op on other DBs).
@event.listens_for(engine.sync_engine, "connect")
def _set_sqlite_pragma(dbapi_conn, _connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.close()

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
    ("user_id",               "CHAR(36)"),
]

_COMPS_MIGRATIONS: list[tuple[str, str]] = [
    ("pct_over_asking", "FLOAT"),
]

_USERS_MIGRATIONS: list[tuple[str, str]] = [
    ("display_name",         "VARCHAR(128)"),
    ("subscription_tier",    "VARCHAR(16) NOT NULL DEFAULT 'buyer'"),
    ("stripe_customer_id",   "VARCHAR(128)"),
    ("stripe_subscription_id", "VARCHAR(128)"),
    ("subscription_status",  "VARCHAR(32)"),
    ("is_grandfathered",     "INTEGER NOT NULL DEFAULT 0"),
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


async def _migrate_users(conn) -> None:
    """Add subscription/Stripe columns to the users table; grandfather pre-existing users."""
    result = await conn.execute(text("PRAGMA table_info(users)"))
    existing = {row[1] for row in result.fetchall()}
    # Track whether this is the first time we add the is_grandfathered column so
    # we know to run the one-time grandfathering UPDATE only on this deploy.
    is_first_migration = "is_grandfathered" not in existing
    for col_name, col_type in _USERS_MIGRATIONS:
        if col_name not in existing:
            await conn.execute(
                text(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            )
            log.info("Migration: added users.%s", col_name)
    if is_first_migration:
        # Promote every user who existed before the payment system (no Stripe
        # subscription yet) to the Investor tier for free, permanently.
        await conn.execute(
            text(
                "UPDATE users "
                "SET subscription_tier = 'investor', is_grandfathered = 1 "
                "WHERE stripe_subscription_id IS NULL"
            )
        )
        log.info("Grandfathering: promoted all pre-Stripe users to Investor tier")


async def _promote_first_user_to_superuser(conn) -> None:
    """If no superuser exists, promote the first-created user (by rowid) to superuser.

    Runs at every startup; idempotent — exits immediately when a superuser already exists.
    """
    result = await conn.execute(text("SELECT COUNT(*) FROM users WHERE is_superuser = 1"))
    if result.scalar_one() > 0:
        return  # superuser already exists

    result = await conn.execute(text("SELECT id FROM users ORDER BY rowid LIMIT 1"))
    row = result.fetchone()
    if row:
        await conn.execute(
            text("UPDATE users SET is_superuser = 1 WHERE id = :id"),
            {"id": row[0]},
        )
        log.info("Promoted first user to superuser: %s", row[0])


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await _migrate_analyses(conn)
        await _migrate_comps(conn)
        await _migrate_users(conn)
        await _promote_first_user_to_superuser(conn)


async def get_db():
    async with SessionLocal() as session:
        yield session
