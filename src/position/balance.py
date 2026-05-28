"""Balance fetching and position sizing."""

import logging
from datetime import UTC, datetime, timedelta

import ccxt

from src.config.settings import BALANCE_REFRESH_INTERVAL, BUFFER_RATIO, MAX_PAIRS

logger = logging.getLogger(__name__)


def fetchSpotBalance(spotExchange: ccxt.binance, asset: str) -> float:
    """Fetch free balance of `asset` on spot exchange."""
    try:
        balance: dict[str, object] = spotExchange.fetch_balance()
        free: dict[str, object] = balance.get("free", {})  # type: ignore[assignment]
        return float(str(free.get(asset, 0.0)))
    except ccxt.BaseError as e:
        logger.error("Failed to fetch spot balance for %s: %s", asset, e)
        return 0.0


def fetchFuturesBalance(futuresExchange: ccxt.binanceusdm) -> float:
    """GET /fapi/v2/balance → find USDT → return availableBalance."""
    try:
        balances = futuresExchange.fapiPrivateV2GetBalance()
        for bal in balances:
            if bal.get("asset") == "USDT":
                return float(bal.get("availableBalance", 0))
        return 0.0
    except ccxt.BaseError as e:
        logger.error(f"Failed to fetch futures balance: {e}")
        return 0.0


def computeSizePerPair(availableBalance: float) -> float:
    """effectiveCapital / MAX_PAIRS with buffer applied."""
    effectiveCapital = availableBalance * (1 - BUFFER_RATIO)
    return effectiveCapital / MAX_PAIRS


def shouldRefreshBalance(lastRefresh: datetime) -> bool:
    """True if > BALANCE_REFRESH_INTERVAL since lastRefresh."""
    return datetime.now(UTC) - lastRefresh > timedelta(seconds=BALANCE_REFRESH_INTERVAL)
