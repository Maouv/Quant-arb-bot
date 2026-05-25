# Funding Rate Arbitrage Bot

A delta-neutral quantitative trading system for capturing funding rate spreads on Binance perpetual futures. Currently in Phase 4 paper trading validation on testnet.

## Project Overview

**Purpose:** Validate that backtested edge translates to live execution by measuring actual fill rates, real-time costs, and bot correctness over 4-6 weeks of continuous operation.

**Core Strategy:** Delta-neutral arbitrage — long spot + short futures (or vice versa) when funding rate magnitude exceeds entry threshold. Profit comes from funding payments, not price movement.

**Architecture:** Single Python process, clock-aligned 5-minute cycles, batch API calls for efficiency, dual-exchange (spot + futures) coordination with algorithmic stop-loss/take-profit protection.

**Current State:** Phase 4 of 5-phase pipeline. Phases 0-3 (research, viability analysis, math framework, backtesting) completed in separate repository. Phase 5 (mainnet deployment) requires passing all validation metrics.

## System Architecture

Data Flow per Cycle:
1. **Fetch** (batch): premiumIndex (FR), bookTicker (bid/ask), positionRisk (open positions)
2. **Monitor**: Check exit signals for each open position → dispatch exit if needed
3. **Scan**: Filter candidates by FR threshold, net expected profit
4. **Execute**: Place simultaneous spot+futures limit orders, poll fills, attach SL/TP
5. **Cleanup**: Orphan detection, unprotected position handling, state persistence

## Repository Structure

```
quant-arb-bot/
├── src/
│   ├── config/       # All parameters, universe, secrets loader
│   ├── exchange/     # ccxt factory, raw API auth, endpoints
│   ├── market/       # Data fetching, cost calculation, slippage estimation
│   ├── strategy/     # Entry/exit signals, risk guards
│   ├── execution/    # Order placement, monitoring, algo orders (SL/TP)
│   ├── position/     # Position tracking, orphan detection, balance management
│   ├── bot/          # Main loop, startup, cycle orchestration
│   ├── discord_ui/   # Discord bot for monitoring/alerting
│   ├── ai/           # AI assistant for natural language queries
│   └── logging_/     # Logging setup, trade log persistence
├── tests/
├── plan/             # Implementation specifications
├── phase4-handoff/   # Context from Phase 3 research
├── logs/             # Runtime logs, trade journal, cost cache
└── deps/             # Requirements files
```

Module responsibilities: `config/` — constants only. `exchange/` — ccxt setup + HMAC raw API. `market/` — batch fetch, cost model, slippage, rolling avg cache. `strategy/` — entry/exit signals, risk guards. `execution/` — order lifecycle, SL/TP via raw API. `position/` — state tracking, orphan detection, sizing. `bot/` — orchestration. `discord_ui/` — slash commands, alerts. `ai/` — OpenAI-compatible queries.

## Quantitative Models

**Entry:** |FR| ≥ 0.05% (raw: ≥ 0.0005). **Exit normal:** |FR| < 0.02%. **Exit emergency:** FR sign flip.

**Position side:** FR > 0 → long spot + short futures. FR < 0 → short spot + long futures.

**Net expected profit:** π = |FR × 100| − C_rt, where C_rt = FEE_RT(0.08%) + 2×spread_spot + 2×spread_fut + 2×slippage_spot + 2×slippage_fut + basis. Entry only if π > 0.01%.

**Slippage:** scan orderbook asks until cumulative notional ≥ sizePerPair/2 (~$150), record worst fill price.

**Cost cache:** rolling 100-sample avg per symbol. Cold-start fallback = FEE_RT (0.08%) — not DEFAULT_COST_TIER, to avoid cold-start deadlock where no coin is profitable until first trade occurs.

**Position sizing:** effectiveCapital = balance × (1 − 0.40), sizePerPair = effectiveCapital / 6.

**Risk guards:** cost spike > 3× rolling avg → skip symbol. >50% coins with cost > 2× avg → broad market stress → skip all entries. Blackout: 5 min before settlement (UTC 0:00, 8:00, 16:00).

**Backtest (2022-2024):** $834 net from $3,000, ~28% APY, max DD $5.96, win/loss 13.9:1. OOS 2025: $497 net.

**Phase 4 PASS criteria:** APY ≥ 13.2%, APY ≥ 14% (50% of backtest), max DD < $50, fill rate ≥ 60%.

## Dependencies

```
ccxt==4.2.86           # LOCKED — newer versions break testnet URL routing
requests>=2.31.0
python-dotenv>=1.0.0
discord.py>=2.3.0
httpx>=0.27.0
```

## API Endpoints

| Endpoint | Purpose | Weight |
|----------|---------|--------|
| `GET /fapi/v1/premiumIndex` | All coins FR/mark/index | 10 |
| `GET /fapi/v1/ticker/bookTicker` | All coins bid/ask futures | 5 |
| `GET /api/v3/ticker/bookTicker` | All coins bid/ask spot | 2 |
| `GET /fapi/v2/positionRisk` | Open positions | 5 |
| `POST /fapi/v1/algoOrder` | SL/TP placement (raw API) | 1 |
| `DELETE /fapi/v1/algoOrder` | SL/TP cancel — use algoId, NOT orderId | 1 |

Total: ~32 weight/cycle (<1% of 2400/min limit).

## Known Testnet Behaviors & Fixes (2026-05-25)

**Bug fixed — unit mismatch in scanner.py:** `filterCandidates` compared raw decimal FR (e.g. 0.0005) against ENTRY_THRESHOLD (0.05%) without converting to percentage first. Result: `frOk=0` every cycle, bot never entered. Fix: `fr = abs(item["lastFundingRate"]) * 100`.

**Bug fixed — cold-start deadlock in cost_cache.py:** `getRollingAvg` fallback was `DEFAULT_COST_TIER = 0.12%`. With empty cache, no coin was profitable (FR − 0.12% ≤ 0.01% threshold). Bot never traded → cache never populated → permanent deadlock. Fix: cold-start fallback changed to `FEE_RT = 0.08%` (theoretical minimum cost = fees only).

**Bug fixed — spot demo exchange in factory.py:** ccxt `binance` class calls `sapi/v1/capital/config/getall` in `fetch_currencies()` during every `load_markets()`. This endpoint does not exist on `demo-api.binance.com` → `-2008 Invalid Api-Key ID` on all spot order attempts. Fix: `exchange.fetch_currencies = lambda params={}: {}` to skip the unreachable endpoint.

**Demo spot behavior:** All limit orders fill instantly (status `FILLED` on creation). Cancel returns `-2011 Unknown order` because order no longer exists in book. This is expected demo server behavior — `_cancelSafe` already handles it gracefully.

**Discord stale commands:** `vc` and `whoami` commands from a previous bot version persisted on Discord's servers. Fix: added `bot.tree.error` handler for `CommandNotFound`, and `on_ready` now clears global commands when guild-scoped sync is active.

**Spot demo keys:** API keys for demo-api.binance.com are created at binance.com/api-management (same as mainnet keys). They are NOT from testnet.binancefuture.com. Spot and futures demo use the same key management portal but different endpoints.

## Engineering Style

Python 3.12, strict mypy. camelCase functions/variables, PascalCase classes, UPPER_SNAKE constants. Max 30 lines/function, 150 lines/file. All parameters in `config/settings.py`. No `print()`, no bare `except:`. Type aliases via `type` keyword.

Trading bot: synchronous. Discord bot: async. Run as separate processes, share state via files.

Bot must not crash — all errors logged, cycle continues:
```python
try:
    result = exchange.someCall()
except ccxt.NetworkError as e:
    logger.error("Network: %s", e)
except ccxt.ExchangeError as e:
    logger.error("Exchange: %s", e)
except Exception as e:
    logger.critical("Unexpected: %s", e, exc_info=True)
```

State: in-memory `botState` dict + `logs/trades.jsonl` (append-only) + `logs/cost_cache.json` (rolling avg). On restart: reconcile API positions vs trade log, place emergency SL if missing.

## Operation

```bash
python -m src.bot.main          # trading bot
python -m src.discord_ui.bot    # discord UI (separate process)
pytest tests/ -v --cov=src --cov-fail-under=80
ruff check . && mypy .
```

Secrets: `~/.secret/quant-arb-bot/.env`

Required: `BINANCE_TESTNET_KEY`, `BINANCE_TESTNET_SECRET`, `BINANCE_TESTNET_SPOT_KEY`, `BINANCE_TESTNET_SPOT_SECRET`, `BINANCE_API_KEY`, `BINANCE_API_SECRET`, `DISCORD_BOT_TOKEN`, `DISCORD_USER_ID`, `DISCORD_GUILD_ID`, `AI_BASE_URL`, `AI_API_KEY`, `AI_MODEL`.

## Constraints & Known Weaknesses

Locked parameters (no change without governance): entry 0.05%, exit 0.02%, max pairs 6, buffer 40%.

Universe limited to 8h funding interval coins — 4h coins excluded. No position rebalancing. Single exchange (Binance only).

Weaknesses: regime dependency (low FR months near-zero profit), short-hold fragility (≤3 settlements aggregate loss — structural), option-like payoff (many small losses, few large wins — expected, do not fix).

## Documentation

- `plan/00-framework.md` — implementation rules
- `plan/04-strategy-risk.md` — signal logic, risk guards
- `plan/05-execution.md` — order placement, algo orders
- `plan/07-bot-orchestration.md` — cycle flow, state management
- `plan/12-edge-cases-gotchas.md` — common pitfalls
- `phase4-handoff/05-validation-findings.md` — API corrections, testnet issues

*Phase 4 paper trading. Not for production until all metrics pass and governance review complete.*
