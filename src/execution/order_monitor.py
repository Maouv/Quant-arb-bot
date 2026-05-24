"""Poll order fill status and handle partial fills."""

import logging
import time

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS: int = 5
_FILLED_STATUSES: frozenset[str] = frozenset({"filled", "closed"})


def pollOrderFill(
    exchange: object,
    orderId: str,
    symbol: str,
    timeoutSeconds: int = 60,
) -> tuple[str, dict[str, object]]:
    """
    Poll setiap 5s sampai filled/closed atau timeout.
    Return: (status, orderInfo)
    status: "filled" | "timeout" | "cancelled"

    Note: "filled" dan "closed" keduanya = executed.
    """
    ccxtSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    elapsed = 0

    while elapsed < timeoutSeconds:
        orderInfo: dict[str, object] = exchange.fetch_order(orderId, ccxtSymbol)  # type: ignore[attr-defined]
        status = str(orderInfo.get("status", ""))

        if status in _FILLED_STATUSES:
            logger.info("Order %s filled: %s", orderId, status)
            return "filled", orderInfo

        if status == "canceled":
            logger.warning("Order %s was cancelled externally", orderId)
            return "cancelled", orderInfo

        time.sleep(_POLL_INTERVAL_SECONDS)
        elapsed += _POLL_INTERVAL_SECONDS

    logger.warning("Order %s timed out after %ss", orderId, timeoutSeconds)
    orderInfo = exchange.fetch_order(orderId, ccxtSymbol)  # type: ignore[attr-defined]
    return "timeout", orderInfo


def handlePartialFill(
    spotExchange: object,
    futuresExchange: object,
    spotOrder: dict[str, object],
    futuresOrder: dict[str, object],
    symbol: str,
) -> None:
    """
    Salah satu fill, yang lain timeout:
    1. Cancel keduanya
    2. Close yang sudah fill dengan MARKET order
    3. Log "partial_fill_failed"
    """
    ccxtSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    spotId = str(spotOrder.get("id", ""))
    futuresId = str(futuresOrder.get("id", ""))

    _cancelSafe(spotExchange, spotId, ccxtSymbol)
    _cancelSafe(futuresExchange, futuresId, ccxtSymbol)

    spotStatus = str(spotOrder.get("status", ""))
    futuresStatus = str(futuresOrder.get("status", ""))

    if spotStatus in _FILLED_STATUSES:
        qty = float(str(spotOrder.get("filled") or 0))
        spotExchange.create_order(ccxtSymbol, "market", "sell", qty)  # type: ignore[attr-defined]
        logger.error("partial_fill_failed: closed spot leg for %s qty=%s", symbol, qty)

    elif futuresStatus in _FILLED_STATUSES:
        qty = float(str(futuresOrder.get("filled") or 0))
        futuresExchange.create_order(ccxtSymbol, "market", "buy", qty, params={"reduceOnly": True})  # type: ignore[attr-defined]
        logger.error("partial_fill_failed: closed futures leg for %s qty=%s", symbol, qty)


def _cancelSafe(exchange: object, orderId: str, ccxtSymbol: str) -> None:
    """Cancel order, ignore if already filled or not found."""
    try:
        exchange.cancel_order(orderId, ccxtSymbol)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Cancel order %s skipped: %s", orderId, exc)
