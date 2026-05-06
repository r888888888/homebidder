"""Unit tests for buying_plan.logic — pure functions, no I/O."""

import math
from datetime import date

import pytest
from buying_plan.logic import composite_score, derive_plan, plan_status


def test_composite_score_min():
    """terrible quality + bad location = 0.0"""
    assert composite_score("terrible", "bad") == pytest.approx(0.0)


def test_composite_score_max():
    """excellent quality + good location = 1.0"""
    assert composite_score("excellent", "good") == pytest.approx(1.0)


def test_composite_score_neutral_neutral():
    """neutral + neutral = 0.5"""
    assert composite_score("neutral", "neutral") == pytest.approx(0.5)


def test_composite_score_good_bad():
    """good (0.75) + bad (0.0) → (0.75 + 0.0) / 2 = 0.375"""
    assert composite_score("good", "bad") == pytest.approx(0.375)


def test_composite_score_bad_good():
    """bad (0.25) + good (1.0) → (0.25 + 1.0) / 2 = 0.625"""
    assert composite_score("bad", "good") == pytest.approx(0.625)


def test_composite_score_excellent_neutral():
    """excellent (1.0) + neutral (0.5) → 0.75"""
    assert composite_score("excellent", "neutral") == pytest.approx(0.75)


def test_invalid_quality_raises():
    with pytest.raises(ValueError, match="quality"):
        composite_score("amazing", "good")


def test_invalid_location_raises():
    with pytest.raises(ValueError, match="location"):
        composite_score("good", "excellent")


# ---------------------------------------------------------------------------
# derive_plan
# ---------------------------------------------------------------------------

def test_derive_plan_typical():
    """10 weeks away × 3 viewings/week → N=30, threshold=floor(30/e)=11."""
    today = date(2026, 5, 5)
    buy_by = date(2026, 7, 14)  # 70 days = 10 weeks
    result = derive_plan(buy_by, 3.0, today=today)
    assert result["total_n"] == 30
    assert result["explore_threshold"] == math.floor(30 / math.e)


def test_derive_plan_minimum_n():
    """A buy-by date in the past or today results in total_n=1, threshold=1."""
    today = date(2026, 5, 5)
    result = derive_plan(today, 3.0, today=today)
    assert result["total_n"] == 1
    assert result["explore_threshold"] == 1


def test_derive_plan_threshold_at_least_one():
    """Even with total_n=1, explore_threshold is at least 1."""
    today = date(2026, 5, 5)
    buy_by = date(2026, 5, 6)  # 1 day away → 0.14 weeks × 3 = 0.43 → total_n=1
    result = derive_plan(buy_by, 3.0, today=today)
    assert result["explore_threshold"] >= 1


def test_derive_plan_large_n():
    """52 weeks × 2/week → N=104, threshold=floor(104/e)=38."""
    today = date(2026, 5, 5)
    buy_by = date(2027, 5, 5)  # ~365 days = ~52.1 weeks
    result = derive_plan(buy_by, 2.0, today=today)
    expected_n = round(52.142857 * 2.0)
    expected_threshold = max(1, math.floor(expected_n / math.e))
    assert result["total_n"] == expected_n
    assert result["explore_threshold"] == expected_threshold


# ---------------------------------------------------------------------------
# plan_status
# ---------------------------------------------------------------------------

def _make_seen(composite: float) -> dict:
    return {"composite_score": composite}


def test_plan_status_empty():
    """No seen properties → explore phase, no explore_max_score."""
    result = plan_status(explore_threshold=11, seen_properties=[])
    assert result["phase"] == "explore"
    assert result["seen_count"] == 0
    assert result["explore_max_score"] is None
    assert result["properties_past_threshold"] == 0
    assert result["bid_premium_pct"] == pytest.approx(0.0)


def test_plan_status_explore_phase_partial():
    """Fewer seen than threshold → still in explore phase."""
    props = [_make_seen(0.5), _make_seen(0.8), _make_seen(0.3)]
    result = plan_status(explore_threshold=11, seen_properties=props)
    assert result["phase"] == "explore"
    assert result["seen_count"] == 3
    assert result["explore_max_score"] == pytest.approx(0.8)
    assert result["properties_past_threshold"] == 0
    assert result["bid_premium_pct"] == pytest.approx(0.0)


def test_plan_status_transitions_to_commit_at_threshold():
    """Exactly explore_threshold seen → commit phase begins."""
    threshold = 3
    props = [_make_seen(0.4), _make_seen(0.9), _make_seen(0.6)]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["seen_count"] == 3
    assert result["explore_max_score"] == pytest.approx(0.9)
    assert result["properties_past_threshold"] == 0
    assert result["bid_premium_pct"] == pytest.approx(0.0)


def test_plan_status_commit_phase_with_extra():
    """2 qualifying commit-phase properties (>= explore max) → bid premium 2%."""
    threshold = 3
    # explore: [0.4, 0.9, 0.6] → max = 0.9
    # commit: [0.9, 0.95] → both >= 0.9 → 2 qualifying
    props = [_make_seen(0.4), _make_seen(0.9), _make_seen(0.6),
             _make_seen(0.9), _make_seen(0.95)]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["seen_count"] == 5
    assert result["explore_max_score"] == pytest.approx(0.9)  # max of first 3
    assert result["properties_past_threshold"] == 2
    assert result["bid_premium_pct"] == pytest.approx(0.02)


def test_plan_status_explore_max_locked_after_threshold():
    """explore_max_score is determined only by the first explore_threshold properties."""
    threshold = 2
    # First 2 (explore): 0.3, 0.5 → max=0.5
    # Next 2 (commit): 0.9, 1.0 → should NOT affect explore_max_score
    props = [_make_seen(0.3), _make_seen(0.5), _make_seen(0.9), _make_seen(1.0)]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["explore_max_score"] == pytest.approx(0.5)


def test_plan_status_bid_premium_one_pct_per_extra():
    """5 properties past threshold, all with score equal to explore max → bid premium 5%."""
    threshold = 2
    props = [_make_seen(0.5)] * (threshold + 5)
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["properties_past_threshold"] == 5
    assert result["bid_premium_pct"] == pytest.approx(0.05)


def test_plan_status_commit_below_explore_max_not_counted():
    """Commit-phase properties below explore max do not increment the premium counter."""
    threshold = 3
    # explore: [0.4, 0.9, 0.6] → max = 0.9
    # commit: [0.5, 0.7] → both < 0.9, neither qualifies
    props = [_make_seen(0.4), _make_seen(0.9), _make_seen(0.6),
             _make_seen(0.5), _make_seen(0.7)]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["properties_past_threshold"] == 0
    assert result["bid_premium_pct"] == pytest.approx(0.0)


def test_plan_status_commit_equal_to_explore_max_counts():
    """A commit-phase property that exactly equals the explore max counts toward the premium."""
    threshold = 2
    # explore: [0.5, 0.75] → max = 0.75
    # commit: [0.75] → equals max → counts
    props = [_make_seen(0.5), _make_seen(0.75), _make_seen(0.75)]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["phase"] == "commit"
    assert result["properties_past_threshold"] == 1
    assert result["bid_premium_pct"] == pytest.approx(0.01)


def test_plan_status_commit_mixed_qualifying():
    """Only qualifying commit-phase properties (>= explore max) count."""
    threshold = 2
    # explore: [0.5, 0.75] → max = 0.75
    # commit: [0.4, 0.75, 0.3, 0.9] → qualifying: 0.75, 0.9 → 2
    props = [_make_seen(0.5), _make_seen(0.75),
             _make_seen(0.4), _make_seen(0.75), _make_seen(0.3), _make_seen(0.9)]
    result = plan_status(explore_threshold=threshold, seen_properties=props)
    assert result["properties_past_threshold"] == 2
    assert result["bid_premium_pct"] == pytest.approx(0.02)
