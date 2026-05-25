# PHASE 4 HANDOFF — 06: RATE LIMITS & ERROR HANDLING
**Date:** 24 May 2026
**Source:** Binance Futures API docs + Binance Spot API docs (verified 24 May 2026)

---

## RATE LIMITS

### Futures (`fapi.binance.com`)
- **Limit:** 2400 weight/menit
- **Header:** `X-MBX-USED-WEIGHT-1M` — current usage, ada di setiap response
- **Basis:** per IP, bukan per API key

### Spot (`api.binance.com` / `demo-api.binance.com`)
- **Mekanisme:** sama dengan futures — weight per endpoint, 429 → 418
- **Header:** `X-MBX-USED-WEIGHT-(intervalNum)(intervalLetter)`
- **Basis:** per IP

---

## WEIGHT PER ENDPOINT

### Futures — per cycle (5 menit)

| Endpoint | Param | Weight |
|---|---|---|
| `GET /fapi/v1/premiumIndex` | tanpa symbol | **10** |
| `GET /fapi/v1/ticker/bookTicker` | tanpa symbol | **5** |
| `GET /fapi/v2/positionRisk` | tanpa symbol | **5** |
| `GET /fapi/v1/openOrders` | tanpa symbol | **40** ⚠️ |
| `GET /fapi/v1/openAlgoOrders` | tanpa symbol | **40** ⚠️ |
| `GET /fapi/v1/depth` (limit≤50) | per symbol | **2** × kandidat |
| **Total per cycle (5 kandidat)** | | **~110** |
| **Per menit** | | **~22** |
| **Utilisasi** | | **<1% dari 2400** ✅ |

### Futures — occasional

| Endpoint | Weight |
|---|---|
| `GET /fapi/v2/balance` | **5** |
| `GET /fapi/v1/exchangeInfo` | **40** (startup only) |
| `POST /fapi/v1/order` | **0** (IP weight) |
| `POST /fapi/v1/algoOrder` | **0** (IP weight) |

### ⚠️ Optimisasi orphan check

`openOrders` dan `openAlgoOrders` tanpa symbol = weight **40 masing-masing = 80 total per cycle**.

Alternatif lebih efisien: fetch per-symbol hanya untuk coins yang punya open position:
- `GET /fapi/v1/openOrders?symbol=ETHUSDT` = weight **1**
- `GET /fapi/v1/openAlgoOrders?symbol=ETHUSDT` = weight **1**
- Untuk 6 open positions: 12 weight vs 80 weight — **6.7× lebih efisien**

Rekomendasi: pakai per-symbol untuk orphan check, simpan no-symbol untuk monitoring awal saja.

---

## HTTP ERROR CODES

### `429` — Rate Limit Hit

- **Meaning:** Weight limit terlampaui
- **Action:**
  1. Stop semua request segera
  2. Baca `Retry-After` header (nilai dalam detik)
  3. Sleep selama `Retry-After` + 1 detik buffer
  4. Resume normal
- **JANGAN:** retry langsung tanpa sleep → akan naik ke 418

### `418` — IP Ban

- **Meaning:** Binance ban IP karena terus request setelah 429
- **Durasi:** 2 menit → 3 hari (scale per pelanggaran, akumulatif)
- **Action:**
  1. Stop bot sepenuhnya
  2. Baca `Retry-After` header
  3. Log + alert
  4. Posisi yang open: SL/TP sudah terpasang — biarkan exchange yang handle
  5. Jangan restart bot sampai ban selesai
- **Prevention:** Jangan pernah ignore 429

### `503` — Server Issue (3 variant berbeda)

#### Variant A: `"Unknown error, please check your request or try again later"`
- **Execution status: UNKNOWN** — mungkin sudah dieksekusi, mungkin belum
- **Action untuk entry order:** query order by `clientOrderId` dulu, jangan place ulang
- **Action untuk SL/TP:** query `openAlgoOrders` dulu, jangan place ulang

#### Variant B: `"Service Unavailable"`
- **Execution status: FAILED** — 100% gagal
- **Action:** retry dengan exponential backoff (200ms → 400ms → 800ms, max 3x)

#### Variant C: `-1008` `"Request throttled by system-level protection"`
- **Execution status: FAILED** — 100% gagal
- **Exception:** reduce-only / close-position orders **exempt** dari error ini
- **Action:** backoff dan retry, kurangi concurrency

### `408` / `-1007` — Timeout
- Request dikirim tapi tidak ada response dari matching engine
- Status UNKNOWN — sama seperti 503 Variant A
- **Action:** query order status sebelum retry

### `4xx` lainnya — Client Error
- **Jangan retry** — ini bug di request kita, bukan server issue
- Log dan skip

---

## ERROR HANDLING HIERARCHY

```
HTTP response
├── 418 → STOP BOT, alert, sleep(Retry-After), jangan restart sampai ban habis
├── 429 → sleep(Retry-After + 1s), lanjut normal
├── 503 "Unknown error" → QUERY STATUS DULU, baru decide retry/skip
├── 503 "Service Unavailable" → exponential backoff (200→400→800ms, max 3x)
├── 503 "-1008 throttled" → backoff, retry (reduce-only exempt)
├── 408 / -1007 → QUERY STATUS DULU (sama seperti 503 Unknown)
├── 5xx lainnya → retry 3x dengan backoff
└── 4xx → log dan skip, JANGAN retry
```

---

## CRITICAL: 503 + SL/TP

Kasus paling berbahaya: `POST /fapi/v1/algoOrder` return 503 saat place SL/TP setelah entry fill.

Posisi open tanpa SL/TP = unprotected.

**Protocol wajib:**
```python
# Setelah place algoOrder, selalu verify:
openAlgoOrders = fetchOpenAlgoOrders(symbol=symbol)
slPlaced = any(o['algoId'] == expectedAlgoId for o in openAlgoOrders)
if not slPlaced:
    # Retry place SL/TP
    # Jika 503 Unknown: cek dulu, jangan double-place
```

Jika retry gagal semua → place emergency SL via regular order (`POST /fapi/v1/order` dengan `type=STOP_MARKET, reduceOnly=true`) sebagai fallback. Regular order exempt dari beberapa error, dan lebih sederhana.

---

## MONITOR USAGE DI PRODUCTION

Baca header `X-MBX-USED-WEIGHT-1M` dari setiap response dan log kalau > 50% limit:

```python
usedWeight = int(response.headers.get("X-MBX-USED-WEIGHT-1M", 0))
if usedWeight > 1200:  # >50% dari 2400
    logger.warning(f"Rate limit usage high: {usedWeight}/2400")
```

Ini akan catch kalau ada bug yang fetch terlalu banyak sebelum kena 429.
