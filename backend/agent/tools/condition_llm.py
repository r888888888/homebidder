"""
Optional LLM-based condition signal evaluator for listing descriptions.
"""

import json
import os
import re
from typing import Any

import anthropic


MIN_CONFIDENCE = 0.60
MAX_ABS_ADJUSTMENT_PCT = 3.0
LLM_CONTRIBUTION_CAP_PCT = 1.0
DEFAULT_MODEL = "claude-4-6-haiku-latest"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(value, high))


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


def _normalize_llm_signals(raw_signals: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_signals, list):
        return []

    out: list[dict[str, Any]] = []
    for signal in raw_signals:
        if not isinstance(signal, dict):
            continue
        label = str(signal.get("label", "")).strip()
        if not label:
            continue
        category = str(signal.get("category", "")).strip() or "condition_negative"
        direction = str(signal.get("direction", "")).strip() or "negative"
        try:
            weight_pct = float(signal.get("weight_pct", 0.0))
        except (TypeError, ValueError):
            weight_pct = 0.0
        weight_pct = _clamp(weight_pct, -2.0, 2.0)

        phrases = signal.get("matched_phrases")
        if not isinstance(phrases, list):
            phrases = []
        matched_phrases = [str(p) for p in phrases if str(p).strip()]

        out.append(
            {
                "label": label,
                "category": category,
                "direction": direction,
                "weight_pct": round(weight_pct, 2),
                "matched_phrases": matched_phrases,
            }
        )
    return out


async def evaluate_condition_with_llm(description_text: str | None) -> dict[str, Any] | None:
    if not (description_text or "").strip():
        return None

    if os.getenv("ENABLE_DESCRIPTION_LLM", "").strip() != "1":
        return None

    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        return None

    model = os.getenv("DESCRIPTION_LLM_MODEL", DEFAULT_MODEL)
    client = anthropic.AsyncAnthropic(api_key=api_key)

    prompt = (
        "You are classifying real-estate listing description condition signals.\n"
        "Return JSON only with fields: confidence (0-1), signals (array).\n"
        "Each signal item: label, category, direction, weight_pct, matched_phrases.\n"
        "Allowed categories: condition_positive, condition_negative, occupancy_negative.\n"
        "Allowed direction: positive or negative.\n"
        "Keep each weight_pct in [-2.0, 2.0].\n"
        f"Description:\n{description_text}"
    )

    try:
        resp = await client.messages.create(
            model=model,
            max_tokens=300,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception:
        return None

    text_parts: list[str] = []
    for block in resp.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(getattr(block, "text", ""))
    payload = _extract_json_object("\n".join(text_parts))
    if not payload:
        return None

    try:
        confidence = float(payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    confidence = _clamp(confidence, 0.0, 1.0)
    if confidence < MIN_CONFIDENCE:
        return None

    detected_signals = _normalize_llm_signals(payload.get("signals", []))
    net = sum(float(s.get("weight_pct", 0.0)) for s in detected_signals)
    net = _clamp(net, -MAX_ABS_ADJUSTMENT_PCT, MAX_ABS_ADJUSTMENT_PCT)

    return {
        "source": "llm",
        "model": model,
        "confidence": round(confidence, 3),
        "detected_signals": detected_signals,
        "net_adjustment_pct": round(net, 2),
    }


def merge_signal_results(
    rule_result: dict[str, Any],
    llm_result: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(rule_result)
    base_signals = list(rule_result.get("detected_signals") or [])
    base_net = float(rule_result.get("net_adjustment_pct") or 0.0)

    if not llm_result:
        merged["llm"] = {"used": False, "confidence": None, "model": None, "adjustment_pct": 0.0}
        merged["detected_signals"] = base_signals
        merged["net_adjustment_pct"] = round(_clamp(base_net, -MAX_ABS_ADJUSTMENT_PCT, MAX_ABS_ADJUSTMENT_PCT), 2)
        return merged

    _CONDITION_CATEGORIES = {"condition_negative", "condition_positive"}

    llm_confidence = float(llm_result.get("confidence") or 0.0)
    # Condition (fixer/renovated) signals are surfaced for display only — rule-based signals
    # are the authoritative source for condition pricing. Only non-condition LLM signals
    # (e.g. occupancy_negative) may contribute to the price adjustment.
    llm_pricing_signals = [
        s for s in (llm_result.get("detected_signals") or [])
        if s.get("category") not in _CONDITION_CATEGORIES
    ]
    llm_net_raw = sum(float(s.get("weight_pct") or 0.0) for s in llm_pricing_signals)
    llm_adjustment = _clamp(llm_net_raw, -LLM_CONTRIBUTION_CAP_PCT, LLM_CONTRIBUTION_CAP_PCT)

    combined_net = _clamp(base_net + llm_adjustment, -MAX_ABS_ADJUSTMENT_PCT, MAX_ABS_ADJUSTMENT_PCT)

    seen_labels = {str(s.get("label", "")).strip().lower() for s in base_signals}
    for signal in llm_result.get("detected_signals") or []:
        label = str(signal.get("label", "")).strip().lower()
        if not label or label in seen_labels:
            continue
        base_signals.append(signal)
        seen_labels.add(label)

    merged["detected_signals"] = base_signals
    merged["net_adjustment_pct"] = round(combined_net, 2)
    merged["llm"] = {
        "used": True,
        "confidence": round(llm_confidence, 3),
        "model": llm_result.get("model"),
        "adjustment_pct": round(llm_adjustment, 2),
    }
    return merged
