# PHASE 4 HANDOFF — 01: CONTEXT
**Date:** 23 May 2026
**Project:** Funding Rate Arbitrage Bot — Binance Perpetual Futures

---

## APA YANG SUDAH SELESAI

### Phase 0 — Foundation
- Universe: 108 coins 8h interval, filtered by: ada spot+futures di Binance, funding interval 8h, min 18 bulan training data. Volume filter di-drop (redundant dengan dynamic cost filter).
- Cost model: real-time dari orderbook di live — bukan flat tier, bukan hardcode
- Data split: train 2022-2024, validation 2025, test 2026
- Rejection criteria: APY < 13.2% atau < 50% dari backtest → reject
- API docs: semua public endpoints verified dari VPS. Private endpoints belum di-test.

### Phase 1 — Viability Analysis
- Entry threshold: |FR| >= 0.05%
- Exit threshold: |FR| < 0.02%
- Trades/year: 1,030 (sebelum slot constraint)
- Capture rate 6 slots: 92%
- Decay ratio: d = 0.777 per settlement
- Avg hold: 5.9 settlements (median 3)
- Win/loss ratio: 13.9:1
- FR autocorrelation: 0.635 — entry berdasarkan current FR valid

### Phase 2 — Math Framework
- APY formula: T × κ × φ × [(1-b)/S] × net_avg
- Absolute floor: 13.2% APY pada worst-case assumptions
- Buffer adequacy: $1,200 buffer adequate untuk semua skenario realistis

### Phase 3 — Backtest (Training 2022-2024)
- Net mid-tier: $834 / 3 tahun dari modal $3,000 (~28% APY)
- Max drawdown: $5.96 (0.18% dari modal)
- 7 statistical tests: semua PASS termasuk permutation test (p=0.000)
- Validation 2025 (OOS): $497 net, semua kriteria PASS

---

## STATE SEKARANG

Phase 3 selesai. Semua output ada di:
```
/root/quant-arb/phase3_backtest/results_v2/     ← training results (gunakan ini)
/root/quant-arb/phase3_backtest/results_validation/  ← validation 2025 results
```

Data 2026 (test set) belum didownload — download sekarang sebelum bot jalan.

---

## STRATEGI — RINGKASAN EKSEKUSI

Long spot + short futures (delta-neutral) saat |FR| >= 0.05%.
Exit saat |FR| < 0.02%.
Collect funding payment setiap 8 jam selama hold.
Price movement net ~0 karena delta-neutral.

Payoff bersifat option-like: banyak loss kecil (~70% trades), sedikit win besar (~30%).
Ini normal dan expected — jangan coba "fix" dengan menaikkan threshold.
Entry 0.05% menghasilkan net tertinggi dari semua threshold yang di-test.

---

## CAPITAL ALLOCATION

```
Total capital:        $3,000
Buffer (40%):         $1,200  (tidak di-deploy)
Effective capital:    $1,800
Max pairs:            6
Size per pair:        $300    ($150 spot + $150 futures margin)
```

---

## PARAMETER YANG LOCKED — TIDAK BOLEH DIUBAH TANPA GOVERNANCE

```
ENTRY_THRESHOLD     = 0.05%
EXIT_THRESHOLD      = 0.02%
MAX_PAIRS           = 6
TOTAL_CAPITAL       = $3,000
BUFFER_RATIO        = 0.40
EXCLUDED_SYMBOLS    = ["NEARUSDT"]
```

Parameter yang boleh di-tune di Phase 4 (dengan trial registry):
- min_profit_threshold
- timeout limit order

---

## TEMUAN PENTING DARI PHASE 3

1. **Short-hold fragility**: hold <= 3 settlements aggregate rugi. Hold = 1 hari: 0% win rate.
   Ini struktural — jangan coba filter karena akan mengurangi total net.

2. **Regime dependency**: bulan dengan FR rendah (Jun-Aug 2024) near-zero atau negatif.
   Strategi butuh elevated FR environment.

3. **Cost tier**: 10 coin punya actual cost dari Phase 0. 90 coin pakai mid tier 0.12% default.
   Di live, pakai real-time cost dari orderbook — bukan flat tier.

4. **LUNA-level crash**: kalau spread melebar > 2x secara broad market → stop new entries.

5. **Validation 2025 konsisten**: $497 net, pola identik dengan training. Edge genuine.

---

## REPO

Research repo (jangan diubah): `/root/quant-arb/`
Bot repo (buat baru, terpisah): `quant-arb-bot/`

Alasan pisah: secrets tidak boleh satu repo dengan data analisis.
