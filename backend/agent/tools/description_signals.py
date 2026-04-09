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
            r"\bsweat\s+equity\b",
            r"\bhandyman\s+special\b",
            r"\bdiamond\s+in\s+the\s+rough\b",
            # Specific real estate terms — near-unambiguous fixer signals
            r"\bdeferred\s+maintenance\b",
            r"\bconservatorship\s+sale\b",
            r"\bprobate\b",
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

    # Mutually exclusive: if both condition_negative and condition_positive fired,
    # the signals contradict each other — suppress both and exclude their weights.
    has_condition_neg = any(s["category"] == "condition_negative" for s in detected)
    has_condition_pos = any(s["category"] == "condition_positive" for s in detected)
    if has_condition_neg and has_condition_pos:
        suppressed = {"condition_negative", "condition_positive"}
        net_adjustment -= sum(s["weight_pct"] for s in detected if s["category"] in suppressed)
        detected = [s for s in detected if s["category"] not in suppressed]

    net_adjustment = max(-MAX_ABS_ADJUSTMENT_PCT, min(MAX_ABS_ADJUSTMENT_PCT, net_adjustment))

    return {
        "version": RULESET_VERSION,
        "raw_description_present": True,
        "detected_signals": detected,
        "net_adjustment_pct": round(net_adjustment, 2),
    }
