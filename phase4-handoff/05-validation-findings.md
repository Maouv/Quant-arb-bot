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
