# PHASE 4 — IMPLEMENTATION FRAMEWORK

## Konteks

Ini adalah Phase 4 dari 5-phase pipeline:
- Phase 0-3: Research & backtest (SELESAI, repo `/root/quant-arb/`)
- **Phase 4: Paper trading validation (SEKARANG, repo `/root/quant-arb-bot/`)**
- Phase 5: Live trading (BELUM)

Phase 4 bukan tentang profit. Tujuannya validate 3 hal:
1. Fill rate actual per coin
2. Cost actual per coin real-time
3. Bot execution correctness

---

## Rules untuk AI Implementor

### WAJIB

1. Ikuti function signatures PERSIS seperti di plan file yang relevan
2. Naming: camelCase functions/variables, PascalCase classes, UPPER_SNAKE constants
3. Max 30 lines per function, max 150 lines per file
4. Type hints pada semua function parameters dan return
5. Docstring pada semua functions
6. Tidak ada `print()` — pakai `logging`
7. Tidak ada bare `except:` — selalu specific exception
8. Tidak ada magic numbers — semua dari `config/settings.py`
9. Setiap file harus punya `__init__.py` di package-nya
10. Import order: stdlib → third-party → local (ruff isort handles this)

### DILARANG

1. Jangan tambah fungsi yang tidak ada di plan
2. Jangan ubah function signatures dari plan
3. Jangan introduce library baru di luar requirements.txt
4. Jangan buat abstraction layer yang tidak diminta (no base classes, no metaclasses, no decorators kecuali di plan)
5. Jangan "improve" atau "optimize" — implementasi exact dari spec
6. Jangan ubah parameter LOCKED (entry 0.05%, exit 0.02%, max_pairs 6, buffer 40%)
7. Jangan merge spot + futures exchange jadi satu instance
8. Jangan pakai ccxt untuk algo orders — wajib raw requests
9. Jangan pakai `/fapi/v1/positionRisk` — wajib v2
10. Jangan pakai `stopPrice` atau `orderType` untuk algo orders — pakai `triggerPrice` + `algoType` + `type`

### KALAU RAGU

- Cek `phase4-handoff/03-api-reference.md` untuk endpoint details
- Cek `phase4-handoff/05-validation-findings.md` untuk koreksi dari testing
- Kalau plan tidak cover sesuatu → tanya, jangan assume

### TYPE HINTS — Plan vs Implementasi

Plan menggunakan shorthand untuk keterbacaan. Implementasi HARUS pakai full type args (mypy strict).

```python
# Plan tulis (shorthand):
def fetchPremiumIndex(...) -> list[dict]:
def fetchBookTickerFutures(...) -> dict[str, dict]:

# Implementasi wajib (full type args):
def fetchPremiumIndex(...) -> list[dict[str, str]]:
def fetchBookTickerFutures(...) -> dict[str, dict[str, float]]:
def estimateSlippage(asks: list[list[str]], ...) -> float:
```

Kalau nested type terlalu verbose, gunakan `type` alias (Python 3.12) di atas file:

```python
type BookTicker = dict[str, float]       # {bid, ask, bidQty, askQty}
type PremiumEntry = dict[str, str]       # raw strings dari API response
```

Jangan pakai `TypeAlias` dari `typing` — itu Python 3.9 style. Kita Python 3.12.
Jangan buat `types.py` tersendiri — premature untuk Phase 4.

---

## Sesi-per-Sesi Guide

### Sesi 1 — Foundation
**Buat:** src/__init__.py, src/config/__init__.py, src/config/settings.py, src/config/universe.py, src/config/secrets.py, src/exchange/__init__.py, src/exchange/endpoints.py, src/logging_/__init__.py, src/logging_/setup.py, deps/requirements.txt, deps/requirements-dev.txt, pyproject.toml, .gitignore (update)
**Baca:** plan/01-overview.md + plan/02-config-exchange.md + plan/10-maintenance-tooling.md
**Verify:** `ruff check . && mypy .`

### Sesi 2 — Exchange Layer
**Buat:** src/exchange/factory.py, src/exchange/auth.py
**Baca:** plan/02-config-exchange.md + plan/13-rate-limits.md + phase4-handoff/03-api-reference.md
**Verify:** `ruff check . && mypy . && python -c "from src.exchange.factory import createFuturesExchange"`

### Sesi 3 — Market Data
**Buat:** src/market/__init__.py, src/market/slippage.py, src/market/cost_calculator.py, src/market/cost_cache.py, src/market/scanner.py
**Baca:** plan/03-market-data.md + phase4-handoff/03-api-reference.md
**Verify:** `ruff check . && mypy . && pytest tests/test_cost_calculator.py -v` (tulis test juga)

### Sesi 4 — Strategy Logic
**Buat:** src/strategy/__init__.py, src/strategy/signal.py, src/strategy/risk_guard.py
**Baca:** plan/04-strategy-risk.md
**Verify:** `ruff check . && mypy . && pytest tests/test_signals.py tests/test_risk_guard.py -v`

### Sesi 5 — Position Management
**Buat:** src/position/__init__.py, src/position/balance.py, src/position/tracker.py, src/position/orphan_checker.py
**Baca:** plan/06-position-logging.md + plan/13-rate-limits.md + phase4-handoff/03-api-reference.md
**Verify:** `ruff check . && mypy .`

### Sesi 6 — Execution
**Buat:** src/execution/__init__.py, src/execution/algo_order.py, src/execution/order_placer.py, src/execution/order_monitor.py, src/execution/exit_handler.py
**Baca:** plan/05-execution.md + plan/13-rate-limits.md + phase4-handoff/03-api-reference.md + phase4-handoff/05-validation-findings.md
**Verify:** `ruff check . && mypy . && pytest tests/test_executor.py -v` (testnet)

### Sesi 7 — Trade Logging
**Buat:** src/logging_/trade_log.py
**Baca:** plan/06-position-logging.md
**Verify:** `ruff check . && mypy .`

### Sesi 8 — Bot Orchestration
**Buat:** src/bot/__init__.py, src/bot/main.py, src/bot/startup.py, src/bot/cycle.py
**Baca:** plan/07-bot-orchestration.md + plan/11-pipeline-reference.md + plan/13-rate-limits.md
**Verify:** `ruff check . && mypy . && python -m src.bot.main` (run 2-3 cycles, check logs)

### Sesi 9 — Discord + AI
**Buat:** src/discord_ui/__init__.py, src/discord_ui/bot.py, src/discord_ui/commands.py, src/discord_ui/formatter.py, src/discord_ui/alerts.py, src/ai/__init__.py, src/ai/client.py, src/ai/context_builder.py, src/ai/prompts/system.md
**Baca:** plan/08-discord-ai.md + plan/prompts/system.md
**Verify:** `ruff check . && mypy . && python -m src.discord_ui.bot` (test slash commands)

### Sesi 10 — Tests & Polish
**Buat:** tests/test_signals.py, tests/test_risk_guard.py, tests/test_cost_calculator.py, tests/test_executor.py
**Baca:** plan/09-tests-validation.md
**Verify:** `pytest tests/ -v --cov=. --cov-report=term-missing && bandit -r . -q`

---

## Dependency Graph (jangan loncat)

```
Wave 1 (config, logging)
  ↓
Wave 2 (exchange)
  ↓
Wave 3 (market) ← depends on exchange
  ↓
Wave 4 (strategy) ← depends on market (CostCache type)
  ↓
Wave 5 (position) ← depends on exchange
  ↓
Wave 6 (execution) ← depends on exchange + market + position
  ↓
Wave 7 (trade log) ← standalone
  ↓
Wave 8 (bot) ← depends on ALL above
  ↓
Wave 9 (discord + ai) ← depends on position + logging + config
  ↓
Wave 10 (tests) ← depends on ALL above
```

Jangan implement wave N sebelum wave N-1 verified clean.

---

## Prompt Template untuk Setiap Sesi

```
Implementasi [wave X] untuk quant-arb-bot Phase 4.

Files yang harus dibuat:
- [list files]

Ikuti spec PERSIS dari plan berikut:
[paste isi plan file yang relevan]

Rules:
- camelCase functions/vars, PascalCase classes, UPPER_SNAKE constants
- Type hints + docstring wajib
- Max 30 lines/function, 150 lines/file
- Tidak ada print(), bare except, magic numbers
- Jangan tambah fungsi di luar spec
- Jangan "improve" — implementasi exact

Reference API (kalau relevan):
[paste bagian 03-api-reference yang relevan SAJA, bukan semua]
```

---

## Validation Checklist (akhir semua sesi)

```
□ ruff check . → 0 errors
□ ruff format --check . → 0 changes needed
□ mypy . → 0 errors
□ bandit -r . -q → 0 high/medium issues
□ pytest tests/ -v → all pass
□ pytest --cov --cov-fail-under=80 → pass
□ Bot runs 24h tanpa crash
□ Trade log populated
□ Discord bot responds
□ AI /ask returns coherent response
```
