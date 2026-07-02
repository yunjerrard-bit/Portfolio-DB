---
phase: quick-260702-nrs
plan: 01
subsystem: output (펀더멘털 히스토리 워크북 writer)
tags: [freeze-panes, display-format, ROE, ROA, D-04, WARNING-2]
requires:
  - fundamentals_history_*.xlsx 트렌드 워크북 렌더 경로(Plan 09-02/09-03)
provides:
  - 전 트렌드 탭 헤더행(1행) 틀 고정
  - ROE/ROA 퍼센트(.1f%) 표기
affects:
  - src/stocksig/output/sheet_metric_matrix.py
  - src/stocksig/output/sheet_snapshot.py
  - src/stocksig/output/sheet_raw.py
tech-stack:
  added: []
  patterns:
    - "display 층 전용 퍼센트 확장(_PERCENT_METRICS) — 레지스트리 is_ratio_0_1 불변"
    - "XlsxWriter freeze_panes(row,col) '첫 비고정 셀' 규약: (1,1)=B2, (1,0)=A2"
key-files:
  created: []
  modified:
    - src/stocksig/output/sheet_metric_matrix.py
    - src/stocksig/output/sheet_snapshot.py
    - src/stocksig/output/sheet_raw.py
    - tests/test_history_sheets.py
    - tests/test_history_render.py
decisions:
  - "ROE/ROA 퍼센트 표기는 display 함수(_format_value_text) 안에서만 확장 — is_ratio_0_1 플래그(0~1 비율 의미)는 ROE 100% 초과 가능성 때문에 건드리지 않음"
  - "원천 탭은 헤더행만 고정(A2, 키 컬럼 미고정), 지표 9탭·스냅샷은 헤더행+A열(B2)"
metrics:
  duration: ~8 min
  completed: 2026-07-02
  tasks: 2
  files: 5
---

# Quick 260702-nrs: 트렌드 탭 헤더행 freeze + ROE/ROA 퍼센트 표기 Summary

펀더멘털 트렌드 워크북(fundamentals_history_YYYYMMDD.xlsx)의 전 탭에 헤더행 틀 고정을 적용하고, ROE/ROA 값을 소수 대신 퍼센트(.1f%)로 표기하도록 두 표시 결함을 수정했다.

## What Changed

### Task 1 — 3개 writer 수정 (commit 87f8d06)

- **sheet_metric_matrix.py**: `freeze_panes(0, 1)` → `freeze_panes(1, 1)`(헤더행+A열 고정, B2 스크롤). `_PERCENT_METRICS = frozenset({"ROE", "ROA"})` 모듈 상수 추가, `_format_value_text` 를 `if _IS_RATIO.get(metric, False) or metric in _PERCENT_METRICS:` 로 확장. docstring/주석 "헤더행 미고정" → "헤더행 고정".
- **sheet_snapshot.py**: 동일하게 `freeze_panes(1, 1)`, `_PERCENT_METRICS` + `_format_value_text` 확장, 주석 갱신.
- **sheet_raw.py**: 데이터 루프 뒤에 `freeze_panes(1, 0)`(헤더행만 고정, A2 스크롤) 신규 추가.
- **metrics_registry.py**: 미변경(git diff 빈 출력 확인). is_ratio_0_1 은 여전히 GPM/OPM 만 True, ROE/ROA 는 False.

### Task 2 — 회귀 테스트 갱신 + 신규 단언 (commit 2561b6d)

- **test_history_sheets.py**: `test_matrix_headers_and_freeze` freeze 단언 B1→B2. `test_raw_sheet_long_rows` 에 원천 freeze A2 단언 추가. 신규 `test_matrix_roe_roa_percent`(ROE 1.151→"115.1%", ROA 0.09→"9.0%"). `test_snapshot_sheet_one_row_per_ticker` 에 ROE 18.0%·ROA 9.0% 퍼센트 + 스냅샷 freeze B2 단언 추가.
- **test_history_render.py**: `test_freeze` 두 단언 B1→B2 + docstring 갱신.

## Verification

- `test_history_sheets.py` + `test_history_render.py` + `test_freeze_panes.py`: **25 passed** (24.6s).
- `test_freeze_panes.py`(시트1/종목시트 경로) 기대값 "B6" 불변 — 회귀 0.
- metrics_registry.py git diff 빈 출력 — is_ratio_0_1 플래그 불변 확인.
- 기존 GPM/OPM 퍼센트·PER 소수 표기 단언(`test_matrix_ratio_percent_vs_decimal`) 불변 통과.

## Success Criteria

- [x] 지표 9탭·최신 스냅샷 = 헤더행+A열(B2), 원천 = 헤더행만(A2)
- [x] ROE/ROA 매트릭스·스냅샷 퍼센트(.1f%) 표기
- [x] GPM/OPM/PER 표기·is_ratio_0_1 플래그·시트1 freeze("B6") 불변
- [x] 회귀 테스트 2파일 + freeze_panes 테스트 통과

## Deviations from Plan

None - plan executed exactly as written.

## Self-Check: PASSED

- 커밋 존재: 87f8d06 (FOUND), 2561b6d (FOUND)
- 파일 존재: 3 writer + 2 test 전부 FOUND
