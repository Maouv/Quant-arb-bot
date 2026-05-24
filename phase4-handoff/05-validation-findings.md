# PHASE 4 HANDOFF — 05: VALIDATION FINDINGS
**Date:** 24 May 2026
**Scope:** Live testnet endpoint validation via `tests/test_connectivity.py`
**Testnet:** `testnet.binancefuture.com` (futures), `testnet.binance.vision` (spot)
**Result:** 9/13 PASS, 0 FAIL, 4 WARN

---

## RINGKASAN EKSEKUTIF

Tiga temuan kritis yang memerlukan koreksi sebelum bot bisa dijalankan:

1. **Schema algo order berubah** — parameter `orderType`/`stopPrice` sudah tidak valid. Binance migrasi ke `algoType=CONDITIONAL` + `type` + `triggerPrice` (mandatory sejak Nov 2025).
2. **positionRisk endpoint salah versi** — harus `/fapi/v2/` bukan `/fapi/v1/`.
3. **Spot testnet key terpisah** — spot private endpoints butuh key dari `testnet.binance.vision`, bukan key futures.

---

## TEMUAN DETAIL

### TEMUAN 1 — KRITIS: Algo Order Schema Berubah

**Status handoff awal:** Dokumentasi menyebut parameter `orderType` dan `stopPrice`.

**Realita:**
- `-1102`: `"Mandatory parameter 'algotype' was not sent"` → `orderType` tidak dikenal
- `-4500`: `"Invalid algoType"` → nilai `"STOP"` tidak valid
- Binance mengubah API algo order sejak **6 November 2025** (mandatory migration)

**Schema yang benar (verified ✅):**
```python
{
    "algoType":     "CONDITIONAL",   # satu-satunya nilai valid
    "type":         "STOP_MARKET",   # atau STOP/TAKE_PROFIT/TAKE_PROFIT_MARKET/TRAILING_STOP_MARKET
    "triggerPrice": "3000.00",       # BUKAN stopPrice
    "workingType":  "MARK_PRICE",
}
```

**Response field:** `algoId` confirmed present. `orderType` di response (bukan `type`) — jangan konfusikan dengan request param `type`.

**Implikasi bot:** Semua kode yang place SL/TP harus pakai schema baru ini. Kode lama dengan `orderType`/`stopPrice` akan gagal dengan `-1102`.

---

### TEMUAN 2 — KRITIS: positionRisk Endpoint Versi Salah

**Status handoff awal:** Documented sebagai `GET /fapi/v1/positionRisk`.

**Realita:**
- `/fapi/v1/positionRisk` via ccxt `set_sandbox_mode` → `-5000` "Path invalid"
- `/fapi/v2/positionRisk` → ✅ 752 symbols returned, format benar

**Endpoint yang benar:** `GET /fapi/v2/positionRisk`

**ccxt method:** `exchange.fapiPrivateV2GetPositionRisk()`

**Symbol format confirmed:** `info['symbol']` = `"BTCUSDT"` (raw), bukan `symbol` = `"BTC/USDT:USDT"` (ccxt unified). Handoff benar soal ini.

---

### TEMUAN 3 — MEDIUM: Spot Testnet Key Terpisah

**Status handoff awal:** Tidak disebutkan bahwa spot dan futures testnet pakai key berbeda.

**Realita:**
- Semua spot private endpoints (`/api/v3/account`, `/api/v3/openOrders`, `POST /api/v3/order`) → `-2015` "Invalid API-key"
- Penyebab: futures testnet key (`testnet.binancefuture.com`) tidak berlaku untuk spot testnet (`testnet.binance.vision`)
- Keduanya adalah sistem terpisah dengan akun terpisah

**Yang perlu dilakukan:**
1. Daftar di https://testnet.binance.vision
2. Generate API key spot testnet
3. Tambah ke `.env`:
   ```env
   BINANCE_TESTNET_SPOT_KEY=...
   BINANCE_TESTNET_SPOT_SECRET=...
   ```
4. Update `test_connectivity.py` untuk pakai key yang benar per exchange instance

**Implikasi bot:** Di production, spot dan futures pakai key yang sama (mainnet Binance). Ini hanya masalah testnet.

---

### TEMUAN 4 — LOW: GET /fapi/v1/algo/orders/open Tidak Ada di Testnet

**Status:** `-5000` "Path invalid" di testnet.

**Implikasi:** Endpoint list algo orders tidak bisa divalidasi di testnet. Harus diverifikasi di mainnet.

**Risk:** Kalau endpoint ini return struktur berbeda dari `{"orders": [...]}`, orphan detection algo orders akan fail silently.

**Mitigation:** Saat pertama kali bot jalan di mainnet, add explicit logging untuk raw response dari endpoint ini sebelum parsing.

---

## ENDPOINTS YANG DIVALIDASI

| Endpoint | Method | Status | Catatan |
|----------|--------|--------|---------|
| `/fapi/v1/depth` | GET | ✅ PASS | 5 bids/asks, format `[[price, qty]]` confirmed |
| `/api/v3/depth` | GET | ✅ PASS | sama |
| `/fapi/v2/balance` | GET | ✅ PASS | `availableBalance` field confirmed |
| `/api/v3/account` | GET | ⚠️ WARN | butuh spot testnet key |
| `/fapi/v2/positionRisk` | GET | ✅ PASS | 752 symbols, raw symbol format confirmed |
| `/fapi/v1/openOrders` | GET | ✅ PASS | return array langsung (bukan wrapped) |
| `/api/v3/openOrders` | GET | ⚠️ WARN | butuh spot testnet key |
| `/fapi/v1/order` | POST+DELETE | ✅ PASS | place + cancel lifecycle confirmed |
| `/api/v3/order` | POST+DELETE | ⚠️ WARN | butuh spot testnet key |
| `/fapi/v1/algoOrder` | POST | ✅ PASS | schema baru confirmed |
| `/fapi/v1/algoOrder` | DELETE | ✅ PASS | algoId required, orderId correctly rejected |
| `/fapi/v1/algo/orders/open` | GET | ⚠️ WARN | tidak ada di testnet |

---

## KOREKSI KE HANDOFF DOCS

Semua koreksi sudah di-apply ke `03-api-reference.md`.

| Field | Lama (salah) | Baru (benar) |
|-------|-------------|--------------|
| positionRisk path | `/fapi/v1/positionRisk` | `/fapi/v2/positionRisk` |
| ccxt method | `fapiPrivateGetPositionRisk` | `fapiPrivateV2GetPositionRisk` |
| algo param | `"orderType": "STOP"` | `"algoType": "CONDITIONAL", "type": "STOP_MARKET"` |
| algo param | `"stopPrice": "..."` | `"triggerPrice": "..."` |
| depth status | "Belum verified" | ✅ Verified 24 May 2026 |

---

---

## TEMUAN POST-IMPLEMENTATION (24 May 2026 — sesi bot run pertama)

### TEMUAN 5 — KRITIS: factory.py URL Override Salah

**Error:**
```
binanceusdm does not have a testnet/sandbox URL for fapiPrivateV2 endpoints
binanceusdm does not have a testnet/sandbox URL for fapiPublic endpoints
```

**Root cause:**
```python
# SALAH — replace seluruh dict dengan string
exchange.urls["api"] = "https://testnet.binancefuture.com"

# BENAR — assign built-in testnet dict dari ccxt
exchange.urls["api"] = exchange.urls["test"]
```

`urls["api"]` di `ccxt.binanceusdm` adalah dict dengan 19 keys (`fapiPublic`, `fapiPrivate`, `fapiPrivateV2`, `sapi`, dll). Ketika di-replace dengan string, semua endpoint lookup `urls["api"]["fapiPublic"]` dll fail karena string tidak punya keys.

**Fix:** `exchange.urls["test"]` adalah dict built-in ccxt yang berisi semua testnet URLs yang benar:
```python
{
    "fapiPublic":    "https://testnet.binancefuture.com/fapi/v1",
    "fapiPrivate":   "https://testnet.binancefuture.com/fapi/v1",
    "fapiPrivateV2": "https://testnet.binancefuture.com/fapi/v2",
    "fapiPublicV2":  "https://testnet.binancefuture.com/fapi/v2",
    "fapiData":      "https://testnet.binancefuture.com/futures/data",
    ...
}
```

Note: `sapi` tidak ada di `urls["test"]` — ini expected karena sapi tidak tersedia di testnet futures. Operasi yang kita pakai (`fapi*`) semua ada.

**File yang difix:** `src/exchange/factory.py`

---

### TEMUAN 6 — KRITIS: scanner.py ccxt Method Names Salah

**Error:**
```
AttributeError: 'binance' object has no attribute 'publicGetApiV3TickerBookTicker'
```

**Root cause:** Method yang di-call tidak ada di ccxt `binance` object.

**Mapping yang benar (verified via `dir(ccxt.binance())`):**

| Yang salah | Yang benar |
|-----------|-----------|
| `publicGetApiV3TickerBookTicker()` | `publicGetTickerBookTicker()` |
| `publicGetApiV3Depth({"symbol": ..., "limit": ...})` | `publicGetDepth({"symbol": ..., "limit": ...})` |

ccxt naming convention untuk spot: method name = endpoint path tanpa `/api/v3/` prefix, camelCase. Bukan `publicGetApiV3*`.

**File yang difix:** `src/market/scanner.py`

---

### TEMUAN 7 — KRITIS: createSpotExchange URL Override Salah

**Error:**
```
binance does not have a testnet/sandbox URL for public endpoints
```

**Root cause:** Bug sama seperti Temuan 5 tapi di `createSpotExchange`. `urls["api"]` di-replace dengan string:
```python
# SALAH
exchange.urls["api"] = "https://demo-api.binance.com"
```

**Kenapa tidak bisa pakai `urls["test"]` seperti futures:**
`ccxt.binance().urls["test"]` mengarah ke `testnet.binance.vision` (bukan `demo-api.binance.com`). Keduanya berbeda — demo-api.binance.com adalah Binance Demo Mode dengan key dari demo.binance.com.

**Fix:** Override per-key, hanya `public`, `private`, `v1`:
```python
# BENAR
exchange.urls["api"]["public"]  = "https://demo-api.binance.com/api/v3"
exchange.urls["api"]["private"] = "https://demo-api.binance.com/api/v3"
exchange.urls["api"]["v1"]      = "https://demo-api.binance.com/api/v1"
```

`sapi` dan key lain tetap default (mengarah ke `api.binance.com`) — tidak perlu diubah karena kita tidak pakai sapi di spot demo mode.

**File yang difix:** `src/exchange/factory.py`

---

## ITEMS BELUM TERVALIDASI

Yang masih perlu diverifikasi sebelum Phase 5 (mainnet):

1. `GET /fapi/v1/algo/orders/open` — verify response schema `{"orders": [...]}` di mainnet
2. Semua spot private endpoints — verify dengan spot testnet key yang benar
3. `POST /fapi/v1/algoOrder` untuk posisi yang benar-benar open — test dengan posisi real (bukan `reduceOnly`)
4. Algo order `workingType: MARK_PRICE` vs `CONTRACT_PRICE` — verify trigger behavior di live market

---

## TEST SCRIPT

`tests/test_connectivity.py` — dijalankan 24 May 2026, exit code 0.

Untuk re-run setelah setup spot testnet key:
```bash
cd /root/quant-arb-bot
.venv/bin/python tests/test_connectivity.py
```

Expected: 13/13 PASS setelah spot testnet key ditambahkan ke `.env`.
