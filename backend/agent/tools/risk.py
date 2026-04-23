"""
Risk assessment tool — pure function, no I/O.

Aggregates listing, market, hazard, and neighborhood data into an overall
risk level and a list of per-factor assessments.

Scoring (additive):
  high   factor → +3
  moderate factor → +1
  low / n/a → 0

Overall:
  ≥ 9 → Very High
  ≥ 5 → High
  ≥ 2 → Moderate
  < 2 → Low
"""

from __future__ import annotations


def _factor(name: str, level: str, description: str) -> dict:
    return {"name": name, "level": level, "description": description}


# ---------------------------------------------------------------------------
# Individual factor assessors
# ---------------------------------------------------------------------------

def _assess_fault_zone(hazard_zones: dict | None) -> dict:
    if hazard_zones is None:
        return _factor(
            "alquist_priolo_fault_zone", "n/a",
            "No hazard zone data available."
        )
    if hazard_zones.get("alquist_priolo"):
        return _factor(
            "alquist_priolo_fault_zone", "high",
            "Property is within a CGS Alquist-Priolo Earthquake Fault Zone. "
            "Structures for human occupancy built across active fault traces are prohibited; "
            "retrofitting and disclosure requirements apply."
        )
    return _factor(
        "alquist_priolo_fault_zone", "low",
        "Property is not within a mapped Alquist-Priolo Earthquake Fault Zone."
    )


def _assess_flood_zone(hazard_zones: dict | None) -> dict:
    if hazard_zones is None:
        return _factor("flood_zone", "n/a", "No FEMA flood zone data available.")
    sfha = hazard_zones.get("flood_zone_sfha", False)
    zone = hazard_zones.get("flood_zone")
    if sfha:
        return _factor(
            "flood_zone", "high",
            f"Property is in FEMA Special Flood Hazard Area (zone {zone or 'unknown'}). "
            "Federal flood insurance is mandatory for federally backed mortgages."
        )
    if zone and zone != "X":
        return _factor(
            "flood_zone", "moderate",
            f"Property is in FEMA flood zone {zone} — not a SFHA, but some flood risk exists."
        )
    return _factor(
        "flood_zone", "low",
        f"Property is in FEMA flood zone {zone or 'X'} — minimal flood risk."
    )


def _assess_fire_hazard(hazard_zones: dict | None) -> dict:
    if hazard_zones is None:
        return _factor("fire_hazard_zone", "n/a", "No CalFire hazard zone data available.")
    zone = hazard_zones.get("fire_hazard_zone")
    if zone is None:
        return _factor("fire_hazard_zone", "n/a", "Property is not within a mapped CalFire Fire Hazard Severity Zone.")
    if zone == "Very High":
        return _factor(
            "fire_hazard_zone", "high",
            "Property is in a Very High Fire Hazard Severity Zone (CalFire FHSZ). "
            "Expect defensible space requirements, ember-resistant venting mandates, "
            "and significantly higher homeowner's insurance premiums."
        )
    if zone == "High":
        return _factor(
            "fire_hazard_zone", "moderate",
            "Property is in a High Fire Hazard Severity Zone (CalFire FHSZ). "
            "Defensible space and building code hardening requirements apply."
        )
    return _factor(
        "fire_hazard_zone", "low",
        f"Property is in a {zone} Fire Hazard Severity Zone — lower wildfire risk."
    )


def _assess_liquefaction(hazard_zones: dict | None) -> dict:
    if hazard_zones is None:
        return _factor("liquefaction_risk", "n/a", "No CGS liquefaction zone data available.")
    risk = hazard_zones.get("liquefaction_risk")
    if risk is None:
        return _factor("liquefaction_risk", "n/a", "Property is not within a mapped CGS liquefaction hazard zone.")
    # The CGS Seismic Hazard Zone dataset is binary: in-zone or not. All mapped
    # zones carry "Moderate" — no High/Low distinction is available from this source.
    return _factor(
        "liquefaction_risk", "moderate",
        "Property is within a CGS Seismic Hazard Zone for liquefaction — soils here may "
        "liquefy during a strong earthquake. A site-specific geotechnical investigation "
        "is typically required before development or major renovation."
    )


def _assess_home_age(listing: dict) -> dict:
    year_built = listing.get("year_built")
    if year_built is None:
        return _factor("home_age", "n/a", "Year built unknown — deferred maintenance risk cannot be estimated.")
    year_built = int(year_built)
    if year_built < 1940:
        return _factor(
            "home_age", "high",
            f"Built in {year_built} — pre-war construction may include knob-and-tube wiring, "
            "galvanized steel pipes, asbestos insulation, or lead paint. "
            "Budget for significant deferred maintenance."
        )
    if year_built < 1978:
        return _factor(
            "home_age", "moderate",
            f"Built in {year_built} — mid-century construction; potential lead paint (pre-1978) "
            "and aging systems. A thorough inspection is especially important."
        )
    return _factor(
        "home_age", "low",
        f"Built in {year_built} — modern construction standards apply; lower deferred maintenance risk."
    )


def _assess_days_on_market(listing: dict) -> dict:
    dom = listing.get("days_on_market")
    if dom is None:
        return _factor("days_on_market", "n/a", "Days on market unknown.")
    dom = int(dom)
    if dom > 60:
        return _factor(
            "days_on_market", "high",
            f"Listing has been active for {dom} days — well above the SF Bay Area median. "
            "Stale listings often signal a pricing or condition problem. Significant negotiating leverage likely."
        )
    if dom > 21:
        return _factor(
            "days_on_market", "moderate",
            f"Listing has been active for {dom} days — slightly above the local median. "
            "Some negotiating room may exist."
        )
    return _factor(
        "days_on_market", "low",
        f"Listing is fresh at {dom} days — expect competitive offers."
    )


def _assess_hpi_trend(fhfa_hpi: dict | None) -> dict:
    if fhfa_hpi is None or "error" in fhfa_hpi or "hpi_trend" not in fhfa_hpi:
        return _factor("hpi_trend", "n/a", "No FHFA HPI data available for this ZIP code.")
    trend = fhfa_hpi["hpi_trend"]
    yoy = fhfa_hpi.get("yoy_change_pct")
    yoy_str = f" ({yoy:+.1f}% YoY)" if yoy is not None else ""
    if trend == "depreciating":
        return _factor(
            "hpi_trend", "high",
            f"FHFA House Price Index is depreciating in this ZIP{yoy_str}. "
            "Buying into a declining market increases the risk of negative equity."
        )
    if trend == "flat":
        return _factor(
            "hpi_trend", "moderate",
            f"FHFA House Price Index is flat in this ZIP{yoy_str}. "
            "Limited near-term appreciation expected."
        )
    return _factor(
        "hpi_trend", "low",
        f"FHFA House Price Index is appreciating in this ZIP{yoy_str}."
    )



def _assess_tenant_occupied(description_signals: dict | None) -> dict:
    if description_signals is None:
        return _factor("tenant_occupied", "n/a", "No listing description available to assess occupancy.")
    signals = description_signals.get("detected_signals") or []
    occupied = any(s.get("category") == "occupancy_negative" for s in signals)
    if occupied:
        return _factor(
            "tenant_occupied", "high",
            "Listing indicates the property is tenant-occupied. "
            "You may be unable to move in immediately; eviction in many Bay Area cities requires just cause "
            "and can take months. Verify tenant rights, lease terms, and any rent-control protections "
            "before making an offer."
        )
    return _factor("tenant_occupied", "low", "No tenant-occupancy indicators detected in the listing description.")


def _assess_highway_proximity(ces: dict | None) -> dict:
    if ces is None:
        return _factor("highway_proximity", "n/a", "No CalEnviroScreen data available.")
    traffic_pct = ces.get("traffic_proximity_pct")
    diesel_pct = ces.get("diesel_pm_pct")
    if traffic_pct is None:
        return _factor("highway_proximity", "n/a", "No CalEnviroScreen data available.")
    if traffic_pct >= 80 and (diesel_pct or 0) >= 80:
        return _factor(
            "highway_proximity", "high",
            f"High traffic proximity ({traffic_pct:.0f}th pct) and diesel PM ({diesel_pct:.0f}th pct) — "
            "elevated pollution exposure typical of properties near major highways.",
        )
    if traffic_pct >= 80 or (diesel_pct or 0) >= 80:
        return _factor(
            "highway_proximity", "moderate",
            f"Elevated traffic proximity ({traffic_pct:.0f}th pct) — "
            "moderate pollution risk from nearby roads.",
        )
    if traffic_pct >= 60:
        return _factor(
            "highway_proximity", "moderate",
            f"Traffic proximity at {traffic_pct:.0f}th percentile — moderate highway pollution exposure.",
        )
    return _factor(
        "highway_proximity", "low",
        f"Traffic proximity at {traffic_pct:.0f}th percentile — low highway pollution exposure.",
    )


def _assess_air_quality(ces: dict | None) -> dict:
    if ces is None:
        return _factor("air_quality", "n/a", "No CalEnviroScreen data available.")
    pm25_pct = ces.get("pm25_pct")
    if pm25_pct is None:
        return _factor("air_quality", "n/a", "No CalEnviroScreen data available.")
    if pm25_pct >= 80:
        return _factor(
            "air_quality", "high",
            f"Fine particulate matter (PM2.5) at {pm25_pct:.0f}th percentile — significantly above CA average. "
            "Long-term exposure to elevated PM2.5 is linked to respiratory and cardiovascular health risks.",
        )
    if pm25_pct >= 60:
        return _factor(
            "air_quality", "moderate",
            f"Fine particulate matter (PM2.5) at {pm25_pct:.0f}th percentile — moderately elevated relative to CA.",
        )
    return _factor(
        "air_quality", "low",
        f"Fine particulate matter (PM2.5) at {pm25_pct:.0f}th percentile — within acceptable range.",
    )


def _assess_environmental_contamination(ces: dict | None) -> dict:
    if ces is None:
        return _factor("environmental_contamination", "n/a", "No CalEnviroScreen data available.")
    present = {k: v for k, v in {
        "cleanup sites": ces.get("cleanup_sites_pct"),
        "groundwater threats": ces.get("groundwater_threat_pct"),
        "hazardous waste": ces.get("hazardous_waste_pct"),
    }.items() if v is not None}
    if not present:
        return _factor("environmental_contamination", "n/a", "No CalEnviroScreen contamination data available.")

    highest = max(present.values())

    if highest >= 80:
        elevated = [f"{name} ({pct:.0f}th pct)" for name, pct in present.items() if pct >= 80]
        return _factor(
            "environmental_contamination", "high",
            f"High contamination burden: {', '.join(elevated)}. "
            "Investigate whether site-specific remediation orders, deed restrictions, or soil "
            "contamination disclosures apply to this property.",
        )
    if highest >= 60:
        elevated = [f"{name} ({pct:.0f}th pct)" for name, pct in present.items() if pct >= 60]
        return _factor(
            "environmental_contamination", "moderate",
            f"Moderate contamination burden: {', '.join(elevated)}. "
            "Review local environmental records before closing.",
        )
    return _factor(
        "environmental_contamination", "low",
        "Low environmental contamination burden in this census tract.",
    )


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

_SCORE_MAP = {"high": 5, "moderate": 2, "low": 0, "n/a": 0}


def _overall_from_score(score: int) -> str:
    if score >= 9:
        return "Very High"
    if score >= 5:
        return "High"
    if score >= 2:
        return "Moderate"
    return "Low"


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def assess_risk(
    listing: dict,
    market_stats: dict,
    offer_result: dict,
    neighborhood: dict | None = None,
    market_trends: dict | None = None,
    fhfa_hpi: dict | None = None,
    hazard_zones: dict | None = None,
    ejscreen: dict | None = None,
    description_signals: dict | None = None,
) -> dict:
    """
    Aggregate all available data into a risk assessment.

    Returns:
      overall_risk  — "Low" | "Moderate" | "High" | "Very High"
      score         — raw additive score
      factors       — list of {name, level, description} dicts
    """
    _desc_signals = description_signals or listing.get("description_signals")
    factors = [
        _assess_tenant_occupied(_desc_signals),
        _assess_fault_zone(hazard_zones),
        _assess_flood_zone(hazard_zones),
        _assess_fire_hazard(hazard_zones),
        _assess_liquefaction(hazard_zones),
        _assess_home_age(listing),
        _assess_days_on_market(listing),
        _assess_hpi_trend(fhfa_hpi),
        _assess_highway_proximity(ejscreen),
        _assess_air_quality(ejscreen),
        _assess_environmental_contamination(ejscreen),
    ]

    score = sum(_SCORE_MAP.get(f["level"], 0) for f in factors)
    overall = _overall_from_score(score)

    return {
        "overall_risk": overall,
        "score": score,
        "factors": factors,
        "ces_census_tract": (ejscreen or {}).get("census_tract"),
    }
