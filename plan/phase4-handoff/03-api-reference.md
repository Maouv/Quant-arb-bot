# PHASE 4 HANDOFF — 03: API REFERENCE
**Date:** 23 May 2026
**Last updated:** 24 May 2026 (post-validation — lihat 05-validation-findings.md)
**Source:** phase0-api-docs.md (verified 19 May 2026) + live testnet validation (24 May 2026)

---

## LIBRARY

```
ccxt == 4.2.86   ← LOCKED, jangan upgrade
                   Versi baru block testnet futures API
requests         ← untuk algo orders (ccxt tidak support)
python-dotenv    ← untuk load secrets.env
```

---

## BASE URLS

```python
BASE_SPOT              = "https://api.binance.com"
BASE_FUTURES           = "https://fapi.binance.com"
BASE_TESTNET_FUTURES   = "https://testnet.binancefuture.com"
BASE_TESTNET_SPOT      = "https://testnet.binance.vision"
```

---

## DUA INSTANCE ccxt — WAJIB TERPISAH

```python
import ccxt

spotExchange = ccxt.binance({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "options": {"defaultType": "spot"},
    "recvWindow": 60000,              # WAJIB — clock drift VPS
    "adjustForTimeDifference": True,  # WAJIB — clock drift VPS
})

futuresExchange = ccxt.binanceusdm({
    "apiKey": API_KEY,
    "secret": API_SECRET,
    "options": {"defaultType": "future"},
    "recvWindow": 60000,
    "adjustForTimeDifference": True,
})
```

**Testnet:** gunakan `exchange.set_sandbox_mode(True)` — jangan override URL manual.

**⚠️ Spot testnet key BERBEDA dari futures testnet key.**
- Futures testnet key: dari https://testnet.binancefuture.com
- Spot testnet key: dari https://testnet.binance.vision (akun terpisah)
- Keduanya perlu di-setup di `.env` dengan key berbeda.

---

## PUBLIC ENDPOINTS

### Scan FR semua coins sekaligus (UTAMA — pakai ini, bukan per-coin)
```
GET /fapi/v1/premiumIndex
→ Tidak perlu symbol param → return semua coins
→ Key fields per coin:
   symbol          → "ETHUSDT"
   markPrice       → mark price (untuk SL/TP reference)
   indexPrice      → harga spot index
   lastFundingRate → FR terakhir yang settled (dalam desimal, kalikan 100 untuk %)
   nextFundingTime → timestamp settlement berikutnya (ms)
→ Verified: ✅
```

### Real-time bid/ask futures (untuk spread + slippage)
```
GET /fapi/v1/ticker/bookTicker
→ Tidak perlu symbol param → return semua coins sekaligus
→ Key fields: bidPrice, bidQty, askPrice, askQty
→ Verified: ✅
```

### Real-time bid/ask spot
```
GET /api/v3/ticker/bookTicker
→ Return semua coins sekaligus
→ Key fields: bidPrice, bidQty, askPrice, askQty
→ Verified: ✅
```

### Order book depth (untuk estimate slippage)
```
GET /fapi/v1/depth?symbol=ETHUSDT&limit=20
GET /api/v3/depth?symbol=ETHUSDT&limit=20
→ Key fields:
   bids → [[price, qty], ...]
   asks → [[price, qty], ...]
→ Verified: ✅ (24 May 2026 — testnet, both endpoints return valid orderbook)
```

### Exchange info (min notional — fetch saat startup saja)
```
GET /fapi/v1/exchangeInfo
→ Key fields per symbol:
   filters → MIN_NOTIONAL
   status  → "TRADING" atau tidak
→ Verified: ✅
```

---

## PRIVATE ENDPOINTS

### Balance
```
GET /fapi/v2/balance
→ Key fields: asset, balance, availableBalance
→ Verified: ✅ availableBalance field confirmed present dan float-parseable

GET /api/v3/account
→ Key fields: balances → [{asset, free, locked}]
→ ⚠️ Butuh spot testnet key terpisah (bukan futures key)
```

### Open Positions
```
GET /fapi/v2/positionRisk          ← BUKAN /fapi/v1/ — v2 yang valid
→ Key fields (via ccxt fapiPrivateV2GetPositionRisk):
   info['symbol']  → raw format "ETHUSDT" (BUKAN ccxt unified "ETH/USDT:USDT")
   positionAmt     → size (positif=long, negatif=short)
   entryPrice
   markPrice
   unRealizedProfit
→ PENTING: pakai pos['info']['symbol'], BUKAN pos['symbol']
→ Verified: ✅ (24 May 2026 — 752 symbols returned, raw symbol format confirmed)

⚠️ KOREKSI dari handoff awal: endpoint adalah /fapi/v2/positionRisk, BUKAN /fapi/v1/positionRisk.
   /fapi/v1/positionRisk return -5000 "Path invalid" di testnet via ccxt sandbox_mode.
```

### Place Orders
```
POST /api/v3/order           → spot order (via ccxt)
POST /fapi/v1/order          → futures order (via ccxt, BUKAN untuk SL/TP)
→ Verified: ✅ (24 May 2026 — place + cancel lifecycle confirmed)

Key params:
  symbol, side (BUY/SELL), type (LIMIT/MARKET)
  quantity, price (untuk LIMIT)
  timeInForce: GTC (untuk limit order)
  reduceOnly: True (untuk close posisi futures)

Min notional futures: $50 (verified dari -4164 error)
```

### Open Orders (regular — bukan algo)
```
GET /fapi/v1/openOrders      → futures regular orders → return list langsung (bukan wrapped object)
GET /api/v3/openOrders       → spot orders
→ Dipakai untuk: orphan detection
→ Verified: ✅ GET /fapi/v1/openOrders confirmed return array
→ ⚠️ GET /api/v3/openOrders butuh spot testnet key terpisah
```

### Cancel Orders (regular)
```
DELETE /fapi/v1/order        → cancel futures order
DELETE /api/v3/order         → cancel spot order
→ Key params: symbol, orderId
```

---

## ALGO ORDERS (SL/TP) — WAJIB VIA REQUESTS, BUKAN ccxt

ccxt tidak support endpoint ini. Gunakan requests langsung.

### Place SL/TP ⚠️ SCHEMA BERBEDA DARI HANDOFF AWAL

```python
# ⚠️ KOREKSI KRITIS — parameter berubah dari dokumentasi lama:
# - "orderType" → TIDAK ADA. Diganti dua field terpisah: "algoType" + "type"
# - "stopPrice"  → DIGANTI dengan "triggerPrice"
# - "algoType"   → HANYA support nilai "CONDITIONAL" (bukan "STOP", "VP", dll)

POST /fapi/v1/algoOrder

params = {
    "symbol":       "ETHUSDT",
    "side":         "BUY",              # BUY untuk close short, SELL untuk close long
    "positionSide": "SHORT",            # atau "LONG" (Hedge Mode) / omit (One-way Mode)
    "quantity":     "0.1",
    "algoType":     "CONDITIONAL",      # ← WAJIB, satu-satunya nilai valid
    "type":         "STOP_MARKET",      # ← order type: STOP/STOP_MARKET/TAKE_PROFIT/
                                        #   TAKE_PROFIT_MARKET/TRAILING_STOP_MARKET
    "triggerPrice": "3000.00",          # ← BUKAN stopPrice
    "workingType":  "MARK_PRICE",       # WAJIB — prevent trigger dari candle spike
}

Response: {"algoId": 12345, "orderType": "STOP_MARKET", ...}
→ Simpan algoId — ini yang dipakai untuk cancel
→ Response field "orderType" (bukan "type") — bedakan dari request param
→ Verified: ✅ (24 May 2026 — place + cancel via algoId confirmed)
```

### Cancel SL/TP
```
DELETE /fapi/v1/algoOrder
→ Key params: symbol, algoId
→ JANGAN pakai orderId — request akan di-reject (verified adversarially ✅)
→ JANGAN pakai cancel_order() dari ccxt — wrong endpoint
→ Verified: ✅ cancel via algoId confirmed. cancel via orderId correctly rejected.
```

### List Open Algo Orders
```
GET /fapi/v1/openAlgoOrders          ← BUKAN /fapi/v1/algo/orders/open
→ TERPISAH dari GET /fapi/v1/openOrders
→ Keduanya harus di-check saat orphan detection
→ Response: [{algoId, symbol, side, algoType, orderType, ...}]  ← flat array, BUKAN {"orders": [...]}
→ Verified: ✅ (24 May 2026)
```

---

## SLIPPAGE ESTIMATION

Scan order book untuk estimate slippage pada $150 position:

```python
def estimateSlippage(asks: list, bids: list, positionSize: float) -> float:
    """
    Scan asks dari best ask, accumulate sampai positionSize terpenuhi.
    Return slippage % = (worst_fill - mid_price) / mid_price * 100
    """
    bestBid = float(bids[0][0])
    bestAsk = float(asks[0][0])
    midPrice = (bestBid + bestAsk) / 2

    cumulative = 0.0
    worstPrice = bestAsk
    for price, qty in asks:
        cumulative += float(price) * float(qty)
        worstPrice = float(price)
        if cumulative >= positionSize:
            break
    return (worstPrice - midPrice) / midPrice * 100
```

---

## ORDER STATUS

```python
if orderStatus in ("filled", "closed"):
    # keduanya = executed, treat sama
```

---

## ERROR CODES

| Code  | Cause | Fix |
|-------|-------|-----|
| -4137 | Stop price already triggered | Skip, log warning |
| -4120 | Pakai /fapi/v1/order untuk algo order | Pakai /fapi/v1/algoOrder dengan algoType=CONDITIONAL |
| -4500 | algoType value tidak valid | Pastikan algoType="CONDITIONAL" (satu-satunya nilai valid) |
| -1102 | Parameter wajib tidak dikirim (e.g. algotype salah case) | Cek nama parameter: "algoType" bukan "algotype"/"orderType" |
| -4164 | Notional di bawah minimum $50 | Hitung quantity dari mark price real-time sebelum order |
| -5000 | Path/method invalid (endpoint tidak ada di testnet) | Beberapa endpoint algo tidak tersedia di testnet — skip saat test |
| -2015 | API key invalid / IP / permissions | Spot testnet butuh key berbeda dari futures testnet |
| -1021 | Timestamp out of sync | Pastikan adjustForTimeDifference=True |
| -1100 | Illegal characters in parameter | Cek format symbol |
| -2010 | Insufficient balance | Cek availableBalance sebelum order |
| -4003 | Quantity less than min notional | Fetch exchangeInfo, validate dulu |

---

## PRIVATE ENDPOINT TEST CHECKLIST

Status per 24 May 2026 (testnet validation via test_connectivity.py):

```
✅ GET  /fapi/v1/depth
✅ GET  /api/v3/depth
✅ GET  /fapi/v2/balance
✅ GET  /api/v3/account          (demo-api.binance.com — key dari demo.binance.com)
✅ GET  /fapi/v2/positionRisk    (v2 bukan v1)
✅ GET  /fapi/v1/openOrders
✅ GET  /api/v3/openOrders       (demo-api.binance.com)
✅ POST /api/v3/order            (demo-api.binance.com — via raw requests, bukan ccxt)
✅ DELETE /api/v3/order
✅ POST /fapi/v1/order
✅ DELETE /fapi/v1/order
✅ POST /fapi/v1/algoOrder       (algoType=CONDITIONAL, type=STOP_MARKET, triggerPrice)
✅ DELETE /fapi/v1/algoOrder     (algoId required — cancel via orderId correctly rejected)
✅ GET  /fapi/v1/openAlgoOrders  (BUKAN /fapi/v1/algo/orders/open — response flat array)
```

Semua endpoint: **13/13 PASS** — verified 24 May 2026.
