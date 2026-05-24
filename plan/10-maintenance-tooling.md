# 10 — MAINTENANCE & TOOLING

---

## Dev Dependencies

```
ruff>=0.4.0           # linter + formatter (replaces flake8, isort, black)
mypy>=1.10.0          # static type checking
bandit>=1.7.0         # security scanner (hardcoded secrets, unsafe patterns)
pytest>=8.0.0         # test runner
pytest-asyncio>=0.23  # async test support (untuk discord/ai tests)
pytest-cov>=5.0.0     # coverage report
```

Tambah ke `requirements-dev.txt` (terpisah dari `requirements.txt` production).

---

## Ruff Config (pyproject.toml)

```toml
[tool.ruff]
target-version = "py312"
line-length = 100

[tool.ruff.lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "N",    # pep8-naming
    "UP",   # pyupgrade
    "B",    # flake8-bugbear
    "SIM",  # flake8-simplify
    "RET",  # flake8-return
    "TCH",  # flake8-type-checking
]
ignore = [
    "N806",  # camelCase variable (kita pakai camelCase by design)
    "N802",  # camelCase function name
    "N815",  # camelCase class variable
]

[tool.ruff.lint.isort]
known-first-party = ["config", "exchange", "market", "strategy", "execution", "position", "logging_", "bot", "discord_ui", "ai"]
```

---

## Mypy Config (pyproject.toml)

```toml
[tool.mypy]
python_version = "3.12"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
no_implicit_optional = true

[[tool.mypy.overrides]]
module = ["ccxt.*", "discord.*"]
ignore_missing_imports = true
```

---

## Bandit Config (pyproject.toml)

```toml
[tool.bandit]
exclude_dirs = ["tests", ".venv"]
skips = ["B101"]  # assert OK — kita pakai untuk mainnet guard
```

Bandit checks yang paling relevan untuk project ini:
- B105/B106: hardcoded passwords/secrets
- B108: insecure temp file
- B301/B302: pickle usage (jangan pakai)
- B501: requests tanpa verify (kita selalu verify=True)
- B603/B607: subprocess injection (kita tidak pakai subprocess)

---

## Pytest Coverage Config (pyproject.toml)

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"

[tool.coverage.run]
source = ["config", "exchange", "market", "strategy", "execution", "position", "bot"]
omit = ["tests/*", ".venv/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
skip_empty = true
```

---

## Pre-commit Hooks (.pre-commit-config.yaml)

```yaml
repos:
  - repo: local
    hooks:
      - id: ruff-check
        name: ruff check
        entry: ruff check --fix
        language: system
        types: [python]
      - id: ruff-format
        name: ruff format
        entry: ruff format
        language: system
        types: [python]
      - id: mypy
        name: mypy
        entry: mypy
        language: system
        types: [python]
        pass_filenames: false
      - id: bandit
        name: bandit
        entry: bandit -q
        language: system
        types: [python]
```

---

## Commands Cheat Sheet

```bash
# Lint
ruff check .

# Auto-fix lint issues
ruff check --fix .

# Format
ruff format .

# Type check
mypy .

# Security scan
bandit -r config/ exchange/ market/ strategy/ execution/ position/ bot/ discord_ui/ ai/ -q

# Tests with coverage
pytest tests/ -v --cov=. --cov-report=term-missing

# Coverage target: 90%+ untuk strategy/ dan execution/
pytest tests/ --cov=strategy --cov=execution --cov-fail-under=90

# All checks (run before commit)
ruff check . && ruff format --check . && mypy . && bandit -r . -q && pytest tests/ -v
```

---

## Bug Handling Protocol

### Severity Classification

| Level | Criteria | Response Time |
|-------|----------|---------------|
| P0 — Critical | Unprotected position, orphan order, bot crash loop | Immediate fix |
| P1 — High | Wrong entry/exit, incorrect cost calc, SL/TP not placed | < 1 hour |
| P2 — Medium | Logging error, Discord bot down, cost cache stale | < 24 hours |
| P3 — Low | Formatting, non-critical warning, cosmetic | Next maintenance window |

### Bug Fix Workflow

```
1. REPRODUCE
   - Check logs/bot.log for error context
   - Check logs/trades.jsonl for affected trades
   - Identify exact cycle + timestamp

2. ISOLATE
   - Which module? (market/ execution/ position/ strategy/)
   - Which function?
   - What input caused it?

3. WRITE FAILING TEST
   - Reproduce bug as unit test BEFORE fixing
   - Test must fail with current code

4. FIX
   - Minimal change — fix root cause, not symptom
   - No unrelated changes in same commit

5. VERIFY
   - Failing test now passes
   - All existing tests still pass
   - ruff check + mypy pass

6. DEPLOY
   - Commit with message: "fix(module): description [P0/P1/P2/P3]"
   - Restart bot if P0/P1
```

---

## Error Handling Patterns

### Pattern 1 — API Call Wrapper

```python
def safeApiCall(callable, *args, fallback=None, context: str = "") -> Any:
    """
    Wrap any exchange API call.
    Log error with context, return fallback on failure.
    Bot never crashes from API errors.
    """
    try:
        return callable(*args)
    except ccxt.NetworkError as e:
        logger.warning(f"Network error [{context}]: {e}")
        return fallback
    except ccxt.ExchangeError as e:
        logger.error(f"Exchange error [{context}]: {e}")
        return fallback
    except Exception as e:
        logger.critical(f"Unexpected [{context}]: {e}", exc_info=True)
        return fallback
```

### Pattern 2 — Retry with Backoff (hanya untuk network errors)

```python
def retryOnNetwork(callable, maxRetries: int = 3, 
                   baseDelay: float = 2.0, context: str = "") -> Any:
    """
    Retry on NetworkError only. Exponential backoff.
    Raise after maxRetries exhausted.
    """
```

### Pattern 3 — Critical Path Guard

```python
# Untuk operasi yang HARUS berhasil (e.g. emergency SL placement):
def ensureStopLoss(symbol, side, qty, triggerPrice, ...) -> int:
    """
    Retry sampai berhasil atau 5 attempts.
    Kalau gagal semua → log CRITICAL + alert via Discord.
    TIDAK return None — raise jika benar-benar gagal.
    """
```

### Error Categories

| Category | Example | Action |
|----------|---------|--------|
| Transient | Network timeout, rate limit | Retry next cycle |
| Recoverable | Insufficient balance, min notional | Log, skip entry, continue |
| Data integrity | Trade log corrupt, cost cache invalid | Rebuild from API state |
| Critical | No SL on position, orphan > 1 settlement | Immediate fix + alert |
| Fatal | API key revoked, exchange maintenance | Stop bot, alert, wait |

---

## Refactoring Guidelines

### When to Refactor

- File > 120 lines → split
- Function > 25 lines → extract
- Same logic in 2+ places → extract to shared module
- Test is hard to write → code is too coupled
- Bug fix requires understanding 3+ files → responsibility unclear

### How to Refactor

```
1. Ensure tests cover current behavior
2. Make structural change (move/split/rename)
3. Verify all tests still pass
4. Commit structural change SEPARATELY from behavior change
```

### Refactor Signals (code smells)

| Smell | Fix |
|-------|-----|
| God function (does 5 things) | Split into focused functions |
| Deep nesting (3+ levels) | Early return, extract helper |
| Boolean parameter changes behavior | Split into 2 functions |
| Comment explains "what" not "why" | Rename to be self-documenting |
| Same try/except in 5 places | Extract wrapper pattern |
| Module imports 8+ siblings | Likely wrong responsibility boundary |

---

## Monitoring & Alerting (via Discord)

Bot auto-posts ke designated Discord channel:

| Event | Channel | Urgency |
|-------|---------|---------|
| Bot started/stopped | #bot-status | Info |
| Trade entry/exit | #trades | Info |
| Emergency exit (FR flip) | #alerts | High |
| Unprotected position detected | #alerts | Critical |
| Orphan order cancelled | #alerts | Medium |
| Manipulation event | #alerts | High |
| Bot crash/restart | #alerts | Critical |
| Cost spike broad market | #bot-status | Medium |

Implementation: tambah `discord_ui/alerts.py` (~40 lines) — webhook-based, tidak perlu bot online.

```python
async def sendAlert(webhookUrl: str, level: str, message: str) -> None:
    """Fire-and-forget alert via Discord webhook. Non-blocking."""
```

---

## Commit Message Convention

```
type(scope): description

Types:
  feat     — new feature
  fix      — bug fix
  refactor — structural change, no behavior change
  test     — add/update tests
  docs     — documentation
  chore    — tooling, deps, config

Scope: module name (config, market, execution, position, strategy, bot, discord, ai)

Examples:
  feat(execution): add partial fill handling
  fix(position): use v2 positionRisk endpoint
  refactor(market): split scanner into scanner + cost_calculator
  test(strategy): add blackout window edge cases
```

---

## Health Checks (automated, setiap cycle)

```python
def runHealthChecks(botState: dict) -> list[str]:
    """
    Return list of issues (empty = healthy).
    Checks:
    1. All positions have SL/TP
    2. No orphan orders
    3. Cost cache not stale (updated within last hour)
    4. Balance sufficient for at least 1 pair
    5. Last successful API call < 5 minutes ago
    6. Trade log writable
    """
```

Kalau issues non-empty → log WARNING + Discord alert.
