"""
Tests for investment.py — compute_investment_metrics.
"""


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
