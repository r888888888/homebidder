"""
Tool: fetch_neighborhood_context

Pulls Prop 13 assessed-value data from Bay Area county assessor APIs and
Census ACS neighborhood statistics as a fallback.

Supported primary paths (Prop 13):
  - San Francisco → DataSF Assessor-Recorder API
  - Alameda       → Alameda County ArcGIS REST
  - Santa Clara   → Santa Clara County open-data endpoint
  - All others    → no Prop 13 data; Census ACS fallback for neighborhood stats

Census ACS fallback requires CENSUS_API_KEY env var.
"""

import os
from typing import Any
from urllib.parse import urlencode, quote

import httpx

CA_TAX_RATE = 0.0125  # CA effective property tax rate (~1.25%)

# DataSF stores street types in abbreviated form (e.g. AVE→AV, BLVD→BL).
# Strip the trailing type suffix before building the LIKE search so that
# "319 PLYMOUTH AVE" matches "0000 0319 PLYMOUTH            AV0000".
_STREET_SUFFIXES = {
    "AVE", "AVENUE", "BLVD", "BOULEVARD", "CT", "COURT",
    "DR", "DRIVE", "LN", "LANE", "PL", "PLACE",
    "RD", "ROAD", "ST", "STREET", "WAY",
    "TER", "TERRACE", "CIR", "CIRCLE", "HWY", "HIGHWAY",
}


def _sf_search_term(street: str) -> str:
    """Return the street string with trailing type suffix removed for LIKE matching."""
    parts = street.split()
    if len(parts) > 2 and parts[-1].upper() in _STREET_SUFFIXES:
        return " ".join(parts[:-1])
    return street


# Counties with primary Prop 13 assessor path
_SF_COUNTY = "San Francisco"
_ALAMEDA_COUNTY = "Alameda"
_SANTA_CLARA_COUNTY = "Santa Clara"
_SUPPORTED_PROP13 = {_SF_COUNTY, _ALAMEDA_COUNTY, _SANTA_CLARA_COUNTY}


async def fetch_neighborhood_context(
    county: str,
    state: str,
    zip_code: str,
    address_matched: str,
) -> dict[str, Any]:
    """
    Fetch Prop 13 assessed-value data and Census ACS neighborhood statistics.

    Returns keys:
      median_home_value, housing_units, vacancy_rate, median_year_built,
      prop13_assessed_value, prop13_base_year, prop13_annual_tax
    """
    prop13: dict[str, Any] = {
        "prop13_assessed_value": None,
        "prop13_base_year": None,
        "prop13_annual_tax": None,
    }

    if state == "CA" and county in _SUPPORTED_PROP13:
        prop13 = await _fetch_prop13(county, address_matched)

    acs = await _fetch_acs(zip_code)

    return {**acs, **prop13}


# ---------------------------------------------------------------------------
# Prop 13 — county assessor paths
# ---------------------------------------------------------------------------

async def _fetch_prop13(county: str, address_matched: str) -> dict[str, Any]:
    null = {"prop13_assessed_value": None, "prop13_base_year": None, "prop13_annual_tax": None}
    try:
        if county == _SF_COUNTY:
            return await _sf_assessor(address_matched)
        if county == _ALAMEDA_COUNTY:
            return await _alameda_assessor(address_matched)
        if county == _SANTA_CLARA_COUNTY:
            return await _santa_clara_assessor(address_matched)
    except Exception:
        pass
    return null


def _prop13_result(assessed_land: float, assessed_impr: float, base_year: int) -> dict[str, Any]:
    total = assessed_land + assessed_impr
    return {
        "prop13_assessed_value": total,
        "prop13_base_year": base_year,
        "prop13_annual_tax": round(total * CA_TAX_RATE, 2),
    }


async def _sf_assessor(address_matched: str) -> dict[str, Any]:
    """DataSF Assessor-Recorder API — keyed on street address."""
    # Extract street portion: "319 PLYMOUTH AVE, SAN FRANCISCO, CA, 94112" → "319 PLYMOUTH AVE"
    # Strip trailing type suffix so "319 PLYMOUTH AVE" → "319 PLYMOUTH" (DB stores "AV" not "AVE")
    street = address_matched.split(",")[0].strip()
    search_term = _sf_search_term(street)
    params = {
        "$where": f"upper(property_location) like '%{search_term}%'",
        "$order": "closed_roll_year DESC",
        "$limit": 1,
        "$select": "assessed_land_value,assessed_improvement_value,closed_roll_year,property_location",
    }
    url = "https://data.sfgov.org/resource/wv5m-vpq2.json?" + urlencode(params)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        rows = resp.json()

    if not rows:
        return {"prop13_assessed_value": None, "prop13_base_year": None, "prop13_annual_tax": None}

    row = rows[0]
    land = float(row.get("assessed_land_value") or 0)
    impr = float(row.get("assessed_improvement_value") or 0)
    base_year = int(row.get("closed_roll_year") or 0) or None
    if base_year is None:
        return {"prop13_assessed_value": None, "prop13_base_year": None, "prop13_annual_tax": None}
    return _prop13_result(land, impr, base_year)


async def _alameda_assessor(address_matched: str) -> dict[str, Any]:
    """Alameda County parcel data via ArcGIS REST."""
    street = address_matched.split(",")[0].strip()
    params = {
        "where": f"UPPER(SITUS_ADDR) LIKE '%{street}%'",
        "outFields": "ASSESSED_LAND,ASSESSED_IMPR,YEAR_BUILT,TAX_YEAR",
        "returnGeometry": "false",
        "f": "json",
        "resultRecordCount": 1,
    }
    url = (
        "https://data.acgov.org/datasets/ac-county-assessor-parcel-data"
        "/arcgis/rest/services/ParcelData/FeatureServer/0/query?" + urlencode(params)
    )

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()

    features = data.get("features", [])
    if not features:
        return {"prop13_assessed_value": None, "prop13_base_year": None, "prop13_annual_tax": None}

    attrs = features[0]["attributes"]
    land = float(attrs.get("ASSESSED_LAND") or 0)
    impr = float(attrs.get("ASSESSED_IMPR") or 0)
    base_year = int(attrs.get("TAX_YEAR") or 0) or None
    if base_year is None:
        return {"prop13_assessed_value": None, "prop13_base_year": None, "prop13_annual_tax": None}
    return _prop13_result(land, impr, base_year)


async def _santa_clara_assessor(address_matched: str) -> dict[str, Any]:
    """Santa Clara County assessor open-data endpoint."""
    street = address_matched.split(",")[0].strip()
    params = {
        "$where": f"upper(situs_address) like '%{street}%'",
        "$limit": 1,
        "$select": "assessed_land_value,assessed_improvement_value,year_built,tax_year",
    }
    url = "https://data.sccgov.org/resource/assessor-parcel.json?" + urlencode(params)

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()
        rows = resp.json()

    if not rows:
        return {"prop13_assessed_value": None, "prop13_base_year": None, "prop13_annual_tax": None}

    row = rows[0]
    land = float(row.get("assessed_land_value") or 0)
    impr = float(row.get("assessed_improvement_value") or 0)
    base_year = int(row.get("tax_year") or 0) or None
    if base_year is None:
        return {"prop13_assessed_value": None, "prop13_base_year": None, "prop13_annual_tax": None}
    return _prop13_result(land, impr, base_year)


# ---------------------------------------------------------------------------
# Census ACS fallback — neighborhood statistics
# ---------------------------------------------------------------------------

_NULL_ACS: dict[str, Any] = {
    "median_home_value": None,
    "housing_units": None,
    "vacancy_rate": None,
    "median_year_built": None,
}

_ACS_VARS = ",".join([
    "B25077_001E",  # median home value
    "B25001_001E",  # total housing units
    "B25004_002E",  # vacant — for rent
    "B25004_001E",  # total vacant units (all reasons)  ← used for vacancy rate
    "B25035_001E",  # median year structure built
])


async def _fetch_acs(zip_code: str) -> dict[str, Any]:
    api_key = os.environ.get("CENSUS_API_KEY")
    if not api_key or not zip_code:
        return _NULL_ACS

    url = (
        f"https://api.census.gov/data/2022/acs/acs5"
        f"?get={_ACS_VARS}&for=zip+code+tabulation+area:{zip_code}&key={api_key}"
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
    except Exception:
        return _NULL_ACS

    if len(data) < 2:
        return _NULL_ACS

    headers, row = data[0], data[1]

    def _get(var: str) -> float | None:
        try:
            idx = headers.index(var)
            val = int(row[idx])
            return None if val < 0 else float(val)
        except (ValueError, IndexError):
            return None

    total_units = _get("B25001_001E")
    vacant_units = _get("B25004_001E")
    vacancy_rate: float | None = None
    if total_units and vacant_units is not None and total_units > 0:
        vacancy_rate = round(vacant_units / total_units * 100, 1)

    return {
        "median_home_value": _get("B25077_001E"),
        "housing_units": int(total_units) if total_units else None,
        "vacancy_rate": vacancy_rate,
        "median_year_built": int(_get("B25035_001E")) if _get("B25035_001E") else None,
    }
