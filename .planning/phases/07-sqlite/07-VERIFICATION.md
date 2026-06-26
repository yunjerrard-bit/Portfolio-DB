---
phase: 07-sqlite
verified: 2026-06-19T00:00:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
---

# Phase 7: SQLite 펀더멘털 히스토리 & 델타 Verification Report

**Phase Goal:** 사용자가 도구를 실행할 때마다 각 종목의 분기별 펀더멘털 원천이 영구 히스토리로 누적되고, 새 분기·정정공시가 없으면 외부 펀더멘털 호출이 사실상 발생하지 않는다. 과거 분기 데이터가 사라지지 않고 보존되어 추후 신규 지표 계산의 원천이 된다.
**Verified:** 2026-06-19T00:00:00Z
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| #   | Truth | Status | Evidence |
| --- | ----- | ------ | -------- |
| 1 | 실행 후 data/fundamentals.db 생성/갱신, 분기별 원천 항목이 raw long 테이블에 누적, 과거 분기 행이 재실행으로 사라지지 않음 (TTL 없음) | ✓ VERIFIED | `fundamentals_store.py`: `raw_facts` 테이블 PK `(ticker, source, quarter, field)` + `ON CONFLICT DO UPDATE`. `test_rerun_preserves_past_quarters` + `test_run_creates_history_db` PASSED. TTL/expire 컬럼 없음(grep 0건). D-H3 설계 불변 명시. |
| 2 | state 테이블에 종목·소스별 last_accession(EDGAR accession / DART rcept_no) 기록·비교 | ✓ VERIFIED | `delta_state` 테이블 PK `(ticker, source)` DDL 존재. `get_last_accession` / `set_last_accession` 구현 및 ON CONFLICT DO UPDATE 갱신. `test_last_accession_roundtrip` PASSED. `sync_ticker_history`가 `store.get_last_accession` 비교 후 조건 분기(L138-139). |
| 3 | 저장 접수번호 == 최신 접수번호인 종목은 외부 펀더멘털 전체 호출 생략 → 평소 실행 외부 호출 0 수렴 (가벼운 list/메타 조회만) | ✓ VERIFIED | `sync_ticker_history` L139: `if last is not None and last == latest: mark_delta_hit(); return`. `test_same_accession_skips_fetch`: `spy.call_count == 0`. `test_steady_state_zero_full_calls`: 3종목 전부 SKIP, `full_fetch == 0`. `test_steady_state_history_zero_full_fetch`(통합): `full_fetch == 0`, `delta_hit == 2`. |
| 4 | 접수번호가 달라진 종목만 전체 facts 재추출·누적·last_accession 갱신 | ✓ VERIFIED | `sync_ticker_history` L145-158: `mark_delta_miss` → `_full_fetch` → `upsert_quarters` → `mark_full_fetch` → `set_last_accession`. `test_changed_accession_refetches`: fetch 1회·`last_accession=="ACC2"`. `test_no_state_triggers_first_fetch`: 최초 state 부재 시 full-fetch. |
| 5 | data/fundamentals.db는 .gitignore 처리(미커밋), 기존 .cache/(OHLCV 7일 TTL)와 별개 동작 (회귀 무손상) | ✓ VERIFIED | `.gitignore`: `data/` 라인 존재(L11). `git check-ignore data/fundamentals.db` → IGNORED 확인. `test_cache_dir_unchanged_by_history`: 히스토리 실행 전후 `.cache/` 파일 목록 불변 assert PASSED. 전 스위트 308 passed(회귀 0). |

**Score:** 5/5 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
| -------- | --------- | ------ | ------- |
| `src/stocksig/io/fundamentals_store.py` | sqlite3 WAL 싱글톤 + raw_facts/delta_state DDL + upsert + state CRUD + 델타 카운터 | ✓ VERIFIED | 198줄. `get_store`/`upsert_quarters`/`get_last_accession`/`set_last_accession`/`count_rows`/`reset_delta_stats`/`get_delta_stats`/`mark_delta_hit`/`mark_delta_miss`/`mark_full_fetch` 전부 존재. WAL + busy_timeout. |
| `src/stocksig/io/fundamentals_delta.py` | probe + delta_state 비교 + skip/refetch 오케스트레이션 + DART 싱글톤 | ✓ VERIFIED | 163줄. `probe_edgar_accession`/`probe_dart_rcept`/`sync_ticker_history`/`_get_dart`(dart_client 싱글톤 공유 import) 모두 존재. |
| `src/stocksig/main_run.py` | run() 히스토리 경로 배선 + 델타 카운터 reset/요약 | ✓ VERIFIED | `fund_store.reset_delta_stats()`(L256), `fundamentals_delta.sync_ticker_history`(L347), `fund_store.get_delta_stats()`(L379) + 요약 로그 존재. PASS2 `wb.close()` 이후 순차 루프 배치(D-07). |
| `.gitignore` | `data/` 라인 존재 | ✓ VERIFIED | L11에 `data/` 존재. `git check-ignore` IGNORED 확인. |
| `tests/test_fundamentals_store.py` | FUND-07 upsert/보존/NULL/정정 회귀 테스트 | ✓ VERIFIED | 6종 테스트 전부 PASSED. `test_rerun_preserves_past_quarters`/`test_amendment_upsert_overwrites`/`test_none_stored_as_null` 존재. |
| `tests/test_fundamentals_delta.py` | FUND-08/SC3 probe/skip/refetch/probe실패/≈0 spy 테스트 | ✓ VERIFIED | 6종 테스트 전부 PASSED. `test_steady_state_zero_full_calls`/`test_same_accession_skips_fetch`/`test_changed_accession_refetches`/`test_probe_failure_keeps_db` 존재. |
| `tests/test_history_integration.py` | 히스토리 경로 통합 테스트 5종 | ✓ VERIFIED | 5종 전부 PASSED. `test_steady_state_history_zero_full_fetch`/`test_sheet1_unchanged_by_history`/`test_cache_dir_unchanged_by_history`/`test_history_failure_does_not_break_sheet1` 존재. |
| `tests/conftest.py` | `_isolated_fundamentals_db` autouse fixture | ✓ VERIFIED | `monkeypatch.setattr(_store_mod, "_DB_PATH", ...)` + `_conn=None` 격리 확인. |

### Key Link Verification

| From | To | Via | Status | Details |
| ---- | -- | --- | ------ | ------- |
| `main_run.run` | `fundamentals_delta.sync_ticker_history` | D-07 별도 순차 루프 (PASS2 wb.close 이후) | ✓ WIRED | L334-354, `for s in specs: ... fundamentals_delta.sync_ticker_history(s.symbol, source)` |
| `main_run.run` | `fundamentals_store.reset_delta_stats / get_delta_stats` | run 시작 reset + 요약 블록 출력 | ✓ WIRED | L256 `fund_store.reset_delta_stats()`, L379 `fund_store.get_delta_stats()` |
| `fundamentals_delta.sync_ticker_history` | `fundamentals_store.get_last_accession / set_last_accession` | D-02: 비교 → 같으면 SKIP, 다르면 forward 누적 | ✓ WIRED | L138 `store.get_last_accession(ticker, source)`, L158 `store.set_last_accession(ticker, source, latest)` |
| `fundamentals_delta` | `edgar_client.fetch_edgar_quarterly_raw / dart_client.fetch_dart_quarterly_raw` | D-02: 델타(변경) 있을 때만 full-fetch | ✓ WIRED | `_full_fetch()` L76-81 source 분기, `test_same_accession_skips_fetch` spy.call_count==0 검증 |
| `conftest._isolated_fundamentals_db` | `fundamentals_store._DB_PATH` | monkeypatch tmp_path + `_conn=None` | ✓ WIRED | conftest.py L32-33 `monkeypatch.setattr(_store_mod, "_DB_PATH", ...)` + `_conn=None` |
| `fundamentals_store.upsert_quarters` | `raw_facts (ON CONFLICT DO UPDATE)` | D-09: executemany UPSERT under _store_lock | ✓ WIRED | L82-91 `_UPSERT` SQL + L131-134 `with _store_lock: conn.executemany(_UPSERT, rows)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
| -------- | ------------- | ------ | ------------------ | ------ |
| `fundamentals_store.py` raw_facts | `rows: list[tuple]` | `upsert_quarters(rows)` ← `_rows_to_tuples(rows)` ← `_full_fetch` ← `fetch_edgar_quarterly_raw` / `fetch_dart_quarterly_raw` | YES — 외부 API 응답에서 실 데이터, 결손은 None(NULL), 정정 시 덮어쓰기. | ✓ FLOWING |
| `fundamentals_store.py` delta_state | `accession: str` | `set_last_accession` ← `sync_ticker_history` ← probe 결과(EDGAR accession / DART rcept_no) | YES — probe가 실 접수번호 반환(혹은 None으로 skip). delta 없으면 쓰기 0. | ✓ FLOWING |
| `main_run.py` 히스토리 루프 | `delta = fund_store.get_delta_stats()` | `fund_store.reset_delta_stats()` → 종목 루프 `sync_ticker_history` → 카운터 누적 → `get_delta_stats()` | YES — 정수 카운터가 실 실행 흐름에서 증가. | ✓ FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
| -------- | ------- | ------ | ------ |
| fundamentals_store 6종 단위 테스트 | `uv run python -m pytest tests/test_fundamentals_store.py -v` | 6 passed | ✓ PASS |
| fundamentals_delta 6종 단위 테스트 | `uv run python -m pytest tests/test_fundamentals_delta.py -v` | 6 passed | ✓ PASS |
| 히스토리 통합 테스트 5종 | `uv run python -m pytest tests/test_history_integration.py -v` | 5 passed | ✓ PASS |
| 전 스위트 회귀 | `uv run python -m pytest -q` | 308 passed, 4 warnings | ✓ PASS |
| .gitignore DB 제외 | `git check-ignore data/fundamentals.db` | `data/fundamentals.db` (IGNORED) | ✓ PASS |
| SQL f-string/% 보간 없음 | `grep "f\".*SELECT\|%.*SELECT" src/stocksig/io/fundamentals_store.py` | (empty) | ✓ PASS |
| ON CONFLICT upsert 존재 | `grep "ON CONFLICT" src/stocksig/io/fundamentals_store.py` | 2 hits (raw_facts, delta_state) | ✓ PASS |

### Probe Execution

Step 7c: SKIPPED — 이 phase는 probe 스크립트(`scripts/*/tests/probe-*.sh`)를 사용하지 않으며, 검증은 pytest 기반 테스트로 수행됨.

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
| ----------- | ----------- | ----------- | ------ | -------- |
| FUND-07 | 07-01, 07-02, 07-04 | 분기별 펀더멘털 원천 SQLite 영구 누적, 과거 분기 보존, TTL 없음 | ✓ SATISFIED | `fundamentals_store.py` raw_facts DDL + upsert 구현. `test_rerun_preserves_past_quarters` PASSED. `test_run_creates_history_db` PASSED. REQUIREMENTS.md `[x] FUND-07` |
| FUND-08 | 07-03, 07-04 | last_accession 비교로 변경 없으면 외부 전체 호출 생략 → 평소 ≈0 | ✓ SATISFIED | `sync_ticker_history` D-02 skip/refetch 구현. `test_steady_state_zero_full_calls`/`test_steady_state_history_zero_full_fetch` PASSED. REQUIREMENTS.md `[x] FUND-08` |

요구사항 추적 테이블(`REQUIREMENTS.md` Traceability 섹션)에서 FUND-07/FUND-08 모두 `Phase 7 / Complete` 로 기록됨. 고아(orphaned) 요구사항 없음.

### Anti-Patterns Found

| File | Pattern | Severity | Impact |
| ---- | ------- | -------- | ------ |
| `dart_account_map.py` | `# [Open Q2 — 005930 BS/CF 실응답 1회 확정 후 VERIFIED]` 주석(미검증 account_id) | ℹ️ Info | 005930 BS/CF 실 응답에서 account_id 미스 시 한글 nm 2차 폴백으로 보강됨. Phase 8 첫 실호출 시 VERIFIED 승격 예정. 행동 미영향(결손=None). 의도된 Known Stub(SUMMARY에 명시). |

TBD/FIXME/XXX 미검증 채무 마커: 대상 3개 파일(`fundamentals_store.py`, `fundamentals_delta.py`, `main_run.py`)에 해당 마커 0건. 채무 게이트 CLEAR.

### Human Verification Required

이 phase는 완전히 자동화된 pytest 기반 테스트로 검증 가능하며, 네트워크 0 mock 환경에서 17종 테스트가 전부 통과함. 시각적 UI, 실시간 동작, 외부 서비스 통합이 이 phase의 목표 범위 밖이므로 인간 검증 항목 없음.

### Gaps Summary

없음. 5개 성공 기준 모두 코드베이스에서 직접 확인되었으며, 17종 테스트가 PASSED, 전 스위트 308 tests 회귀 0.

---

_Verified: 2026-06-19T00:00:00Z_
_Verifier: Claude (gsd-verifier)_
