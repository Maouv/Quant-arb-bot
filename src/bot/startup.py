"""Bot startup sequence — run once before cycle loop."""

import logging
import time
from datetime import UTC, datetime

import ccxt

from src.config.secrets import loadSecrets
from src.config.settings import CONFIRM_MAINNET, USE_TESTNET
from src.exchange.endpoints import BASE_FUTURES, BASE_TESTNET_FUTURES
from src.exchange.factory import createFuturesExchange, createSpotExchange
from src.execution.algo_order import listOpenAlgoOrders
from src.logging_.trade_log import loadTradeLog
from src.market.cost_cache import CostCache
from src.position.balance import computeSizePerPair, fetchFuturesBalance
from src.position.orphan_checker import checkUnprotectedPositions
from src.position.tracker import fetchOpenPositions, reconcilePositions

logger = logging.getLogger(__name__)


def runStartupSequence() -> dict[str, object]:
    """
    1. loadSecrets()  2. Assert testnet/mainnet guard
    3. Create exchanges  4. Fetch balance → sizePerPair
    5. Fetch exchangeInfo → minNotionals  6. validateUniverse()
    7. fetchOpenPositions() → reconcile  8. checkUnprotectedPositions()
    9. Log downtime  10. Return botState dict.
    """
    secrets = loadSecrets()
    if not USE_TESTNET:
        assert CONFIRM_MAINNET, "Set CONFIRM_MAINNET=True setelah review manual"

    spotExchange = createSpotExchange(testnet=USE_TESTNET)
    futuresExchange = createFuturesExchange(testnet=USE_TESTNET)
    availableBalance = fetchFuturesBalance(futuresExchange)
    sizePerPair = computeSizePerPair(availableBalance)
    minNotionals = _fetchMinNotionals(futuresExchange)
    validUniverse = validateUniverse(futuresExchange, _loadUniverse())

    openPositions = fetchOpenPositions(futuresExchange)
    discrepancies = reconcilePositions(openPositions, loadTradeLog())
    if discrepancies:
        logger.warning("Startup reconcile: %d discrepancies", len(discrepancies))

    baseUrl = BASE_TESTNET_FUTURES if USE_TESTNET else BASE_FUTURES
    keyName = "BINANCE_TESTNET_KEY" if USE_TESTNET else "BINANCE_API_KEY"
    secretName = "BINANCE_TESTNET_SECRET" if USE_TESTNET else "BINANCE_API_SECRET"
    apiKey = str(secrets.get(keyName, ""))
    apiSecret = str(secrets.get(secretName, ""))

    algoOrders = listOpenAlgoOrders(baseUrl, apiKey, apiSecret)
    unprotected = checkUnprotectedPositions(openPositions, algoOrders)
    if unprotected:
        logger.warning("Startup: %d unprotected positions", len(unprotected))

    logger.info(
        "Startup complete: balance=%.2f sizePerPair=%.2f universe=%d",
        availableBalance, sizePerPair, len(validUniverse),
    )
    return {
        "spotExchange": spotExchange, "futuresExchange": futuresExchange,
        "validUniverse": validUniverse, "minNotionals": minNotionals,
        "sizePerPair": sizePerPair, "availableBalance": availableBalance,
        "lastBalanceRefresh": datetime.now(UTC), "costCache": CostCache(),
        "openPositions": openPositions, "suspendedSymbols": {},
        "cycleCount": 0, "apiKey": apiKey, "apiSecret": apiSecret, "baseUrl": baseUrl,
    }


def validateUniverse(futuresExchange: object, universe: list[str]) -> list[str]:
    """
    Filter symbols: status == TRADING.
    gap < 7h → kemungkinan 4h interval → exclude + log WARNING.
    """
    try:
        info = futuresExchange.fapiPublicGetExchangeInfo()  # type: ignore[attr-defined]
    except ccxt.BaseError as exc:
        logger.error("validateUniverse exchangeInfo failed: %s", exc)
        return universe
    tradingSymbols = {s["symbol"] for s in info.get("symbols", []) if s.get("status") == "TRADING"}
    valid: list[str] = []
    for symbol in universe:
        if symbol not in tradingSymbols:
            logger.warning("Universe exclude (not TRADING): %s", symbol)
            continue
        valid.append(symbol)
    return valid


def waitForNextCycle(intervalMinutes: int = 5) -> None:
    """Clock-aligned sleep. Skip kalau < 5s ke boundary."""
    now = datetime.now(UTC)
    secondsToWait = (intervalMinutes - now.minute % intervalMinutes) * 60 - now.second
    if secondsToWait < 5:
        secondsToWait += intervalMinutes * 60
    logger.debug("Waiting %ss for next cycle", secondsToWait)
    time.sleep(secondsToWait)


def _fetchMinNotionals(futuresExchange: object) -> dict[str, float]:
    """Fetch exchangeInfo dan extract MIN_NOTIONAL per symbol."""
    try:
        info = futuresExchange.fapiPublicGetExchangeInfo()  # type: ignore[attr-defined]
    except ccxt.BaseError as exc:
        logger.error("fetchMinNotionals failed: %s", exc)
        return {}
    result: dict[str, float] = {}
    for sym in info.get("symbols", []):
        for f in sym.get("filters", []):
            if f.get("filterType") == "MIN_NOTIONAL":
                result[sym["symbol"]] = float(f.get("notional", 0))
    return result


def _loadUniverse() -> list[str]:
    """Load UNIVERSE_8H from config."""
    from src.config.universe import UNIVERSE_8H
    return list(UNIVERSE_8H)
