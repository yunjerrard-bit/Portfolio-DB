---
phase: 09-trend-render
plan: 02
subsystem: 트렌드 워크북 작성 층 — 별도 워크북 팩토리 + 3종 시트 writer
tags: [FUND-10, xlsxwriter, history-workbook, metric-matrix, raw-sheet, snapshot, core-value-invariant]
requires:
  - stocksig.compute.color_rules.GREEN_100
  - stocksig.compute.color_rules.GREEN_900
  - stocksig.compute.color_rules.RED_100
  - stocksig.compute.color_rules.RED_900
  - stocksig.compute.trend_color.relative_bucket
  - stocksig.compute.trend_color.yoy_glyph
  - stocksig.io.fundamentals._is_missing
  - stocksig.io.fundamentals.MetricCell
  - stocksig.io.metrics_registry.REGISTRY
  - stocksig.io.fundamentals_store.fetch_raw_quarters
provides:
  - stocksig.output.history_workbook.make_history_workbook
  - stocksig.output.sheet_metric_matrix.write_metric_sheet
  - stocksig.output.sheet_raw.write_raw_sheet
  - stocksig.output.sheet_snapshot.write_snapshot_sheet
affects:
  - Plan 09-03 (history_render 오케스트레이션 — 4 writer 호출·peer_lookup/prior_lookup 주입·시트명 sanitize)
tech-stack:
  added: []
  patterns:
    - "트렌드 전용 워크북 팩토리(make_history_workbook) — 시트1 make_workbook 45키 캐시와 비결합(Pitfall 5/T-09-03)"
    - "색 상수만 import(GREEN/RED) — 함수(decide_*) 미참조"
    - "YoY 글리프 결합 = 텍스트 셀 write_string(num_format 미적용, RESEARCH 방법 A)"
    - "비율 지표 퍼센트 텍스트 베이킹(WARNING-2 시트1 표시 정합) — 신규 산식 아님 표시 분기"
    - "peer/prior 호출자 주입(WARNING-3) — writer 모집단 자체 구성 0"
    - "결손/sanity-밖 = '-'+사유 코멘트(D-11, 0/빈칸 sentinel 금지)"
key-files:
  created:
    - src/stocksig/output/history_workbook.py
    - src/stocksig/output/sheet_metric_matrix.py
    - src/stocksig/output/sheet_raw.py
    - src/stocksig/output/sheet_snapshot.py
    - tests/test_history_sheets.py
  modified: []
decisions:
  - "지표 시트명 [원천]/[최신 스냅샷] 의 Excel 금지문자([]) sanitize는 호출자(Plan 03) 책임 — writer 는 sanitize명 worksheet 수신(테스트도 sanitize명 검증)"
  - "freeze A열만(0,1) — 매트릭스·스냅샷 동일 적용(D-04 일관)"
  - "텍스트 셀 분리(green_text/red_text/plain_text) — YoY 글리프 결합 셀은 문자열 write, num_format 미적용"
metrics:
  duration: ~18 min
  completed: 2026-06-22
  tasks: 3
  files: 5
---

# Phase 09 Plan 02: 트렌드 워크북 작성 층 Summary

시트1 Format 캐시와 완전 비결합한 트렌드 전용 워크북 팩토리(`make_history_workbook`)와 3종 시트 writer(지표 매트릭스·[원천] long·[최신 스냅샷])를 XlsxWriter 정적 색 베이킹으로 구현하고, openpyxl read-back 7종 단언으로 식별 5열+분기열·상대색·YoY 글리프·결손 '-'·퍼센트 정합·A열 freeze를 검증했다 — 시트1 portfolio 모듈·color_rules·writer 0줄 수정(Core Value 색 신호 불변).

## What Was Built

### Task 1 — `history_workbook.make_history_workbook` (Pitfall 5 / T-09-03)
- `make_history_workbook(path, *, constant_memory=False) -> (Workbook, formats)` — writer.py 패턴 차용(직접 호출 금지), `p.parent.mkdir`·`{"constant_memory": False, "nan_inf_to_errors": True}`.
- formats 7키: `green`/`red`(bg+font+소수2자리), `plain`(무색 D-07), `green_text`/`red_text`/`plain_text`(YoY 글리프 결합용 텍스트 셀 — num_format 미적용 RESEARCH 방법 A), `header`.
- `color_rules`에서 GREEN_100/GREEN_900/RED_100/RED_900 **상수만** import — `make_workbook`·`decide_*` 미참조. 커밋 f6e1785.

### Task 2 — `sheet_metric_matrix.write_metric_sheet` (D-01/02/04/05/07/08/11/12)
- 식별 5열 `_IDENT_COLUMNS=["티커","기업명","시장","티어","산업"]` + 명명 인덱스 dict 트렌드 전용 재정의(sheet_portfolio `_COL` import 0).
- 헤더 = 식별 5열 + `display_quarters`(최신 왼쪽 D-01); 종목 행마다 식별 5열 폴백 write + 분기 셀.
- 분기 셀: `relative_bucket(metric, value, peer_values, industry)`(D-05/06/07) → green/red/plain Format, `yoy_glyph(cell, prior)`(D-08) 글리프 결합, `_is_missing`/미보유(`.get` None Pitfall 2) → `write_string "-"` + 사유 코멘트(D-11), 값 있으면 provenance 코멘트(D-12).
- 값 텍스트(WARNING-2): `_IS_RATIO`(REGISTRY `is_ratio_0_1`) 조회 → 비율 `f"{v*100:.1f}%"` / 비-비율 `f"{v:.2f}"` — 시트1 퍼센트 표시 정합(신규 산식 0).
- `freeze_panes(0,1)`(A열만, 헤더행 미고정 D-04), 식별 열 개별 폭. peer/prior 호출자 주입(WARNING-3 — writer 모집단 자체 구성 0). 커밋 75f3c5a.

### Task 3 — `sheet_raw` [원천] + `sheet_snapshot` [최신 스냅샷] (D-13/Open Q2)
- `write_raw_sheet(ws, raw_by_ticker, formats, sorted_tickers=None)` — 한국어 헤더 8열(티커·소스·분기·필드·값·기간유형·보고서코드·단위) + `fetch_raw_quarters` 7-tuple long 행. value 결손 → "-" 일관(D-11). 종목 순서 = 호출자 `sorted_tickers`.
- `write_snapshot_sheet(ws, snapshot_rows, formats)` — 식별 5열 + 9지표(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA) 헤더 + 종목 1행 × **매트릭스 최신 열 셀 재사용**(재계산 0, D-13). PEG/결손 셀 "-"+코멘트(`_is_missing` 게이트). 신규 산식·`price_ratio`/`compute_peg_cell` 호출 0(Plan 03 책임).
- `tests/test_history_sheets.py` — openpyxl read-back 7종. 커밋 84eb511.

## Verification

- `tests/test_history_sheets.py` → 7 passed (matrix 5 + raw 1 + snapshot 1).
- 전 스위트 **361 passed, 4 warnings** (baseline 354 + 신규 7, 회귀 0). edgar UserWarning은 기존 smoke 잔존(본 플랜 무관).
- 비결합 단언: history_workbook 에 bare `make_workbook(` 호출 0(only `make_history_workbook`), `decide_*` 미참조(docstring만). sheet_metric_matrix/sheet_snapshot 의 `sheet_portfolio` 문자열은 전부 docstring/주석(실제 import 0).
- `_is_missing` 재사용 ≥1(matrix·raw·snapshot 전부), 신규 결손 게이트 정의 0.
- 시트1 불변: `git diff HEAD~3 -- sheet_portfolio.py color_rules.py writer.py` = 0줄(Core Value 색 신호 불변).

## Deviations from Plan

### 조정 사항

**1. [Plan 정합 - 시트명 sanitize] [원천]/[최신 스냅샷] worksheet 명 검증을 sanitize명으로**
- **Found during:** Task 3 (read-back 테스트 작성)
- **Issue:** Excel 시트명은 `[]` 금지문자 → `wb.add_worksheet("[원천]")`가 `InvalidWorksheetName` raise. PLAN acceptance("[원천]" 시트 또는 **sanitize명**)·PATTERNS(`_sanitize_sheet_name` 호출자 책임)·threat T-09-04 정합.
- **Fix:** writer 자체는 시트명을 만들지 않으므로(호출자가 add_worksheet) 변경 없음. 테스트가 sanitize명("원천"/"최신 스냅샷")으로 worksheet 생성·검증하도록 정렬. 시트명 sanitize는 Plan 03 run_history 책임(D-15)으로 명시.
- **Files modified:** tests/test_history_sheets.py
- **Commit:** 84eb511

Rule 1-3 자동수정 없음(신규 모듈, 기존 코드 버그 미발견).

## Known Stubs

없음. peer_lookup/prior_lookup 은 호출자 주입 콜백(WARNING-3 책임 단일화)이며 테스트는 결정적 람다로 주입 — 프로덕션 모집단(분기열×산업 2차원)·4분기 전 셀 계산은 Plan 03 run_history 가 담당한다.

## Threat Flags

없음 — 신규 네트워크 엔드포인트·인증 경로·스키마 변경 0. 시트명은 고정/sanitize(T-09-04 mitigate, 호출자), provenance 코멘트는 source 라벨만(T-09-05 accept).

## Notes for Downstream (Plan 03 run_history)

- 4 writer 호출 순서·시트명 sanitize(`[]`→`_` 또는 한글명) 책임은 run_history.
- `write_metric_sheet`에 `peer_lookup(metric, quarter, industry) -> list[float]`·`prior_lookup(metric, ticker, quarter) -> MetricCell|None` 주입 — 모집단=(분기열×산업) 2차원 보장은 호출자(Pitfall 3). 4분기 전 키 = `_calendar_quarter_offset(q, -4)`.
- `ticker_rows[*]["cells"]` = 그 지표의 `{quarter: MetricCell}`(matrix[metric]) 그대로; `display_quarters` = `reversed(all_quarters)`(최신 왼쪽 D-01).
- snapshot `metrics` = 매트릭스 최신 열 셀 재사용(재계산 금지), PER/PBR/PCR/PSR/PEG 가격·성장률 주입은 run_history 가 `price_ratio`/`compute_peg_cell`로 산출해 matrix 최신 열에 채워 넘김.
- raw `raw_by_ticker[t]` = `fetch_raw_quarters(t)`, `sorted_tickers` = D-03 정렬(US→KR·각 그룹 sorted).

## Self-Check: PASSED

- FOUND: src/stocksig/output/history_workbook.py
- FOUND: src/stocksig/output/sheet_metric_matrix.py
- FOUND: src/stocksig/output/sheet_raw.py
- FOUND: src/stocksig/output/sheet_snapshot.py
- FOUND: tests/test_history_sheets.py
- FOUND commit: f6e1785 (history_workbook T1)
- FOUND commit: 75f3c5a (sheet_metric_matrix T2)
- FOUND commit: 84eb511 (sheet_raw + sheet_snapshot + 테스트 T3)
