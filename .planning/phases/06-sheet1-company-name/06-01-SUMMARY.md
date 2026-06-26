---
phase: 06-sheet1-company-name
plan: 01
subsystem: output / io
tags: [company-name, sheet1, yfinance-info, cache, column-shift]
requires:
  - "stocksig.io.market._SESSION (curl_cffi Chrome 단일 세션)"
  - "stocksig.io.throttle.throttled_yahoo (2 RPS limiter)"
  - "stocksig.io.cache (diskcache 네임스페이스 패턴)"
  - "stocksig.runner.run_all / process_ticker (fan-out 오케스트레이션)"
  - "stocksig.output.sheet_portfolio.write_portfolio_sheet (시트1 writer)"
provides:
  - "stocksig.io.company.fetch_company_name(ticker) — 캐시 우선 영문 기업명 조회"
  - "stocksig.io.cache company 네임스페이스 (30일 TTL, name_hit/name_miss)"
  - "TickerResult.company_name 필드 + process_ticker/run_all company_name_fn 배선"
  - "시트1 22열 (기업명 index 1) + _COL 헤더 기반 명명 인덱스 단일 진실 출처"
affects:
  - "src/stocksig/output/sheet_portfolio.py (전 정수 col → _COL 명명 인덱스)"
  - "src/stocksig/runner.py (TickerResult + 시그니처 + executor.submit 배선)"
  - "src/stocksig/main_run.py (fetch_company_name 주입 + 요약 로그)"
tech-stack:
  added: []
  patterns:
    - "헤더 기반 명명 인덱스(_COL)로 컬럼 시프트 회귀 구조적 차단 (RESEARCH Pattern 3)"
    - "company 캐시 네임스페이스를 펀더멘털 캐시 구조로 복제 (30일 TTL, _stats 자동 초기화)"
    - "fetch 예외 흡수 + 티커 폴백 — 기업명 결손 ≠ 티커 실패 (D-disc-10)"
key-files:
  created:
    - "src/stocksig/io/company.py"
    - "tests/test_company_name.py"
  modified:
    - "src/stocksig/io/cache.py"
    - "src/stocksig/runner.py"
    - "src/stocksig/main_run.py"
    - "src/stocksig/output/sheet_portfolio.py"
    - "tests/test_sheet_portfolio.py"
    - "tests/test_smoke_end_to_end.py"
    - "tests/test_freeze_panes.py"
    - "tests/test_cache.py"
decisions:
  - "기업명 폴백 체인 longName → shortName → 티커 (longName 1순위, shortName KR 쓰레기값 가드)"
  - "company 캐시 30일 TTL (기업명 안정적, 날짜 무관 키) — 재실행 무호출 (COMPANY-04)"
  - "실패행 HIGH-1 단일 규칙: 현행 동작을 _COL 기반으로 한 칸 우측 시프트 (티커=col1, 기업명=col2 빈칸, ?=col3, reason=col18)"
  - "freeze_panes(5, 1) 불변 — A열만 고정, 기업명(B) 비고정 → openpyxl 'B6' 불변"
  - "폴백값(티커)은 캐시에 put 하지 않음 — 다음 실행 재시도 허용"
metrics:
  duration: "약 35분 (이어받기 — Task 1 중단 복구 포함)"
  tasks_completed: 4
  tasks_total: 5
  files_created: 2
  files_modified: 8
  tests: "259 passed (네트워크 없음)"
  completed_date: "2026-06-16"
---

# Phase 6 Plan 01: 시트1 영문 기업명(B열) Summary

시트1(통합 포트폴리오)의 티커(A)와 시장(C) 사이에 영문 기업명 B열을 추가하고, 컬럼 1칸 시프트 위험을 `_COL` 헤더 기반 명명 인덱스로 구조적으로 차단했다. 기업명은 yfinance `.info`(longName→shortName→티커)에서만 조회하며 30일 캐시·2 RPS throttle·5회 retry 정책을 따른다.

## What Was Built

Tasks 1–4 (자동 TDD)를 완료했다. Task 5(human-verify checkpoint, `gate="blocking"`)는 **PENDING** — 실행하지 않았다(아래 참조).

- **Task 1 (RED)** `a6fc84f` — `tests/test_company_name.py`(7건: longName/shortName/티커 폴백, 캐시 HIT 무호출, MISS 후 put, YFRateLimitError 흡수) + `tests/test_sheet_portfolio.py` 좌표 +1 시프트·22열 카운트·실패행 HIGH-1 단일 규칙(col3="?", col18=reason)·신규 `test_company_name_column`. 구현 전이므로 `ModuleNotFoundError`로 의도된 RED.
- **Task 2 (GREEN)** `39f4e76` — `io/company.py`(`fetch_company_name` 캐시 우선 + `@throttled_yahoo` + `@retry(YFRateLimitError 5회)` + `_SESSION` 재사용 + `_pick_name` 폴백 + 예외 흡수 티커 폴백) + `cache.py` company 네임스페이스(`_NAME_DIR`, `_NAME_TTL_SECONDS=30일`, `get/put_company_name`, `name_hit/name_miss`). company 테스트 7건 GREEN.
- **Task 3 (GREEN)** `217ca55` — `sheet_portfolio.py` 22열(기업명 index 1) + `_COL` 단일 진실 출처 + 전 정수 col → `_COL["헤더명"]` 치환 + 기업명 셀 write(`res.company_name or spec.symbol`) + 실패행 HIGH-1 시프트 + `freeze_panes(5,1)` 불변. `runner.py` `TickerResult.company_name` 필드 + `process_ticker`/`run_all`에 `company_name_fn` + **`executor.submit` 실제 배선**. `main_run.py` `fetch_company_name` 주입 + 요약 로그 기업명 HIT/MISS. sheet_portfolio + freeze 테스트 GREEN.
- **Task 4 (회귀)** `563ecc8` — smoke/freeze 테스트에 기업명 fetch stub(네트워크 격리, Pitfall 5) + 시트1 B5="기업명" 헤더 단언 + 데이터행 B열 not-empty 단언(HIGH-2). 전체 스위트 그린.

## Verification Results

- `uv run pytest -q` 전체 스위트: **259 passed, 0 failed** (네트워크 없음 — 모든 yfinance `.info`/`.history` mock/stub).
- 시트1 헤더 22열, index 1 == "기업명", index -4: == ["PER","PEG","GPM","OPM"].
- 시트1 B5 == "기업명" + 데이터행 B열 not-empty 단언 존재 (HIGH-2).
- 실패행 단일 규칙: A=티커(col1), B(기업명)=빈칸(col2), C(시장)="?"(col3), 마지막 임펄스(col18)=실패 reason (HIGH-1).
- `freeze_panes` "B6" 불변 (test_freeze_panes 3건 무수정 통과).
- `company.py`가 `market._SESSION` 재사용 + `@throttled_yahoo` + `@retry` 보유, 신규 세션 미생성 (grep 0건).
- `run_all → executor.submit`에 `company_name_fn` 실제 전달 (HIGH-3 배선).
- cache.py company 네임스페이스 30일 TTL + name_hit/name_miss + reset_cache_stats 자동 초기화.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_sheet_portfolio.py 펀더멘털 4셀 좌표 미시프트**
- **Found during:** Task 3
- **Issue:** 이어받기 시점에 `test_sheet_portfolio.py`의 펀더멘털 테스트(`test_fund_cols`/`test_fund_missing_cell_blank_with_note`/`test_fund_none_backward_compat`/`test_fund_failure_row_no_fund_cells`)와 실패행 테스트가 +1 시프트 좌표(18~21→19~22, "?" col2→col3, reason col17→col18)로 갱신되지 않은 채 구버전 좌표를 유지하고 있었다. 이는 Task 1의 RED 테스트 작업이 중단으로 인해 미완성이었던 부분이다.
- **Fix:** 펀더멘털 4셀 좌표를 19~22로, 실패행 "?"를 col3, reason을 col18로 갱신. 신규 `test_company_name_column` 추가, `_result` 헬퍼에 `company_name` 인자 추가(기본 None).
- **Files modified:** tests/test_sheet_portfolio.py
- **Commit:** a6fc84f (RED 보강) / 217ca55 (GREEN 시점 좌표 정렬)

**2. [Rule 1 - Bug] test_cache.py::test_reset_then_get_stats_all_zero 정확 일치 단언 회귀**
- **Found during:** Task 4 (전체 스위트 실행)
- **Issue:** Task 2에서 `_stats`에 `name_hit`/`name_miss` 키를 추가하자, `get_cache_stats()`의 정확 dict 일치를 단언하던 기존 테스트가 신규 키 2개 때문에 실패(`Left contains 2 more items`).
- **Fix:** 해당 테스트의 기대 dict에 `name_hit: 0`, `name_miss: 0` 추가 (interfaces 블록의 "신규 키도 reset에서 0 초기화" 계약과 일치).
- **Files modified:** tests/test_cache.py
- **Commit:** 563ecc8

**3. [Rule 1 - 정정] company.py 도크스트링 false-positive 회피**
- **Found during:** Task 2 (acceptance grep 검증)
- **Issue:** acceptance 기준 `Session\(impersonate|curl_cffi` 매치 0건을 요구하나, 도크스트링의 "신규 curl_cffi/httpx 세션 생성 금지" 문구가 false-positive로 1건 매치됨.
- **Fix:** 도크스트링 "curl_cffi/httpx" → "TLS"로 문구만 변경 (코드/동작 무변경). 실제 신규 세션 생성은 없으며 `_SESSION` 재사용만 한다.
- **Files modified:** src/stocksig/io/company.py
- **Commit:** 39f4e76

**4. [Rule 1 - Bug] yfinance longName 콤마-결합 식별자 쓰레기값 (체크포인트 발견)**
- **Found during:** Task 5 (휴먼 검증 체크포인트 — 실제 워크북 생성 후 시트1 검증)
- **Issue:** yfinance `.info["longName"]`이 일부 KR 종목(263750/348210/382900.KS)에 `"263750.KS,0P0001BL7Y,135285"`(티커 + Morningstar PerformanceID + 숫자) 같은 콤마-결합 식별자 쓰레기 문자열을 반환. truthy라서 `_pick_name`의 폴백을 통과해 시트1 B열에 사람이 읽을 수 없는 값이 표시됨. PLAN은 "shortName 쓰레기값"은 예상했으나 "longName 자체가 쓰레기"인 케이스는 미가드.
- **Fix:** `_is_junk_name(candidate, ticker)` 가드 추가 — 콤마-분리 토큰 중 티커 자신 또는 `0P`-prefixed Morningstar ID 패턴이 있으면 거부하고 다음 후보(shortName→티커)로 폴백. 정상 콤마 포함 기업명("Samsung Electronics Co., Ltd.")은 통과. `_pick_name`을 가드 경유 루프로 리팩터. 신규 테스트 2건(junk→티커 폴백, junk longName + clean shortName→shortName).
- **Verify:** `uv run pytest -q` → 261 passed(259+2). 재생성 워크북에서 3종목 모두 티커 폴백 확인(263750.KS→"263750.KS" 등), 정상 KR 영문명 무회귀.
- **Files modified:** src/stocksig/io/company.py, tests/test_company_name.py
- **Commit:** 86db0bf

### Resume-state 정정

이어받기 컨텍스트는 `test_sheet_portfolio.py`가 "실패행 시프트 좌표(col3, col18)를 이미 포함"한다고 명시했으나, 실제 파일은 구버전 좌표(col2/col17)와 미시프트 펀더멘털 좌표(18~21)를 유지하고 있었다. 명세(PLAN behavior/acceptance)를 권위로 삼아 좌표를 전수 정정했다 (위 Deviation 1).

## Task 5 — APPROVED (Human-Verify Checkpoint, BLOCKING) ✅

오케스트레이터가 `uv run python main.py`로 실제 워크북(`output/portfolio_20260616.xlsx`, 125종목/성공 124/실패 1=ZZZZZ, 기업명 HIT/MISS 로그 확인)을 생성하고 시트1을 openpyxl로 객관 검증 + 사용자 Excel 육안 검증을 거쳐 **2026-06-16 "APPROVED"** 처리됨. 검증 중 발견된 longName 쓰레기값 이슈는 가드(커밋 86db0bf)로 수정 후 재생성·재검증 완료(위 Deviation 4).

### 검증 방법 (PLAN Task 5 보존)

생성 명령:
```
cd "C:/Users/kimyunjae/Documents/Claude 앱 개발/example"; uv run python main.py
```
출력: `output/portfolio_YYYYMMDD.xlsx`. 첫 실행은 기업명 캐시 MISS(.info 왕복), 재실행은 캐시 HIT(무호출) — 요약 로그 "기업명 HIT/MISS"로 확인.

1. 생성된 `.xlsx`를 Excel로 열어 "시트1" 선택.
2. B5 헤더가 "기업명"인지, A열(티커)과 C열(시장) 사이인지 확인.
3. 각 성공 티커 행 B열에 영문 기업명(예: AAPL→"Apple Inc.", 005930.KS→"Samsung Electronics Co., Ltd." 영문)이 표시되는지. 한국 종목도 영문인지.
4. 기업명 결손 종목 B열에 티커가 폴백 표시되는지 (빈칸 아닌지).
5. 컬럼 시프트 후 기존 열 정상: 시장(C)·티어·산업·최신 종가·전일 등락률·DIFF EMA 색·거래량·Stoch/RSI·(일)/(주)임펄스 색·펀더멘털 PER/PEG/GPM/OPM 값·주석이 올바른 열에 있고 색 미손상인지.
6. A열 티커 하이퍼링크 클릭 → 해당 종목 시트 이동.
7. 스크롤 시 1~5행 + A열(티커) 고정 (freeze B6 — 기업명은 함께 스크롤).
8. 실패 티커가 있으면 실패 행 마커: A=티커, B(기업명)=빈칸, C(시장)="?", 마지막 임펄스 열="실패: ...".
9. (선택) 두 번째 실행 후 콘솔 요약의 기업명 캐시 HIT 증가 (재실행 무호출 = COMPANY-04).

**Resume signal:** 정상 확인 시 "approved" 입력. 문제 발견 시 어느 열/색/행이 어떻게 어긋났는지 기술.

## Known Stubs

없음 — Task 1–4는 production 코드를 완전히 구현했다. 테스트의 기업명 stub(smoke/freeze)은 네트워크 격리용 테스트 더블이며 production 경로는 실제 `fetch_company_name`을 사용한다(Task 5에서 사용자 검증).

## Self-Check: PASSED

- FOUND: src/stocksig/io/company.py
- FOUND: tests/test_company_name.py
- FOUND: .planning/phases/06-sheet1-company-name/06-01-SUMMARY.md
- FOUND commit: a6fc84f (Task 1 RED)
- FOUND commit: 39f4e76 (Task 2 GREEN)
- FOUND commit: 217ca55 (Task 3 GREEN)
- FOUND commit: 563ecc8 (Task 4 회귀 그린)
- FOUND commit: 86db0bf (Task 5 체크포인트 발견 가드 수정)
- APPROVED: Task 5 human-verify checkpoint (2026-06-16)
