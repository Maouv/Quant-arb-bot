# 13 — RATE LIMITS & ERROR HANDLING (dari 06-rate-limits.md)

---

## Weight Budget per Cycle

| Endpoint | Weight | Frequency |
|---|---|---|
| `GET /fapi/v1/premiumIndex` (all) | 10 | every cycle |
| `GET /fapi/v1/ticker/bookTicker` (all) | 5 | every cycle |
| `GET /fapi/v2/positionRisk` (all) | 5 | every cycle |
| `GET /fapi/v1/openOrders?symbol=X` | 1 × positions | every cycle |
| `GET /fapi/v1/openAlgoOrders?symbol=X` | 1 × positions | every cycle |
| `GET /fapi/v1/depth?limit=5` | 2 × candidates | every cycle |
| **Total per cycle (6 pos, 5 candidates)** | **~32** | |
| **Per menit (cycle=5min)** | **~6.4** | |
| **Limit** | **2400/min** | **<1% utilisasi** ✅ |

---

## Optimisasi: Orphan Check per-Symbol

JANGAN fetch `openOrders` / `openAlgoOrders` tanpa symbol (weight 40 each = 80 total).

**Pakai per-symbol** untuk coins yang punya open position:
```python
# Per-symbol: weight 1 each
# 6 positions × 2 endpoints = 12 weight (vs 80)
for symbol in openPositionSymbols:
    fetchOpenOrders(symbol=symbol)       # weight 1
    fetchOpenAlgoOrders(symbol=symbol)   # weight 1
```

---

## HTTP Error Hierarchy

```
Response code:
├── 418 → STOP BOT, alert, sleep(Retry-After)
│         Jangan restart sampai ban habis
│         SL/TP sudah terpasang — exchange handle
│
├── 429 → sleep(Retry-After + 1s), lanjut normal
│         JANGAN retry langsung → naik ke 418
│
├── 503 "Unknown error" → QUERY STATUS DULU
│         Order mungkin sudah executed
│         Cek via clientOrderId / openAlgoOrders
│         Jangan place ulang tanpa verify
│
├── 503 "Service Unavailable" → retry exponential backoff
│         200ms → 400ms → 800ms, max 3x
│         100% gagal, aman retry
│
├── 503 "-1008 throttled" → backoff + retry
│         reduce-only orders EXEMPT dari error ini
│
├── 408 / -1007 timeout → QUERY STATUS DULU
│         Sama seperti 503 Unknown
│
├── 5xx lainnya → retry 3x dengan backoff
│
└── 4xx → log dan skip, JANGAN retry (bug di request kita)
```

---

## Critical: 503 saat Place SL/TP

Kasus paling berbahaya. Posisi open tanpa SL/TP = unprotected.

```python
def placeStopLossWithVerify(symbol, side, qty, triggerPrice, ...) -> int:
    """
    1. POST /fapi/v1/algoOrder
    2. Kalau 503 Unknown → query openAlgoOrders(symbol)
       - Found? → return algoId
       - Not found? → retry place
    3. Kalau retry gagal semua → FALLBACK:
       POST /fapi/v1/order type=STOP_MARKET reduceOnly=true
       (regular order, lebih simple, exempt dari beberapa error)
    4. Kalau semua gagal → log CRITICAL + Discord alert
    """
```

---

## Rate Limit Monitoring

Baca header dari setiap response:

```python
def checkRateLimitUsage(responseHeaders: dict) -> None:
    """
    Baca X-MBX-USED-WEIGHT-1M.
    > 50% (1200/2400) → log WARNING
    > 80% (1920/2400) → skip non-essential fetches this cycle
    """
```

Tambah ke `exchange/auth.py` atau buat `exchange/rate_limiter.py` (~30 lines).

---

## Implementation Notes

- `exchange/auth.py` → `signedRequest()` harus return response headers juga (untuk weight tracking)
- `execution/algo_order.py` → `placeStopLoss()` harus implement verify + fallback pattern
- `position/orphan_checker.py` → pakai per-symbol fetch, BUKAN tanpa symbol
- `bot/cycle.py` → kalau 429 received, skip rest of cycle, sleep, resume next cycle
- `bot/main.py` → kalau 418 received, stop loop, alert, sleep(Retry-After), exit
