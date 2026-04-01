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

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.lookup_property_by_address", new_callable=AsyncMock) as mock_lookup:

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]
            mock_lookup.return_value = property_result

            events = await collect_events("450 Sanchez St, San Francisco, CA 94114")

        tool_result_events = [e for e in events if e.get("type") == "tool_result"]
        assert len(tool_result_events) == 1
        assert tool_result_events[0]["tool"] == "lookup_property_by_address"

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
