"""Market data scanning and candidate filtering."""

import logging
from typing import Any

from src.config.settings import ENTRY_THRESHOLD, MIN_PROFIT_THRESHOLD
from src.config.universe import UNIVERSE_8H
from src.market.cost_cache import CostCache
from src.market.cost_calculator import calculateBasis, calculateNetExpected, calculateSpread

logger = logging.getLogger(__name__)

type BookTicker = dict[str, float]
type PremiumIndexEntry = dict[str, Any]


def fetchPremiumIndex(futuresExchange: Any) -> list[PremiumIndexEntry]:
    """
    GET /fapi/v1/premiumIndex — semua coins sekaligus (1 call).
    Return list of: {symbol, markPrice, indexPrice, lastFundingRate, nextFundingTime}.
    """
    result = futuresExchange.fapiPublicGetPremiumIndex()
    return [{"symbol": item["symbol"], "markPrice": float(item["markPrice"]),
             "indexPrice": float(item["indexPrice"]),
             "lastFundingRate": float(item["lastFundingRate"]),
             "nextFundingTime": int(item["nextFundingTime"])} for item in result]


def fetchBookTickerFutures(futuresExchange: Any) -> dict[str, BookTicker]:
    """
    GET /fapi/v1/ticker/bookTicker — semua coins sekaligus.
    Return: {symbol: {bid, ask, bidQty, askQty}}.
    """
    result = futuresExchange.fapiPublicGetTickerBookTicker()
    return {item["symbol"]: {"bid": float(item["bidPrice"]), "ask": float(item["askPrice"]),
                             "bidQty": float(item["bidQty"]), "askQty": float(item["askQty"])}
            for item in result}


def fetchBookTickerSpot(spotExchange: Any) -> dict[str, BookTicker]:
    """
    GET /api/v3/ticker/bookTicker — semua coins sekaligus.
    Return: {symbol: {bid, ask, bidQty, askQty}}.
    """
    result = spotExchange.publicGetTickerBookTicker()
    return {item["symbol"]: {"bid": float(item["bidPrice"]), "ask": float(item["askPrice"]),
                             "bidQty": float(item["bidQty"]), "askQty": float(item["askQty"])}
            for item in result}


def fetchDepth(exchange: Any, symbol: str, limit: int = 5) -> dict[str, list[list[str]]]:
    """
    GET /fapi/v1/depth atau /api/v3/depth per symbol.
    Return: {bids: [[price, qty], ...], asks: [[price, qty], ...]}.
    """
    if hasattr(exchange, "fapiPublicGetDepth"):
        result = exchange.fapiPublicGetDepth({"symbol": symbol, "limit": limit})
    else:
        result = exchange.publicGetDepth({"symbol": symbol, "limit": limit})
    return {"bids": result["bids"], "asks": result["asks"]}


def filterCandidates(premiumIndex: list[PremiumIndexEntry], bookTickerSpot: dict[str, BookTicker],
                     bookTickerFutures: dict[str, BookTicker], openSlots: int,
                     excludedSymbols: list[str], validUniverse: list[str],
                     costCache: CostCache) -> list[PremiumIndexEntry]:
    """
    Filter: 1) Symbol in validUniverse dan bukan excluded
            2) |lastFundingRate| >= ENTRY_THRESHOLD
            3) net_expected > MIN_PROFIT_THRESHOLD.
    Sort: net_expected desc, tie-break alphabetical.
    """
    candidates = []
    passedUniverse = 0
    passedThreshold = 0
    passedBook = 0
    passedBasis = 0
    for item in premiumIndex:
        symbol = item["symbol"]
        if symbol not in validUniverse or symbol in excludedSymbols:
            continue
        passedUniverse += 1
        fr = abs(item["lastFundingRate"]) * 100  # API returns decimal, threshold is %
        if fr < ENTRY_THRESHOLD:
            continue
        passedThreshold += 1
        if symbol not in bookTickerSpot or symbol not in bookTickerFutures:
            continue
        passedBook += 1

        basis = calculateBasis(item["markPrice"], item["indexPrice"])
        if basis > 0.05:
            logger.info(
                "%s rejected: basis=%.4f%% > 0.05%% (FR=%.4f%%)",
                symbol, basis, item["lastFundingRate"] * 100,
            )
            continue
        passedBasis += 1

        spreadSpot = calculateSpread(bookTickerSpot[symbol]["bid"],
                                      bookTickerSpot[symbol]["ask"])
        spreadFutures = calculateSpread(bookTickerFutures[symbol]["bid"],
                                        bookTickerFutures[symbol]["ask"])
        costEstimate = costCache.getRollingAvg(symbol)
        netExpected = calculateNetExpected(item["lastFundingRate"], costEstimate)

        if netExpected <= MIN_PROFIT_THRESHOLD:
            logger.info(
                "%s rejected: net=%.4f%% (FR=%.4f%% - cost=%.4f%%)",
                symbol, netExpected, abs(item["lastFundingRate"]) * 100, costEstimate,
            )
            continue

        candidates.append({**item, "spreadSpot": spreadSpot, "spreadFutures": spreadFutures,
                          "basis": basis, "netExpected": netExpected})

    candidates.sort(key=lambda x: (-x["netExpected"], x["symbol"]))
    result = candidates[:openSlots]
    logger.info(
        "Filter: univ=%d frOk=%d book=%d basis=%d profit=%d → pick=%d",
        passedUniverse, passedThreshold, passedBook, passedBasis, len(candidates), len(result),
    )
    if result:
        top = result[0]
        logger.info(
            "Best candidate: %s FR=%.4f%% net=%.4f%%",
            top["symbol"], top["lastFundingRate"] * 100, top["netExpected"],
        )
    return result
