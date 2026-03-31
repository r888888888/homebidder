"""
Statistical analysis of comps to derive an offer price range.
"""

import statistics
from typing import Any


def analyze_market(comps: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Given a list of comp sales, compute market statistics.
    Returns median/mean price-per-sqft and a suggested adjustment range.
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

    return result


def recommend_offer(
    listing: dict[str, Any],
    market_stats: dict[str, Any],
    buyer_context: str = "",
) -> dict[str, Any]:
    """
    Produce an offer range based on listing price vs. comp market data.
    This is a starting heuristic; the LLM refines the rationale.
    """
    list_price = listing.get("price")
    median_comp = market_stats.get("median_sale_price")
    ppsf = market_stats.get("median_price_per_sqft")
    sqft = listing.get("sqft")

    if not list_price:
        return {"error": "Listing price unknown"}

    # Estimated fair value based on comps
    if ppsf and sqft:
        fair_value = round(ppsf * sqft)
    elif median_comp:
        fair_value = median_comp
    else:
        fair_value = list_price

    # Price spread: comps below list → negotiate; above list → compete
    spread = fair_value - list_price
    spread_pct = spread / list_price

    if spread_pct >= 0.05:
        # Comps support higher value — list price is a deal
        low = round(list_price * 0.99 / 1000) * 1000
        recommended = round(list_price * 1.01 / 1000) * 1000
        high = round(list_price * 1.04 / 1000) * 1000
        posture = "competitive"
    elif spread_pct <= -0.05:
        # List price above comps — room to negotiate down
        low = round(fair_value * 0.95 / 1000) * 1000
        recommended = round(fair_value * 0.98 / 1000) * 1000
        high = round(list_price * 0.99 / 1000) * 1000
        posture = "negotiating"
    else:
        # At-market
        low = round(list_price * 0.97 / 1000) * 1000
        recommended = round(list_price / 1000) * 1000
        high = round(list_price * 1.02 / 1000) * 1000
        posture = "at-market"

    return {
        "list_price": list_price,
        "fair_value_estimate": fair_value,
        "offer_low": low,
        "offer_recommended": recommended,
        "offer_high": high,
        "posture": posture,
        "spread_vs_list_pct": round(spread_pct * 100, 1),
    }
