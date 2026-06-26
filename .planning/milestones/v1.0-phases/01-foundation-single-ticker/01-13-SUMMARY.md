---
phase: 01-foundation-single-ticker
plan: 13
subsystem: compute + output
tags: [compute, pct-change, volume-color, layout, gap-fix]
requires: [01-07, 01-11, 01-12]
provides: [COMP-06, SHEET-07, COLOR-06]
affects: [main_run pipeline, sheet column layout, color dispatch]
tech-stack:
  patterns: [pandas pct_change, expanding stats, trend bucket, sigma bucket]
key-files:
  modified:
    - src/stocksig/compute/stats.py
    - src/stocksig/main_run.py
    - src/stocksig/output/sheet_per_ticker.py
    - tests/test_stats.py
    - tests/test_smoke_end_to_end.py
decisions:
  - Volume cell color uses TechBucket via decide_trend_bucket(Volume_pct_change) so first row (NaN pct) gracefully falls back to DEFAULT
  - Hidden rule unchanged — `_median/_std` suffix auto-hides Volume_pct_change_median/_std with no new pattern
metrics:
  duration: ~30 min
  completed: 2026-05-21
---

# Phase 1 Plan 13: pct-change columns + Volume color Summary

Adds `Close_pct_change` (K) and `Volume_pct_change` (M) columns, recolors `Volume` cell by Volume_pct_change sign, and swaps the obsolete `Volume_median/_std` for `Volume_pct_change_median/_std`. Column count 68 → 70.

## Tasks Completed

| # | Task                                           | Commit  |
|---|------------------------------------------------|---------|
| 1 | compute: add_pct_change_columns helper         | 6a0e494 |
| 2 | main_run pipeline + DATA_COLS swap             | 957a34d |
| 3 | sheet layout 68→70 + headers + colors          | 50fe66a |
| 4 | tests (5 new + col-count + hidden updates)     | 49e1e39 |

## Deviations from Plan

None — plan executed exactly as written.

## Verification Samples (output_new/portfolio_20260521.xlsx)

- `max_column = 70`
- `Close_pct_change` @ **K6** = `0.01097` `0.00%` → **GREEN_800 bold** (positive trend)
- `Volume` @ **L6** = `38,188,800` `#,##0` → **RED_800** (Volume_pct_change<0 row)
- `Volume_pct_change` @ **M6** = `-0.09599` `0.00%` → **DEFAULT** (deviation within ±1σ from `median=-0.01731`, `std=0.36127` — sigma bucket correctly DEFAULT)
- `Volume_pct_change_median` @ **N6** = `-0.01731` `0.00%` **hidden**
- Headers row-5: "종가 등락률" (K), "거래량 등락률" (M)
- 42/42 tests GREEN

## Self-Check: PASSED

- src/stocksig/compute/stats.py: FOUND (add_pct_change_columns present)
- src/stocksig/main_run.py: FOUND (Volume_pct_change in DATA_COLS)
- src/stocksig/output/sheet_per_ticker.py: FOUND (70-col layout)
- tests/test_stats.py: FOUND (test_pct_change_columns, test_expanding_volume_pct_change)
- tests/test_smoke_end_to_end.py: FOUND (4 new smoke tests)
- Commits: 6a0e494, 957a34d, 50fe66a, 49e1e39 — all in git log
