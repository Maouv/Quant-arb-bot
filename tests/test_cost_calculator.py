"""Unit tests for market/cost_calculator.py and market/slippage.py — pure logic, no API."""

import pytest

from src.config.settings import FEE_RT, TAKER_FEE
from src.market.cost_calculator import (
    calculateActualCostRt,
    calculateBasis,
    calculateNetExpected,
    calculateSpread,
    calculateTotalRtCost,
)
from src.market.slippage import estimateSlippage


def test_calculateSpread_normal() -> None:
    """Standard spread calculation."""
    assert calculateSpread(100.0, 102.0) == pytest.approx(2.0 / 101.0 * 100)


def test_calculateSpread_zero_mid() -> None:
    """Zero mid price → return 0, no ZeroDivision."""
    assert calculateSpread(0.0, 0.0) == 0.0


def test_calculateBasis_normal() -> None:
    """Standard basis calculation."""
    result = calculateBasis(101.0, 100.0)
    assert abs(result - 1.0) < 0.0001


def test_calculateBasis_zero_index() -> None:
    """Zero index price → return 0, no ZeroDivision."""
    assert calculateBasis(100.0, 0.0) == 0.0


def test_calculateTotalRtCost() -> None:
    """Total RT cost = FEE_RT + all spreads*2 + all slippages*2 + basis."""
    result = calculateTotalRtCost(0.01, 0.01, 0.005, 0.005, 0.02)
    expected = FEE_RT + 0.02 + 0.02 + 0.01 + 0.01 + 0.02
    assert abs(result - expected) < 1e-9


def test_calculateNetExpected_profitable() -> None:
    """FR high enough to cover cost → positive net."""
    result = calculateNetExpected(0.10, 0.05)
    assert result > 0


def test_calculateNetExpected_unprofitable() -> None:
    """FR too low relative to cost → negative net. FR 0.001 = 0.1%, cost 0.20% → -0.1."""
    result = calculateNetExpected(0.001, 0.20)
    assert result < 0


def test_calculateNetExpected_negative_fr() -> None:
    """Negative FR uses abs value."""
    assert calculateNetExpected(-0.10, 0.05) == calculateNetExpected(0.10, 0.05)


def test_calculateActualCostRt() -> None:
    """Post-trade cost computed correctly."""
    result = calculateActualCostRt(101.0, 100.0, 99.0, 100.0)
    expected = (0.01 + 0.01 + TAKER_FEE * 4) * 100
    assert abs(result - expected) < 1e-9


def test_estimateSlippage_fills_within_book() -> None:
    """positionSize filled within first few levels → slippage > 0."""
    asks = [["100.0", "1.0"], ["101.0", "1.0"], ["102.0", "1.0"]]
    bids = [["99.0", "1.0"]]
    result = estimateSlippage(asks, bids, 150.0)
    assert result > 0.0


def test_estimateSlippage_empty_book() -> None:
    """Empty book → return 0.0, no crash."""
    assert estimateSlippage([], [], 100.0) == 0.0


def test_estimateSlippage_small_position() -> None:
    """Position fills at best ask → minimal slippage."""
    asks = [["100.0", "10.0"]]
    bids = [["99.0", "10.0"]]
    result = estimateSlippage(asks, bids, 50.0)
    assert result >= 0.0
