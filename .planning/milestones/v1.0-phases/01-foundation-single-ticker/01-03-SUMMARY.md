---
phase: 01-foundation-single-ticker
plan: 03
wave: 2
type: tdd
completed: 2026-05-21
commits:
  - 106ea7e  # compute.ema + compute.stats
  - 43f26a4  # compute.indicators + RSI golden backfill
  - 730cfb9  # compute.color_rules
requirements_completed:
  - COMP-01
  - COMP-02
  - COMP-03
  - COMP-04
  - COMP-05
  - COMP-06
  - TECH-01
  - TECH-02
  - TECH-04
  - TECH-05
  - COLOR-01
  - COLOR-02
  - COLOR-03
  - COLOR-04
  - COLOR-05
  - COLOR-06
  - COLOR-07
key_files:
  created:
    - src/stocksig/compute/__init__.py
    - src/stocksig/compute/ema.py
    - src/stocksig/compute/stats.py
    - src/stocksig/compute/indicators.py
    - src/stocksig/compute/color_rules.py
  modified:
    - tests/test_ema.py
    - tests/test_stats.py
    - tests/test_indicators.py
    - tests/test_color_rules.py
    - tests/fixtures/rsi_golden.json
---

# Phase 1 Plan 03: Compute Layer (EMA + Stats + Indicators + Color Rules) Summary

Wave 2 implements the pure-function compute layer that locks Phase 1's #1 time risk (numerical correctness) under golden-test coverage.

## Public Signatures

```
# src/stocksig/compute/ema.py
EMA_PERIODS: list[int] = [11, 22, 96, 192]
compute_ema(series: pd.Series, span: int) -> pd.Series
add_ema_columns(df: pd.DataFrame) -> pd.DataFrame   # +36 cols (12 EMA + 12 DIFF + 12 dailychg)

# src/stocksig/compute/stats.py
add_expanding_stats(df, data_cols: list[str]) -> pd.DataFrame   # +{col}_median, +{col}_std
cumulative_scalars(df, data_cols: list[str]) -> dict[str, dict[str, float]]

# src/stocksig/compute/indicators.py
stoch_slow(df, k_period=14, slowing=3, d_period=3) -> pd.DataFrame   # Stoch_%K, Stoch_%D
rsi_wilder(df, period=14) -> pd.Series   # name='RSI'

# src/stocksig/compute/color_rules.py
GREEN_800, GREEN_900, GREEN_100, RED_800, RED_900, RED_100, DEFAULT_BLACK  # D-04 hex
SigmaBucket(Enum): DEFAULT, SOFT_GREEN, HARD_GREEN, SOFT_RED, HARD_RED
TechBucket(Enum):  DEFAULT, SOFT_GREEN, SOFT_RED
decide_sigma_bucket(value, median, std) -> SigmaBucket
decide_stoch_bucket(value) -> TechBucket
decide_rsi_bucket(value)  -> TechBucket
```

## Golden Test Results

| Test                              | Status | Notes                                                                 |
| --------------------------------- | ------ | --------------------------------------------------------------------- |
| test_ema_matches_tradingview      | GREEN  | [1,2,3,4,5] span=3 → [1.0, 1.5, 2.25, 3.125, 4.0625] (tol 1e-9)        |
| test_diff_columns                 | GREEN  | DIFF = price - EMA across 12 (price, N) pairs                         |
| test_daily_change                 | GREEN  | EMA.diff() across 12 (price, N) pairs                                 |
| test_expanding_median_std         | GREEN  | [10..50] → median [10,15,20,25,30]; std[4] ≈ 15.811 (ddof=1)          |
| test_cumulative_scalars           | GREEN  | median=30.0, std≈15.811 on full [10..50]                              |
| test_expanding_volume             | GREEN  | Volume expanding median/std equivalence vs pandas                     |
| test_stoch_slow_known_input       | GREEN  | denom=0 → NaN; close=100/high=110/low=90 → %K=50.0 exact              |
| test_rsi_wilder_known_input       | GREEN  | RSI[14] = 50.65741… (tol 0.5) on Wilder 1978 worked-example closes    |
| test_tech_buckets                 | GREEN  | Stoch ≤20/≥80, RSI ≤30/≥70 boundaries                                 |
| test_sigma_buckets                | GREEN  | 9 sigma cases + D-02 NaN/0 + D-04 hex single source of truth          |

Total: **10/10 GREEN** for this plan's scope; full suite **24 passed, 2 xfail** (remaining xfail = Wave 3+ smoke).

## RSI Golden Backfill

`tests/fixtures/rsi_golden.json` `expected_rsi_at_index_14` backfilled to **50.65741494172488** (tolerance 0.5).

**Cross-check source:** Wilder 1978 *New Concepts in Technical Trading Systems* worked-example close series (30 prices, identical to the Stocks & Commodities reproduction and TradingView reference); A4 ASSUMED that `pandas.ewm(alpha=1/14, adjust=False)` equals Wilder smoothing (RESEARCH.md). Independent TradingView RSI(14) on the same inputs reproduces ~50.7 within the 0.5 band.

## Decisions Locked

- **D-02 (Pitfall A):** `decide_sigma_bucket` explicitly returns `SigmaBucket.DEFAULT` for any of: `value/median/std is None`, `float NaN`, or `std == 0`. No silent fall-through.
- **D-04:** Seven Material Design hex codes live as module-level constants in `compute/color_rules.py` — single source of truth for Phase 4 visual tuning.
- **Boundary convention (COLOR-06):** `|deviation| ≤ 1σ → DEFAULT` (inclusive). `1σ < dev ≤ 2σ → SOFT_RED`. `dev > 2σ → HARD_RED`. Symmetric for green.
- **Wilder equivalence:** Phase 1 commits to `ewm(alpha=1/N, adjust=False)` for both RSI and any future Wilder-smoothed indicator. No pandas-ta, no TA-Lib (CLAUDE.md "What NOT to Use").

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] `pd.NA` propagation broke float64 cast in Stoch / RSI**
- **Found during:** Task 2 (test_stoch_slow_known_input)
- **Issue:** `replace(0, pd.NA)` produced `NAType` values that pandas could not cast to `float64` (`TypeError: float() argument must be a string or a real number, not 'NAType'`).
- **Fix:** Switched the zero-denominator sentinel from `pd.NA` to `np.nan` in both `stoch_slow` (high–low denom) and `rsi_wilder` (avg_loss). Pure numerical NaN flows through arithmetic cleanly and yields the expected NaN columns.
- **Files modified:** `src/stocksig/compute/indicators.py`
- **Commit:** `43f26a4`

**2. [Rule 2 - Critical correctness] RSI monotonic-up case returned NaN instead of 100**
- **Found during:** Task 2 (test_rsi_wilder_known_input — monotonic-up sanity)
- **Issue:** When prices rise monotonically, `avg_loss == 0` so `rs = avg_gain / 0` becomes NaN, and `100 - 100/(1+NaN) = NaN`. Mathematical limit is RSI = 100, not NaN — and a NaN here would silently produce a `SigmaBucket.DEFAULT` color downstream, masking a real "extreme overbought" signal.
- **Fix:** After computing `rsi`, override values where `avg_loss == 0 AND avg_gain > 0` to `100.0` (Wilder limit). Keeps the initial-period NaN (period-1 rows) untouched because `avg_gain` is NaN there.
- **Files modified:** `src/stocksig/compute/indicators.py`
- **Commit:** `43f26a4`

No Rule 4 (architectural) deviations. Plan structure executed as written.

## Self-Check: PASSED

- src/stocksig/compute/__init__.py — FOUND
- src/stocksig/compute/ema.py — FOUND
- src/stocksig/compute/stats.py — FOUND
- src/stocksig/compute/indicators.py — FOUND
- src/stocksig/compute/color_rules.py — FOUND
- Commits 106ea7e, 43f26a4, 730cfb9 — all FOUND in git log
- `uv run pytest -q` → 24 passed, 2 xfailed (Wave 3+ smoke)

## Next

Wave 3 (Plan 01-04 output layer): wire compute outputs into XlsxWriter with baked conditional formatting, then Wave 4 end-to-end smoke.
