"""Handle normal and emergency position exits."""

import logging

from src.execution.algo_order import cancelAlgoOrder
from src.execution.order_monitor import pollOrderFill

logger = logging.getLogger(__name__)


def exitNormal(
    spotExchange: object, futuresExchange: object, symbol: str,
    spotSide: str, futuresSide: str, spotQuantity: float, futuresQuantity: float,
    algoIds: list[int], baseUrl: str, apiKey: str, apiSecret: str,
) -> dict[str, object]:
    """
    1. Cancel SL/TP  2. Limit exit both legs (spot skipped if qty=0)
    3. Poll fill; timeout → market fallback  4. Return trade result dict.
    """
    for algoId in algoIds:
        _cancelAlgoSafe(symbol, algoId, baseUrl, apiKey, apiSecret)
    spotInfo = _closeSpotNormal(spotExchange, symbol, spotSide, spotQuantity)
    futInfo = _closeFuturesNormal(futuresExchange, symbol, futuresSide, futuresQuantity)
    logger.info(
        "exitNormal complete: %s spotQty=%s futQty=%s", symbol, spotQuantity, futuresQuantity
    )
    return {
        "symbol": symbol, "spotOrder": spotInfo, "futuresOrder": futInfo, "exitType": "normal"
    }


def exitEmergency(
    spotExchange: object, futuresExchange: object, symbol: str,
    spotSide: str, futuresSide: str, spotQuantity: float, futuresQuantity: float,
    algoIds: list[int], baseUrl: str, apiKey: str, apiSecret: str,
) -> dict[str, object]:
    """FR flip → market exit immediately. Spot skipped if qty=0 (dust)."""
    for algoId in algoIds:
        _cancelAlgoSafe(symbol, algoId, baseUrl, apiKey, apiSecret)
    spotSymbol = symbol.replace("USDT", "/USDT") if "USDT" in symbol else symbol
    futSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    spotInfo: dict[str, object] = {}
    if spotQuantity > 0:
        spotInfo = spotExchange.create_order(  # type: ignore[attr-defined]
            spotSymbol, "market", spotSide.lower(), spotQuantity,
        )
    futInfo: dict[str, object] = futuresExchange.create_order(  # type: ignore[attr-defined]
        futSymbol, "market", futuresSide.lower(), futuresQuantity, params={"reduceOnly": True},
    )
    logger.warning(
        "exitEmergency complete: %s spotQty=%s futQty=%s", symbol, spotQuantity, futuresQuantity
    )
    return {
        "symbol": symbol, "spotOrder": spotInfo, "futuresOrder": futInfo, "exitType": "emergency"
    }


def _closeSpotNormal(
    exchange: object, symbol: str, side: str, quantity: float
) -> dict[str, object]:
    """Limit sell spot. Returns {} if qty=0 (dust skip)."""
    if quantity <= 0:
        logger.warning("exitNormal %s: spotQty=0, skipping spot leg (dust)", symbol)
        return {}
    spotSymbol = symbol.replace("USDT", "/USDT") if "USDT" in symbol else symbol
    ticker: dict[str, object] = exchange.fetch_ticker(spotSymbol)  # type: ignore[attr-defined]
    mid = (float(str(ticker.get("bid", 0))) + float(str(ticker.get("ask", 0)))) / 2
    order: dict[str, object] = exchange.create_order(  # type: ignore[attr-defined]
        spotSymbol, "limit", side.lower(), quantity, mid, params={"timeInForce": "GTC"},
    )
    status, info = pollOrderFill(exchange, str(order.get("id")), symbol)
    if status == "timeout":
        _cancelSafe(exchange, str(order.get("id")), spotSymbol)
        return _marketFallback(exchange, symbol, side, quantity, False)
    return info


def _closeFuturesNormal(
    exchange: object, symbol: str, side: str, quantity: float
) -> dict[str, object]:
    """Limit close futures (reduceOnly). Market fallback on timeout."""
    futSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    ticker: dict[str, object] = exchange.fetch_ticker(futSymbol)  # type: ignore[attr-defined]
    mid = (float(str(ticker.get("bid", 0))) + float(str(ticker.get("ask", 0)))) / 2
    order: dict[str, object] = exchange.create_order(  # type: ignore[attr-defined]
        futSymbol, "limit", side.lower(), quantity, mid,
        params={"timeInForce": "GTC", "reduceOnly": True},
    )
    status, info = pollOrderFill(exchange, str(order.get("id")), symbol)
    if status == "timeout":
        _cancelSafe(exchange, str(order.get("id")), futSymbol)
        return _marketFallback(exchange, symbol, side, quantity, True)
    return info


def _cancelSafe(exchange: object, orderId: str, ccxtSymbol: str) -> None:
    """Cancel a limit order before market fallback. Ignore -2011 (already filled/cancelled)."""
    try:
        exchange.cancel_order(orderId, ccxtSymbol)  # type: ignore[attr-defined]
    except Exception as exc:
        logger.warning("Cancel order %s skipped: %s", orderId, exc)


def _cancelAlgoSafe(symbol: str, algoId: int, baseUrl: str, apiKey: str, apiSecret: str) -> None:
    """Cancel algo order, ignore if already triggered or not found."""
    try:
        cancelAlgoOrder(symbol, algoId, baseUrl, apiKey, apiSecret)
    except Exception as exc:
        logger.warning("Cancel algoId=%s skipped: %s", algoId, exc)


def _marketFallback(
    exchange: object, symbol: str, side: str, quantity: float, reduceOnly: bool,
) -> dict[str, object]:
    """Market order fallback on limit timeout."""
    ccxtSymbol = (symbol.replace("USDT", "/USDT:USDT") if reduceOnly
                  else symbol.replace("USDT", "/USDT")) if "USDT" in symbol else symbol
    params = {"reduceOnly": True} if reduceOnly else {}
    result: dict[str, object] = exchange.create_order(  # type: ignore[attr-defined]
        ccxtSymbol, "market", side.lower(), quantity, params=params,
    )
    logger.warning("Market fallback: %s side=%s reduceOnly=%s", symbol, side, reduceOnly)
    return result
