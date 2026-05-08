"""
Tests that init_db() migrates an existing database that is missing columns
added after the initial schema was created.
"""
import pytest
import aiosqlite


@pytest.mark.asyncio
async def test_init_db_adds_missing_columns_to_existing_analyses_table(tmp_path):
    """
    Given a pre-existing analyses table that lacks the newer columns
    (risk_level, investment_rating, property_data_json, etc.),
    init_db() must add them without destroying existing rows.
    """
    import os
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    # Create the old-schema database with only the original columns.
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address_input TEXT NOT NULL,
                address_matched TEXT UNIQUE,
                latitude REAL, longitude REAL,
                county TEXT, state TEXT, zip_code TEXT,
                price REAL, bedrooms INTEGER, bathrooms REAL,
                sqft INTEGER, year_built INTEGER, lot_size REAL,
                property_type TEXT, avm_estimate REAL,
                neighborhood_context TEXT,
                scraped_at DATETIME
            )
        """)
        await conn.execute("""
            CREATE TABLE analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL REFERENCES listings(id),
                session_id TEXT,
                offer_low REAL, offer_high REAL, offer_recommended REAL,
                rationale TEXT, market_summary TEXT,
                created_at DATETIME
            )
        """)
        await conn.execute("""
            INSERT INTO listings (address_input, address_matched)
            VALUES ('711 Vienna St', '711 VIENNA ST, SAN FRANCISCO, CA, 94112')
        """)
        await conn.execute("""
            INSERT INTO analyses (listing_id, rationale)
            VALUES (1, 'old row preserved')
        """)
        await conn.commit()

    # Run init_db with the old database.
    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        # Re-import so the engine picks up the new URL
        import importlib
        import db as db_module
        importlib.reload(db_module)
        await db_module.init_db()
    finally:
        if old_url is not None:
            os.environ["DATABASE_URL"] = old_url
        else:
            del os.environ["DATABASE_URL"]
        importlib.reload(db_module)

    # All newer columns must now exist in the analyses table.
    async with aiosqlite.connect(str(db_path)) as conn:
        cursor = await conn.execute("PRAGMA table_info(analyses)")
        col_names = {row[1] async for row in cursor}

    expected_new_cols = {
        "risk_level",
        "investment_rating",
        "property_data_json",
        "neighborhood_data_json",
        "offer_data_json",
        "risk_data_json",
        "investment_data_json",
        "permits_data_json",
        "renovation_data_json",
        "crime_data_json",
        "buyer_context",
        "validation_data_json",
    }
    missing = expected_new_cols - col_names
    assert not missing, f"Columns not added by migration: {missing}"

    # Existing data must survive.
    async with aiosqlite.connect(str(db_path)) as conn:
        cursor = await conn.execute("SELECT rationale FROM analyses WHERE id = 1")
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == "old row preserved"


@pytest.mark.asyncio
async def test_init_db_adds_bidding_intent_to_seen_properties(tmp_path):
    """
    Given a pre-existing seen_properties table that lacks bidding_intent,
    init_db() must add the column without destroying existing rows.
    """
    import os
    db_path = tmp_path / "test.db"
    db_url = f"sqlite+aiosqlite:///{db_path}"

    # Create an old-schema seen_properties table.
    async with aiosqlite.connect(str(db_path)) as conn:
        await conn.execute("""
            CREATE TABLE users (
                id CHAR(36) PRIMARY KEY,
                email TEXT,
                hashed_password TEXT,
                is_active BOOLEAN DEFAULT 1,
                is_superuser BOOLEAN DEFAULT 0,
                is_verified BOOLEAN DEFAULT 0
            )
        """)
        await conn.execute("""
            CREATE TABLE listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                address_input TEXT NOT NULL,
                address_matched TEXT UNIQUE
            )
        """)
        await conn.execute("""
            CREATE TABLE analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                listing_id INTEGER NOT NULL REFERENCES listings(id),
                created_at DATETIME
            )
        """)
        await conn.execute("""
            CREATE TABLE seen_properties (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id CHAR(36) NOT NULL REFERENCES users(id),
                analysis_id INTEGER REFERENCES analyses(id),
                address_snapshot TEXT NOT NULL,
                quality TEXT NOT NULL,
                location TEXT NOT NULL,
                composite_score REAL NOT NULL,
                seen_at DATETIME,
                notes TEXT
            )
        """)
        # Seed legacy row to ensure migration preserves data.
        await conn.execute("""
            INSERT INTO users (id) VALUES ('00000000-0000-0000-0000-000000000001')
        """)
        await conn.execute("""
            INSERT INTO listings (address_input, address_matched)
            VALUES ('99 Legacy St', '99 LEGACY ST')
        """)
        await conn.execute("""
            INSERT INTO analyses (listing_id) VALUES (1)
        """)
        await conn.execute("""
            INSERT INTO seen_properties
            (user_id, analysis_id, address_snapshot, quality, location, composite_score, seen_at, notes)
            VALUES
            ('00000000-0000-0000-0000-000000000001', 1, '99 Legacy St',
             'good', 'good', 0.875, '2026-04-01T00:00:00', 'old row')
        """)
        await conn.commit()

    old_url = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = db_url
    try:
        import importlib
        import db as db_module
        importlib.reload(db_module)
        await db_module.init_db()
    finally:
        if old_url is not None:
            os.environ["DATABASE_URL"] = old_url
        else:
            del os.environ["DATABASE_URL"]
        importlib.reload(db_module)

    # bidding_intent column must now exist.
    async with aiosqlite.connect(str(db_path)) as conn:
        cursor = await conn.execute("PRAGMA table_info(seen_properties)")
        col_names = {row[1] async for row in cursor}
    assert "bidding_intent" in col_names, "Migration failed to add bidding_intent column"

    # Legacy row must survive with NULL bidding_intent and unchanged composite_score.
    async with aiosqlite.connect(str(db_path)) as conn:
        cursor = await conn.execute(
            "SELECT composite_score, bidding_intent, notes FROM seen_properties WHERE id = 1"
        )
        row = await cursor.fetchone()
    assert row is not None
    assert row[0] == 0.875
    assert row[1] is None
    assert row[2] == "old row"
