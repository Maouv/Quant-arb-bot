"""Single bot cycle — called every 5 minutes."""

import logging
from datetime import UTC, datetime
from typing import Any

import ccxt

from src.config.settings import MAX_PAIRS
from src.execution.algo_order import (
    cancelAlgoOrder,
    listOpenAlgoOrders,
    placeStopLoss,
    placeTakeProfit,
)
from src.execution.exit_handler import exitEmergency, exitNormal
from src.execution.order_monitor import handlePartialFill, pollOrderFill
from src.execution.order_placer import calculateQuantity, placeEntryOrders
from src.logging_.trade_log import appendTradeRecord, buildTradeRecord
from src.market.cost_cache import CostCache
from src.market.scanner import (
    fetchBookTickerFutures,
    fetchBookTickerSpot,
    fetchPremiumIndex,
    filterCandidates,
)
from src.position.balance import computeSizePerPair, fetchFuturesBalance, shouldRefreshBalance
from src.position.orphan_checker import (
    checkOrphanAlgoOrders,
    checkOrphanRegularOrders,
    checkUnprotectedPositions,
    handleManipulationEvent,
)
from src.position.tracker import fetchOpenPositions
from src.strategy.risk_guard import isBlackoutWindow, isBroadMarketStress
from src.strategy.signal import isExitSignal, isFundingRateFlipped

logger = logging.getLogger(__name__)


def runCycle(botState: dict[str, object]) -> None:
    """
    STEP 0 Safety → STEP 1 Fetch → STEP 2 Monitor → STEP 3 Opportunities
    → STEP 4 Execute → STEP 5 Orphan check → Housekeeping.
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
    """Core cycle logic — separated for clean error boundary in runCycle."""
    spot = botState["spotExchange"]
    fut = botState["futuresExchange"]
    baseUrl = str(botState["baseUrl"])
    apiKey = str(botState["apiKey"])
    apiSecret = str(botState["apiSecret"])
    costCache: CostCache = botState["costCache"]  # type: ignore[assignment]
    suspended: dict[str, int] = botState["suspendedSymbols"]  # type: ignore[assignment]
    universe: list[str] = botState["validUniverse"]  # type: ignore[assignment]

    premiumIndex: list[dict[str, Any]] = fetchPremiumIndex(fut)
    bookFutures: dict[str, dict[str, float]] = fetchBookTickerFutures(fut)
    bookSpot: dict[str, dict[str, float]] = fetchBookTickerSpot(spot)
    openPositions: list[dict[str, Any]] = fetchOpenPositions(fut)
    botState["openPositions"] = openPositions

    _monitorPositions(openPositions, premiumIndex, botState)

    slots = MAX_PAIRS - len(openPositions)
    if slots > 0 and not isBlackoutWindow() and not isBroadMarketStress({}, costCache):
        _executeEntries(botState, premiumIndex, bookFutures, bookSpot, slots, costCache, universe)

    algoOrders = listOpenAlgoOrders(baseUrl, apiKey, apiSecret)
    for order in checkOrphanRegularOrders(fut, spot, openPositions):
        _cancelOrderSafe(fut, order)
    for order in checkOrphanAlgoOrders(algoOrders, openPositions):
        _cancelAlgoSafe(str(order["symbol"]), int(str(order["algoId"])), baseUrl, apiKey, apiSecret)
    for pos in checkUnprotectedPositions(openPositions, algoOrders):
        logger.warning("Unprotected position: %s", pos.get("symbol"))
    for pos in openPositions:
        handleManipulationEvent(str(pos.get("symbol", "")), spot, fut, suspended)

    if shouldRefreshBalance(botState["lastBalanceRefresh"]):  # type: ignore[arg-type]
        bal = fetchFuturesBalance(fut)
        botState["availableBalance"] = bal
        botState["sizePerPair"] = computeSizePerPair(bal)
        botState["lastBalanceRefresh"] = datetime.now(UTC)

    costCache.save()
    _decrementSuspended(suspended)
    logger.info("Cycle %s complete: positions=%d", botState.get("cycleCount"), len(openPositions))


def _monitorPositions(
    openPositions: list[dict[str, Any]],
    premiumIndex: list[dict[str, Any]],
    botState: dict[str, object],
) -> None:
    """Check each open position for exit signals."""
    frMap = {p["symbol"]: float(p["lastFundingRate"]) * 100 for p in premiumIndex}
    for pos in openPositions:
        symbol = str(pos.get("symbol", ""))
        currentFr = frMap.get(symbol, 0.0)
        entryFr = float(str(pos.get("entryFr", currentFr)))
        qty = float(str(pos.get("positionAmt", 0)))
        kwargs: dict[str, object] = {
            "spotExchange": botState["spotExchange"],
            "futuresExchange": botState["futuresExchange"],
            "symbol": symbol, "spotSide": "sell", "futuresSide": "buy",
            "quantity": qty, "algoIds": [],
            "baseUrl": str(botState["baseUrl"]),
            "apiKey": str(botState["apiKey"]),
            "apiSecret": str(botState["apiSecret"]),
        }
        try:
            if isFundingRateFlipped(entryFr, currentFr):
                exitEmergency(**kwargs)  # type: ignore[arg-type]
            elif isExitSignal(currentFr):
                exitNormal(**kwargs)  # type: ignore[arg-type]
        except Exception as exc:
            logger.error("Exit failed for %s: %s", symbol, exc)


def _executeEntries(
    botState: dict[str, object],
    premiumIndex: list[dict[str, Any]],
    bookFutures: dict[str, dict[str, float]],
    bookSpot: dict[str, dict[str, float]],
    slots: int,
    costCache: CostCache,
    universe: list[str],
) -> None:
    """Filter candidates and execute entry orders for available slots."""
    suspended: dict[str, int] = botState["suspendedSymbols"]  # type: ignore[assignment]
    from src.config.settings import EXCLUDED_SYMBOLS
    candidates = filterCandidates(
        premiumIndex, bookSpot, bookFutures, slots,
        EXCLUDED_SYMBOLS + list(suspended.keys()), universe, costCache,
    )
    entered = 0
    for candidate in candidates:
        if entered >= slots:
            break
        try:
            entered += _placeEntry(botState, candidate, bookFutures, bookSpot, costCache)
        except Exception as exc:
            logger.error("Entry failed for %s: %s", candidate.get("symbol"), exc)


def _placeEntry(
    botState: dict[str, object], candidate: dict[str, Any],
    bookFutures: dict[str, dict[str, float]], bookSpot: dict[str, dict[str, float]],
    costCache: CostCache,
) -> int:
    """Place entry for one candidate. Return 1 if successful, 0 otherwise."""
    symbol = str(candidate["symbol"])
    fr = float(str(candidate.get("lastFundingRate", 0)))
    markPrice = float(str(candidate.get("markPrice", 0)))
    sizePerPair = float(str(botState["sizePerPair"]))
    minNotionals: dict[str, float] = botState["minNotionals"]  # type: ignore[assignment]
    baseUrl = str(botState["baseUrl"])
    apiKey = str(botState["apiKey"])
    apiSecret = str(botState["apiSecret"])

    qty = calculateQuantity(markPrice, sizePerPair, minNotionals.get(symbol, 50.0))
    spotBk = bookSpot.get(symbol, {})
    futBk = bookFutures.get(symbol, {})
    spotMid = (spotBk.get("bid", markPrice) + spotBk.get("ask", markPrice)) / 2
    futMid = (futBk.get("bid", markPrice) + futBk.get("ask", markPrice)) / 2

    spotOrder, futOrder = placeEntryOrders(
        botState["spotExchange"], botState["futuresExchange"],
        symbol, "buy", "sell", qty, spotMid, futMid,
    )
    spotStatus, spotInfo = pollOrderFill(botState["spotExchange"], str(spotOrder.get("id")), symbol)
    futStatus, futInfo = pollOrderFill(botState["futuresExchange"], str(futOrder.get("id")), symbol)

    if spotStatus != "filled" or futStatus != "filled":
        handlePartialFill(
            botState["spotExchange"], botState["futuresExchange"], spotInfo, futInfo, symbol
        )
        return 0

    slId = placeStopLoss(
        symbol, "sell", str(qty), str(markPrice * 0.98), baseUrl, apiKey, apiSecret
    )
    tpId = placeTakeProfit(
        symbol, "sell", str(qty), str(markPrice * 1.02), baseUrl, apiKey, apiSecret
    )
    record = buildTradeRecord(
        symbol=symbol, side="long", entryTime=datetime.now(UTC).isoformat(), exitTime="",
        entryFr=fr, exitFr=0.0, holdSettlements=0,
        grossPct=0.0, costRtPct=0.0, netPct=0.0, netDollar=0.0,
        fillTimeSpotMs=0, fillTimeFuturesMs=0,
        actualFillPriceSpot=float(str(spotInfo.get("average", spotMid))),
        actualFillPriceFutures=float(str(futInfo.get("average", futMid))),
        slippageSpotPct=0.0, slippageFuturesPct=0.0, partialFillOccurred=False,
    )
    record["algo_ids"] = [slId, tpId]
    appendTradeRecord(record)
    costCache.update(symbol, 0.0)
    return 1


def _cancelOrderSafe(exchange: object, order: dict[str, object]) -> None:
    """Cancel regular order, log on failure."""
    try:
        exchange.cancel_order(str(order.get("id")), str(order.get("symbol")))  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Cancel order skipped: %s", exc)


def _cancelAlgoSafe(symbol: str, algoId: int, baseUrl: str, apiKey: str, apiSecret: str) -> None:
    """Cancel algo order, log on failure."""
    try:
        cancelAlgoOrder(symbol, algoId, baseUrl, apiKey, apiSecret)
    except Exception as exc:
        logger.warning("Cancel algo %s skipped: %s", algoId, exc)


def _decrementSuspended(suspendedSymbols: dict[str, int]) -> None:
    """Decrement suspension counters, remove expired."""
    for sym in list(suspendedSymbols):
        suspendedSymbols[sym] -= 1
        if suspendedSymbols[sym] <= 0:
            del suspendedSymbols[sym]
            logger.info("Symbol %s suspension lifted", sym)
