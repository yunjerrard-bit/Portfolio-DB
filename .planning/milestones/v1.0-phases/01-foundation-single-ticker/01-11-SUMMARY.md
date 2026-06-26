---
phase: 01-foundation-single-ticker
plan: 11
subsystem: compute/ema + compute/color_rules + output/sheet_per_ticker
tags: [ema-trend, color-rules, layout, gap-fix, ui]
requires: [01-07, 01-08, 01-09, 01-10]
provides: [SHEET-07 EMA trend visualization, EMA value cols hidden by default]
affects:
  - src/stocksig/compute/ema.py
  - src/stocksig/compute/color_rules.py
  - src/stocksig/output/sheet_per_ticker.py
  - tests/test_ema.py
  - tests/test_color_rules.py
  - tests/test_smoke_end_to_end.py
tech-stack:
  patterns:
    - pandas Series.pct_change() for day-over-day rate of change
    - re.compile regex for exact EMA_Close_N value-column hide rule
    - TechBucket reuse (SOFT_GREEN/SOFT_RED) for trend sign coloring
key-files:
  created: []
  modified:
    - src/stocksig/compute/ema.py
    - src/stocksig/compute/color_rules.py
    - src/stocksig/output/sheet_per_ticker.py
    - tests/test_ema.py
    - tests/test_color_rules.py
    - tests/test_smoke_end_to_end.py
decisions:
  - "EMA_Close_N value columns now hidden by default (joined median/std hidden rule via regex r'^EMA_Close_\\d+$'); trend/dailychg explicitly visible."
  - "Trend = EMA_Close_N.pct_change() (ratio), formatted as '0.00%' (percent_ratio — Excel auto ×100), matching DIFF convention."
  - "decide_trend_bucket reuses TechBucket.SOFT_GREEN/SOFT_RED — no new bucket type, no new Format keys (33 cache size unchanged)."
  - "Layout grew 76 → 80; per-period EMA group is now [val, median, std, trend]."
metrics:
  duration: ~10min
  completed: 2026-05-21
---

# Phase 01 Plan 11: EMA Trend Columns + Value Hide Summary

One-liner: EMA 절댓값보다 추세 방향이 더 유용 — EMA_Close_N 값을 숨기고 같은 period 그룹에 pct_change 추세 컬럼 4개를 추가 (양수=초록 굵게, 음수=빨강 굵게, '0.00%').

## Tasks

| # | Description | Commit |
|---|---|---|
| 1 | Add 4 `EMA_Close_N_trend` cols (pct_change) + ema test | 841d710 |
| 2 | `decide_trend_bucket` + test_trend_bucket | 1e235a9 |
| 3 | Layout 76→80, korean_header/num_format/hidden-rule/color-dispatch | 50f2853 |
| 4 | 3 smoke tests (hidden val / visible trend / color bake) + regression updates | ac6f9e4 |

## Verification

- All 37 tests GREEN (`uv run pytest -x -q`)
- xlsx regenerated to `output_new/portfolio_20260521.xlsx` (existing `output/` xlsx locked)
- Sample: `EMA_Close_11_trend` at column **Q**, row 6 value=0.00524 (+0.52%), font color=`FF2E7D32` (GREEN_800), bold=True, number_format=`'0.00%'`, header row 5 = "ema11 추세"
- `EMA_Close_11`, `_22`, `_96`, `_192` value columns hidden=True; trend columns hidden=False
- Layout count: `len(build_column_layout()) == 80`

## Deviations from Plan

None — plan executed exactly as written. `writer.py` already registered `percent_ratio` Format keys for both SigmaBucket and TechBucket (groundwork from 01-06/01-07), so no Format cache changes were needed.

## Self-Check: PASSED
