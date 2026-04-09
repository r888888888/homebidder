"""
Phase 9 orchestrator tests: renovation estimation guard.
Verifies that estimate_renovation_cost runs for ALL properties
when a fair_value_estimate is present, not just fixer properties.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers shared with other orchestrator tests
# ---------------------------------------------------------------------------

def _make_fetch_comps_exchange():
    """Return (tool_use_response, end_turn_response) that has Claude call fetch_comps."""
    comps_block = MagicMock()
    comps_block.type = "tool_use"
    comps_block.name = "fetch_comps"
    comps_block.id = "tu_comps_phase9"
    comps_block.input = {
        "address": "500 Castro St, San Francisco, CA 94114",
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


FAKE_COMPS = {
    "comps": [
        {
            "address": "501 Castro St",
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

# Offer WITH fair_value_estimate — triggers Phase 9
OFFER_WITH_FV = {
    "offer_recommended": 1_050_000,
    "offer_low": 1_000_000,
    "offer_high": 1_100_000,
    "posture": "competitive",
    "fair_value_estimate": 1_150_000.0,
}

FAKE_RISK = {"overall_risk": "Moderate", "score": 4.0}
FAKE_INVESTMENT = {"investment_rating": "Buy", "gross_yield_pct": 3.1}
FAKE_RENOVATION = {
    "verdict": "cheaper_fixer",
    "savings_mid": 50_000,
    "is_fixer": False,
    "offer_recommended": 1_050_000,
    "turnkey_value": 1_150_000.0,
    "renovation_estimate_low": 30_000,
    "renovation_estimate_mid": 45_000,
    "renovation_estimate_high": 60_000,
    "all_in_fixer_low": 1_080_000,
    "all_in_fixer_mid": 1_095_000,
    "all_in_fixer_high": 1_110_000,
}


async def _run_agent(address="500 Castro St, San Francisco, CA 94114"):
    from agent.orchestrator import run_agent
    events = []
    async for chunk in run_agent(address):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPhase9RunsForAllProperties:
    async def test_renovation_runs_for_non_fixer_when_fv_present(self):
        """estimate_renovation_cost must be called even when is_fixer=False,
        as long as fair_value_estimate is present."""
        tool_use_response, end_turn_response = _make_fetch_comps_exchange()

        mock_renovation = AsyncMock(return_value=FAKE_RENOVATION)

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=OFFER_WITH_FV), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT), \
             patch("agent.orchestrator.estimate_renovation_cost", mock_renovation), \
             patch("agent.orchestrator._is_fixer_property", return_value=False):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            await _run_agent()

        mock_renovation.assert_called_once()

    async def test_renovation_sse_event_emitted_for_non_fixer(self):
        """estimate_renovation_cost tool_result SSE event is emitted for non-fixer properties."""
        tool_use_response, end_turn_response = _make_fetch_comps_exchange()

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=OFFER_WITH_FV), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT), \
             patch("agent.orchestrator.estimate_renovation_cost", new_callable=AsyncMock, return_value=FAKE_RENOVATION), \
             patch("agent.orchestrator._is_fixer_property", return_value=False):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await _run_agent()

        renovation_events = [
            e for e in events
            if e.get("type") == "tool_result" and e.get("tool") == "estimate_renovation_cost"
        ]
        assert len(renovation_events) == 1

    async def test_renovation_skipped_when_no_fair_value_estimate(self):
        """estimate_renovation_cost must NOT be called when fair_value_estimate is absent."""
        tool_use_response, end_turn_response = _make_fetch_comps_exchange()

        offer_without_fv = {
            "offer_recommended": 1_050_000,
            "posture": "competitive",
            # no fair_value_estimate
        }
        mock_renovation = AsyncMock(return_value=FAKE_RENOVATION)

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=FAKE_COMPS), \
             patch("agent.orchestrator.analyze_market", return_value={"median_price_per_sqft": 647.0}), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.0), \
             patch("agent.orchestrator.recommend_offer", return_value=offer_without_fv), \
             patch("agent.orchestrator.assess_risk", return_value=FAKE_RISK), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={"rate_30yr_fixed": 6.0}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={"adu_potential": False}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value=FAKE_INVESTMENT), \
             patch("agent.orchestrator.estimate_renovation_cost", mock_renovation):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            await _run_agent()

        mock_renovation.assert_not_called()
