"""
Position tests — Part A: pure logic (no API), Part B: testnet lifecycle.
Run all:    pytest tests/test_position.py -v
Run unit:   pytest tests/test_position.py -v -m "not integration"
Run live:   pytest tests/test_position.py -v -m integration
"""

import os

import pytest
import requests
from dotenv import load_dotenv

from src.position.orphan_checker import checkOrphanAlgoOrders, checkUnprotectedPositions
from src.position.tracker import reconcilePositions

load_dotenv(os.path.expanduser("~/.secret/quant-arb-bot/.env"))

_API_KEY = os.getenv("BINANCE_TESTNET_KEY", "")
_API_SECRET = os.getenv("BINANCE_TESTNET_SECRET", "")
_BASE_URL = "https://testnet.binancefuture.com"
_CCXT_SYMBOL = "BTC/USDT:USDT"

_REQUIRES_CREDS = pytest.mark.skipif(
    not _API_KEY or not _API_SECRET,
    reason="BINANCE_TESTNET_KEY / BINANCE_TESTNET_SECRET not set",
)

# ── Part A: pure logic ─────────────────────────────────────────────────────────

def _makePosition(symbol: str) -> dict[str, object]:
    """Build minimal ccxt-style position dict."""
    return {"info": {"symbol": symbol, "positionAmt": "1.0"}}


def test_reconcilePositions_match() -> None:
    """API and log match → no discrepancies."""
    positions = [_makePosition("BTCUSDT")]
    tradeLog = [{"symbol": "BTCUSDT", "exit_time": None}]
    assert reconcilePositions(positions, tradeLog) == []


def test_reconcilePositions_api_extra() -> None:
    """API has position not in log → discrepancy detected."""
    positions = [_makePosition("BTCUSDT")]
    discrepancies = reconcilePositions(positions, [])
    assert any("BTCUSDT" in d for d in discrepancies)


def test_reconcilePositions_log_extra() -> None:
    """Log has open trade not in API → discrepancy detected."""
    tradeLog = [{"symbol": "ETHUSDT", "exit_time": None}]
    discrepancies = reconcilePositions([], tradeLog)
    assert any("ETHUSDT" in d for d in discrepancies)


def test_reconcilePositions_closed_log_ignored() -> None:
    """Closed trade log entries (exit_time set) are not checked."""
    tradeLog = [{"symbol": "ETHUSDT", "exit_time": "2026-01-01T00:00:00Z"}]
    assert reconcilePositions([], tradeLog) == []


def test_checkOrphanAlgoOrders_no_orphan() -> None:
    """Algo orders match open positions → no orphan."""
    positions = [_makePosition("BTCUSDT")]
    algoOrders = [{"symbol": "BTCUSDT", "algoId": 1}]
    assert checkOrphanAlgoOrders(algoOrders, positions) == []


def test_checkOrphanAlgoOrders_detects_orphan() -> None:
    """Algo order for symbol with no position → orphan."""
    positions = [_makePosition("ETHUSDT")]
    algoOrders = [{"symbol": "BTCUSDT", "algoId": 1}]
    orphans = checkOrphanAlgoOrders(algoOrders, positions)
    assert len(orphans) == 1
    assert orphans[0]["symbol"] == "BTCUSDT"


def test_checkUnprotectedPositions_protected() -> None:
    """Position has SL/TP algo order → not unprotected."""
    positions = [_makePosition("BTCUSDT")]
    algoOrders = [{"symbol": "BTCUSDT", "algoId": 1}]
    assert checkUnprotectedPositions(positions, algoOrders) == []


def test_checkUnprotectedPositions_unprotected() -> None:
    """Position has no algo order → flagged as unprotected."""
    positions = [_makePosition("BTCUSDT")]
    unprotected = checkUnprotectedPositions(positions, [])
    assert len(unprotected) == 1


def test_checkUnprotectedPositions_empty() -> None:
    """No open positions → nothing to protect."""
    assert checkUnprotectedPositions([], []) == []


# ── Part B: testnet lifecycle ──────────────────────────────────────────────────

def _markPrice() -> float:
    """Fetch BTC mark price from testnet."""
    resp = requests.get(
        f"{_BASE_URL}/fapi/v1/premiumIndex", params={"symbol": "BTCUSDT"}, timeout=5
    )
    resp.raise_for_status()
    return float(resp.json()["markPrice"])


@pytest.mark.integration
@_REQUIRES_CREDS
def test_fetchOpenPositions_returns_list() -> None:
    """fetchOpenPositions returns list — may be empty on clean testnet."""
    from src.exchange.factory import createFuturesExchange
    from src.position.tracker import fetchOpenPositions
    exchange = createFuturesExchange(testnet=True)
    positions = fetchOpenPositions(exchange)
    assert isinstance(positions, list)
    for pos in positions:
        assert "info" in pos
        amt = float(pos["info"].get("positionAmt", "0"))
        assert amt != 0.0


@pytest.mark.integration
@_REQUIRES_CREDS
def test_openClosePosition_lifecycle() -> None:
    """Open a small BTC long position → verify it appears → close it → verify gone."""
    from src.exchange.factory import createFuturesExchange
    from src.position.tracker import fetchOpenPositions

    exchange = createFuturesExchange(testnet=True)
    price = _markPrice()
    qty = round(60.0 / price, 3)  # ~$60, safely above $50 min notional

    # Open position
    exchange.create_market_order(_CCXT_SYMBOL, "buy", qty)

    positions = fetchOpenPositions(exchange)
    btcPos = [p for p in positions if p["info"].get("symbol") == "BTCUSDT"]
    assert len(btcPos) > 0, "Position not found after market buy"

    # Close position
    exchange.create_market_order(
        _CCXT_SYMBOL, "sell", qty, params={"reduceOnly": True}
    )

    positionsAfter = fetchOpenPositions(exchange)
    btcPosAfter = [p for p in positionsAfter if p["info"].get("symbol") == "BTCUSDT"]
    assert len(btcPosAfter) == 0, "Position still open after market sell"


@pytest.mark.integration
@_REQUIRES_CREDS
def test_reconcilePositions_live_empty_log() -> None:
    """Live positions vs empty trade log → any open position is flagged."""
    from src.exchange.factory import createFuturesExchange
    from src.position.tracker import fetchOpenPositions

    exchange = createFuturesExchange(testnet=True)
    positions = fetchOpenPositions(exchange)
    discrepancies = reconcilePositions(positions, [])
    assert len(discrepancies) == len(positions)
