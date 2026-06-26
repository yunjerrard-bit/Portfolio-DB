---
phase: 01-foundation-single-ticker
plan: 12
subsystem: compute+output
tags: [compute, remove-dailychg, layout-shrink, gap-fix]
requires: [01-07, 01-11]
provides: [layout-68-cols, dailychg-removed]
affects: [src/stocksig/compute/ema.py, src/stocksig/output/sheet_per_ticker.py, src/stocksig/main_run.py, tests/test_ema.py, tests/test_smoke_end_to_end.py]
tech-added: []
patterns: [layout-shrink-by-replacement]
key-files-created: []
key-files-modified:
  - src/stocksig/compute/ema.py
  - src/stocksig/output/sheet_per_ticker.py
  - src/stocksig/main_run.py
  - tests/test_ema.py
  - tests/test_smoke_end_to_end.py
decisions:
  - "dailychg(가격 단위) 컬럼은 trend(비율) 가 의미상 우월하므로 완전 제거 — 사용자 결정"
metrics:
  duration_min: 6
  completed: 2026-05-21
  tasks: 4
  files_modified: 5
requirements: [SHEET-07]
---

# Phase 1 Plan 12: Remove dailychg columns Summary

One-liner: trend(%) 컬럼이 EMA 변화량의 더 직관적 표현이므로 가격 단위 dailychg 컬럼 12개(4 base + 4 _median + 4 _std)를 레이아웃·계산·테스트에서 완전 제거 (80→68 컬럼).

## Tasks Executed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | compute/ema.py — dailychg 라인 제거 | 88889ce | src/stocksig/compute/ema.py |
| 2 | sheet_per_ticker.py — layout dailychg 그룹 제거 | 2ad4710 | src/stocksig/output/sheet_per_ticker.py |
| 3 | main_run.py — DATA_COLS dailychg 4엔트리 제거 (24→20) | 1524233 | src/stocksig/main_run.py |
| 4 | 테스트 갱신 + 전체 회귀 (37/37) | 1f1d193 | tests/test_ema.py, tests/test_smoke_end_to_end.py |

## Verification

- `len(build_column_layout()) == 68` ✓
- `[c for c in layout if 'dailychg' in c] == []` ✓
- `pytest -x -q` → 37/37 GREEN ✓
- Workbook 재생성: `output/portfolio_20260521.xlsx` 68 컬럼 ✓
- Trend cell `Q6` (EMA_Close_11_trend): value=0.00524, num_format=`0.00%`, font_color=`#2E7D32` (GREEN_800), bold=True ✓
- EMA value 컬럼(EMA_Close_11~192) hidden 유지 ✓
- DIFF 블록, freeze_panes A6, 색 베이킹, 한국어 헤더 — 회귀 없음 ✓

## Deviations from Plan

None — plan executed exactly as written. (소소한 추가 작업: 한국어 로그 메시지 "일변동" → "추세" 변경, 그리고 sheet_per_ticker.py 내부 docstring/주석 "76 컬럼"·"80" 표기를 "68"로 정리.)

## Self-Check: PASSED

- src/stocksig/compute/ema.py FOUND
- src/stocksig/output/sheet_per_ticker.py FOUND
- src/stocksig/main_run.py FOUND
- tests/test_ema.py FOUND
- tests/test_smoke_end_to_end.py FOUND
- output/portfolio_20260521.xlsx FOUND (68 cols, regenerated)
- Commits 88889ce, 2ad4710, 1524233, 1f1d193 all present in git log
