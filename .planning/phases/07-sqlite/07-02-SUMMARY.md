---
phase: 07-sqlite
plan: 02
subsystem: io/fundamentals-fetch
tags: [edgar, dart, per-quarter, raw, backfill, calendar-quarter, FUND-07]
requires:
  - "07-01: fundamentals_store upsert_quarters 12-tuple 컬럼 계약 (행 형태 정합 대상)"
provides:
  - "fetch_edgar_quarterly_raw(ticker) — get_facts 1회 per-quarter 손익·BS·CF·발행주식수 raw 행 (D-01/D-04)"
  - "fetch_dart_quarterly_raw(ticker, years=3) — 최근 N년 finstate_all 분기 백필 raw 행 (D-01/D-04)"
  - "dart_account_map BS/CF/shares 매핑 + SJ_DIV_BALANCE_SHEET/SJ_DIV_CASHFLOW 상수"
  - "dart_client _get_dart() OpenDartReader 싱글톤 (Pitfall 1, 07-03 공유)"
affects:
  - "Plan 03 (델타): rcept_no/accession 비교 + 싱글톤 _get_dart 재사용"
  - "Plan 04 (오케스트레이션): 추출기 → upsert_quarters 누적"
  - "Phase 8 (지표 계산): D-03 슈퍼셋(ROE/PBR/부채비율) 외부 재호출 0 계산"
tech-stack:
  added: []  # 신규 외부 패키지 0 (edgartools/opendartreader 기존 의존)
  patterns:
    - "cache.py double-checked locking 싱글톤 복제 (OpenDartReader 대상, corp_codes 1회)"
    - "get_display_period_key 'Q2 2026' → 'YYYYQn' 캘린더 분기 정규화 (D-08)"
    - "EDGAR query 빌더 by_concept/by_period_type/by_period_length 추출"
key-files:
  created:
    - tests/test_edgar_quarterly.py
    - tests/test_dart_quarterly.py
  modified:
    - src/stocksig/io/dart_account_map.py
    - src/stocksig/io/edgar_client.py
    - src/stocksig/io/dart_client.py
    - tests/fixtures/edgar_aapl_facts.py
    - tests/fixtures/dart_005930_finstate.py
decisions:
  - "D-01 적용: EDGAR get_facts 1회 공짜 backfill / DART years=3 finstate_all 루프 차등"
  - "D-04 적용: EDGAR duration(손익·CF)/instant(BS) query 분리, DART SJ_DIV_BALANCE_SHEET/CASHFLOW 필터"
  - "D-08 적용: quarter 키 = period 종료일 기준 캘린더 분기 'YYYYQn' (EDGAR display_period_key·DART bsns_year+reprt_code)"
  - "D-05 적용: 결손 value=None (0/-999999 금지)"
  - "D-06 적용: 기존 fetch_edgar_raw/fetch_dart_raw 시트1 TTM 경로 불변 (회귀 0)"
  - "Pitfall 1: OpenDartReader 모듈 싱글톤(_dart_singleton) double-checked lock"
metrics:
  duration: "~20 min"
  completed: "2026-06-18"
  tasks: 3
  files_changed: 7
---

# Phase 7 Plan 02: 펀더멘털 per-quarter raw 추출 Summary

Phase 3 fetch 층에 per-quarter raw 추출 경로를 additive로 추가 — EDGAR `fetch_edgar_quarterly_raw`(get_facts 1회로 손익5종·영업현금흐름·BS3종·발행주식수 분기 행 추출, D-01 공짜) 와 DART `fetch_dart_quarterly_raw`(최근 3년 finstate_all 분기 백필, D-01 차등), 그리고 `dart_account_map`에 D-03 슈퍼셋 BS/CF/shares 매핑·sj_div 상수를 추가했다. 모든 행은 D-08 캘린더 분기키("YYYYQn")·accession·결손 None(D-05)을 부여하며, 기존 시트1 TTM 경로는 불변(D-06)이다.

## What Was Built

- **`src/stocksig/io/dart_account_map.py`** (Task 1, additive):
  - `DART_ACCOUNT_ID_MAP`/`DART_ACCOUNT_MAP`에 신규 키 `total_equity`/`total_liabilities`/`total_assets`/`operating_cash_flow` + placeholder `shares_outstanding` (id 1차 IFRS 표준 태그, nm 2차 한글 후보).
  - `SJ_DIV_BALANCE_SHEET = ("BS",)` / `SJ_DIV_CASHFLOW = ("CF",)` 상수.
  - 신규 account_id는 `# [Open Q2 — 005930 BS/CF 실응답 1회 확정 후 VERIFIED]` 주석. shares는 finstate_all 통상 부재 → Phase 8/yf 위임 명시(본 plan API 호출 0).
  - 기존 5종 키·`SJ_DIV_INCOME_STATEMENT` 불변.

- **`src/stocksig/io/edgar_client.py`** (Task 2, additive):
  - `fetch_edgar_quarterly_raw(ticker) -> list[dict]` (`@throttled_edgar`) — `Company(ticker).get_facts()` **1회**(D-01) 후 query 빌더로 추출: duration(`by_period_length(3)`) = revenue/gross_profit/op_income/net_income/eps/operating_cash_flow, instant = total_equity/total_liabilities/total_assets, + `shares_outstanding_fact`(있으면).
  - `_calendar_quarter_key` — `get_display_period_key()` "Q2 2026" → "2026Q2" (D-08).
  - `_fact_to_row` — value=`numeric_value`(None-safe, D-05)·accession·period_start/end(ISO)·period_type·reprt_code=None.
  - `_query_facts` try/except 흡수, `_instant_fallback`([A5] get_total_assets/get_shareholders_equity 헬퍼).
  - 기존 `fetch_edgar_raw`·`fetch_edgar_cached`·import-time set_identity 불변.

- **`src/stocksig/io/dart_client.py`** (Task 3, additive):
  - `fetch_dart_quarterly_raw(ticker, years=3) -> list[dict]` (`@throttled_dart`) — `for year in range(this_year-years, this_year+1): for code in QUARTER_CODES` 루프(D-01, ~16 호출/3년). 손익은 `_income_rows`(IS/CIS), BS는 `SJ_DIV_BALANCE_SHEET`, CF는 `SJ_DIV_CASHFLOW` 필터 + `_match_amount`.
  - `_calendar_quarter_key(bsns_year, reprt_code)` — 11013→Q1/11012→Q2/11014→Q3/11011→Q4 (D-08).
  - 각 행 accession=rcept_no(매 행 동일 델타 키)·value None-safe(D-05)·period_type(손익·CF=duration/BS=instant)·YTD as-reported(분기 분해 Phase 8, Pitfall 4).
  - `_get_dart()` OpenDartReader 모듈 싱글톤(double-checked locking, Pitfall 1 corp_codes 1회) — 07-03 공유.
  - status dict/빈 df 가드로 미존재 분기 skip. 기존 `fetch_dart_raw`·`fetch_dart_cached` 불변.

- **fixture 확장**: `edgar_aapl_facts.py`(FakeFinancialFact/FakeQuery/FakeQuarterlyFacts query 빌더 mock + 2분기 손익·BS·CF·shares 행), `dart_005930_finstate.py`(BS_CF_ROWS/ALL_ROWS + EXPECTED_VALUES BS/CF 4종).
- **테스트 신규**: `test_edgar_quarterly.py`(8종), `test_dart_quarterly.py`(12종) — 모두 네트워크 0(mock).

## Verification Results

- `python -m pytest tests/test_edgar_quarterly.py -x -q` → **8 passed** (0.75s).
- `python -m pytest tests/test_dart_quarterly.py -x -q` → **12 passed** (5.49s).
- `python -m pytest tests/ -k edgar -q` → **29 passed** (회귀 0, fetch_edgar_raw 불변).
- `python -m pytest tests/ -k dart -q` → **33 passed** (회귀 0, fetch_dart_raw 불변).
- `python -m pytest -q` 전 스위트 → **297 passed** (324s). 베이스라인 277 + 신규 20, 회귀 0 — additive.
- Task 1 verify 명령 → `True True ('BS',) ('CF',)`, SJ_DIV_INCOME_STATEMENT 불변 확인.

## Commits

- `9ff6a93` feat(07-02): dart_account_map BS/CF 매핑 + SJ_DIV 상수 (D-04)
- `de9fa7f` feat(07-02): fetch_edgar_quarterly_raw per-quarter 추출 (D-01/D-04/D-08)
- `0437640` feat(07-02): fetch_dart_quarterly_raw 분기 백필 (D-01/D-04/D-08)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] dart_account_map 첫 Edit 가 잘못된 위치에 삽입 (자체 수정)**
- **Found during:** Task 1
- **Issue:** DART_ACCOUNT_MAP 신규 키 블록이 dict 닫는 `}` 뒤에 삽입되어 SyntaxError 유발.
- **Fix:** old_string 을 `eps` 라인 + 닫는 `}` 로 재지정해 dict 내부로 이동. import 검증 통과.
- **Files modified:** src/stocksig/io/dart_account_map.py
- **Commit:** 9ff6a93 (커밋 전 수정 완료)

### Plan 조정 (acceptance 의도 보존)

**2. test_dart_quarterly QUARTER_CODES 단언을 type-annotation 허용으로 완화**
- 소스는 `QUARTER_CODES: list[str] = ["11013", ...]`(type 주석) 로 선언 — 더 나은 관행. acceptance 의 정확 문자열 대신 `"QUARTER_CODES" in src` + 값 리스트 부분문자열로 검증(의도 동일).

## Known Stubs

- **`shares_outstanding` 매핑** (dart_account_map): placeholder 키. finstate_all 에 통상 부재(Open Q2 RESOLVED) → Phase 8 또는 yf 보완 위임이 의도된 설계(plan acceptance 명시). 본 plan 에서 별도 API 호출 추가 안 함. EDGAR 측은 `shares_outstanding_fact` 있으면 추출(있을 때만).
- 신규 BS/CF account_id 는 005930 실응답 미검증(`[Open Q2]` 주석) — API 키 부재로 실호출 미수행. id 1차 미스 시 한글 nm 2차 폴백으로 보강, Phase 8 첫 실호출 시 VERIFIED 승격 예정.

## Threat Model Compliance

- **T-07-04 (Tampering, thstrm 파싱)** mitigate: 기존 `_parse_amount`/`_match_amount`(쉼표 제거+int try/except) 재사용. 파싱 실패=None.
- **T-07-05 (Information Disclosure, 예외 메시지)** mitigate: query/헬퍼 try/except 는 타입 무관 흡수만, crtfc_key·예외 원문 로그 보간 없음(status 코드만 로그).
- **T-07-06 (Tampering, raw 오염)** mitigate: 결손=None(D-05), 0/-999999 0건. YTD 분해 없이 as-reported → Phase 8 산식 오염 차단.
- **T-07-SC (패키지 설치)** accept: 신규 외부 패키지 0.

## Threat Flags

신규 trust boundary 표면 없음 — 기존 EDGAR/DART 응답 파싱 경로 재사용(추가 네트워크 엔드포인트·auth·파일 접근 0).

## Notes for Downstream Plans

- 추출기 행 dict 키 = (ticker, source, quarter, field, value, unit, accession, period_start, period_end, period_type, reprt_code). Plan 01 `upsert_quarters` 12-tuple 과 컬럼 1:1(fetched_at 만 store 측 생성) — Plan 04 가 dict→tuple 변환 후 누적.
- DART `_get_dart()` 싱글톤은 07-03 `fundamentals_delta._get_dart()` 가 재사용(또는 본 모듈 싱글톤 공유)해 corp_codes 이중 다운로드 차단.
- EDGAR accession / DART rcept_no 가 행 `accession` 필드에 보존 — Plan 03 델타 비교(last_accession) 입력.

## Self-Check: PASSED

- FOUND: src/stocksig/io/dart_account_map.py (SJ_DIV_BALANCE_SHEET/CASHFLOW)
- FOUND: src/stocksig/io/edgar_client.py (def fetch_edgar_quarterly_raw)
- FOUND: src/stocksig/io/dart_client.py (def fetch_dart_quarterly_raw)
- FOUND: tests/test_edgar_quarterly.py
- FOUND: tests/test_dart_quarterly.py
- FOUND: tests/fixtures/edgar_aapl_facts.py (FakeQuarterlyFacts)
- FOUND: tests/fixtures/dart_005930_finstate.py (BS_CF_ROWS)
- FOUND commit: 9ff6a93
- FOUND commit: de9fa7f
- FOUND commit: 0437640
