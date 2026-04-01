"""
Statistical analysis of comps to derive an offer price range.
"""

import statistics
from datetime import datetime, timedelta
from typing import Any


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
    dom = listing.get("days_on_market")
    list_date = listing.get("list_date")

    # Passthrough overbid stats from market_stats
    median_overbid: float | None = market_stats.get("median_pct_over_asking")
    pct_sold_over_asking: float | None = market_stats.get("pct_sold_over_asking")

    if not list_price:
        return {"error": "Listing price unknown"}

    # Estimated fair value based on comps
    if ppsf and sqft:
        fair_value = round(ppsf * sqft)
    elif median_comp:
        fair_value = median_comp
    else:
        fair_value = list_price

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
    if posture == "competitive":
        if median_overbid is not None and median_overbid > 0:
            recommended = round(fair_value * (1 + median_overbid / 100) / 1000) * 1000
        else:
            recommended = round(list_price * 1.01 / 1000) * 1000
        # Anchor range to recommended so low <= recommended <= high always holds.
        # High is at least list_price (don't cap the aggressive end below asking).
        low = round(recommended * 0.97 / 1000) * 1000
        high = max(round(recommended * 1.03 / 1000) * 1000, round(list_price / 1000) * 1000)
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

    return {
        "list_price": list_price,
        "fair_value_estimate": fair_value,
        "offer_low": low,
        "offer_recommended": recommended,
        "offer_high": high,
        "posture": posture,
        "spread_vs_list_pct": round(spread_pct * 100, 1),
        "median_pct_over_asking": median_overbid,
        "pct_sold_over_asking": pct_sold_over_asking,
        "offer_review_advisory": offer_review_advisory,
        "contingency_recommendation": contingency_recommendation,
    }
