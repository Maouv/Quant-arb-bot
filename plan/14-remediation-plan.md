# 14 — REMEDIATION PLAN (Phase 4 → Phase 5 hardening)

Handoff spec for fixing correctness defects in the exit / reconciliation /
orphan-handling pipeline, plus the ccxt-vs-library decision. Written for
execution by a separate model. **Analysis + plan only — no code was changed
when this doc was created.**

Read order before executing: `00-framework.md` (style rules), `05-execution.md`,
`07-bot-orchestration.md`, `04-strategy-risk.md`, `12-edge-cases-gotchas.md`.

Engineering constraints (from `00-framework.md` / README): Python 3.12, strict
mypy, camelCase funcs/vars, PascalCase classes, UPPER_SNAKE consts, max 30
lines/function, 150 lines/file, all params in `config/settings.py`, no
`print()`, no bare `except:`. Bot must never crash — log + continue.

Locked params (do NOT change): entry 0.05%, exit 0.02%, max pairs 6, buffer 40%.

---

## Root-cause summary (why the orphan happens)

Position side per entry: **long spot + short futures** (FR>0 only, per
`scanner.filterCandidates`). SL/TP are placed **only on the futures leg**
(`entry.py` → `placeStopLoss`/`placeTakeProfit`, `slTpSide="buy"`).

Failure chain:
1. Futures SL or TP triggers → Binance auto-closes the **futures** leg only.
2. Spot leg is untouched → futures flat, spot still long = **orphan spot**,
   delta-neutral broken into a naked long.
3. `monitorPositions` iterates only `fetchOpenPositions()` (futures
   positionRisk). Futures gone ⇒ symbol absent ⇒ spot never re-checked.
4. `runOrphanCheck` → `checkOrphanRegularOrders` inspects **open orders only**,
   not balances. A FILLED spot holding is not an open order ⇒ slips through.
5. The one mechanism built for this — `handleManipulationEvent`
   ("futures closed, spot open") — is **disabled** in `cycle/orphan.py`.

Net: **no code path detects "spot balance exists with no paired futures
position."** That is the hole.

---

## Issue register (priority order)

| # | Severity | Area | One-line |
|---|----------|------|----------|
| I1 | CRITICAL | orphan | No sweeper for spot-without-futures; orphan spot never sold |
| I2 | CRITICAL | exit signal | FR-flip detection is dead code (`entryFr` always == `currentFr`) |
| I3 | HIGH | exit | `algoIds=[]` on monitor exit ⇒ SL/TP not cancelled on exit |
| I4 | HIGH | logging | Trade log never updated on exit; `exit_time` stays `""` forever |
| I5 | HIGH | strategy | SL/TP on futures leg *creates* directional risk for delta-neutral |
| I6 | MED | execution | Sequential fill polling ⇒ up to ~60s un-hedged window |
| I7 | MED | auth | Raw `signedRequest` has no recvWindow / no clock-skew adjust (`-1021`) |
| I8 | MED | exit | Spot market fallback not balance-aware (insufficient-balance fail) |
| I9 | LOW | dust | Sub-MIN_SPOT_NOTIONAL residue skipped → permanent dust, dirties PnL |
| I10 | DECISION | infra | ccxt 4.2.86 pin is a liability for mainnet (see §ccxt decision) |

Note on BNB-for-fees: paying fees in BNB keeps spot base-asset qty symmetric
with futures (fee not deducted from base asset) and removes fractional dust —
helps I9, does **not** fix I1 (orphan is structural, not fee-driven). If
adopted, add BNB-balance monitoring (silent fallback to base-asset fee when BNB
runs out re-introduces dust).

---

## I1 — Spot orphan sweeper (CRITICAL)

**Goal:** every cycle, detect any spot base-asset holding ≥ MIN_SPOT_NOTIONAL
whose symbol has **no** open futures position, and market-sell it.

**Where:** re-enable a corrected `handleManipulationEvent` path, driven from
`cycle/orphan.py runOrphanCheck`. The previously-disabled version triggered for
all open positions because it lacked the "futures absent" guard — fix that.

**Spec:**
```
def checkOrphanSpotHoldings(spotExchange, openPositions, universe) -> list[str]:
    """
    For each symbol in universe (or in trade log with open entry):
      baseAsset = symbol[:-4]   # strip USDT
      bal = fetchSpotBalance(spotExchange, baseAsset)
      notional = bal * markPrice  (use last known mark or a fresh ticker)
      if notional >= MIN_SPOT_NOTIONAL and symbol NOT in {p.symbol for openPositions}:
          -> orphan spot, return symbol
    Return list of orphaned spot symbols.
    """
```
Then in `runOrphanCheck`: for each orphaned symbol, market-sell the full free
base balance (reuse the corrected `handleManipulationEvent` body — it already
fetches free balance and market-sells). Log `manipulation_event` / `orphan_spot`
and optionally suspend the symbol N cycles.

**Guard against false positives:** only sweep symbols the bot actually trades
(universe ∩ symbols that had an entry). Do NOT blanket-scan the whole wallet, or
you may dump unrelated balances. This is the bug that got the old version
disabled.

**Acceptance:** simulate futures-closed-but-spot-open (close futures manually on
testnet, leave spot) → next cycle sells the spot leg; a healthy two-leg position
is left untouched.

---

## I2 — Restore FR-flip detection (CRITICAL)

**Problem:** `monitor.py` does `entryFr = pos.get("entryFr", currentFr)`.
positionRisk has no `entryFr` field ⇒ always falls back to `currentFr` ⇒
`isFundingRateFlipped(entryFr, currentFr)` compares equal values ⇒ never fires.

**Fix:** persist and recover the real entry FR.
- On entry it is already written to `trades.jsonl` as `entry_fr`.
- Build a lookup of open entries by symbol → `entry_fr` (and `algo_ids`, see I3)
  from the trade log, keyed to records with empty `exit_time` (depends on I4 so
  closed records are excluded). Pass that map into `monitorPositions`.
- Use the recovered `entry_fr` for `isFundingRateFlipped`.

**Acceptance:** open a position with FR>0, flip FR sign in a stubbed
premiumIndex → `exitEmergency` is dispatched. Unit-test `monitorPositions` with
a fake trade-log map.

---

## I3 — Cancel SL/TP on monitor-driven exit (HIGH)

**Problem:** `monitor.py` passes `"algoIds": []`, so `exitNormal`/`exitEmergency`
never cancel the live SL/TP. They linger until the next orphan-algo sweep,
leaving a window where SL can trigger mid-exit (compounding I1).

**Fix:** recover `algo_ids` from the open trade-log record (same lookup as I2)
and pass the real list into the exit kwargs. `exit_handler` already loops
`for algoId in algoIds: _cancelAlgoSafe(...)`.

**Acceptance:** exit a position → assert `cancelAlgoOrder` called for each stored
algoId; `listOpenAlgoOrders` shows none left for that symbol.

---

## I4 — Update trade log on exit (HIGH)

**Problem:** append-only log, `exit_time` written `""` at entry, never updated.
`reconcilePositions` treats every symbol ever traded as perpetually open
(`logSymbols = {r for r in tradeLog if not r.get("exit_time")}`), so
reconciliation is unusable and the I2/I3 "open entry" lookup is ambiguous
(multiple records per symbol).

**Fix:** add `updateTradeRecord(tradeId, fields, filepath)` in
`logging_/trade_log.py`. Since file is JSON-lines append-only, implement as
read-all → patch matching `trade_id` → rewrite file (small file, fine for Phase
4). On exit, set `exit_time`, `exit_fr`, `hold_settlements`, realized
`gross_pct`/`net_pct`/`net_dollar`, `partial_fill_occurred`.

Keep the "open entry" lookup keyed on `trade_id` with empty `exit_time`. For a
symbol, the open entry = the record with empty `exit_time` (there should be at
most one once this lands).

**Acceptance:** entry then exit → exactly one record for symbol has
`exit_time != ""`; `reconcilePositions` reports zero false "in log not in API".

---

## I5 — Reconsider SL/TP on the futures leg (HIGH, design decision)

**Problem:** price-based SL/TP on a single leg of a delta-neutral pair
*manufactures* directional exposure when it triggers (this is the direct cause
of I1). For funding arb, price moves are hedged by design; a futures-only SL is
protecting against a risk that the hedge already neutralizes, while creating the
orphan risk.

**Options (pick one, document choice):**
- **(A) Remove futures SL/TP entirely.** Rely on FR-based exits (I2) + the
  spot-orphan sweeper (I1). Simplest; aligns with delta-neutral thesis. Removes
  the entire `algoOrder` dependency and the I3 problem.
- **(B) Keep SL/TP but make exit atomic.** If futures SL/TP triggers, the next
  cycle MUST immediately close the spot leg (I1 sweeper handles this). Keep SL/TP
  only as a catastrophe backstop (e.g. exchange outage), with wide triggers.
- **(C) Pair-aware protection.** Replace single-leg SL/TP with a monitor rule
  that closes BOTH legs when combined PnL breaches a threshold.

Recommendation: **(A)** for Phase 4 simplicity, or **(B)** if a hard backstop is
required for mainnet. Avoid leaving it as-is. Whichever is chosen, the
`markPrice * 1.02` SL / `markPrice * 0.95` TP triggers in `entry.py` are
arbitrary and should be justified or removed.

**Acceptance:** documented decision in `04-strategy-risk.md`; if (A), `entry.py`
no longer calls `placeStopLoss`/`placeTakeProfit` and `algo_ids` handling is
simplified.

---

## I6 — Concurrent fill polling (MED)

**Problem:** `entry.py` polls spot to completion (≤60s) **then** futures (≤60s),
serial. On mainnet, fast spot + slow futures = up to 60s un-hedged.

**Fix:** poll both legs in an interleaved loop (single loop, check both each
5s tick), or shorten entry timeout and treat first-leg-filled-second-leg-pending
as the partial-fill path sooner. Keep it synchronous (no asyncio — trading bot
is sync per house style). Reduce the un-hedged window; if futures lags past a
short bound, unwind the filled spot leg via `handlePartialFill`.

**Acceptance:** stub one leg slow → both polled within the same wall-clock
window; un-hedged duration bounded by the shorter timeout.

---

## I7 — Harden raw `signedRequest` (MED)

**Problem:** `exchange/auth.py` builds timestamp from local clock only, no
`recvWindow`. ccxt uses `adjustForTimeDifference: True`; the raw path does not.
Clock skew on the live host → `-1021` on every algo order (SL/TP).

**Fix:** add `recvWindow` (match ccxt's 60000) to params, and offset the
timestamp by the server-time delta (GET `/fapi/v1/time` once at startup, cache
the offset in `botState`, apply in `signedRequest`). If I5 option (A) is chosen
and raw algo orders are removed, I7 may become moot — sequence after I5.

**Acceptance:** inject a synthetic local-clock skew → signed requests still
succeed.

---

## I8 — Balance-aware spot market fallback (MED)

**Problem:** `exit_handler._marketFallback` and `handlePartialFill` sell the
*requested* `quantity` on spot. If free spot balance < quantity (fee dust w/o
BNB), the order fails "insufficient balance". Futures is safe via `reduceOnly`;
spot has no equivalent.

**Fix:** before any spot market-sell on exit/unwind, clamp quantity to actual
free balance via `fetchSpotBalance` and `amount_to_precision` (round down). If
the clamped qty falls below MIN_SPOT_NOTIONAL, treat as dust (see I9).

**Acceptance:** exit with spot balance slightly below requested qty → sell
succeeds with clamped qty, no exchange error.

---

## I9 — Dust policy (LOW)

**Problem:** `monitor._resolveSpotQty` returns `0.0` when residue notional <
MIN_SPOT_NOTIONAL ($10), skipping the spot leg. Residue accumulates as permanent
dust and dirties Phase-4 PnL / fill-rate measurement.

**Fix (choose):**
- Enable **BNB fee payment** (set `BNB` fee asset on spot account) to prevent
  fractional base-asset dust at the source. Add a BNB-balance check to startup
  and a low-BNB alert (Discord). Document that without BNB, dust returns.
- And/or add a periodic dust-sweep that converts residue (Binance `dust-to-BNB`
  endpoint) on a slow cadence.
- Track skipped-dust notional in the trade log so PnL stays honest.

**Acceptance:** after N entries/exits, residual base balances stay below a
documented dust bound; PnL accounts for any skipped dust.

---

## I10 — ccxt vs library decision (mainnet infra)

**Verified facts (2026-05):**
- **2025-12-09 Binance made the Algo Order API mandatory** for futures
  conditional orders (`STOP_MARKET`/`TAKE_PROFIT_MARKET`). Old `/fapi/v1/order`
  now returns **`-4120` "Please use the Algo Order API endpoints instead."**
  (freqtrade issue #12610, ccxt 4.5.20). This repo already uses
  `/fapi/v1/algoOrder` via raw API, so it dodged the trap — but only on the algo
  path; entry/exit orders still go through ccxt.
- ccxt is **pinned at 4.2.86** ("newer break testnet URL routing"). That version
  predates the algo-order mandate and forces the parallel raw-HMAC path.
- python-binance is maintained (v1.0.20+, updates early 2026), Binance-specific,
  native `testnet=True`.
- Official Binance connectors exist: `binance-futures-connector-python` and the
  newer `binance-sdk-derivatives-trading-usds-futures` (~Feb 2026) — fastest to
  track API changes like the algo-order mandate.

**Assessment:** for a single-exchange Binance bot, ccxt's multi-exchange
abstraction is unused while its costs are paid in full (version pin, testnet URL
surgery `fetch_currencies = lambda...` + `urls["api"]` override,
`set_sandbox_mode` forbidden, parallel raw path). The pin is a mainnet liability.

**Recommendation (do NOT big-bang migrate right before mainnet):**
- Ranking for API-change resilience: **official Binance connector > python-binance
  > ccxt-pinned**.
- If migrating: prefer the **official connector** (best correctness for mainnet,
  unifies the two auth paths, removes testnet hacks). python-binance is an
  acceptable middle ground and still better than the ccxt pin.
- Sequence the migration **after** I1–I4 land and Phase-4 metrics pass on the
  current stack, on a branch, behind the existing `USE_TESTNET` switch, with the
  full test suite green. Treat it as its own phase, not bundled with the
  correctness fixes.

**Acceptance:** decision recorded; if migrating, a spike branch places an
entry+exit+SL/TP on testnet through the new library with parity to current
behavior before committing.

---

## Suggested execution order

1. **I4** (trade-log update) — unblocks reliable open-entry lookup.
2. **I2 + I3** (recover entry_fr + algo_ids from log) — depend on I4.
3. **I1** (spot orphan sweeper) — the headline bug; benefits from I2/I3.
4. **I5** (SL/TP design decision) — may simplify I3/I7 depending on choice.
5. **I8 + I6** (exit robustness, un-hedged window).
6. **I7** (raw auth hardening) — skip if I5(A) removes raw algo path.
7. **I9** (dust / BNB policy).
8. **I10** (library migration) — separate phase, post Phase-4 pass.

## Cross-cutting test requirements

- Add/extend unit tests in `tests/` for each fix (project uses pytest, target
  `--cov-fail-under=80`).
- Re-run `ruff check . && mypy .` — must be clean (strict mypy).
- For I1/I2/I3, prefer pure functions taking injected state (trade-log map,
  positions, balances) so they're unit-testable without live exchange calls.
- Manual testnet validation for I1 (close futures, leave spot) and I5 choice.

## Files likely touched

- `src/logging_/trade_log.py` (I4)
- `src/bot/cycle/monitor.py` (I2, I3)
- `src/bot/cycle/orphan.py` + `src/position/orphan_checker.py` (I1)
- `src/execution/exit_handler.py` + `src/execution/order_monitor.py` (I6, I8)
- `src/bot/cycle/entry.py` (I5)
- `src/exchange/auth.py` (I7)
- `src/config/settings.py` (any new threshold consts — all params live here)
- `src/exchange/factory.py` (I10, only if migrating)
- `tests/` (all)
