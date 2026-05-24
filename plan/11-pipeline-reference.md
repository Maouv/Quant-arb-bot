# 11 — PIPELINE REFERENCE

Diagram visual bot cycle. Setiap 5 menit, clock-aligned UTC.

---

## Cycle Flow

```
┌─────────────────────────────────────────────────────────┐
│ STEP 0 — SAFETY                                         │
│  isBlackoutWindow()? → skip ENTRY (exit tetap jalan)    │
│  isBroadMarketStress()? → skip ALL entry                │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 1 — FETCH (batch, 1 call each, semua coins)        │
│  GET /fapi/v1/premiumIndex     → FR, markPrice, next    │
│  GET /fapi/v1/ticker/bookTicker → bid/ask futures       │
│  GET /api/v3/ticker/bookTicker  → bid/ask spot          │
│  GET /fapi/v2/positionRisk      → open positions        │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 2 — MONITOR POSITIONS (selalu jalan)               │
│  For each open position:                                │
│    |FR| < 0.02%  → exitNormal (limit, timeout 60s)      │
│    FR flip sign  → exitEmergency (market, immediate)    │
│  After exits → quick orphan check                       │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 3 — FIND OPPORTUNITIES                             │
│  Skip kalau: 6 slot penuh / blackout / broad stress     │
│                                                         │
│  filterCandidates():                                    │
│    |FR| >= 0.05%                                        │
│    bukan EXCLUDED / suspended                           │
│    quick spread check: net > MIN_PROFIT_THRESHOLD       │
│                                                         │
│  For each candidate (typical 2-5 coins):                │
│    fetchDepth (spot + futures, limit=20)                 │
│    estimateSlippage($150 position)                      │
│    calculateTotalRtCost()                               │
│    Filters:                                             │
│      net_expected > 0.01% (strict >)                    │
│      isCostSpike() == False                             │
│      isBasisTooHigh() == False (basis <= 0.05%)         │
│                                                         │
│  Sort: net_expected desc, tie-break alphabetical        │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 4 — EXECUTE ENTRY                                  │
│  For each winner (up to available slots):               │
│    calculateQuantity(markPrice, sizePerPair, minNot)    │
│    placeEntryOrders(spot LIMIT + futures LIMIT, mid)    │
│    pollOrderFill(5s interval, 60s timeout)              │
│                                                         │
│    IF both fill:                                        │
│      placeStopLoss (algo, MARK_PRICE, triggerPrice)     │
│      placeTakeProfit (algo, MARK_PRICE, triggerPrice)   │
│      appendTradeRecord (entry, exit_time=null)          │
│      costCache.update(symbol, actualCost)               │
│                                                         │
│    IF partial fill (one leg timeout):                   │
│      cancel both orders                                 │
│      close filled leg with MARKET order                 │
│      log "partial_fill_failed"                          │
│      DO NOT place SL/TP                                 │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ STEP 5 — ORPHAN CHECK                                   │
│  GET /fapi/v1/openOrders       → regular futures orders │
│  GET /api/v3/openOrders        → regular spot orders    │
│  GET /fapi/v1/openAlgoOrders   → algo orders (SL/TP)   │
│                                                         │
│  Order tanpa posisi → cancel                            │
│  Posisi tanpa SL/TP → place emergency SL immediately    │
│  Futures closed + spot open → manipulation:             │
│    close spot MARKET, suspend coin 3 cycles, log        │
└──────────────────────────┬──────────────────────────────┘
                           ↓
┌─────────────────────────────────────────────────────────┐
│ HOUSEKEEPING                                            │
│  shouldRefreshBalance()? → recompute sizePerPair        │
│  costCache.save()                                       │
│  decrement suspendedSymbols counters                    │
│  log cycle summary                                      │
└──────────────────────────┬──────────────────────────────┘
                           ↓
              waitForNextCycle() → sleep sampai :00/:05/:10/...
              ↓
              LOOP ke STEP 0
```

---

## Startup Flow (sekali, sebelum cycle pertama)

```
┌─────────────────────────────────────────────────────────┐
│ 1. loadSecrets()                                        │
│ 2. Assert USE_TESTNET or CONFIRM_MAINNET                │
│ 3. createSpotExchange() + createFuturesExchange()       │
│ 4. fetchFuturesBalance() → computeSizePerPair()         │
│ 5. GET /fapi/v1/exchangeInfo → cache MIN_NOTIONAL       │
│ 6. validateUniverse() → filter active + 8h interval     │
│ 7. fetchOpenPositions() → reconcile vs trade log        │
│ 8. checkUnprotectedPositions() → place emergency SL     │
│ 9. Log downtime (if restart)                            │
│ 10. waitForNextCycle() → align to clock boundary        │
└──────────────────────────┬──────────────────────────────┘
                           ↓
                    Enter cycle loop
```

---

## Key Rules (quick reference)

- Exit SELALU diproses — blackout/stress hanya block entry
- Entry langsung saat signal — tidak tunggu settlement
- Depth hanya untuk candidates, bukan semua 100 coins
- SL/TP via raw requests (algo order) — bukan ccxt
- `sizePerPair = effectiveBalance / MAX_PAIRS` — SELALU, tidak re-allocate
- Idle capital stays idle — tidak distribute ke fewer pairs
- Bot TIDAK BOLEH crash — semua error → log → continue
