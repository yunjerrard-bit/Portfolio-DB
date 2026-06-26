---
phase: 02-scaling-portfolio-summary
plan: 03
subsystem: output/portfolio-sheet
tags: [python, xlsxwriter, portfolio-sheet, korean-headers]
requires: [TickerResult, TickerFailure, Format-cache-42-keys]
provides: [write_portfolio_sheet, PORTFOLIO_COLUMNS, failed_row_marker, timestamp]
affects: [src/stocksig/output/writer.py, src/stocksig/output/sheet_portfolio.py]
tech_added: []
patterns: [single-source-color-decision, input-order-preservation]
key_files_created: [src/stocksig/output/sheet_portfolio.py, tests/test_sheet_portfolio.py, tests/test_writer.py]
key_files_modified: [src/stocksig/output/writer.py]
decisions:
  - "시트 이름은 한글 literal '시트1' (VALIDATION map과 일치)"
  - "DIFF 셀 값 = ratio 자체 (percent_ratio fmt), 색 = decide_sigma_bucket(DIFF, med, std)"
  - "단일 색 결정 함수 = compute.color_rules.* — 시트1과 종목 시트 동일 import (D-02)"
  - "하이퍼링크 single-quote 항상 wrap (`internal:'<sym>'!A1`) — KR .KS/.KQ 무조건 호환"
  - "실패 행은 성공 행 다음에 input_order 순으로 추가 (D-03)"
metrics:
  duration_min: 9
  completed: 2026-05-26
  tasks: 2
  files_changed: 4
  tests_added: 18
  tests_total: 115
---

# Phase 2 Plan 3: 통합 포트폴리오 시트 (시트1) Summary

XlsxWriter 기반 standalone 시트1 작성기 — 15 컬럼 한국어 레이아웃, σ-bucket 색 결정 단일 경로, 실패 티커 inline marker, input_order 보존.

## What Changed

### `src/stocksig/output/writer.py`
- Format 캐시 42 → 44 키
- `failed_row_marker`: italic + RED_800 font + #FFEBEE pastel pink bg (D-03)
- `timestamp`: italic 12pt (PORT-08 A1)

### `src/stocksig/output/sheet_portfolio.py` (NEW, 217 lines)
- `PORTFOLIO_COLUMNS` (15) — D-08 컬럼 레이아웃
- `write_portfolio_sheet(wb, formats, results, failures, input_order, now=None)` — 메인 진입
- `_write_success_row` — 성공 티커 한 행 (하이퍼링크 + 시장/티어/산업 + 종가 + 등락률 + DIFF×4 + 거래량 + Stoch %K + RSI + 임펄스 일/주)
- `_write_failure_row` — D-03: ticker, "?", 빈 칸, `실패: <reason>` italic+pastel red

## Sample Output

**성공 행 (AAPL, row 6):**
```
A6=AAPL (hyperlink internal:'AAPL'!A1)  B6=US  C6=1  D6=Technology
E6=100.00 (price)  F6=0.50% (percent_ratio, color by σ)
G6..J6=DIFF EMA11/22/96/192 (ratio, σ-bucket color)
K6=1,000,000 (volume, σ-bucket color from Volume_pct_change)
L6=15.00% (TechBucket.SOFT_GREEN, GREEN_800 bold)
M6=75.00% (TechBucket.SOFT_RED, RED_800 bold)
N6=녹색 (impulse_green: GREEN_800 + GREEN_100 bg, bold center)
O6=청색 (impulse_blue: BLUE_800 + BLUE_100 bg, bold center)
```

**실패 행 (XYZ, row 6 (no successes)):**
```
A6=XYZ  B6=?  C6..N6=빈 칸  O6=실패: 부분 데이터: 100 거래일
all cells italic + RED_800 font + #FFEBEE pastel pink bg
```

## Test Coverage

| Test file | Count | Focus |
| --------- | ----- | ----- |
| `tests/test_writer.py` | 4 | Format 캐시 44 키, 키 존재, Phase 1 42 키 intact, add_format count |
| `tests/test_sheet_portfolio.py` | 14 | 15 col 순서, A1 timestamp, input_order 보존, hyperlink US/KR, DIFF 색, 거래량 색, Stoch/RSI 색, 임펄스, 티어/산업, 실패 행, success+failure mixed order |

총 18 new tests. Suite 97 → 115 GREEN (full run 106s).

## Deviations from Plan

### Rule 1 — Bug (test design)
**`test_add_format_count` threshold**: Plan asserted `≤ 44` total `Workbook.add_format` calls. Empirically, `xlsxwriter.Workbook.__init__` itself invokes `add_format` twice for internal defaults, so observed total = 46. Test redesigned to count *user-driven* calls only (subtracting 2 internal ones) and assert exactly 44. Intent (verify only 2 new keys added) preserved.

### Rule 1 — Simplification (planner-allowed)
**`test_diff_color_matches_per_ticker`**: Planner flagged cross-sheet cell color comparison as fragile (column letter discovery in per-ticker sheet). Simplified per the plan's risk note: assert (a) `sheet_portfolio.py` imports `decide_sigma_bucket` (single source of truth), and (b) the same inputs produce the canonical `SigmaBucket` enum. Test still enforces D-02 invariant.

No other deviations. Plan executed verbatim.

## Threat Flags

None new — module surface (synthetic-DF-only-test, no I/O, no external strings) within plan's `<threat_model>`. Mitigations applied:
- T-02-07: `_sanitize_sheet_name` strips `[]:/\\?*` + 31-char truncate; `_internal_link` single-quote wrap.
- T-02-08: failure.reason rendered as-is — accepted (local single-user tool).

## Self-Check: PASSED

- File: `src/stocksig/output/sheet_portfolio.py` — FOUND
- File: `src/stocksig/output/writer.py` (modified) — FOUND
- File: `tests/test_sheet_portfolio.py` — FOUND
- File: `tests/test_writer.py` — FOUND
- Commit `a905706` (Task 1 — Format cache extension) — FOUND
- Commit `32f4807` (Task 2 — sheet_portfolio implementation) — FOUND
- `PORTFOLIO_COLUMNS` length = 15 — VERIFIED
- Full suite: 115/115 GREEN — VERIFIED
