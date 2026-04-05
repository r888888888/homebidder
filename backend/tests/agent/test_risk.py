"""
Phase 7 risk assessment tests.
All tests call assess_risk() — a pure function with no I/O.
"""

import pytest


def make_listing(**overrides):
    base = {
        "address_matched": "450 SANCHEZ ST, SAN FRANCISCO, CA, 94114",
        "price": 1_250_000.0,
        "bedrooms": 3,
        "bathrooms": 2.0,
        "sqft": 1800,
        "year_built": 2005,
        "lot_size": 2500,
        "property_type": "SINGLE_FAMILY",
        "days_on_market": 7,
        "zip_code": "94114",
        "latitude": 37.76,
        "longitude": -122.43,
        "hoa_fee": None,
        "avm_estimate": None,
        "price_history": [],
    }
    base.update(overrides)
    return base


def make_market_stats(**overrides):
    base = {
        "comp_count": 10,
        "median_price": 1_280_000.0,
        "mean_price": 1_310_000.0,
        "median_ppsf": 720.0,
        "mean_ppsf": 735.0,
        "pct_sold_over_asking": 70.0,
        "median_pct_over_asking": 5.2,
        "median_lot_sqft": 2400.0,
        "median_sqft": 1750.0,
    }
    base.update(overrides)
    return base


def make_offer_result(**overrides):
    base = {
        "posture": "competitive",
        "fair_value": 1_295_000,
        "recommended": 1_320_000,
        "low": 1_270_000,
        "high": 1_370_000,
    }
    base.update(overrides)
    return base


def make_hazards(**overrides):
    base = {
        "alquist_priolo": False,
        "liquefaction_risk": None,
        "fire_hazard_zone": None,
        "flood_zone": None,
        "flood_zone_sfha": False,
    }
    base.update(overrides)
    return base


def make_fhfa(**overrides):
    base = {
        "zip_code": "94114",
        "yoy_change_pct": 3.2,
        "three_yr_avg_chg_pct": 2.8,
        "hpi_trend": "appreciating",
        "as_of_year": 2023,
    }
    base.update(overrides)
    return base


def make_market_trends(**overrides):
    base = {
        "zip_code": "94114",
        "months": [
            {"period_end": "2024-12-31", "median_sale_price": 1_300_000, "homes_sold": 12, "median_dom": 8, "months_of_supply": 1.2, "pct_sold_above_list": 0.72, "price_drops_pct": 0.08},
            {"period_end": "2024-11-30", "median_sale_price": 1_280_000, "homes_sold": 10, "median_dom": 10, "months_of_supply": 1.4, "pct_sold_above_list": 0.68, "price_drops_pct": 0.10},
        ],
        "trend": "appreciating",
    }
    base.update(overrides)
    return base


def make_neighborhood(**overrides):
    base = {
        "prop13_assessed_value": 420_000.0,
        "prop13_base_year": 2001,
        "prop13_annual_tax": 5_250.0,
        "median_home_value": 1_200_000,
        "housing_units": 3400,
        "vacancy_rate": 4.2,
        "median_year_built": 1958,
    }
    base.update(overrides)
    return base


class TestAssessRiskStructure:
    def test_returns_dict_with_required_keys(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        assert "overall_risk" in result
        assert "score" in result
        assert "factors" in result

    def test_overall_risk_is_valid_level(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        assert result["overall_risk"] in ("Low", "Moderate", "High", "Very High")

    def test_factors_is_list_of_dicts(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        assert isinstance(result["factors"], list)
        for factor in result["factors"]:
            assert "name" in factor
            assert "level" in factor
            assert "description" in factor
            assert factor["level"] in ("low", "moderate", "high", "n/a")

    def test_all_inputs_optional_except_listing(self):
        """assess_risk should not raise when optional inputs are None or missing."""
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        assert "overall_risk" in result

    def test_none_inputs_do_not_raise(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            neighborhood=None,
            market_trends=None,
            fhfa_hpi=None,
            hazard_zones=None,
        )
        assert "overall_risk" in result


class TestPhysicalHazardFactors:
    def test_alquist_priolo_fault_zone_is_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(alquist_priolo=True),
        )
        fault_factor = next(f for f in result["factors"] if f["name"] == "alquist_priolo_fault_zone")
        assert fault_factor["level"] == "high"

    def test_no_fault_zone_is_low(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(alquist_priolo=False),
        )
        fault_factor = next(f for f in result["factors"] if f["name"] == "alquist_priolo_fault_zone")
        assert fault_factor["level"] == "low"

    def test_flood_zone_sfha_is_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(flood_zone_sfha=True, flood_zone="AE"),
        )
        flood_factor = next(f for f in result["factors"] if f["name"] == "flood_zone")
        assert flood_factor["level"] == "high"

    def test_no_flood_zone_sfha_is_low(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(flood_zone_sfha=False, flood_zone="X"),
        )
        flood_factor = next(f for f in result["factors"] if f["name"] == "flood_zone")
        assert flood_factor["level"] == "low"

    def test_very_high_fire_zone_is_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(fire_hazard_zone="Very High"),
        )
        fire_factor = next(f for f in result["factors"] if f["name"] == "fire_hazard_zone")
        assert fire_factor["level"] == "high"

    def test_high_fire_zone_is_moderate(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(fire_hazard_zone="High"),
        )
        fire_factor = next(f for f in result["factors"] if f["name"] == "fire_hazard_zone")
        assert fire_factor["level"] == "moderate"

    def test_moderate_fire_zone_is_low(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(fire_hazard_zone="Moderate"),
        )
        fire_factor = next(f for f in result["factors"] if f["name"] == "fire_hazard_zone")
        assert fire_factor["level"] == "low"

    def test_no_fire_zone_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(fire_hazard_zone=None),
        )
        fire_factor = next(f for f in result["factors"] if f["name"] == "fire_hazard_zone")
        assert fire_factor["level"] == "n/a"

    def test_high_liquefaction_is_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(liquefaction_risk="High"),
        )
        liq_factor = next(f for f in result["factors"] if f["name"] == "liquefaction_risk")
        assert liq_factor["level"] == "high"

    def test_moderate_liquefaction_is_moderate(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(liquefaction_risk="Moderate"),
        )
        liq_factor = next(f for f in result["factors"] if f["name"] == "liquefaction_risk")
        assert liq_factor["level"] == "moderate"

    def test_no_liquefaction_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(liquefaction_risk=None),
        )
        liq_factor = next(f for f in result["factors"] if f["name"] == "liquefaction_risk")
        assert liq_factor["level"] == "n/a"

    def test_no_hazard_zones_input_gives_na_for_all_hazards(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=None,
        )
        hazard_names = {"alquist_priolo_fault_zone", "flood_zone", "fire_hazard_zone", "liquefaction_risk"}
        for factor in result["factors"]:
            if factor["name"] in hazard_names:
                assert factor["level"] == "n/a", f"Expected n/a for {factor['name']} when no hazard data"


class TestPropertyRiskFactors:
    def test_old_home_pre1940_is_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=1925),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        age_factor = next(f for f in result["factors"] if f["name"] == "home_age")
        assert age_factor["level"] == "high"

    def test_mid_century_home_is_moderate(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=1955),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        age_factor = next(f for f in result["factors"] if f["name"] == "home_age")
        assert age_factor["level"] == "moderate"

    def test_modern_home_is_low(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=1985),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        age_factor = next(f for f in result["factors"] if f["name"] == "home_age")
        assert age_factor["level"] == "low"

    def test_none_year_built_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=None),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        age_factor = next(f for f in result["factors"] if f["name"] == "home_age")
        assert age_factor["level"] == "n/a"

    def test_long_dom_is_high(self):
        """Listing sitting >60 days signals pricing problem."""
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(days_on_market=75),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        dom_factor = next(f for f in result["factors"] if f["name"] == "days_on_market")
        assert dom_factor["level"] == "high"

    def test_moderate_dom_is_moderate(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(days_on_market=40),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        dom_factor = next(f for f in result["factors"] if f["name"] == "days_on_market")
        assert dom_factor["level"] == "moderate"

    def test_fresh_listing_dom_is_low(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(days_on_market=5),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        dom_factor = next(f for f in result["factors"] if f["name"] == "days_on_market")
        assert dom_factor["level"] == "low"

    def test_none_dom_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(days_on_market=None),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        dom_factor = next(f for f in result["factors"] if f["name"] == "days_on_market")
        assert dom_factor["level"] == "n/a"


class TestMarketRiskFactors:
    def test_depreciating_hpi_is_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            fhfa_hpi=make_fhfa(hpi_trend="depreciating", yoy_change_pct=-2.5),
        )
        hpi_factor = next(f for f in result["factors"] if f["name"] == "hpi_trend")
        assert hpi_factor["level"] == "high"

    def test_flat_hpi_is_moderate(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            fhfa_hpi=make_fhfa(hpi_trend="flat", yoy_change_pct=0.3),
        )
        hpi_factor = next(f for f in result["factors"] if f["name"] == "hpi_trend")
        assert hpi_factor["level"] == "moderate"

    def test_appreciating_hpi_is_low(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            fhfa_hpi=make_fhfa(hpi_trend="appreciating", yoy_change_pct=4.1),
        )
        hpi_factor = next(f for f in result["factors"] if f["name"] == "hpi_trend")
        assert hpi_factor["level"] == "low"

    def test_no_fhfa_data_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            fhfa_hpi=None,
        )
        hpi_factor = next(f for f in result["factors"] if f["name"] == "hpi_trend")
        assert hpi_factor["level"] == "n/a"

    def test_fhfa_with_error_key_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            fhfa_hpi={"zip_code": "94114", "error": "No data found for this ZIP"},
        )
        hpi_factor = next(f for f in result["factors"] if f["name"] == "hpi_trend")
        assert hpi_factor["level"] == "n/a"


class TestProp13RiskFactor:
    def test_large_tax_shock_is_high(self):
        """Buyer pays >$15k/yr more than seller → high prop13 risk."""
        from agent.tools.risk import assess_risk

        # Purchase price $1.5M → buyer tax ~$18,750/yr; seller pays $3,000/yr
        result = assess_risk(
            listing=make_listing(price=1_500_000),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            neighborhood=make_neighborhood(prop13_annual_tax=3_000.0),
        )
        p13_factor = next(f for f in result["factors"] if f["name"] == "prop13_tax_shock")
        assert p13_factor["level"] == "high"

    def test_moderate_tax_shock_is_moderate(self):
        """Delta $8k–$15k → moderate."""
        from agent.tools.risk import assess_risk

        # Purchase price $1.25M → buyer tax ~$15,625; seller pays $6,000 → delta ~$9,625
        result = assess_risk(
            listing=make_listing(price=1_250_000),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            neighborhood=make_neighborhood(prop13_annual_tax=6_000.0),
        )
        p13_factor = next(f for f in result["factors"] if f["name"] == "prop13_tax_shock")
        assert p13_factor["level"] == "moderate"

    def test_small_tax_shock_is_low(self):
        from agent.tools.risk import assess_risk

        # Purchase price $800k → buyer tax $10k; seller pays $9,000 → delta $1,000
        result = assess_risk(
            listing=make_listing(price=800_000),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            neighborhood=make_neighborhood(prop13_annual_tax=9_000.0),
        )
        p13_factor = next(f for f in result["factors"] if f["name"] == "prop13_tax_shock")
        assert p13_factor["level"] == "low"

    def test_no_prop13_data_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            neighborhood=None,
        )
        p13_factor = next(f for f in result["factors"] if f["name"] == "prop13_tax_shock")
        assert p13_factor["level"] == "n/a"

    def test_none_prop13_annual_tax_is_na(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            neighborhood=make_neighborhood(prop13_annual_tax=None),
        )
        p13_factor = next(f for f in result["factors"] if f["name"] == "prop13_tax_shock")
        assert p13_factor["level"] == "n/a"


class TestOverallRiskLevel:
    def test_all_low_factors_gives_low_overall(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=2005, days_on_market=7),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(),  # all clear
            fhfa_hpi=make_fhfa(hpi_trend="appreciating"),
            neighborhood=make_neighborhood(prop13_annual_tax=14_000.0),  # delta < $2k
        )
        # Buyer tax at $1.25M = $15,625; seller pays $14,000 → delta $1,625 → low
        assert result["overall_risk"] == "Low"

    def test_fault_zone_alone_gives_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=2005, days_on_market=7),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(alquist_priolo=True),
            fhfa_hpi=make_fhfa(hpi_trend="appreciating"),
            neighborhood=make_neighborhood(prop13_annual_tax=14_000.0),
        )
        assert result["overall_risk"] in ("High", "Very High")

    def test_multiple_highs_gives_very_high(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=1920, days_on_market=90, price=1_500_000),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(alquist_priolo=True, flood_zone_sfha=True, fire_hazard_zone="Very High"),
            fhfa_hpi=make_fhfa(hpi_trend="depreciating"),
            neighborhood=make_neighborhood(prop13_annual_tax=3_000.0),
        )
        assert result["overall_risk"] == "Very High"

    def test_score_is_non_negative_integer(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        assert isinstance(result["score"], int)
        assert result["score"] >= 0


class TestHighwayProximityFactor:
    def test_high_when_traffic_pct_above_80_and_diesel_above_80(self):
        from agent.tools.risk import _assess_highway_proximity

        result = _assess_highway_proximity({"traffic_proximity_pct": 85.0, "diesel_pm_pct": 82.0, "ces_score_pct": 70.0})
        assert result["level"] == "high"
        assert result["name"] == "highway_proximity"

    def test_moderate_when_traffic_pct_above_80_but_diesel_below_80(self):
        from agent.tools.risk import _assess_highway_proximity

        result = _assess_highway_proximity({"traffic_proximity_pct": 82.0, "diesel_pm_pct": 50.0, "ces_score_pct": 40.0})
        assert result["level"] == "moderate"

    def test_moderate_when_traffic_pct_above_60(self):
        from agent.tools.risk import _assess_highway_proximity

        result = _assess_highway_proximity({"traffic_proximity_pct": 70.0, "diesel_pm_pct": 30.0, "ces_score_pct": 20.0})
        assert result["level"] == "moderate"

    def test_low_when_traffic_pct_below_60(self):
        from agent.tools.risk import _assess_highway_proximity

        result = _assess_highway_proximity({"traffic_proximity_pct": 40.0, "diesel_pm_pct": 20.0, "ces_score_pct": 10.0})
        assert result["level"] == "low"

    def test_na_when_ces_data_is_none(self):
        from agent.tools.risk import _assess_highway_proximity

        result = _assess_highway_proximity(None)
        assert result["level"] == "n/a"

    def test_highway_factor_included_in_assess_risk_output(self):
        from agent.tools.risk import assess_risk

        ejscreen = {"traffic_proximity_pct": 85.0, "diesel_pm_pct": 85.0, "ces_score_pct": 70.0}
        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            ejscreen=ejscreen,
        )
        names = [f["name"] for f in result["factors"]]
        assert "highway_proximity" in names
