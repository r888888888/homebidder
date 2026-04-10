"""
Tests for agent orchestrator error handling.
All Anthropic API calls are mocked — no real network requests.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import anthropic


async def collect_events(address: str, buyer_context: str = "") -> list[dict]:
    """Helper: drain the run_agent async generator into a list of parsed events."""
    from agent.orchestrator import run_agent

    events = []
    async for chunk in run_agent(address, buyer_context):
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[6:]))
    return events


def make_rate_limit_exc(retry_after: str = "30") -> anthropic.RateLimitError:
    return anthropic.RateLimitError(
        message="rate_limit_error",
        response=httpx.Response(
            429,
            headers={"retry-after": retry_after},
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        ),
        body={"type": "error", "error": {"type": "rate_limit_error", "message": "rate limit"}},
    )


def make_bad_request_exc() -> anthropic.BadRequestError:
    return anthropic.BadRequestError(
        message="invalid_request_error",
        response=httpx.Response(
            400,
            headers={"x-should-retry": "false"},
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        ),
        body={"type": "error", "error": {"type": "invalid_request_error", "message": "bad request"}},
    )


class TestRateLimitHandling:
    async def test_rate_limit_emits_error_event(self):
        """When the Anthropic API returns 429, run_agent yields an error event
        with a human-readable message rather than raising an exception."""
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_rate_limit_exc()

            events = await collect_events("123 Main St, SF CA 94110")

        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1, f"Expected 1 error event, got: {events}"

    async def test_rate_limit_error_includes_retry_after(self):
        """The error event should include the retry_after value from the response header."""
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_rate_limit_exc(retry_after="45")

            events = await collect_events("123 Main St, SF CA 94110")

        error_event = next(e for e in events if e.get("type") == "error")
        assert error_event.get("retry_after") == 45

    async def test_rate_limit_error_message_is_user_friendly(self):
        """The error message should be readable by a non-technical user."""
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_rate_limit_exc()

            events = await collect_events("123 Main St, SF CA 94110")

        error_event = next(e for e in events if e.get("type") == "error")
        msg = error_event.get("text", "")
        assert any(word in msg.lower() for word in ("rate", "limit", "try again", "busy", "capacity"))

    async def test_rate_limit_followed_by_done_event(self):
        """After the error event the generator should still emit 'done' so the
        frontend knows the stream has ended."""
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_rate_limit_exc()

            events = await collect_events("123 Main St, SF CA 94110")

        types = [e.get("type") for e in events]
        assert "done" in types, f"No 'done' event in: {types}"
        assert types.index("done") > types.index("error")


class TestToolDispatchErrorHandling:
    async def test_tool_error_does_not_crash_stream(self):
        """If a tool raises an exception, the stream should not crash — it
        should return an error result to Claude and continue the loop."""
        from unittest.mock import MagicMock

        # Build a mock response that requests a tool call
        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "scrape_listing"
        tool_use_block.id = "tu_123"
        tool_use_block.input = {"url": "https://zillow.com/homedetails/fake"}

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [tool_use_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Analysis complete."
        end_turn_response.content = [text_block]

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator._dispatch_tool", side_effect=RuntimeError("Chromium not installed")):
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            events = await collect_events("123 Main St, SF CA 94110")

        # Should not raise; should reach done
        types = [e.get("type") for e in events]
        assert "done" in types

    async def test_tool_error_result_is_sent_back_to_claude(self):
        """The error from a failed tool must be included in the tool_result
        sent back to Claude so the messages array stays valid (no 400s)."""
        from unittest.mock import MagicMock, call

        tool_use_block = MagicMock()
        tool_use_block.type = "tool_use"
        tool_use_block.name = "scrape_listing"
        tool_use_block.id = "tu_456"
        tool_use_block.input = {"url": "https://zillow.com/homedetails/fake"}

        tool_use_response = MagicMock()
        tool_use_response.stop_reason = "tool_use"
        tool_use_response.content = [tool_use_block]

        end_turn_response = MagicMock()
        end_turn_response.stop_reason = "end_turn"
        text_block = MagicMock()
        text_block.type = "text"
        text_block.text = "Done."
        end_turn_response.content = [text_block]

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator._dispatch_tool", side_effect=RuntimeError("Chromium not installed")):
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            await collect_events("123 Main St, SF CA 94110")

        # Second call to messages.create should include a tool_result for tu_456
        second_call_messages = mock_client.messages.create.call_args_list[1].kwargs["messages"]
        tool_results_turn = second_call_messages[-1]
        assert tool_results_turn["role"] == "user"
        result_block = tool_results_turn["content"][0]
        assert result_block["tool_use_id"] == "tu_456"
        assert result_block["type"] == "tool_result"


class TestBadRequestHandling:
    async def test_bad_request_emits_error_event(self):
        """When the Anthropic API returns 400, run_agent yields an error event
        rather than raising an exception."""
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_bad_request_exc()

            events = await collect_events("123 Main St, SF CA 94110")

        error_events = [e for e in events if e.get("type") == "error"]
        assert len(error_events) == 1, f"Expected 1 error event, got: {events}"

    async def test_bad_request_error_message_is_user_friendly(self):
        """The 400 error message should not expose internal API details."""
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_bad_request_exc()

            events = await collect_events("123 Main St, SF CA 94110")

        error_event = next(e for e in events if e.get("type") == "error")
        msg = error_event.get("text", "")
        # Should not leak raw API internals
        assert "invalid_request_error" not in msg
        assert "httpx" not in msg
        assert len(msg) > 0

    async def test_bad_request_followed_by_done_event(self):
        """After a 400 error the generator must still emit 'done'."""
        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_bad_request_exc()

            events = await collect_events("123 Main St, SF CA 94110")

        types = [e.get("type") for e in events]
        assert "done" in types, f"No 'done' event in: {types}"
        assert types.index("done") > types.index("error")


class TestModelSelection:
    """Tool-calling phase uses MODEL_TOOLS (Sonnet); final narrative uses MODEL_NARRATIVE (Opus)."""

    async def _run_full_analysis(self):
        """Simulate a complete run: fetch_comps tool call → auto-compute → final narrative."""
        comps_block = MagicMock()
        comps_block.type = "tool_use"
        comps_block.name = "fetch_comps"
        comps_block.id = "tu_comps_model"
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
        text_block.text = "Here is the narrative analysis."
        end_turn_response.content = [text_block]

        fake_comps = {
            "comps": [{"sold_price": 1_000_000, "price_per_sqft": 700.0, "sqft": 1400, "list_price": 980_000}],
            "subject_sale": None,
        }

        from agent.orchestrator import run_agent

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls, \
             patch("agent.orchestrator.fetch_comps", new_callable=AsyncMock, return_value=fake_comps), \
             patch("agent.orchestrator.get_current_mortgage_rate_pct", new_callable=AsyncMock, return_value=6.5), \
             patch("agent.orchestrator.recommend_offer", return_value={"offer_recommended": 1_000_000, "posture": "at-market", "fair_value_estimate": 1_000_000}), \
             patch("agent.orchestrator.assess_risk", return_value={"overall_risk": "Low", "score": 2.0, "factors": []}), \
             patch("agent.orchestrator.fetch_mortgage_rates", new_callable=AsyncMock, return_value={}), \
             patch("agent.orchestrator.fetch_ba_value_drivers", new_callable=AsyncMock, return_value={}), \
             patch("agent.orchestrator.compute_investment_metrics", return_value={}), \
             patch("agent.orchestrator.estimate_renovation_cost", new_callable=AsyncMock, return_value=None):

            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = [tool_use_response, end_turn_response]

            async for _ in run_agent("450 Sanchez St, San Francisco, CA 94114"):
                pass

            return mock_client.messages.create.call_args_list

    async def test_tool_phase_uses_model_tools(self):
        """The first (tool-use) API call must use MODEL_TOOLS."""
        from agent.orchestrator import MODEL_TOOLS

        calls = await self._run_full_analysis()
        first_call_model = calls[0].kwargs["model"]
        assert first_call_model == MODEL_TOOLS, (
            f"Tool-use phase used {first_call_model!r}, expected MODEL_TOOLS={MODEL_TOOLS!r}"
        )

    async def test_narrative_phase_uses_model_narrative(self):
        """The final (narrative) API call must use MODEL_NARRATIVE, not MODEL_TOOLS."""
        from agent.orchestrator import MODEL_NARRATIVE, MODEL_TOOLS

        calls = await self._run_full_analysis()
        final_call_model = calls[-1].kwargs["model"]
        assert final_call_model == MODEL_NARRATIVE, (
            f"Narrative phase used {final_call_model!r}, expected MODEL_NARRATIVE={MODEL_NARRATIVE!r}"
        )
        assert final_call_model != MODEL_TOOLS, "Narrative phase must not reuse MODEL_TOOLS"

    def test_model_constants_are_different(self):
        """MODEL_TOOLS and MODEL_NARRATIVE must refer to distinct model IDs."""
        from agent.orchestrator import MODEL_TOOLS, MODEL_NARRATIVE

        assert MODEL_TOOLS != MODEL_NARRATIVE
