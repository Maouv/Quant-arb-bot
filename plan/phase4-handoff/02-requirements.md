# PHASE 4 HANDOFF — 02: REQUIREMENTS
**Date:** 23 May 2026

---

## TUJUAN PHASE 4

Bukan profit. Validate 3 hal yang tidak bisa divalidasi di backtest:
1. Fill rate actual per coin (backtest assume 100%)
2. Cost actual per coin real-time (backtest pakai flat tier)
3. Bot execution correctness (orphan orders, timing, race conditions)

Minimum durasi: 4–6 minggu non-stop.

---

## CODING STANDARDS

Python 3.12, PEP8, camelCase variabel/fungsi, PascalCase class, type hints wajib,
docstring wajib, max 30 baris per fungsi, semua parameter di config.py,
tidak ada bare `except:`, tidak ada `print()` — pakai logging.

---

## REPO STRUCTURE

Buat repo baru `quant-arb-bot`. TERPISAH dari `/root/quant-arb/`.

```
quant-arb-bot/
├── config/
│   ├── config.py           # semua parameter
│   └── secrets.env         # API keys — JANGAN di-commit ke git
├── bot/
│   ├── main.py             # entrypoint, clock-aligned cycle loop
│   ├── scanner.py          # scan FR, hitung net_expected
│   ├── executor.py         # place/cancel orders, verify fills
│   ├── position_manager.py # monitor posisi open, orphan check
│   └── risk_guard.py       # pre-entry checks, cost spike guard
├── data/
│   └── cost_cache.py       # rolling average cost per coin
├── logs/
│   └── .gitkeep
├── tests/
│   ├── test_connectivity.py
│   └── test_executor.py
├── .gitignore              # wajib: secrets.env, logs/, __pycache__/
└── requirements.txt        # ccxt==4.2.86 (LOCKED), requests, python-dotenv
```

---

## CONFIG — SEMUA NILAI WAJIB ADA

```python
# --- Mode ---
USE_TESTNET: bool = True        # False hanya saat Phase 5
CONFIRM_MAINNET: bool = False   # Wajib True sebelum Phase 5

# API keys diload dari secrets.env, BUKAN hardcode

# --- Universe ---
EXCLUDED_SYMBOLS: list[str] = ["NEARUSDT"]  # permanen, Phase 0

# --- Strategy (LOCKED) ---
ENTRY_THRESHOLD: float = 0.05   # % |FR| >= ini → entry signal
EXIT_THRESHOLD: float  = 0.02   # % |FR| < ini → exit signal

# --- Portfolio (LOCKED) ---
TOTAL_CAPITAL: float  = 3000.0  # referensi — actual balance di-fetch dari API
BUFFER_RATIO: float   = 0.40
MAX_PAIRS: int        = 6
# effectiveCapital = getAvailableBalance() * (1 - BUFFER_RATIO)
# sizePerPair      = effectiveCapital / MAX_PAIRS  — TIDAK di-hardcode

# --- Execution ---
ORDER_TIMEOUT_SECONDS: int      = 60
CYCLE_INTERVAL_MINUTES: int     = 5
BLACKOUT_MINUTES: int           = 5        # pre-settlement, ENTRY only
SETTLEMENT_HOURS_UTC: list[int] = [0, 8, 16]

# --- Cost model ---
# Cost selalu real-time dari orderbook — bukan flat tier
# isCostSpike/isBroadMarketStress pakai rolling average dari cost_cache
DEFAULT_COST_TIER: float      = 0.12   # fallback sebelum rolling avg terbentuk
COST_SPIKE_MULTIPLIER: float  = 3.0
BROAD_STRESS_THRESHOLD: float = 0.50
MIN_PROFIT_THRESHOLD: float   = 0.01   # % — threshold lebih tinggi mengurangi net dollar

# --- Fees ---
TAKER_FEE: float = 0.04
FEE_RT: float    = 0.08   # 2 × taker_fee

# --- Rejection criteria ---
PAPER_APY_ABSOLUTE_FLOOR: float = 13.2   # Phase 2 floor
PAPER_APY_RELATIVE_FLOOR: float = 0.50   # 50% dari backtest
BACKTEST_APY_MID: float         = 28.0   # dari Phase 3 results_v2
```

---

## UNIVERSE

108 coins 8h interval, no volume filter. Criteria:
```
1. Ada spot USDT + perpetual futures USDT-margined di Binance
2. Funding interval 8 jam (verify saat startup)
3. Bukan stablecoin / wrapped token
4. Bukan NEARUSDT
```

`fundingIntervalHours` tidak tersedia di API — tidak bisa di-fetch dynamically.
Universe di-hardcode di config.py sebagai `UNIVERSE_8H` (list 108 symbols).

Saat startup, filter dengan dua checks:
1. `exchangeInfo` status = "TRADING" → exclude delist/suspend
2. Interval check: fetch 2 last funding records per coin, hitung gap.
   Kalau gap < 7 jam → interval berubah ke 4h, exclude + log WARNING.
   (MTLUSDT/SOLUSDT/XVGUSDT pernah berubah interval secara historical — sudah 8h lagi sekarang)

Volume filter di-drop (look-ahead bias, redundant dengan dynamic cost filter).
⚠️ Dynamic cost filter HARUS bekerja benar — kalau ada bug, bot bisa entry ke coins illiquid.

Test wajib:
- Verify coins dengan spread > 0.5% tidak pernah ter-entry
- Verify log menunjukkan coins illiquid di-skip dengan alasan "net_expected < threshold"

Expand ke 4h coins = Phase 5 territory.

---

## ACTUAL COST LOGGING

Setelah setiap trade closed, hitung dan log actual RT cost:

```python
actual_cost_rt_pct = (
    abs(actual_fill_price_spot - mid_price_spot_at_order) / mid_price_spot_at_order
    + abs(actual_fill_price_futures - mid_price_futures_at_order) / mid_price_futures_at_order
    + TAKER_FEE * 4   # spot entry, spot exit, futures entry, futures exit
) * 100
```

Di mana `mid_price = (bid + ask) / 2` saat order di-place. Simpan mid price saat order dikirim.

Validasi di akhir Phase 4:
```
actual_cost_avg = mean(actual_cost_rt_pct) semua trades
< 0.12% → backtest conservative ✅
> 0.12% → backtest optimistic ⚠️ → update cost assumption sebelum Phase 5
```

---

## DATA FETCH PER CYCLE

**Batch (semua coins, 1 call masing-masing):**
```
GET /fapi/v1/premiumIndex      → lastFundingRate, markPrice, nextFundingTime
GET /fapi/v1/ticker/bookTicker → bid/ask futures
GET /api/v3/ticker/bookTicker  → bid/ask spot
GET /fapi/v1/positionRisk      → open positions
GET /fapi/v1/openOrders        → open regular futures orders
GET /fapi/v1/algo/orders/open  → open algo orders (SL/TP)
GET /api/v3/openOrders         → open spot orders
```

**Per kandidat (hanya coins yang lolos FR pre-filter):**
```
GET /fapi/v1/depth?symbol=X&limit=5  → slippage futures
GET /api/v3/depth?symbol=X&limit=5   → slippage spot
```
Pre-filter: `lastFundingRate - spread_estimate > MIN_PROFIT_THRESHOLD` sebelum fetch depth.
Typical candidates: 2-5 coins. Rate limit aman.

**Startup saja (cache di memory):**
```
GET /fapi/v1/exchangeInfo → MIN_NOTIONAL + interval check
GET /fapi/v2/balance + /api/v3/account → balance awal
```

**Balance re-fetch:**
```python
BALANCE_REFRESH_INTERVAL = 3600   # 1 jam
BALANCE_REFRESH_AFTER_TRADE = True  # selalu refresh setelah trade
# sizePerPair = effectiveBalance / MAX_PAIRS (recompute setiap refresh)
```

---

## COST SPIKE BASE

Priority untuk base cost di `isCostSpike()`:
```
1. Rolling average dari paper trading (cost_cache.py) — paling akurat
2. DEFAULT_COST_TIER = 0.12% — fallback sebelum rolling avg terbentuk
```

Phase 0 sampling (11 coins) tidak dipakai sebagai hardcode base — snapshot satu hari,
tidak representatif sebagai "normal cost". Rolling average lebih valid.

---

## STARTUP SEQUENCE

```
1. Load config + secrets.env
2. Assert USE_TESTNET atau CONFIRM_MAINNET (lihat MAINNET GUARD)
3. Fetch balance → compute effectiveCapital, sizePerPair
4. Fetch min notional dari GET /fapi/v1/exchangeInfo → simpan di memory
5. Fetch open positions → reconcile dengan trade log
6. Place emergency SL untuk posisi tanpa SL/TP
7. Log downtime kalau restart
8. Tunggu clock-aligned cycle boundary
9. Mulai cycle normal
```

---

## BOT CYCLE

Setiap 5 menit, clock-aligned:

```
STEP 0 — SAFETY
→ isBlackoutWindow()? → skip ENTRY, monitoring tetap jalan
→ isBroadMarketStress()? → skip semua entry

STEP 1 — FETCH (batch, semua coins sekaligus)
→ GET /fapi/v1/premiumIndex     → FR + nextFundingTime semua coins
→ GET /fapi/v1/ticker/bookTicker → bid/ask futures semua coins
→ GET /api/v3/ticker/bookTicker  → bid/ask spot semua coins
→ GET /fapi/v1/positionRisk      → posisi open

STEP 2 — MONITOR POSISI
→ FR < EXIT_THRESHOLD → exit normal (limit order, timeout 60s)
→ FR flip sign → emergency exit (market order langsung)
→ Orphan check setelah exits

STEP 3 — CARI OPPORTUNITY (skip kalau slot penuh)
→ Fetch depth hanya untuk kandidat yang lolos FR threshold (rate limit!)
→ Hitung total_rt_cost real-time (spread + slippage + basis)
→ Filter: net_expected > MIN_PROFIT_THRESHOLD (strict >, Phase 0)
→ Filter: isCostSpike() == False
→ Sort by net_expected desc, tie-break alphabetical
→ Entry LANGSUNG — tidak tunggu settlement berikutnya
   (berbeda dari backtest t+1: live collect FR settlement terdekat)

STEP 4 — EXECUTE ENTRY
→ Place spot + futures limit order bersamaan (mid price)
→ Poll fill setiap 5s, timeout 60s
→ Partial fill → cancel keduanya, close yang sudah fill (market), log "partial_fill_failed"
→ Keduanya fill → place SL/TP via algo order, verify terpasang, log

STEP 5 — ORPHAN CHECK
→ Regular orders + algo orders (DUA endpoint berbeda)
→ Order tanpa posisi → cancel
→ Posisi tanpa SL/TP → place emergency SL dulu, lalu alert
```

Note: live punya lebih sedikit trades dari backtest karena dynamic cost filter pre-trade.
Expected live yield sedikit lebih tinggi dari backtest (~$198/tahun) karena bisa collect FR lebih awal.

---

## REAL-TIME COST

```
total_rt_cost = FEE_RT
              + (spread_spot × 2)       # (ask-bid)/mid × 100
              + (spread_futures × 2)
              + (slippage_spot × 2)     # scan asks sampai sizePerPair/2
              + (slippage_futures × 2)
              + basis                   # |markPrice-indexPrice|/indexPrice × 100

Kalau basis > 0.05% → skip coin (Phase 0 rule)
net_expected = |lastFundingRate| - total_rt_cost
```

Slippage estimation: lihat `estimateSlippage()` di `03-api-reference.md`.

---

## RISK GUARDS

```python
def isCostSpike(symbol: str, currentCost: float, costCache: dict) -> bool:
    baseline = costCache.get(symbol, {}).get("rolling_avg", DEFAULT_COST_TIER)
    return currentCost > baseline * COST_SPIKE_MULTIPLIER

def isBroadMarketStress(costSamples: dict[str, float], costCache: dict) -> bool:
    elevated = sum(1 for s, c in costSamples.items()
                   if c > costCache.get(s, {}).get("rolling_avg", DEFAULT_COST_TIER) * 2)
    return elevated / len(costSamples) > BROAD_STRESS_THRESHOLD
```

---

## MANIPULATION HANDLING

Primary: MARK_PRICE SL mencegah trigger dari candle spike palsu.

Secondary (di orphan checker):
```
Futures closed tapi spot masih open →
  Close spot dengan MARKET ORDER immediately
  Log manipulation_event: {timestamp, symbol, prices}
  Suspend coin 3 cycle
```

Monitoring: >10% trades satu coin = manipulation_event → suspend lebih lama, review manual.

---

## SL/TP

WAJIB via `requests` langsung, BUKAN ccxt. Detail lengkap di `03-api-reference.md`.
Key rules:
- `workingType: "MARK_PRICE"` — wajib
- Simpan `algoId` dari response, bukan `orderId`
- Cancel via `DELETE /fapi/v1/algoOrder` dengan `algoId`

---

## EXECUTION RULES

**Idle capital:** kalau < 6 slot terisi, sisa IDLE. `sizePerPair = effectiveCapital / MAX_PAIRS` selalu, tidak re-allocate.

**Symbol format:** API calls pakai raw `pos['info']['symbol']` → `"ETHUSDT"`. ccxt calls pakai unified `pos['symbol']` → `"ETH/USDT:USDT"`.

**Clock-aligned cycle:**
```python
def waitForNextCycle(intervalMinutes: int = 5) -> None:
    now = datetime.now(timezone.utc)
    secondsToWait = (intervalMinutes - now.minute % intervalMinutes) * 60 - now.second
    if secondsToWait < 5:
        secondsToWait += intervalMinutes * 60
    time.sleep(secondsToWait)
```

**Blackout window (ENTRY only, exit tidak terblokir):**
```python
def isBlackoutWindow() -> bool:
    now = datetime.now(timezone.utc)
    for hour in SETTLEMENT_HOURS_UTC:
        diff = (now.replace(hour=hour, minute=0, second=0) - now).total_seconds()
        if 0 < diff <= BLACKOUT_MINUTES * 60:
            return True
    return False
```

**Mainnet guard:**
```python
if not USE_TESTNET:
    assert CONFIRM_MAINNET, "Set CONFIRM_MAINNET=True di config setelah review manual"
```

**Rate limiting:** pakai batch endpoints (1 call untuk semua coins). Depth hanya untuk kandidat. Jangan fetch apapun kalau slot penuh.

---

## TRADE LOG FIELDS

Append ke file, jangan overwrite:
```python
{
    "trade_id", "symbol", "side",           # identitas
    "entry_time", "exit_time",              # ISO8601 UTC
    "entry_fr", "exit_fr",                  # FR saat signal
    "hold_settlements",                     # int
    "gross_pct", "cost_rt_pct", "net_pct", "net_dollar",  # P&L
    # Phase 4 extras (validate backtest assumptions):
    "fill_time_spot_ms", "fill_time_futures_ms",
    "actual_fill_price_spot", "actual_fill_price_futures",
    "slippage_spot_pct", "slippage_futures_pct",
    "partial_fill_occurred",                # bool
}
```

---

## RESTART PROTOCOL

```
1. Check open positions
2. Verify SL/TP — place emergency SL kalau missing
3. Reconcile trade log dengan actual positions
4. Log downtime duration + reason
```

---

## VALIDITY & METRICS

**Paper trading valid kalau:**
- Total downtime < 10% durasi (4 minggu = max 67 jam)
- Tidak ada unprotected position > 1 settlement saat down
- Trade log intact

**Invalid (ulang dari nol):**
- Orphan position > 1 settlement
- Posisi tanpa SL/TP saat bot down
- Trade log hilang

**PASS kalau SEMUA:**
```
APY >= 13.2%    (absolute floor Phase 2)
APY >= 14%      (50% dari backtest 28%)
Max DD < $50
Fill rate >= 60%
```

**Monitor per bulan:**
- Top 10% trades > 150% of net → alert
- manipulation_event > 10% trades satu coin → suspend

---

## TESTS SEBELUM BOT JALAN

`test_connectivity.py` — verify semua private endpoints dari VPS:
```
□ GET /api/v3/account          □ GET /fapi/v2/balance
□ GET /api/v3/openOrders       □ GET /fapi/v1/positionRisk
□ POST/DELETE /api/v3/order    □ POST/DELETE /fapi/v1/order
□ POST/DELETE /fapi/v1/algoOrder (pakai algoId)
□ GET /fapi/v1/algo/orders/open
□ GET /fapi/v1/depth           □ GET /api/v3/depth
```

`test_executor.py`:
- Simultaneous spot+futures order → verify keduanya fill
- Timeout scenario → cancel + close partial fill (market order)
- Algo order → verify algoId disimpan, bukan orderId
- Cancel via algoId → verify cancelled
- Orphan order → verify terdeteksi dan di-cancel

---

## DILARANG DI PHASE 4

- Optimize entry/exit threshold dari paper trading results
- Expand universe tanpa review
- Ubah position sizing
- Deploy ke mainnet sebelum 4 minggu + pass semua metrics
- Buka data 2026 untuk tuning
- Run multiple parameter variants simultaneously

---

## TRIAL REGISTRY

Max 5 trials. Update `/root/quant-arb/phase0.md` Trial Registry setiap perubahan.
```
Trial 0: entry 0.05%, exit 0.02%, min_profit 0.01%, timeout 60s
```
Boleh di-tune: `min_profit_threshold`, `ORDER_TIMEOUT_SECONDS`.
Tidak boleh: entry/exit threshold, max_pairs, buffer_ratio, universe.
