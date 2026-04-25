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

    def test_deferred_maintenance_is_fixer(self):
        text = "With significant deferred maintenance, this is truly a contractor's special."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Fixer / Contractor Special" in labels

    def test_conservatorship_sale_is_fixer(self):
        text = "This is a conservatorship sale presenting a unique chance to bring new life to the property."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Fixer / Contractor Special" in labels

    def test_probate_is_fixer(self):
        for phrase in [
            "Offered as a probate sale with court confirmation required.",
            "This is a probate property being sold by the estate.",
            "Subject to probate — priced to sell.",
        ]:
            result = extract_description_signals(phrase)
            labels = {s["label"] for s in result["detected_signals"]}
            assert "Fixer / Contractor Special" in labels, f"Expected fixer for: {phrase!r}"

    def test_sample_bernal_heights_description_is_fixer(self):
        # Full real-world description — should fire fixer, not renovated
        text = (
            "Nestled in the heart of highly sought-after Bernal Heights, this property offers a rare "
            "opportunity to restore and reimagine a classic turn-of-the-century San Francisco home. "
            "Cherished by its owner for decades, this property is rich with history and ready for its "
            "next chapter. The upper level features three bedrooms and one full bathroom, providing a "
            "traditional layout that reflects the character of its era. A new foundation installed in "
            "1990 provides an important structural upgrade while preserving the home's vintage charm "
            "above. Contractors, visionaries, and buyers seeking a project will recognize the immense "
            "potential here. With significant deferred maintenance, this is truly a contractor's special "
            "where the possibilities are as exciting as the location. Positioned for convenience, the "
            "home offers excellent access to major freeways leading to the Peninsula as well as nearby "
            "public transportation, including San Francisco Municipal Railway connections to downtown "
            "San Francisco, making it an ideal base for commuters. This is a conservatorship sale "
            "(court confirmation not required), presenting a unique chance to bring new life to a "
            "beloved property in one of the city's most vibrant neighborhoods. Opportunity knocks "
            "loudly for contractors and dreamers alike, will you answer the door?"
        )
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Fixer / Contractor Special" in labels
        assert "Renovated / Updated" not in labels

    def test_standalone_updated_does_not_trigger_renovated(self):
        # "updated" alone is too broad — should NOT fire renovated signal
        text = "Listing updated with new photos. Updated MLS status."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Renovated / Updated" not in labels

    def test_new_appliances_alone_does_not_trigger_renovated(self):
        # New appliances alone is weak signal — fixer homes can have new appliances
        text = "Property includes new appliances but requires substantial work throughout."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Renovated / Updated" not in labels

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


class TestTICSignal:
    def test_detects_tenancy_in_common_phrase(self):
        text = "This is a tenancy-in-common unit in a Victorian 4-plex."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Tenancy-in-Common (TIC)" in labels

    def test_detects_tenancy_in_common_spaced(self):
        text = "Offered as tenancy in common with separate agreements."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Tenancy-in-Common (TIC)" in labels

    def test_detects_tic_abbreviation(self):
        text = "TIC unit with fractional financing available."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Tenancy-in-Common (TIC)" in labels

    def test_detects_tenants_in_common(self):
        text = "Sold as tenants in common — each party holds an undivided interest."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Tenancy-in-Common (TIC)" in labels

    def test_tic_signal_has_ownership_tic_category(self):
        text = "TIC property in desirable Noe Valley."
        result = extract_description_signals(text)
        categories = {s["category"] for s in result["detected_signals"]}
        assert "ownership_tic" in categories

    def test_tic_signal_has_negative_direction(self):
        text = "TIC unit in Noe Valley."
        result = extract_description_signals(text)
        tic = next(s for s in result["detected_signals"] if s["category"] == "ownership_tic")
        assert tic["direction"] == "negative"

    def test_tic_applies_negative_net_adjustment(self):
        text = "TIC unit in Noe Valley."
        result = extract_description_signals(text)
        assert result["net_adjustment_pct"] < 0

    def test_tic_does_not_conflict_with_fixer(self):
        # TIC is a separate category — should not suppress fixer signals
        text = "Fixer TIC unit — bring your contractor."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Fixer / Contractor Special" in labels
        assert "Tenancy-in-Common (TIC)" in labels

    def test_tic_does_not_conflict_with_renovated(self):
        # TIC is a separate category — should not suppress renovated signals
        text = "Beautifully remodeled TIC unit — turn-key."
        result = extract_description_signals(text)
        labels = {s["label"] for s in result["detected_signals"]}
        assert "Renovated / Updated" in labels
        assert "Tenancy-in-Common (TIC)" in labels
