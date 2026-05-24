# 02 — CONFIG & EXCHANGE

---

## config/settings.py (~80 lines)

Semua constants. Tidak ada logic.

```python
# Mode
USE_TESTNET: bool = True
CONFIRM_MAINNET: bool = False

# Strategy (LOCKED — tidak boleh diubah tanpa governance)
ENTRY_THRESHOLD: float = 0.05   # % |FR| >= ini → entry
EXIT_THRESHOLD: float = 0.02    # % |FR| < ini → exit

# Portfolio (LOCKED)
TOTAL_CAPITAL: float = 3000.0
BUFFER_RATIO: float = 0.40
MAX_PAIRS: int = 6

# Execution
ORDER_TIMEOUT_SECONDS: int = 60
CYCLE_INTERVAL_MINUTES: int = 5
BLACKOUT_MINUTES: int = 5
SETTLEMENT_HOURS_UTC: list[int] = [0, 8, 16]

# Cost model
DEFAULT_COST_TIER: float = 0.12
COST_SPIKE_MULTIPLIER: float = 3.0
BROAD_STRESS_THRESHOLD: float = 0.50
MIN_PROFIT_THRESHOLD: float = 0.01

# Fees
TAKER_FEE: float = 0.04
FEE_RT: float = 0.08

# Balance refresh
BALANCE_REFRESH_INTERVAL: int = 3600
BALANCE_REFRESH_AFTER_TRADE: bool = True

# Rejection criteria
PAPER_APY_ABSOLUTE_FLOOR: float = 13.2
PAPER_APY_RELATIVE_FLOOR: float = 0.50
BACKTEST_APY_MID: float = 28.0

# Excluded
EXCLUDED_SYMBOLS: list[str] = ["NEARUSDT"]
```

---

## config/universe.py (~115 lines)

```python
UNIVERSE_8H: list[str] = [
    "1INCHUSDT", "AAVEUSDT", "ACHUSDT", "ADAUSDT", "ALGOUSDT",
    "APEUSDT", "APTUSDT", "ARBUSDT", "ARPAUSDT", "ARUSDT",
    "ASTRUSDT", "ATOMUSDT", "AVAXUSDT", "BANDUSDT", "BATUSDT",
    "BCHUSDT", "BELUSDT", "BNBUSDT", "BTCUSDT", "C98USDT",
    "CELOUSDT", "CELRUSDT", "CFXUSDT", "CHRUSDT", "CHZUSDT",
    "CKBUSDT", "COMPUSDT", "COTIUSDT", "CRVUSDT", "CTSIUSDT",
    "DASHUSDT", "DOGEUSDT", "DOTUSDT", "DYDXUSDT", "EDUUSDT",
    "EGLDUSDT", "ENSUSDT", "ETCUSDT", "ETHUSDT", "FETUSDT",
    "FILUSDT", "GALAUSDT", "GMXUSDT", "GRTUSDT", "GTCUSDT",
    "HBARUSDT", "HFTUSDT", "HIGHUSDT", "HOTUSDT", "ICPUSDT",
    "IDUSDT", "INJUSDT", "IOSTUSDT", "IOTAUSDT", "IOTXUSDT",
    "JASMYUSDT", "JOEUSDT", "KNCUSDT", "KSMUSDT", "LDOUSDT",
    "LINKUSDT", "LQTYUSDT", "LTCUSDT", "MANAUSDT", "MAVUSDT",
    "MINAUSDT", "MTLUSDT", "NEOUSDT", "ONEUSDT", "OPUSDT",
    "PEOPLEUSDT", "QNTUSDT", "QTUMUSDT", "RLCUSDT", "ROSEUSDT",
    "RSRUSDT", "RUNEUSDT", "SANDUSDT", "SFPUSDT", "SNXUSDT",
    "SOLUSDT", "SPELLUSDT", "SSVUSDT", "STGUSDT", "STXUSDT",
    "SUIUSDT", "SUSHIUSDT", "THETAUSDT", "TRXUSDT", "UNIUSDT",
    "USDCUSDT", "VETUSDT", "WOOUSDT", "XLMUSDT", "XRPUSDT",
    "XVGUSDT", "XVSUSDT", "YFIUSDT", "ZECUSDT", "ZENUSDT",
]  # 100 symbols, 8h funding interval
```

Hardcoded. `fundingIntervalHours` tidak tersedia di API.

---

## config/secrets.py (~20 lines)

```python
def loadSecrets() -> dict[str, str]:
    """
    Load .env dari ~/.secrets/quant-arb-bot/.env
    Return dict: {key_name: value}
    Raise RuntimeError jika file tidak ada.
    """
```

Lokasi: `~/.secrets/quant-arb-bot/.env` — BUKAN di project dir.

---

## exchange/endpoints.py (~15 lines)

```python
BASE_SPOT = "https://api.binance.com"
BASE_FUTURES = "https://fapi.binance.com"
BASE_TESTNET_FUTURES = "https://testnet.binancefuture.com"
BASE_DEMO_SPOT = "https://demo-api.binance.com"  # Binance Demo Mode — key dari demo.binance.com
                                                  # BUKAN testnet.binance.vision (tidak reliable)
```

---

## exchange/factory.py (~50 lines)

```python
def createSpotExchange(testnet: bool = True) -> ccxt.binance:
    """
    Create ccxt spot instance.
    - recvWindow: 60000
    - adjustForTimeDifference: True
    - Testnet: override URL ke demo-api.binance.com (JANGAN pakai set_sandbox_mode)
    - Spot demo key BERBEDA dari futures testnet key (dari demo.binance.com)
    """

def createFuturesExchange(testnet: bool = True) -> ccxt.binanceusdm:
    """
    Create ccxt futures instance.
    - recvWindow: 60000
    - adjustForTimeDifference: True
    - Testnet: override URL ke testnet.binancefuture.com (JANGAN pakai set_sandbox_mode)
    - set_sandbox_mode(True) DILARANG — menyebabkan positionRisk path invalid (-5000)
    """
```

---

## exchange/auth.py (~40 lines)

```python
def signedRequest(method: str, baseUrl: str, endpoint: str,
                  params: dict, apiKey: str, apiSecret: str) -> dict:
    """
    HMAC-SHA256 signed request untuk raw API calls.
    Dipakai oleh algo_order.py (ccxt tidak support algo endpoint).
    
    Steps:
    1. Tambah timestamp ke params
    2. Build query string
    3. Sign dengan HMAC-SHA256
    4. Send request dengan X-MBX-APIKEY header
    5. Raise on HTTP error
    6. Return parsed JSON
    """
```

---

## Critical Notes

- `ccxt==4.2.86` LOCKED — versi baru block testnet futures
- Spot testnet key (`BINANCE_TESTNET_SPOT_KEY`) BERBEDA dari futures testnet key
- Production: spot + futures pakai key yang sama
- `recvWindow: 60000` + `adjustForTimeDifference: True` WAJIB (clock drift VPS)
