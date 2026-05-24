"""Position tracking and reconciliation."""

import logging
from typing import Any

import ccxt

logger = logging.getLogger(__name__)


def fetchOpenPositions(futuresExchange: ccxt.binanceusdm) -> list[dict[str, Any]]:
    """
    GET /fapi/v2/positionRisk via fapiPrivateV2GetPositionRisk().
    Filter: positionAmt != 0.
    """
    try:
        positions = futuresExchange.fapiPrivateV2GetPositionRisk()
        return [p for p in positions if float(p.get("info", {}).get("positionAmt", 0)) != 0]
    except ccxt.BaseError as e:
        logger.error(f"Failed to fetch open positions: {e}")
        return []


def reconcilePositions(
    openPositions: list[dict[str, Any]],
    tradeLog: list[dict[str, Any]],
) -> list[str]:
    """
    Compare API positions vs trade log entries without exit_time.
    Return list of discrepancy messages.
    """
    discrepancies: list[str] = []
    apiSymbols = {p.get("info", {}).get("symbol") for p in openPositions}
    logSymbols = {r.get("symbol") for r in tradeLog if not r.get("exit_time")}

    for sym in apiSymbols - logSymbols:
        msg = f"Position {sym} in API but not in trade log"
        logger.warning(msg)
        discrepancies.append(msg)

    for sym in logSymbols - apiSymbols:
        msg = f"Position {sym} in trade log but not in API"
        logger.warning(msg)
        discrepancies.append(msg)

    return discrepancies
