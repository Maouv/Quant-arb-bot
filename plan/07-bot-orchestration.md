# 07 — BOT ORCHESTRATION

---

## bot/main.py (~30 lines)

```python
def main() -> None:
    """
    Entrypoint:
    1. configureLogging()
    2. botState = runStartupSequence()
    3. loop forever:
       a. runCycle(botState)
       b. waitForNextCycle()
    
    Ctrl+C → graceful shutdown (log, save cost cache).
    """
```

Run: `python -m bot.main`

---

## bot/startup.py (~80 lines)

```python
def runStartupSequence() -> dict:
    """
    1. loadSecrets()
    2. Assert USE_TESTNET or CONFIRM_MAINNET
       → if not USE_TESTNET: assert CONFIRM_MAINNET
    3. createSpotExchange() + createFuturesExchange()
    4. fetchFuturesBalance() → computeSizePerPair()
    5. Fetch exchangeInfo → extract MIN_NOTIONAL per symbol, cache in memory
    6. validateUniverse() → filter active symbols
    7. fetchOpenPositions() → reconcilePositions()
    8. checkUnprotectedPositions() → place emergency SL
    9. Log downtime duration (compare last log timestamp vs now)
    10. Return botState dict
    """

def validateUniverse(futuresExchange, universe: list[str]) -> list[str]:
    """
    Per symbol:
    1. exchangeInfo status == "TRADING" → else exclude + log
    2. Fetch 2 last funding records, hitung gap
       gap < 7 hours → interval berubah ke 4h → exclude + log WARNING
    
    Return: list of valid symbols.
    """

def waitForNextCycle(intervalMinutes: int = 5) -> None:
    """
    Clock-aligned:
    secondsToWait = (interval - now.minute % interval) * 60 - now.second
    if secondsToWait < 5: secondsToWait += interval * 60
    time.sleep(secondsToWait)
    """
```

Mainnet guard:
```python
if not USE_TESTNET:
    assert CONFIRM_MAINNET, "Set CONFIRM_MAINNET=True setelah review manual"
```

---

## bot/cycle.py (~100 lines)

```python
def runCycle(botState: dict) -> None:
    """
    STEP 0 — SAFETY
      isBlackoutWindow()? → skip entry, monitoring tetap
      isBroadMarketStress()? → skip all entry

    STEP 1 — FETCH (batch, 1 call each)
      fetchPremiumIndex()
      fetchBookTickerFutures()
      fetchBookTickerSpot()
      fetchOpenPositions()

    STEP 2 — MONITOR POSITIONS
      For each open position:
        FR < EXIT_THRESHOLD → exitNormal()
        FR flip sign → exitEmergency()
      After exits: orphan check

    STEP 3 — FIND OPPORTUNITIES (skip kalau slot penuh)
      filterCandidates()
      For each candidate:
        fetchDepth() (spot + futures)
        estimateSlippage()
        calculateTotalRtCost()
        net_expected > MIN_PROFIT_THRESHOLD? (strict >)
        isCostSpike()? → skip
        isBasisTooHigh()? → skip

    STEP 4 — EXECUTE ENTRY
      calculateQuantity()
      placeEntryOrders() (spot + futures limit, mid price)
      pollOrderFill() (both legs, 5s interval, 60s timeout)
      Partial fill? → handlePartialFill()
      Both fill? → placeStopLoss() + placeTakeProfit()
      appendTradeRecord() (entry only, exit_time null)
      costCache.update()

    STEP 5 — ORPHAN CHECK
      checkOrphanRegularOrders() → cancel
      checkOrphanAlgoOrders() → cancel
      checkUnprotectedPositions() → place emergency SL
      handleManipulationEvent() if detected

    Balance refresh if shouldRefreshBalance()
    costCache.save()
    """
```

---

## Bot State (in-memory, passed between cycles)

```python
botState = {
    "spotExchange": ccxt.binance,
    "futuresExchange": ccxt.binanceusdm,
    "validUniverse": list[str],
    "minNotionals": dict[str, float],
    "sizePerPair": float,
    "availableBalance": float,
    "lastBalanceRefresh": datetime,
    "costCache": CostCache,
    "openPositions": list[dict],
    "suspendedSymbols": dict[str, int],   # symbol → cycles remaining
    "cycleCount": int,
    "apiKey": str,
    "apiSecret": str,
    "baseUrl": str,                        # futures base URL (testnet/prod)
}
```

---

## Error Handling

```python
# Setiap API call:
try:
    result = exchange.someCall()
except ccxt.NetworkError as e:
    logger.error(f"Network: {e}")
    # skip, retry next cycle
except ccxt.ExchangeError as e:
    logger.error(f"Exchange: {e}")
    # log, skip
except Exception as e:
    logger.critical(f"Unexpected: {e}", exc_info=True)
    # log traceback, continue
```

Bot TIDAK BOLEH crash. Semua error → log → continue next cycle.

---

## Restart Protocol

Handled by `runStartupSequence()`:
1. Check open positions
2. Verify SL/TP — place emergency SL kalau missing
3. Reconcile trade log vs actual positions
4. Log downtime duration + reason
