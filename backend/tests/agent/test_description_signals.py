"""
Tests for deterministic listing description signal extraction.
"""

from agent.tools.description_signals import extract_description_signals


class TestExtractDescriptionSignals:
    def test_detects_representative_positive_negative_and_occupancy_phrases(self):
        # When both condition signals conflict, neither appears — but occupancy still does
        text = (
            "Contractor special with great bones. Recently renovated kitchen with new appliances. "
            "Currently tenant occupied."
        )
        result = extract_description_signals(text)

        labels = {s["label"] for s in result["detected_signals"]}
        assert "Fixer / Contractor Special" not in labels
        assert "Renovated / Updated" not in labels
        assert "Tenant Occupied" in labels

    def test_is_case_insensitive_and_tolerates_punctuation_noise(self):
        # AS-IS (fixer) + MOVE-IN READY / REMODELED (renovated) conflict → neither shows
        text = "MOVE-IN READY!!! Newly REMODELED baths; sold AS-IS."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}

        assert "Renovated / Updated" not in labels
        assert "Fixer / Contractor Special" not in labels

    def test_conflicting_condition_signals_suppress_both(self):
        text = "Cosmetic fixer with a beautifully renovated kitchen."
        result = extract_description_signals(text)
        categories = {s["category"] for s in result["detected_signals"]}
        assert "condition_negative" not in categories
        assert "condition_positive" not in categories

    def test_conflicting_signals_suppress_condition_but_keep_other_signals(self):
        # Occupancy signal should survive even when condition signals conflict
        text = (
            "Fixer. Contractor special. Needs TLC. As-is sale. "
            "Renovated and updated with new appliances and move-in ready. "
            "Tenant in place."
        )
        result = extract_description_signals(text)
        categories = {s["category"] for s in result["detected_signals"]}
        assert "condition_negative" not in categories
        assert "condition_positive" not in categories
        assert "occupancy_negative" in categories

    def test_fixer_alone_shows_normally(self):
        text = "Handyman special — priced to reflect condition. Needs TLC."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Fixer / Contractor Special" in labels

    def test_renovated_alone_shows_normally(self):
        text = "Beautifully remodeled with new appliances. Turnkey and move-in ready."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Renovated / Updated" in labels

    def test_duplicate_phrases_do_not_double_count(self):
        text = "Fixer fixer fixer. Contractor special fixer!"
        result = extract_description_signals(text)
        fixer = next(
            s for s in result["detected_signals"] if s["label"] == "Fixer / Contractor Special"
        )
        assert fixer["weight_pct"] == -2.0

    def test_detects_sweat_equity_and_handyman_phrases_as_fixer(self):
        for phrase in [
            "Great opportunity for buyers willing to put in some sweat equity.",
            "Handyman special — priced to reflect condition.",
            "A diamond in the rough with incredible potential.",
        ]:
            result = extract_description_signals(phrase)
            labels = {s["label"] for s in result["detected_signals"]}
            assert "Fixer / Contractor Special" in labels, f"Expected fixer signal for: {phrase!r}"

    def test_missing_or_empty_description_is_safe(self):
        for text in [None, "", "   "]:
            result = extract_description_signals(text)
            assert result["raw_description_present"] is False
            assert result["detected_signals"] == []
            assert result["net_adjustment_pct"] == 0.0

    def test_net_adjustment_excludes_suppressed_condition_weights(self):
        # When both conflict and are suppressed, only occupancy weight remains
        text = "Fixer. Renovated. Tenant occupied."
        result = extract_description_signals(text)
        # Only occupancy_negative (-1.5) should remain
        assert result["net_adjustment_pct"] == -1.5
