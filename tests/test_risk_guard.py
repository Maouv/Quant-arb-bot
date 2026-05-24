"""Unit tests for strategy/risk_guard.py — pure logic, no API."""

from unittest.mock import MagicMock

from src.config.settings import BROAD_STRESS_THRESHOLD, COST_SPIKE_MULTIPLIER, DEFAULT_COST_TIER
from src.strategy.risk_guard import isBasisTooHigh, isBroadMarketStress, isBlackoutWindow, isCostSpike


def _mockCache(avg: float) -> MagicMock:
    """Return CostCache mock with fixed getRollingAvg."""
    cache = MagicMock()
    cache.getRollingAvg.return_value = avg
    return cache


def test_isCostSpike_normal() -> None:
    """Cost within 3x baseline → no spike."""
    cache = _mockCache(DEFAULT_COST_TIER)
    assert isCostSpike("BTCUSDT", DEFAULT_COST_TIER * 2.0, cache) is False


def test_isCostSpike_elevated() -> None:
    """Cost > 3x baseline → spike detected."""
    cache = _mockCache(DEFAULT_COST_TIER)
    assert isCostSpike("BTCUSDT", DEFAULT_COST_TIER * (COST_SPIKE_MULTIPLIER + 0.1), cache) is True


def test_isCostSpike_exact_multiplier() -> None:
    """Cost exactly at 3x → no spike (not strictly greater)."""
    cache = _mockCache(DEFAULT_COST_TIER)
    assert isCostSpike("BTCUSDT", DEFAULT_COST_TIER * COST_SPIKE_MULTIPLIER, cache) is False


def test_isBroadMarketStress_below_threshold() -> None:
    """Fewer than 50% coins stressed → no broad stress."""
    cache = _mockCache(DEFAULT_COST_TIER)
    samples = {"BTCUSDT": DEFAULT_COST_TIER * 3.0, "ETHUSDT": DEFAULT_COST_TIER * 0.5}
    assert isBroadMarketStress(samples, cache) is False


def test_isBroadMarketStress_above_threshold() -> None:
    """More than 50% coins stressed → broad stress."""
    cache = _mockCache(DEFAULT_COST_TIER)
    samples = {f"COIN{i}USDT": DEFAULT_COST_TIER * 3.0 for i in range(6)}
    assert isBroadMarketStress(samples, cache) is True


def test_isBroadMarketStress_empty() -> None:
    """Empty samples → no stress (avoid ZeroDivision)."""
    cache = _mockCache(DEFAULT_COST_TIER)
    assert isBroadMarketStress({}, cache) is False


def test_isBlackoutWindow_outside() -> None:
    """isBlackoutWindow returns bool — just verify it doesn't raise."""
    result = isBlackoutWindow()
    assert isinstance(result, bool)


def test_isBasisTooHigh_above() -> None:
    """basis > 0.05% → too high."""
    assert isBasisTooHigh(0.06) is True


def test_isBasisTooHigh_below() -> None:
    """basis <= 0.05% → acceptable."""
    assert isBasisTooHigh(0.04) is False


def test_isBasisTooHigh_exact() -> None:
    """basis exactly 0.05% → acceptable (not strictly greater)."""
    assert isBasisTooHigh(0.05) is False
