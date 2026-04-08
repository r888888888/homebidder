"""
Tests for validation mode: when a property has already sold, the orchestrator
computes and emits a validation_result SSE event comparing our estimate to actual.
All Anthropic API calls and tool functions are mocked.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROPERTY_RESULT = {
    "address_matched": "400 HEARST AVE, SAN FRANCISCO, CA, 94112",
    "latitude": 37.7612,
    "longitude": -122.4313,
    "county": "San Francisco",
    "state": "CA",
    "zip_code": "94112",
    "price": 1_200_000.0,
    "bedrooms": 3,
    "bathrooms": 2.0,
    "sqft": 1800,
    "year_built": 1928,
    "lot_size": 2500,
    "property_type": "SINGLE_FAMILY",
    "hoa_fee": None,
    "days_on_market": None,
    "price_history": [],
    "avm_estimate": None,
    "source": "homeharvest",
    "description_signals": {},
}

OFFER_RESULT = {
    "list_price": 1_200_000,
    "fair_value_estimate": 1_200_000,
    "fair_value_breakdown": {
        "method": "median_comp_anchor",
        "base_comp_median": 1_200_000,
        "lot_adjustment_pct": 0,
        "sqft_adjustment_pct": 0,
    },
    "fair_value_confidence_interval": {
        "low": 1_100_000,
        "high": 1_300_000,
        "ci_pct": 8.0,
        "confidence": "moderate",
        "factors": [],
    },
    "offer_low": 1_150_000,
    "offer_recommended": 1_200_000,
    "offer_high": 1_280_000,
    "posture": "at-market",
    "offer_range_band_pct": 4.0,
    "spread_vs_list_pct": 0.0,
    "condition_signals": [],
    "median_pct_over_asking": 2.0,
    "pct_sold_over_asking": 60.0,
    "offer_review_advisory": None,
    "contingency_recommendation": {
        "waive_appraisal": False,
        "waive_loan": False,
        "keep_inspection": True,
    },
    "hoa_equivalent_sfh_value": None,
}

NEIGHBORHOOD_RESULT = {"zip_code": "94112"}
MARKET_TRENDS = {"zip_code": "94112", "months": [], "trend": "flat"}
FHFA = {"zip_code": "94112", "hpi_trend": "flat"}
HAZARDS = {"alquist_priolo": False}
MORTGAGE_RATES = {"rate_30yr": 6.5}
BA_VALUE = {"adu_potential": False}
INVESTMENT = {"investment_rating": "Hold", "gross_yield_pct": 3.2}
RISK = {"overall_risk": "Moderate", "score": 40, "factors": []}


def _make_tool_use_block(name: str, block_id: str, inputs: dict) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.id = block_id
    block.input = inputs
    return block


def _make_text_block(text: str) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = text
    return block


async def collect_events(address: str = "400 Hearst Ave, SF CA 94112") -> list[dict]:
    from agent.orchestrator import run_agent

    events = []
    async for chunk in run_agent(address):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestValidationResultEvent:
    async def test_validation_result_emitted_when_subject_sale_present(self):
        """When fetch_comps detects the subject property sold recently,
        a validation_result event is emitted after recommend_offer."""
        subject_sale = {
            "sold_price": 1_350_000,
            "sold_date": "2026-01-15",
            "address": "400 Hearst Ave",
        }
        comps_full = {"comps": [], "subject_sale": subject_sale}

        lookup_block = _make_tool_use_block(
            "lookup_property_by_address", "tu_1",
            {"address": "400 Hearst Ave, SF CA 94112"},
        )
        neighborhood_block = _make_tool_use_block(
            "fetch_neighborhood_context", "tu_2",
            {"address": "400 Hearst Ave", "city": "San Francisco", "state": "CA",
             "county": "San Francisco", "zip_code": "94112"},
        )
        comps_block = _make_tool_use_block(
            "fetch_comps", "tu_3",
            {"address": "400 Hearst Ave", "city": "San Francisco", "state": "CA",
             "zip_code": "94112"},
        )

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block, neighborhood_block, comps_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        end_turn_response.content = [_make_text_block("Retrospective analysis.")]

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock, return_value=PROPERTY_RESULT), \
             patch("agent.orchestrator.fetch_neighborhood_context", new_callable=AsyncMock, return_value=NEIGHBORHOOD_RESULT), \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=comps_full), \
             patch("agent.orchestrator.fetch_market_trends", new_callable=AsyncMock, return_value=MARKET_TRENDS), \
             patch("agent.orchestrator.fetch_fhfa_hpi", new_callable=AsyncMock, return_value=FHFA), \
             patch("agent.orchestrator.fetch_ca_hazard_zones", new_callable=AsyncMock, return_value=HAZARDS), \
             patch("agent.orchestrator.fetch_sf_permits", new_callable=AsyncMock, return_value=None), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value=MORTGAGE_RATES), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value=BA_VALUE), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=INVESTMENT), \
             patch("agent.orchestrator.recommend_offer", return_value=OFFER_RESULT), \
             patch("agent.orchestrator.assess_risk", return_value=RISK), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.5):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events()

        validation_events = [e for e in events if e.get("type") == "validation_result"]
        assert len(validation_events) == 1

        vr = validation_events[0]["result"]
        assert vr["actual_sold_price"] == 1_350_000
        assert vr["estimated_price"] == 1_200_000
        # error_pct = (1_200_000 - 1_350_000) / 1_350_000 * 100 ≈ -11.1%
        assert vr["error_pct"] == pytest.approx(-11.1, abs=0.2)
        assert vr["within_ci"] is False   # 1_350_000 > ci_high 1_300_000
        assert vr["sold_date"] == "2026-01-15"

    async def test_no_validation_event_when_subject_sale_absent(self):
        """When fetch_comps returns no subject_sale, no validation_result event is emitted."""
        comps_full = {"comps": [], "subject_sale": None}

        lookup_block = _make_tool_use_block(
            "lookup_property_by_address", "tu_1",
            {"address": "450 Sanchez St, SF CA 94114"},
        )
        neighborhood_block = _make_tool_use_block(
            "fetch_neighborhood_context", "tu_2",
            {"address": "450 Sanchez St", "city": "San Francisco", "state": "CA",
             "county": "San Francisco", "zip_code": "94114"},
        )
        comps_block = _make_tool_use_block(
            "fetch_comps", "tu_3",
            {"address": "450 Sanchez St", "city": "San Francisco", "state": "CA",
             "zip_code": "94114"},
        )

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block, neighborhood_block, comps_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        end_turn_response.content = [_make_text_block("Normal analysis.")]

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock, return_value=PROPERTY_RESULT), \
             patch("agent.orchestrator.fetch_neighborhood_context", new_callable=AsyncMock, return_value=NEIGHBORHOOD_RESULT), \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=comps_full), \
             patch("agent.orchestrator.fetch_market_trends", new_callable=AsyncMock, return_value=MARKET_TRENDS), \
             patch("agent.orchestrator.fetch_fhfa_hpi", new_callable=AsyncMock, return_value=FHFA), \
             patch("agent.orchestrator.fetch_ca_hazard_zones", new_callable=AsyncMock, return_value=HAZARDS), \
             patch("agent.orchestrator.fetch_sf_permits", new_callable=AsyncMock, return_value=None), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value=MORTGAGE_RATES), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value=BA_VALUE), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=INVESTMENT), \
             patch("agent.orchestrator.recommend_offer", return_value=OFFER_RESULT), \
             patch("agent.orchestrator.assess_risk", return_value=RISK), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.5):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events("450 Sanchez St, SF CA 94114")

        validation_events = [e for e in events if e.get("type") == "validation_result"]
        assert len(validation_events) == 0

    async def test_within_ci_true_when_actual_inside_confidence_interval(self):
        """within_ci is True when actual sale price falls within the CI range."""
        subject_sale = {
            "sold_price": 1_200_000,   # exactly at fair_value_estimate, inside CI [1.1M, 1.3M]
            "sold_date": "2026-02-01",
            "address": "400 Hearst Ave",
        }
        comps_full = {"comps": [], "subject_sale": subject_sale}

        lookup_block = _make_tool_use_block(
            "lookup_property_by_address", "tu_1",
            {"address": "400 Hearst Ave, SF CA 94112"},
        )
        neighborhood_block = _make_tool_use_block(
            "fetch_neighborhood_context", "tu_2",
            {"address": "400 Hearst Ave", "city": "San Francisco", "state": "CA",
             "county": "San Francisco", "zip_code": "94112"},
        )
        comps_block = _make_tool_use_block(
            "fetch_comps", "tu_3",
            {"address": "400 Hearst Ave", "city": "San Francisco", "state": "CA",
             "zip_code": "94112"},
        )

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block, neighborhood_block, comps_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        end_turn_response.content = [_make_text_block("Analysis.")]

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock, return_value=PROPERTY_RESULT), \
             patch("agent.orchestrator.fetch_neighborhood_context", new_callable=AsyncMock, return_value=NEIGHBORHOOD_RESULT), \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=comps_full), \
             patch("agent.orchestrator.fetch_market_trends", new_callable=AsyncMock, return_value=MARKET_TRENDS), \
             patch("agent.orchestrator.fetch_fhfa_hpi", new_callable=AsyncMock, return_value=FHFA), \
             patch("agent.orchestrator.fetch_ca_hazard_zones", new_callable=AsyncMock, return_value=HAZARDS), \
             patch("agent.orchestrator.fetch_sf_permits", new_callable=AsyncMock, return_value=None), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value=MORTGAGE_RATES), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value=BA_VALUE), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=INVESTMENT), \
             patch("agent.orchestrator.recommend_offer", return_value=OFFER_RESULT), \
             patch("agent.orchestrator.assess_risk", return_value=RISK), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.5):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events()

        validation_events = [e for e in events if e.get("type") == "validation_result"]
        assert len(validation_events) == 1
        assert validation_events[0]["result"]["within_ci"] is True

    async def test_fetch_comps_sse_event_sends_only_comps_list(self):
        """The SSE tool_result event for fetch_comps contains a list (not a dict),
        so CompsCard in the frontend does not break."""
        subject_sale = {
            "sold_price": 1_350_000,
            "sold_date": "2026-01-15",
            "address": "400 Hearst Ave",
        }
        comp_item = {"address": "402 Hearst Ave", "sold_price": 1_100_000}
        comps_full = {"comps": [comp_item], "subject_sale": subject_sale}

        lookup_block = _make_tool_use_block(
            "lookup_property_by_address", "tu_1",
            {"address": "400 Hearst Ave, SF CA 94112"},
        )
        comps_block = _make_tool_use_block(
            "fetch_comps", "tu_2",
            {"address": "400 Hearst Ave", "city": "San Francisco", "state": "CA",
             "zip_code": "94112"},
        )

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block, comps_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        end_turn_response.content = [_make_text_block("Analysis.")]

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock, return_value=PROPERTY_RESULT), \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=comps_full), \
             patch("agent.orchestrator.fetch_market_trends", new_callable=AsyncMock, return_value=MARKET_TRENDS), \
             patch("agent.orchestrator.fetch_fhfa_hpi", new_callable=AsyncMock, return_value=FHFA), \
             patch("agent.orchestrator.fetch_ca_hazard_zones", new_callable=AsyncMock, return_value=HAZARDS), \
             patch("agent.orchestrator.fetch_sf_permits", new_callable=AsyncMock, return_value=None), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value=MORTGAGE_RATES), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value=BA_VALUE), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=INVESTMENT), \
             patch("agent.orchestrator.recommend_offer", return_value=OFFER_RESULT), \
             patch("agent.orchestrator.assess_risk", return_value=RISK), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.5):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events()

        fetch_comps_result_events = [
            e for e in events
            if e.get("type") == "tool_result" and e.get("tool") == "fetch_comps"
        ]
        assert len(fetch_comps_result_events) == 1
        payload = fetch_comps_result_events[0]["result"]
        assert isinstance(payload, list), "fetch_comps SSE result must be a list for CompsCard"
        assert len(payload) == 1
        assert payload[0]["address"] == "402 Hearst Ave"
