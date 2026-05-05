"""Unit tests for buying_plan.logic — pure functions, no I/O."""

import pytest
from buying_plan.logic import composite_score


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
