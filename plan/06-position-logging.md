# 06 — POSITION & LOGGING

---

## position/tracker.py (~60 lines)

```python
def fetchOpenPositions(futuresExchange) -> list[dict]:
    """
    GET /fapi/v2/positionRisk via fapiPrivateV2GetPositionRisk()
    
    BUKAN /fapi/v1/ — v1 return -5000 di testnet.
    
    Filter: positionAmt != 0
    Return raw dicts. Symbol format: pos['info']['symbol'] = "ETHUSDT"
    """

def reconcilePositions(openPositions: list[dict],
                       tradeLog: list[dict]) -> list[str]:
    """
    Compare API positions vs trade log entries tanpa exit_time.
    Return list of discrepancy messages.
    Log WARNING per discrepancy.
    """
```

---

## position/orphan_checker.py (~70 lines)

```python
def checkOrphanRegularOrders(futuresExchange, spotExchange,
                             openPositions: list[dict]) -> list[dict]:
    """
    GET /fapi/v1/openOrders + GET /api/v3/openOrders
    Order yang symbol-nya tidak ada di openPositions → orphan.
    Return list of orders to cancel.
    """

def checkOrphanAlgoOrders(openAlgoOrders: list[dict],
                          openPositions: list[dict]) -> list[dict]:
    """
    Algo order yang symbol-nya tidak ada di openPositions → orphan.
    Return list of algo orders to cancel (by algoId).
    """

def checkUnprotectedPositions(openPositions: list[dict],
                              openAlgoOrders: list[dict]) -> list[dict]:
    """
    Posisi yang tidak punya SL/TP di openAlgoOrders → unprotected.
    Return list of positions needing emergency SL.
    """

def handleManipulationEvent(symbol: str, spotExchange,
                            futuresExchange, suspendedSymbols: dict) -> None:
    """
    Futures closed tapi spot masih open:
    1. Close spot MARKET immediately
    2. Log manipulation_event
    3. Suspend coin 3 cycles (add to suspendedSymbols)
    
    Monitor: >10% trades satu coin = manipulation → suspend lebih lama.
    """
```

---

## position/balance.py (~40 lines)

```python
def fetchFuturesBalance(futuresExchange) -> float:
    """
    GET /fapi/v2/balance → find USDT → return float(availableBalance)
    """

def computeSizePerPair(availableBalance: float) -> float:
    """
    effectiveCapital = availableBalance * (1 - BUFFER_RATIO)
    sizePerPair = effectiveCapital / MAX_PAIRS
    
    ⚠️ WAJIB pakai availableBalance dari API.
    JANGAN pakai TOTAL_CAPITAL dari config (itu hanya referensi dokumentasi).
    TIDAK re-allocate kalau < 6 slot terisi. Sisa IDLE.
    """

def shouldRefreshBalance(lastRefresh: datetime) -> bool:
    """True kalau > BALANCE_REFRESH_INTERVAL sejak lastRefresh."""
```

---

## logging_/setup.py (~30 lines)

```python
def configureLogging(logDir: str = "logs") -> logging.Logger:
    """
    - File handler: logs/bot.log (rotating, 10MB, 5 backups)
    - Console handler: INFO level
    - Format: "2026-05-24T06:00:00Z [INFO] module — message"
    """
```

---

## logging_/trade_log.py (~50 lines)

```python
def appendTradeRecord(record: dict, filepath: str = "logs/trades.jsonl") -> None:
    """Append satu JSON line. Jangan overwrite."""

def loadTradeLog(filepath: str = "logs/trades.jsonl") -> list[dict]:
    """Load semua records dari JSON-lines file."""

def buildTradeRecord(symbol: str, side: str, entryTime: str, exitTime: str,
                     entryFr: float, exitFr: float, holdSettlements: int,
                     grossPct: float, costRtPct: float, netPct: float,
                     netDollar: float, fillTimeSpotMs: int,
                     fillTimeFuturesMs: int, actualFillPriceSpot: float,
                     actualFillPriceFutures: float, slippageSpotPct: float,
                     slippageFuturesPct: float,
                     partialFillOccurred: bool) -> dict:
    """
    Construct trade record dict.
    Tambah: trade_id (UUID), timestamp ISO8601 UTC.
    """
```

Trade log fields (dari 02-requirements):
```
trade_id, symbol, side,
entry_time, exit_time,
entry_fr, exit_fr,
hold_settlements,
gross_pct, cost_rt_pct, net_pct, net_dollar,
fill_time_spot_ms, fill_time_futures_ms,
actual_fill_price_spot, actual_fill_price_futures,
slippage_spot_pct, slippage_futures_pct,
partial_fill_occurred
```
