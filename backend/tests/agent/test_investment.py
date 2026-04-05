"""
Tests for investment.py — compute_investment_metrics.
"""


class TestComputeInvestmentMetrics:
    def test_computes_metrics_with_live_rate(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_250_000, "hoa_fee": 250},
            rental_estimate={"rent_estimate": 5000},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_appreciation_pct": 4.0},
            ba_value_drivers={"adu_potential": True, "adu_rent_estimate": 2400},
        )

        assert result["gross_yield_pct"] == 4.8
        assert result["price_to_rent_ratio"] == 20.8
        assert result["rate_30yr_fixed"] == 6.5
        assert result["as_of_date"] == "2026-03-26"
        assert result["investment_rating"] == "Buy"
        assert result["adu_gross_yield_boost_pct"] > result["gross_yield_pct"]

    def test_rating_thresholds_are_bay_area_calibrated(self):
        from agent.tools.investment import compute_investment_metrics

        buy = compute_investment_metrics(
            property={"price": 1_000_000, "hoa_fee": 0},
            rental_estimate={"rent_estimate": 3200},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_appreciation_pct": 3.0},
            ba_value_drivers={"adu_potential": False, "adu_rent_estimate": None},
        )
        hold = compute_investment_metrics(
            property={"price": 1_500_000, "hoa_fee": 0},
            rental_estimate={"rent_estimate": 3800},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_appreciation_pct": 3.0},
            ba_value_drivers={"adu_potential": False, "adu_rent_estimate": None},
        )
        overpriced = compute_investment_metrics(
            property={"price": 2_000_000, "hoa_fee": 0},
            rental_estimate={"rent_estimate": 3300},
            mortgage_rates={"rate_30yr_fixed": 6.5, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_appreciation_pct": 3.0},
            ba_value_drivers={"adu_potential": False, "adu_rent_estimate": None},
        )

        assert buy["investment_rating"] == "Buy"
        assert hold["investment_rating"] == "Hold"
        assert overpriced["investment_rating"] == "Overpriced"

    def test_uses_fhfa_yoy_change_pct_for_projection_growth(self):
        from agent.tools.investment import compute_investment_metrics

        result = compute_investment_metrics(
            property={"price": 1_000_000, "hoa_fee": 0},
            rental_estimate={"rent_estimate": 3500},
            mortgage_rates={"rate_30yr_fixed": 6.2, "as_of_date": "2026-03-26"},
            hpi_trend={"yoy_change_pct": 4.0},
            ba_value_drivers={"adu_potential": False, "adu_rent_estimate": None},
        )

        assert result["projected_value_1yr"] > 1_000_000
        assert result["projected_value_3yr"] > result["projected_value_1yr"]
        assert result["projected_value_5yr"] > result["projected_value_3yr"]
