"""
LLM-based renovation cost estimator for fixer properties.
"""

import json
import logging
import os
import re
from typing import Any, Literal

import anthropic

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Cost benchmarks (replaces embedded prompt strings)
# ---------------------------------------------------------------------------

RENOVATION_BENCHMARKS: dict[str, dict] = {
    "kitchen":        {"low": 80_000,  "high": 250_000, "unit": "flat",     "label": "Kitchen remodel"},
    "bathroom":       {"low_per": 25_000, "high_per": 60_000,
                       "low_gut_per": 50_000, "high_gut_per": 90_000,
                       "unit": "per_bath", "label": "Bathroom remodel"},
    "flooring":       {"low_per_sqft": 12, "high_per_sqft": 22, "unit": "per_sqft", "label": "Flooring replacement"},
    "paint":          {"low_per_sqft": 4,  "high_per_sqft": 8,  "unit": "per_sqft", "label": "Interior paint"},
    "roof":           {"low": 25_000,  "high": 60_000,  "unit": "flat",     "label": "Roof replacement"},
    "electrical":     {"low": 15_000,  "high": 40_000,  "unit": "flat",     "label": "Electrical panel + rewire"},
    "plumbing":       {"low": 15_000,  "high": 35_000,  "unit": "flat",     "label": "Plumbing repipe"},
    "hvac":           {"low": 15_000,  "high": 50_000,  "unit": "flat",     "label": "HVAC (furnace + ducts + AC)"},
    "foundation":     {"low": 20_000,  "high": 80_000,  "unit": "flat",     "label": "Foundation work"},
    "seismic":        {"low": 10_000,  "high": 25_000,  "unit": "flat",     "label": "Seismic retrofit"},
    "windows":        {"low": 20_000,  "high": 60_000,  "unit": "flat",     "label": "Windows (full replacement)"},
    "hazmat_encap":   {"low": 2_000,   "high": 5_000,   "unit": "flat",     "label": "Lead paint encapsulation"},
    "hazmat_partial": {"low": 5_000,   "high": 12_000,  "unit": "flat",     "label": "Hazmat partial remediation"},
    "hazmat_full":    {"low": 8_000,   "high": 25_000,  "unit": "flat",     "label": "Hazmat full abatement"},
}

# ---------------------------------------------------------------------------
# Regional labor multipliers (relative to East Bay baseline = 1.0)
# ---------------------------------------------------------------------------

REGIONAL_MULTIPLIERS: dict[str, float] = {
    "san francisco": 1.18,
    "palo alto": 1.13, "menlo park": 1.13, "atherton": 1.13,
    "los altos": 1.12, "cupertino": 1.12,
    "sunnyvale": 1.10, "mountain view": 1.10,
    "santa clara": 1.08, "san jose": 1.05,
    "sausalito": 1.12, "mill valley": 1.12, "san rafael": 1.08,
    "san mateo": 1.08, "redwood city": 1.08, "burlingame": 1.08,
    "foster city": 1.07,
    "berkeley": 1.03, "emeryville": 1.02,
    "oakland": 1.00, "alameda": 1.00, "fremont": 1.00,
    "hayward": 0.98, "napa": 0.97, "petaluma": 0.95, "santa rosa": 0.95,
}

# ---------------------------------------------------------------------------
# Per-item likelihood defaults by scope level
# ---------------------------------------------------------------------------

_SCOPE_DEFAULTS: dict[str, dict[str, str]] = {
    "cosmetic": {
        "kitchen": "possible", "bathroom": "possible",
        "flooring": "likely",  "paint": "likely",
        "roof": "unlikely",    "electrical": "unlikely",
        "plumbing": "unlikely","hvac": "unlikely",
        "foundation": "unlikely", "seismic": "unlikely", "windows": "unlikely",
    },
    "mid": {
        "kitchen": "likely",   "bathroom": "likely",
        "flooring": "likely",  "paint": "likely",
        "roof": "possible",    "electrical": "possible",
        "plumbing": "possible","hvac": "possible",
        "foundation": "unlikely", "seismic": "unlikely", "windows": "possible",
    },
    "full": {
        "kitchen": "likely",   "bathroom": "likely",
        "flooring": "likely",  "paint": "likely",
        "roof": "likely",      "electrical": "likely",
        "plumbing": "likely",  "hvac": "likely",
        "foundation": "possible", "seismic": "possible", "windows": "likely",
    },
}

# Keyword → item slug for buyer-notes overrides
_BUYER_ITEM_KEYWORDS: list[tuple[str, str]] = [
    ("kitchen", "kitchen"),
    ("bath", "bathroom"),
    ("roof", "roof"),
    ("electrical", "electrical"),
    ("plumbing", "plumbing"),
    ("hvac", "hvac"),
    ("foundation", "foundation"),
    ("seismic", "seismic"),
    ("window", "windows"),
    ("flooring", "flooring"),
    ("floor", "flooring"),
    ("paint", "paint"),
]


# ---------------------------------------------------------------------------
# Pure helper functions
# ---------------------------------------------------------------------------

def _classify_era(year_built: int | None) -> tuple[str, list[str]]:
    """Return (era_label, list_of_system_slugs_at_heightened_risk)."""
    if year_built is None:
        return ("unknown", ["electrical", "plumbing", "hvac"])
    if year_built < 1940:
        return ("pre_1940", ["electrical", "plumbing", "foundation", "seismic", "windows"])
    if year_built < 1960:
        return ("1940s_1960s", ["electrical", "plumbing", "hvac", "seismic"])
    if year_built < 1978:
        return ("1960s_1978", ["electrical", "hvac", "seismic"])
    if year_built < 1990:
        return ("1978_1990", ["hvac"])
    if year_built < 2010:
        return ("1990_2010", [])
    return ("post_2010", [])


def _classify_hazmat(
    year_built: int | None,
    scope_level: str,
    fixer_phrases: list[str],
) -> str:
    """Return hazmat tier: 'none' | 'encapsulation' | 'partial' | 'full'."""
    if not year_built or year_built >= 1980:
        return "none"
    combined = " ".join(fixer_phrases).lower()
    hazmat_explicit = any(kw in combined for kw in ("asbestos", "lead paint", "abatement"))
    if hazmat_explicit or scope_level == "full":
        return "full"
    if scope_level == "mid":
        return "partial"
    return "encapsulation"


def _get_regional_multiplier(city: str | None) -> float:
    """Return labor cost multiplier for city. Default 1.0 (East Bay baseline)."""
    if not city:
        return 1.0
    return REGIONAL_MULTIPLIERS.get(city.strip().lower(), 1.0)


def build_scope_profile(
    year_built: int | None,
    fixer_signals: list[str],
    fixer_phrases: list[str],
    sqft: int | None = None,
    buyer_notes: str = "",
) -> dict:
    """
    Determine renovation scope level, per-item likelihoods, and hazmat tier from
    property characteristics, listing signals, and buyer intent.

    Returns a dict with keys:
        scope_level: 'cosmetic' | 'mid' | 'full'
        item_likelihood: dict[slug, 'likely' | 'possible' | 'unlikely']
        hazmat_tier: 'none' | 'encapsulation' | 'partial' | 'full'
        age_era: str
        scope_reasoning: list[str]
    """
    reasoning: list[str] = []
    combined_phrases = " ".join(fixer_phrases).lower()
    buyer_lower = buyer_notes.lower()

    # ---- Step 1: Determine scope level from listing phrases ----
    scope_level: str = "mid"
    good_bones = "good bones" in combined_phrases

    if any(kw in combined_phrases for kw in ("cosmetic fixer", "paint and carpet", "light cosmetic")):
        scope_level = "cosmetic"
        reasoning.append("listing phrase indicates cosmetic scope")
    elif any(kw in combined_phrases for kw in ("deferred maintenance", "gut renovation", "full renovation", "major work")):
        scope_level = "full"
        reasoning.append("listing phrase indicates full scope")
    elif year_built and year_built < 1940 and fixer_signals:
        scope_level = "full"
        reasoning.append(f"pre-1940 home with fixer signals → full scope")
    elif "as-is" in combined_phrases and year_built and year_built < 1960:
        scope_level = "full"
        reasoning.append("as-is pre-1960 home → full scope")
    else:
        reasoning.append("default mid scope")

    # good bones caps scope at mid
    if good_bones and scope_level == "full":
        scope_level = "mid"
        reasoning.append("'good bones' phrase caps scope at mid")

    # ---- Step 2: Buyer notes override scope ----
    if buyer_lower:
        if any(kw in buyer_lower for kw in ("full gut", "gut renovation", "total renovation", "down to the studs")):
            scope_level = "full"
            reasoning.append("buyer notes indicate full gut renovation")
        elif any(kw in buyer_lower for kw in ("cosmetic", "light renovation", "just paint", "won't gut", "diy",
                                               "just planning to paint", "just painting", "painting and carpet",
                                               "paint and carpet", "paint and update", "update carpet")):
            scope_level = "cosmetic"
            reasoning.append("buyer notes indicate cosmetic scope only")

    # ---- Step 3: Build item likelihood from scope defaults ----
    item_likelihood: dict[str, str] = dict(_SCOPE_DEFAULTS[scope_level])

    # Era-based at-risk items: upgrade unlikely → possible
    age_era, at_risk_slugs = _classify_era(year_built)
    for slug in at_risk_slugs:
        if slug in item_likelihood and item_likelihood[slug] == "unlikely":
            item_likelihood[slug] = "possible"
            reasoning.append(f"era {age_era}: {slug} upgraded to possible")

    # Listing phrase signal overrides
    if any(kw in combined_phrases for kw in ("needs new roof", "new roof", "roof repair", "roof replacement")):
        item_likelihood["roof"] = "likely"
        reasoning.append("listing mentions roof → roof=likely")
    if good_bones:
        item_likelihood["foundation"] = "unlikely"
        item_likelihood["seismic"] = "unlikely"
        reasoning.append("'good bones' → foundation/seismic=unlikely")
    if "original kitchen" in combined_phrases:
        item_likelihood["kitchen"] = "likely"
        reasoning.append("listing mentions original kitchen → kitchen=likely")
    if "original" in combined_phrases and year_built and year_built < 1960:
        item_likelihood["electrical"] = "likely"
        item_likelihood["plumbing"] = "likely"
        reasoning.append("'original' phrase + pre-1960 → electrical/plumbing=likely")
    if any(kw in combined_phrases for kw in ("foundation", "settling", "cracked foundation")):
        item_likelihood["foundation"] = "likely"
        reasoning.append("listing mentions foundation → foundation=likely")

    # Buyer notes item overrides
    if buyer_lower:
        for keyword, slug in _BUYER_ITEM_KEYWORDS:
            if slug not in item_likelihood:
                continue
            # "new kitchen", "kitchen is priority", "want to redo kitchen" → likely
            if keyword in buyer_lower and any(
                trigger in buyer_lower for trigger in ("new " + keyword, keyword + " is", "redo", "replace", "priority")
            ):
                item_likelihood[slug] = "likely"
                reasoning.append(f"buyer notes mention {keyword} → {slug}=likely")
            # "not planning to redo kitchen", "skip kitchen" → unlikely
            elif any(neg in buyer_lower for neg in ("not " + keyword, "skip " + keyword, "won't " + keyword)):
                item_likelihood[slug] = "unlikely"
                reasoning.append(f"buyer notes skip {keyword} → {slug}=unlikely")

    # ---- Step 4: Hazmat tier ----
    hazmat_tier = _classify_hazmat(year_built, scope_level, fixer_phrases)

    return {
        "scope_level": scope_level,
        "item_likelihood": item_likelihood,
        "hazmat_tier": hazmat_tier,
        "age_era": age_era,
        "scope_reasoning": reasoning,
    }


def _render_benchmark(slug: str, benchmark: dict, multiplier: float, sqft: int | None, bath_count: int | None) -> str:
    """Return a single prompt line for a benchmark item with multiplier applied."""
    label = benchmark["label"]
    unit = benchmark["unit"]

    if unit == "flat":
        low = round(benchmark["low"] * multiplier / 1000) * 1000
        high = round(benchmark["high"] * multiplier / 1000) * 1000
        return f"  - {label}: ${low:,}–${high:,}"
    elif unit == "per_sqft":
        if sqft:
            low = round(sqft * benchmark["low_per_sqft"] * multiplier / 1000) * 1000
            high = round(sqft * benchmark["high_per_sqft"] * multiplier / 1000) * 1000
            rate_low = round(benchmark["low_per_sqft"] * multiplier)
            rate_high = round(benchmark["high_per_sqft"] * multiplier)
            return f"  - {label} ({sqft} sqft): ${low:,}–${high:,} (at ${rate_low}–${rate_high}/sqft installed)"
        else:
            low = round(15_000 * multiplier / 1000) * 1000
            high = round(35_000 * multiplier / 1000) * 1000
            return f"  - {label}: ${low:,}–${high:,}"
    elif unit == "per_bath":
        if bath_count:
            low = round(benchmark["low_per"] * multiplier / 1000) * 1000
            high = round(benchmark["high_per"] * multiplier / 1000) * 1000
            low_gut = round(benchmark["low_gut_per"] * multiplier / 1000) * 1000
            high_gut = round(benchmark["high_gut_per"] * multiplier / 1000) * 1000
            return (
                f"  - {label}: ${low:,}–${high:,}/bath × {bath_count} = "
                f"${low*bath_count:,}–${high*bath_count:,} total (full gut ${low_gut:,}–${high_gut:,}/bath)"
            )
        else:
            low = round(benchmark["low_per"] * multiplier / 1000) * 1000
            high = round(benchmark["high_per"] * multiplier / 1000) * 1000
            return f"  - {label}: ${low:,}–${high:,}/bath"
    return f"  - {label}"


# ---------------------------------------------------------------------------
# Original helpers
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Main estimation function
# ---------------------------------------------------------------------------

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
    city = property_data.get("city")
    bath_count = int(bathrooms) if bathrooms else None

    # Build scope profile and regional multiplier
    scope_profile = build_scope_profile(
        year_built, fixer_signals, fixer_phrases,
        sqft=sqft, buyer_notes=buyer_context,
    )
    multiplier = _get_regional_multiplier(city)
    scope_level = scope_profile["scope_level"]
    item_likelihood = scope_profile["item_likelihood"]
    hazmat_tier = scope_profile["hazmat_tier"]
    age_era = scope_profile["age_era"]
    scope_reasoning = scope_profile["scope_reasoning"]

    # Build prompt sections: only likely + possible items
    likely_lines: list[str] = []
    possible_lines: list[str] = []
    core_slugs = ["kitchen", "bathroom", "flooring", "paint", "roof",
                  "electrical", "plumbing", "hvac", "foundation", "seismic", "windows"]

    for slug in core_slugs:
        likelihood = item_likelihood.get(slug, "unlikely")
        if likelihood == "unlikely":
            continue
        benchmark = RENOVATION_BENCHMARKS[slug]
        line = _render_benchmark(slug, benchmark, multiplier, sqft, bath_count)
        if likelihood == "likely":
            likely_lines.append(line)
        else:
            possible_lines.append(line)

    # Add hazmat line if applicable
    if hazmat_tier != "none":
        hazmat_slug = f"hazmat_{hazmat_tier}" if hazmat_tier in ("encap", "partial", "full") else f"hazmat_{hazmat_tier}"
        # Map tier names to benchmark keys
        hazmat_key_map = {
            "encapsulation": "hazmat_encap",
            "partial": "hazmat_partial",
            "full": "hazmat_full",
        }
        hkey = hazmat_key_map.get(hazmat_tier)
        if hkey and hkey in RENOVATION_BENCHMARKS:
            hbenchmark = RENOVATION_BENCHMARKS[hkey]
            low = round(hbenchmark["low"] * multiplier / 1000) * 1000
            high = round(hbenchmark["high"] * multiplier / 1000) * 1000
            likely_lines.append(f"  - {hbenchmark['label']}: ${low:,}–${high:,}")

    # Build prompt
    city_label = city or "Bay Area"
    reasoning_str = "; ".join(scope_profile["scope_reasoning"][:3])  # first 3 reasons

    likely_section = "\n".join(likely_lines) if likely_lines else "  (none pre-selected)"
    possible_section = "\n".join(possible_lines) if possible_lines else "  (none)"

    prompt = (
        f"You are an experienced SF Bay Area general contractor estimating renovation costs for a buyer's due diligence.\n"
        f"Regional labor: {city_label} — multiplier {multiplier:.2f}x East Bay baseline; apply to all ranges below.\n"
        f"Renovation scope: {scope_level} (reason: {reasoning_str}).\n"
        f"Property era: {age_era}.\n\n"
        f"LIKELY items (include in estimate):\n{likely_section}\n\n"
        f"POSSIBLE items (include only if signals suggest need):\n{possible_section}\n\n"
        f"Assume union or prevailing-wage labor, permit fees, and a 15% contractor margin.\n"
        f"Err on the high side — buyers are better served by conservative estimates.\n\n"
        f"Property: {sqft or 'unknown'} sqft, "
        f"built {year_built or 'unknown'}, "
        f"{property_data.get('property_type', 'unknown')}, "
        f"{bedrooms or 'unknown'} bed / {bathrooms or 'unknown'} bath\n"
        f"Fixer signals: {', '.join(fixer_phrases) if fixer_phrases else 'general fixer condition'}\n"
        + (f"Buyer notes: {buyer_context}\n" if buyer_context.strip() else "")
        + "\nReturn JSON only (4–7 line items):\n"
        '{"line_items": [{"category": "...", "low": <int>, "high": <int>}], "scope_notes": "..."}\n'
        "Include only items that make sense for this scope. Integers only for costs."
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
        "scope_level": scope_level,
        "hazmat_tier": hazmat_tier,
        "age_era": age_era,
        "regional_multiplier": multiplier,
        "scope_reasoning": scope_reasoning,
        "disclaimer": (
            "Renovation costs are rough Bay Area estimates based on current labor and material rates. "
            "Get contractor bids before committing."
        ),
        "llm_model": model,
    }
