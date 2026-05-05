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


def composite_score(quality: str, location: str) -> float:
    """Return a normalized 0–1 composite score from quality and location ratings.

    Quality covers internal property factors (roof, foundation, fixtures, etc.).
    Location covers external factors (walkability, transit, noise, hills, etc.).
    """
    if quality not in QUALITY_SCALE:
        raise ValueError(f"Invalid quality: {quality!r}. Must be one of {list(QUALITY_SCALE)}")
    if location not in LOCATION_SCALE:
        raise ValueError(f"Invalid location: {location!r}. Must be one of {list(LOCATION_SCALE)}")
    return (QUALITY_SCALE[quality] + LOCATION_SCALE[location]) / 2


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
    """Compute the current buying-plan status from the explore threshold and seen properties.

    seen_properties must be in chronological order (oldest first). Each item must
    have a ``composite_score`` key (float 0–1).

    Returns:
        dict with keys:
            phase (str): "explore" or "commit".
            seen_count (int): Total number of seen properties.
            explore_max_score (float | None): Best score from the explore phase,
                or None when no properties have been seen yet.
            properties_past_threshold (int): Number of properties seen after the
                explore threshold was reached.
            bid_premium_pct (float): Calibration premium to add to the fair-value
                bid (1% per property past the threshold).
    """
    seen_count = len(seen_properties)
    phase = "commit" if seen_count >= explore_threshold else "explore"

    if seen_count == 0:
        explore_max_score = None
    elif phase == "commit":
        # Explore max is locked to the first explore_threshold properties.
        explore_scores = [sp["composite_score"] for sp in seen_properties[:explore_threshold]]
        explore_max_score = max(explore_scores) if explore_scores else 0.0
    else:
        # Still in explore phase — running max over what's been seen so far.
        explore_max_score = max(sp["composite_score"] for sp in seen_properties)

    properties_past_threshold = max(0, seen_count - explore_threshold)
    bid_premium_pct = round(0.01 * properties_past_threshold, 4)

    return {
        "phase": phase,
        "seen_count": seen_count,
        "explore_max_score": explore_max_score,
        "properties_past_threshold": properties_past_threshold,
        "bid_premium_pct": bid_premium_pct,
    }
