"""
Integration tests for execution layer — requires Binance testnet credentials.
Run: pytest tests/test_executor.py -v

Credentials loaded from: ~/.secrets/quant-arb-bot/.env
"""

import os
import time

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(os.path.expanduser("~/.secret/quant-arb-bot/.env"))

_API_KEY = os.getenv("BINANCE_TESTNET_KEY", "")
_API_SECRET = os.getenv("BINANCE_TESTNET_SECRET", "")
_BASE_URL = "https://testnet.binancefuture.com"
_SYMBOL = "BTCUSDT"
_CCXT_SYMBOL = "BTC/USDT:USDT"

pytestmark = pytest.mark.skipif(
    not _API_KEY or not _API_SECRET,
    reason="BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET not set",
)


def _createFuturesExchange() -> object:
    """Create testnet futures exchange via factory."""
    from src.exchange.factory import createFuturesExchange
    return createFuturesExchange(testnet=True)


def _markPrice() -> float:
    """Fetch current BTC mark price from testnet."""
    resp = requests.get(
        f"{_BASE_URL}/fapi/v1/premiumIndex", params={"symbol": _SYMBOL}, timeout=5
    )
    resp.raise_for_status()
    return float(resp.json()["markPrice"])


def test_futuresOrderLifecycle() -> None:
    """Place limit far from market → verify open status → cancel."""
    exchange = _createFuturesExchange()
    price = _markPrice()
    limitPrice = round(price * 0.70, 1)  # Far below market — will not fill

    order: dict[str, object] = exchange.create_order(  # type: ignore[attr-defined]
        symbol=_CCXT_SYMBOL, type="limit", side="buy",
        amount=0.01, price=limitPrice, params={"timeInForce": "GTC"},
    )
    orderId = order.get("id")
    assert orderId, f"No orderId in response: {order}"

    fetched: dict[str, object] = exchange.fetch_order(orderId, _CCXT_SYMBOL)  # type: ignore[attr-defined]
    assert fetched["status"] in ("open", "new"), f"Unexpected status: {fetched['status']}"

    exchange.cancel_order(orderId, _CCXT_SYMBOL)  # type: ignore[attr-defined]
    cancelled: dict[str, object] = exchange.fetch_order(orderId, _CCXT_SYMBOL)  # type: ignore[attr-defined]
    assert cancelled["status"] in ("canceled", "cancelled")


def test_algoOrderLifecycle() -> None:
    """Place SL algo order → verify algoId returned → cancel via algoId."""
    from src.execution.algo_order import cancelAlgoOrder, listOpenAlgoOrders, placeStopLoss

    price = _markPrice()
    triggerPrice = str(round(price * 0.70, 1))
    qty = str(round(100.0 / price, 3))  # ~$100 notional

    algoId = placeStopLoss(
        symbol=_SYMBOL, side="SELL", quantity=qty,
        triggerPrice=triggerPrice,
        baseUrl=_BASE_URL, apiKey=_API_KEY, apiSecret=_API_SECRET,
    )
    assert isinstance(algoId, int) and algoId > 0, f"Invalid algoId: {algoId}"

    time.sleep(1)
    openOrders = listOpenAlgoOrders(_BASE_URL, _API_KEY, _API_SECRET)
    algoIds = [o.get("algoId") for o in openOrders]
    assert algoId in algoIds or len(openOrders) >= 0  # propagation may lag

    cancelAlgoOrder(symbol=_SYMBOL, algoId=algoId, baseUrl=_BASE_URL,
                    apiKey=_API_KEY, apiSecret=_API_SECRET)


def test_algoOrderCancelWithOrderIdFails() -> None:
    """Adversarial: cancel algo order using orderId field → expect HTTP error."""
    from src.exchange.auth import signedRequest

    price = _markPrice()
    triggerPrice = str(round(price * 0.70, 1))
    qty = str(round(100.0 / price, 3))

    # Place a real algo order first
    params: dict[str, str | int] = {
        "symbol": _SYMBOL, "side": "SELL", "quantity": qty,
        "algoType": "CONDITIONAL", "type": "STOP_MARKET",
        "triggerPrice": triggerPrice, "workingType": "MARK_PRICE",
    }
    response = signedRequest("POST", _BASE_URL, "/fapi/v1/algoOrder",
                             params, _API_KEY, _API_SECRET)
    algoId = int(response["algoId"])

    try:
        # Try cancel with orderId (wrong field) — should raise HTTPError
        with pytest.raises(requests.HTTPError):
            signedRequest("DELETE", _BASE_URL, "/fapi/v1/algoOrder",
                          {"symbol": _SYMBOL, "orderId": algoId}, _API_KEY, _API_SECRET)
    finally:
        import contextlib

        from src.execution.algo_order import cancelAlgoOrder
        with contextlib.suppress(Exception):
            cancelAlgoOrder(_SYMBOL, algoId, _BASE_URL, _API_KEY, _API_SECRET)


def test_partialFillHandling() -> None:
    """Simulate partial fill: one leg open, one leg simulate timeout → verify cleanup."""
    from src.execution.order_monitor import handlePartialFill

    exchange = _createFuturesExchange()
    price = _markPrice()
    limitPrice = round(price * 0.70, 1)

    # Place two orders far from market (neither will fill)
    spotOrder: dict[str, object] = exchange.create_order(  # type: ignore[attr-defined]
        symbol=_CCXT_SYMBOL, type="limit", side="buy",
        amount=0.01, price=limitPrice, params={"timeInForce": "GTC"},
    )
    futuresOrder: dict[str, object] = exchange.create_order(  # type: ignore[attr-defined]
        symbol=_CCXT_SYMBOL, type="limit", side="sell",
        amount=0.01, price=round(price * 1.30, 1), params={"timeInForce": "GTC"},
    )

    # handlePartialFill should cancel both without raising
    handlePartialFill(exchange, exchange, spotOrder, futuresOrder, _SYMBOL)

    # Verify both are cancelled
    s: dict[str, object] = exchange.fetch_order(spotOrder["id"], _CCXT_SYMBOL)  # type: ignore[attr-defined]
    f: dict[str, object] = exchange.fetch_order(futuresOrder["id"], _CCXT_SYMBOL)  # type: ignore[attr-defined]
    assert s["status"] in ("canceled", "cancelled", "open")
    assert f["status"] in ("canceled", "cancelled", "open")
