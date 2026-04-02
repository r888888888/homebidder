"""
Tests for pricing.py — analyze_market and recommend_offer.
Phase 5: overbid stats, buyer_context parsing, DOM velocity,
offer review advisory, contingency recommendations.
"""

import pytest
from agent.tools.pricing import analyze_market, recommend_offer


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

BASE_COMP = {
    "sold_price": 1_100_000,
    "list_price": 1_000_000,
    "sqft": 1500,
    "price_per_sqft": 733.0,
    "pct_over_asking": 10.0,
}

BASE_LISTING = {
    "price": 1_250_000,
    "sqft": 1500,
    "days_on_market": 20,
    "list_date": "2026-03-10 00:00:00",
}

BASE_STATS = {
    "comp_count": 3,
    "median_sale_price": 1_100_000,
    "median_price_per_sqft": 733.0,
    "median_pct_over_asking": 8.0,
    "pct_sold_over_asking": 100.0,
}


# ---------------------------------------------------------------------------
# analyze_market — overbid statistics
# ---------------------------------------------------------------------------

class TestAnalyzeMarketOverbidStats:
    def test_computes_median_pct_over_asking(self):
        comps = [
            {**BASE_COMP, "pct_over_asking": 2.0},
            {**BASE_COMP, "pct_over_asking": 8.0},
            {**BASE_COMP, "pct_over_asking": 12.0},
        ]
        result = analyze_market(comps)
        assert result["median_pct_over_asking"] == pytest.approx(8.0)

    def test_computes_pct_sold_over_asking(self):
        comps = [
            {**BASE_COMP, "pct_over_asking": 5.0},
            {**BASE_COMP, "pct_over_asking": -2.0},
            {**BASE_COMP, "pct_over_asking": 3.0},
        ]
        result = analyze_market(comps)
        # 2 of 3 sold over asking
        assert result["pct_sold_over_asking"] == pytest.approx(66.7, abs=0.1)

    def test_excludes_null_pct_over_asking_from_stats(self):
        comps = [
            {**BASE_COMP, "pct_over_asking": 10.0},
            {**BASE_COMP, "pct_over_asking": None},
        ]
        result = analyze_market(comps)
        assert result["median_pct_over_asking"] == pytest.approx(10.0)

    def test_overbid_fields_absent_when_all_null(self):
        comps = [
            {**BASE_COMP, "pct_over_asking": None},
            {**BASE_COMP, "pct_over_asking": None},
        ]
        result = analyze_market(comps)
        assert "median_pct_over_asking" not in result
        assert "pct_sold_over_asking" not in result

    def test_negative_pct_over_asking_included_in_median(self):
        comps = [
            {**BASE_COMP, "pct_over_asking": -5.0},
            {**BASE_COMP, "pct_over_asking": -3.0},
        ]
        result = analyze_market(comps)
        assert result["median_pct_over_asking"] == pytest.approx(-4.0)

    def test_single_comp_has_overbid_stats(self):
        comps = [{**BASE_COMP, "pct_over_asking": 10.0}]
        result = analyze_market(comps)
        assert result["median_pct_over_asking"] == pytest.approx(10.0)
        assert result["pct_sold_over_asking"] == pytest.approx(100.0)

    def test_computes_median_lot_size_and_comp_sqft(self):
        comps = [
            {**BASE_COMP, "sqft": 1300, "lot_size": 2200},
            {**BASE_COMP, "sqft": 1500, "lot_size": 2500},
            {**BASE_COMP, "sqft": 1700, "lot_size": 3100},
        ]
        result = analyze_market(comps)
        assert result["median_comp_sqft"] == 1500
        assert result["median_lot_size"] == 2500


# ---------------------------------------------------------------------------
# recommend_offer — buyer_context keyword parsing
# ---------------------------------------------------------------------------

class TestBuyerContextParsing:
    @pytest.mark.parametrize("buyer_context", [
        "multiple offers expected",
        "need a fast close",
    ])
    def test_competitive_keyword_raises_posture(self, buyer_context):
        result = recommend_offer(BASE_LISTING, BASE_STATS, buyer_context=buyer_context)
        assert result["posture"] == "competitive"

    def test_below_asking_lowers_posture_to_negotiating(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 1.0}
        result = recommend_offer(BASE_LISTING, stats, buyer_context="interested but below asking")
        assert result["posture"] == "negotiating"

    def test_buyer_context_case_insensitive(self):
        result = recommend_offer(BASE_LISTING, BASE_STATS, buyer_context="MULTIPLE OFFERS")
        assert result["posture"] == "competitive"

    def test_empty_buyer_context_no_override(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 1.0}
        result = recommend_offer(BASE_LISTING, stats, buyer_context="")
        assert result["posture"] != "competitive"


# ---------------------------------------------------------------------------
# recommend_offer — DOM market velocity
# ---------------------------------------------------------------------------

class TestMarketVelocityDom:
    @pytest.mark.parametrize("dom,expected_posture", [
        (5,  "competitive"),
        (60, "negotiating"),
    ])
    def test_dom_velocity_sets_posture(self, dom, expected_posture):
        listing = {**BASE_LISTING, "days_on_market": dom}
        stats = {**BASE_STATS, "median_pct_over_asking": 1.0}
        result = recommend_offer(listing, stats)
        assert result["posture"] == expected_posture

    def test_neutral_dom_no_velocity_override(self):
        listing = {**BASE_LISTING, "days_on_market": 20}
        stats = {**BASE_STATS, "median_pct_over_asking": 1.0}
        result = recommend_offer(listing, stats)
        # DOM alone doesn't flip at-market to competitive
        assert result["posture"] in ("at-market", "negotiating")

    def test_missing_dom_no_crash(self):
        listing = {k: v for k, v in BASE_LISTING.items() if k != "days_on_market"}
        result = recommend_offer(listing, BASE_STATS)
        assert "posture" in result


# ---------------------------------------------------------------------------
# recommend_offer — Bay Area overbid posture
# ---------------------------------------------------------------------------

class TestOverbidPosture:
    def test_competitive_posture_when_median_overbid_gt_5(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 8.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["posture"] == "competitive"

    def test_offer_recommended_includes_overbid_when_competitive(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 8.0, "median_sale_price": 1_100_000, "median_price_per_sqft": 733.0}
        listing = {**BASE_LISTING, "days_on_market": 20}
        result = recommend_offer(listing, stats)
        # recommended should be above fair_value, not just list price
        assert result["offer_recommended"] > result["fair_value_estimate"]

    def test_overbid_does_not_multiply_fair_value_directly(self):
        """
        Overbid should influence aggressiveness within the band, not full-price scaling.
        """
        stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "median_pct_over_asking": 20.0,
        }
        listing = {**BASE_LISTING, "days_on_market": 3}
        result = recommend_offer(listing, stats)

        # Old behavior would be ~1.32M (1.1M * 1.20). New behavior should be much tighter.
        assert result["offer_recommended"] < 1_200_000

    def test_at_market_when_median_overbid_lte_5(self):
        listing = {**BASE_LISTING, "days_on_market": 20}
        stats = {**BASE_STATS, "median_pct_over_asking": 3.0}
        result = recommend_offer(listing, stats)
        assert result["posture"] != "competitive"

    def test_no_overbid_stat_falls_back_to_spread(self):
        stats = {k: v for k, v in BASE_STATS.items() if k != "median_pct_over_asking"}
        result = recommend_offer(BASE_LISTING, stats)
        assert "posture" in result  # no crash; spread heuristic takes over

    def test_offer_range_invariant_low_lte_recommended_lte_high(self):
        """offer_low <= offer_recommended <= offer_high must always hold."""
        for overbid in [2.0, 8.0, 12.0, 20.0]:
            stats = {**BASE_STATS, "median_pct_over_asking": overbid}
            result = recommend_offer(BASE_LISTING, stats)
            assert result["offer_low"] <= result["offer_recommended"], f"overbid={overbid}"
            assert result["offer_recommended"] <= result["offer_high"], f"overbid={overbid}"


# ---------------------------------------------------------------------------
# recommend_offer — offer review advisory
# ---------------------------------------------------------------------------

class TestOfferReviewAdvisory:
    def test_advisory_present_with_correct_deadline(self):
        """Advisory is present and contains the correct review date (list_date + 7 days)."""
        listing = {**BASE_LISTING, "days_on_market": 3, "list_date": "2026-03-25 00:00:00"}
        result = recommend_offer(listing, BASE_STATS)
        assert result.get("offer_review_advisory") is not None
        assert "Offer review likely" in result["offer_review_advisory"]
        # list_date + 7 days = 2026-04-01
        assert "2026-04-01" in result["offer_review_advisory"]

    @pytest.mark.parametrize("dom,list_date", [
        (10, "2026-03-20 00:00:00"),  # DOM too high
        (3,  None),                   # list_date absent
    ])
    def test_advisory_absent(self, dom, list_date):
        listing = {**BASE_LISTING, "days_on_market": dom, "list_date": list_date}
        result = recommend_offer(listing, BASE_STATS)
        assert not result.get("offer_review_advisory")

    def test_advisory_date_calculation_correct(self):
        listing = {**BASE_LISTING, "days_on_market": 2, "list_date": "2026-03-28 00:00:00"}
        result = recommend_offer(listing, BASE_STATS)
        assert "2026-04-04" in result["offer_review_advisory"]


# ---------------------------------------------------------------------------
# recommend_offer — contingency recommendations
# ---------------------------------------------------------------------------

class TestContingencyRecommendations:
    @pytest.mark.parametrize("median_overbid,expected_waive", [
        (12.0, True),
        (8.0,  False),
    ])
    def test_waive_appraisal_threshold(self, median_overbid, expected_waive):
        stats = {**BASE_STATS, "median_pct_over_asking": median_overbid}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["contingency_recommendation"]["waive_appraisal"] is expected_waive

    def test_waive_loan_false_and_keep_inspection_true_regardless_of_overbid(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 20.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["contingency_recommendation"]["waive_loan"] is False
        assert result["contingency_recommendation"]["keep_inspection"] is True


# ---------------------------------------------------------------------------
# recommend_offer — passthrough fields
# ---------------------------------------------------------------------------

class TestPassthroughFields:
    def test_missing_overbid_stats_returned_as_none(self):
        stats = {k: v for k, v in BASE_STATS.items()
                 if k not in ("median_pct_over_asking", "pct_sold_over_asking")}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["median_pct_over_asking"] is None
        assert result["pct_sold_over_asking"] is None


# ---------------------------------------------------------------------------
# recommend_offer — fair value algorithm (land-aware)
# ---------------------------------------------------------------------------

class TestFairValueAlgorithm:
    def test_lot_size_increases_fair_value_when_lot_is_larger_than_comps(self):
        listing = {**BASE_LISTING, "sqft": 1500, "lot_size": 4000}
        stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "median_comp_sqft": 1500,
            "median_lot_size": 2500,
            "median_price_per_sqft": 733.0,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(listing, stats)
        assert result["fair_value_estimate"] > 1_100_000

    def test_does_not_explode_fair_value_from_ppsf_times_sqft(self):
        """
        Protect against Bay Area distortion where ppsf*sqft can overstate value.
        With median comp near $1M, fair value should stay near that anchor.
        """
        listing = {**BASE_LISTING, "sqft": 2000, "lot_size": 2500}
        stats = {
            **BASE_STATS,
            "median_sale_price": 1_000_000,
            "median_price_per_sqft": 2000.0,  # would imply $4.0M under old logic
            "median_comp_sqft": 1500,
            "median_lot_size": 2500,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(listing, stats)
        assert result["fair_value_estimate"] < 1_500_000

    def test_returns_fair_value_breakdown_with_adjustment_details(self):
        listing = {
            **BASE_LISTING,
            "sqft": 1800,
            "lot_size": 3200,
            "avm_estimate": 1_260_000,
        }
        stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "median_comp_sqft": 1500,
            "median_lot_size": 2500,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(listing, stats)
        breakdown = result["fair_value_breakdown"]
        assert breakdown["method"] == "median_comp_anchor"
        assert breakdown["lot_adjustment_pct"] is not None
        assert breakdown["sqft_adjustment_pct"] is not None
        assert breakdown["avm_blend_used"] is True

    def test_breakdown_uses_ppsf_fallback_method_when_median_comp_missing(self):
        listing = {**BASE_LISTING, "sqft": 1500}
        stats = {
            "median_price_per_sqft": 700.0,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(listing, stats)
        breakdown = result["fair_value_breakdown"]
        assert breakdown["method"] == "ppsf_fallback"
        assert breakdown["lot_adjustment_pct"] is None
        assert breakdown["sqft_adjustment_pct"] is None
        assert breakdown["avm_blend_used"] is False


# ---------------------------------------------------------------------------
# recommend_offer — dynamic offer range band
# ---------------------------------------------------------------------------

class TestDynamicOfferRangeBand:
    def test_competitive_band_widens_with_high_volatility_and_few_comps(self):
        listing = {**BASE_LISTING, "days_on_market": 2}
        high_uncertainty_stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "price_stdev": 320_000,
            "comp_count": 3,
            "median_pct_over_asking": 8.0,
        }
        low_uncertainty_stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "price_stdev": 60_000,
            "comp_count": 14,
            "median_pct_over_asking": 8.0,
        }

        high_uncertainty = recommend_offer(listing, high_uncertainty_stats)
        low_uncertainty = recommend_offer(listing, low_uncertainty_stats)

        assert high_uncertainty["offer_range_band_pct"] > low_uncertainty["offer_range_band_pct"]

    def test_defaults_to_three_percent_band_when_dispersion_data_missing(self):
        listing = {**BASE_LISTING, "days_on_market": 2}
        stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "median_pct_over_asking": 8.0,
        }
        result = recommend_offer(listing, stats)
        assert result["offer_range_band_pct"] == pytest.approx(3.0)
