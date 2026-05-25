"""Handle normal and emergency position exits."""

import logging

from src.execution.algo_order import cancelAlgoOrder
from src.execution.order_monitor import pollOrderFill
from src.execution.order_placer import placeEntryOrders

logger = logging.getLogger(__name__)


def exitNormal(
    spotExchange: object, futuresExchange: object, symbol: str,
    spotSide: str, futuresSide: str, quantity: float, algoIds: list[int],
    baseUrl: str, apiKey: str, apiSecret: str,
) -> dict[str, object]:
    """
    1. Cancel existing SL/TP (via algoIds)
    2. Place limit exit orders (spot + futures)
    3. Poll fill, timeout 60s — kalau timeout → fallback market order
    4. Return trade result dict. futures exit: reduceOnly=True.
    """
    for algoId in algoIds:
        _cancelAlgoSafe(symbol, algoId, baseUrl, apiKey, apiSecret)

    spotOrder, futuresOrder = _placeLimitExit(
        spotExchange, futuresExchange, symbol, spotSide, futuresSide, quantity
    )
    spotStatus, spotInfo = pollOrderFill(spotExchange, str(spotOrder.get("id")), symbol)
    futuresStatus, futuresInfo = pollOrderFill(futuresExchange, str(futuresOrder.get("id")), symbol)

    if spotStatus == "timeout":
        spotInfo = _marketFallback(spotExchange, symbol, spotSide, quantity, reduceOnly=False)
    if futuresStatus == "timeout":
        futuresInfo = _marketFallback(
            futuresExchange, symbol, futuresSide, quantity, reduceOnly=True
        )

    logger.info(
        "exitNormal complete: %s spotStatus=%s futuresStatus=%s",
        symbol, spotStatus, futuresStatus,
    )
    return {
        "symbol": symbol, "spotOrder": spotInfo, "futuresOrder": futuresInfo, "exitType": "normal"
    }


def exitEmergency(
    spotExchange: object, futuresExchange: object, symbol: str,
    spotSide: str, futuresSide: str, quantity: float, algoIds: list[int],
    baseUrl: str, apiKey: str, apiSecret: str,
) -> dict[str, object]:
    """
    FR flip → market order langsung, no waiting.
    1. Cancel SL/TP  2. Market order both legs  3. Return trade result dict.
    """
    for algoId in algoIds:
        _cancelAlgoSafe(symbol, algoId, baseUrl, apiKey, apiSecret)

    spotSymbol = symbol.replace("USDT", "/USDT") if "USDT" in symbol else symbol
    futSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    spotInfo = spotExchange.create_order(spotSymbol, "market", spotSide.lower(), quantity)  # type: ignore[attr-defined]
    futuresInfo = futuresExchange.create_order(  # type: ignore[attr-defined]
        futSymbol, "market", futuresSide.lower(), quantity, params={"reduceOnly": True}
    )
    logger.warning("exitEmergency complete: %s spot=%s futures=%s", symbol, spotSide, futuresSide)
    return {
        "symbol": symbol, "spotOrder": spotInfo,
        "futuresOrder": futuresInfo, "exitType": "emergency",
    }


def _cancelAlgoSafe(symbol: str, algoId: int, baseUrl: str, apiKey: str, apiSecret: str) -> None:
    """Cancel algo order, ignore if already triggered or not found."""
    try:
        cancelAlgoOrder(symbol, algoId, baseUrl, apiKey, apiSecret)
    except Exception as exc:
        logger.warning("Cancel algoId=%s skipped: %s", algoId, exc)


def _placeLimitExit(
    spotExchange: object, futuresExchange: object, symbol: str,
    spotSide: str, futuresSide: str, quantity: float,
) -> tuple[dict[str, object], dict[str, object]]:
    """Fetch mid price dan place limit exit orders."""
    spotSymbol = symbol.replace("USDT", "/USDT") if "USDT" in symbol else symbol
    futSymbol = symbol.replace("USDT", "/USDT:USDT") if "USDT" in symbol else symbol
    spotT: dict[str, object] = spotExchange.fetch_ticker(spotSymbol)  # type: ignore[attr-defined]
    futT: dict[str, object] = futuresExchange.fetch_ticker(futSymbol)  # type: ignore[attr-defined]
    spotMid = (float(spotT["bid"]) + float(spotT["ask"])) / 2  # type: ignore[arg-type]
    futMid = (float(futT["bid"]) + float(futT["ask"])) / 2  # type: ignore[arg-type]
    return placeEntryOrders(
        spotExchange, futuresExchange, symbol, spotSide, futuresSide, quantity, spotMid, futMid
    )


def _marketFallback(
    exchange: object, symbol: str, side: str, quantity: float, reduceOnly: bool,
) -> dict[str, object]:
    """Place market order sebagai fallback saat limit timeout."""
    # reduceOnly=True means futures; False means spot
    ccxtSymbol = (symbol.replace("USDT", "/USDT:USDT") if reduceOnly
                  else symbol.replace("USDT", "/USDT")) if "USDT" in symbol else symbol
    params = {"reduceOnly": True} if reduceOnly else {}
    result: dict[str, object] = exchange.create_order(  # type: ignore[attr-defined]
        ccxtSymbol, "market", side.lower(), quantity, params=params
    )
    logger.warning("Market fallback executed: %s side=%s reduceOnly=%s", symbol, side, reduceOnly)
    return result
