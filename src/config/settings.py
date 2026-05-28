"""All configuration constants. No logic, only values."""

# Mode
USE_TESTNET: bool = True
CONFIRM_MAINNET: bool = False

# Strategy (LOCKED — do not change without governance)
ENTRY_THRESHOLD: float = 0.05
EXIT_THRESHOLD: float = 0.02

# Portfolio (LOCKED)
# NOTE: TOTAL_CAPITAL is DOCUMENTATION ONLY — sizing must use live balance from API
# See: position/balance.py fetchFuturesBalance()
TOTAL_CAPITAL: float = 3000.0
BUFFER_RATIO: float = 0.40
MAX_PAIRS: int = 6

# Execution
MIN_NOTIONAL_FUTURES: float = 50.0
MIN_SPOT_NOTIONAL: float = 10.0
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

# Discord alerts
DISCORD_ALERT_INTERVAL_SECONDS: int = 60
DISCORD_ALERT_KEYWORDS: tuple[str, ...] = ("ERROR", "CRITICAL", "orphan")

# AI
AI_HTTP_TIMEOUT_SECONDS: float = 120.0
AI_RECENT_TRADES_FOR_CONTEXT: int = 20
AI_TOP_COST_COINS: int = 5
