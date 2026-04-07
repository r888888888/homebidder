"""
Phase 9 orchestrator persistence tests.
Tests that run_agent writes Listing, Analysis, and Comp records to DB
and emits an analysis_id SSE event.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_comps_response():
    comps_block = MagicMock()
    comps_block.type = "tool_use"
    comps_block.name = "fetch_comps"
    comps_block.id = "tu_comps_persist"
    comps_block.input = {
        "address": "450 Sanchez St, San Francisco, CA 94114",
        "city": "San Francisco",
        "state": "CA",
        "zip_code": "94114",
    }

    tool_use_response = MagicMock()
    tool_use_response.stop_reason = "tool_use"
    tool_use_response.content = [comps_block]

    end_turn_response = MagicMock()
    end_turn_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Analysis complete."
    end_turn_response.content = [text_block]

    return tool_use_response, end_turn_response


FAKE_PROPERTY = {
    "address_matched": "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
    "address_input": "450 Sanchez St, San Francisco, CA 94114",
    "latitude": 37.7612,
    "longitude": -122.4313,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94114",
    "price": 1_250_000.0,
    "bedrooms": 3,
    "bathrooms": 2.0,
    "sqft": 1800,
    "year_built": 1928,
    "property_type": "SINGLE_FAMILY",
}

FAKE_COMPS = {
    "comps": [
        {
            "address": "100 Comp St",
            "sold_price": 1_100_000,
            "sold_date": "2026-02-01",
            "bedrooms": 3,
            "bathrooms": 2.0,
            "sqft": 1700,
            "price_per_sqft": 647.0,
            "pct_over_asking": 4.76,
            "distance_miles": 0.3,
        }
    ],
    "subject_sale": None,
}

FAKE_OFFER = {
    "offer_recommended": 1_200_000,
    "offer_low": 1_170_000,
    "offer_high": 1_250_000,
    "posture": "competitive",
}

FAKE_RISK = {
    "overall_risk": "Moderate",
    "score": 4.0,
}

FAKE_INVESTMENT = {
    "investment_rating": "Buy",
    "gross_yield_pct": 3.1,
}


async def _collect_events_with_db(address, db=None):
    from agent.orchestrator import run_agent
    events = []
    async for chunk in run_agent(address, db=db):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


def _mock_patches(side_effects, property_result=None):
    """Build common patch context for orchestrator tests."""
    return [
        patch("agent.orchestrator.anthropic.AsyncAnthropic"),
        patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS),
        patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}),
        patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0),
        patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER),
        patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK),
        patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}),
        patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}),
        patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}),
        patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

async def test_analysis_id_event_not_emitted_when_db_is_none():
    """No analysis_id event when db=None (default behavior unchanged)."""
    tool_use_response, end_turn_response = _make_comps_response()

    with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
         patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
         patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
         patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
         patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER), \
         patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
         patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
         patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}), \
         patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
         patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT):

        mock_client = AsyncMock()
        mock_cls.return_value = mock_client
        mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

        events = await _collect_events_with_db("450 Sanchez St, San Francisco, CA 94114", db=None)

    analysis_id_events = [e for e in events if e.get("type") == "analysis_id"]
    assert len(analysis_id_events) == 0


async def test_analysis_id_event_emitted_when_db_provided():
    """analysis_id SSE event is emitted when a real DB session is provided."""
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from db.models import Base

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tool_use_response, end_turn_response = _make_comps_response()

    async with AsyncSessionLocal() as db:
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await _collect_events_with_db(
                "450 Sanchez St, San Francisco, CA 94114", db=db
            )

    analysis_id_events = [e for e in events if e.get("type") == "analysis_id"]
    assert len(analysis_id_events) == 1
    assert isinstance(analysis_id_events[0]["id"], int)
    assert analysis_id_events[0]["id"] > 0

    await engine.dispose()


async def test_listing_is_upserted_in_db():
    """After end_turn, a Listing exists in DB with correct address_matched."""
    import os
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from db.models import Base, Listing

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tool_use_response, end_turn_response = _make_comps_response()

    async with AsyncSessionLocal() as db:
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            await _collect_events_with_db(
                "450 Sanchez St, San Francisco, CA 94114", db=db
            )

    async with AsyncSessionLocal() as verify_db:
        result = await verify_db.execute(select(Listing))
        listings = result.scalars().all()
        assert len(listings) == 1
        # address_matched comes from property_result; since no property lookup was mocked,
        # it falls back to the address_input
        assert listings[0].address_input == "450 Sanchez St, San Francisco, CA 94114"

    await engine.dispose()


async def test_analysis_record_created_in_db():
    """Analysis record is created with offer_recommended, risk_level, investment_rating."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from db.models import Base, Analysis

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tool_use_response, end_turn_response = _make_comps_response()

    async with AsyncSessionLocal() as db:
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            await _collect_events_with_db(
                "450 Sanchez St, San Francisco, CA 94114", db=db
            )

    async with AsyncSessionLocal() as verify_db:
        result = await verify_db.execute(select(Analysis))
        analyses = result.scalars().all()
        assert len(analyses) == 1
        a = analyses[0]
        assert a.offer_recommended == FAKE_OFFER["offer_recommended"]
        assert a.risk_level == FAKE_RISK["overall_risk"]
        assert a.investment_rating == FAKE_INVESTMENT["investment_rating"]

    await engine.dispose()


async def test_comps_saved_in_db():
    """Comp records are saved linked to the Analysis."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from db.models import Base, Comp

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tool_use_response, end_turn_response = _make_comps_response()

    async with AsyncSessionLocal() as db:
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            await _collect_events_with_db(
                "450 Sanchez St, San Francisco, CA 94114", db=db
            )

    async with AsyncSessionLocal() as verify_db:
        result = await verify_db.execute(select(Comp))
        comps = result.scalars().all()
        assert len(comps) == 1
        assert comps[0].address == "100 Comp St"
        assert comps[0].sold_price == 1_100_000
        assert comps[0].pct_over_asking == pytest.approx(4.76)

    await engine.dispose()


async def test_analysis_persisted_when_property_lookup_raises():
    """Analysis IS saved even when lookup_property_by_address fails (geocoder error)."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from db.models import Base, Analysis

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Claude gets an error for lookup_property_by_address and writes a short failure response
    end_turn_response = MagicMock()
    end_turn_response.stop_reason = "end_turn"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "I could not find this address."
    end_turn_response.content = [text_block]

    async with AsyncSessionLocal() as db:
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            # Claude returns end_turn immediately with no tool calls — simulates the
            # case where lookup_property_by_address failed and Claude gave up.
            mock_client.messages.create.side_effect = [end_turn_response]

            events = await _collect_events_with_db(
                "95 Lake Vista Ave, Daly City, CA 94015", db=db
            )

    analysis_id_events = [e for e in events if e.get("type") == "analysis_id"]
    assert len(analysis_id_events) == 1

    async with AsyncSessionLocal() as verify_db:
        result = await verify_db.execute(select(Analysis))
        analyses = result.scalars().all()
        assert len(analyses) == 1

    await engine.dispose()


async def test_analysis_persisted_when_max_tokens():
    """Analysis IS saved even when the final narrative hits max_tokens (not end_turn)."""
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import select
    from db.models import Base, Analysis

    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    tool_use_response, _ = _make_comps_response()

    # Simulate Claude truncating the final narrative at the token limit
    max_tokens_response = MagicMock()
    max_tokens_response.stop_reason = "max_tokens"
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "This is a long analysis that got cut off at the token lim"
    max_tokens_response.content = [text_block]

    async with AsyncSessionLocal() as db:
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=FAKE_OFFER), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value={"rent_estimate": 4000}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            # First call: Claude requests fetch_comps. Second call: narrative truncated.
            mock_client.messages.create.side_effect = [tool_use_response, max_tokens_response]

            events = await _collect_events_with_db(
                "450 Sanchez St, San Francisco, CA 94114", db=db
            )

    analysis_id_events = [e for e in events if e.get("type") == "analysis_id"]
    assert len(analysis_id_events) == 1, "analysis_id event must be emitted even on max_tokens"
    assert isinstance(analysis_id_events[0]["id"], int)

    async with AsyncSessionLocal() as verify_db:
        result = await verify_db.execute(select(Analysis))
        analyses = result.scalars().all()
        assert len(analyses) == 1
        assert analyses[0].offer_recommended == FAKE_OFFER["offer_recommended"]

    await engine.dispose()
