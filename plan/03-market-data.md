# 03 — MARKET DATA

---

## market/scanner.py (~90 lines)

```python
def fetchPremiumIndex(futuresExchange) -> list[dict]:
    """
    GET /fapi/v1/premiumIndex — semua coins sekaligus (1 call).
    Return list of:
      {symbol, markPrice, indexPrice, lastFundingRate, nextFundingTime}
    lastFundingRate dalam desimal — kalikan 100 untuk %.
    """

def fetchBookTickerFutures(futuresExchange) -> dict[str, dict]:
    """
    GET /fapi/v1/ticker/bookTicker — semua coins sekaligus.
    Return: {symbol: {bid: float, ask: float, bidQty, askQty}}
    """

def fetchBookTickerSpot(spotExchange) -> dict[str, dict]:
    """
    GET /api/v3/ticker/bookTicker — semua coins sekaligus.
    Return: {symbol: {bid: float, ask: float, bidQty, askQty}}
    """

def fetchDepth(exchange, symbol: str, limit: int = 5) -> dict:
    """
    GET /fapi/v1/depth atau /api/v3/depth per symbol.
    Hanya dipanggil untuk candidates yang lolos pre-filter.
    Return: {bids: [[price, qty], ...], asks: [[price, qty], ...]}
    """

def filterCandidates(premiumIndex: list, bookTickerSpot: dict,
                     bookTickerFutures: dict, openSlots: int,
                     excludedSymbols: list[str],
                     validUniverse: list[str]) -> list[dict]:
    """
    Filter:
    1. Symbol in validUniverse dan bukan excluded
    2. |lastFundingRate| >= ENTRY_THRESHOLD
    3. Quick spread estimate: net_expected > MIN_PROFIT_THRESHOLD
    
    Sort: net_expected desc, tie-break alphabetical.
    Return max openSlots candidates.
    """
```

---

## market/cost_calculator.py (~60 lines)

```python
def calculateSpread(bid: float, ask: float) -> float:
    """(ask - bid) / midPrice * 100 — dalam %"""

def calculateBasis(markPrice: float, indexPrice: float) -> float:
    """|markPrice - indexPrice| / indexPrice * 100 — dalam %"""

def calculateTotalRtCost(spreadSpot: float, spreadFutures: float,
                         slippageSpot: float, slippageFutures: float,
                         basis: float) -> float:
    """
    total_rt_cost = FEE_RT
                  + (spreadSpot * 2)
                  + (spreadFutures * 2)
                  + (slippageSpot * 2)
                  + (slippageFutures * 2)
                  + basis
    Semua dalam %.
    """

def calculateNetExpected(fundingRate: float, totalRtCost: float) -> float:
    """net_expected = |fundingRate * 100| - totalRtCost"""

def calculateActualCostRt(fillPriceSpot: float, midPriceSpot: float,
                          fillPriceFutures: float, midPriceFutures: float) -> float:
    """
    Post-trade actual cost:
    = (|fillSpot - midSpot| / midSpot
     + |fillFutures - midFutures| / midFutures
     + TAKER_FEE * 4) * 100
    Untuk validasi backtest assumption.
    """
```

---

## market/slippage.py (~35 lines)

```python
def estimateSlippage(asks: list[list], bids: list[list],
                     positionSize: float) -> float:
    """
    Scan asks, accumulate notional sampai positionSize terpenuhi.
    Return slippage % = (worstFillPrice - midPrice) / midPrice * 100
    
    midPrice = (bestBid + bestAsk) / 2
    """
```

---

## market/cost_cache.py (~50 lines)

```python
class CostCache:
    """
    Rolling average cost per coin.
    Persist ke logs/cost_cache.json.
    """

    def __init__(self, filepath: str = "logs/cost_cache.json"):
        ...

    def update(self, symbol: str, cost: float) -> None:
        """Tambah data point, recompute rolling avg."""

    def getRollingAvg(self, symbol: str) -> float:
        """Return rolling avg. Fallback: DEFAULT_COST_TIER."""

    def save(self) -> None:
        """Write ke disk."""

    def load(self) -> None:
        """Load dari disk. No-op kalau file belum ada."""
```

---

## Critical Notes

- Batch endpoints (premiumIndex, bookTicker) = 1 call untuk semua coins
- Depth hanya di-fetch untuk candidates yang lolos FR pre-filter (2-5 coins typical)
- Jangan fetch depth kalau slot penuh — rate limit awareness
- `basis > 0.05%` → skip coin (Phase 0 rule)
- `lastFundingRate` dari API dalam desimal (e.g. 0.0005 = 0.05%)
