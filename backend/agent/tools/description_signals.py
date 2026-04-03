"""
Deterministic listing description signal extraction for valuation adjustments.
"""

import re
from typing import TypedDict


MAX_ABS_ADJUSTMENT_PCT = 3.0
RULESET_VERSION = "v1"


class DescriptionSignal(TypedDict):
    label: str
    category: str
    direction: str
    weight_pct: float
    matched_phrases: list[str]


class DescriptionSignalResult(TypedDict):
    version: str
    raw_description_present: bool
    detected_signals: list[DescriptionSignal]
    net_adjustment_pct: float


class _SignalRule(TypedDict):
    label: str
    category: str
    direction: str
    weight_pct: float
    phrases: list[str]


SIGNAL_RULES: list[_SignalRule] = [
    {
        "label": "Fixer / Contractor Special",
        "category": "condition_negative",
        "direction": "negative",
        "weight_pct": -2.0,
        "phrases": [
            r"\bfixer(?:[-\s]?upper)?\b",
            r"\bcontractor\s+special\b",
            r"\bneeds?\s+tlc\b",
            r"\bas[-\s]?is\b",
            r"\bbring\s+your\s+contractor\b",
            r"\bcosmetic\s+fixer\b",
        ],
    },
    {
        "label": "Renovated / Updated",
        "category": "condition_positive",
        "direction": "positive",
        "weight_pct": 1.5,
        "phrases": [
            r"\brenovat(?:ed|ion|e)\b",
            r"\bremodel(?:ed|ing)?\b",
            r"\bupdated?\b",
            r"\bnew\s+appliances?\b",
            r"\bmove[-\s]?in\s+ready\b",
            r"\bturn[-\s]?key\b",
        ],
    },
    {
        "label": "Tenant Occupied",
        "category": "occupancy_negative",
        "direction": "negative",
        "weight_pct": -1.5,
        "phrases": [
            r"\btenant[-\s]?occupied\b",
            r"\btenant\s+in\s+place\b",
            r"\bsubject\s+to\s+tenant\s+rights\b",
            r"\boccupied\s+by\s+tenant(?:s)?\b",
        ],
    },
]


def extract_description_signals(description_text: str | None) -> DescriptionSignalResult:
    text = (description_text or "").strip()
    if not text:
        return {
            "version": RULESET_VERSION,
            "raw_description_present": False,
            "detected_signals": [],
            "net_adjustment_pct": 0.0,
        }

    lowered = text.lower()
    detected: list[DescriptionSignal] = []
    net_adjustment = 0.0

    for rule in SIGNAL_RULES:
        matched_phrases: list[str] = []
        for pattern in rule["phrases"]:
            if re.search(pattern, lowered, flags=re.IGNORECASE):
                matched_phrases.append(pattern)

        if not matched_phrases:
            continue

        detected.append(
            {
                "label": rule["label"],
                "category": rule["category"],
                "direction": rule["direction"],
                "weight_pct": rule["weight_pct"],
                "matched_phrases": matched_phrases,
            }
        )
        net_adjustment += rule["weight_pct"]

    net_adjustment = max(-MAX_ABS_ADJUSTMENT_PCT, min(MAX_ABS_ADJUSTMENT_PCT, net_adjustment))

    return {
        "version": RULESET_VERSION,
        "raw_description_present": True,
        "detected_signals": detected,
        "net_adjustment_pct": round(net_adjustment, 2),
    }
