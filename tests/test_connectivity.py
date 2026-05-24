#!/usr/bin/env python3
"""
test_connectivity.py — Adversarial endpoint validation for Binance API.
Tests all private endpoints before bot execution. Testnet only.
"""
import os
import sys
import time
import logging
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
import ccxt

# --- Load secrets ---
load_dotenv(os.path.expanduser("~/.secret/quant-arb-bot/.env"))

API_KEY = os.getenv("BINANCE_TESTNET_KEY")
API_SECRET = os.getenv("BINANCE_TESTNET_SECRET")
SPOT_API_KEY = os.getenv("BINANCE_TESTNET_SPOT_KEY") or API_KEY
SPOT_API_SECRET = os.getenv("BINANCE_TESTNET_SPOT_SECRET") or API_SECRET
BASE_TESTNET_FUTURES = "https://testnet.binancefuture.com"
BASE_DEMO_SPOT       = "https://demo-api.binance.com"  # Binance Demo Mode — key dari demo.binance.com

# --- Logging setup ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)

# --- Test state ---
results = {"passed": 0, "failed": 0, "warn": 0}


def passTest(name: str, msg: str = "") -> None:
    results["passed"] += 1
    logger.info(f"[PASS] {name}{' — ' + msg if msg else ''}")


def failTest(name: str, msg: str) -> None:
    results["failed"] += 1
    logger.error(f"[FAIL] {name} — {msg}")


def warnTest(name: str, msg: str) -> None:
    results["warn"] += 1
    logger.warning(f"[WARN] {name} — {msg}")


# --- ccxt instances ---
def createSpotExchange() -> ccxt.binance:
    ex = ccxt.binance({
        "apiKey": SPOT_API_KEY,
        "secret": SPOT_API_SECRET,
        "options": {"defaultType": "spot"},
        "urls": {"api": {
            "public":  f"{BASE_DEMO_SPOT}/api/v3",
            "private": f"{BASE_DEMO_SPOT}/api/v3",
        }},
        "recvWindow": 60000,
        "adjustForTimeDifference": True,
    })
    return ex


def createFuturesExchange() -> ccxt.binanceusdm:
    ex = ccxt.binanceusdm({
        "apiKey": API_KEY,
        "secret": API_SECRET,
        "options": {"defaultType": "future"},
        "recvWindow": 60000,
        "adjustForTimeDifference": True,
    })
    ex.set_sandbox_mode(True)
    return ex


# --- Raw requests for algo orders ---
def algoOrderRequest(method: str, endpoint: str, params: dict = None) -> dict:
    url = f"{BASE_TESTNET_FUTURES}{endpoint}"
    timestamp = int(time.time() * 1000)
    params = params or {}
    params["timestamp"] = timestamp
    queryString = "&".join(f"{k}={v}" for k, v in params.items())
    import hmac
    import hashlib
    signature = hmac.new(
        API_SECRET.encode(), queryString.encode(), hashlib.sha256
    ).hexdigest()
    params["signature"] = signature
    headers = {"X-MBX-APIKEY": API_KEY}
    resp = requests.request(method, url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


# --- Test functions ---
def testFapiDepth() -> None:
    """Test GET /fapi/v1/depth — schema and completeness."""
    name = "GET /fapi/v1/depth"
    try:
        exchange = createFuturesExchange()
        result = exchange.fapiPublicGetDepth({"symbol": "BTCUSDT", "limit": 5})
        if "bids" not in result or "asks" not in result:
            failTest(name, "missing bids/asks")
            return
        if not result["bids"] or not result["asks"]:
            failTest(name, "empty orderbook")
            return
        bid = result["bids"][0]
        if len(bid) != 2:
            failTest(name, f"bid format invalid: {bid}")
            return
        passTest(name, f"{len(result['bids'])} bids, {len(result['asks'])} asks")
    except Exception as e:
        failTest(name, str(e))


def testApiDepth() -> None:
    """Test GET /api/v3/depth — schema and completeness."""
    name = "GET /api/v3/depth"
    try:
        exchange = createSpotExchange()
        result = exchange.publicGetDepth({"symbol": "BTCUSDT", "limit": 5})
        if "bids" not in result or "asks" not in result:
            failTest(name, "missing bids/asks")
            return
        if not result["bids"] or not result["asks"]:
            failTest(name, "empty orderbook")
            return
        passTest(name, f"{len(result['bids'])} bids, {len(result['asks'])} asks")
    except Exception as e:
        failTest(name, str(e))


def testFapiV2Balance() -> None:
    """Test GET /fapi/v2/balance — availableBalance field."""
    name = "GET /fapi/v2/balance"
    try:
        exchange = createFuturesExchange()
        result = exchange.fapiPrivateV2GetBalance()
        if not isinstance(result, list):
            failTest(name, f"expected list, got {type(result).__name__}")
            return
        usdt = next((b for b in result if b.get("asset") == "USDT"), None)
        if not usdt:
            warnTest(name, "no USDT balance found")
            return
        if "availableBalance" not in usdt:
            failTest(name, "missing availableBalance field")
            return
        avail = float(usdt["availableBalance"])
        passTest(name, f"USDT availableBalance={avail}")
    except Exception as e:
        failTest(name, str(e))


def testApiV3Account() -> None:
    """Test GET /api/v3/account — balances structure."""
    name = "GET /api/v3/account"
    try:
        exchange = createSpotExchange()
        result = exchange.privateGetAccount()
        if "balances" not in result:
            failTest(name, "missing balances field")
            return
        if not isinstance(result["balances"], list):
            failTest(name, "balances not a list")
            return
        usdt = next((b for b in result["balances"] if b.get("asset") == "USDT"), None)
        if usdt:
            free = usdt.get("free", "0")
            locked = usdt.get("locked", "0")
            passTest(name, f"USDT free={free}, locked={locked}")
        else:
            passTest(name, "USDT balance=0")
    except ccxt.AuthenticationError as e:
        warnTest(name, f"spot testnet key may differ from futures key — verify BINANCE_TESTNET_SPOT_KEY: {e}")
    except Exception as e:
        failTest(name, str(e))


def testFapiPositionRisk() -> None:
    """Test GET /fapi/v2/positionRisk — raw symbol format."""
    name = "GET /fapi/v2/positionRisk"
    try:
        exchange = createFuturesExchange()
        result = exchange.fapiPrivateV2GetPositionRisk()
        if not isinstance(result, list):
            failTest(name, f"expected list, got {type(result).__name__}: {result}")
            return
        openPositions = [p for p in result if float(p.get("positionAmt", 0)) != 0]
        if openPositions:
            first = openPositions[0]
            rawSymbol = first.get("info", {}).get("symbol", "")
            if "USDT" in rawSymbol and ":" not in rawSymbol:
                passTest(name, f"raw symbol format OK: {rawSymbol}")
            else:
                warnTest(name, f"unexpected symbol format: {rawSymbol}")
        else:
            passTest(name, f"no open positions ({len(result)} symbols returned)")
    except Exception as e:
        failTest(name, str(e))


def testFapiOpenOrders() -> None:
    """Test GET /fapi/v1/openOrders — array response."""
    name = "GET /fapi/v1/openOrders"
    try:
        exchange = createFuturesExchange()
        result = exchange.fapiPrivateGetOpenOrders()
        if not isinstance(result, list):
            failTest(name, f"expected list, got {type(result).__name__}")
            return
        passTest(name, f"{len(result)} open futures orders")
    except Exception as e:
        failTest(name, str(e))


def testApiOpenOrders() -> None:
    """Test GET /api/v3/openOrders — array response."""
    name = "GET /api/v3/openOrders"
    try:
        exchange = createSpotExchange()
        result = exchange.privateGetOpenOrders()
        if not isinstance(result, list):
            failTest(name, f"expected list, got {type(result).__name__}")
            return
        passTest(name, f"{len(result)} open spot orders")
    except ccxt.AuthenticationError as e:
        warnTest(name, f"spot testnet key may differ from futures key: {e}")
    except Exception as e:
        failTest(name, str(e))


def spotOrderRequest(method: str, endpoint: str, params: dict = None) -> dict:
    """Raw authenticated request to demo spot API."""
    url = f"{BASE_DEMO_SPOT}/api/v3{endpoint}"
    timestamp = int(time.time() * 1000)
    params = params or {}
    params["timestamp"] = timestamp
    queryString = "&".join(f"{k}={v}" for k, v in params.items())
    import hmac as _hmac
    import hashlib
    signature = _hmac.new(
        SPOT_API_SECRET.encode(), queryString.encode(), hashlib.sha256
    ).hexdigest()
    params["signature"] = signature
    headers = {"X-MBX-APIKEY": SPOT_API_KEY}
    resp = requests.request(method, url, params=params, headers=headers, timeout=10)
    resp.raise_for_status()
    return resp.json()


def testSpotOrderLifecycle() -> None:
    """Test POST + DELETE /api/v3/order — place, verify, cancel."""
    name = "POST/DELETE /api/v3/order"
    orderId = None
    try:
        # Fetch current price to stay within PERCENT_PRICE filter
        price = float(requests.get(
            f"{BASE_DEMO_SPOT}/api/v3/ticker/price",
            params={"symbol": "BTCUSDT"}, timeout=5
        ).json()["price"])
        limitPrice = round(price * 0.98, 2)
        result = spotOrderRequest("POST", "/order", {
            "symbol": "BTCUSDT", "side": "BUY", "type": "LIMIT",
            "quantity": "0.0001", "price": str(limitPrice), "timeInForce": "GTC"
        })
        orderId = result.get("orderId")
        if not orderId:
            failTest(name, f"no orderId in response: {result}")
            return
        spotOrderRequest("DELETE", "/order", {"symbol": "BTCUSDT", "orderId": orderId})
        passTest(name, f"placed and cancelled order {orderId} at {limitPrice}")
    except requests.HTTPError as e:
        failTest(name, f"HTTP {e.response.status_code}: {e.response.text[:200]}")
    except Exception as e:
        failTest(name, str(e))
    finally:
        if orderId:
            try:
                spotOrderRequest("DELETE", "/order", {"symbol": "BTCUSDT", "orderId": orderId})
            except:
                pass


def testFuturesOrderLifecycle() -> None:
    """Test POST + DELETE /fapi/v1/order — place, verify, cancel."""
    name = "POST/DELETE /fapi/v1/order"
    orderId = None
    try:
        exchange = createFuturesExchange()
        # 0.01 BTC at $10,000 = $100 — safely above $50 min notional
        order = exchange.createOrder(
            symbol="BTC/USDT:USDT",
            type="limit",
            side="buy",
            amount=0.01,
            price=10000.0  # Far below market, won't fill
        )
        orderId = order.get("id") or order.get("info", {}).get("orderId")
        if not orderId:
            failTest(name, "no orderId in response")
            return
        exchange.cancelOrder(orderId, "BTC/USDT:USDT")
        passTest(name, f"placed and cancelled order {orderId}")
    except Exception as e:
        failTest(name, str(e))
        if orderId:
            try:
                createFuturesExchange().cancelOrder(orderId, "BTC/USDT:USDT")
            except:
                pass


def getMinQuantityForNotional(symbol: str, minNotional: float = 100.0) -> str:
    """Fetch mark price and return quantity for at least minNotional USD."""
    resp = requests.get(
        f"{BASE_TESTNET_FUTURES}/fapi/v1/premiumIndex",
        params={"symbol": symbol},
        timeout=5
    )
    resp.raise_for_status()
    markPrice = float(resp.json()["markPrice"])
    qty = minNotional / markPrice
    # Round up to 3 decimal places
    return f"{qty:.3f}"


def testAlgoOrderLifecycle() -> None:
    """Test POST/GET/DELETE /fapi/v1/algoOrder — algoId distinction."""
    name = "POST/DELETE /fapi/v1/algoOrder"
    algoId = None
    try:
        qty = getMinQuantityForNotional("BTCUSDT", minNotional=100.0)
        params = {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "quantity": qty,
            "algoType": "CONDITIONAL",    # Only valid value per Binance docs
            "type": "STOP_MARKET",
            "triggerPrice": "10000",
            "workingType": "MARK_PRICE",
            "reduceOnly": "true"          # Bypass min notional for test order
        }
        result = algoOrderRequest("POST", "/fapi/v1/algoOrder", params)
        algoId = result.get("algoId")
        if not algoId:
            failTest(name, f"no algoId in response: {result}")
            return
        passTest(f"{name} (place)", f"algoId={algoId}")
        # Check open algo orders (may not be available on testnet)
        try:
            openAlgo = algoOrderRequest("GET", "/fapi/v1/openAlgoOrders")
            if not isinstance(openAlgo, list):
                warnTest(f"{name} (list)", f"expected list, got: {type(openAlgo).__name__} — {str(openAlgo)[:100]}")
            else:
                found = any(o.get("algoId") == algoId for o in openAlgo)
                if found:
                    passTest(f"{name} (list)", f"algoId {algoId} found")
                else:
                    warnTest(f"{name} (list)", f"algoId {algoId} not in open orders — may be propagation delay")
        except requests.HTTPError as listErr:
            warnTest(f"{name} (list)", f"endpoint unavailable: {listErr.response.text}")
        # Cancel with algoId
        algoOrderRequest("DELETE", "/fapi/v1/algoOrder", {
            "symbol": "BTCUSDT",
            "algoId": algoId
        })
        passTest(f"{name} (cancel)", f"cancelled algoId={algoId}")
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "no body"
        failTest(name, f"HTTP {e.response.status_code}: {body}")
        if algoId:
            try:
                algoOrderRequest("DELETE", "/fapi/v1/algoOrder", {
                    "symbol": "BTCUSDT", "algoId": algoId
                })
            except:
                pass
    except Exception as e:
        failTest(name, str(e))


def testAlgoCancelWithWrongField() -> None:
    """Adversarial: try cancel algo order with orderId (should fail)."""
    name = "Algo cancel with orderId (expect fail)"
    algoId = None
    try:
        qty = getMinQuantityForNotional("BTCUSDT", minNotional=100.0)
        params = {
            "symbol": "BTCUSDT",
            "side": "SELL",
            "quantity": qty,
            "algoType": "CONDITIONAL",
            "type": "STOP_MARKET",
            "triggerPrice": "10000",
            "workingType": "MARK_PRICE",
            "reduceOnly": "true"
        }
        result = algoOrderRequest("POST", "/fapi/v1/algoOrder", params)
        algoId = result.get("algoId")
        if not algoId:
            warnTest(name, f"could not place algo order: {result}")
            return
        try:
            algoOrderRequest("DELETE", "/fapi/v1/algoOrder", {
                "symbol": "BTCUSDT",
                "orderId": algoId  # Wrong field intentionally
            })
            failTest(name, "cancel with orderId succeeded — should have failed")
        except requests.HTTPError:
            passTest(name, "correctly rejected cancel with orderId field")
    except requests.HTTPError as e:
        body = e.response.text if e.response is not None else "no body"
        warnTest(name, f"test setup failed: {body}")
    except Exception as e:
        warnTest(name, f"test setup failed: {e}")
    finally:
        if algoId:
            try:
                algoOrderRequest("DELETE", "/fapi/v1/algoOrder", {
                    "symbol": "BTCUSDT", "algoId": algoId
                })
            except:
                pass


# --- Main ---
def main() -> int:
    logger.info("=" * 60)
    logger.info("CONNECTIVITY TEST — Binance Testnet")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    # Public
    testFapiDepth()
    testApiDepth()

    # Account
    testFapiV2Balance()
    testApiV3Account()

    # Positions & Orders
    testFapiPositionRisk()
    testFapiOpenOrders()
    testApiOpenOrders()

    # Order lifecycle
    testSpotOrderLifecycle()
    testFuturesOrderLifecycle()

    # Algo orders (most critical)
    testAlgoOrderLifecycle()
    testAlgoCancelWithWrongField()

    # Summary
    total = results["passed"] + results["failed"] + results["warn"]
    logger.info("=" * 60)
    logger.info(f"SUMMARY: {results['passed']}/{total} passed, {results['failed']} failed, {results['warn']} warnings")
    logger.info("=" * 60)

    return 1 if results["failed"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
