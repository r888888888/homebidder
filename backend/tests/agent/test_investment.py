"""
Tests for investment.py — compute_investment_metrics.
"""

import pytest


class TestComputeInvestmentMetrics:
    def test_computes_appreciation_projections(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_250_000, "hoa_fee": 250},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_appreciation_pct": 4.0},
            ba_value_drivers={"adu_potential": True, "adu_rent_estimate": 2400},
        )

        assert result["rate_30yr_fixed"] == 6.5
        assert result["as_of_date"] == "2026-03-26"
        assert result["purchase_price"] == 1_250_000
        assert result["projected_value_10yr"] > 1_250_000
        assert result["projected_value_20yr"] > result["projected_value_10yr"]
        assert result["projected_value_30yr"] > result["projected_value_20yr"]
        assert result["adu_potential"] is True
        assert result["adu_rent_estimate"] == 2400

    def test_uses_fhfa_yoy_change_pct_for_projection_growth(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_000_000, "hoa_fee": 0},
            mortgage_rates={"rate_30yr_fixed": 6.2, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_change_pct": 4.0},
            ba_value_drivers={"adu_potential": False, "adu_rent_estimate": None},
        )

        assert result["projected_value_10yr"] > 1_000_000
        assert result["projected_value_20yr"] > result["projected_value_10yr"]
        assert result["projected_value_30yr"] > result["projected_value_20yr"]

    def test_ba_value_drivers_fields_included(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_200_000},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_change_pct": 3.0},
            ba_value_drivers={
                "adu_potential": True,
                "adu_rent_estimate": 2200,
                "rent_controlled": True,
                "rent_control_city": "San Francisco",
                "implications": "Strong tenant protections apply.",
                "nearest_bart_station": "16TH ST MISSION",
                "bart_distance_miles": 0.3,
                "transit_premium_likely": True,
            },
        )

        assert result["rent_controlled"] is True
        assert result["rent_control_city"] == "San Francisco"
        assert result["nearest_bart_station"] == "16TH ST MISSION"
        assert result["transit_premium_likely"] is True

    def test_source_dict_has_rates_and_hpi(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_000_000},
            mortgage_rates={"rate_30yr_fixed": 6.5, "source": "Freddie Mac"},
            hpi_trend={"yoy_change_pct": 3.0, "source": "FHFA"},
            ba_value_drivers={},
        )

        assert result["source"]["rates"] == "Freddie Mac"
        assert result["source"]["hpi"] == "FHFA"
        assert "rent" not in result["source"]

    def test_opportunity_cost_keys_present(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_200_000},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_change_pct": 3.0},
            ba_value_drivers={"zip_median_rent": 3500.0},
        )

        for key in ("monthly_buy_cost", "monthly_rent_equivalent", "monthly_cost_diff",
                    "opportunity_cost_10yr", "opportunity_cost_20yr", "opportunity_cost_30yr"):
            assert key in result, f"missing key: {key}"
            assert result[key] is not None

    def test_opportunity_cost_increases_with_horizon(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_200_000},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={},
            ba_value_drivers={"zip_median_rent": 3_000.0},
        )

        # buying at $1.2M vs $3k/mo rent — buying costs significantly more
        assert result["opportunity_cost_10yr"] > 0
        assert result["opportunity_cost_20yr"] > result["opportunity_cost_10yr"]
        assert result["opportunity_cost_30yr"] > result["opportunity_cost_20yr"]

    def test_opportunity_cost_exact_values(self):
        from agent.tools.investment import (
            compute_investment_metrics,
            _monthly_mortgage_payment,
            _ANNUAL_RENT_INCREASE_PCT,
        )

        price = 800_000
        rate = 6.0
        rent = 3_200.0

        loan = price * 0.80
        expected_mortgage = _monthly_mortgage_payment(loan, rate)
        expected_maintenance = price * 0.005 / 12
        expected_buy_cost = round(expected_mortgage + expected_maintenance, 2)
        expected_diff = round(expected_buy_cost - rent, 2)

        r = (1 + 10.0 / 100) ** (1 / 12) - 1
        g = (1 + _ANNUAL_RENT_INCREASE_PCT / 100) ** (1 / 12) - 1

        def expected_opp(n_months):
            return round(
                expected_buy_cost * ((1 + r) ** n_months - 1) / r
                - rent * ((1 + g) ** n_months - (1 + r) ** n_months) / (g - r),
                0,
            )

        result = compute_investment_metrics(
            property={"price": price},
            mortgage_rates={"rate_30yr_fixed": rate},
            hpi_trend={},
            ba_value_drivers={"zip_median_rent": rent},
        )

        assert result["monthly_buy_cost"] == pytest.approx(expected_buy_cost, abs=0.01)
        assert result["monthly_cost_diff"] == pytest.approx(expected_diff, abs=0.01)
        assert result["opportunity_cost_10yr"] == expected_opp(120)
        assert result["opportunity_cost_20yr"] == expected_opp(240)
        assert result["opportunity_cost_30yr"] == expected_opp(360)

    def test_rent_growth_lowers_opportunity_cost_vs_flat(self):
        """With rent growing annually, buying looks more favorable than flat-rent model."""
        from agent.tools.investment import (
            _opportunity_cost_fv,
            _ANNUAL_RENT_INCREASE_PCT,
        )

        buy_cost = 6_500.0
        rent_0 = 3_000.0

        opp_with_growth = _opportunity_cost_fv(buy_cost, rent_0, 30)

        # Simulate flat rent (0% growth) using the same function API
        # by temporarily using g=0: formula reduces to (buy-rent)*FV_annuity
        r = (1 + 10.0 / 100) ** (1 / 12) - 1
        n = 360
        opp_flat = round((buy_cost - rent_0) * ((1 + r) ** n - 1) / r, 0)

        assert _ANNUAL_RENT_INCREASE_PCT > 0, "rent growth constant should be positive"
        # Rent growth means renting gets pricier → buying looks better → lower (or less positive) opp cost
        assert opp_with_growth < opp_flat

    def test_opportunity_cost_null_when_no_rent_data(self):
        from agent.tools.investment import compute_investment_metrics

        # Missing key
        result_no_key = compute_investment_metrics(
            property={"price": 1_000_000},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={},
            ba_value_drivers={},
        )
        for key in ("monthly_buy_cost", "monthly_rent_equivalent", "monthly_cost_diff",
                    "opportunity_cost_10yr", "opportunity_cost_20yr", "opportunity_cost_30yr"):
            assert result_no_key[key] is None, f"expected None for {key}"

        # Explicit None
        result_none = compute_investment_metrics(
            property={"price": 1_000_000},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={},
            ba_value_drivers={"zip_median_rent": None},
        )
        for key in ("monthly_buy_cost", "monthly_rent_equivalent", "monthly_cost_diff",
                    "opportunity_cost_10yr", "opportunity_cost_20yr", "opportunity_cost_30yr"):
            assert result_none[key] is None, f"expected None for {key}"

    def test_negative_diff_when_renting_costs_more(self):
        from agent.tools.investment import compute_investment_metrics

        # Very high rent relative to a cheap property → renting more expensive
        result = compute_investment_metrics(
            property={"price": 400_000},
            mortgage_rates={"rate_30yr_fixed": 4.0},
            hpi_trend={},
            ba_value_drivers={"zip_median_rent": 5_000.0},
        )

        assert result["monthly_cost_diff"] < 0
        assert result["opportunity_cost_10yr"] < 0
        assert result["opportunity_cost_20yr"] < 0
        assert result["opportunity_cost_30yr"] < 0

    def test_uses_five_yr_avg_over_three_yr_avg_for_projection(self):
        """When five_yr_avg_chg_pct is provided, projections use it instead of three_yr_avg_chg_pct."""
        from agent.tools.investment import compute_investment_metrics
        from math import pow

        price = 1_000_000
        three_yr = 6.0
        five_yr = 4.5

        result = compute_investment_metrics(
            property={"price": price},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={"three_yr_avg_chg_pct": three_yr, "five_yr_avg_chg_pct": five_yr},
            ba_value_drivers={},
        )

        expected_10yr = round(price * pow(1 + five_yr / 100, 10), 0)
        assert result["projected_value_10yr"] == expected_10yr
        assert result["hpi_yoy_assumption_pct"] == five_yr

    def test_falls_back_to_three_yr_when_no_five_yr_avg(self):
        """When five_yr_avg_chg_pct is absent, falls back to three_yr_avg_chg_pct."""
        from agent.tools.investment import compute_investment_metrics
        from math import pow

        price = 1_000_000
        three_yr = 5.0

        result = compute_investment_metrics(
            property={"price": price},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={"three_yr_avg_chg_pct": three_yr},
            ba_value_drivers={},
        )

        expected_10yr = round(price * pow(1 + three_yr / 100, 10), 0)
        assert result["projected_value_10yr"] == expected_10yr
        assert result["hpi_yoy_assumption_pct"] == three_yr

    def test_uses_three_yr_avg_over_single_yoy_for_projection(self):
        """When three_yr_avg_chg_pct is provided, projections use it instead of yoy_change_pct."""
        from agent.tools.investment import compute_investment_metrics
        from math import pow

        price = 1_000_000
        yoy = 7.65     # volatile single-year value
        avg3 = 5.17    # smoothed 3-year average

        result = compute_investment_metrics(
            property={"price": price},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={"yoy_change_pct": yoy, "three_yr_avg_chg_pct": avg3},
            ba_value_drivers={},
        )

        expected_10yr = round(price * pow(1 + avg3 / 100, 10), 0)
        expected_30yr = round(price * pow(1 + avg3 / 100, 30), 0)

        assert result["projected_value_10yr"] == expected_10yr
        assert result["projected_value_30yr"] == expected_30yr
        assert result["hpi_yoy_assumption_pct"] == avg3

    def test_falls_back_to_yoy_when_no_three_yr_avg(self):
        """When three_yr_avg_chg_pct is absent, projections fall back to yoy_change_pct."""
        from agent.tools.investment import compute_investment_metrics
        from math import pow

        price = 1_000_000
        yoy = 4.0

        result = compute_investment_metrics(
            property={"price": price},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={"yoy_change_pct": yoy},
            ba_value_drivers={},
        )

        expected_10yr = round(price * pow(1 + yoy / 100, 10), 0)
        assert result["projected_value_10yr"] == expected_10yr
        assert result["hpi_yoy_assumption_pct"] == yoy

    def test_uses_fair_value_for_projections_when_provided(self):
        """When fair_value is passed, projections and purchase_price use it instead of list price."""
        from agent.tools.investment import compute_investment_metrics
        from math import pow

        list_price = 1_250_000
        fair_value = 1_100_000
        growth = 4.0

        result = compute_investment_metrics(
            property={"price": list_price},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={"yoy_change_pct": growth},
            ba_value_drivers={},
            fair_value=fair_value,
        )

        expected_10yr = round(fair_value * pow(1 + growth / 100, 10), 0)
        assert result["purchase_price"] == fair_value
        assert result["projected_value_10yr"] == expected_10yr
        assert result["projected_value_10yr"] != round(list_price * pow(1 + growth / 100, 10), 0)

    def test_uses_fair_value_for_opportunity_cost(self):
        """When fair_value is passed, monthly mortgage is computed from fair value, not list price."""
        from agent.tools.investment import compute_investment_metrics, _monthly_mortgage_payment

        list_price = 1_500_000
        fair_value = 1_200_000
        rent = 4_000.0

        result = compute_investment_metrics(
            property={"price": list_price},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={},
            ba_value_drivers={"zip_median_rent": rent},
            fair_value=fair_value,
        )

        expected_loan = fair_value * 0.80
        expected_mortgage = _monthly_mortgage_payment(expected_loan, 6.5)
        expected_maintenance = fair_value * 0.005 / 12
        expected_buy_cost = round(expected_mortgage + expected_maintenance, 2)

        assert result["monthly_buy_cost"] == pytest.approx(expected_buy_cost, abs=0.01)

    def test_falls_back_to_list_price_when_no_fair_value(self):
        """Without fair_value, behavior is unchanged — list price is used."""
        from agent.tools.investment import compute_investment_metrics
        from math import pow

        price = 900_000
        growth = 3.5

        result = compute_investment_metrics(
            property={"price": price},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={"yoy_change_pct": growth},
            ba_value_drivers={},
        )

        expected_10yr = round(price * pow(1 + growth / 100, 10), 0)
        assert result["purchase_price"] == price
        assert result["projected_value_10yr"] == expected_10yr

    def test_muni_fields_passed_through_from_ba_value_drivers(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_200_000},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_change_pct": 3.0},
            ba_value_drivers={
                "nearest_muni_stop": "Castro St",
                "muni_distance_miles": 0.15,
            },
        )

        assert result["nearest_muni_stop"] == "Castro St"
        assert result["muni_distance_miles"] == 0.15

    def test_muni_fields_are_none_when_absent(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_000_000},
            mortgage_rates={"rate_30yr_fixed": 6.5},
            hpi_trend={},
            ba_value_drivers={},
        )

        assert result["nearest_muni_stop"] is None
        assert result["muni_distance_miles"] is None
