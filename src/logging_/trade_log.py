"""Append-only JSON-lines trade log."""

import json
import logging
import uuid
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)


def appendTradeRecord(record: dict[str, object], filepath: str = "logs/trades.jsonl") -> None:
    """Append satu JSON line ke trade log. Tidak overwrite."""
    Path(filepath).parent.mkdir(parents=True, exist_ok=True)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")
    logger.debug("Trade record appended: trade_id=%s", record.get("trade_id"))


def loadTradeLog(filepath: str = "logs/trades.jsonl") -> list[dict[str, object]]:
    """Load semua records dari JSON-lines file. Return [] kalau file tidak ada."""
    path = Path(filepath)
    if not path.exists():
        return []
    with open(filepath, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def buildTradeRecord(
    symbol: str, side: str, entryTime: str, exitTime: str,
    entryFr: float, exitFr: float, holdSettlements: int,
    grossPct: float, costRtPct: float, netPct: float, netDollar: float,
    fillTimeSpotMs: int, fillTimeFuturesMs: int,
    actualFillPriceSpot: float, actualFillPriceFutures: float,
    slippageSpotPct: float, slippageFuturesPct: float,
    partialFillOccurred: bool,
) -> dict[str, object]:
    """
    Construct trade record dict dengan trade_id (UUID) dan timestamp ISO8601 UTC.
    Fields sesuai spec: trade_id, symbol, side, entry_time, exit_time,
    entry_fr, exit_fr, hold_settlements, gross_pct, cost_rt_pct, net_pct,
    net_dollar, fill_time_spot_ms, fill_time_futures_ms,
    actual_fill_price_spot, actual_fill_price_futures,
    slippage_spot_pct, slippage_futures_pct, partial_fill_occurred.
    """
    return {
        "trade_id": str(uuid.uuid4()),
        "timestamp": datetime.now(UTC).isoformat(),
        "symbol": symbol, "side": side,
        "entry_time": entryTime, "exit_time": exitTime,
        "entry_fr": entryFr, "exit_fr": exitFr,
        "hold_settlements": holdSettlements,
        "gross_pct": grossPct, "cost_rt_pct": costRtPct,
        "net_pct": netPct, "net_dollar": netDollar,
        "fill_time_spot_ms": fillTimeSpotMs, "fill_time_futures_ms": fillTimeFuturesMs,
        "actual_fill_price_spot": actualFillPriceSpot,
        "actual_fill_price_futures": actualFillPriceFutures,
        "slippage_spot_pct": slippageSpotPct, "slippage_futures_pct": slippageFuturesPct,
        "partial_fill_occurred": partialFillOccurred,
    }
