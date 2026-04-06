"""
LLM-based renovation cost estimator for fixer properties.
"""

import json
import logging
import os
import re
from typing import Any

import anthropic

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
log = logging.getLogger(__name__)


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
        log.warning("estimate_renovation_cost: ANTHROPIC_API_KEY not set — skipping")
        return None

    fair_value = offer_result.get("fair_value_estimate")
    if fair_value is None:
        log.warning("estimate_renovation_cost: fair_value_estimate is None — skipping")
        return None

    offer_recommended = offer_result.get("offer_recommended") or 0
    if not offer_recommended:
        log.warning("estimate_renovation_cost: offer_recommended is %s — skipping", offer_recommended)
        return None

    signals = (property_data.get("description_signals") or {}).get("detected_signals") or []
    fixer_signals = [s["label"] for s in signals if s.get("category") == "condition_negative"]
    fixer_phrases = []
    for s in signals:
        if s.get("category") == "condition_negative":
            fixer_phrases.extend(s.get("matched_phrases") or [])

    model = os.getenv("RENOVATION_LLM_MODEL", DEFAULT_MODEL)
    client = anthropic.AsyncAnthropic(api_key=api_key)

    sqft = property_data.get("sqft")
    bedrooms = property_data.get("bedrooms")
    bathrooms = property_data.get("bathrooms")
    year_built = property_data.get("year_built")

    # Pre-compute scaled anchors to feed into the prompt
    flooring_low  = round(sqft * 12 / 1000) * 1000 if sqft else None
    flooring_high = round(sqft * 22 / 1000) * 1000 if sqft else None
    paint_low     = round(sqft * 4  / 1000) * 1000 if sqft else None
    paint_high    = round(sqft * 8  / 1000) * 1000 if sqft else None
    bath_count    = int(bathrooms) if bathrooms else None

    flooring_note = (
        f"  - Flooring (replace, {sqft} sqft): ${flooring_low:,}–${flooring_high:,} "
        f"(at $12–$22/sqft installed)\n"
        if flooring_low else "  - Flooring (replace): $15k–$35k\n"
    )
    paint_note = (
        f"  - Interior paint ({sqft} sqft): ${paint_low:,}–${paint_high:,} "
        f"(at $4–$8/sqft)\n"
        if paint_low else "  - Interior paint: $8k–$20k\n"
    )
    bath_note = (
        f"  - Bathroom remodel: $25k–$60k per bath × {bath_count} "
        f"= ${bath_count*25:,}k–${bath_count*60:,}k total (full gut $50k–$90k each)\n"
        if bath_count else "  - Bathroom remodel: $25k–$60k per bath; full gut: $50k–$90k\n"
    )
    hazmat_note = (
        "  - Hazmat remediation (lead paint, asbestos likely in pre-1980 home): $8k–$25k\n"
        if year_built and year_built < 1980 else ""
    )

    prompt = (
        "You are an experienced SF Bay Area general contractor estimating renovation costs for a buyer's due diligence.\n"
        "SF Bay Area labor is among the most expensive in the country. Use these 2025 benchmarks "
        "scaled to the specific property:\n"
        "  - Kitchen remodel (mid-range): $80k–$150k; full gut/high-end: $150k–$250k+\n"
        + bath_note
        + flooring_note
        + paint_note
        + "  - Roof replacement: $25k–$60k depending on size and material\n"
        "  - Electrical panel upgrade + rewire: $15k–$40k\n"
        "  - Plumbing repipe (copper/PEX): $15k–$35k\n"
        "  - HVAC (furnace + ducts): $15k–$30k; adding central AC: $10k–$20k additional\n"
        "  - Foundation work: $20k–$80k+ depending on scope\n"
        "  - Seismic retrofit (cripple wall): $10k–$25k\n"
        "  - Windows (full replacement): $20k–$60k\n"
        + hazmat_note
        + "Assume union or prevailing-wage labor, permit fees, and a 15% contractor margin.\n"
        "Err on the high side — buyers are better served by conservative estimates.\n\n"
        "Given the property details below, produce a line-item estimate to bring this fixer to "
        "move-in-ready condition. Scale each item to the actual sqft and room count.\n\n"
        f"Property: {sqft or 'unknown'} sqft, "
        f"built {year_built or 'unknown'}, "
        f"{property_data.get('property_type', 'unknown')}, "
        f"{bedrooms or 'unknown'} bed / {bathrooms or 'unknown'} bath\n"
        f"Fixer signals: {', '.join(fixer_phrases) if fixer_phrases else 'general fixer condition'}\n"
        + (f"Buyer notes: {buyer_context}\n" if buyer_context.strip() else "")
        + "\nReturn JSON only:\n"
        '{"line_items": [{"category": "...", "low": <int>, "high": <int>}], "scope_notes": "..."}\n'
        "Include 4–7 line items covering all likely work. Integers only for costs."
    )

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=1200,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as exc:
        log.warning("estimate_renovation_cost: LLM call failed: %s", exc)
        return None

    text_parts = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    payload = _extract_json_object("\n".join(text_parts))
    if not payload:
        log.warning("estimate_renovation_cost: could not parse LLM JSON response")
        return None

    line_items = payload.get("line_items")
    if not isinstance(line_items, list) or not line_items:
        log.warning("estimate_renovation_cost: line_items missing or empty in LLM response")
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

    # Condition signals do not discount fair_value, so the post-renovation value
    # equals fair_value directly.
    renovated_fair_value = fair_value
    implied_equity_mid = renovated_fair_value - all_in_mid

    return {
        "is_fixer": True,
        "fixer_signals": fixer_signals,
        "offer_recommended": offer_recommended,
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
