"""Entry/exit signal detection."""

from src.config.settings import ENTRY_THRESHOLD, EXIT_THRESHOLD


def isEntrySignal(fundingRate: float) -> bool:
    """abs(fundingRate) >= ENTRY_THRESHOLD (0.05%). fundingRate sudah dalam %."""
    return abs(fundingRate) >= ENTRY_THRESHOLD


def isExitSignal(fundingRate: float) -> bool:
    """abs(fundingRate) < EXIT_THRESHOLD (0.02%)."""
    return abs(fundingRate) < EXIT_THRESHOLD


def isFundingRateFlipped(entryFr: float, currentFr: float) -> bool:
    """Sign berubah → emergency exit. entryFr positif tapi currentFr negatif, atau sebaliknya."""
    return (entryFr > 0 and currentFr < 0) or (entryFr < 0 and currentFr > 0)


def determineSide(fundingRate: float) -> tuple[str, str]:
    """
    Determine spot side + futures side.
    FR > 0 → long spot (BUY), short futures (SELL).
    FR < 0 → short spot (SELL), long futures (BUY).
    Return: (spotSide, futuresSide)
    """
    if fundingRate > 0:
        return ("BUY", "SELL")
    return ("SELL", "BUY")
