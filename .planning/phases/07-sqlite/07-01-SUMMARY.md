---
phase: 07-sqlite
plan: 01
subsystem: io/fundamentals-store
tags: [sqlite, wal, fundamentals, delta, persistence, FUND-07]
requires: []
provides:
  - "fundamentals_store 공개 API (get_store/upsert_quarters/get·set_last_accession/count_rows/델타 카운터)"
  - "raw_facts (분기 원천 long) + delta_state (last_accession) 스키마"
  - "tests/conftest.py _isolated_fundamentals_db autouse 격리 fixture"
affects:
  - "Plan 02 (추출): upsert_quarters로 facts 누적"
  - "Plan 03 (델타): get/set_last_accession + mark_delta_* 카운터"
  - "Plan 04 (오케스트레이션): get_store + count_rows + .gitignore"
  - "Phase 8 (지표 계산) / Phase 9 (트렌드 엑셀): 단일 원천 백엔드"
tech-stack:
  added: []  # 신규 외부 패키지 0 — sqlite3/threading/datetime/pathlib stdlib
  patterns:
    - "cache.py double-checked 락 싱글톤 복제 (sqlite 연결 대상)"
    - "cache.py _stats/_stats_lock 카운터 복제 (델타 hit/miss/full)"
    - "ON CONFLICT DO UPDATE upsert (D-09 정정공시 최신값 덮어쓰기)"
key-files:
  created:
    - src/stocksig/io/fundamentals_store.py
    - tests/test_fundamentals_store.py
  modified:
    - tests/conftest.py
decisions:
  - "D-09 적용: raw_facts PK (ticker,source,quarter,field), 정정공시 ON CONFLICT DO UPDATE 최신값 덮어쓰기 (이력 미보존)"
  - "D-H3 적용: TTL/expire 컬럼 없음 — 영구 누적 (.cache/ 7일 TTL과 별개)"
  - "D-05 적용: 결손값 = NULL (value REAL NULL), 0/-999999 sentinel 금지"
  - "전 SQL ? 파라미터 바인딩 (ASVS V5, T-07-01 mitigate)"
  - "write _store_lock 직렬화 + WAL + busy_timeout=5000 + check_same_thread=False (T-07-03 mitigate)"
metrics:
  duration: "~12 min"
  completed: "2026-06-18"
  tasks: 2
  files_changed: 3
---

# Phase 7 Plan 01: 펀더멘털 SQLite 영구 store Summary

FUND-07 펀더멘털 영구 store(`data/fundamentals.db`, WAL)를 신규 구축 — 분기별 원천 long 테이블 `raw_facts`와 델타 state 테이블 `delta_state`에 정정공시 upsert(D-09)·과거 분기 보존·결손 NULL(D-05)·last_accession CRUD·델타 hit/miss 카운터를 제공하고, 운영 DB 오염을 막는 conftest autouse 격리 fixture로 FUND-07 회귀 6종을 GREEN으로 검증.

## What Was Built

- **`src/stocksig/io/fundamentals_store.py`** (197 lines, TDD GREEN):
  - `get_store()` — double-checked 락 싱글톤(cache.py `_get_cache` 패턴 복제), `PRAGMA journal_mode=WAL` + `busy_timeout=5000` + `check_same_thread=False`, 스키마 멱등 적용(`CREATE TABLE IF NOT EXISTS`).
  - `raw_facts` 스키마: 12컬럼(ticker/source/quarter/field/value REAL NULL/unit/accession/period_start/period_end/period_type/reprt_code/fetched_at), **PK (ticker, source, quarter, field)** (D-09), `idx_raw_ticker_q` 인덱스.
  - `delta_state` 스키마: (ticker, source, last_accession, last_checked_at), PK (ticker, source).
  - `upsert_quarters(rows)` — `ON CONFLICT(ticker,source,quarter,field) DO UPDATE`로 정정공시 최신값 덮어쓰기(행 수 불변), `_store_lock` 하 `executemany` + `commit` (fan-out write 직렬화).
  - `get_last_accession` / `set_last_accession`(delta_state ON CONFLICT upsert + `_now_iso()`), `count_rows(ticker=None)`.
  - 델타 카운터: `reset_delta_stats` / `get_delta_stats`(dict 복사본) / `mark_delta_hit` / `mark_delta_miss` / `mark_full_fetch` — `+=`는 `_stats_lock` 하 (cache.py 복제).
  - 전 SQL `?` 파라미터 바인딩만 (f-string/`%` 없음).

- **`tests/test_fundamentals_store.py`** (FUND-07 회귀 6종): upsert 생성 / 재실행 보존 / **정정공시 덮어쓰기(D-09)** / 새 분기 증가만 / 결손 NULL(D-05) / last_accession 라운드트립.

- **`tests/conftest.py`** (+`_isolated_fundamentals_db` autouse fixture): `_DB_PATH`→tmp_path + `_conn=None` 격리, teardown `conn.close()` try/except(Windows tmp 정리 PermissionError 방지).

## Verification Results

- `python -m pytest tests/test_fundamentals_store.py -x -q` → **6 passed** (0.08s).
- `python -m pytest -q` 전 스위트 → **277 passed** (314.78s). 베이스라인 271 + 신규 6, 회귀 0 — store는 additive.
- ruff check (store + 신규/수정 테스트) → All checks passed.
- 어셉턴스 grep: `def get_store(`/`upsert_quarters(`/`get_last_accession(`/`set_last_accession(`/`count_rows(`/`reset_delta_stats(`/`get_delta_stats(` 모두 존재. SCHEMA에 `PRIMARY KEY (ticker, source, quarter, field)` + `PRAGMA journal_mode=WAL` 포함. 스키마에 expire/ttl **컬럼** 없음(grep 매치 3건은 모두 D-H3 "TTL 없음" 설명 docstring/주석 — 컬럼 아님). `ON CONFLICT(ticker, source, quarter, field) DO UPDATE` 존재.

## Commits

- `5e27d47` test(07-01): RED — 회귀 6종 + conftest 격리 fixture (store 부재로 import 실패)
- `898bf3f` feat(07-01): GREEN — fundamentals_store WAL 싱글톤 + DDL + upsert + state CRUD + 델타 카운터

## TDD Gate Compliance

RED(`5e27d47`, test) → GREEN(`898bf3f`, feat) 순서 준수. RED는 store 모듈 부재로 import error 실패(예상대로), GREEN에서 6종 전부 통과. REFACTOR 불필요(GREEN 코드가 이미 cache.py 패턴 정합).

## Threat Model Compliance

- **T-07-01 (Tampering, SQL 보간)** mitigate: 전 쿼리 `?` 바인딩, f-string/`%` SQL 0건.
- **T-07-02 (Tampering, value 컬럼)** mitigate: value REAL NULL, 결손=NULL(test_none_stored_as_null GREEN).
- **T-07-03 (DoS, WAL 동시 write)** mitigate: `_store_lock` 직렬화 + `busy_timeout=5000` + `check_same_thread=False` + teardown `conn.close()`.
- **T-07-SC (패키지 설치)** accept: 신규 외부 패키지 0 (stdlib만).

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — store API는 Plan 02/03/04 소비를 위한 완결된 계약. `mark_delta_*` 카운터는 의도적으로 Plan 03이 호출할 hook(현재 데이터 소스 미연결이나 이는 plan 경계상 정상, 본 plan의 책임 아님).

## Notes for Downstream Plans

- `upsert_quarters` rows는 **12-tuple**, 컬럼 순서 = (ticker, source, quarter, field, value, unit, accession, period_start, period_end, period_type, reprt_code, fetched_at). Plan 02 추출기가 이 순서로 구성.
- `data/fundamentals.db`는 아직 `.gitignore`에 없음 — **Plan 04(SC5)**에서 추가 예정(플랜 명시). 운영 실행 전까지 DB 파일 미생성, 테스트는 tmp_path 격리로 운영 경로 미접근.
- 델타 카운터(`mark_delta_hit/miss/full`)는 Plan 03이 호출. run 요약 출력은 Plan 04.

## Self-Check: PASSED

- FOUND: src/stocksig/io/fundamentals_store.py (197 lines)
- FOUND: tests/test_fundamentals_store.py
- FOUND: tests/conftest.py (fixture 추가)
- FOUND commit: 5e27d47
- FOUND commit: 898bf3f
