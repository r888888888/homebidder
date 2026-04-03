"""Pure investment-metrics calculations for Phase 8."""

from math import pow
from typing import Any


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


def _rating_from_yield(gross_yield_pct: float) -> str:
    if gross_yield_pct >= 3.5:
        return "Buy"
    if gross_yield_pct >= 2.5:
        return "Hold"
    return "Overpriced"


def compute_investment_metrics(
    property: dict[str, Any],
    rental_estimate: dict[str, Any],
    mortgage_rates: dict[str, Any],
    hpi_trend: dict[str, Any],
    ba_value_drivers: dict[str, Any],
    prop13_annual_tax: float | None,
) -> dict[str, Any]:
    """Compute gross yield, cashflow, appreciation projections, and investment rating."""
    price = _safe_float(property.get("price"))
    monthly_rent = _safe_float(rental_estimate.get("rent_estimate"))
    hoa = _safe_float(property.get("hoa_fee"))
    annual_tax = _safe_float(prop13_annual_tax)

    rate_30 = _safe_float(mortgage_rates.get("rate_30yr_fixed"))
    as_of_date = mortgage_rates.get("as_of_date")

    annual_rent = monthly_rent * 12
    gross_yield_pct = round((annual_rent / price) * 100, 1) if price > 0 else 0.0
    price_to_rent_ratio = round(price / annual_rent, 1) if annual_rent > 0 else None

    down_payment = 0.20 * price
    loan_principal = max(price - down_payment, 0.0)
    mortgage_monthly = _monthly_mortgage_payment(loan_principal, rate_30, term_years=30) if loan_principal > 0 else 0.0

    vacancy = monthly_rent * 0.10
    maintenance = monthly_rent * 0.10
    monthly_tax = annual_tax / 12.0
    monthly_cashflow = monthly_rent - (mortgage_monthly + monthly_tax + hoa + vacancy + maintenance)

    yoy_pct = _safe_float(hpi_trend.get("yoy_appreciation_pct"))
    growth = 1.0 + (yoy_pct / 100.0)

    projected_1yr = round(price * pow(growth, 1), 0) if price > 0 else None
    projected_3yr = round(price * pow(growth, 3), 0) if price > 0 else None
    projected_5yr = round(price * pow(growth, 5), 0) if price > 0 else None

    adu_boost = None
    if ba_value_drivers.get("adu_potential") and ba_value_drivers.get("adu_rent_estimate") is not None and price > 0:
        adu_monthly = _safe_float(ba_value_drivers.get("adu_rent_estimate"))
        adu_boost = round((((monthly_rent + adu_monthly) * 12) / price) * 100, 1)

    return {
        "gross_yield_pct": gross_yield_pct,
        "price_to_rent_ratio": price_to_rent_ratio,
        "monthly_cashflow_estimate": round(monthly_cashflow, 0),
        "adu_gross_yield_boost_pct": adu_boost,
        "projected_value_1yr": projected_1yr,
        "projected_value_3yr": projected_3yr,
        "projected_value_5yr": projected_5yr,
        "investment_rating": _rating_from_yield(gross_yield_pct),
        "rate_30yr_fixed": rate_30,
        "as_of_date": as_of_date,
        "hpi_yoy_assumption_pct": yoy_pct,
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
            "rent": rental_estimate.get("source"),
            "hpi": hpi_trend.get("source"),
        },
    }
