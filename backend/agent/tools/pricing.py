"""
Statistical analysis of comps to derive an offer price range.
"""

import statistics
from datetime import datetime, timedelta
from typing import Any


DEFAULT_MORTGAGE_RATE_PCT = 6.5
DEFAULT_MORTGAGE_TERM_YEARS = 30
DEFAULT_DOWN_PAYMENT_PCT = 20.0


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


def _monthly_payment_per_dollar(annual_rate_pct: float, term_years: int) -> float:
    """Monthly principal+interest payment for each $1 borrowed."""
    months = term_years * 12
    monthly_rate = annual_rate_pct / 100 / 12
    if monthly_rate == 0:
        return 1 / months
    return monthly_rate / (1 - (1 + monthly_rate) ** (-months))


def _compute_offer_range_band_pct(
    market_stats: dict[str, Any],
    median_comp: float | None,
) -> float:
    """
    Return uncertainty band as a decimal (e.g. 0.03 == 3%).
    Uses comp dispersion and sample size, bounded to [2%, 6%].
    """
    base_band = 0.03
    stdev = market_stats.get("price_stdev")
    comp_count = market_stats.get("comp_count")

    vol_adjustment = 0.0
    if stdev and median_comp:
        cv = stdev / median_comp
        # Around 10% CV stays near baseline; higher volatility widens.
        vol_adjustment = _clamp((cv - 0.10) * 0.50, -0.01, 0.02)

    sample_adjustment = 0.0
    if stdev and median_comp and comp_count is not None:
        if comp_count < 4:
            sample_adjustment = 0.01
        elif comp_count < 6:
            sample_adjustment = 0.005
        elif comp_count >= 12:
            sample_adjustment = -0.005

    return _clamp(base_band + vol_adjustment + sample_adjustment, 0.02, 0.06)


def _compute_fair_value_ci(
    fair_value: float,
    method: str,
    market_stats: dict[str, Any],
    total_adjustment: float,
    list_price: float,
) -> dict[str, Any]:
    """
    Return a confidence interval for the fair value estimate.

    Half-width (ci_pct) is computed additively from signals that increase or
    decrease uncertainty, then clamped to [3%, 15%].

    Confidence label: ≤5% → "high", ≤8% → "moderate", >8% → "low".
    """
    ci_pct = 5.0
    factors: list[str] = []

    # Method penalty
    if method == "ppsf_fallback":
        ci_pct += 4.0
        factors.append("ppsf_fallback")
    elif method == "list_price_fallback":
        ci_pct += 5.0
        factors.append("list_price_fallback")

    # Comp count
    comp_count = market_stats.get("comp_count")
    if comp_count is not None:
        if comp_count < 4:
            ci_pct += 3.0
            factors.append("few_comps")
        elif comp_count < 8:
            ci_pct += 1.0
            factors.append("few_comps")
        elif comp_count >= 12:
            ci_pct -= 1.0

    # Price dispersion
    median_comp = market_stats.get("median_sale_price")
    stdev = market_stats.get("price_stdev")
    if stdev and median_comp and stdev / median_comp > 0.20:
        ci_pct += 2.0
        factors.append("high_dispersion")

    # Mean/median skew (outlier-high comps inflate mean)
    mean_comp = market_stats.get("mean_sale_price")
    if mean_comp and median_comp and mean_comp / median_comp > 1.10:
        ci_pct += 1.0
        factors.append("skewed_comps")

    # Large lot/sqft adjustment applied — comps are less comparable
    if abs(total_adjustment) > 0.15:
        ci_pct += 1.0
        factors.append("large_adjustment")

    # List price convergence: only when list price is credible (not an SF underpricing play)
    # Condition: fair_value ≈ list_price (<3% apart) AND list_price >= 95% of fair_value
    if list_price and fair_value:
        spread = abs(fair_value - list_price) / list_price
        credible = list_price >= fair_value * 0.95
        if spread < 0.03 and credible:
            ci_pct -= 0.5

    ci_pct = _clamp(ci_pct, 3.0, 15.0)

    if ci_pct <= 5.0:
        confidence = "high"
    elif ci_pct <= 8.0:
        confidence = "moderate"
    else:
        confidence = "low"

    return {
        "low": round(fair_value * (1 - ci_pct / 100) / 1000) * 1000,
        "high": round(fair_value * (1 + ci_pct / 100) / 1000) * 1000,
        "ci_pct": round(ci_pct, 1),
        "confidence": confidence,
        "factors": factors,
    }


def analyze_market(comps: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Given a list of comp sales, compute market statistics.
    Returns median/mean price-per-sqft and a suggested adjustment range.

    Phase 5 additions:
    - median_pct_over_asking: median of per-comp pct_over_asking (nulls excluded)
    - pct_sold_over_asking: percentage of comps that sold above list price
    Both fields are omitted when all comps have null pct_over_asking.
    """
    prices = [c["sold_price"] for c in comps if c.get("sold_price")]
    ppsf_values = [c["price_per_sqft"] for c in comps if c.get("price_per_sqft")]
    lot_sizes = [c["lot_size"] for c in comps if c.get("lot_size")]
    comp_sqft_values = [c["sqft"] for c in comps if c.get("sqft")]

    if not prices:
        return {"error": "No valid comp prices found"}

    result: dict[str, Any] = {
        "comp_count": len(prices),
        "median_sale_price": round(statistics.median(prices)),
        "mean_sale_price": round(statistics.mean(prices)),
        "min_sale_price": round(min(prices)),
        "max_sale_price": round(max(prices)),
    }

    if ppsf_values:
        result["median_price_per_sqft"] = round(statistics.median(ppsf_values), 2)
        result["mean_price_per_sqft"] = round(statistics.mean(ppsf_values), 2)

    if lot_sizes:
        result["median_lot_size"] = round(statistics.median(lot_sizes))

    if comp_sqft_values:
        result["median_comp_sqft"] = round(statistics.median(comp_sqft_values))

    if len(prices) >= 3:
        result["price_stdev"] = round(statistics.stdev(prices))

    # Phase 5: overbid statistics — only when at least one comp has pct_over_asking
    overbid_values = [
        c["pct_over_asking"] for c in comps if c.get("pct_over_asking") is not None
    ]
    if overbid_values:
        result["median_pct_over_asking"] = round(statistics.median(overbid_values), 2)
        sold_over = sum(1 for v in overbid_values if v > 0)
        result["pct_sold_over_asking"] = round(sold_over / len(overbid_values) * 100, 1)

    return result


def recommend_offer(
    listing: dict[str, Any],
    market_stats: dict[str, Any],
    buyer_context: str = "",
    mortgage_rate_pct: float = DEFAULT_MORTGAGE_RATE_PCT,
) -> dict[str, Any]:
    """
    Produce an offer range based on listing price vs. comp market data.

    Phase 5 additions:
    - buyer_context parsing: "multiple offer"/"fast close" → competitive;
      "below asking" → negotiating (case-insensitive, highest priority)
    - DOM velocity: dom < 7 → competitive; dom > 45 → negotiating
    - median_overbid > 5 → competitive posture; offer_recommended scaled by overbid
    - offer_review_advisory: when dom <= 7 and list_date present, estimates review deadline
    - contingency_recommendation: dict with waive_appraisal/waive_loan/keep_inspection
    - median_pct_over_asking, pct_sold_over_asking passed through from market_stats (None if absent)
    """
    list_price = listing.get("price")
    median_comp = market_stats.get("median_sale_price")
    ppsf = market_stats.get("median_price_per_sqft")
    sqft = listing.get("sqft")
    lot_size = listing.get("lot_size")
    dom = listing.get("days_on_market")
    list_date = listing.get("list_date")
    median_lot_size = market_stats.get("median_lot_size")
    median_comp_sqft = market_stats.get("median_comp_sqft")
    description_signals = listing.get("description_signals") or {}
    condition_signals = description_signals.get("detected_signals") or []
    # Passthrough overbid stats from market_stats
    median_overbid: float | None = market_stats.get("median_pct_over_asking")
    pct_sold_over_asking: float | None = market_stats.get("pct_sold_over_asking")

    if not list_price:
        return {"error": "Listing price unknown"}

    # Estimated fair value:
    # - Anchor to comp median price (Bay Area land-scarcity friendly)
    # - Apply bounded lot-size and sqft adjustments when available
    # - Use ppsf*sqft only as fallback when comp median is missing
    total_adjustment = 0.0  # tracked for CI width calculation

    if median_comp:
        fair_value = median_comp

        lot_adjustment_pct: float | None = None
        sqft_adjustment_pct: float | None = None

        if lot_size and median_lot_size:
            lot_delta = (lot_size - median_lot_size) / median_lot_size
            lot_adjustment_pct = _clamp(lot_delta * 0.60, -0.20, 0.25)
            total_adjustment += lot_adjustment_pct

        if sqft and median_comp_sqft:
            sqft_delta = (sqft - median_comp_sqft) / median_comp_sqft
            sqft_adjustment_pct = _clamp(sqft_delta * 0.25, -0.10, 0.12)
            total_adjustment += sqft_adjustment_pct

        fair_value = round(fair_value * (1 + total_adjustment))
        fair_value_breakdown = {
            "method": "median_comp_anchor",
            "base_comp_median": median_comp,
            "lot_adjustment_pct": round(lot_adjustment_pct * 100, 2) if lot_adjustment_pct is not None else None,
            "sqft_adjustment_pct": round(sqft_adjustment_pct * 100, 2) if sqft_adjustment_pct is not None else None,
        }
    elif ppsf and sqft:
        fair_value = round(ppsf * sqft)
        total_adjustment = 0.0
        fair_value_breakdown = {
            "method": "ppsf_fallback",
            "base_comp_median": None,
            "lot_adjustment_pct": None,
            "sqft_adjustment_pct": None,
        }
    else:
        fair_value = round(list_price)
        total_adjustment = 0.0
        fair_value_breakdown = {
            "method": "list_price_fallback",
            "base_comp_median": None,
            "lot_adjustment_pct": None,
            "sqft_adjustment_pct": None,
        }

    # --- Fair value confidence interval ---
    fair_value_ci = _compute_fair_value_ci(
        fair_value=fair_value,
        method=fair_value_breakdown["method"],
        market_stats=market_stats,
        total_adjustment=total_adjustment,
        list_price=list_price,
    )

    # --- Posture determination (lowest to highest priority) ---

    # 1. Spread heuristic
    spread = fair_value - list_price
    spread_pct = spread / list_price

    if spread_pct >= 0.05:
        posture = "competitive"
    elif spread_pct <= -0.05:
        posture = "negotiating"
    else:
        posture = "at-market"

    # 2. Bay Area overbid stats override
    if median_overbid is not None and median_overbid > 5:
        posture = "competitive"

    # 3. DOM velocity override
    if dom is not None:
        if dom < 7:
            posture = "competitive"
        elif dom > 45:
            posture = "negotiating"

    # 4. Buyer context override (highest priority)
    ctx = buyer_context.lower()
    if "multiple offer" in ctx or "fast close" in ctx:
        posture = "competitive"
    elif "below asking" in ctx:
        posture = "negotiating"

    # --- Offer range ---
    band_pct = _compute_offer_range_band_pct(market_stats, median_comp)

    if posture == "competitive":
        # Use median overbid as an aggression signal inside the uncertainty band,
        # rather than multiplying fair value directly (avoids double-counting heat).
        if median_overbid is not None and median_overbid > 0:
            overbid_signal = _clamp(median_overbid / 20, 0.0, 1.0)
        else:
            overbid_signal = 0.0
        aggressive_fraction = 0.35 + 0.65 * overbid_signal
        recommended = round(
            fair_value * (1 + band_pct * aggressive_fraction) / 1000
        ) * 1000

        base_low = round(fair_value * (1 - band_pct) / 1000) * 1000
        base_high = round(fair_value * (1 + band_pct) / 1000) * 1000
        low = min(base_low, recommended)
        high = max(base_high, recommended, round(list_price / 1000) * 1000)
    elif posture == "negotiating":
        low = round(fair_value * 0.95 / 1000) * 1000
        recommended = round(fair_value * 0.98 / 1000) * 1000
        high = round(list_price * 0.99 / 1000) * 1000
    else:  # at-market
        low = round(list_price * 0.97 / 1000) * 1000
        recommended = round(list_price / 1000) * 1000
        high = round(list_price * 1.02 / 1000) * 1000

    # --- Offer review advisory ---
    offer_review_advisory = None
    if dom is not None and dom <= 7 and list_date:
        try:
            dt = datetime.fromisoformat(str(list_date).split()[0])
            deadline = dt + timedelta(days=7)
            offer_review_advisory = (
                f"Offer review likely — submit by {deadline.strftime('%Y-%m-%d')}"
            )
        except (ValueError, TypeError):
            pass

    # --- Contingency recommendations ---
    waive_appraisal = median_overbid is not None and median_overbid > 10
    contingency_recommendation = {
        "waive_appraisal": waive_appraisal,
        "waive_loan": False,
        "keep_inspection": True,
    }

    hoa_equivalent_sfh_value = None
    hoa_fee = listing.get("hoa_fee")
    if hoa_fee is not None and hoa_fee > 0 and recommended:
        payment_per_dollar = _monthly_payment_per_dollar(
            mortgage_rate_pct,
            DEFAULT_MORTGAGE_TERM_YEARS,
        )
        down_payment_ratio = DEFAULT_DOWN_PAYMENT_PCT / 100
        loan_capacity = hoa_fee / payment_per_dollar
        extra_purchase_power = round(loan_capacity / (1 - down_payment_ratio) / 1000) * 1000
        hoa_equivalent_sfh_value = {
            "monthly_hoa_fee": round(hoa_fee),
            "extra_purchase_power": extra_purchase_power,
            "equivalent_sfh_price_no_hoa": recommended + extra_purchase_power,
            "assumptions": {
                "mortgage_rate_pct": mortgage_rate_pct,
                "mortgage_term_years": DEFAULT_MORTGAGE_TERM_YEARS,
                "down_payment_pct": DEFAULT_DOWN_PAYMENT_PCT,
            },
        }

    return {
        "list_price": list_price,
        "fair_value_estimate": fair_value,
        "fair_value_breakdown": fair_value_breakdown,
        "fair_value_confidence_interval": fair_value_ci,
        "offer_low": low,
        "offer_recommended": recommended,
        "offer_high": high,
        "posture": posture,
        "offer_range_band_pct": round(band_pct * 100, 2),
        "spread_vs_list_pct": round(spread_pct * 100, 1),
        "condition_signals": condition_signals,
        "median_pct_over_asking": median_overbid,
        "pct_sold_over_asking": pct_sold_over_asking,
        "offer_review_advisory": offer_review_advisory,
        "contingency_recommendation": contingency_recommendation,
        "hoa_equivalent_sfh_value": hoa_equivalent_sfh_value,
    }
