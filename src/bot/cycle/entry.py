"""Filter candidates and execute entry orders."""

import logging
from datetime import UTC, datetime
from typing import Any

from src.config.settings import EXCLUDED_SYMBOLS
from src.execution.algo_order import placeStopLoss, placeTakeProfit
from src.execution.order_monitor import handlePartialFill, pollOrderFill
from src.execution.order_placer import calculateQuantity, placeEntryOrders
from src.logging_.trade_log import appendTradeRecord, buildTradeRecord
from src.market.cost_cache import CostCache
from src.market.scanner import filterCandidates

logger = logging.getLogger(__name__)


def executeEntries(
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
    minNotionals: dict[str, float] = botState["minNotionals"]  # type: ignore[assignment]
    baseUrl = str(botState["baseUrl"])
    apiKey = str(botState["apiKey"])
    apiSecret = str(botState["apiSecret"])

    qty = calculateQuantity(
        markPrice, float(str(botState["sizePerPair"])), minNotionals.get(symbol, 50.0)
    )
    spotBk, futBk = bookSpot.get(symbol, {}), bookFutures.get(symbol, {})
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
        entryFr=fr, exitFr=0.0, holdSettlements=0, grossPct=0.0, costRtPct=0.0,
        netPct=0.0, netDollar=0.0, fillTimeSpotMs=0, fillTimeFuturesMs=0,
        actualFillPriceSpot=float(str(spotInfo.get("average", spotMid))),
        actualFillPriceFutures=float(str(futInfo.get("average", futMid))),
        slippageSpotPct=0.0, slippageFuturesPct=0.0, partialFillOccurred=False,
    )
    record["algo_ids"] = [slId, tpId]
    appendTradeRecord(record)
    costCache.update(symbol, 0.0)
    return 1
