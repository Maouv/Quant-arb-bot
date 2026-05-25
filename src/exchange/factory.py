"""Exchange factory for creating ccxt instances."""

import ccxt

from src.config.secrets import loadSecrets
from src.exchange.endpoints import BASE_DEMO_SPOT


def createSpotExchange(testnet: bool = True) -> ccxt.binance:
    """
    Create ccxt spot instance.
    - recvWindow: 60000
    - adjustForTimeDifference: True
    - Testnet: override URL ke demo-api.binance.com (JANGAN pakai set_sandbox_mode)
    - Spot demo key BERBEDA dari futures testnet key (dari demo.binance.com)
    """
    secrets = loadSecrets()

    if testnet:
        apiKey = secrets.get("BINANCE_TESTNET_SPOT_KEY", "")
        apiSecret = secrets.get("BINANCE_TESTNET_SPOT_SECRET", "")
    else:
        apiKey = secrets.get("BINANCE_API_KEY", "")
        apiSecret = secrets.get("BINANCE_API_SECRET", "")

    exchange = ccxt.binance(
        {
            "apiKey": apiKey,
            "secret": apiSecret,
            "options": {"defaultType": "spot"},
            "recvWindow": 60000,
            "adjustForTimeDifference": True,
        }
    )

    if testnet:
        exchange.urls["api"]["public"] = f"{BASE_DEMO_SPOT}/api/v3"
        exchange.urls["api"]["private"] = f"{BASE_DEMO_SPOT}/api/v3"
        exchange.urls["api"]["v1"] = f"{BASE_DEMO_SPOT}/api/v1"
        exchange.urls["api"]["sapi"] = f"{BASE_DEMO_SPOT}/sapi/v1"
        exchange.urls["api"]["sapiV2"] = f"{BASE_DEMO_SPOT}/sapi/v2"
        exchange.urls["api"]["sapiV3"] = f"{BASE_DEMO_SPOT}/sapi/v3"
        exchange.urls["api"]["sapiV4"] = f"{BASE_DEMO_SPOT}/sapi/v4"
        # demo-api.binance.com does not support sapi/v1/capital/config/getall
        # which ccxt calls internally in fetch_currencies → skip it
        exchange.fetch_currencies = lambda params={}: {}  # type: ignore[method-assign]

    return exchange


def createFuturesExchange(testnet: bool = True) -> ccxt.binanceusdm:
    """
    Create ccxt futures instance.
    - recvWindow: 60000
    - adjustForTimeDifference: True
    - Testnet: override URL ke testnet.binancefuture.com (JANGAN pakai set_sandbox_mode)
    - set_sandbox_mode(True) DILARANG — menyebabkan positionRisk path invalid (-5000)
    """
    secrets = loadSecrets()

    if testnet:
        apiKey = secrets.get("BINANCE_TESTNET_KEY", "")
        apiSecret = secrets.get("BINANCE_TESTNET_SECRET", "")
    else:
        apiKey = secrets.get("BINANCE_API_KEY", "")
        apiSecret = secrets.get("BINANCE_API_SECRET", "")

    exchange = ccxt.binanceusdm(
        {
            "apiKey": apiKey,
            "secret": apiSecret,
            "options": {"defaultType": "future"},
            "recvWindow": 60000,
            "adjustForTimeDifference": True,
        }
    )

    if testnet:
        # urls["test"] berisi dict testnet yang sudah built-in di ccxt:
        # fapiPublic, fapiPrivate, fapiPrivateV2, dll → testnet.binancefuture.com
        # Assign dict (bukan string) agar semua endpoint lookup tetap bekerja.
        exchange.urls["api"] = exchange.urls["test"]
        # apiBackup signals ccxt that this is sandbox → skip sapi (no testnet URL)
        exchange.urls["apiBackup"] = exchange.urls["test"]

    return exchange
