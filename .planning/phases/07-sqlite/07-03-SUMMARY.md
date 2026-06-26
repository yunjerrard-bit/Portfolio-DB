---
phase: 07-sqlite
plan: 03
subsystem: io/fundamentals-delta
tags: [delta, accession, rcept_no, probe, skip, forward-accumulate, FUND-08, SC3]
requires:
  - "07-01: fundamentals_store get/set_last_accession + mark_delta_*/get_delta_stats 카운터 + upsert_quarters 12-tuple"
  - "07-02: fetch_edgar_quarterly_raw / fetch_dart_quarterly_raw 추출기 + dart_client._get_dart() 싱글톤"
provides:
  - "fundamentals_delta.sync_ticker_history(ticker, source, years=3) — probe→델타 비교→skip/refetch 오케스트레이션 (D-02 forward 누적)"
  - "probe_edgar_accession / probe_dart_rcept — 가벼운 메타 접수번호 probe (네트워크 비용 ≪ full-fetch)"
affects:
  - "Plan 04 (오케스트레이션): sync_ticker_history 를 종목 루프로 호출 + get_delta_stats run 요약"
  - "Phase 8 (지표 계산): 변경 없는 평소 실행 외부 호출 ≈0 — DB raw 만으로 계산"
tech-stack:
  added: []  # 신규 외부 패키지 0 (edgar/opendartreader 기존 의존, RESEARCH Audit [OK])
  patterns:
    - "probe(가벼운 메타) → delta_state 비교 → 같으면 SKIP / 다르면 full-fetch (D-02)"
    - "dart_client._get_dart() 싱글톤 공유 import (Pitfall 1 — corp_codes 이중 다운로드 차단)"
    - "probe/fetch 예외 전면 흡수 + 기존 DB 유지(보수적 재추출 금지, Pitfall 2)"
key-files:
  created:
    - src/stocksig/io/fundamentals_delta.py
    - tests/test_fundamentals_delta.py
  modified: []
decisions:
  - "D-02 적용: 저장 last_accession == probe → full-fetch·신규 저장 0(평소 ≈0, SC3) / 다르면 재추출·upsert·set_last_accession(forward 누적, SC4)"
  - "Pitfall 1: DART probe·fetch 모두 dart_client._get_dart() 싱글톤 재사용 — 별도 OpenDartReader 미생성(T-07-09)"
  - "Pitfall 2 / T-07-07: probe 실패(예외/None) + fetch 실패 → 갱신 생략·기존 DB 유지(보수적 재추출 금지 → 쿼터 폭주 차단)"
  - "T-04-03 / T-07-08: probe/fetch 예외 로그는 type(exc).__name__ 만 — crtfc_key·예외 원문 보간 0"
  - "dict 11-key 추출기 행 → store 12-tuple(+fetched_at) 변환은 delta 가 수행(_rows_to_tuples)"
metrics:
  duration: "~9 min"
  completed: "2026-06-18"
  tasks: 2
  files_changed: 2
---

# Phase 7 Plan 03: 접수번호 델타 오케스트레이션 Summary

FUND-08 의 핵심 — "새 분기/정정공시 없으면 외부 펀더멘털 전체 호출 ≈0" 을 구현. 신규 `fundamentals_delta.py` 가 가벼운 메타 probe(EDGAR `Company.latest("10-Q").accession_number` / DART `list(kind="A").iloc[0]["rcept_no"]`)로 최신 접수번호만 얻고, store(Plan 01)의 `delta_state`와 비교해 같으면 full-fetch 를 생략(SC3 평소 ≈0)·다르면 추출기(Plan 02)로 재추출·누적·`last_accession` 갱신(SC4 forward 누적)한다. probe/fetch 실패 시 "갱신 생략, 기존 DB 유지"(Pitfall 2)로 보수적 재추출 폭주를 차단하고, OpenDartReader 는 `dart_client._get_dart()` 싱글톤을 공유(Pitfall 1)한다. FUND-08/SC3 spy 테스트 6종 GREEN.

## What Was Built

- **`src/stocksig/io/fundamentals_delta.py`** (162 lines, TDD GREEN):
  - `probe_edgar_accession(ticker)` (`@throttled_edgar`) — `Company(ticker).latest("10-Q")` → `.accession_number`, 최신 10-Q 부재 시 None.
  - `probe_dart_rcept(ticker)` (`@throttled_dart`) — `_get_dart().list(stock_code, kind="A").iloc[0]["rcept_no"]`(rcept_dt desc), 빈 df/컬럼 부재 시 None. `dart_client._get_dart()` 싱글톤 공유 import(Pitfall 1, T-07-09).
  - `sync_ticker_history(ticker, source, years=3)` (D-02 forward 누적):
    1. `_probe` try/except — 예외/None 이면 갱신 생략·기존 DB 유지(Pitfall 2/T-07-07), `type(exc).__name__` 만 로그(T-04-03/T-07-08), return.
    2. `store.get_last_accession` 비교 — `last == latest` 이면 `mark_delta_hit()` + return(full-fetch·신규 저장 0, SC3).
    3. else(델타/state 부재) — `mark_delta_miss()` → `_full_fetch`(추출기) → fetch 실패도 안전 흡수(갱신 생략·기존 DB 유지) → `_rows_to_tuples`(dict 11-key→12-tuple, +fetched_at) → `upsert_quarters` → `mark_full_fetch()` → `set_last_accession(latest)`(forward 누적, SC4).
  - SQL 직접 작성 0(store 가 `?` 바인딩 처리). 외부 호출 함수에 throttle 데코레이터 적용.

- **`tests/test_fundamentals_delta.py`** (FUND-08/SC3 회귀 6종, 네트워크 0):
  - `test_same_accession_skips_fetch`(D-02): 동일 accession → fetch spy `.call_count == 0`·`count_rows == 0`·`delta_hit == 1`.
  - `test_changed_accession_refetches`(D-02/SC4): 다른 accession → fetch 1회·upsert·`set_last_accession` "ACC2" 갱신·`delta_miss`/`full_fetch`.
  - `test_no_state_triggers_first_fetch`: state 부재 → 첫 backfill full-fetch.
  - `test_probe_failure_keeps_db`(T-07-07): probe 예외 → fetch 0·count_rows 불변·last_accession 미갱신.
  - `test_probe_none_keeps_db`: probe None → fetch 0·기존 DB 유지.
  - `test_steady_state_zero_full_calls`(SC3): 3종목 전부 동일 accession → fetch 총 0·`full_fetch == 0`·`delta_hit == 3`.

## Verification Results

- `uv run python -m pytest tests/test_fundamentals_delta.py -x -q` → **6 passed** (0.85s).
- `uv run python -m pytest -q` 전 스위트 → **303 passed** (323.28s). 베이스라인 297 + 신규 6, 회귀 0 — delta 모듈은 additive.
- Acceptance grep: `def sync_ticker_history(`·`def probe_edgar_accession(`·`def probe_dart_rcept(` 정의 존재. `_get_dart` 는 `dart_client` 싱글톤 공유 import(본 모듈 내 OpenDartReader 신규 인스턴스 생성 0). 예외 로그는 `type(exc).__name__` 만(crtfc_key/원문 보간 0).
- ruff/`_get_dart()` 별도 인스턴스: 본 모듈은 `from stocksig.io.dart_client import _get_dart` 로 07-02 싱글톤을 직접 공유 — corp_codes 이중 다운로드 없음.

## Commits

- `1c6966d` test(07-03): RED — fundamentals_delta probe/skip/refetch/probe실패/≈0 spy 6종 (FUND-08/SC3)
- `bfc8837` feat(07-03): GREEN — fundamentals_delta probe+델타 비교+skip/refetch (D-02 forward 누적)

## TDD Gate Compliance

RED(`1c6966d`, test) → GREEN(`bfc8837`, feat) 순서 준수. RED 는 delta 모듈 부재로 import error 실패(예상대로), GREEN 에서 6종 전부 통과. REFACTOR 불필요(GREEN 코드가 cache.py/dart_client 패턴 정합, store API 만 소비).

## Deviations from Plan

### 환경 조정 (acceptance 의도 보존)

**1. [Rule 3 - Blocking] pytest 실행 = `uv run python -m pytest` (시스템 python 미설치)**
- **Found during:** Task 1 verify
- **Issue:** 시스템 `python -m pytest` 는 pytest/pytest-mock 미설치(`No module named pytest`). 프로젝트는 `.venv` + `uv` (pyproject `[dependency-groups].dev` 에 pytest>=8/pytest-mock 선언).
- **Fix:** verify 명령을 `uv run python -m pytest ...` 로 실행(플랜 `python -m pytest` 의도 = 프로젝트 테스트 러너). 패키지 신규 설치 없음(기존 dev 의존).
- **Files modified:** 없음 (실행 환경만).

**2. [Plan 조정] probe 디스패치 도우미 `_probe`/`_full_fetch`/`_rows_to_tuples` 추가**
- 플랜은 sync 본문에 source 분기를 기술 — 가독성·테스트성을 위해 source 디스패치(`_probe`/`_full_fetch`)와 dict→12-tuple 변환(`_rows_to_tuples`)을 내부 헬퍼로 분리. 동작·계약 동일(probe→비교→skip/refetch, D-02).

**3. [테스트 보강] `test_probe_none_keeps_db` 1종 추가**
- 플랜 behavior 의 "probe None" 케이스를 예외 케이스(`test_probe_failure_keeps_db`)와 분리해 명시적 단언(Pitfall 2 의 두 폴백 경로 — 예외 / 빈 메타 — 각각 입증). acceptance 의도 강화.

## Known Stubs

None — `sync_ticker_history` 는 Plan 04 가 종목 루프로 호출하는 완결된 오케스트레이터. `get_delta_stats()` run 요약 출력·`.gitignore`(data/fundamentals.db)·실 probe 네트워크 호출은 Plan 04 책임(플랜 경계상 정상, 본 plan API 호출 0).

## Threat Model Compliance

- **T-07-07 (DoS, probe 실패 보수적 재추출 폭주)** mitigate: probe 예외/None → SKIP + 기존 DB 유지(test_probe_failure_keeps_db/test_probe_none_keeps_db GREEN). fetch 실패도 동일 흡수 → DART 쿼터 연쇄 차단.
- **T-07-08 (Information Disclosure, crtfc_key URL 누설)** mitigate: probe/fetch 예외 로그 = `type(exc).__name__` 만. 예외 원문·키 보간 0건.
- **T-07-09 (DoS/비용, OpenDartReader 반복 생성)** mitigate: `dart_client._get_dart()` 싱글톤 공유 import — 본 모듈 내 신규 OpenDartReader 인스턴스 0(corp_codes 1회).
- **T-07-10 (Tampering, delta_state 동시 write)** mitigate: delta 는 store API(`set_last_accession`/`mark_*`)만 사용 — write 직렬화는 store `_store_lock`/`_stats_lock` 에 위임.
- **T-07-SC (패키지 설치)** accept: 신규 외부 패키지 0.

## Threat Flags

신규 trust boundary 표면 없음 — probe 는 기존 EDGAR `Company`/DART `list` 메타 경로 재사용(추가 네트워크 엔드포인트·auth·파일 접근 0). delta_state write 는 store API 경유.

## Notes for Downstream Plans

- **Plan 04**: 종목 루프에서 `reset_delta_stats()` → 각 종목 `sync_ticker_history(ticker, source, years)` → `get_delta_stats()` 로 run 요약(delta_hit/miss/full_fetch) 출력. source 분류(US→EDGAR / KR→DART)는 Plan 04 가 결정해 인자로 전달.
- `.gitignore` 의 `data/fundamentals.db` 추가는 Plan 04(SC5) 미완 — 운영 실행 전 추가 필요.
- probe 는 throttle 적용된 실 네트워크 호출 — 테스트는 `mocker.patch`/`mocker.spy` 로 네트워크 0 유지.

## Self-Check: PASSED

- FOUND: src/stocksig/io/fundamentals_delta.py (162 lines, def sync_ticker_history/probe_edgar_accession/probe_dart_rcept)
- FOUND: tests/test_fundamentals_delta.py (6 tests)
- FOUND commit: 1c6966d
- FOUND commit: bfc8837
