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


class TestDescriptionSignalAdjustments:
    def test_description_signals_do_not_affect_fair_value(self):
        """condition signals must not shift fair_value."""
        listing_fixer = {
            **BASE_LISTING,
            "description_signals": {
                "net_adjustment_pct": -2.0,
                "detected_signals": [
                    {
                        "label": "Fixer / Contractor Special",
                        "category": "condition_negative",
                        "direction": "negative",
                        "weight_pct": -2.0,
                        "matched_phrases": ["fixer"],
                    }
                ],
            },
        }
        listing_plain = {**BASE_LISTING}
        stats = {**BASE_STATS, "median_pct_over_asking": 1.0}

        result_fixer = recommend_offer(listing_fixer, stats)
        result_plain = recommend_offer(listing_plain, stats)

        assert result_fixer["fair_value_estimate"] == pytest.approx(result_plain["fair_value_estimate"])
        assert "condition_adjustment_pct" not in result_fixer
        assert "condition_adjustment_pct" not in result_fixer.get("fair_value_breakdown", {})

    def test_condition_signals_still_passed_through_for_display(self):
        listing_fixer = {
            **BASE_LISTING,
            "description_signals": {
                "net_adjustment_pct": -2.0,
                "detected_signals": [
                    {
                        "label": "Fixer / Contractor Special",
                        "category": "condition_negative",
                        "direction": "negative",
                        "weight_pct": -2.0,
                        "matched_phrases": ["fixer"],
                    }
                ],
            },
        }
        result = recommend_offer(listing_fixer, BASE_STATS)
        assert result["condition_signals"]
        assert result["condition_signals"][0]["label"] == "Fixer / Contractor Special"

    def test_offer_range_invariant_holds_with_description_adjustment(self):
        listing = {
            **BASE_LISTING,
            "description_signals": {
                "net_adjustment_pct": -3.0,
                "detected_signals": [
                    {
                        "label": "Tenant Occupied",
                        "category": "occupancy_negative",
                        "direction": "negative",
                        "weight_pct": -1.5,
                        "matched_phrases": ["tenant occupied"],
                    }
                ],
            },
        }
        result = recommend_offer(listing, BASE_STATS)
        assert result["offer_low"] <= result["offer_recommended"] <= result["offer_high"]


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
# recommend_offer — HOA equivalent no-HOA SFH value
# ---------------------------------------------------------------------------

class TestHoaEquivalentSfhValue:
    def test_returns_equivalent_sfh_value_when_hoa_fee_present(self):
        listing = {**BASE_LISTING, "hoa_fee": 1_443}
        result = recommend_offer(listing, BASE_STATS)

        hoa_equiv = result["hoa_equivalent_sfh_value"]
        assert hoa_equiv is not None
        assert hoa_equiv["monthly_hoa_fee"] == 1_443
        assert hoa_equiv["extra_purchase_power"] == 285_000
        assert hoa_equiv["equivalent_sfh_price_no_hoa"] == (
            result["offer_recommended"] + 285_000
        )

    def test_omits_equivalent_sfh_value_when_no_hoa_fee(self):
        listing = {**BASE_LISTING, "hoa_fee": None}
        result = recommend_offer(listing, BASE_STATS)
        assert result["hoa_equivalent_sfh_value"] is None

    def test_omits_equivalent_sfh_value_when_hoa_fee_zero(self):
        listing = {**BASE_LISTING, "hoa_fee": 0}
        result = recommend_offer(listing, BASE_STATS)
        assert result["hoa_equivalent_sfh_value"] is None

    def test_lower_mortgage_rate_increases_extra_purchase_power(self):
        listing = {**BASE_LISTING, "hoa_fee": 1_443}
        at_default_rate = recommend_offer(listing, BASE_STATS)
        at_lower_rate = recommend_offer(listing, BASE_STATS, mortgage_rate_pct=5.0)

        assert (
            at_lower_rate["hoa_equivalent_sfh_value"]["extra_purchase_power"]
            > at_default_rate["hoa_equivalent_sfh_value"]["extra_purchase_power"]
        )


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

    def test_lot_adjustment_skipped_for_condo(self):
        """
        For condos, lot_size is the building parcel — irrelevant to unit value.
        The lot adjustment must not be applied regardless of what lot_sqft data
        is present, and fair_value should equal the raw comp median.
        """
        condo_listing = {
            **BASE_LISTING,
            "sqft": 800,
            "lot_size": 5000,   # building parcel — would skew SFH pricing badly
            "property_type": "CONDO",
        }
        stats = {
            **BASE_STATS,
            "median_sale_price": 900_000,
            "median_comp_sqft": 800,
            "median_lot_size": 2500,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(condo_listing, stats)
        breakdown = result["fair_value_breakdown"]
        # Lot adjustment must be suppressed for condos
        assert breakdown["lot_adjustment_pct"] is None
        # Fair value should not be inflated by the parcel-size delta
        assert result["fair_value_estimate"] == 900_000

    @pytest.mark.parametrize("prop_type", ["condo", "CONDO", "Condo/Co-op", "CONDO/COOP"])
    def test_lot_adjustment_skipped_for_all_condo_type_variants(self, prop_type):
        """Condo detection must be case-insensitive and handle common homeharvest variants."""
        listing = {
            **BASE_LISTING,
            "sqft": 800,
            "lot_size": 6000,
            "property_type": prop_type,
        }
        stats = {
            **BASE_STATS,
            "median_sale_price": 800_000,
            "median_lot_size": 2500,
            "median_comp_sqft": 800,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(listing, stats)
        assert result["fair_value_breakdown"]["lot_adjustment_pct"] is None

    def test_lot_adjustment_still_applied_for_sfh(self):
        """SFH pricing must still use the lot-size adjustment (regression guard)."""
        sfh_listing = {
            **BASE_LISTING,
            "sqft": 1500,
            "lot_size": 4000,
            "property_type": "SINGLE_FAMILY",
        }
        stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "median_comp_sqft": 1500,
            "median_lot_size": 2500,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(sfh_listing, stats)
        assert result["fair_value_breakdown"]["lot_adjustment_pct"] is not None
        assert result["fair_value_estimate"] > 1_100_000


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


# ---------------------------------------------------------------------------
# recommend_offer — fair value confidence interval
# ---------------------------------------------------------------------------

class TestFairValueCI:
    def test_ci_present_in_output(self):
        result = recommend_offer(BASE_LISTING, BASE_STATS)
        ci = result["fair_value_confidence_interval"]
        assert "low" in ci and "high" in ci and "ci_pct" in ci and "confidence" in ci

    def test_ci_brackets_fair_value(self):
        result = recommend_offer(BASE_LISTING, BASE_STATS)
        ci = result["fair_value_confidence_interval"]
        assert ci["low"] < result["fair_value_estimate"] < ci["high"]

    def test_ci_high_confidence_when_many_comps_low_dispersion(self):
        stats = {
            **BASE_STATS,
            "comp_count": 15,
            "price_stdev": 50_000,
            "mean_sale_price": 1_105_000,
            "median_sale_price": 1_100_000,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(BASE_LISTING, stats)
        assert result["fair_value_confidence_interval"]["confidence"] == "high"

    def test_ci_low_confidence_when_few_comps_high_dispersion(self):
        stats = {
            **BASE_STATS,
            "comp_count": 3,
            "price_stdev": 280_000,
            "median_sale_price": 1_100_000,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(BASE_LISTING, stats)
        assert result["fair_value_confidence_interval"]["confidence"] == "low"

    def test_ci_low_confidence_for_ppsf_fallback(self):
        stats = {"median_price_per_sqft": 700.0, "median_pct_over_asking": 0.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert result["fair_value_confidence_interval"]["confidence"] == "low"

    def test_ci_widens_with_large_adjustment(self):
        """Large lot size difference (>15% total adjustment) should widen CI."""
        listing_large = {**BASE_LISTING, "sqft": 1500, "lot_size": 8000}
        listing_small = {**BASE_LISTING, "sqft": 1500, "lot_size": 2600}
        stats = {
            **BASE_STATS,
            "median_sale_price": 1_100_000,
            "median_lot_size": 2500,
            "median_comp_sqft": 1500,
            "median_pct_over_asking": 0.0,
        }
        ci_large = recommend_offer(listing_large, stats)["fair_value_confidence_interval"]["ci_pct"]
        ci_small = recommend_offer(listing_small, stats)["fair_value_confidence_interval"]["ci_pct"]
        assert ci_large > ci_small

    def test_ci_narrows_when_fair_value_converges_with_list_price(self):
        """When comp-based fair value ≈ list price, both signals agree — CI tightens slightly."""
        stats = {**BASE_STATS, "median_sale_price": 1_250_000, "median_pct_over_asking": 0.0}
        converged = recommend_offer(BASE_LISTING, stats)  # list_price = 1_250_000

        stats_far = {**BASE_STATS, "median_sale_price": 900_000, "median_pct_over_asking": 0.0}
        diverged = recommend_offer(BASE_LISTING, stats_far)

        assert (
            converged["fair_value_confidence_interval"]["ci_pct"]
            < diverged["fair_value_confidence_interval"]["ci_pct"]
        )

    def test_ci_convergence_does_not_fire_when_list_price_is_artificially_low(self):
        """List price $999k on a $1.4M property is an SF underpricing strategy — not a signal."""
        listing_under = {**BASE_LISTING, "price": 999_000}
        listing_credible = {**BASE_LISTING, "price": 1_400_000}
        stats = {**BASE_STATS, "median_sale_price": 1_400_000, "median_pct_over_asking": 0.0}

        result_under = recommend_offer(listing_under, stats)
        result_credible = recommend_offer(listing_credible, stats)

        # Artificially-low listing should not get a lower CI than the credibly-priced one
        assert (
            result_under["fair_value_confidence_interval"]["ci_pct"]
            >= result_credible["fair_value_confidence_interval"]["ci_pct"]
        )

    def test_ci_factors_few_comps(self):
        stats = {**BASE_STATS, "comp_count": 3, "median_pct_over_asking": 0.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert "few_comps" in result["fair_value_confidence_interval"]["factors"]

    def test_ci_factors_high_dispersion(self):
        stats = {
            **BASE_STATS,
            "comp_count": 10,
            "price_stdev": 350_000,
            "median_sale_price": 1_100_000,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(BASE_LISTING, stats)
        assert "high_dispersion" in result["fair_value_confidence_interval"]["factors"]

    def test_ci_factors_skewed_comps(self):
        stats = {
            **BASE_STATS,
            "comp_count": 8,
            "median_sale_price": 1_100_000,
            "mean_sale_price": 1_250_000,
            "median_pct_over_asking": 0.0,
        }
        result = recommend_offer(BASE_LISTING, stats)
        assert "skewed_comps" in result["fair_value_confidence_interval"]["factors"]

    def test_ci_factors_ppsf_fallback(self):
        stats = {"median_price_per_sqft": 700.0, "median_pct_over_asking": 0.0}
        result = recommend_offer(BASE_LISTING, stats)
        assert "ppsf_fallback" in result["fair_value_confidence_interval"]["factors"]


TIC_SIGNAL = {
    "label": "Tenancy-in-Common (TIC)",
    "category": "ownership_tic",
    "direction": "negative",
    "weight_pct": -2.0,
    "matched_phrases": [r"\bTIC\b"],
}


class TestTICFairValueDiscount:
    def test_tic_signal_reduces_fair_value_vs_no_tic(self):
        listing_no_tic = {**BASE_LISTING, "sqft": 1000}
        listing_tic = {
            **BASE_LISTING,
            "sqft": 1000,
            "description_signals": {"detected_signals": [TIC_SIGNAL]},
        }
        stats = {**BASE_STATS, "median_sale_price": 1_000_000, "median_pct_over_asking": 0.0}
        result_no_tic = recommend_offer(listing_no_tic, stats)
        result_tic = recommend_offer(listing_tic, stats)
        assert result_tic["fair_value_estimate"] < result_no_tic["fair_value_estimate"]

    def test_tic_adjustment_appears_in_breakdown(self):
        listing_tic = {
            **BASE_LISTING,
            "description_signals": {"detected_signals": [TIC_SIGNAL]},
        }
        result = recommend_offer(listing_tic, BASE_STATS)
        breakdown = result["fair_value_breakdown"]
        assert breakdown.get("tic_adjustment_pct") is not None
        assert breakdown["tic_adjustment_pct"] < 0

    def test_non_tic_listing_has_null_tic_adjustment_in_breakdown(self):
        result = recommend_offer(BASE_LISTING, BASE_STATS)
        breakdown = result["fair_value_breakdown"]
        assert breakdown.get("tic_adjustment_pct") is None

    def test_tic_discount_is_applied_to_comp_anchor(self):
        listing_tic = {
            **BASE_LISTING,
            "sqft": 1000,
            "description_signals": {"detected_signals": [TIC_SIGNAL]},
        }
        stats = {**BASE_STATS, "median_sale_price": 1_000_000, "median_pct_over_asking": 0.0}
        result = recommend_offer(listing_tic, stats)
        # Fair value must be strictly below the anchor (no lot/sqft offsets in this listing)
        assert result["fair_value_estimate"] < 1_000_000

