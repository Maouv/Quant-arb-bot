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
from src.position.balance import fetchSpotBalance

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

    # Set 1x leverage + isolated margin before entry (required for delta-neutral)
    _setFuturesMarginSettings(botState["futuresExchange"], symbol)

    spotBk, futBk = bookSpot.get(symbol, {}), bookFutures.get(symbol, {})
    spotMid = (spotBk.get("bid", markPrice) + spotBk.get("ask", markPrice)) / 2
    futMid = (futBk.get("bid", markPrice) + futBk.get("ask", markPrice)) / 2

    # FR > 0: long spot + short futures. FR < 0: short spot + long futures.
    spotSide = "buy" if fr > 0 else "sell"
    futSide = "sell" if fr > 0 else "buy"
    slTpSide = "buy" if futSide == "sell" else "sell"  # exit = opposite of entry
    if spotSide == "sell":
        baseAsset = symbol.replace("USDT", "")
        if fetchSpotBalance(botState["spotExchange"], baseAsset) < qty:
            logger.warning("Skip %s: spot asset balance insufficient for sell-short leg", symbol)
            return 0

    spotOrder, futOrder = placeEntryOrders(
        botState["spotExchange"], botState["futuresExchange"],
        symbol, spotSide, futSide, qty, spotMid, futMid,
    )
    spotSymbol = symbol.replace("USDT", "/USDT") if "USDT" in symbol else symbol
    futSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    spotStatus, spotInfo = pollOrderFill(
        botState["spotExchange"], str(spotOrder.get("id")), spotSymbol
    )
    futStatus, futInfo = pollOrderFill(
        botState["futuresExchange"], str(futOrder.get("id")), futSymbol
    )

    if spotStatus != "filled" or futStatus != "filled":
        handlePartialFill(
            botState["spotExchange"], botState["futuresExchange"], spotInfo, futInfo, symbol
        )
        return 0

    # Use actual filled qty from exchange (already precision-correct per symbol rules)
    filledQty = float(str(futInfo.get("filled") or qty))
    tick = float(str(botState.get("tickSizes", {}).get(symbol, 0.01)))  # type: ignore[union-attr]
    decimals = len(str(tick).rstrip("0").split(".")[-1])

    def _roundTick(price: float) -> str:
        return str(round(round(price / tick) * tick, decimals))

    try:
        slId = placeStopLoss(
            symbol, slTpSide, str(filledQty),
            _roundTick(markPrice * 1.02), baseUrl, apiKey, apiSecret,
        )
        tpId = placeTakeProfit(
            symbol, slTpSide, str(filledQty),
            _roundTick(markPrice * 0.95), baseUrl, apiKey, apiSecret,
        )
    except Exception as exc:
        logger.error("SL/TP failed for %s — rolling back entry: %s", symbol, exc)
        handlePartialFill(
            botState["spotExchange"], botState["futuresExchange"], spotInfo, futInfo, symbol
        )
        return 0

    record = buildTradeRecord(
        symbol=symbol, side=spotSide, entryTime=datetime.now(UTC).isoformat(), exitTime="",
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

def _setFuturesMarginSettings(futuresExchange: object, symbol: str) -> None:
    """Set 1x leverage + ISOLATED margin for symbol before entry."""
    try:
        futuresExchange.fapiPrivatePostMarginType(  # type: ignore[attr-defined]
            {"symbol": symbol, "marginType": "ISOLATED"}
        )
    except Exception as exc:
        # -4046 = already isolated, ignore. -4067 = open orders exist, abort entry.
        if "-4067" in str(exc) or "-1007" in str(exc):
            raise RuntimeError(f"setMarginType unknown/blocked for {symbol}") from exc
        if "-4046" not in str(exc):
            logger.warning("setMarginType %s: %s", symbol, exc)
    try:
        futuresExchange.fapiPrivatePostLeverage(  # type: ignore[attr-defined]
            {"symbol": symbol, "leverage": 1}
        )
    except Exception as exc:
        logger.warning("setLeverage %s: %s", symbol, exc)
