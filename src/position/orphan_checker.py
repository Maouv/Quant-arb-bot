"""Orphan order and unprotected position detection."""

import logging
from typing import Any

import ccxt

logger = logging.getLogger(__name__)


def checkOrphanRegularOrders(
    futuresExchange: ccxt.binanceusdm,
    spotExchange: ccxt.binance,
    openPositions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    GET /fapi/v1/openOrders + GET /api/v3/openOrders.
    Order yang symbol-nya tidak ada di openPositions → orphan.
    Return list of orders to cancel.
    """
    posSymbols = {p.get("symbol") for p in openPositions}
    orphans: list[dict[str, Any]] = []

    try:
        futuresOrders = futuresExchange.fapiPrivateGetOpenOrders()
        for o in futuresOrders:
            if o.get("symbol") not in posSymbols:
                orphans.append({
                    "exchange": "futures",
                    "symbol": o.get("symbol"),
                    "orderId": o.get("orderId"),
                })
    except ccxt.BaseError as e:
        logger.error(f"Failed to fetch futures open orders: {e}")

    try:
        spotOrders = spotExchange.privateGetOpenOrders()
        for o in spotOrders:
            if o.get("symbol") not in posSymbols:
                orphans.append({
                    "exchange": "spot",
                    "symbol": o.get("symbol"),
                    "orderId": o.get("orderId"),
                })
    except ccxt.BaseError as e:
        logger.error(f"Failed to fetch spot open orders: {e}")

    return orphans


def checkOrphanAlgoOrders(
    openAlgoOrders: list[dict[str, Any]],
    openPositions: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Algo order yang symbol-nya tidak ada di openPositions → orphan.
    Return list of algo orders to cancel (by algoId).
    """
    posSymbols = {p.get("symbol") for p in openPositions}
    return [o for o in openAlgoOrders if o.get("symbol") not in posSymbols]


def checkUnprotectedPositions(
    openPositions: list[dict[str, Any]],
    openAlgoOrders: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """
    Posisi yang tidak punya SL/TP di openAlgoOrders → unprotected.
    Return list of positions needing emergency SL.
    """
    protectedSymbols = {o.get("symbol") for o in openAlgoOrders}
    return [p for p in openPositions if p.get("symbol") not in protectedSymbols]


def handleManipulationEvent(
    symbol: str,
    spotExchange: ccxt.binance,
    futuresExchange: ccxt.binanceusdm,
    suspendedSymbols: dict[str, int],
) -> None:
    """
    Futures closed tapi spot masih open.
    1. Close spot MARKET immediately.
    2. Log manipulation_event.
    3. Suspend coin 3 cycles.
    """
    logger.critical(f"MANIPULATION EVENT: {symbol}")

    try:
        spotExchange.create_market_order(symbol, "sell", 0)  # qty must be fetched
    except ccxt.BaseError as e:
        logger.error(f"Failed to close spot during manipulation event: {e}")

    suspendedSymbols[symbol] = 3
