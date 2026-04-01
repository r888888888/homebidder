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


# ---------------------------------------------------------------------------
# recommend_offer — buyer_context keyword parsing
# ---------------------------------------------------------------------------

class TestBuyerContextParsing:
    def test_multiple_offers_raises_posture_to_competitive(self):
        result = recommend_offer(BASE_LISTING, BASE_STATS, buyer_context="multiple offers expected")
        assert result["posture"] == "competitive"

    def test_fast_close_raises_posture_to_competitive(self):
        result = recommend_offer(BASE_LISTING, BASE_STATS, buyer_context="need a fast close")
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
    def test_hot_market_dom_lt_7_sets_competitive(self):
        listing = {**BASE_LISTING, "days_on_market": 5}
        stats = {**BASE_STATS, "median_pct_over_asking": 1.0}
        result = recommend_offer(listing, stats)
        assert result["posture"] == "competitive"

    def test_slow_market_dom_gt_45_sets_negotiating(self):
        listing = {**BASE_LISTING, "days_on_market": 60}
        stats = {**BASE_STATS, "median_pct_over_asking": 1.0}
        result = recommend_offer(listing, stats)
        assert result["posture"] == "negotiating"

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
    def test_advisory_present_when_dom_le_7_and_list_date_set(self):
        listing = {**BASE_LISTING, "days_on_market": 3, "list_date": "2026-03-25 00:00:00"}
        result = recommend_offer(listing, BASE_STATS)
        assert result.get("offer_review_advisory") is not None
        assert "Offer review likely" in result["offer_review_advisory"]

    def test_advisory_contains_deadline_date(self):
        listing = {**BASE_LISTING, "days_on_market": 3, "list_date": "2026-03-25 00:00:00"}
        result = recommend_offer(listing, BASE_STATS)
        # list_date + 7 days = 2026-04-01
        assert "2026-04-01" in result["offer_review_advisory"]

    def test_advisory_absent_when_dom_gt_7(self):
        listing = {**BASE_LISTING, "days_on_market": 10, "list_date": "2026-03-20 00:00:00"}
        result = recommend_offer(listing, BASE_STATS)
        assert not result.get("offer_review_advisory")

    def test_advisory_absent_when_list_date_missing(self):
        listing = {**BASE_LISTING, "days_on_market": 3, "list_date": None}
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
    def test_contingency_key_present(self):
        result = recommend_offer(BASE_LISTING, BASE_STATS)
        assert "contingency_recommendation" in result
        assert isinstance(result["contingency_recommendation"], dict)

    def test_waive_appraisal_true_when_overbid_gt_10(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 12.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["contingency_recommendation"]["waive_appraisal"] is True

    def test_waive_appraisal_false_when_overbid_lte_10(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 8.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["contingency_recommendation"]["waive_appraisal"] is False

    def test_waive_loan_always_false(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 20.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["contingency_recommendation"]["waive_loan"] is False

    def test_keep_inspection_always_true(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 20.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["contingency_recommendation"]["keep_inspection"] is True


# ---------------------------------------------------------------------------
# recommend_offer — passthrough fields
# ---------------------------------------------------------------------------

class TestPassthroughFields:
    def test_median_pct_over_asking_in_result(self):
        stats = {**BASE_STATS, "median_pct_over_asking": 8.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["median_pct_over_asking"] == pytest.approx(8.0)

    def test_pct_sold_over_asking_in_result(self):
        stats = {**BASE_STATS, "pct_sold_over_asking": 75.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["pct_sold_over_asking"] == pytest.approx(75.0)

    def test_missing_overbid_stats_returned_as_none(self):
        stats = {k: v for k, v in BASE_STATS.items()
                 if k not in ("median_pct_over_asking", "pct_sold_over_asking")}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["median_pct_over_asking"] is None
        assert result["pct_sold_over_asking"] is None
