---
phase: 01-foundation-single-ticker
plan: 10
subsystem: output/writer + output/sheet_per_ticker
tags: [xlsxwriter, freeze-panes, bold, gap-fix, ui]
requires: [01-04, 01-06, 01-09]
provides: [SHEET-07 freeze panes, SHEET-08 colored cell bold]
affects:
  - src/stocksig/output/writer.py
  - src/stocksig/output/sheet_per_ticker.py
  - tests/test_smoke_end_to_end.py
tech-stack:
  patterns:
    - XlsxWriter Format with bold attribute on colored buckets only
    - XlsxWriter ws.freeze_panes(row, col) → openpyxl 'A6'
key-files:
  modified:
    - src/stocksig/output/writer.py
    - src/stocksig/output/sheet_per_ticker.py
    - tests/test_smoke_end_to_end.py
decisions:
  - "bold=True applied to 6 colored bucket variants (Sigma SOFT/HARD GREEN/RED + Tech SOFT GREEN/RED), each ×4 num_format types — DEFAULT buckets remain non-bold."
  - "freeze_panes(5, 0) chosen so Excel rows 1–5 (ticker, median, std, blank, Korean header) stay visible while scrolling."
  - "Format cache size unchanged (33 keys); only Format object attributes were augmented — no key explosion."
metrics:
  duration: ~5min
  completed: 2026-05-21
---

# Phase 01 Plan 10: Freeze Panes + Bold Colored Cells Summary

One-liner: UI polish — 1~5행 freeze로 한국어 헤더 상시 노출 + 색이 칠해진 SigmaBucket/TechBucket 셀에 bold를 추가해 신호 강도 시각화.

## Tasks

| # | Description | Commit |
|---|---|---|
| 1 | Add `bold=True` to 6 colored bucket Formats in `_COLOR_PROPS` | 87575af |
| 2 | Add `ws.freeze_panes(5, 0)` at end of `write_sheet_for_ticker` | 9512d9e |
| 3 | Add `test_header_freeze_and_colored_bold` smoke assertions | 5eaf0e5 |

## Verification

- 32 / 32 tests GREEN (31 prior + 1 new).
- `python -m uv run python main.py` regenerated `output/portfolio_20260521.xlsx`.
- Sample inspection (regenerated file, sheet `AAPL`):
  - `ws.freeze_panes == 'A6'` ✓
  - Colored cell `B6` (HARD_RED Close): `font.b == True`, color `FFB71C1C` ✓
  - DEFAULT cell `B3` (median scalar): `font.b == False` ✓
- Programmatic verification via Task 1 `<automated>` snippet: `sample.bold: True`, `default.bold: 0`, `OK`.

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- src/stocksig/output/writer.py: FOUND
- src/stocksig/output/sheet_per_ticker.py: FOUND
- tests/test_smoke_end_to_end.py: FOUND
- commit 87575af: FOUND
- commit 9512d9e: FOUND
- commit 5eaf0e5: FOUND
