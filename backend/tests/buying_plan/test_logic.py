"""Unit tests for buying_plan.logic — pure functions, no I/O."""

import math
from datetime import date

import pytest
from buying_plan.logic import (
    composite_score,
    composite_score_from_intent,
    derive_plan,
    plan_status,
)


# ---------------------------------------------------------------------------
# composite_score (legacy formula; kept for back-compat with pre-binary rows)
# ---------------------------------------------------------------------------

def test_composite_score_min():
    assert composite_score("terrible", "bad") == pytest.approx(0.0)


def test_composite_score_max():
    assert composite_score("excellent", "good") == pytest.approx(1.0)


def test_composite_score_neutral_neutral():
    assert composite_score("neutral", "neutral") == pytest.approx(0.5)


def test_composite_score_good_bad():
    assert composite_score("good", "bad") == pytest.approx(0.375)


def test_composite_score_bad_good():
    assert composite_score("bad", "good") == pytest.approx(0.625)


def test_composite_score_excellent_neutral():
    assert composite_score("excellent", "neutral") == pytest.approx(0.75)


def test_invalid_quality_raises():
    with pytest.raises(ValueError, match="quality"):
        composite_score("amazing", "good")


def test_invalid_location_raises():
    with pytest.raises(ValueError, match="location"):
        composite_score("good", "excellent")


# ---------------------------------------------------------------------------
# composite_score_from_intent
# ---------------------------------------------------------------------------

def test_composite_score_from_intent_yes_is_one():
    assert composite_score_from_intent("yes") == 1.0


def test_composite_score_from_intent_no_is_zero():
    assert composite_score_from_intent("no") == 0.0


def test_composite_score_from_intent_invalid_raises():
    with pytest.raises(ValueError, match="bidding_intent"):
        composite_score_from_intent("maybe")


# ---------------------------------------------------------------------------
# derive_plan (unchanged behaviour)
# ---------------------------------------------------------------------------

def test_derive_plan_typical():
    """10 weeks away × 3 viewings/week → N=30, threshold=floor(30/e)=11."""
    today = date(2026, 5, 5)
    buy_by = date(2026, 7, 14)
    result = derive_plan(buy_by, 3.0, today=today)
    assert result["total_n"] == 30
    assert result["explore_threshold"] == math.floor(30 / math.e)


def test_derive_plan_minimum_n():
    today = date(2026, 5, 5)
    result = derive_plan(today, 3.0, today=today)
    assert result["total_n"] == 1
    assert result["explore_threshold"] == 1


def test_derive_plan_threshold_at_least_one():
    today = date(2026, 5, 5)
    buy_by = date(2026, 5, 6)
    result = derive_plan(buy_by, 3.0, today=today)
    assert result["explore_threshold"] >= 1


def test_derive_plan_large_n():
    today = date(2026, 5, 5)
    buy_by = date(2027, 5, 5)
    result = derive_plan(buy_by, 2.0, today=today)
    expected_n = round(52.142857 * 2.0)
    expected_threshold = max(1, math.floor(expected_n / math.e))
    assert result["total_n"] == expected_n
    assert result["explore_threshold"] == expected_threshold


# ---------------------------------------------------------------------------
# plan_status — binary bidding_intent
# ---------------------------------------------------------------------------

def _make_seen(intent: str | None = "yes", *, legacy_score: float | None = None) -> dict:
    """Build a seen-property dict for plan_status tests.

    If `legacy_score` is provided, the row simulates a pre-feature record
    (intent=None, only composite_score is set).
    """
    if legacy_score is not None:
        return {"bidding_intent": None, "composite_score": legacy_score}
    return {
        "bidding_intent": intent,
        "composite_score": 1.0 if intent == "yes" else 0.0,
    }


def test_plan_status_empty():
    result = plan_status(explore_threshold=11, seen_properties=[])
    assert result["phase"] == "explore"
    assert result["seen_count"] == 0
    assert result["explore_max_score"] is None
    assert result["properties_past_threshold"] == 0
    assert result["bid_premium_pct"] == pytest.approx(0.0)


def test_plan_status_explore_phase_partial_with_yes():
    """In explore phase with at least one Yes → explore_max_score = 1.0."""
    props = [_make_seen("no"), _make_seen("yes"), _make_seen("no")]
    result = plan_status(explore_threshold=11, seen_properties=props)
    assert result["phase"] == "explore"
    assert result["seen_count"] == 3
    assert result["explore_max_score"] == pytest.approx(1.0)
    assert result["properties_past_threshold"] == 0


def test_plan_status_explore_phase_all_no():
    """In explore phase with all No → explore_max_score = 0.0."""
    props = [_make_seen("no"), _make_seen("no")]
    result = plan_status(explore_threshold=11, seen_properties=props)
    assert result["phase"] == "explore"
    assert result["explore_max_score"] == pytest.approx(0.0)


def test_plan_status_transitions_to_commit_at_threshold():
    threshold = 3
    props = [_make_seen("no"), _make_seen("yes"), _make_seen("no")]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["seen_count"] == 3
    assert result["explore_max_score"] == pytest.approx(1.0)
    assert result["properties_past_threshold"] == 0


def test_plan_status_commit_qualifies_only_when_yes():
    """In commit phase, only Yes properties contribute to bid premium."""
    threshold = 3
    # explore: [no, yes, no] → explore_max=1.0
    # commit: [yes, no, yes] → 2 Yes
    props = [_make_seen("no"), _make_seen("yes"), _make_seen("no"),
             _make_seen("yes"), _make_seen("no"), _make_seen("yes")]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["properties_past_threshold"] == 2
    assert result["bid_premium_pct"] == pytest.approx(0.02)


def test_plan_status_commit_all_no_zero_premium():
    threshold = 2
    props = [_make_seen("yes"), _make_seen("yes"),
             _make_seen("no"), _make_seen("no"), _make_seen("no")]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["properties_past_threshold"] == 0
    assert result["bid_premium_pct"] == pytest.approx(0.0)


def test_plan_status_explore_no_yes_commit_yes_still_counts():
    """If explore had no Yes, commit-phase Yes properties still count as 'missed'."""
    threshold = 2
    props = [_make_seen("no"), _make_seen("no"),
             _make_seen("yes"), _make_seen("yes"), _make_seen("yes")]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["explore_max_score"] == pytest.approx(0.0)
    assert result["properties_past_threshold"] == 3
    assert result["bid_premium_pct"] == pytest.approx(0.03)


def test_plan_status_explore_max_locked_after_threshold():
    """Once in commit phase, explore_max_score is fixed by the first explore_threshold rows."""
    threshold = 2
    # First 2 (explore): [no, no] → max=0.0
    # Next 2 (commit): [yes, yes] do NOT change explore_max_score
    props = [_make_seen("no"), _make_seen("no"),
             _make_seen("yes"), _make_seen("yes")]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["explore_max_score"] == pytest.approx(0.0)


def test_plan_status_bid_premium_one_pct_per_yes():
    threshold = 2
    props = [_make_seen("yes"), _make_seen("yes")] + [_make_seen("yes")] * 5
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["properties_past_threshold"] == 5
    assert result["bid_premium_pct"] == pytest.approx(0.05)


# ---------------------------------------------------------------------------
# Legacy fallback: bidding_intent=None → composite_score >= 0.5 → would_bid
# ---------------------------------------------------------------------------

def test_plan_status_legacy_high_score_treated_as_yes():
    threshold = 2
    # explore: legacy [0.4, 0.9] → would_bid [F, T] → max=1.0
    # commit: legacy [0.6, 0.3] → [T, F] → 1 qualifying
    props = [
        _make_seen(None, legacy_score=0.4),
        _make_seen(None, legacy_score=0.9),
        _make_seen(None, legacy_score=0.6),
        _make_seen(None, legacy_score=0.3),
    ]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["explore_max_score"] == pytest.approx(1.0)
    assert result["properties_past_threshold"] == 1


def test_plan_status_legacy_low_score_treated_as_no():
    threshold = 2
    props = [
        _make_seen(None, legacy_score=0.4),
        _make_seen(None, legacy_score=0.3),
    ]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["explore_max_score"] == pytest.approx(0.0)


def test_plan_status_legacy_threshold_boundary_inclusive():
    """composite_score == 0.5 (the legacy threshold) is treated as Yes."""
    threshold = 1
    props = [_make_seen(None, legacy_score=0.5)]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["explore_max_score"] == pytest.approx(1.0)


def test_plan_status_mixed_legacy_and_intent_rows():
    """A mix of new (intent set) and legacy (intent None) rows works correctly."""
    threshold = 2
    # explore: [legacy 0.7 → T, intent no → F] → max=1.0
    # commit:  [intent yes, legacy 0.4 → F, intent yes] → 2 Yes
    props = [
        _make_seen(None, legacy_score=0.7),
        _make_seen("no"),
        _make_seen("yes"),
        _make_seen(None, legacy_score=0.4),
        _make_seen("yes"),
    ]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["properties_past_threshold"] == 2


def test_plan_status_row_missing_intent_and_score_treated_as_no():
    """Defensive: row with neither intent nor score → would_bid is False."""
    props = [{"bidding_intent": None}]
    result = plan_status(explore_threshold=1, seen_properties=props)
    assert result["explore_max_score"] == pytest.approx(0.0)
