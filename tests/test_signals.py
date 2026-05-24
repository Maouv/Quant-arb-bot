"""Unit tests for strategy/signal.py — pure logic, no API."""

import pytest

from src.config.settings import ENTRY_THRESHOLD, EXIT_THRESHOLD
from src.strategy.signal import determineSide, isEntrySignal, isExitSignal, isFundingRateFlipped


def test_isEntrySignal_above_threshold() -> None:
    """FR well above threshold → entry signal."""
    assert isEntrySignal(0.10) is True


def test_isEntrySignal_below_threshold() -> None:
    """FR below threshold → no entry."""
    assert isEntrySignal(0.03) is False


def test_isEntrySignal_exact_threshold() -> None:
    """FR exactly at threshold → entry (>=)."""
    assert isEntrySignal(ENTRY_THRESHOLD) is True


def test_isEntrySignal_negative_above_threshold() -> None:
    """Negative FR with abs above threshold → entry."""
    assert isEntrySignal(-0.10) is True


def test_isEntrySignal_negative_below_threshold() -> None:
    """Negative FR with abs below threshold → no entry."""
    assert isEntrySignal(-0.03) is False


def test_isExitSignal_below_threshold() -> None:
    """FR below exit threshold → exit signal."""
    assert isExitSignal(0.01) is True


def test_isExitSignal_above_threshold() -> None:
    """FR above exit threshold → no exit."""
    assert isExitSignal(0.03) is False


def test_isExitSignal_exact_threshold() -> None:
    """FR exactly at exit threshold → no exit (<, not <=)."""
    assert isExitSignal(EXIT_THRESHOLD) is False


def test_isFundingRateFlipped_positive_to_negative() -> None:
    """Positive entry FR flipped to negative → True."""
    assert isFundingRateFlipped(0.05, -0.01) is True


def test_isFundingRateFlipped_negative_to_positive() -> None:
    """Negative entry FR flipped to positive → True."""
    assert isFundingRateFlipped(-0.05, 0.01) is True


def test_isFundingRateFlipped_same_sign() -> None:
    """Both positive → no flip."""
    assert isFundingRateFlipped(0.05, 0.03) is False


def test_isFundingRateFlipped_same_sign_negative() -> None:
    """Both negative → no flip."""
    assert isFundingRateFlipped(-0.05, -0.03) is False


def test_determineSide_positive_fr() -> None:
    """Positive FR → long spot (BUY), short futures (SELL)."""
    assert determineSide(0.05) == ("BUY", "SELL")


def test_determineSide_negative_fr() -> None:
    """Negative FR → short spot (SELL), long futures (BUY)."""
    assert determineSide(-0.05) == ("SELL", "BUY")
