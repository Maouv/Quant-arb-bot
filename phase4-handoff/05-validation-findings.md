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

### TEMUAN 7 — KRITIS: orphan_checker.py Method + Raw API Format Salah

**Error:**
```
AttributeError: 'binance' object has no attribute 'publicGetOpenOrders'
```

**Root cause 1 — Wrong visibility prefix:**

`GET /api/v3/openOrders` adalah private endpoint (butuh API key + signature). ccxt method-nya adalah `privateGetOpenOrders()`, bukan `publicGetOpenOrders()`. `publicGet*` di ccxt hanya untuk endpoint yang benar-benar tidak butuh auth.

**Root cause 2 — Raw API vs ccxt unified format:**

`fapiPrivateV2GetPositionRisk()` mengembalikan **raw Binance API response** (flat dict), bukan ccxt unified format yang membungkus data di `"info"`. Tapi di 4 tempat di codebase, posisi di-akses via `p.get("info", {}).get("symbol/positionAmt")` — selalu return `{}` / `0`.

**Impact:**
- `tracker.py::fetchOpenPositions` → selalu return `[]` (bot pikir tidak ada posisi terbuka)
- `tracker.py::reconcilePositions` → `apiSymbols` selalu `{None}`
- `orphan_checker.py::checkOrphanRegularOrders` → `posSymbols` selalu `{None}`, semua order dianggap orphan
- `orphan_checker.py::checkOrphanAlgoOrders` → `posSymbols` selalu `{None}`

**Mapping fix:**

| File | Yang salah | Yang benar |
|------|-----------|-----------|
| `orphan_checker.py` L37 | `spotExchange.publicGetOpenOrders()` | `spotExchange.privateGetOpenOrders()` |
| `tracker.py` L17 | `p.get("info", {}).get("positionAmt", 0)` | `p.get("positionAmt", 0)` |
| `tracker.py` L33 | `p.get("info", {}).get("symbol")` | `p.get("symbol")` |
| `orphan_checker.py` L22 | `p.get("info", {}).get("symbol")` | `p.get("symbol")` |
| `orphan_checker.py` L55 | `p.get("info", {}).get("symbol")` | `p.get("symbol")` |

**Rule:** `fapiPrivateV2GetPositionRisk()` (dan semua `fapi*Get*` raw methods) → akses key langsung dari dict. Hanya method ccxt unified (`fetch_positions()`, `fetch_balance()` dll) yang punya wrapper `"info"`.

**Files yang difix:** `src/position/tracker.py`, `src/position/orphan_checker.py`

---

### TEMUAN 8 — KRITIS: cancel_order() Unified Routing ke sapi Bukan fapi

**Error (warning):**
```
Cancel order skipped: binanceusdm does not have a testnet/sandbox URL for sapi endpoints
```

**Root cause:**

`exchange.cancel_order()` adalah ccxt unified method. Pada `ccxt.binanceusdm`, method ini internally routing ke `/sapi/v1/order` (margin/spot cancel endpoint) bukan `/fapi/v1/order`. Di testnet tidak ada sapi — tapi di mainnet juga salah karena futures orders harus dibatalkan via fapi.

**Fix — raw method per exchange type:**

| Exchange | Yang salah | Yang benar |
|---|---|---|
| `ccxt.binanceusdm` | `exchange.cancel_order(id, symbol)` | `exchange.fapiPrivateDeleteOrder({"symbol": ..., "orderId": ...})` |
| `ccxt.binance` (spot) | `exchange.cancel_order(id, symbol)` | `exchange.privateDeleteOrder({"symbol": ..., "orderId": ...})` |

**Perubahan arsitektur:** `_cancelOrderSafe()` (satu fungsi, satu exchange) diganti menjadi dua fungsi terpisah `_cancelFuturesOrderSafe()` dan `_cancelSpotOrderSafe()`, dipanggil conditional berdasarkan `order["exchange"]` field yang sudah ada dari `checkOrphanRegularOrders()`.

**Rule:** Untuk operasi futures, selalu pakai raw `fapi*` methods. Unified ccxt methods (`cancel_order`, `fetch_balance`, `fetch_positions`) tidak reliable pada `binanceusdm` karena routing-nya ke endpoint yang salah.

**File yang difix:** `src/bot/cycle/orphan.py`

---

### TEMUAN 9 — KRITIS: datetime.utcnow() vs datetime.now(UTC) — Timezone Mismatch

**Error:**
```
TypeError: can't subtract offset-naive and offset-aware datetimes
```

**Root cause:**

`botState["lastBalanceRefresh"]` di-set di `startup.py` dengan `datetime.now(UTC)` → timezone-aware (`tzinfo=UTC`).

`shouldRefreshBalance()` di `balance.py` membandingkan dengan `datetime.utcnow()` → timezone-naive (`tzinfo=None`).

Python tidak bisa subtract aware dari naive — `TypeError` langsung crash cycle.

**Fix:**
```python
# SALAH
return datetime.utcnow() - lastRefresh > timedelta(seconds=BALANCE_REFRESH_INTERVAL)

# BENAR
return datetime.now(UTC) - lastRefresh > timedelta(seconds=BALANCE_REFRESH_INTERVAL)
```

**Rule:** `datetime.utcnow()` deprecated sejak Python 3.12. Seluruh codebase wajib pakai `datetime.now(UTC)` agar konsisten timezone-aware. Tidak boleh ada `utcnow()` di codebase.

**File yang difix:** `src/position/balance.py`

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

---

## TEMUAN POST-IMPLEMENTATION LANJUTAN (24 May 2026 — sesi debug bot run)

### TEMUAN 8 — KRITIS: fetch_currencies() Memanggil sapi di Testnet

**Error:**
```
Cancel order skipped: binanceusdm does not have a testnet/sandbox URL for sapi endpoints
```

**Root cause:**
`ccxt.binanceusdm.fetch_currencies()` memanggil `sapiGetCapitalConfigGetall` (endpoint `sapi/v1/capital/config/getall`). Di testnet, `sapi` tidak ada di `urls["test"]` — hanya ada di `urls["api"]` production.

ccxt punya guard internal di `fetch_currencies()`:
```python
# sandbox/testnet does not support sapi endpoints
apiBackup = self.safe_value(self.urls, 'apiBackup')
if apiBackup is not None:
    return None  # skip sapi call
```

Guard ini hanya aktif kalau `urls['apiBackup']` di-set — yang dilakukan secara otomatis oleh `set_sandbox_mode(True)`. Karena factory pakai URL override manual (`urls["api"] = urls["test"]`), `apiBackup` tidak pernah di-set → `fetch_currencies()` tetap hit production `sapi`.

**Fix:**
```python
exchange.urls["api"] = exchange.urls["test"]
exchange.urls["apiBackup"] = exchange.urls["test"]  # signal ccxt: skip sapi
```

**File yang difix:** `src/exchange/factory.py`

**Lesson:** Ketika tidak pakai `set_sandbox_mode()`, harus manually replicate semua side effects-nya — termasuk set `apiBackup`.

---

### TEMUAN 9 — BUG: Orphan Cancel Routing ke Exchange yang Salah

**Error:**
```
Cancel order skipped: binanceusdm {"code":-2011,"msg":"Unknown order sent."}
```

**Root cause:**
`checkOrphanRegularOrders()` mengumpulkan orphan orders dari dua exchange (futures + spot) dan tag setiap order dengan `"exchange": "futures"` atau `"exchange": "spot"`. Tapi `runOrphanCheck()` selalu pass `fut` (futures exchange) ke `_cancelOrderSafe()` tanpa melihat tag:

```python
# SALAH
for order in checkOrphanRegularOrders(fut, spot, openPositions):
    _cancelOrderSafe(fut, order)  # spot orders dikirim ke futures exchange!

# BENAR
for order in checkOrphanRegularOrders(fut, spot, openPositions):
    exchange = spot if order.get("exchange") == "spot" else fut
    _cancelOrderSafe(exchange, order)
```

Spot order ID tidak dikenal oleh futures exchange → `-2011`.

**Verified:** Ada stale LIMIT BUY `BTCUSDT` di spot testnet account (`orderId: 36567940991`) yang orphan detection berhasil temukan. Detection benar, routing-nya yang salah.

**File yang difix:** `src/bot/cycle/orphan.py`

---

### TEMUAN 10 — BUG: Logging Module Name Mismatch

**Symptom:** Bot jalan tapi tidak ada log di console selain satu baris WARNING.

**Root cause:**
`configureLogging()` attach handler ke named logger `"bot"`:
```python
logger = logging.getLogger("bot")
```

Semua module pakai `logging.getLogger(__name__)` → nama logger seperti `"src.bot.startup"`, `"src.position.balance"`, dll. Logger ini bukan child dari `"bot"` → tidak inherit handler-nya → log hilang.

**Fix:** Ganti ke root logger:
```python
logger = logging.getLogger()  # root logger — semua module logger inherit
```

**File yang difix:** `src/logging_/setup.py`

**Rule:** Selalu pakai root logger di `configureLogging()`, atau pastikan semua module logger adalah child dari nama yang sama (misal semua pakai `logging.getLogger("bot.xyz")`).

---

### TEMUAN 11 — BUG: Discord on_message Tidak Trigger

**Symptom:** Mention bot di Discord tidak dibalas AI. Slash commands tidak respond.

**Root cause 1 — `command_prefix=""`:**
Empty string sebagai prefix menyebabkan `commands.Bot` mencoba match setiap message sebagai prefix command, interferring dengan event processing. Error `CommandNotFound: Command "tes"` muncul karena setiap pesan dianggap command.

**Fix:** Ganti ke `commands.when_mentioned` — hanya trigger saat bot di-mention langsung.

**Root cause 2 — `process_commands()` tidak dipanggil di cog:**
`on_message` listener di cog tidak otomatis memanggil `process_commands()`. Tanpa ini, `commands.Bot` tidak forward message ke event system dengan benar.

**Fix:** Tambah `await self.bot.process_commands(message)` di awal `on_message`.

**Files yang difix:** `src/discord_ui/bot.py`, `src/discord_ui/commands.py`

---

## STATUS TERKINI (24 May 2026 — EOD)

| Komponen | Status |
|----------|--------|
| Bot utama (`src.bot.main`) | ✅ Jalan — cycle berjalan, log muncul |
| Futures exchange testnet | ✅ Connected — balance, positions, orders OK |
| Spot exchange testnet (private) | ⚠️ Butuh spot testnet key |
| Discord bot | ✅ Connected ke guild "Crito Maou" |
| Discord slash commands | ✅ Synced ke guild |
| Discord AI mention response | 🔧 Fix applied, belum re-verified |
| Orphan detection | ✅ Benar — deteksi stale spot order |
| Orphan cancel routing | ✅ Fixed — route ke exchange yang tepat |
