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
        assert result["projected_value_1yr"] > 1_250_000
        assert result["projected_value_3yr"] > result["projected_value_1yr"]
        assert result["projected_value_5yr"] > result["projected_value_3yr"]
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

        assert result["projected_value_1yr"] > 1_000_000
        assert result["projected_value_3yr"] > result["projected_value_1yr"]
        assert result["projected_value_5yr"] > result["projected_value_3yr"]

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
        from agent.tools.investment import compute_investment_metrics, _monthly_mortgage_payment

        price = 800_000
        rate = 6.0
        rent = 3_200.0

        # Compute expected values using same helpers so we pin the formula, not the float
        loan = price * 0.80
        expected_mortgage = _monthly_mortgage_payment(loan, rate)
        expected_maintenance = price * 0.005 / 12
        expected_buy_cost = round(expected_mortgage + expected_maintenance, 2)
        expected_diff = round(expected_buy_cost - rent, 2)

        r = (1 + 10.0 / 100) ** (1 / 12) - 1
        expected_opp_10yr = round(expected_diff * ((1 + r) ** 120 - 1) / r, 0)
        expected_opp_20yr = round(expected_diff * ((1 + r) ** 240 - 1) / r, 0)
        expected_opp_30yr = round(expected_diff * ((1 + r) ** 360 - 1) / r, 0)

        result = compute_investment_metrics(
            property={"price": price},
            mortgage_rates={"rate_30yr_fixed": rate},
            hpi_trend={},
            ba_value_drivers={"zip_median_rent": rent},
        )

        assert result["monthly_buy_cost"] == pytest.approx(expected_buy_cost, abs=0.01)
        assert result["monthly_cost_diff"] == pytest.approx(expected_diff, abs=0.01)
        assert result["opportunity_cost_10yr"] == expected_opp_10yr
        assert result["opportunity_cost_20yr"] == expected_opp_20yr
        assert result["opportunity_cost_30yr"] == expected_opp_30yr

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
