"""
Tool: fetch_neighborhood_context

Pulls Census ACS neighborhood statistics for any US address.

Census ACS fallback requires CENSUS_API_KEY env var.
"""

import os
from typing import Any

import httpx


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

async def fetch_neighborhood_context(
    county: str,
    state: str,
    zip_code: str,
    address_matched: str,
) -> dict[str, Any]:
    """
    Fetch Census ACS neighborhood statistics.

    Returns keys:
      median_home_value, housing_units, vacancy_rate, median_year_built
    """
    return await _fetch_acs(zip_code)


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
