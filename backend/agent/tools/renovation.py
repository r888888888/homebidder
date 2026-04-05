"""
LLM-based renovation cost estimator for fixer properties.
"""

import json
import os
import re
from typing import Any

import anthropic

DEFAULT_MODEL = "claude-haiku-4-5-20251001"


def _is_fixer_property(property_data: dict) -> bool:
    signals = (property_data.get("description_signals") or {}).get("detected_signals") or []
    return any(s.get("category") == "condition_negative" for s in signals)


def _extract_json_object(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if not text:
        return None
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    m = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not m:
        return None
    try:
        parsed = json.loads(m.group(0))
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        return None
    return None


async def estimate_renovation_cost(
    property_data: dict[str, Any],
    offer_result: dict[str, Any],
    buyer_context: str = "",
) -> dict[str, Any] | None:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    fair_value = offer_result.get("fair_value_estimate")
    if fair_value is None:
        return None

    offer_recommended = offer_result.get("offer_recommended") or 0
    if not offer_recommended:
        return None

    signals = (property_data.get("description_signals") or {}).get("detected_signals") or []
    fixer_signals = [s["label"] for s in signals if s.get("category") == "condition_negative"]
    fixer_phrases = []
    for s in signals:
        if s.get("category") == "condition_negative":
            fixer_phrases.extend(s.get("matched_phrases") or [])

    model = os.getenv("RENOVATION_LLM_MODEL", DEFAULT_MODEL)
    client = anthropic.AsyncAnthropic(api_key=api_key)

    prompt = (
        "You are an experienced SF Bay Area general contractor estimating renovation costs for a buyer's due diligence.\n"
        "SF Bay Area labor is among the most expensive in the country. Use these 2025 benchmarks:\n"
        "  - Kitchen remodel (mid-range): $80k–$150k; full gut/high-end: $150k–$250k+\n"
        "  - Bathroom remodel: $25k–$60k per bath; full gut: $50k–$90k\n"
        "  - Roof replacement: $25k–$60k depending on size and material\n"
        "  - Electrical panel upgrade + rewire: $15k–$40k\n"
        "  - Plumbing repipe (copper/PEX): $15k–$35k\n"
        "  - HVAC (furnace + ducts): $15k–$30k; adding central AC: $10k–$20k additional\n"
        "  - Hardwood floors (refinish): $5k–$12k; replace: $15k–$35k\n"
        "  - Interior paint (full house): $8k–$20k\n"
        "  - Foundation work: $20k–$80k+ depending on scope\n"
        "  - Seismic retrofit (cripple wall): $10k–$25k\n"
        "  - Windows (full replacement): $20k–$60k\n"
        "Assume union or prevailing-wage labor, permit fees, and a 15% contractor margin.\n"
        "Older homes (pre-1980) often require hazmat remediation (lead paint, asbestos): add $5k–$20k.\n\n"
        "Given the property details below, estimate realistic costs to bring this fixer to move-in-ready condition. "
        "Err on the high side — buyers are better served by conservative estimates.\n\n"
        f"Property: {property_data.get('sqft', 'unknown')} sqft, "
        f"built {property_data.get('year_built', 'unknown')}, "
        f"{property_data.get('property_type', 'unknown')}, "
        f"{property_data.get('bedrooms', 'unknown')} bed / {property_data.get('bathrooms', 'unknown')} bath\n"
        f"Fixer signals: {', '.join(fixer_phrases) if fixer_phrases else 'general fixer condition'}\n"
        + (f"Buyer notes: {buyer_context}\n" if buyer_context.strip() else "")
        + "\nReturn JSON only:\n"
        '{"line_items": [{"category": "...", "low": <int>, "high": <int>}], "scope_notes": "..."}\n'
        "Include 4–7 line items covering all likely work. Integers only for costs."
    )

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=600,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return None

    text_parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    payload = _extract_json_object("\n".join(text_parts))
    if not payload:
        return None

    line_items = payload.get("line_items")
    if not isinstance(line_items, list) or not line_items:
        return None

    try:
        total_low = sum(int(item["low"]) for item in line_items)
        total_high = sum(int(item["high"]) for item in line_items)
    except (KeyError, TypeError, ValueError):
        return None

    total_mid = (total_low + total_high) // 2
    all_in_mid = offer_recommended + total_mid
    savings = fair_value - all_in_mid

    if fair_value > 0:
        ratio = savings / fair_value
    else:
        ratio = 0.0

    if ratio > 0.03:
        verdict = "cheaper_fixer"
    elif ratio < -0.03:
        verdict = "cheaper_turnkey"
    else:
        verdict = "comparable"

    condition_adjustment_pct = (
        (offer_result.get("fair_value_breakdown") or {}).get("condition_adjustment_pct") or 0.0
    )

    # Condition signals no longer discount fair_value, so the post-renovation value
    # equals fair_value directly.
    renovated_fair_value = fair_value
    implied_equity_mid = renovated_fair_value - all_in_mid

    return {
        "is_fixer": True,
        "fixer_signals": fixer_signals,
        "offer_recommended": offer_recommended,
        "condition_adjustment_pct": condition_adjustment_pct,
        "renovation_estimate_low": total_low,
        "renovation_estimate_mid": total_mid,
        "renovation_estimate_high": total_high,
        "line_items": line_items,
        "all_in_fixer_low": offer_recommended + total_low,
        "all_in_fixer_mid": all_in_mid,
        "all_in_fixer_high": offer_recommended + total_high,
        "turnkey_value": fair_value,
        "renovated_fair_value": renovated_fair_value,
        "implied_equity_mid": implied_equity_mid,
        "verdict": verdict,
        "savings_mid": savings,
        "scope_notes": payload.get("scope_notes"),
        "disclaimer": (
            "Renovation costs are rough Bay Area estimates based on current labor and material rates. "
            "Get contractor bids before committing."
        ),
        "llm_model": model,
    }
