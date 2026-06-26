---
phase: 03-edgar-dart-yfinance-naver
plan: 05
subsystem: 펀더멘털 배선 + 시트1 렌더
tags: [runner, main_run, sheet_portfolio, fundamentals, wiring, provenance]
requires:
  - "io/fundamentals.fetch_fundamentals (03-03/03-04)"
  - "io/naver_scraper.reset_naver_count (03-04)"
  - "runner.run_all / TickerResult (Phase 2)"
  - "output/sheet_portfolio.write_portfolio_sheet (Phase 2)"
  - "output/writer.make_workbook Format 캐시 44키 (Phase 1/2)"
provides:
  - "runner.process_ticker PASS 1b (fundamentals_fn 주입 + 예외 흡수)"
  - "runner.TickerResult.fundamentals 필드"
  - "main_run.run fetch_fundamentals 클로저 배선 + reset_naver_count"
  - "sheet_portfolio PORTFOLIO_COLUMNS 21열 + _write_fund_cell"
affects:
  - "src/stocksig/runner.py"
  - "src/stocksig/main_run.py"
  - "src/stocksig/output/sheet_portfolio.py"
tech-stack:
  added: []
  patterns:
    - "의존성 주입 클로저 (fundamentals_fn) — 테스트는 stub 주입으로 우회"
    - "try/except 흡수 = 펀더멘털 결손 ≠ 티커 실패 (D-disc-10)"
    - "XlsxWriter write_comment 로 셀 provenance, num_format 무손상"
    - "Format 캐시 재사용 (신규 add_format 0개)"
key-files:
  created: []
  modified:
    - "src/stocksig/runner.py"
    - "src/stocksig/main_run.py"
    - "src/stocksig/output/sheet_portfolio.py"
    - "tests/test_runner.py"
    - "tests/test_sheet_portfolio.py"
decisions:
  - "TickerResult.fundamentals 기본 None — 3-인자 호출/미주입 하위호환"
  - "process_ticker 가 fetch_fundamentals 위에 방어적 try/except 한 겹 더 — 시세 정상이면 항상 TickerResult 반환"
  - "결손 펀더멘털 셀은 write_blank + 한국어 주석 (0/-999999 금지, D-05)"
  - "실패 티커 행은 펀더멘털 셀 미작성 (D-06)"
metrics:
  duration: "~9분 (테스트 실행 4분 포함)"
  completed: "2026-06-05"
  tasks: 2
  files-modified: 5
requirements: [PORT-05, FUND-05]
---

# Phase 3 Plan 05: 펀더멘털 배선 + 시트1 21열 렌더 Summary

03-03/03-04가 만든 `fetch_fundamentals`를 per-ticker 파이프라인(PASS 1b)에 의존성 주입으로 연결하고, 시트1 우측 4열(PER/PEG/GPM/OPM = col 17~20, 시트 R/S/T/U)에 값 + 출처를 `write_comment` 셀 주석으로 렌더한다. 펀더멘털 fetch 예외는 흡수해 시세 정상 티커의 시트 생성을 막지 않으며(D-disc-10), 결손 셀은 빈 칸 + 한국어 사유 주석으로 표시(D-05)한다. 신규 Excel Format 0개.

## What Was Built

### Task 1 — runner PASS 1b + main_run 클로저 주입 (commit 5840753)
- `TickerResult`에 `fundamentals: object | None = None` 필드 추가 — Phase 1/2 3-인자 호출 및 `fundamentals_fn` 미주입 시 무회귀.
- `process_ticker(spec, classify_market, pipeline, fundamentals_fn=None)`: 시세 검증(`_validate_row_count`) 통과 후 `fundamentals_fn` 이 있으면 `last_close = df.iloc[-1].get("Close")` 를 주입해 호출. 예외는 `try/except` 로 흡수하고 `logger.warning("...펀더멘털 fetch 예외 흡수...")` 후 `fundamentals=None` 유지 → 티커 실패 아님(D-disc-10).
- `run_all` 시그니처에 `fundamentals_fn=None` 추가 + `executor.submit` 에 4번째 positional 인자로 전달.
- `main_run.run`: `from stocksig.io.fundamentals import fetch_fundamentals` → `run_all(..., fundamentals_fn=fetch_fundamentals)`. run 시작 시 `naver_scraper.reset_naver_count()` 1회 호출(D-07 — run마다 네이버 폴백 카운터 초기화).

### Task 2 — sheet_portfolio 21열 + _write_fund_cell + write_comment (commit 8f2a1ba)
- `PORTFOLIO_COLUMNS` 17→21열 (끝에 "PER","PEG","GPM","OPM" = index 17~20). `set_column(0, len-1, 14)` 가 21열 자동 적용 — set_column 라인 미변경.
- `_write_fund_cell(ws, row, col, cell, num_fmt, formats)`: 값 존재 → `write_number`(기존 `formats[(SigmaBucket.DEFAULT, num_fmt)]` 재사용) + `note or source` 를 `write_comment`. 결손 → `write_blank` + `note or "조회 실패"` 주석. PER/PEG = `"price"`(#,##0.00), GPM/OPM = `"percent_ratio"`(0.00%).
- `_write_success_row` 말미: `res.fundamentals is not None` 가드 후 4셀 작성, None 이면 4셀 빈칸 + "펀더멘털 미수집" 주석(하위호환).
- `_write_failure_row` 무변경 — 실패 행은 col 16 사유만, 펀더멘털 셀 미작성(D-06).
- `freeze_panes(5,1)` 유지. 신규 `add_format` 0개 (Format 캐시 44키 불변).

## Tests
- `tests/test_runner.py`: `test_fundamentals_fn_injected`(주입 채워짐), `test_fundamentals_fn_exception_absorbed`(예외 시 failures 아님·fund=None), `test_fundamentals_fn_exception_absorbed_logs`(한국어 로그), `test_fundamentals_backward_compat_default_none`(3-인자 하위호환).
- `tests/test_sheet_portfolio.py`: `test_column_count_is_21`(17→21 갱신), `test_fund_cols`(col 18~21 값 + 출처 주석 + num_format #,##0.00 / 0.00% 무손상), `test_fund_missing_cell_blank_with_note`(D-05 빈셀+사유), `test_fund_none_backward_compat`(하위호환), `test_fund_failure_row_no_fund_cells`(D-06).
- openpyxl 컬럼 매핑: PORTFOLIO_COLUMNS index 17~20 = openpyxl 1-based col 18~21.

## Verification
- `uv run pytest tests/test_runner.py -x` → 11 passed
- `uv run pytest tests/test_sheet_portfolio.py` → 18 passed
- `uv run pytest` (전체) → **194 passed in 243.90s** — Phase 1/2 무회귀, 종목별 시트 97열·Format 캐시 44키 불변 확인.

## Deviations from Plan

없음 — 계획대로 실행. 레이아웃 컬럼 수 단언은 `test_column_count_is_17` 단 1곳만 portfolio 대상이었고(나머지 `max_column==97` / `len(layout)==97` 은 per-ticker 시트, D-06으로 불변) 동일 갱신 완료. `.continue-here` 흩어짐 없음.

## 메모
- `TickerResult.fundamentals` 타입 힌트는 `"object | None"` 으로 두어 runner → fundamentals 순환 import 회피. 실제 주입값은 `FundamentalsResult`.
- `process_ticker` 의 try/except 는 `fetch_fundamentals` 내부 흡수(전 경로) 위에 방어적으로 한 겹 더 — last_close 추출(`df.iloc[-1].get`) 단계 예외까지 격리.

## Known Stubs
없음. 펀더멘털 데이터는 03-03/03-04 의 실데이터 fetcher가 채우며, 본 plan은 배선·렌더만 담당. 결손 셀은 의도된 빈칸+사유(D-05).

## Manual Gate (Phase gate, 미실행)
`python main.py` 1회 실행 후 시트1 R/S/T/U 4값 + 출처 주석 육안 확인 — VALIDATION Manual-Only (자동 테스트는 openpyxl readback 으로 대체 검증 완료).

## Self-Check: PASSED
- 수정 파일 5종 + SUMMARY.md 모두 FOUND
- 커밋 5840753 (Task 1), 8f2a1ba (Task 2) 모두 FOUND
