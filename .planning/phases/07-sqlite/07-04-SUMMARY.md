---
phase: 07-sqlite
plan: 04
subsystem: main-run/history-orchestration
tags: [orchestration, delta, history, gitignore, FUND-07, FUND-08, SC3, SC5, D-07]
requires:
  - "07-01: fundamentals_store reset_delta_stats / get_delta_stats / count_rows / set·get_last_accession"
  - "07-03: fundamentals_delta.sync_ticker_history(ticker, source, years=3) 오케스트레이터"
provides:
  - "main_run.run() 히스토리 경로 배선 — PASS2 write 이후 별도 순차 루프 + 델타 카운터 reset/요약 (D-07)"
  - ".gitignore data/ — data/fundamentals.db 미커밋 (SC5)"
  - "tests/test_history_integration.py — ≈0 호출·시트1 불변·DB 생성·실패 격리 5종 (네트워크 0)"
affects:
  - "Phase 8 (지표 계산): 평소 실행 외부 호출 ≈0 — DB raw 만으로 계산"
  - "Phase 10 (단일 원천 통합): 시트1 fetch ↔ 히스토리 probe 이중 호출 자연 해소"
tech-stack:
  added: []  # 신규 외부 패키지 0 — 기존 모듈 배선만
  patterns:
    - "PASS1/PASS2 시트1 경로(D-06 불변) 이후·요약 직전 분리된 additive 순차 루프 (D-07)"
    - "히스토리 종목 호출 try/except — 시트1 산출물(이미 저장) 보호 + 예외 타입명만 로그"
    - "run 시작부 카운터 reset(cache.reset_cache_stats 옆) — 다회 실행 누적 방지"
key-files:
  created:
    - tests/test_history_integration.py
  modified:
    - src/stocksig/main_run.py
    - .gitignore
decisions:
  - "D-07 적용: 히스토리 루프는 시트1 경로와 완전 분리된 additive 경로 — PASS2 wb.close() 이후 배치(시트1 이미 저장)로 시트1 회귀 위험 0. 분기 경계 이중 외부 호출 허용(드문 이벤트, Phase 10 자연 해소)."
  - "인증 실패 소스(auth.edgar_ok/dart_ok is False) skip + yf/Naver 전용 폴백 종목(US/KR 외)은 접수번호 개념 없어 대상 외(deferred)"
  - "T-04-01 / T-07-12: 요약 델타 줄·예외 로그는 정수 카운트·심볼·타입명만 (API 키·예외 원문 미포함)"
metrics:
  duration: "~13 min"
  completed: "2026-06-18"
  tasks: 3
  files_changed: 3
---

# Phase 7 Plan 04: 히스토리 경로 main 실행 배선 Summary

FUND-07/08 을 실행 진입점에 연결 — `main_run.run()` 의 PASS1/PASS2 시트1 경로(D-06 불변) 이후·요약 직전에 **시트1과 완전 분리된 별도 순차 루프**(D-07)로 종목별 `sync_ticker_history(ticker, source)` 를 호출하고, run 시작부에 `fund_store.reset_delta_stats()` 를 추가, 요약 블록에 델타 HIT/MISS·full-fetch 줄을 더했다(정수 카운트만, T-04-01). `.gitignore` 에 `data/` 를 추가해 `data/fundamentals.db` 미커밋(SC5). 통합 테스트 5종이 "평소 실행 full-fetch 0(SC3)"·"시트1 on/off 셀 단위 불변(D-07)"·"DB 누적(SC1)"·"`.cache/` 불변(SC5)"·"히스토리 실패 시 시트1 보호(T-07-11)"를 네트워크 0 으로 입증, 전 스위트 308 passed(회귀 0).

## What Was Built

- **`src/stocksig/main_run.py`** (+41 lines, 시트1 경로 무수정):
  - import 추가: `fundamentals_delta`, `fundamentals_store as fund_store`.
  - **(a)** run 시작부 카운터 reset — `cache.reset_cache_stats()` 옆에 `fund_store.reset_delta_stats()`.
  - **(b)** PASS2 `wb.close()`(finally) 이후·요약 블록 직전에 **별도 순차 루프** 삽입(D-07): `for s in specs:` → `classify_market` US→`source="EDGAR"` / KR→`"DART"`, 인증 실패 소스(`auth.edgar_ok`/`dart_ok is False`)·US/KR 외 폴백 종목 skip. 각 호출을 `try/except Exception` 으로 감싸 히스토리 실패가 시트1 산출물(이미 저장됨)을 깨지 않게 하고, 예외는 `type(exc).__name__` 만 로그(T-04-03/T-07-12).
  - **(c)** 요약 블록 캐시 줄 옆에 `delta = fund_store.get_delta_stats()` → `logger.info("히스토리: 델타 HIT %d/MISS %d · full-fetch %d", ...)` (정수만, T-04-01).
  - PASS1 `run_all` / PASS2 `write_portfolio_sheet`·`write_sheet_for_ticker` 블록 **한 줄도 미수정**(D-06).

- **`.gitignore`** (+1 line): `.cache/`·`docs_cache/` 근처에 `data/` 추가 — `git check-ignore data/fundamentals.db` → IGNORED (T-07-13).

- **`tests/test_history_integration.py`** (신규, 252 lines, 네트워크 0):
  - `test_run_creates_history_db`(SC1): probe accession + state 부재 → full-fetch → `count_rows > 0`·`last_accession` 갱신·`full_fetch == 1`.
  - `test_steady_state_history_zero_full_fetch`(SC3): 2종목 delta_state 시드 + probe 동일 accession → fetch spy `.call_count == 0`·`full_fetch == 0`·`delta_hit == 2`.
  - `test_sheet1_unchanged_by_history`(D-07): 히스토리 mock **off(probe None)** vs **on(델타 감지·실제 누적)** 두 run() 의 `write_portfolio_sheet` 인자(results scalars/failures/input_order) **와** 산출 xlsx 시트1 셀(값·폰트색) 스냅샷을 직접 비교해 동일 단언. ON 실행이 `count_rows > 0` 로 진짜 다른 경로였음도 확인 — 막연한 회귀 통과 비의존.
  - `test_cache_dir_unchanged_by_history`(SC5): 2회 run() 전후 `.cache/` 파일 목록(os.walk)이 불변 + `count_rows > 0` — data/ 와 .cache/ 분리.
  - `test_history_failure_does_not_break_sheet1`(T-07-11): `sync_ticker_history` RuntimeError → run() 이 시트1·종목 시트 정상 저장.

## Verification Results

- `uv run python -m pytest tests/test_history_integration.py -x -q` → **5 passed** (28.55s).
- `uv run python -m pytest -q` 전 스위트 → **308 passed** (399.52s). 베이스라인 303 + 신규 5, 회귀 0 — 히스토리 배선은 additive(D-06/D-07 입증). 경고 4건은 기존 edgartools `dei:EntityCommonStockSharesOutstanding` UserWarning(본 plan 무관, 범위 외).
- `git check-ignore data/fundamentals.db` → `data/fundamentals.db` / IGNORED (SC5).
- Acceptance grep: main_run.py 에 `fundamentals_delta.sync_ticker_history`·`fund_store.reset_delta_stats()`·`"히스토리: 델타 HIT %d/MISS %d · full-fetch %d"` 존재. 히스토리 루프가 `wb.close()`(finally) 이후 위치, 종목 호출 try/except 보호. PASS1/PASS2 블록 무수정.

## Commits

- `971e544` chore(07-04): .gitignore data/ — fundamentals.db 미커밋 (SC5)
- `42336e6` feat(07-04): run() 히스토리 경로 배선 + 델타 카운터 reset/요약 (D-07)
- `fce2e79` test(07-04): 히스토리 경로 통합 테스트 5종 (≈0 호출·시트1 불변·DB 생성·실패 격리)

## Deviations from Plan

### 환경 조정 (acceptance 의도 보존)

**1. [Rule 3 - Blocking] pytest 실행 = `uv run python -m pytest` (시스템 python 미설치)**
- **Found during:** Task 2/3 verify
- **Issue:** 시스템 `python -m pytest` 는 pytest 미설치(`No module named pytest`). 프로젝트는 `.venv` + `uv` 러너(07-03 SUMMARY 와 동일).
- **Fix:** verify 명령을 `uv run python -m pytest ...` 로 실행(플랜 `python -m pytest` 의도 = 프로젝트 테스트 러너). 신규 패키지 설치 0.
- **Files modified:** 없음 (실행 환경만).

**2. [Plan 조정] 인증 실패 소스 skip 가드 추가**
- 플랜 action 의 "인증 실패 소스는 skip" 을 명시적 `if auth.edgar_ok is False / dart_ok is False: continue` 로 구현(probe 가 어차피 실패할 소스의 불필요한 throttle 대기·로그 방지). 동작·계약 동일(Rule 2 — 불필요 외부 호출 차단).

**3. [테스트 보강] D-07 시트1 불변을 인자 스냅샷 + xlsx 셀 스냅샷 이중 단언**
- 플랜은 "write_portfolio_sheet 결과 스냅샷 비교" 를 요구 — write_portfolio_sheet 호출 인자(spy)와 산출 xlsx 시트1 셀(값·폰트색)을 **둘 다** 비교해 D-07 회귀 위험 0 을 강하게 입증. ON 실행의 실제 누적(`count_rows > 0`)도 단언해 두 경로가 진짜 달랐음을 보장.

## Known Stubs

None — 본 plan 으로 FUND-07/08 가 실행 진입점에 완전 연결됨(`uv run python main.py` 시 분기 raw 누적·평소 ≈0). 시트1 fetch ↔ 히스토리 probe 단일 원천 통합은 D-07 에 따라 의도적으로 Phase 10 으로 이연(드문 분기 경계 이중 호출 허용, 시트1 회귀 위험 0 우선).

## Threat Model Compliance

- **T-07-11 (DoS, 히스토리 예외 → 시트1 중단)** mitigate: 종목별 try/except + PASS2 `wb.close()` 이후 호출(시트1 이미 저장). `test_history_failure_does_not_break_sheet1` GREEN.
- **T-07-12 (Information Disclosure, 요약/예외 로그)** mitigate: 요약 델타 줄 = 정수 카운트만, 예외 로그 = `type(exc).__name__` + 심볼만. API 키·예외 원문 보간 0.
- **T-07-13 (Information Disclosure, DB git 커밋)** mitigate: `.gitignore` `data/`(Task 1), `git check-ignore` IGNORED 검증.
- **T-07-SC (패키지 설치)** accept: 신규 외부 패키지 0 (기존 모듈 배선만).

## Threat Flags

신규 trust boundary 표면 없음 — 히스토리 루프는 07-03 `sync_ticker_history`(기존 probe/fetch 경로) 호출만, run() 은 기존 import·로깅 패턴 재사용. 신규 네트워크 엔드포인트·auth·파일 접근·스키마 변경 0.

## Notes for Downstream Plans

- **Phase 8 (지표 계산)**: 평소 실행에서 히스토리 full-fetch ≈0 보장(SC3 입증) — DB `raw_facts` 만으로 저량/유량 TTM/하이브리드 지표 계산. `fund_store.count_rows`/raw 조회 API 소비.
- **Phase 10 (단일 원천 통합)**: D-07 의 분기 경계 시트1↔히스토리 이중 외부 호출은 단일 원천 이관 시 자연 해소 — 본 plan 은 의도적으로 분리 유지(시트1 회귀 위험 0 우선).
- 히스토리 경로 대상은 현재 EDGAR/DART 종목만 — yf/Naver 전용 폴백 종목 분기라벨 보완은 deferred(접수번호 개념 부재).

## Self-Check: PASSED

- FOUND: tests/test_history_integration.py (252 lines, 5 tests)
- FOUND: src/stocksig/main_run.py (히스토리 루프 + reset + 요약 줄)
- FOUND: .gitignore (data/ 라인)
- FOUND commit: 971e544
- FOUND commit: 42336e6
- FOUND commit: fce2e79
