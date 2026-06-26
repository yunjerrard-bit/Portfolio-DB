---
phase: 01-foundation-single-ticker
plan: 08
subsystem: output/sheet_per_ticker
tags: [xlsxwriter, hidden-column, ui, gap-fix]
requires: [01-04, 01-07]
provides: [SHEET-07 hidden default columns]
affects: [src/stocksig/output/sheet_per_ticker.py, tests/test_smoke_end_to_end.py]
tech-stack:
  patterns: [XlsxWriter set_column hidden option, range-aware openpyxl column dimension lookup]
key-files:
  modified:
    - src/stocksig/output/sheet_per_ticker.py
    - tests/test_smoke_end_to_end.py
decisions:
  - "Hide *_median / *_std with second set_column call after bulk width — last-write-wins semantics of XlsxWriter."
  - "Test uses range-aware helper (cd.min ≤ idx ≤ cd.max) instead of column_dimensions[letter] dict access — openpyxl returns defaultdict entries that miss the actual stored ranges."
metrics:
  duration: ~6min
  completed: 2026-05-21
---

# Phase 01 Plan 08: Hide *_median / *_std Columns Summary

One-liner: 시각적 정돈 — `*_median`, `*_std` 컬럼을 모두 hidden 처리해 사용자가 시트 진입 시 핵심 데이터(OHLCV·EMA·DIFF·dailychg·Stoch·RSI)만 보이고, 통계 컬럼은 Excel 컬럼 헤더에서 펼치기로 접근.

## Tasks

| # | Description | Commit |
|---|---|---|
| 1 | Add hidden loop after bulk `set_column` in `write_sheet_for_ticker` | b81c0a9 |
| 2 | Add `test_median_std_columns_hidden` smoke test (range-aware lookup) | d3538ff |

## Verification

- 30 / 30 tests GREEN (29 prior + 1 new).
- `python -m uv run python main.py` regenerated `output/portfolio_20260521.xlsx`.
- Sample inspection (regenerated file):
  - cols 1-2 (Date, Close): hidden=False
  - cols 3-4 (Close_median, Close_std): hidden=True
  - cols 5 (High): hidden=False
  - cols 6-7 (High_median, High_std): hidden=True
  - cols 74-76 (Stoch_%K, Stoch_%D, RSI): hidden=False
- Total: 26 hidden ranges covering 50 columns; 26 visible ranges covering 26 columns.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Test infrastructure bug] Range-aware ColumnDimension lookup**
- **Found during:** Task 2 verification
- **Issue:** `ws.column_dimensions[letter]` returns a freshly-created defaultdict entry with `hidden=False, width=13` when the letter is not an explicit dict key. XlsxWriter merges consecutive `set_column` ranges (e.g. cols 3-4 share one ColumnDimension keyed by `C`, so `D` is missing).
- **Fix:** Helper iterates stored `ColumnDimension.values()` and checks if Excel col index falls inside any `(min, max)` range. Captures actual XML state regardless of merging.
- **Files modified:** tests/test_smoke_end_to_end.py
- **Commit:** d3538ff

## Self-Check: PASSED

- src/stocksig/output/sheet_per_ticker.py: FOUND
- tests/test_smoke_end_to_end.py: FOUND
- Commits b81c0a9, d3538ff: FOUND
- xlsx regenerated: output/portfolio_20260521.xlsx
