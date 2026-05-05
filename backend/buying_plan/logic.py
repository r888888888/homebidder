"""Pure logic for the buying plan / mark-seen feature. No I/O."""

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
