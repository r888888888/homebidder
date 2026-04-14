"""
Tests verifying that buyer_context is wrapped in <buyer_notes> XML tags
in LLM prompts, not interpolated raw — defence against prompt injection.
All Anthropic API calls are mocked.
"""

import json
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import anthropic


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_rate_limit_exc() -> anthropic.RateLimitError:
    return anthropic.RateLimitError(
        message="rate_limit_error",
        response=httpx.Response(
            429,
            headers={"retry-after": "1"},
            request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"),
        ),
        body={"type": "error", "error": {"type": "rate_limit_error", "message": "rate limit"}},
    )


def _make_llm_json_response(payload: dict) -> MagicMock:
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(payload)
    resp = MagicMock()
    resp.content = [block]
    return resp


def _make_property(
    *,
    sqft: int = 1400,
    year_built: int = 1952,
    property_type: str = "SINGLE_FAMILY",
    bedrooms: int = 3,
    bathrooms: float = 1.0,
    avm_estimate: float | None = 1_100_000.0,
    listing_description: str = "Great fixer-upper. As-is sale.",
    city: str | None = None,
) -> dict:
    return {
        "sqft": sqft,
        "year_built": year_built,
        "property_type": property_type,
        "bedrooms": bedrooms,
        "bathrooms": bathrooms,
        "avm_estimate": avm_estimate,
        "listing_description": listing_description,
        "city": city,
        "description_signals": {
            "detected_signals": [
                {
                    "label": "Fixer / Contractor Special",
                    "category": "condition_negative",
                    "direction": "negative",
                    "weight_pct": -2.0,
                    "matched_phrases": ["fixer-upper"],
                }
            ],
            "net_adjustment_pct": -2.0,
        },
    }


def _make_offer(
    *,
    offer_recommended: float = 900_000.0,
    fair_value_estimate: float | None = 1_100_000.0,
) -> dict:
    return {
        "offer_recommended": offer_recommended,
        "fair_value_estimate": fair_value_estimate,
        "fair_value_breakdown": {"method": "median_comp_anchor"},
    }


# ---------------------------------------------------------------------------
# Orchestrator prompt tests
# ---------------------------------------------------------------------------

class TestOrchestratorPromptInjectionDefence:
    async def test_buyer_context_wrapped_in_xml_tags(self):
        """The user message sent to Claude must wrap buyer_context in
        <buyer_notes>...</buyer_notes>, not interpolate it raw."""
        from agent.orchestrator import run_agent

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_rate_limit_exc()

            events = []
            async for chunk in run_agent(
                "123 Main St, SF CA 94110",
                buyer_context="quick close preferred",
            ):
                if chunk.startswith("data: "):
                    events.append(json.loads(chunk[6:]))

        call_kwargs = mock_client.messages.create.call_args.kwargs
        user_message = call_kwargs["messages"][0]
        assert user_message["role"] == "user"
        content = user_message["content"]

        assert "<buyer_notes>" in content, "buyer_context must be wrapped in <buyer_notes>"
        assert "quick close preferred" in content
        assert "</buyer_notes>" in content, "buyer_context must be closed with </buyer_notes>"
        # Raw interpolation should NOT appear
        assert "Buyer notes: quick close preferred" not in content

    async def test_buyer_context_absent_when_empty(self):
        """When buyer_context is empty, no buyer_notes block should appear."""
        from agent.orchestrator import run_agent

        with patch("agent.orchestrator.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = make_rate_limit_exc()

            async for _ in run_agent("123 Main St, SF CA 94110", buyer_context=""):
                pass

        call_kwargs = mock_client.messages.create.call_args.kwargs
        content = call_kwargs["messages"][0]["content"]
        assert "<buyer_notes>" not in content
        assert "Buyer notes:" not in content


# ---------------------------------------------------------------------------
# Renovation prompt tests
# ---------------------------------------------------------------------------

class TestRenovationPromptInjectionDefence:
    async def test_buyer_context_wrapped_in_xml_tags(self):
        """The renovation cost prompt must wrap buyer_context in
        <buyer_notes>...</buyer_notes>."""
        from agent.tools.renovation import estimate_renovation_cost

        captured: list[dict] = []

        async def mock_create(**kwargs):
            captured.append(kwargs)
            return _make_llm_json_response({
                "line_items": [{"category": "Kitchen", "low": 20000, "high": 40000}],
                "scope_notes": "moderate scope",
            })

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(side_effect=mock_create)

            await estimate_renovation_cost(
                _make_property(),
                _make_offer(),
                buyer_context="prefer gut renovation",
            )

        assert len(captured) == 1, "expected exactly one LLM call"
        content = captured[0]["messages"][0]["content"]

        assert "<buyer_notes>" in content, "buyer_context must be wrapped in <buyer_notes>"
        assert "prefer gut renovation" in content
        assert "</buyer_notes>" in content
        assert "Buyer notes: prefer gut renovation" not in content

    async def test_buyer_context_absent_from_prompt_when_empty(self):
        """When buyer_context is empty, no buyer_notes block should appear
        in the renovation prompt."""
        from agent.tools.renovation import estimate_renovation_cost

        captured: list[dict] = []

        async def mock_create(**kwargs):
            captured.append(kwargs)
            return _make_llm_json_response({
                "line_items": [{"category": "Kitchen", "low": 20000, "high": 40000}],
                "scope_notes": "moderate scope",
            })

        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create = AsyncMock(side_effect=mock_create)

            await estimate_renovation_cost(
                _make_property(),
                _make_offer(),
                buyer_context="",
            )

        assert len(captured) == 1
        content = captured[0]["messages"][0]["content"]
        assert "<buyer_notes>" not in content
        assert "Buyer notes:" not in content
