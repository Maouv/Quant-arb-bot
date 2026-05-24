"""Risk guard checks for entry/exit decisions."""

from datetime import UTC, datetime

from src.config.settings import (
    BLACKOUT_MINUTES,
    BROAD_STRESS_THRESHOLD,
    COST_SPIKE_MULTIPLIER,
    DEFAULT_COST_TIER,
    SETTLEMENT_HOURS_UTC,
)
from src.market.cost_cache import CostCache


def isCostSpike(symbol: str, currentCost: float, costCache: CostCache) -> bool:
    """currentCost > baseline * COST_SPIKE_MULTIPLIER (3x)."""
    baseline = costCache.getRollingAvg(symbol)
    if baseline == DEFAULT_COST_TIER:
        baseline = DEFAULT_COST_TIER
    return currentCost > baseline * COST_SPIKE_MULTIPLIER


def isBroadMarketStress(costSamples: dict[str, float], costCache: CostCache) -> bool:
    """Hitung % coins punya cost > 2x rolling avg. Return True kalau > BROAD_STRESS_THRESHOLD."""
    if not costSamples:
        return False
    stressedCount = 0
    for symbol, cost in costSamples.items():
        baseline = costCache.getRollingAvg(symbol)
        if cost > baseline * 2:
            stressedCount += 1
    return (stressedCount / len(costSamples)) > BROAD_STRESS_THRESHOLD


def isBlackoutWindow() -> bool:
    """True jika dalam BLACKOUT_MINUTES sebelum settlement. Settlement hours: 0, 8, 16 UTC."""
    now = datetime.now(UTC)
    currentMinute = now.hour * 60 + now.minute
    for hour in SETTLEMENT_HOURS_UTC:
        settlementMinute = hour * 60
        if settlementMinute - BLACKOUT_MINUTES <= currentMinute < settlementMinute:
            return True
    return False


def isBasisTooHigh(basis: float) -> bool:
    """basis > 0.05% → skip coin."""
    return basis > 0.05
