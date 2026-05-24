"""Orphan order detection and cleanup."""

import logging
from typing import Any

import ccxt

from src.execution.algo_order import cancelAlgoOrder, listOpenAlgoOrders
from src.position.orphan_checker import (
    checkOrphanAlgoOrders,
    checkOrphanRegularOrders,
    checkUnprotectedPositions,
    handleManipulationEvent,
)

logger = logging.getLogger(__name__)


def runOrphanCheck(
    botState: dict[str, object],
    openPositions: list[dict[str, Any]],
) -> None:
    """
    1. Cancel orphan regular orders (no matching position).
    2. Cancel orphan algo orders (no matching position).
    3. Log unprotected positions (no SL/TP).
    4. Handle manipulation events (futures closed, spot open).
    """
    spot = botState["spotExchange"]
    fut = botState["futuresExchange"]
    baseUrl = str(botState["baseUrl"])
    apiKey = str(botState["apiKey"])
    apiSecret = str(botState["apiSecret"])
    suspended: dict[str, int] = botState["suspendedSymbols"]  # type: ignore[assignment]

    algoOrders = listOpenAlgoOrders(baseUrl, apiKey, apiSecret)

    for order in checkOrphanRegularOrders(fut, spot, openPositions):
        if order.get("exchange") == "spot":
            _cancelSpotOrderSafe(spot, order)
        else:
            _cancelFuturesOrderSafe(fut, order)
    for order in checkOrphanAlgoOrders(algoOrders, openPositions):
        _cancelAlgoSafe(str(order["symbol"]), int(str(order["algoId"])), baseUrl, apiKey, apiSecret)
    for pos in checkUnprotectedPositions(openPositions, algoOrders):
        logger.warning("Unprotected position: %s", pos.get("symbol"))
    for pos in openPositions:
        handleManipulationEvent(str(pos.get("symbol", "")), spot, fut, suspended)


def _cancelFuturesOrderSafe(exchange: ccxt.binanceusdm, order: dict[str, object]) -> None:
    """Cancel futures order via fapiPrivateDeleteOrder (avoids sapi routing)."""
    try:
        exchange.fapiPrivateDeleteOrder({"symbol": order.get("symbol"), "orderId": order.get("orderId")})
    except ccxt.BaseError as exc:
        logger.warning("Cancel futures order skipped: %s", exc)


def _cancelSpotOrderSafe(exchange: ccxt.binance, order: dict[str, object]) -> None:
    """Cancel spot order via privateDeleteOrder."""
    try:
        exchange.privateDeleteOrder({"symbol": order.get("symbol"), "orderId": order.get("orderId")})
    except ccxt.BaseError as exc:
        logger.warning("Cancel spot order skipped: %s", exc)


def _cancelAlgoSafe(symbol: str, algoId: int, baseUrl: str, apiKey: str, apiSecret: str) -> None:
    """Cancel algo order, log on failure."""
    try:
        cancelAlgoOrder(symbol, algoId, baseUrl, apiKey, apiSecret)
    except Exception as exc:
        logger.warning("Cancel algo %s skipped: %s", algoId, exc)
