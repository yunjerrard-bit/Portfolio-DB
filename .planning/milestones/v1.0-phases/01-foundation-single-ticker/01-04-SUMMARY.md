---
phase: 01-foundation-single-ticker
plan: 04
wave: 3
type: execute
completed: 2026-05-21
commits:
  - ff2824d  # output.writer + sheet_per_ticker (Task 1+2)
requirements_completed:
  - SHEET-01
  - SHEET-02
  - SHEET-03
  - SHEET-04
  - SHEET-05
  - SHEET-06
  - SHEET-07
  - SHEET-08
  - TECH-03
  - TECH-06
  - OUT-01
  - OUT-02
  - OUT-03
key_files:
  created:
    - src/stocksig/output/__init__.py
    - src/stocksig/output/writer.py
    - src/stocksig/output/sheet_per_ticker.py
    - .planning/phases/01-foundation-single-ticker/01-04-COLUMN-MAP.md
  modified:
    - .gitignore
dependency_graph:
  requires: [01-02 (io), 01-03 (compute)]
  provides: [output.make_workbook, output.write_sheet_for_ticker]
  affects: [Wave 4 main.py 통합]
tech_stack:
  added: [xlsxwriter 3.2.9]
  patterns: [Pattern 8 Format 캐싱, D-03 컬럼 레이아웃, D-04 정적 색 베이킹]
decisions:
  - "Format 캐시 9개 키 (5 SigmaBucket + 3 TechBucket + header) — 워크북당 add_format 9회 고정"
  - "정적 색 베이킹 (XlsxWriter write-only) — Excel 조건부 서식 규칙 0개"
  - ".gitignore의 'output/' → '/output/'로 변경하여 src/stocksig/output/ 패키지 보호"
metrics:
  duration_min: 4
  tasks_complete: 2
  files_changed: 5
---

# Phase 01 Plan 04: output 레이어 (XlsxWriter Workbook + 시트) Summary

XlsxWriter Workbook 라이프사이클 + Format 캐시 + D-03 124 컬럼 레이아웃 + 정적 색 베이킹을 구현해 `make_workbook → write_sheet_for_ticker → wb.close()` 만으로 실제 `.xlsx` 파일이 생성되는 출력 레이어를 완성.

## What Was Built

### `src/stocksig/output/writer.py`
- `make_workbook(path) -> (Workbook, formats)`: 부모 디렉터리 자동 생성, `constant_memory=False`로 Workbook 오픈, 9키 Format 캐시 dict 생성.
- 9키: `SigmaBucket.DEFAULT/SOFT_GREEN/SOFT_RED/HARD_GREEN/HARD_RED` + `TechBucket.DEFAULT/SOFT_GREEN/SOFT_RED` + `'header'`.
- 색 hex는 `compute.color_rules`에서 import (D-04 단일 진실원).

### `src/stocksig/output/sheet_per_ticker.py`
- `build_column_layout(df) -> list[str]`: D-03 124 컬럼 순서 list.
- `korean_header(col) -> str`: suffix-aware 한국어 헤더 변환기 (`_median`, `_std`, `_dailychg`, EMA/DIFF prefix 분해).
- `KOREAN_HEADERS: dict`: layout 컬럼 → 한국어 lookup dict alias.
- `write_sheet_for_ticker(wb, formats, ticker, df, scalars)`: A1=ticker, row 2/3=median/std, row 4=한국어 헤더(header Format), row 5+=날짜 내림차순 데이터 + per-cell SigmaBucket/TechBucket Format 적용.

### `.planning/phases/01-foundation-single-ticker/01-04-COLUMN-MAP.md`
- 124 행 인덱스 표 (col index | 원본 컬럼명 | 한국어 헤더 | 색 규칙 | 그룹).
- Phase 2 통합 시트의 hyperlink 작성용 reference.

## Column Layout (D-03)

- **Total**: 124 columns (= 1 Date + 4 OHLCV × 3 + 12 EMA × 3 + 12 DIFF × 3 + 12 dailychg × 3 + 3 tech)
- **First 10**: `Date, Close, Close_median, Close_std, High, High_median, High_std, Low, Low_median, Low_std`
- **Last 5**: `EMA_Low_192_dailychg, EMA_Low_192_dailychg_median, EMA_Low_192_dailychg_std, Stoch_%K, Stoch_%D, RSI`

## Format Cache Keys (9)

1. `SigmaBucket.DEFAULT` — empty Format (기본색)
2. `SigmaBucket.SOFT_GREEN` — `font_color=#2E7D32`
3. `SigmaBucket.SOFT_RED` — `font_color=#C62828`
4. `SigmaBucket.HARD_GREEN` — `font_color=#1B5E20, bg_color=#C8E6C9`
5. `SigmaBucket.HARD_RED` — `font_color=#B71C1C, bg_color=#FFCDD2`
6. `TechBucket.DEFAULT` — empty
7. `TechBucket.SOFT_GREEN` — `font_color=#2E7D32`
8. `TechBucket.SOFT_RED` — `font_color=#C62828`
9. `'header'` — `bold=True, align=center`

## Tests / Verification

- Tests turned GREEN: **none new** (Wave 4 smoke가 종합 검증 예정).
- 24 tests from Waves 0–2 still passing.
- xfailed remaining: `tests/test_smoke_end_to_end.py` (Wave 4 활성화 예정).
- Plan 인라인 smoke (`uv run python -c "..."`) 성공 — `output/_smoke_writer.xlsx` 387 KB 생성.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] `.gitignore`가 src/stocksig/output/까지 무시함**
- **Found during:** Task 1 commit.
- **Issue:** `.gitignore`의 `output/` 패턴이 재귀 매치되어 `src/stocksig/output/` 패키지 파일도 무시 — `git add` 실패.
- **Fix:** `output/` → `/output/` (루트 한정). 출력 파일 보호는 유지하면서 패키지 디렉터리만 풀어줌. `*.xlsx` 룰이 출력 보호의 2차 방어선.
- **Files modified:** `.gitignore`
- **Commit:** `ff2824d`

### Plan Compression

Task 1과 Task 2를 단일 commit (`ff2824d`)으로 통합 — `write_sheet_for_ticker` 본문이 작고 (~50 lines) Task 1과 같은 모듈에 위치하여 분리 commit의 가치가 적음. COLUMN-MAP.md는 `.planning/` 하위라 commit 대상 외 (Wave 0 결정).

## Known Stubs

None.

## Threat Flags

None — Format 캐싱(T-01-FMT), 출력 파일 보호(T-01-INFO), 컬럼별 분기(T-01-CALC2) 모두 코드에 명시.

## Self-Check: PASSED

- `src/stocksig/output/__init__.py` FOUND
- `src/stocksig/output/writer.py` FOUND
- `src/stocksig/output/sheet_per_ticker.py` FOUND
- `.planning/phases/01-foundation-single-ticker/01-04-COLUMN-MAP.md` FOUND (131 lines)
- Commit `ff2824d` FOUND in `git log`
- Plan smoke command produced `output/_smoke_writer.xlsx` (387184 bytes)
