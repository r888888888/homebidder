"""
Tests for optional LLM-based condition evaluation.
All Anthropic calls are mocked.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch


class TestEvaluateConditionWithLlm:
    async def test_returns_none_when_llm_feature_disabled(self):
        from agent.tools.condition_llm import evaluate_condition_with_llm

        with patch.dict(os.environ, {}, clear=True):
            result = await evaluate_condition_with_llm("Fixer upper")
        assert result is None

    async def test_returns_none_when_api_key_missing(self):
        from agent.tools.condition_llm import evaluate_condition_with_llm

        with patch.dict(os.environ, {"ENABLE_DESCRIPTION_LLM": "1"}, clear=True):
            result = await evaluate_condition_with_llm("Fixer upper")
        assert result is None

    async def test_parses_valid_json_and_caps_adjustment(self):
        from agent.tools.condition_llm import evaluate_condition_with_llm

        response = MagicMock()
        response.content = [MagicMock(type="text", text="""
        {
          "confidence": 0.92,
          "signals": [
            {"label": "Fixer / Contractor Special", "category": "condition_negative", "direction": "negative", "weight_pct": -4.5, "matched_phrases": ["fixer"]},
            {"label": "Tenant Occupied", "category": "occupancy_negative", "direction": "negative", "weight_pct": -2.0, "matched_phrases": ["tenant occupied"]}
          ]
        }
        """)]

        with patch.dict(
            os.environ,
            {"ENABLE_DESCRIPTION_LLM": "1", "ANTHROPIC_API_KEY": "test-key"},
            clear=True,
        ), patch("agent.tools.condition_llm.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = response

            result = await evaluate_condition_with_llm("Fixer and tenant occupied")

        assert result is not None
        assert result["source"] == "llm"
        assert result["net_adjustment_pct"] == -3.0

    async def test_low_confidence_result_is_rejected(self):
        from agent.tools.condition_llm import evaluate_condition_with_llm

        response = MagicMock()
        response.content = [MagicMock(type="text", text='{"confidence": 0.45, "signals": []}')]

        with patch.dict(
            os.environ,
            {"ENABLE_DESCRIPTION_LLM": "1", "ANTHROPIC_API_KEY": "test-key"},
            clear=True,
        ), patch("agent.tools.condition_llm.anthropic.AsyncAnthropic") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.messages.create.return_value = response

            result = await evaluate_condition_with_llm("Updated kitchen")

        assert result is None


class TestMergeSignalResults:
    def test_llm_occupancy_negative_still_adjusts_price(self):
        """LLM occupancy_negative signals do affect net_adjustment_pct."""
        from agent.tools.condition_llm import merge_signal_results

        rule_result = {
            "version": "v1",
            "raw_description_present": True,
            "detected_signals": [],
            "net_adjustment_pct": 0.0,
        }
        llm_result = {
            "source": "llm",
            "confidence": 0.9,
            "detected_signals": [{"label": "Tenant Occupied", "category": "occupancy_negative", "weight_pct": -1.5}],
            "net_adjustment_pct": -1.5,
            "model": "test-model",
        }

        merged = merge_signal_results(rule_result, llm_result)
        # occupancy_negative still contributes (capped at LLM_CONTRIBUTION_CAP_PCT=1.0)
        assert merged["net_adjustment_pct"] == -1.0
        assert merged["llm"]["used"] is True
        assert "Tenant Occupied" in [s["label"] for s in merged["detected_signals"]]

    def test_llm_condition_negative_does_not_adjust_price(self):
        """LLM condition_negative signals are surfaced for display but do not affect net_adjustment_pct."""
        from agent.tools.condition_llm import merge_signal_results

        rule_result = {
            "version": "v1",
            "raw_description_present": True,
            "detected_signals": [{"label": "Fixer / Contractor Special", "category": "condition_negative", "weight_pct": -2.0}],
            "net_adjustment_pct": -2.0,
        }
        llm_result = {
            "source": "llm",
            "confidence": 0.9,
            "detected_signals": [{"label": "Needs Work", "category": "condition_negative", "weight_pct": -2.0}],
            "net_adjustment_pct": -2.0,
            "model": "test-model",
        }

        merged = merge_signal_results(rule_result, llm_result)
        # condition_negative from LLM does NOT change the price
        assert merged["net_adjustment_pct"] == -2.0
        # but the signal still appears in detected_signals for display
        assert "Needs Work" in [s["label"] for s in merged["detected_signals"]]

    def test_llm_condition_positive_does_not_adjust_price(self):
        """LLM condition_positive signals are surfaced for display but do not affect net_adjustment_pct."""
        from agent.tools.condition_llm import merge_signal_results

        rule_result = {
            "version": "v1",
            "raw_description_present": True,
            "detected_signals": [],
            "net_adjustment_pct": 0.0,
        }
        llm_result = {
            "source": "llm",
            "confidence": 0.85,
            "detected_signals": [{"label": "Renovated / Updated", "category": "condition_positive", "weight_pct": 1.5}],
            "net_adjustment_pct": 1.5,
            "model": "test-model",
        }

        merged = merge_signal_results(rule_result, llm_result)
        assert merged["net_adjustment_pct"] == 0.0
        assert "Renovated / Updated" in [s["label"] for s in merged["detected_signals"]]

    def test_llm_mixed_signals_only_non_condition_affects_price(self):
        """When LLM returns both condition and occupancy signals, only occupancy adjusts price."""
        from agent.tools.condition_llm import merge_signal_results

        rule_result = {
            "version": "v1",
            "raw_description_present": True,
            "detected_signals": [{"label": "Fixer / Contractor Special", "category": "condition_negative", "weight_pct": -2.0}],
            "net_adjustment_pct": -2.0,
        }
        llm_result = {
            "source": "llm",
            "confidence": 0.9,
            "detected_signals": [
                {"label": "Needs Updating", "category": "condition_negative", "weight_pct": -1.5},
                {"label": "Tenant Occupied", "category": "occupancy_negative", "weight_pct": -1.0},
            ],
            "net_adjustment_pct": -2.5,
            "model": "test-model",
        }

        merged = merge_signal_results(rule_result, llm_result)
        # Only occupancy_negative (-1.0) counts; capped at 1.0 → -2.0 + -1.0 = -3.0
        assert merged["net_adjustment_pct"] == -3.0
        labels = [s["label"] for s in merged["detected_signals"]]
        assert "Needs Updating" in labels
        assert "Tenant Occupied" in labels
