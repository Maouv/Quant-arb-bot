# 05 — EXECUTION

---

## execution/order_placer.py (~80 lines)

```python
def placeEntryOrders(spotExchange, futuresExchange, symbol: str,
                     spotSide: str, futuresSide: str,
                     quantity: float, spotPrice: float,
                     futuresPrice: float) -> tuple[dict, dict]:
    """
    Place spot + futures LIMIT order bersamaan (mid price).
    timeInForce: GTC
    
    Return: (spotOrder, futuresOrder) — raw order dicts.
    Caller handles fill monitoring.
    """

def calculateQuantity(markPrice: float, sizePerPair: float,
                      minNotional: float) -> float:
    """
    quantity = sizePerPair / markPrice
    Validate: quantity * markPrice >= minNotional ($50 futures)
    Raise ValueError kalau insufficient.
    """
```

Symbol format note:
- ccxt calls: `"ETH/USDT:USDT"` (unified)
- Raw API / logging: `"ETHUSDT"` (dari `pos['info']['symbol']`)

---

## execution/order_monitor.py (~70 lines)

```python
def pollOrderFill(exchange, orderId: str, symbol: str,
                  timeoutSeconds: int = 60) -> tuple[str, dict]:
    """
    Poll setiap 5s sampai filled/closed atau timeout.
    Return: (status, orderInfo)
    status: "filled" | "timeout" | "cancelled"
    
    Note: "filled" dan "closed" keduanya = executed.
    """

def handlePartialFill(spotExchange, futuresExchange,
                      spotOrder: dict, futuresOrder: dict,
                      symbol: str) -> None:
    """
    Salah satu fill, yang lain timeout:
    1. Cancel keduanya
    2. Close yang sudah fill dengan MARKET order
    3. Log "partial_fill_failed"
    """
```

---

## execution/algo_order.py (~80 lines)

```python
def placeStopLoss(symbol: str, side: str, quantity: str,
                  triggerPrice: str, baseUrl: str,
                  apiKey: str, apiSecret: str) -> int:
    """
    POST /fapi/v1/algoOrder
    
    Params:
      algoType: "CONDITIONAL"     ← satu-satunya nilai valid
      type: "STOP_MARKET"
      triggerPrice: str           ← BUKAN stopPrice
      workingType: "MARK_PRICE"   ← WAJIB, prevent candle spike trigger
    
    Return: algoId (int) — BUKAN orderId.
    """

def placeTakeProfit(symbol: str, side: str, quantity: str,
                    triggerPrice: str, baseUrl: str,
                    apiKey: str, apiSecret: str) -> int:
    """Same schema, type: "TAKE_PROFIT_MARKET". Return algoId."""

def cancelAlgoOrder(symbol: str, algoId: int, baseUrl: str,
                    apiKey: str, apiSecret: str) -> None:
    """
    DELETE /fapi/v1/algoOrder
    Params: symbol, algoId
    
    JANGAN pakai orderId — akan di-reject.
    JANGAN pakai ccxt cancel_order() — wrong endpoint.
    """

def listOpenAlgoOrders(baseUrl: str, apiKey: str,
                       apiSecret: str) -> list[dict]:
    """
    GET /fapi/v1/openAlgoOrders
    
    Return: flat array [{algoId, symbol, side, algoType, orderType, ...}]
    BUKAN wrapped {"orders": [...]}
    BUKAN /fapi/v1/algo/orders/open (endpoint tidak ada)
    """
```

---

## execution/exit_handler.py (~60 lines)

```python
def exitNormal(spotExchange, futuresExchange, symbol: str,
               spotSide: str, futuresSide: str,
               quantity: float, algoIds: list[int],
               baseUrl: str, apiKey: str, apiSecret: str) -> dict:
    """
    1. Cancel existing SL/TP (via algoIds)
    2. Place limit exit orders (spot + futures)
    3. Poll fill, timeout 60s
    4. Kalau timeout → fallback market order
    5. Return trade result dict
    
    futures exit: reduceOnly=True
    """

def exitEmergency(spotExchange, futuresExchange, symbol: str,
                  spotSide: str, futuresSide: str,
                  quantity: float, algoIds: list[int],
                  baseUrl: str, apiKey: str, apiSecret: str) -> dict:
    """
    FR flip → market order langsung, no waiting.
    1. Cancel SL/TP
    2. Market order both legs
    3. Return trade result dict
    """
```

---

## Critical Notes

- Algo orders WAJIB via `requests` langsung — ccxt tidak support
- `algoType` case-sensitive: `"CONDITIONAL"` bukan `"conditional"`
- Response field `orderType` (di response) ≠ request param `type`
- Min notional futures: $50 — validate sebelum order
- Order fill: check both `"filled"` dan `"closed"` status
- Simpan `midPrice` saat order dikirim — untuk actual cost calculation nanti
