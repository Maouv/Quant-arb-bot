# 01 — OVERVIEW

## Tujuan Phase 4

Validate 3 hal yang tidak bisa divalidasi di backtest:
1. Fill rate actual per coin
2. Cost actual per coin real-time
3. Bot execution correctness

Minimum durasi: 4–6 minggu non-stop.

---

## Dependencies

```
ccxt==4.2.86          # LOCKED
requests>=2.31.0
python-dotenv>=1.0.0
discord.py>=2.3.0
httpx>=0.27.0         # async HTTP untuk AI calls
```

---

## Project Structure

```
quant-arb-bot/
├── src/
│   ├── __init__.py
│   ├── config/
│   │   ├── __init__.py
│   │   ├── settings.py          # semua parameter (LOCKED + tunable)
│   │   ├── universe.py          # UNIVERSE_8H list 100 symbols
│   │   └── secrets.py           # load dari ~/.secrets/quant-arb-bot/.env
│   ├── exchange/
│   │   ├── __init__.py
│   │   ├── factory.py           # create spot + futures ccxt instances
│   │   ├── auth.py              # raw request signing (untuk algo orders)
│   │   └── endpoints.py         # constants: BASE_URLs
│   ├── market/
│   │   ├── __init__.py
│   │   ├── scanner.py           # fetch FR, book ticker, filter candidates
│   │   ├── cost_calculator.py   # hitung total_rt_cost, net_expected
│   │   ├── slippage.py          # estimateSlippage() dari orderbook
│   │   └── cost_cache.py        # rolling average cost per coin
│   ├── strategy/
│   │   ├── __init__.py
│   │   ├── signal.py            # entry/exit signal logic
│   │   └── risk_guard.py        # isCostSpike, isBroadMarketStress, isBlackoutWindow
│   ├── execution/
│   │   ├── __init__.py
│   │   ├── order_placer.py      # place spot+futures limit orders simultaneously
│   │   ├── order_monitor.py     # poll fill status, handle timeout/partial
│   │   ├── algo_order.py        # place/cancel/list SL/TP via raw requests
│   │   └── exit_handler.py      # exit normal (limit) + emergency exit (market)
│   ├── position/
│   │   ├── __init__.py
│   │   ├── tracker.py           # fetch + reconcile open positions
│   │   ├── orphan_checker.py    # detect orphan orders + unprotected positions
│   │   └── balance.py           # fetch balance, compute sizePerPair
│   ├── logging_/
│   │   ├── __init__.py
│   │   ├── setup.py             # configure logging (file + console)
│   │   └── trade_log.py         # append trade records to JSON-lines file
│   ├── discord_ui/
│   │   ├── __init__.py
│   │   ├── bot.py               # Discord bot entrypoint
│   │   ├── commands.py          # slash commands
│   │   ├── formatter.py         # format data ke Discord embeds
│   │   └── alerts.py            # webhook alerts
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── client.py            # OpenAI-compatible API client
│   │   ├── context_builder.py   # build context dari bot state + logs
│   │   └── prompts/
│   │       └── system.md        # system prompt (loaded at runtime)
│   └── bot/
│       ├── __init__.py
│       ├── main.py              # entrypoint — startup sequence + cycle loop
│       ├── cycle.py             # single cycle logic (step 0-5)
│       └── startup.py           # startup checks, reconciliation, clock align
├── tests/
│   ├── test_connectivity.py
│   ├── test_executor.py
│   ├── test_signals.py
│   └── test_risk_guard.py
├── logs/
│   └── .gitkeep
├── deps/
│   ├── requirements.txt         # production deps
│   └── requirements-dev.txt     # dev/test deps
├── plan/                         # ← planning docs (kamu baca ini)
├── phase4-handoff/               # ← handoff docs dari Phase 3
├── pyproject.toml
├── .env.example
└── .gitignore
```

---

## Implementation Order

| Wave | Scope | Files |
|------|-------|-------|
| 1 | Foundation | config/, exchange/endpoints.py, logging_/setup.py |
| 2 | Exchange Layer | exchange/factory.py, exchange/auth.py |
| 3 | Market Data | market/* |
| 4 | Strategy Logic | strategy/* |
| 5 | Position Management | position/* |
| 6 | Execution | execution/* |
| 7 | Trade Logging | logging_/trade_log.py |
| 8 | Bot Orchestration | bot/* |
| 9 | Discord + AI | discord_ui/*, ai/* |
| 10 | Tests | tests/* |

---

## Coding Standards

- Python 3.12, PEP8
- camelCase variables/functions, PascalCase classes, UPPER_SNAKE constants
- Type hints wajib, docstring wajib
- Max 30 lines per function, max 150 lines per file
- Tidak ada `print()` — pakai `logging`
- Tidak ada bare `except:`
- Semua parameter di config — no magic numbers
