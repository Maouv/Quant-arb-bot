"""Poll order fill status and handle partial fills."""

import logging
import time

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS: int = 5
_FILLED_STATUSES: frozenset[str] = frozenset({"filled", "closed"})


def pollOrderFill(
    exchange: object, orderId: str, symbol: str, timeoutSeconds: int = 60,
) -> tuple[str, dict[str, object]]:
    """
    Poll setiap 5s sampai filled/closed atau timeout.
    symbol: ccxt format sudah dikonversi (CHR/USDT untuk spot, CHR/USDT:USDT untuk futures).
    Return: (status, orderInfo) — status: "filled" | "timeout" | "cancelled".
    """
    elapsed = 0
    while elapsed < timeoutSeconds:
        orderInfo: dict[str, object] = exchange.fetch_order(orderId, symbol)  # type: ignore[attr-defined]
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
    return "timeout", exchange.fetch_order(orderId, symbol)  # type: ignore[attr-defined]


def handlePartialFill(
    spotExchange: object, futuresExchange: object,
    spotOrder: dict[str, object], futuresOrder: dict[str, object], symbol: str,
) -> None:
    """
    Salah satu fill, yang lain timeout:
    1. Cancel keduanya 2. Re-fetch status (cancel -2011 = already filled)
    3. Close filled leg dengan MARKET order 4. Log "partial_fill_failed".
    """
    spotSymbol = symbol.replace("USDT", "/USDT") if "USDT" in symbol else symbol
    futSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    _cancelSafe(spotExchange, str(spotOrder.get("id", "")), spotSymbol)
    _cancelSafe(futuresExchange, str(futuresOrder.get("id", "")), futSymbol)

    # Re-fetch: cancel returning -2011 means order was already filled
    try:
        spotOrder = spotExchange.fetch_order(str(spotOrder.get("id", "")), spotSymbol)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Re-fetch spot order failed, using stale status: %s", exc)
    try:
        futuresOrder = futuresExchange.fetch_order(str(futuresOrder.get("id", "")), futSymbol)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Re-fetch futures order failed, using stale status: %s", exc)

    if str(spotOrder.get("status", "")) in _FILLED_STATUSES:
        qty = float(str(spotOrder.get("filled") or 0))
        spotExchange.create_order(spotSymbol, "market", "sell", qty)  # type: ignore[attr-defined]
        logger.error("partial_fill_failed: closed spot leg for %s qty=%s", symbol, qty)
    elif str(futuresOrder.get("status", "")) in _FILLED_STATUSES:
        qty = float(str(futuresOrder.get("filled") or 0))
        futuresExchange.create_order(futSymbol, "market", "buy", qty, params={"reduceOnly": True})  # type: ignore[attr-defined]
        logger.error("partial_fill_failed: closed futures leg for %s qty=%s", symbol, qty)


def _cancelSafe(exchange: object, orderId: str, ccxtSymbol: str) -> None:
    """Cancel order, ignore if already filled or not found."""
    try:
        exchange.cancel_order(orderId, ccxtSymbol)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Cancel order %s skipped: %s", orderId, exc)
