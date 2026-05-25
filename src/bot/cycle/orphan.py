"""Orphan order detection and cleanup."""

import logging
from typing import Any

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

    algoOrders = listOpenAlgoOrders(baseUrl, apiKey, apiSecret)

    for order in checkOrphanRegularOrders(fut, spot, openPositions):
        exchange = spot if order.get("exchange") == "spot" else fut
        _cancelOrderSafe(exchange, order)
    for order in checkOrphanAlgoOrders(algoOrders, openPositions):
        _cancelAlgoSafe(str(order["symbol"]), int(str(order["algoId"])), baseUrl, apiKey, apiSecret)
    for pos in checkUnprotectedPositions(openPositions, algoOrders):
        logger.warning("Unprotected position: %s", pos.get("symbol"))
    # NOTE: handleManipulationEvent removed — requires proper futures-closed-but-spot-open
    # detection logic before re-enabling (was triggering for ALL open positions)


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
