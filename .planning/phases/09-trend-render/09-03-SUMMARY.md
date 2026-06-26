---
phase: 09-trend-render
plan: 03
subsystem: 트렌드 렌더 오케스트레이션 — DB→별도 엑셀 엔트리 + CLI 서브커맨드
tags: [FUND-10, history-render, cli-subcommand, orchestration, core-value-invariant, network-zero]
requires:
  - stocksig.io.metrics_engine.compute_matrix
  - stocksig.io.metrics_engine.price_ratio
  - stocksig.io.metrics_engine.compute_peg_cell
  - stocksig.io.metrics_engine._calendar_quarter_offset
  - stocksig.io.quarter_price.quarter_end_prices
  - stocksig.io.fundamentals_store.count_rows
  - stocksig.io.fundamentals_store.fetch_raw_quarters
  - stocksig.io.input.read_tickers_extended
  - stocksig.io.company.fetch_company_name
  - stocksig.io.market_kind.classify_market
  - stocksig.output.history_workbook.make_history_workbook
  - stocksig.output.sheet_metric_matrix.write_metric_sheet
  - stocksig.output.sheet_raw.write_raw_sheet
  - stocksig.output.sheet_snapshot.write_snapshot_sheet
provides:
  - stocksig.io.history_render.run_history
  - main.history 서브커맨드 (CLI)
affects:
  - Phase 09 완료 (FUND-10 트렌드 렌더 엔드투엔드 — 사용자 진입점 확정)
tech-stack:
  added: []
  patterns:
    - "오케스트레이션 전용 모듈 — 신규 산식·외부 펀더멘털 호출 0(검증 함수만 소비)"
    - "가격 주입 in-place: price_ratio 4종 + 분기별 compute_peg_cell 3단(D-09/10)"
    - "(분기열×산업) peer_lookup + 4분기 전 prior_lookup 호출자 주입(WARNING-3 책임 단일화)"
    - "시트명 sanitize([] 제거) 호출자 책임(D-15) — writer 는 sanitize명 worksheet 수신"
    - "argparse add_subparsers — 서브커맨드 분리 + 늦은 import 하위호환"
    - "종목별 try/except 격리(type(exc).__name__만 로깅, T-09-07/08)"
key-files:
  created:
    - src/stocksig/io/history_render.py
    - tests/test_history_render.py
  modified:
    - main.py
decisions:
  - "시트명 sanitize=금지문자([]:*?/\\) 제거 후 strip — [원천]→원천 / [최신 스냅샷]→최신 스냅샷 (D-15 호출자 책임)"
  - "history 서브커맨드에 description 부여 — `history --help` 자체 출력에 '펀더멘털 트렌드' 노출(acceptance 정합)"
  - "분기별 가격: 종목별 최신 분기=현재가, 그 외=분기말 종가 qmap.get (Pitfall 2 .get 가드)"
  - "스냅샷 최신 열 = 종목별 자기 분기 최대값 기준(다종목 분기 비대칭 안전)"
metrics:
  duration: ~15 min
  completed: 2026-06-22
  tasks: 3
  files: 3
---

# Phase 09 Plan 03: 트렌드 렌더 오케스트레이션 + CLI 서브커맨드 Summary

Phase 8 엔진(`compute_matrix`/`price_ratio`/`compute_peg_cell`)·Plan 01 가격(`quarter_end_prices`)·Plan 02 워크북/3종 시트 writer 를 배선해, 사용자가 `uv run python main.py history` 한 번으로 DB 적재 분기 펀더멘털을 `fundamentals_history_YYYYMMDD.xlsx` 별도 파일로 렌더하도록 완성했다(FUND-10). 신규 산식·외부 펀더멘털 호출 0, 시트1(portfolio) 흐름·색 신호 완전 불변(Core Value), 전 스위트 375 passed(회귀 0).

## What Was Built

### Task 1 — `history_render.run_history` (D-09/10/14/15, 커밋 8a0f155)
- DB 미적재 게이트: `count_rows()==0` → 한국어 안내 print 후 `return None`(예외 아님, D-15).
- 종목 정렬 `_sorted_tickers`: US → KR 그룹화 후 각 그룹 내 심볼 알파벳순(D-03).
- ticker 별 `compute_matrix`(외부 호출 0) + `quarter_end_prices`(D-09) → `_inject_prices` in-place:
  - 가격 의존 4종(PER/PBR/PCR/PSR) `price_ratio(matrix[denom][q], price)` 주입 — 최신 분기=현재가, 그 외=분기말 종가(`qmap.get`, Pitfall 2 가드).
  - 분기별 PEG 3단 계약(D-10): `per=price_ratio(EPS_ttm,price)` → `eps_prior=eps_map.get(_calendar_quarter_offset(q,-4))` → `compute_peg_cell(per.value, eps_now, eps_prior)`.
- 다종목 분기 합집합 → `reversed`(최신 왼쪽 D-01, Pitfall 1).
- `peer_lookup(metric,quarter,industry)`=같은 산업 유효값 리스트(`_is_missing` 제외)·`prior_lookup(metric,ticker,quarter)`=4분기 전 셀 — Plan 02 writer 에 주입(WARNING-3 모집단=분기열×산업 2차원).
- `make_history_workbook` → 9 지표 시트(`write_metric_sheet`) + [원천](sanitize "원천", `fetch_raw_quarters`) + [최신 스냅샷](sanitize "최신 스냅샷", 매트릭스 최신 열 재사용) write, `wb.close()`, path 반환.
- 종목별 try/except 격리 — 한 종목 실패가 전체 렌더 차단 안 함, `type(exc).__name__`만 로깅(T-09-07/08).

### Task 2 — `main.py` history 서브커맨드 (D-15, 커밋 0491f2f)
- `add_subparsers(dest="cmd")` + `history`(--tickers/--output-dir) 서브커맨드, `description`으로 자체 `--help`에 "펀더멘털 트렌드" 노출.
- `args.cmd=="history"` → 늦은 import `run_history` 호출(None 반환 시 종료코드 0, 예외 아님); else 기존 `main_run.run` portfolio 흐름(하위호환 — --env/--summary-only 유지).

### Task 3 — 통합 검증 (tests/test_history_render.py, Task 1 커밋에 포함)
- SC1 `test_separate_file_sheet1_untouched`: 트렌드 파일 생성·portfolio_*.xlsx 미생성.
- SC2 `test_all_nine_metric_sheets`·`test_matrix_layout_latest_left`(최신 왼쪽 D-01).
- SC3 `test_raw_and_snapshot_sheets`: [원천](sanitize "원천")·[최신 스냅샷] 시트 존재·헤더·행 수.
- SC4/D-10 `test_peg_per_quarter`: 분기별 PEG == `compute_peg_cell` 재현 동치.
- D-04 `test_freeze`: 지표·스냅샷 시트 `freeze_panes=="B1"`(A열만).
- D-15 `test_db_empty_guard`·CLI 4종(`test_history_cli_help`/`dispatch`/`default_cli_dispatch`/`db_empty_exit0`) — subprocess + monkeypatch.

## Verification

- `tests/test_history_render.py` → 14 passed.
- 전 스위트 **375 passed, 4 warnings** (baseline 361 + 신규 14, 회귀 0). edgar UserWarning 은 기존 smoke 잔존(본 플랜 무관).
- 통합 테스트 네트워크·실DB 호출 0 — `count_rows`/`fetch_raw_quarters`/`quarter_end_prices`/`fetch_company_name`/`read_tickers_extended` monkeypatch + `compute_matrix(fetch_fn=fetch_fn_stub)` + `build_ohlcv`.
- `grep main_run history_render.py` = 0(D-15 분리), `compute_matrix`/`quarter_end_prices`/`price_ratio`/`compute_peg_cell` 참조 ≥1.
- Core Value 불변: `git diff 4b6a3f7..HEAD` — `sheet_portfolio.py`·`color_rules.py`·`writer.py`·`main_run.py` 변경 0줄.
- 신규 SQL·신규 산식 0(store `?`-바인딩 함수만 호출, T-08-01/T-09-06 불변).

## Deviations from Plan

### 조정 사항

**1. [Rule 3 - blocking] history 서브커맨드 description 추가**
- **Found during:** Task 2 (`test_history_cli_help`)
- **Issue:** `add_parser(help=...)`만으로는 서브커맨드 자체 `--help` 출력에 도움말 문구가 나오지 않아(부모 `--help`에만 노출) acceptance("'펀더멘털 트렌드' 출력")가 깨짐.
- **Fix:** `add_parser`에 `description=`을 동일 문구로 추가 — 서브커맨드 `--help`에 직접 노출.
- **Files modified:** main.py
- **Commit:** 0491f2f

Rule 1/2 자동수정 없음(신규 모듈, 기존 코드 버그 미발견).

## Known Stubs

없음. `peer_lookup`/`prior_lookup`은 run_history 가 실제 매트릭스로 구성한 프로덕션 콜백(테스트는 fixture stub 으로 동일 경로 구동). 테스트 fixture(`fetch_fn_stub`/`build_ohlcv`)는 Plan 01 산출물 재사용(T-09-02 mitigate).

## Threat Flags

없음 — 신규 네트워크 엔드포인트·인증 경로·스키마 변경 0. CLI args 는 경로 인자만(셀 값·시트명 미진입), 시트명은 sanitize(T-09-04 mitigate), 종목별 except 는 `type(exc).__name__`만 로깅(T-09-07).

## Self-Check: PASSED

- FOUND: src/stocksig/io/history_render.py
- FOUND: tests/test_history_render.py
- FOUND: main.py (history 서브커맨드)
- FOUND commit: 8a0f155 (run_history T1 + 통합 테스트 T3)
- FOUND commit: 0491f2f (main.py history 서브커맨드 T2)
