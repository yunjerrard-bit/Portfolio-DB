---
phase: 08-registry
plan: 01
subsystem: 펀더멘털 지표 계산 (선행 진실 + 입력 경로 + 테스트 스캐폴드)
tags: [fundamentals, metrics, spike, store, tdd-scaffold, FUND-09]
requires:
  - "raw_facts 테이블 (07-01 fundamentals_store, PK ticker/source/quarter/field)"
  - "기존 fixture dart_005930_finstate.py / edgar_aapl_facts.py (03-02 spike)"
provides:
  - "fundamentals_store.fetch_raw_quarters(ticker) — 엔진 raw 조회 진입점"
  - "tests/fixtures/raw_quarters.py::raw_row — 12-tuple 분기 행 builder"
  - "tests/test_metrics_engine.py — 엔진 -k 마커 RED 스캐폴드 + fetch_raw_quarters GREEN"
  - "DART thstrm_amount=분기 단독값 / EDGAR Q4 갭 진실 확정 (08-03 산식 방침 입력)"
affects:
  - "08-03 Wave 2 metrics_engine (산식 방침·store 입력·테스트 스캐폴드 직접 소비)"
tech-stack:
  added: []
  patterns:
    - "?-바인딩 SELECT (ASVS V5) — count_rows analog, 신규 connection 금지"
    - "디폴트 인자 12-tuple 팩토리 (test_fundamentals_store._row 스타일)"
    - "pytest.skip RED 스캐폴드 — 미존재 엔진 모듈을 collect만 통과"
key-files:
  created:
    - "tests/test_raw_semantics_spike.py"
    - "tests/fixtures/raw_quarters.py"
    - "tests/test_metrics_engine.py"
  modified:
    - "src/stocksig/io/fundamentals_store.py (fetch_raw_quarters 추가)"
decisions:
  - "DART 손익 thstrm_amount = 분기 단독값(누적은 thstrm_add_amount) → 08-03 단순 4분기 합 TTM, YTD 분해 미구현"
  - "EDGAR raw에 캘린더 Q4·FY duration 부재 → Q4=빈값+사유(D-05), FY−9M 보정 미구현(자연 결손)"
metrics:
  duration: ~10 min
  completed: 2026-06-19
  tasks: 2
  files: 4
---

# Phase 8 Plan 01: raw 진실 확정 + 입력 경로 + 테스트 스캐폴드 Summary

Phase 8 산식의 옳고 그름을 좌우하는 2개 raw-data 의미 갭(DART 분기/누적·EDGAR Q4)을
fixture 기반 spike로 확정·박제하고, 08-03 엔진이 읽을 `fetch_raw_quarters` 조회 헬퍼·
분기 행 builder·엔진 테스트 RED 스캐폴드를 제공한다.

## What Was Built

- **raw 진실 확정 spike** (`tests/test_raw_semantics_spike.py`): 네트워크 0, 기존 fixture만 사용.
  - `test_dart_quarter_semantics` — 005930 실응답에서 thstrm_amount가 분기/기간 단독값이고
    누적은 별도 `thstrm_add_amount` 컬럼(본 응답 빈값)임을 교차 단언.
  - `test_edgar_q4_gap_absent` — AAPL 분기 store에 캘린더 Q4 손익 duration·FY duration이
    부재함을 단언(저장 키 Q1~Q3만).
- **store 조회 헬퍼** (`fundamentals_store.fetch_raw_quarters`): raw_facts를 quarter 오름차순
  `?-바인딩` SELECT(ASVS V5, T-08-01), `(quarter, source, field, value, period_type, reprt_code, unit)` 반환.
- **raw 행 builder** (`tests/fixtures/raw_quarters.py::raw_row`): 디폴트 인자 12-tuple,
  EDGAR duration·DART reprt_code·BS instant·결손(None) 전부 표현.
- **엔진 테스트 스캐폴드** (`tests/test_metrics_engine.py`): fetch_raw_quarters 2종 GREEN +
  `test_type_rules/reproduce/ttm_missing/provenance_or_pershare/edgar_q4` 5종 RED(skip).

## 08-03 직접 입력 (필수 기록)

1. **DART thstrm_amount 확정 = 분기 단독값** (누적은 thstrm_add_amount, OpenDART DS003 + 005930 fixture 교차).
   → **08-03 DART TTM 방침: 단순 4분기 thstrm_amount 합 = TTM. YTD 분해(thisQ누적−직전Q누적) 로직 미구현.**
   STATE의 "DART YTD 분해" 가정은 철회된다.

2. **EDGAR Q4 갭 확정 = 캘린더 Q4 손익 단독값·FY duration 모두 raw 부재** (by_period_length(3)만 저장).
   → **08-03 EDGAR Q4 방침: Q4 유량 지표 = 빈값+사유(D-05, 0/-999999 금지). Q4=FY−9M 보정은
   FY raw 부재로 수행 불가 → Q4 보정 로직 미구현, Q4 행 자연 결손.** FY duration 저장 추가는 범위 밖.

3. **fetch_raw_quarters 시그니처:**
   `fetch_raw_quarters(ticker: str) -> list[tuple]` —
   각 행 `(quarter, source, field, value, period_type, reprt_code, unit)`, quarter 오름차순, 미존재 ticker → `[]`.

## Verification Results

- `uv run pytest tests/test_raw_semantics_spike.py -x -q` → 2 passed (네트워크 0).
- `uv run pytest tests/test_metrics_engine.py -q` → 2 passed, 5 skipped (collect 무에러).
- `uv run pytest tests/test_metrics_engine.py -k "fetch_raw_quarters" -x -q` → 2 passed.
- 전 스위트 `uv run pytest -q` → **312 passed, 5 skipped** (회귀 0, store 헬퍼 additive).

## Deviations from Plan

**1. [Rule 3 - Blocking] fixture import 경로 수정**
- **Found during:** Task 1 (spike 첫 실행)
- **Issue:** `from tests.fixtures...` import가 `ModuleNotFoundError: No module named 'tests'`로 실패.
- **Fix:** 프로젝트 테스트 컨벤션(`from fixtures.X import ...`, rootdir가 tests를 path에 추가)에 맞춰 수정.
- **Files modified:** tests/test_raw_semantics_spike.py
- **Commit:** 021a15e

이외 plan대로 실행. 신규 패키지 설치 없음, 외부 네트워크/인증 호출 없음.

## TDD Gate Compliance

`type: tdd` plan — RED/GREEN gate 충족:
- RED gate: `test(08-01)` 커밋 021a15e (fixture 기반 spike — 진실 단언).
- GREEN gate: `feat(08-01)` 커밋 48e32b9 (fetch_raw_quarters store 헬퍼 + 검증 통과).
- 엔진 계산 테스트 5종은 의도된 RED 스캐폴드(`pytest.skip`)로, 08-03이 채운다.

## Self-Check: PASSED

- FOUND: tests/test_raw_semantics_spike.py
- FOUND: tests/fixtures/raw_quarters.py
- FOUND: tests/test_metrics_engine.py
- FOUND: src/stocksig/io/fundamentals_store.py::fetch_raw_quarters
- FOUND commit: 021a15e
- FOUND commit: 48e32b9
