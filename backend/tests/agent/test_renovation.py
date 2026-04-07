"""
Tests for renovation.py — estimate_renovation_cost and _is_fixer_property.
All LLM calls are mocked — no real network requests.
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _make_llm_response(json_payload: dict) -> MagicMock:
    """Build a mock anthropic Message containing a JSON text block."""
    block = MagicMock()
    block.type = "text"
    block.text = json.dumps(json_payload)
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
    detected_signals: list | None = None,
    city: str | None = None,
) -> dict:
    if detected_signals is None:
        detected_signals = [
            {"label": "Fixer / Contractor Special", "category": "condition_negative",
             "direction": "negative", "weight_pct": -2.0, "matched_phrases": ["fixer-upper"]},
        ]
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
            "detected_signals": detected_signals,
            "net_adjustment_pct": -2.0,
        },
    }


def _make_offer(*, offer_recommended: float = 900_000.0, fair_value_estimate: float | None = 1_100_000.0) -> dict:
    return {
        "offer_recommended": offer_recommended,
        "fair_value_estimate": fair_value_estimate,
        "fair_value_breakdown": {
            "method": "median_comp_anchor",
        },
    }


_GOOD_LLM_JSON = {
    "line_items": [
        {"category": "Kitchen remodel", "low": 35_000, "high": 60_000},
        {"category": "Bathroom remodel", "low": 15_000, "high": 25_000},
        {"category": "Flooring", "low": 10_000, "high": 18_000},
        {"category": "Interior paint", "low": 5_000, "high": 8_000},
    ],
    "scope_notes": "Older SF bungalow; kitchen and bathrooms are the primary work.",
}


# ---------------------------------------------------------------------------
# TestIsFixerProperty — pure unit tests, no mocks
# ---------------------------------------------------------------------------

class TestIsFixerProperty:
    def test_returns_true_for_condition_negative_signal(self):
        from agent.tools.renovation import _is_fixer_property
        prop = _make_property()
        assert _is_fixer_property(prop) is True

    def test_returns_false_for_no_signals(self):
        from agent.tools.renovation import _is_fixer_property
        prop = _make_property(detected_signals=[])
        assert _is_fixer_property(prop) is False

    def test_returns_false_for_condition_positive_only(self):
        from agent.tools.renovation import _is_fixer_property
        prop = _make_property(detected_signals=[
            {"label": "Renovated / Updated", "category": "condition_positive",
             "direction": "positive", "weight_pct": 1.5, "matched_phrases": ["remodeled"]},
        ])
        assert _is_fixer_property(prop) is False

    def test_returns_false_when_description_signals_key_absent(self):
        from agent.tools.renovation import _is_fixer_property
        prop = {"sqft": 1200, "year_built": 1960}
        assert _is_fixer_property(prop) is False


# ---------------------------------------------------------------------------
# TestEstimateRenovationCost — async, LLM mocked
# ---------------------------------------------------------------------------

class TestEstimateRenovationCost:
    async def test_returns_none_when_api_key_missing(self):
        from agent.tools.renovation import estimate_renovation_cost
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        with patch.dict(os.environ, env, clear=True):
            result = await estimate_renovation_cost(_make_property(), _make_offer())
        assert result is None

    async def test_returns_none_when_fair_value_estimate_is_null(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            result = await estimate_renovation_cost(_make_property(), _make_offer(fair_value_estimate=None))
        assert result is None

    async def test_returns_none_when_offer_recommended_is_zero(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
            result = await estimate_renovation_cost(_make_property(), _make_offer(offer_recommended=0))
        assert result is None

    async def test_returns_none_on_llm_exception(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.side_effect = Exception("network error")
            result = await estimate_renovation_cost(_make_property(), _make_offer())
        assert result is None

    async def test_returns_none_on_unparseable_llm_response(self):
        from agent.tools.renovation import estimate_renovation_cost
        bad_resp = MagicMock()
        bad_block = MagicMock()
        bad_block.type = "text"
        bad_block.text = "Sorry, I cannot help with that."
        bad_resp.content = [bad_block]
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = bad_resp
            result = await estimate_renovation_cost(_make_property(), _make_offer())
        assert result is None

    async def test_golden_path_parses_llm_response_and_computes_comparison(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), _make_offer())

        assert result is not None
        assert result["is_fixer"] is True
        assert result["offer_recommended"] == 900_000.0
        assert result["turnkey_value"] == 1_100_000.0
        assert result["renovation_estimate_low"] == 65_000   # 35+15+10+5
        assert result["renovation_estimate_high"] == 111_000  # 60+25+18+8
        assert result["renovation_estimate_mid"] == (65_000 + 111_000) // 2
        assert result["all_in_fixer_mid"] == 900_000 + result["renovation_estimate_mid"]
        assert "verdict" in result
        assert "savings_mid" in result
        assert "disclaimer" in result

    async def test_verdict_cheaper_fixer(self):
        """all-in mid is more than 3% below fair value → cheaper_fixer."""
        from agent.tools.renovation import estimate_renovation_cost
        # offer=800k, reno_mid=50k → all_in=850k; fair_value=1_100k → savings=250k (>3%)
        small_reno = {"line_items": [{"category": "Paint", "low": 40_000, "high": 60_000}], "scope_notes": ""}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(small_reno)
            result = await estimate_renovation_cost(
                _make_property(),
                _make_offer(offer_recommended=800_000.0, fair_value_estimate=1_100_000.0),
            )
        assert result["verdict"] == "cheaper_fixer"
        assert result["savings_mid"] > 0

    async def test_verdict_cheaper_turnkey(self):
        """all-in mid is more than 3% above fair value → cheaper_turnkey."""
        from agent.tools.renovation import estimate_renovation_cost
        # offer=900k, reno_mid=250k → all_in=1_150k; fair_value=1_050k → savings=-100k (<-3%)
        big_reno = {"line_items": [{"category": "Full gut", "low": 200_000, "high": 300_000}], "scope_notes": ""}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(big_reno)
            result = await estimate_renovation_cost(
                _make_property(),
                _make_offer(offer_recommended=900_000.0, fair_value_estimate=1_050_000.0),
            )
        assert result["verdict"] == "cheaper_turnkey"
        assert result["savings_mid"] < 0

    async def test_verdict_comparable(self):
        """Difference within 3% of fair value → comparable."""
        from agent.tools.renovation import estimate_renovation_cost
        # offer=900k, reno_mid=150k → all_in=1_050k; fair_value=1_080k → savings=30k (30/1080=2.8% < 3%)
        mid_reno = {"line_items": [{"category": "Kitchen", "low": 140_000, "high": 160_000}], "scope_notes": ""}
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(mid_reno)
            result = await estimate_renovation_cost(
                _make_property(),
                _make_offer(offer_recommended=900_000.0, fair_value_estimate=1_080_000.0),
            )
        assert result["verdict"] == "comparable"

    async def test_fixer_signals_list_contains_only_condition_negative_labels(self):
        from agent.tools.renovation import estimate_renovation_cost
        mixed_signals = [
            {"label": "Fixer / Contractor Special", "category": "condition_negative",
             "direction": "negative", "weight_pct": -2.0, "matched_phrases": []},
            {"label": "Renovated / Updated", "category": "condition_positive",
             "direction": "positive", "weight_pct": 1.5, "matched_phrases": []},
        ]
        prop = _make_property(detected_signals=mixed_signals)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(prop, _make_offer())
        assert result["fixer_signals"] == ["Fixer / Contractor Special"]

    async def test_model_override_via_env_var(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key", "RENOVATION_LLM_MODEL": "custom-model"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            await estimate_renovation_cost(_make_property(), _make_offer())
        call_kwargs = mock_client.messages.create.call_args
        assert call_kwargs.kwargs.get("model") == "custom-model" or call_kwargs.args[0] == "custom-model" \
            or call_kwargs.kwargs.get("model") == "custom-model"
        # More robustly:
        create_kwargs = mock_client.messages.create.call_args[1]
        assert create_kwargs["model"] == "custom-model"

    async def test_missing_fair_value_breakdown_does_not_crash(self):
        from agent.tools.renovation import estimate_renovation_cost
        offer = {"offer_recommended": 900_000.0, "fair_value_estimate": 1_100_000.0}  # no fair_value_breakdown key
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), offer)
        assert result is not None
        assert "condition_adjustment_pct" not in result

    async def test_line_items_present_in_result(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), _make_offer())
        assert isinstance(result["line_items"], list)
        assert len(result["line_items"]) == 4
        assert result["line_items"][0]["category"] == "Kitchen remodel"
        assert result["line_items"][0]["low"] == 35_000
        assert result["line_items"][0]["high"] == 60_000

    async def test_buyer_context_included_in_llm_prompt(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            await estimate_renovation_cost(
                _make_property(), _make_offer(), buyer_context="planning to DIY most of the work"
            )
        prompt_text = mock_client.messages.create.call_args[1]["messages"][0]["content"]
        assert "planning to DIY most of the work" in prompt_text

    async def test_buyer_context_empty_string_does_not_crash(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), _make_offer(), buyer_context="")
        assert result is not None

    async def test_all_in_costs_computed_correctly(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), _make_offer(offer_recommended=900_000.0))
        assert result["all_in_fixer_low"] == 900_000 + result["renovation_estimate_low"]
        assert result["all_in_fixer_high"] == 900_000 + result["renovation_estimate_high"]
        assert result["all_in_fixer_mid"] == 900_000 + result["renovation_estimate_mid"]

    async def test_renovated_fair_value_equals_fair_value_estimate(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(
                _make_property(),
                _make_offer(fair_value_estimate=1_100_000.0),
            )
        assert result["renovated_fair_value"] == 1_100_000
        assert "condition_adjustment_pct" not in result

    async def test_implied_equity_is_renovated_value_minus_all_in_mid(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), _make_offer())
        assert result["implied_equity_mid"] == result["renovated_fair_value"] - result["all_in_fixer_mid"]


# ---------------------------------------------------------------------------
# TestClassifyEra — pure unit tests, no mocks
# ---------------------------------------------------------------------------

class TestClassifyEra:
    def test_pre_1940(self):
        from agent.tools.renovation import _classify_era
        label, at_risk = _classify_era(1925)
        assert label == "pre_1940"
        assert "electrical" in at_risk
        assert "plumbing" in at_risk
        assert "foundation" in at_risk

    def test_1940s_1960s(self):
        from agent.tools.renovation import _classify_era
        label, at_risk = _classify_era(1955)
        assert label == "1940s_1960s"
        assert "electrical" in at_risk
        assert "plumbing" in at_risk

    def test_1960s_1978(self):
        from agent.tools.renovation import _classify_era
        label, at_risk = _classify_era(1968)
        assert label == "1960s_1978"
        assert "electrical" in at_risk
        assert "plumbing" not in at_risk

    def test_1978_1990(self):
        from agent.tools.renovation import _classify_era
        label, at_risk = _classify_era(1985)
        assert label == "1978_1990"
        assert at_risk == ["hvac"]

    def test_post_2010(self):
        from agent.tools.renovation import _classify_era
        label, at_risk = _classify_era(2015)
        assert label == "post_2010"
        assert at_risk == []

    def test_none_year(self):
        from agent.tools.renovation import _classify_era
        label, at_risk = _classify_era(None)
        assert label == "unknown"
        assert len(at_risk) > 0

    def test_boundary_1940(self):
        from agent.tools.renovation import _classify_era
        label, _ = _classify_era(1940)
        assert label == "1940s_1960s"

    def test_boundary_1978(self):
        from agent.tools.renovation import _classify_era
        label, _ = _classify_era(1978)
        assert label == "1978_1990"


# ---------------------------------------------------------------------------
# TestClassifyHazmat — pure unit tests, no mocks
# ---------------------------------------------------------------------------

class TestClassifyHazmat:
    def test_post_1980_returns_none(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(1990, "mid", []) == "none"

    def test_exactly_1980_returns_none(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(1980, "full", []) == "none"

    def test_pre_1978_cosmetic_returns_encapsulation(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(1965, "cosmetic", []) == "encapsulation"

    def test_pre_1978_mid_returns_partial(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(1965, "mid", []) == "partial"

    def test_pre_1978_full_returns_full(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(1965, "full", []) == "full"

    def test_asbestos_in_phrases_upgrades_to_full(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(1965, "mid", ["asbestos found in attic"]) == "full"

    def test_lead_paint_in_phrases_upgrades_to_full(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(1965, "cosmetic", ["lead paint present"]) == "full"

    def test_none_year_returns_none(self):
        from agent.tools.renovation import _classify_hazmat
        assert _classify_hazmat(None, "full", []) == "none"


# ---------------------------------------------------------------------------
# TestGetRegionalMultiplier — pure unit tests, no mocks
# ---------------------------------------------------------------------------

class TestGetRegionalMultiplier:
    def test_san_francisco_above_one(self):
        from agent.tools.renovation import _get_regional_multiplier
        assert _get_regional_multiplier("San Francisco") > 1.0

    def test_oakland_is_baseline(self):
        from agent.tools.renovation import _get_regional_multiplier
        assert _get_regional_multiplier("Oakland") == 1.0

    def test_none_returns_one(self):
        from agent.tools.renovation import _get_regional_multiplier
        assert _get_regional_multiplier(None) == 1.0

    def test_unknown_city_returns_one(self):
        from agent.tools.renovation import _get_regional_multiplier
        assert _get_regional_multiplier("Atlantis") == 1.0

    def test_case_insensitive(self):
        from agent.tools.renovation import _get_regional_multiplier
        assert _get_regional_multiplier("SAN FRANCISCO") == _get_regional_multiplier("san francisco")

    def test_hayward_below_one(self):
        from agent.tools.renovation import _get_regional_multiplier
        assert _get_regional_multiplier("Hayward") < 1.0

    def test_palo_alto_above_sf_baseline_east_bay(self):
        from agent.tools.renovation import _get_regional_multiplier
        assert _get_regional_multiplier("Palo Alto") > _get_regional_multiplier("Oakland")


# ---------------------------------------------------------------------------
# TestBuildScopeProfile — pure unit tests, no mocks
# ---------------------------------------------------------------------------

_FIXER_SIGNAL = "Fixer / Contractor Special"
_FIXER_SIGNALS = [_FIXER_SIGNAL]


class TestBuildScopeProfile:
    def test_cosmetic_phrase_yields_cosmetic_scope(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["cosmetic fixer"])
        assert profile["scope_level"] == "cosmetic"

    def test_deferred_maintenance_yields_full_scope(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["deferred maintenance"])
        assert profile["scope_level"] == "full"

    def test_default_fixer_is_mid(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["fixer-upper"])
        assert profile["scope_level"] == "mid"

    def test_pre_1940_with_fixer_signal_upgrades_to_full(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1930, _FIXER_SIGNALS, ["fixer-upper"])
        assert profile["scope_level"] == "full"

    def test_good_bones_caps_at_mid(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1930, _FIXER_SIGNALS, ["good bones", "fixer-upper"])
        assert profile["scope_level"] != "full"
        assert profile["item_likelihood"]["foundation"] == "unlikely"
        assert profile["item_likelihood"]["seismic"] == "unlikely"

    def test_needs_new_roof_makes_roof_likely(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1985, _FIXER_SIGNALS, ["needs new roof"])
        assert profile["item_likelihood"]["roof"] == "likely"

    def test_post_1980_hazmat_is_none(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1990, _FIXER_SIGNALS, ["fixer-upper"])
        assert profile["hazmat_tier"] == "none"

    def test_pre_1978_cosmetic_hazmat_is_encapsulation(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["cosmetic fixer"])
        assert profile["hazmat_tier"] == "encapsulation"

    def test_pre_1978_mid_hazmat_is_partial(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["fixer-upper"])
        assert profile["hazmat_tier"] == "partial"

    def test_scope_reasoning_is_nonempty_list(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["fixer-upper"])
        assert isinstance(profile["scope_reasoning"], list)
        assert len(profile["scope_reasoning"]) > 0

    def test_all_core_items_in_item_likelihood(self):
        from agent.tools.renovation import build_scope_profile
        CORE_SLUGS = {"kitchen", "bathroom", "flooring", "paint", "roof",
                      "electrical", "plumbing", "hvac", "foundation", "seismic", "windows"}
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["fixer-upper"])
        for slug in CORE_SLUGS:
            assert slug in profile["item_likelihood"], f"{slug} missing from item_likelihood"

    def test_buyer_notes_full_gut_overrides_cosmetic_phrase(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(
            1965, _FIXER_SIGNALS, ["cosmetic fixer"],
            buyer_notes="planning a full gut renovation down to the studs"
        )
        assert profile["scope_level"] == "full"

    def test_buyer_notes_just_painting_caps_at_cosmetic(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(
            1965, _FIXER_SIGNALS, ["deferred maintenance"],
            buyer_notes="just planning to paint and update carpets"
        )
        assert profile["scope_level"] == "cosmetic"

    def test_buyer_notes_new_kitchen_makes_kitchen_likely(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(
            1965, _FIXER_SIGNALS, ["cosmetic fixer"],
            buyer_notes="new kitchen is our priority"
        )
        assert profile["item_likelihood"]["kitchen"] == "likely"

    def test_cosmetic_scope_has_unlikely_roof_and_electrical(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1990, _FIXER_SIGNALS, ["cosmetic fixer"])
        assert profile["item_likelihood"]["roof"] == "unlikely"
        assert profile["item_likelihood"]["electrical"] == "unlikely"

    def test_age_era_present_in_profile(self):
        from agent.tools.renovation import build_scope_profile
        profile = build_scope_profile(1965, _FIXER_SIGNALS, ["fixer-upper"])
        assert "age_era" in profile
        assert profile["age_era"] == "1960s_1978"


# ---------------------------------------------------------------------------
# TestEstimateRenovationCostWithScope — async, LLM mocked
# ---------------------------------------------------------------------------

class TestEstimateRenovationCostWithScope:
    async def test_scope_level_present_in_result(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), _make_offer())
        assert "scope_level" in result

    async def test_hazmat_tier_present_in_result(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(), _make_offer())
        assert "hazmat_tier" in result

    async def test_pre_1978_cosmetic_fixer_hazmat_is_encapsulation_not_full(self):
        from agent.tools.renovation import estimate_renovation_cost
        cosmetic_signals = [
            {"label": "Fixer / Contractor Special", "category": "condition_negative",
             "direction": "negative", "weight_pct": -2.0, "matched_phrases": ["cosmetic fixer"]},
        ]
        prop = _make_property(year_built=1965, detected_signals=cosmetic_signals)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(prop, _make_offer())
        assert result["hazmat_tier"] == "encapsulation"

    async def test_post_1980_home_has_no_hazmat_in_prompt(self):
        from agent.tools.renovation import estimate_renovation_cost
        prop = _make_property(year_built=1990)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(prop, _make_offer())
        assert result["hazmat_tier"] == "none"
        prompt_text = mock_client.messages.create.call_args[1]["messages"][0]["content"]
        assert "hazmat" not in prompt_text.lower()
        assert "asbestos" not in prompt_text.lower()
        assert "lead paint" not in prompt_text.lower()

    async def test_sf_property_prompt_contains_multiplier_above_one(self):
        from agent.tools.renovation import estimate_renovation_cost
        prop = _make_property(city="San Francisco")
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(prop, _make_offer())
        assert result["regional_multiplier"] > 1.0
        prompt_text = mock_client.messages.create.call_args[1]["messages"][0]["content"]
        assert "1." in prompt_text  # multiplier like "1.18" appears in prompt

    async def test_unlikely_items_excluded_from_prompt_for_cosmetic_scope(self):
        from agent.tools.renovation import estimate_renovation_cost
        cosmetic_signals = [
            {"label": "Fixer / Contractor Special", "category": "condition_negative",
             "direction": "negative", "weight_pct": -2.0, "matched_phrases": ["cosmetic fixer"]},
        ]
        prop = _make_property(year_built=1990, detected_signals=cosmetic_signals)
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            await estimate_renovation_cost(prop, _make_offer())
        prompt_text = mock_client.messages.create.call_args[1]["messages"][0]["content"]
        # Seismic and foundation should not appear in a cosmetic scope prompt for a 1990 home
        assert "seismic" not in prompt_text.lower()
        assert "foundation" not in prompt_text.lower()

    async def test_age_era_present_in_result(self):
        from agent.tools.renovation import estimate_renovation_cost
        with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}), \
             patch("agent.tools.renovation.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = _make_llm_response(_GOOD_LLM_JSON)
            result = await estimate_renovation_cost(_make_property(year_built=1952), _make_offer())
        assert "age_era" in result
        assert result["age_era"] == "1940s_1960s"
