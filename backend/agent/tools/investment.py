"""Pure investment-metrics calculations for Phase 8."""

from math import pow
from typing import Any

_DOWN_PAYMENT_PCT = 0.20
_ANNUAL_STOCK_RETURN_PCT = 10.0   # historical S&P 500 nominal
_MAINTENANCE_ANNUAL_PCT = 0.005   # 0.5% of property value / year


def _monthly_mortgage_payment(principal: float, annual_rate_pct: float, term_years: int = 30) -> float:
    monthly_rate = (annual_rate_pct / 100.0) / 12.0
    n = term_years * 12
    if monthly_rate <= 0:
        return principal / n
    factor = pow(1 + monthly_rate, n)
    return principal * (monthly_rate * factor) / (factor - 1)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _optional_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _opportunity_cost_fv(monthly_diff: float, years: int) -> float:
    """FV of investing monthly_diff in stocks at historical return over N years.

    Positive result: buying costs more (renting has lower monthly outlay).
    Negative result: buying is cheaper (buying has a cash-flow advantage).
    """
    r = (1 + _ANNUAL_STOCK_RETURN_PCT / 100) ** (1 / 12) - 1
    n = years * 12
    return round(monthly_diff * ((1 + r) ** n - 1) / r, 0)


def compute_investment_metrics(
    property: dict[str, Any],
    mortgage_rates: dict[str, Any],
    hpi_trend: dict[str, Any],
    ba_value_drivers: dict[str, Any],
) -> dict[str, Any]:
    """Compute appreciation projections and Bay Area value drivers."""
    price = _safe_float(property.get("price"))

    raw_rate_30 = _optional_float(mortgage_rates.get("rate_30yr_fixed"))
    rate_30 = raw_rate_30 if raw_rate_30 is not None else 6.5
    as_of_date = mortgage_rates.get("as_of_date")

    # FHFA tool emits yoy_change_pct; keep yoy_appreciation_pct as backward-compatible fallback.
    yoy_pct = _optional_float(hpi_trend.get("yoy_change_pct"))
    if yoy_pct is None:
        yoy_pct = _optional_float(hpi_trend.get("yoy_appreciation_pct"))
    if yoy_pct is None:
        yoy_pct = 0.0
    growth = 1.0 + (yoy_pct / 100.0)

    projected_1yr = round(price * pow(growth, 1), 0) if price > 0 else None
    projected_3yr = round(price * pow(growth, 3), 0) if price > 0 else None
    projected_5yr = round(price * pow(growth, 5), 0) if price > 0 else None

    # Opportunity cost vs. renting
    zip_median_rent = _optional_float(ba_value_drivers.get("zip_median_rent"))

    if price > 0 and zip_median_rent is not None:
        loan = price * (1 - _DOWN_PAYMENT_PCT)
        monthly_mortgage = _monthly_mortgage_payment(loan, rate_30)
        monthly_maintenance = price * _MAINTENANCE_ANNUAL_PCT / 12
        monthly_buy_cost = round(monthly_mortgage + monthly_maintenance, 2)
        monthly_cost_diff = round(monthly_buy_cost - zip_median_rent, 2)
        opportunity_cost_1yr = _opportunity_cost_fv(monthly_cost_diff, 1)
        opportunity_cost_3yr = _opportunity_cost_fv(monthly_cost_diff, 3)
        opportunity_cost_5yr = _opportunity_cost_fv(monthly_cost_diff, 5)
    else:
        monthly_buy_cost = None
        monthly_cost_diff = None
        opportunity_cost_1yr = None
        opportunity_cost_3yr = None
        opportunity_cost_5yr = None

    return {
        "projected_value_1yr": projected_1yr,
        "projected_value_3yr": projected_3yr,
        "projected_value_5yr": projected_5yr,
        "rate_30yr_fixed": rate_30,
        "as_of_date": as_of_date,
        "hpi_yoy_assumption_pct": yoy_pct,
        "monthly_buy_cost": monthly_buy_cost,
        "monthly_rent_equivalent": zip_median_rent,
        "monthly_cost_diff": monthly_cost_diff,
        "opportunity_cost_1yr": opportunity_cost_1yr,
        "opportunity_cost_3yr": opportunity_cost_3yr,
        "opportunity_cost_5yr": opportunity_cost_5yr,
        "rent_controlled": bool(ba_value_drivers.get("rent_controlled")),
        "rent_control_city": ba_value_drivers.get("rent_control_city"),
        "rent_control_implications": ba_value_drivers.get("implications"),
        "adu_potential": bool(ba_value_drivers.get("adu_potential")),
        "adu_rent_estimate": ba_value_drivers.get("adu_rent_estimate"),
        "nearest_bart_station": ba_value_drivers.get("nearest_bart_station"),
        "bart_distance_miles": ba_value_drivers.get("bart_distance_miles"),
        "transit_premium_likely": bool(ba_value_drivers.get("transit_premium_likely")),
        "source": {
            "rates": mortgage_rates.get("source"),
            "hpi": hpi_trend.get("source"),
        },
    }
