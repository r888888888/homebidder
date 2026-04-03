"""
Tests for deterministic listing description signal extraction.
"""

from agent.tools.description_signals import extract_description_signals


class TestExtractDescriptionSignals:
    def test_detects_representative_positive_negative_and_occupancy_phrases(self):
        text = (
            "Contractor special with great bones. Recently renovated kitchen with new appliances. "
            "Currently tenant occupied."
        )
        result = extract_description_signals(text)

        labels = {s["label"] for s in result["detected_signals"]}
        assert "Fixer / Contractor Special" in labels
        assert "Renovated / Updated" in labels
        assert "Tenant Occupied" in labels

    def test_is_case_insensitive_and_tolerates_punctuation_noise(self):
        text = "MOVE-IN READY!!! Newly REMODELED baths; sold AS-IS."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}

        assert "Renovated / Updated" in labels
        assert "Fixer / Contractor Special" in labels

    def test_conflicting_signals_net_and_are_capped_conservatively(self):
        text = (
            "Fixer. Contractor special. Needs TLC. As-is sale. "
            "Renovated and updated with new appliances and move-in ready."
        )
        result = extract_description_signals(text)
        assert -3.0 <= result["net_adjustment_pct"] <= 3.0

    def test_duplicate_phrases_do_not_double_count(self):
        text = "Fixer fixer fixer. Contractor special fixer!"
        result = extract_description_signals(text)
        fixer = next(
            s for s in result["detected_signals"] if s["label"] == "Fixer / Contractor Special"
        )
        assert fixer["weight_pct"] == -2.0

    def test_missing_or_empty_description_is_safe(self):
        for text in [None, "", "   "]:
            result = extract_description_signals(text)
            assert result["raw_description_present"] is False
            assert result["detected_signals"] == []
            assert result["net_adjustment_pct"] == 0.0
