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
    def test_merges_rule_and_llm_with_conservative_cap(self):
        from agent.tools.condition_llm import merge_signal_results

        rule_result = {
            "version": "v1",
            "raw_description_present": True,
            "detected_signals": [{"label": "Fixer / Contractor Special", "weight_pct": -2.0}],
            "net_adjustment_pct": -2.0,
        }
        llm_result = {
            "source": "llm",
            "confidence": 0.9,
            "detected_signals": [{"label": "Tenant Occupied", "weight_pct": -1.5}],
            "net_adjustment_pct": -1.5,
            "model": "test-model",
        }

        merged = merge_signal_results(rule_result, llm_result)
        assert merged["net_adjustment_pct"] == -3.0
        assert merged["llm"]["used"] is True
        labels = [s["label"] for s in merged["detected_signals"]]
        assert "Fixer / Contractor Special" in labels
        assert "Tenant Occupied" in labels
