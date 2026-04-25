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

    def test_in_liquefaction_zone_is_moderate(self):
        # CGS data is binary: either in-zone (Moderate) or not (None).
        # No "High" level is available from this source.
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(liquefaction_risk="Moderate"),
        )
        liq_factor = next(f for f in result["factors"] if f["name"] == "liquefaction_risk")
        assert liq_factor["level"] == "moderate"
        assert "CGS Seismic Hazard Zone" in liq_factor["description"]
        assert "site" in liq_factor["description"].lower()

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



class TestOverallRiskLevel:
    def test_all_low_factors_gives_low_overall(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(year_built=2005, days_on_market=7),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(),  # all clear
            fhfa_hpi=make_fhfa(hpi_trend="appreciating"),
            neighborhood=make_neighborhood(),
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
            neighborhood=make_neighborhood(),
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
            neighborhood=make_neighborhood(),
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


class TestTenantOccupiedFactor:
    def _make_signals(self, occupied: bool) -> dict:
        if occupied:
            return {
                "version": "v1",
                "raw_description_present": True,
                "detected_signals": [
                    {
                        "label": "Tenant Occupied",
                        "category": "occupancy_negative",
                        "direction": "negative",
                        "weight_pct": -1.5,
                        "matched_phrases": [r"\btenant[-\s]?occupied\b"],
                    }
                ],
                "net_adjustment_pct": -1.5,
            }
        return {
            "version": "v1",
            "raw_description_present": True,
            "detected_signals": [],
            "net_adjustment_pct": 0.0,
        }

    def test_tenant_occupied_signal_gives_high_factor(self):
        from agent.tools.risk import assess_risk

        listing = make_listing()
        listing["description_signals"] = self._make_signals(occupied=True)
        result = assess_risk(
            listing=listing,
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        factor = next(f for f in result["factors"] if f["name"] == "tenant_occupied")
        assert factor["level"] == "high"

    def test_no_occupancy_signal_gives_low_factor(self):
        from agent.tools.risk import assess_risk

        listing = make_listing()
        listing["description_signals"] = self._make_signals(occupied=False)
        result = assess_risk(
            listing=listing,
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        factor = next(f for f in result["factors"] if f["name"] == "tenant_occupied")
        assert factor["level"] == "low"

    def test_no_description_signals_gives_na_factor(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),  # no description_signals key
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        factor = next(f for f in result["factors"] if f["name"] == "tenant_occupied")
        assert factor["level"] == "n/a"

    def test_tenant_occupied_factor_raises_overall_score(self):
        """Tenant occupied (high) should contribute +5 to risk score."""
        from agent.tools.risk import assess_risk

        listing_clean = make_listing(year_built=2005, days_on_market=7)
        result_clean = assess_risk(
            listing=listing_clean,
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(),
            fhfa_hpi=make_fhfa(hpi_trend="appreciating"),
            neighborhood=make_neighborhood(),
        )

        listing_occupied = make_listing(year_built=2005, days_on_market=7)
        listing_occupied["description_signals"] = self._make_signals(occupied=True)
        result_occupied = assess_risk(
            listing=listing_occupied,
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            hazard_zones=make_hazards(),
            fhfa_hpi=make_fhfa(hpi_trend="appreciating"),
            neighborhood=make_neighborhood(),
        )

        assert result_occupied["score"] == result_clean["score"] + 5

    def test_tenant_occupied_factor_included_in_factors_list(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        names = [f["name"] for f in result["factors"]]
        assert "tenant_occupied" in names


class TestAirQualityFactor:
    def test_high_pm25_gives_high_level(self):
        from agent.tools.risk import _assess_air_quality

        result = _assess_air_quality({"pm25_pct": 85.0})
        assert result["level"] == "high"
        assert result["name"] == "air_quality"

    def test_moderate_pm25_gives_moderate_level(self):
        from agent.tools.risk import _assess_air_quality

        result = _assess_air_quality({"pm25_pct": 65.0})
        assert result["level"] == "moderate"

    def test_low_pm25_gives_low_level(self):
        from agent.tools.risk import _assess_air_quality

        result = _assess_air_quality({"pm25_pct": 40.0})
        assert result["level"] == "low"

    def test_na_when_ces_is_none(self):
        from agent.tools.risk import _assess_air_quality

        result = _assess_air_quality(None)
        assert result["level"] == "n/a"

    def test_na_when_pm25_missing_from_ces(self):
        from agent.tools.risk import _assess_air_quality

        result = _assess_air_quality({"traffic_proximity_pct": 70.0})
        assert result["level"] == "n/a"

    def test_air_quality_factor_in_assess_risk_output(self):
        from agent.tools.risk import assess_risk

        ces = {"pm25_pct": 85.0, "traffic_proximity_pct": 50.0, "diesel_pm_pct": 50.0,
               "cleanup_sites_pct": 30.0, "groundwater_threat_pct": 30.0, "hazardous_waste_pct": 30.0}
        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            ejscreen=ces,
        )
        names = [f["name"] for f in result["factors"]]
        assert "air_quality" in names

    def test_high_air_quality_raises_score(self):
        from agent.tools.risk import assess_risk

        ces_low = {"pm25_pct": 30.0, "traffic_proximity_pct": 30.0, "diesel_pm_pct": 30.0,
                   "cleanup_sites_pct": 30.0, "groundwater_threat_pct": 30.0, "hazardous_waste_pct": 30.0}
        ces_high = {**ces_low, "pm25_pct": 85.0}

        result_low = assess_risk(
            listing=make_listing(), market_stats=make_market_stats(),
            offer_result=make_offer_result(), ejscreen=ces_low,
        )
        result_high = assess_risk(
            listing=make_listing(), market_stats=make_market_stats(),
            offer_result=make_offer_result(), ejscreen=ces_high,
        )
        assert result_high["score"] > result_low["score"]


class TestEnvironmentalContaminationFactor:
    def test_high_cleanup_pct_gives_high_level(self):
        from agent.tools.risk import _assess_environmental_contamination

        result = _assess_environmental_contamination({
            "cleanup_sites_pct": 85.0,
            "groundwater_threat_pct": 30.0,
            "hazardous_waste_pct": 20.0,
        })
        assert result["level"] == "high"
        assert result["name"] == "environmental_contamination"

    def test_high_groundwater_threat_gives_high_level(self):
        from agent.tools.risk import _assess_environmental_contamination

        result = _assess_environmental_contamination({
            "cleanup_sites_pct": 20.0,
            "groundwater_threat_pct": 82.0,
            "hazardous_waste_pct": 30.0,
        })
        assert result["level"] == "high"

    def test_high_hazardous_waste_gives_high_level(self):
        from agent.tools.risk import _assess_environmental_contamination

        result = _assess_environmental_contamination({
            "cleanup_sites_pct": 20.0,
            "groundwater_threat_pct": 30.0,
            "hazardous_waste_pct": 81.0,
        })
        assert result["level"] == "high"

    def test_moderate_when_any_between_60_and_80(self):
        from agent.tools.risk import _assess_environmental_contamination

        result = _assess_environmental_contamination({
            "cleanup_sites_pct": 65.0,
            "groundwater_threat_pct": 40.0,
            "hazardous_waste_pct": 30.0,
        })
        assert result["level"] == "moderate"

    def test_low_when_all_below_60(self):
        from agent.tools.risk import _assess_environmental_contamination

        result = _assess_environmental_contamination({
            "cleanup_sites_pct": 30.0,
            "groundwater_threat_pct": 25.0,
            "hazardous_waste_pct": 40.0,
        })
        assert result["level"] == "low"

    def test_na_when_ces_is_none(self):
        from agent.tools.risk import _assess_environmental_contamination

        result = _assess_environmental_contamination(None)
        assert result["level"] == "n/a"

    def test_contamination_factor_in_assess_risk_output(self):
        from agent.tools.risk import assess_risk

        ces = {"pm25_pct": 40.0, "traffic_proximity_pct": 40.0, "diesel_pm_pct": 40.0,
               "cleanup_sites_pct": 85.0, "groundwater_threat_pct": 30.0, "hazardous_waste_pct": 20.0}
        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            ejscreen=ces,
        )
        names = [f["name"] for f in result["factors"]]
        assert "environmental_contamination" in names

    def test_high_description_mentions_elevated_indicators(self):
        from agent.tools.risk import _assess_environmental_contamination

        result = _assess_environmental_contamination({
            "cleanup_sites_pct": 88.0,
            "groundwater_threat_pct": 91.0,
            "hazardous_waste_pct": 20.0,
        })
        assert result["level"] == "high"
        assert "cleanup" in result["description"].lower() or "groundwater" in result["description"].lower()


class TestCesCensusTract:
    def test_ces_census_tract_included_when_ejscreen_has_tract(self):
        from agent.tools.risk import assess_risk

        ces = {
            "pm25_pct": 40.0,
            "traffic_proximity_pct": 40.0,
            "diesel_pm_pct": 40.0,
            "cleanup_sites_pct": 30.0,
            "groundwater_threat_pct": 30.0,
            "hazardous_waste_pct": 20.0,
            "census_tract": "6075016100",
        }
        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            ejscreen=ces,
        )
        assert result.get("ces_census_tract") == "6075016100"

    def test_ces_census_tract_none_when_ejscreen_has_no_tract(self):
        from agent.tools.risk import assess_risk

        ces = {
            "pm25_pct": 40.0,
            "traffic_proximity_pct": 40.0,
            "diesel_pm_pct": 40.0,
            "cleanup_sites_pct": 30.0,
            "groundwater_threat_pct": 30.0,
            "hazardous_waste_pct": 20.0,
        }
        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            ejscreen=ces,
        )
        assert result.get("ces_census_tract") is None

    def test_ces_census_tract_absent_when_no_ejscreen(self):
        from agent.tools.risk import assess_risk

        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        assert result.get("ces_census_tract") is None


TIC_DESCRIPTION_SIGNALS = {
    "detected_signals": [
        {
            "label": "Tenancy-in-Common (TIC)",
            "category": "ownership_tic",
            "direction": "negative",
            "weight_pct": -2.0,
            "matched_phrases": [r"\bTIC\b"],
        }
    ]
}

EMPTY_DESCRIPTION_SIGNALS = {"detected_signals": []}


class TestTICOwnershipRiskFactor:
    def test_tic_signal_produces_moderate_risk_factor(self):
        from agent.tools.risk import assess_risk

        listing = make_listing(description_signals=TIC_DESCRIPTION_SIGNALS)
        result = assess_risk(
            listing=listing,
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        tic_factor = next(
            (f for f in result["factors"] if f["name"] == "tic_ownership"), None
        )
        assert tic_factor is not None
        assert tic_factor["level"] == "moderate"

    def test_description_present_but_no_tic_produces_low_risk_factor(self):
        from agent.tools.risk import assess_risk

        listing = make_listing(description_signals=EMPTY_DESCRIPTION_SIGNALS)
        result = assess_risk(
            listing=listing,
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        tic_factor = next(
            (f for f in result["factors"] if f["name"] == "tic_ownership"), None
        )
        assert tic_factor is not None
        assert tic_factor["level"] == "low"

    def test_no_description_signals_returns_na_risk_factor(self):
        from agent.tools.risk import assess_risk

        # make_listing() has no description_signals key — cannot assess
        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
        )
        tic_factor = next(
            (f for f in result["factors"] if f["name"] == "tic_ownership"), None
        )
        assert tic_factor is not None
        assert tic_factor["level"] == "n/a"

    def test_tic_description_signals_passed_explicitly_overrides_listing(self):
        from agent.tools.risk import assess_risk

        # Explicit description_signals kwarg should take priority over listing key
        result = assess_risk(
            listing=make_listing(),
            market_stats=make_market_stats(),
            offer_result=make_offer_result(),
            description_signals=TIC_DESCRIPTION_SIGNALS,
        )
        tic_factor = next(
            (f for f in result["factors"] if f["name"] == "tic_ownership"), None
        )
        assert tic_factor is not None
        assert tic_factor["level"] == "moderate"
