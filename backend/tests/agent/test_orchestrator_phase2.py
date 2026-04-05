"""
Phase 2 orchestrator tests.
Verify lookup_property_by_address is registered, scrape_listing is gone,
and tool_result SSE events are emitted for lookup_property_by_address results.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


async def collect_events(address: str, buyer_context: str = "") -> list[dict]:
    from agent.orchestrator import run_agent

    events = []
    async for chunk in run_agent(address, buyer_context):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


class TestToolRegistration:
    def test_lookup_property_tool_registered(self):
        """TOOLS list contains lookup_property_by_address."""
        from agent.orchestrator import TOOLS

        names = [t["name"] for t in TOOLS]
        assert "lookup_property_by_address" in names

    def test_scrape_listing_removed(self):
        """scrape_listing is no longer registered in TOOLS."""
        from agent.orchestrator import TOOLS

        names = [t["name"] for t in TOOLS]
        assert "scrape_listing" not in names

    def test_lookup_property_tool_has_address_input(self):
        """lookup_property_by_address tool schema requires an 'address' field."""
        from agent.orchestrator import TOOLS

        tool = next(t for t in TOOLS if t["name"] == "lookup_property_by_address")
        props = tool["input_schema"]["properties"]
        assert "address" in props
        assert "address" in tool["input_schema"].get("required", [])

    def test_system_prompt_references_lookup(self):
        """System prompt instructs Claude to call lookup_property_by_address first."""
        from agent.orchestrator import SYSTEM_PROMPT

        assert "lookup_property_by_address" in SYSTEM_PROMPT

    def test_fetch_neighborhood_context_registered(self):
        """TOOLS list contains fetch_neighborhood_context."""
        from agent.orchestrator import TOOLS

        names = [t["name"] for t in TOOLS]
        assert "fetch_neighborhood_context" in names

    def test_system_prompt_references_neighborhood(self):
        """System prompt instructs Claude to call fetch_neighborhood_context."""
        from agent.orchestrator import SYSTEM_PROMPT

        assert "fetch_neighborhood_context" in SYSTEM_PROMPT


class TestToolResultSseEvents:
    async def test_tool_result_event_emitted_after_tool_call(self):
        """When lookup_property_by_address completes, a tool_result SSE event is emitted."""
        from unittest.mock import MagicMock

        lookup_block = MagicMock()
        lookup_block.type = "tool_use"
        lookup_block.name = "lookup_property_by_address"
        lookup_block.id = "tu_lookup_1"
        lookup_block.input = {"address": "450 Sanchez St, San Francisco, CA 94114"}

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Analysis complete."
        end_turn_response.content = [text_block]

        property_result = {
            "address_matched": "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
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
            "lot_size": 2500,
            "property_type": "SINGLE_FAMILY",
            "hoa_fee": None,
            "days_on_market": 5,
            "price_history": [],
            "avm_estimate": 1_300_000.0,
            "source": "homeharvest",
        }

        phase6_result = {"zip_code": "94114", "months": [], "trend": "flat"}
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock) as mock_lookup, \
             patch("agent.orchestrator.fetch_market_trends", new_callable=AsyncMock, return_value=phase6_result), \
             patch("agent.orchestrator.fetch_fhfa_hpi", new_callable=AsyncMock, return_value={"zip_code": "94114", "hpi_trend": "flat"}), \
             patch("agent.orchestrator.fetch_ca_hazard_zones", new_callable=AsyncMock, return_value={"alquist_priolo": False}), \
             patch("agent.orchestrator.fetch_calenviroscreen_data", new_callable=AsyncMock, return_value=None):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]
            mock_lookup.return_value = property_result

            events = await collect_events("450 Sanchez St, San Francisco, CA 94114")

        tool_result_events = [e for e in events if e.get("type") == "tool_result"]
        tool_names = [e["tool"] for e in tool_result_events]
        assert "lookup_property_by_address" in tool_names
        # Phase 6 tools are auto-emitted after property lookup
        assert "fetch_market_trends" in tool_names
        assert "fetch_fhfa_hpi" in tool_names
        assert "fetch_ca_hazard_zones" in tool_names

    async def test_tool_result_event_contains_property_data(self):
        """The tool_result event payload includes address_matched and price."""
        from unittest.mock import MagicMock

        lookup_block = MagicMock()
        lookup_block.type = "tool_use"
        lookup_block.name = "lookup_property_by_address"
        lookup_block.id = "tu_lookup_2"
        lookup_block.input = {"address": "450 Sanchez St, San Francisco, CA 94114"}

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        property_result = {
            "address_matched": "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
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
            "lot_size": 2500,
            "property_type": "SINGLE_FAMILY",
            "hoa_fee": None,
            "days_on_market": 5,
            "price_history": [],
            "avm_estimate": None,
            "source": "homeharvest",
        }

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock) as mock_lookup:

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]
            mock_lookup.return_value = property_result

            events = await collect_events("450 Sanchez St, San Francisco, CA 94114")

        tr = next(e for e in events if e.get("type") == "tool_result")
        result_data = tr["result"]
        assert result_data["address_matched"] == "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114"
        assert result_data["price"] == 1_250_000.0

    async def test_phase2_passes_fetched_mortgage_rate_to_recommend_offer(self):
        from unittest.mock import MagicMock

        comps_block = MagicMock()
        comps_block.type = "tool_use"
        comps_block.name = "fetch_comps"
        comps_block.id = "tu_comps_1"
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
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        fake_comps = {
            "comps": [{"sold_price": 1_000_000, "price_per_sqft": 700.0, "sqft": 1400, "list_price": 980_000}],
            "subject_sale": None,
        }
        fake_offer = {
            "list_price": 995000,
            "fair_value_estimate": 1_000_000,
            "fair_value_breakdown": {"method": "median_comp_anchor", "condition_adjustment_pct": -1.5},
            "offer_low": 970000,
            "offer_recommended": 995000,
            "offer_high": 1_020_000,
            "posture": "at-market",
            "offer_range_band_pct": 3.0,
            "spread_vs_list_pct": 0.5,
            "condition_adjustment_pct": -1.5,
            "condition_signals": [{"label": "Tenant Occupied"}],
            "median_pct_over_asking": None,
            "pct_sold_over_asking": None,
            "offer_review_advisory": None,
            "contingency_recommendation": {"waive_appraisal": False, "waive_loan": False, "keep_inspection": True},
            "hoa_equivalent_sfh_value": None,
        }

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=fake_comps), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=5.75), \
             patch("agent.orchestrator.recommend_offer", return_value=fake_offer) as mock_recommend:

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            await collect_events("450 Sanchez St, San Francisco, CA 94114")

        _, kwargs = mock_recommend.call_args
        assert kwargs["mortgage_rate_pct"] == 5.75

    async def test_recommend_offer_tool_result_includes_condition_fields(self):
        from unittest.mock import MagicMock

        lookup_block = MagicMock()
        lookup_block.type = "tool_use"
        lookup_block.name = "lookup_property_by_address"
        lookup_block.id = "tu_lookup_3"
        lookup_block.input = {"address": "450 Sanchez St, San Francisco, CA 94114"}

        comps_block = MagicMock()
        comps_block.type = "tool_use"
        comps_block.name = "fetch_comps"
        comps_block.id = "tu_comps_3"
        comps_block.input = {
            "address": "450 Sanchez St, San Francisco, CA 94114",
            "city": "San Francisco",
            "state": "CA",
            "zip_code": "94114",
        }

        lookup_response = MagicMock()
        lookup_response.stop_reason = "tool_use"
        lookup_response.content = [lookup_block]

        comps_response = MagicMock()
        comps_response.stop_reason = "tool_use"
        comps_response.content = [comps_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        fake_property = {
            "address_matched": "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
            "county": "San Francisco",
            "state": "CA",
            "zip_code": "94114",
            "price": 995000,
            "description_signals": {"net_adjustment_pct": -1.5, "detected_signals": [{"label": "Tenant Occupied"}]},
        }
        fake_comps = {
            "comps": [{"sold_price": 1_000_000, "price_per_sqft": 700.0, "sqft": 1400, "list_price": 980_000}],
            "subject_sale": None,
        }

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=fake_comps), \
             patch("agent.orchestrator.recommend_offer", return_value={
                 "list_price": 995000,
                 "fair_value_estimate": 980000,
                 "fair_value_breakdown": {"method": "median_comp_anchor", "condition_adjustment_pct": -1.5},
                 "offer_low": 960000,
                 "offer_recommended": 980000,
                 "offer_high": 1_000_000,
                 "posture": "at-market",
                 "offer_range_band_pct": 3.0,
                 "spread_vs_list_pct": -1.5,
                 "condition_adjustment_pct": -1.5,
                 "condition_signals": [{"label": "Tenant Occupied"}],
                 "median_pct_over_asking": None,
                 "pct_sold_over_asking": None,
                 "offer_review_advisory": None,
                 "contingency_recommendation": {"waive_appraisal": False, "waive_loan": False, "keep_inspection": True},
                 "hoa_equivalent_sfh_value": None,
             }) as mock_recommend, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock, return_value=fake_property):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [lookup_response, comps_response, end_turn_response]

            events = await collect_events("450 Sanchez St, San Francisco, CA 94114")

        recommend_event = next(
            e for e in events if e.get("type") == "tool_result" and e.get("tool") == "recommend_offer"
        )
        assert "condition_adjustment_pct" in recommend_event["result"]
        assert "condition_signals" in recommend_event["result"]
        args, _ = mock_recommend.call_args
        assert args[0]["description_signals"]["net_adjustment_pct"] == -1.5


class TestPhase8AutoComputation:
    async def test_phase8_emits_investment_tool_events(self):
        from unittest.mock import MagicMock

        comps_block = MagicMock()
        comps_block.type = "tool_use"
        comps_block.name = "fetch_comps"
        comps_block.id = "tu_comps_2"
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
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        fake_comps = {
            "comps": [{"sold_price": 1_000_000, "price_per_sqft": 700.0, "sqft": 1400, "list_price": 980_000}],
            "subject_sale": None,
        }
        fake_market = {"median_price_per_sqft": 700.0}
        fake_offer = {"offer_recommended": 1_200_000, "posture": "competitive"}
        fake_risk = {"overall_risk": "Moderate", "score": 4.0}
        fake_rates = {"rate_30yr_fixed": 6.6, "rate_15yr_fixed": 5.8, "as_of_date": "2026-03-26", "source": "Freddie Mac PMMS via FRED"}
        fake_rent = {"rent_estimate": 4900, "rent_low": 4600, "rent_high": 5200, "confidence": 0.7, "source": "rentcast"}
        fake_drivers = {"adu_potential": True, "adu_rent_estimate": 2800, "rent_controlled": True}
        fake_investment = {"investment_rating": "Hold", "gross_yield_pct": 3.1}

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls,              patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=fake_comps),              patch("agent.orchestrator.analyze_market", return_value=fake_market),              patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=5.75),              patch("agent.orchestrator.recommend_offer", return_value=fake_offer),              patch("agent.orchestrator.assess_risk", return_value=fake_risk),              patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value=fake_rates),              patch("agent.orchestrator.fetch_rental_estimate", new_callable=AsyncMock, return_value=fake_rent),              patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value=fake_drivers),              patch("agent.orchestrator.compute_investment_metrics", return_value=fake_investment):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events("450 Sanchez St, San Francisco, CA 94114")

        tool_result_events = [e for e in events if e.get("type") == "tool_result"]
        tools = [e["tool"] for e in tool_result_events]

        assert "fetch_mortgage_rates" in tools
        assert "fetch_rental_estimate" in tools
        assert "fetch_ba_value_drivers" in tools
        assert "compute_investment_metrics" in tools


class TestSfPermitAutoFetch:
    async def test_sf_lookup_triggers_sf_permit_tool_events(self):
        from unittest.mock import MagicMock

        lookup_block = MagicMock()
        lookup_block.type = "tool_use"
        lookup_block.name = "lookup_property_by_address"
        lookup_block.id = "tu_lookup_sf"
        lookup_block.input = {"address": "450 Sanchez St, San Francisco, CA 94114"}

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        property_result = {
            "address_matched": "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
            "county": "San Francisco",
            "state": "CA",
            "zip_code": "",
            "unit": "2",
            "latitude": None,
            "longitude": None,
        }
        permits_result = {
            "source": "dbi",
            "source_detail": None,
            "open_permits_count": 1,
            "recent_permits_5y": 3,
            "major_permits_10y": 1,
            "oldest_open_permit_age_days": 480,
            "permit_counts_by_type": {"electrical": 1, "plumbing": 0, "building": 0},
            "complaints_open_count": 0,
            "complaints_recent_3y": 1,
            "flags": ["open_over_365_days"],
            "permits": [],
            "complaints": [],
        }

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock, return_value=property_result), \
             patch("agent.orchestrator.fetch_sf_permits", new_callable=AsyncMock, return_value=permits_result):
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events("450 Sanchez St, San Francisco, CA 94114")

        permit_tool_calls = [e for e in events if e.get("type") == "tool_call" and e.get("tool") == "fetch_sf_permits"]
        permit_tool_results = [e for e in events if e.get("type") == "tool_result" and e.get("tool") == "fetch_sf_permits"]
        assert len(permit_tool_calls) == 1
        assert len(permit_tool_results) == 1
        assert permit_tool_results[0]["result"]["open_permits_count"] == 1

    async def test_non_sf_lookup_skips_sf_permit_tool(self):
        from unittest.mock import MagicMock

        lookup_block = MagicMock()
        lookup_block.type = "tool_use"
        lookup_block.name = "lookup_property_by_address"
        lookup_block.id = "tu_lookup_non_sf"
        lookup_block.input = {"address": "1 Main St, Oakland, CA 94607"}

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [lookup_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        property_result = {
            "address_matched": "1 MAIN ST, OAKLAND, CA, 94607",
            "county": "Alameda",
            "state": "CA",
            "zip_code": "",
            "unit": None,
            "latitude": None,
            "longitude": None,
        }

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock, return_value=property_result), \
             patch("agent.orchestrator.fetch_sf_permits", new_callable=AsyncMock) as mock_permits:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events("1 Main St, Oakland, CA 94607")

        permit_events = [e for e in events if e.get("tool") == "fetch_sf_permits"]
        assert not permit_events
        mock_permits.assert_not_called()
