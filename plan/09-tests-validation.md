# 09 — TESTS & VALIDATION

---

## Test Files

### tests/test_signals.py (~60 lines)

```python
def test_isEntrySignal_above_threshold():
def test_isEntrySignal_below_threshold():
def test_isEntrySignal_exact_threshold():
def test_isExitSignal_below_threshold():
def test_isExitSignal_above_threshold():
def test_isFundingRateFlipped_positive_to_negative():
def test_isFundingRateFlipped_same_sign():
def test_determineSide_positive_fr():
def test_determineSide_negative_fr():
```

### tests/test_risk_guard.py (~60 lines)

```python
def test_isCostSpike_normal():
def test_isCostSpike_elevated():
def test_isBroadMarketStress_below_threshold():
def test_isBroadMarketStress_above_threshold():
def test_isBlackoutWindow_inside():
def test_isBlackoutWindow_outside():
def test_isBasisTooHigh():
```

### tests/test_cost_calculator.py (~50 lines)

```python
def test_calculateSpread():
def test_calculateBasis():
def test_calculateTotalRtCost():
def test_calculateNetExpected_profitable():
def test_calculateNetExpected_unprofitable():
def test_estimateSlippage():
```

### tests/test_executor.py (~80 lines, testnet)

```python
def test_futuresOrderLifecycle():
    """Place limit far from market → verify fill status → cancel."""

def test_algoOrderLifecycle():
    """Place SL → verify algoId → cancel via algoId."""

def test_algoOrderCancelWithOrderIdFails():
    """Adversarial: cancel with orderId field → expect rejection."""

def test_partialFillHandling():
    """Simulate one leg filled, other timeout → verify cleanup."""
```

---

## Validation Criteria (setelah 4-6 minggu)

**PASS kalau SEMUA:**
```
APY >= 13.2%         (absolute floor)
APY >= 14%           (50% dari backtest 28%)
Max DD < $50
Fill rate >= 60%
```

**INVALID (ulang dari nol):**
- Orphan position > 1 settlement
- Posisi tanpa SL/TP saat bot down
- Trade log hilang
- Total downtime > 10% durasi

**Monitor per bulan:**
- Top 10% trades > 150% of net → alert
- manipulation_event > 10% trades satu coin → suspend

---

## Test Runner

```bash
# Unit tests (no API)
python -m pytest tests/test_signals.py tests/test_risk_guard.py tests/test_cost_calculator.py -v

# Integration tests (testnet)
python -m pytest tests/test_connectivity.py tests/test_executor.py -v
```

---

## Pre-Launch Checklist

```
□ Semua unit tests pass
□ test_connectivity.py 13/13 pass
□ test_executor.py all pass
□ Bot runs 24h tanpa crash
□ Trade log populated correctly
□ SL/TP verified terpasang untuk semua positions
□ Orphan checker working (log shows checks)
□ Cost cache accumulating data
□ Discord bot responds to /status, /metrics, /positions
□ AI /ask command returns coherent analysis
```
