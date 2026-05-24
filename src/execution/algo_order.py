"""Raw requests for Binance algo orders (SL/TP). ccxt tidak support endpoint ini."""

import logging

from src.exchange.auth import signedRequest

logger = logging.getLogger(__name__)

_ALGO_ORDER_ENDPOINT: str = "/fapi/v1/algoOrder"
_OPEN_ALGO_ORDERS_ENDPOINT: str = "/fapi/v1/openAlgoOrders"


def placeStopLoss(
    symbol: str,
    side: str,
    quantity: str,
    triggerPrice: str,
    baseUrl: str,
    apiKey: str,
    apiSecret: str,
) -> int:
    """
    POST /fapi/v1/algoOrder — place stop loss.

    algoType: "CONDITIONAL" (satu-satunya nilai valid)
    type: "STOP_MARKET"
    triggerPrice: BUKAN stopPrice
    workingType: "MARK_PRICE" — prevent candle spike trigger

    Return: algoId (int) — BUKAN orderId.
    """
    params: dict[str, str | int] = {
        "symbol": symbol, "side": side, "quantity": quantity,
        "algoType": "CONDITIONAL", "type": "STOP_MARKET",
        "triggerPrice": triggerPrice, "workingType": "MARK_PRICE",
    }
    response = signedRequest("POST", baseUrl, _ALGO_ORDER_ENDPOINT, params, apiKey, apiSecret)
    algoId = int(response["algoId"])
    logger.info("StopLoss placed: symbol=%s algoId=%s trigger=%s", symbol, algoId, triggerPrice)
    return algoId


def placeTakeProfit(
    symbol: str,
    side: str,
    quantity: str,
    triggerPrice: str,
    baseUrl: str,
    apiKey: str,
    apiSecret: str,
) -> int:
    """
    POST /fapi/v1/algoOrder — place take profit.
    Same schema, type: "TAKE_PROFIT_MARKET".
    Return: algoId (int).
    """
    params: dict[str, str | int] = {
        "symbol": symbol, "side": side, "quantity": quantity,
        "algoType": "CONDITIONAL", "type": "TAKE_PROFIT_MARKET",
        "triggerPrice": triggerPrice, "workingType": "MARK_PRICE",
    }
    response = signedRequest("POST", baseUrl, _ALGO_ORDER_ENDPOINT, params, apiKey, apiSecret)
    algoId = int(response["algoId"])
    logger.info("TakeProfit placed: symbol=%s algoId=%s trigger=%s", symbol, algoId, triggerPrice)
    return algoId


def cancelAlgoOrder(
    symbol: str,
    algoId: int,
    baseUrl: str,
    apiKey: str,
    apiSecret: str,
) -> None:
    """
    DELETE /fapi/v1/algoOrder.
    Params: symbol, algoId — JANGAN pakai orderId.
    JANGAN pakai ccxt cancel_order() — wrong endpoint.
    """
    params: dict[str, str | int] = {"symbol": symbol, "algoId": algoId}
    signedRequest("DELETE", baseUrl, _ALGO_ORDER_ENDPOINT, params, apiKey, apiSecret)
    logger.info("AlgoOrder cancelled: symbol=%s algoId=%s", symbol, algoId)


def listOpenAlgoOrders(
    baseUrl: str,
    apiKey: str,
    apiSecret: str,
) -> list[dict[str, str | int | float]]:
    """
    GET /fapi/v1/openAlgoOrders — BUKAN /fapi/v1/algo/orders/open.

    Return: flat array [{algoId, symbol, side, algoType, orderType, ...}]
    BUKAN wrapped {"orders": [...]}
    """
    params: dict[str, str | int] = {}
    response = signedRequest("GET", baseUrl, _OPEN_ALGO_ORDERS_ENDPOINT, params, apiKey, apiSecret)
    orders: list[dict[str, str | int | float]] = response if isinstance(response, list) else []  # type: ignore[assignment,unused-ignore]
    logger.debug("Open algo orders: count=%s", len(orders))
    return orders
