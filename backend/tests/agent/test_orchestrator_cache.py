"""
Tests for the analysis result cache in run_agent.
A cache hit should skip Claude entirely and stream stored events from the DB.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ADDRESS = "450 Sanchez St, San Francisco, CA 94114"
ADDRESS_MATCHED = "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114"

FAKE_GEO = {
    "address_matched": ADDRESS_MATCHED,
    "latitude": 37.7612,
    "longitude": -122.4313,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94114",
}

FAKE_PROPERTY = {
    "address_matched": ADDRESS_MATCHED,
    "latitude": 37.7612,
    "longitude": -122.4313,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94114",
    "price": 1_250_000,
    "bedrooms": 3,
    "bathrooms": 2.0,
    "sqft": 1800,
    "year_built": 1928,
    "lot_size": 2500,
    "property_type": "SINGLE_FAMILY",
    "hoa_fee": None,
    "days_on_market": 5,
    "price_history": [],
    "avm_estimate": 1_300_000,
    "source": "homeharvest",
}

FAKE_OFFER = {
    "offer_low": 1_200_000,
    "offer_recommended": 1_250_000,
    "offer_high": 1_300_000,
    "posture": "competitive",
}

FAKE_RISK = {
    "overall_risk": "Moderate",
    "score": 4.0,
    "risk_factors": [],
}

FAKE_INVESTMENT = {
    "investment_rating": "Hold",
    "gross_yield_pct": 3.1,
}


async def _make_seeded_db(with_permits: bool = False):
    """Create an in-memory SQLite DB pre-seeded with one Listing + Analysis."""
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from db.models import Base, Listing, Analysis

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        listing = Listing(
            address_input=ADDRESS,
            address_matched=ADDRESS_MATCHED,
            latitude=FAKE_PROPERTY["latitude"],
            longitude=FAKE_PROPERTY["longitude"],
            county="San Francisco",
            state="CA",
            zip_code="94114",
            price=FAKE_PROPERTY["price"],
        )
        db.add(listing)
        await db.flush()

        kwargs = dict(
            listing_id=listing.id,
            offer_low=FAKE_OFFER["offer_low"],
            offer_recommended=FAKE_OFFER["offer_recommended"],
            offer_high=FAKE_OFFER["offer_high"],
            risk_level="Moderate",
            investment_rating="Hold",
            property_data_json=json.dumps(FAKE_PROPERTY),
            neighborhood_data_json=json.dumps({"median_home_value": 950_000}),
            offer_data_json=json.dumps(FAKE_OFFER),
            risk_data_json=json.dumps(FAKE_RISK),
            investment_data_json=json.dumps(FAKE_INVESTMENT),
            rationale="This is a solid property.",
        )
        if with_permits:
            kwargs["permits_data_json"] = json.dumps({"open_permits_count": 0, "permits": [], "complaints": []})
        analysis = Analysis(**kwargs)
        db.add(analysis)
        await db.commit()

    return Session, engine


async def collect_events_with_db(db, force_refresh: bool = False) -> list[dict]:
    from agent.orchestrator import run_agent

    events = []
    async for chunk in run_agent(ADDRESS, buyer_context="", db=db, force_refresh=force_refresh):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


# ---------------------------------------------------------------------------
# Cache hit behaviour
# ---------------------------------------------------------------------------

class TestCacheHit:
    async def test_cache_hit_skips_claude_api(self):
        """When a cached Analysis exists, Claude is never called."""
        Session, engine = await _make_seeded_db()
        async with Session() as db:
            with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
                 patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                mock_client = AsyncMock()
                mock_cls.return_value = mock_client

                await collect_events_with_db(db)

        mock_client.messages.create.assert_not_called()
        await engine.dispose()

    async def test_cache_hit_emits_property_tool_result(self):
        """Cache hit emits a tool_result for lookup_property_by_address."""
        Session, engine = await _make_seeded_db()
        async with Session() as db:
            with patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                events = await collect_events_with_db(db)

        tool_results = [e for e in events if e.get("type") == "tool_result"]
        tools = [e["tool"] for e in tool_results]
        assert "lookup_property_by_address" in tools
        prop_event = next(e for e in tool_results if e["tool"] == "lookup_property_by_address")
        assert prop_event["result"]["price"] == FAKE_PROPERTY["price"]
        await engine.dispose()

    async def test_cache_hit_emits_offer_tool_result(self):
        """Cache hit emits a tool_result for recommend_offer."""
        Session, engine = await _make_seeded_db()
        async with Session() as db:
            with patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                events = await collect_events_with_db(db)

        tool_results = [e for e in events if e.get("type") == "tool_result"]
        tools = [e["tool"] for e in tool_results]
        assert "recommend_offer" in tools
        await engine.dispose()

    async def test_cache_hit_emits_done(self):
        """Cache hit stream ends with a done event."""
        Session, engine = await _make_seeded_db()
        async with Session() as db:
            with patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                events = await collect_events_with_db(db)

        assert events[-1]["type"] == "done"
        await engine.dispose()

    async def test_cache_hit_emits_analysis_id(self):
        """Cache hit emits analysis_id event with the existing analysis id."""
        Session, engine = await _make_seeded_db()
        async with Session() as db:
            with patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                events = await collect_events_with_db(db)

        id_events = [e for e in events if e.get("type") == "analysis_id"]
        assert len(id_events) == 1
        assert isinstance(id_events[0]["id"], int)
        await engine.dispose()

    async def test_cache_hit_emits_rationale_as_text(self):
        """Cache hit emits the stored rationale as a text event."""
        Session, engine = await _make_seeded_db()
        async with Session() as db:
            with patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                events = await collect_events_with_db(db)

        text_events = [e for e in events if e.get("type") == "text"]
        assert any("solid property" in (e.get("text") or "") for e in text_events)
        await engine.dispose()

    async def test_cache_hit_emits_permits_when_stored(self):
        """Cache hit emits fetch_sf_permits result when permits_data_json is set."""
        Session, engine = await _make_seeded_db(with_permits=True)
        async with Session() as db:
            with patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                events = await collect_events_with_db(db)

        tool_results = [e for e in events if e.get("type") == "tool_result"]
        tools = [e["tool"] for e in tool_results]
        assert "fetch_sf_permits" in tools
        await engine.dispose()


# ---------------------------------------------------------------------------
# force_refresh bypasses cache
# ---------------------------------------------------------------------------

class TestForceRefresh:
    async def test_force_refresh_bypasses_cache(self):
        """With force_refresh=True, Claude IS called even when cache exists."""
        Session, engine = await _make_seeded_db()

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        async with Session() as db:
            with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
                 patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                mock_client = AsyncMock()
                mock_cls.return_value = mock_client
                mock_client.messages.create.return_value = end_turn_response

                await collect_events_with_db(db, force_refresh=True)

        mock_client.messages.create.assert_called()
        await engine.dispose()


# ---------------------------------------------------------------------------
# Geocode failure falls through to live pipeline
# ---------------------------------------------------------------------------

class TestGeocodeFailure:
    async def test_geocode_failure_falls_through_to_live(self):
        """If _geocode raises, run_agent falls through to the live pipeline."""
        Session, engine = await _make_seeded_db()

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        async with Session() as db:
            with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
                 patch("agent.orchestrator._geocode", new_callable=AsyncMock, side_effect=ValueError("geocode failed")):
                mock_client = AsyncMock()
                mock_cls.return_value = mock_client
                mock_client.messages.create.return_value = end_turn_response

                events = await collect_events_with_db(db)

        # Should have fallen through — Claude was called, stream ended normally
        mock_client.messages.create.assert_called()
        assert any(e["type"] == "done" for e in events)
        await engine.dispose()


# ---------------------------------------------------------------------------
# Unit-aware cache: cross-unit collisions must not hit the cache
# ---------------------------------------------------------------------------

UNIT_BUILDING_MATCHED = "1250 ELLIS ST, SAN FRANCISCO, CA 94109"
# Geocoder returns the bare street address (unit stripped) for any unit in the building
UNIT1_GEO = {
    "address_matched": UNIT_BUILDING_MATCHED,
    "latitude": 37.7832,
    "longitude": -122.4272,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94109",
}
UNIT2_GEO = {
    "address_matched": UNIT_BUILDING_MATCHED,
    "latitude": 37.7832,
    "longitude": -122.4272,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94109",
}

UNIT1_PROPERTY = {
    "address_input": "1250 Ellis St #1, San Francisco, CA 94109",
    "address_matched": "1250 ELLIS ST UNIT 1, SAN FRANCISCO, CA 94109",
    "latitude": 37.7832,
    "longitude": -122.4272,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94109",
    "unit": "1",
    "price": 750_000,
    "bedrooms": 1,
    "bathrooms": 1.0,
    "sqft": 650,
    "year_built": 1962,
    "property_type": "CONDO",
    "hoa_fee": 450,
    "source": "homeharvest",
}

UNIT2_PROPERTY = {
    "address_input": "1250 Ellis St #2, San Francisco, CA 94109",
    "address_matched": "1250 ELLIS ST UNIT 2, SAN FRANCISCO, CA 94109",
    "latitude": 37.7832,
    "longitude": -122.4272,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94109",
    "unit": "2",
    "price": 850_000,
    "bedrooms": 2,
    "bathrooms": 2.0,
    "sqft": 900,
    "year_built": 1962,
    "property_type": "CONDO",
    "hoa_fee": 500,
    "source": "homeharvest",
}


async def _make_unit1_db(unit_qualified_key: bool = False):
    """
    Seed DB with a cached analysis for unit #1 of 1250 Ellis St.

    unit_qualified_key=False → simulates the pre-fix buggy state where the
    geocoder-bare address is used as the DB key, causing cross-unit collisions.
    unit_qualified_key=True  → simulates the post-fix state where the unit is
    included in the key so each unit is cached separately.
    """
    from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
    from db.models import Base, Listing, Analysis

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        # Pre-fix: bare geocoder address; post-fix: unit-qualified address
        db_key = (
            "1250 ELLIS ST UNIT 1, SAN FRANCISCO, CA 94109"
            if unit_qualified_key
            else UNIT_BUILDING_MATCHED
        )
        listing = Listing(
            address_input="1250 Ellis St #1, San Francisco, CA 94109",
            address_matched=db_key,
            latitude=UNIT1_PROPERTY["latitude"],
            longitude=UNIT1_PROPERTY["longitude"],
            county="San Francisco",
            state="CA",
            zip_code="94109",
            price=UNIT1_PROPERTY["price"],
        )
        db.add(listing)
        await db.flush()

        analysis = Analysis(
            listing_id=listing.id,
            offer_recommended=740_000,
            offer_low=720_000,
            offer_high=760_000,
            risk_level="Low",
            investment_rating="Buy",
            property_data_json=json.dumps(UNIT1_PROPERTY),
            neighborhood_data_json=json.dumps({}),
            offer_data_json=json.dumps({"offer_recommended": 740_000}),
            risk_data_json=json.dumps({"overall_risk": "Low"}),
            investment_data_json=json.dumps({}),
            rationale="Unit 1 analysis.",
        )
        db.add(analysis)
        await db.commit()

    return Session, engine


class TestUnitAwareCache:
    async def test_different_unit_does_not_hit_unit1_cache(self):
        """
        Requesting analysis for unit #2 must NOT return cached data from unit #1,
        even though the geocoder returns the same bare address_matched for both.
        Pre-fix: the DB stores unit #1 under the bare geocoder key, so a unit #2
        request collides and gets a spurious cache hit.
        Post-fix: the cache key is unit-qualified, so unit #2 misses the cache.
        """
        # Seed with the bare (pre-fix) key — this is the collision scenario
        Session, engine = await _make_unit1_db(unit_qualified_key=False)

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Unit 2 analysis."
        end_turn_response.content = [text_block]

        async with Session() as db:
            with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
                 patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=UNIT2_GEO):
                mock_client = AsyncMock()
                mock_cls.return_value = mock_client
                mock_client.messages.create.return_value = end_turn_response

                events = []
                from agent.orchestrator import run_agent
                async for chunk in run_agent("1250 Ellis St #2, San Francisco, CA 94109", db=db):
                    if chunk.startswith("data: "):
                        events.append(json.loads(chunk[6:]))

        # Claude MUST have been called — unit #1's cache must not have been served for #2
        mock_client.messages.create.assert_called()
        # The streamed text should not contain "Unit 1"
        text_events = [e for e in events if e.get("type") == "text"]
        assert not any("Unit 1" in (e.get("text") or "") for e in text_events)
        await engine.dispose()

    async def test_same_unit_hits_own_cache(self):
        """
        Requesting analysis for unit #1 again should hit the unit #1 cache,
        not run the live pipeline.
        Post-fix: unit-qualified key is used, so unit #1 finds its own cache entry.
        """
        # Seed with the unit-qualified (post-fix) key
        Session, engine = await _make_unit1_db(unit_qualified_key=True)

        async with Session() as db:
            with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
                 patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=UNIT1_GEO):
                mock_client = AsyncMock()
                mock_cls.return_value = mock_client

                events = []
                from agent.orchestrator import run_agent
                async for chunk in run_agent("1250 Ellis St #1, San Francisco, CA 94109", db=db):
                    if chunk.startswith("data: "):
                        events.append(json.loads(chunk[6:]))

        # Cache hit — Claude should NOT have been called
        mock_client.messages.create.assert_not_called()
        # Should emit the cached unit 1 data
        tool_results = [e for e in events if e.get("type") == "tool_result"]
        prop = next((e for e in tool_results if e.get("tool") == "lookup_property_by_address"), None)
        assert prop is not None
        assert prop["result"]["price"] == UNIT1_PROPERTY["price"]
        await engine.dispose()

    async def test_no_unit_address_still_uses_geocoder_key(self):
        """
        Addresses without unit info should still use the bare geocoder key,
        so existing non-unit caches continue to work normally.
        """
        Session, engine = await _make_seeded_db()
        async with Session() as db:
            with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
                 patch("agent.orchestrator._geocode", new_callable=AsyncMock, return_value=FAKE_GEO):
                mock_client = AsyncMock()
                mock_cls.return_value = mock_client

                events = await collect_events_with_db(db)

        # Should be a cache hit (non-unit address)
        mock_client.messages.create.assert_not_called()
        assert any(e["type"] == "done" for e in events)
        await engine.dispose()
