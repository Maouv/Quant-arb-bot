# 12 — EDGE CASES & GOTCHAS

Items dari handoff docs yang mudah terlewat saat implementasi.

---

## 1. Symbol Format Conversion

Bot harus handle DUA format symbol:

```python
# Raw API format (untuk raw requests, logging, trade log):
"ETHUSDT"

# ccxt unified format (untuk ccxt method calls):
"ETH/USDT:USDT"
```

Conversion:
```python
def toUnified(rawSymbol: str) -> str:
    """ETHUSDT → ETH/USDT:USDT"""
    base = rawSymbol.replace("USDT", "")
    return f"{base}/USDT:USDT"

def toRaw(unifiedSymbol: str) -> str:
    """ETH/USDT:USDT → ETHUSDT"""
    return unifiedSymbol.split("/")[0] + "USDT"
```

Taruh di `exchange/` atau `config/` sebagai utility.

---

## 2. Slippage Scan Size

Dari docs: `scan asks sampai sizePerPair/2`

```python
# sizePerPair = ~$300
# Slippage scan untuk SATU LEG = $150 (half)
# Karena: $150 spot + $150 futures
positionSizePerLeg = sizePerPair / 2  # $150
```

---

## 3. Depth Limit

Pakai `limit=5`. Dari validation findings (05-validation-findings.md):
```
/fapi/v1/depth — ✅ PASS — 5 bids/asks confirmed
```
$150 per leg pada most coins cukup di 5 levels.
Kalau 5 levels tidak cukup → slippage tinggi → net_expected rendah → coin di-skip anyway oleh cost filter.

---

## 4. hold_settlements Calculation

```python
# Hitung berapa settlement terjadi selama hold
# Settlement setiap 8 jam: 00:00, 08:00, 16:00 UTC
holdSettlements = countSettlementsBetween(entryTime, exitTime)
```

Perlu fungsi helper:
```python
def countSettlementsBetween(entryTime: datetime, exitTime: datetime) -> int:
    """Count berapa kali 00:00/08:00/16:00 UTC terjadi antara entry dan exit."""
```

---

## 5. gross_pct Calculation

```python
# gross = total FR collected selama hold
# BUKAN price change (delta-neutral, price change ~0)
grossPct = sum(fundingRatesCollected)  # dalam %
```

Bot perlu track FR yang di-collect setiap settlement selama hold.
Option: fetch funding history via `GET /fapi/v1/fundingRate` saat exit.

---

## 6. SL/TP Trigger Price

Docs tidak specify exact SL/TP levels. Reasonable defaults:

```python
# SL: protect dari spread blowout / manipulation
# Futures short position → SL = BUY at markPrice * 1.02 (2% above entry)
# Futures long position → SL = SELL at markPrice * 0.98 (2% below entry)

# TP: tidak wajib di Phase 4 (exit by FR signal, bukan TP)
# Tapi place anyway sebagai safety net
# TP = markPrice * 0.99 (1% profit) — conservative
```

⚠️ Ini perlu di-define di config sebagai tunable:
```python
SL_PERCENT: float = 2.0   # % dari entry price
TP_PERCENT: float = 1.0   # % dari entry price (optional)
```

---

## 7. USDCUSDT in Universe

`USDCUSDT` ada di universe list. Ini stablecoin pair.
Tapi docs bilang "bukan stablecoin" di criteria.

**Resolution:** USDCUSDT adalah USDC/USDT futures — bukan stablecoin itu sendiri yang di-trade, tapi futures contract-nya. FR bisa extreme pada stablecoin pairs. Keep in universe — dynamic cost filter akan handle kalau spread terlalu besar.

---

## 8. Rate Limit Awareness

```
Binance rate limits:
- Spot: 1200 request weight / minute
- Futures: 2400 request weight / minute

Batch endpoints (weight 5-40 each):
- premiumIndex: weight 10
- bookTicker (all): weight 2
- positionRisk: weight 5

Per-symbol depth (weight 5-20):
- depth limit=20: weight 5

Worst case per cycle: ~50 weight (batch) + 5*10 (depth 5 candidates) = ~100 weight
Well within limits.
```

Jangan fetch depth untuk semua 100 coins — itu 500 weight per cycle.

---

## 9. Testnet Limitations

Dari validation findings:
- `GET /fapi/v1/openAlgoOrders` mungkin return format berbeda di mainnet
- Spot testnet key terpisah dari futures testnet key
- Beberapa coins mungkin tidak ada di testnet

**Mitigation:**
- Log raw response pertama kali di mainnet sebelum parsing
- Graceful fallback kalau symbol tidak ada di testnet

---

## 10. Trade Log Entry vs Exit

Trade record di-append DUA KALI:
1. **Entry time:** append dengan `exit_time=null`, `net_dollar=null`
2. **Exit time:** UPDATE record (find by trade_id, fill exit fields)

Atau simpler: append hanya saat EXIT (semua data lengkap).
**Recommendation:** append hanya saat exit — simpler, no partial records.

Tapi perlu track "active trades" in-memory untuk reconciliation:
```python
activePositions: dict[str, dict] = {
    "ETHUSDT": {
        "trade_id": "...",
        "entry_time": "...",
        "entry_fr": 0.08,
        "spot_side": "BUY",
        "futures_side": "SELL",
        "quantity": 0.05,
        "mid_price_spot": 3500.0,
        "mid_price_futures": 3501.0,
        "algo_ids": [123, 456],  # SL + TP
    }
}
```

---

## 11. Funding Rate Collection Tracking

Bot perlu tahu berapa FR yang di-collect selama hold untuk `gross_pct`.

Options:
1. Fetch `GET /fapi/v1/fundingRate?symbol=X&startTime=entryTime` saat exit
2. Track in-memory: setiap settlement, record FR untuk active positions

**Recommendation:** Option 1 — simpler, no state to maintain. Fetch at exit time.

---

## 12. Emergency SL — What Price?

Saat startup, kalau posisi tanpa SL/TP ditemukan:
```python
# Fetch current markPrice
# Place SL at markPrice * (1 + SL_PERCENT/100) untuk short
# Place SL at markPrice * (1 - SL_PERCENT/100) untuk long
```

Bukan dari entry price (mungkin tidak tersedia kalau trade log corrupt).

---

## 13. Concurrent Entry Limit

Dari docs: entry LANGSUNG, bisa multiple per cycle.
Tapi: jangan entry lebih dari `available_slots` per cycle.

```python
availableSlots = MAX_PAIRS - len(openPositions)
candidates = filterCandidates(...)[:availableSlots]
```

Dan: execute ONE AT A TIME (sequential), bukan parallel.
Karena: partial fill handling perlu attention per pair.

---

## 14. NEARUSDT Exclusion — Permanent

Dari Phase 0. Alasan tidak documented tapi marked "permanen".
Hardcode di `EXCLUDED_SYMBOLS`, jangan remove tanpa governance.

---

## 15. TOTAL_CAPITAL — Referensi Saja, JANGAN Pakai untuk Sizing

`TOTAL_CAPITAL = 3000.0` di config adalah DOKUMENTASI, bukan input untuk logic.

```python
# BENAR — sizing dari live balance:
balance = fetchFuturesBalance(futuresExchange)  # dari API
sizePerPair = computeSizePerPair(balance)

# SALAH — jangan pakai constant:
sizePerPair = TOTAL_CAPITAL * (1 - BUFFER_RATIO) / MAX_PAIRS  # ❌ HARDCODE
```

Alasan: balance berubah seiring waktu (profit/loss, deposit/withdraw).

---

## 16. EXCLUDED_SYMBOLS — Hanya NEAR yang Hardcode

`EXCLUDED_SYMBOLS = ["NEARUSDT"]` adalah satu-satunya permanent exclusion.

Semua exclusion lain DYNAMIC per cycle:
- `net_expected <= MIN_PROFIT_THRESHOLD` → skip (cost terlalu tinggi / illiquid)
- `isCostSpike()` → skip (anomaly)
- `isBasisTooHigh()` → skip (basis > 0.05%)
- `exchangeInfo status != "TRADING"` → skip (delist/suspend)
- Interval berubah ke 4h → skip (startup validation)
- `suspendedSymbols[coin] > 0` → skip (manipulation, temporary 3 cycles)

Jangan hardcode coin lain ke EXCLUDED_SYMBOLS tanpa governance.
