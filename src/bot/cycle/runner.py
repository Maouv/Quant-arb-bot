"""Cycle runner — entrypoint, error boundary, housekeeping."""

import logging
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

import ccxt

from src.bot.cycle.entry import executeEntries
from src.bot.cycle.monitor import monitorPositions
from src.bot.cycle.orphan import runOrphanCheck
from src.config.settings import MAX_PAIRS
from src.market.scanner import fetchBookTickerFutures, fetchBookTickerSpot, fetchPremiumIndex
from src.position.balance import computeSizePerPair, fetchFuturesBalance, shouldRefreshBalance
from src.position.tracker import fetchOpenPositions
from src.strategy.risk_guard import isBlackoutWindow, isBroadMarketStress

if TYPE_CHECKING:
    from src.market.cost_cache import CostCache

logger = logging.getLogger(__name__)


def runCycle(botState: dict[str, object]) -> None:
    """
    STEP 0 Safety → STEP 1 Fetch → STEP 2 Monitor → STEP 3 Entry
    → STEP 4 Orphan check → Housekeeping.
    Bot TIDAK BOLEH crash — semua error → log → continue.
    """
    try:
        _runCycleInner(botState)
    except ccxt.NetworkError as exc:
        logger.error("Cycle network error: %s", exc)
    except ccxt.ExchangeError as exc:
        logger.error("Cycle exchange error: %s", exc)
    except Exception as exc:
        logger.critical("Cycle unexpected error: %s", exc, exc_info=True)
    finally:
        botState["cycleCount"] = int(str(botState.get("cycleCount", 0))) + 1


def _runCycleInner(botState: dict[str, object]) -> None:
    """Core cycle logic — fetch, monitor, entry, orphan check, housekeeping."""
    spot = botState["spotExchange"]
    fut = botState["futuresExchange"]
    costCache: CostCache = botState["costCache"]  # type: ignore[assignment]
    suspended: dict[str, int] = botState["suspendedSymbols"]  # type: ignore[assignment]
    universe: list[str] = botState["validUniverse"]  # type: ignore[assignment]

    premiumIndex: list[dict[str, Any]] = fetchPremiumIndex(fut)
    bookFutures: dict[str, dict[str, float]] = fetchBookTickerFutures(fut)
    bookSpot: dict[str, dict[str, float]] = fetchBookTickerSpot(spot)
    openPositions: list[dict[str, Any]] = fetchOpenPositions(fut)
    botState["openPositions"] = openPositions

    monitorPositions(openPositions, premiumIndex, botState)

    slots = MAX_PAIRS - len(openPositions)
    if slots > 0 and not isBlackoutWindow() and not isBroadMarketStress({}, costCache):
        executeEntries(botState, premiumIndex, bookFutures, bookSpot, slots, costCache, universe)

    runOrphanCheck(botState, openPositions)

    if shouldRefreshBalance(botState["lastBalanceRefresh"]):  # type: ignore[arg-type]
        bal = fetchFuturesBalance(fut)
        botState["availableBalance"] = bal
        botState["sizePerPair"] = computeSizePerPair(bal)
        botState["lastBalanceRefresh"] = datetime.now(UTC)

    costCache.save()
    _decrementSuspended(suspended)
    logger.info("Cycle %s complete: positions=%d", botState.get("cycleCount"), len(openPositions))


def _decrementSuspended(suspendedSymbols: dict[str, int]) -> None:
    """Decrement suspension counters, remove expired."""
    for sym in list(suspendedSymbols):
        suspendedSymbols[sym] -= 1
        if suspendedSymbols[sym] <= 0:
            del suspendedSymbols[sym]
            logger.info("Symbol %s suspension lifted", sym)
