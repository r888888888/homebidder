"""Pure logic for the buying plan / mark-seen feature. No I/O."""

import math
from datetime import date

QUALITY_SCALE: dict[str, float] = {
    "terrible": 0.0,
    "bad": 0.25,
    "neutral": 0.5,
    "good": 0.75,
    "excellent": 1.0,
}

LOCATION_SCALE: dict[str, float] = {
    "bad": 0.0,
    "neutral": 0.5,
    "good": 1.0,
}

BIDDING_INTENT_VALUES: set[str] = {"yes", "no"}

# Pre-bidding-intent rows are graded against this composite_score threshold so
# their would_bid signal stays sensible after the binary migration.
LEGACY_INTENT_THRESHOLD: float = 0.5


def composite_score(quality: str, location: str) -> float:
    """Legacy quality+location → 0–1 composite. Retained for back-compat with
    rows written before bidding_intent existed; new rows use
    ``composite_score_from_intent`` instead.
    """
    if quality not in QUALITY_SCALE:
        raise ValueError(f"Invalid quality: {quality!r}. Must be one of {list(QUALITY_SCALE)}")
    if location not in LOCATION_SCALE:
        raise ValueError(f"Invalid location: {location!r}. Must be one of {list(LOCATION_SCALE)}")
    return (QUALITY_SCALE[quality] + LOCATION_SCALE[location]) / 2


def composite_score_from_intent(intent: str) -> float:
    """Map a binary bidding intent to a 0/1 composite score."""
    if intent not in BIDDING_INTENT_VALUES:
        raise ValueError(
            f"Invalid bidding_intent: {intent!r}. "
            f"Must be one of {sorted(BIDDING_INTENT_VALUES)}"
        )
    return 1.0 if intent == "yes" else 0.0


def _would_bid(sp: dict) -> bool:
    """Reduce a seen-property row to a binary 'would actually bid' signal.

    For new rows (intent set), use it directly. For legacy rows (intent=None),
    fall back to ``composite_score >= LEGACY_INTENT_THRESHOLD`` so pre-feature
    data still drives the algorithm sensibly.
    """
    intent = sp.get("bidding_intent")
    if intent is not None:
        return intent == "yes"
    return sp.get("composite_score", 0.0) >= LEGACY_INTENT_THRESHOLD


def derive_plan(buy_by_date: date, viewings_per_week: float, today: date | None = None) -> dict:
    """Compute total_n and explore_threshold from a buy-by date and viewing rate.

    Uses the secretary-problem optimal stopping rule: explore the first floor(N/e)
    candidates, then commit to the next one that beats the explore-phase maximum.

    Args:
        buy_by_date: The date by which the user expects to have purchased.
        viewings_per_week: Estimated number of property viewings per week.
        today: Reference date (defaults to date.today()).

    Returns:
        dict with keys:
            total_n (int): Fixed total expected viewings.
            explore_threshold (int): Number of properties to explore before committing.
    """
    if today is None:
        today = date.today()
    days_remaining = max(0, (buy_by_date - today).days)
    weeks_remaining = days_remaining / 7
    total_n = max(1, round(weeks_remaining * viewings_per_week))
    explore_threshold = max(1, math.floor(total_n / math.e))
    return {"total_n": total_n, "explore_threshold": explore_threshold}


def plan_status(explore_threshold: int, seen_properties: list[dict]) -> dict:
    """Compute the current buying-plan status from seen properties.

    ``seen_properties`` is in chronological order (oldest first). Each row
    contributes a binary ``would_bid`` signal: from ``bidding_intent``
    ("yes"/"no") if present, else from a legacy ``composite_score >= 0.5``
    fallback for pre-feature rows.

    Returns:
        dict with keys:
            phase: "explore" or "commit".
            seen_count: total seen rows.
            explore_max_score: 1.0 if any explore-phase row was a Yes, else 0.0;
                None when no rows have been seen yet. (Float for API back-compat.)
            properties_past_threshold: count of commit-phase Yes rows. Each one
                represents a Yes property the buyer passed over and contributes
                1% to the bid premium for the next decision.
            bid_premium_pct: 0.01 × properties_past_threshold.
    """
    seen_count = len(seen_properties)
    phase = "commit" if seen_count >= explore_threshold else "explore"

    if seen_count == 0:
        explore_max_score: float | None = None
    else:
        # In commit phase the explore window is locked to the first explore_threshold
        # rows; in explore phase it's the running set of all seen rows.
        explore_window = (
            seen_properties[:explore_threshold] if phase == "commit" else seen_properties
        )
        any_explore_yes = any(_would_bid(sp) for sp in explore_window)
        explore_max_score = 1.0 if any_explore_yes else 0.0

    if phase == "commit":
        commit_props = seen_properties[explore_threshold:]
        # Each commit-phase Yes is a property the buyer would have bid on but
        # passed on → 1% bid premium per occurrence.
        properties_past_threshold = sum(1 for sp in commit_props if _would_bid(sp))
    else:
        properties_past_threshold = 0

    bid_premium_pct = round(0.01 * properties_past_threshold, 4)

    return {
        "phase": phase,
        "seen_count": seen_count,
        "explore_max_score": explore_max_score,
        "properties_past_threshold": properties_past_threshold,
        "bid_premium_pct": bid_premium_pct,
    }
