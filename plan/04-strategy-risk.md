# 04 — STRATEGY & RISK

---

## strategy/signal.py (~40 lines)

```python
def isEntrySignal(fundingRate: float) -> bool:
    """abs(fundingRate) >= ENTRY_THRESHOLD (0.05%)
    fundingRate sudah dalam % (bukan desimal).
    """

def isExitSignal(fundingRate: float) -> bool:
    """abs(fundingRate) < EXIT_THRESHOLD (0.02%)"""

def isFundingRateFlipped(entryFr: float, currentFr: float) -> bool:
    """
    Sign berubah → emergency exit.
    entryFr positif tapi currentFr negatif, atau sebaliknya.
    """

def determineSide(fundingRate: float) -> tuple[str, str]:
    """
    Determine spot side + futures side.
    FR > 0 → long spot (BUY), short futures (SELL)
    FR < 0 → short spot (SELL), long futures (BUY)
    Return: (spotSide, futuresSide)
    """
```

---

## strategy/risk_guard.py (~70 lines)

```python
def isCostSpike(symbol: str, currentCost: float, costCache: CostCache) -> bool:
    """
    currentCost > baseline * COST_SPIKE_MULTIPLIER (3x)
    baseline = costCache.getRollingAvg(symbol) atau DEFAULT_COST_TIER
    """

def isBroadMarketStress(costSamples: dict[str, float],
                        costCache: CostCache) -> bool:
    """
    Hitung berapa % coins punya cost > 2x rolling avg.
    Return True kalau > BROAD_STRESS_THRESHOLD (50%).
    Kalau True → skip ALL entries, monitoring tetap jalan.
    """

def isBlackoutWindow() -> bool:
    """
    True jika dalam BLACKOUT_MINUTES (5 min) sebelum settlement.
    Settlement hours: 0, 8, 16 UTC.
    
    HANYA block entry — exit TIDAK terblokir.
    """

def isBasisTooHigh(basis: float) -> bool:
    """basis > 0.05% → skip coin."""
```

---

## Critical Notes

- Entry LANGSUNG saat signal — tidak tunggu settlement berikutnya
- Exit normal: FR < 0.02% → limit order, timeout 60s
- Exit emergency: FR flip sign → market order langsung
- Blackout window TIDAK block exit
- Broad market stress TIDAK block exit
- `determineSide()` logic: kita collect funding, jadi kita ambil sisi yang DIBAYAR
