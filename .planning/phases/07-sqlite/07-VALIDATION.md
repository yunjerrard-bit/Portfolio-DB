---
phase: 7
slug: sqlite
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-18
---

# Phase 7 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (+ pytest-mock, freezegun) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| **Quick run command** | `python -m pytest tests/test_fundamentals_store.py tests/test_fundamentals_delta.py -x -q` |
| **Full suite command** | `python -m pytest -q` |
| **Estimated runtime** | quick ~5s · full ~40s |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_fundamentals_store.py tests/test_fundamentals_delta.py -x -q`
- **After every plan wave:** Run `python -m pytest -q`
- **Before `/gsd:verify-work`:** Full suite must be green + `data/fundamentals.db` 미커밋(`git check-ignore`) 확인
- **Max feedback latency:** ~5 seconds (quick) / ~40 seconds (full)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 07-01-01 | 01 | 1 | FUND-07 | — | conftest 격리 fixture로 운영 DB 오염 차단 (Wave 0 스캐폴드) | unit (scaffold) | `python -m pytest tests/test_fundamentals_store.py -q 2>&1 \| grep -E "error\|failed\|collected"` | ❌ W0 | ⬜ pending |
| 07-01-02 | 01 | 1 | FUND-07 | T-07-01 / T-07-02 / T-07-03 | 전 SQL `?` 바인딩(f-string/`%` 금지); 결손=NULL; WAL+busy_timeout+_store_lock write 직렬화 | unit | `python -m pytest tests/test_fundamentals_store.py -x -q` | ❌ W0 | ⬜ pending |
| 07-02-01 | 02 | 2 | FUND-07 | T-07-06 | 신규 BS/CF/shares 매핑 추가, 기존 5종 매핑 불변 | unit | `python -c "from stocksig.io.dart_account_map import DART_ACCOUNT_ID_MAP, SJ_DIV_BALANCE_SHEET, SJ_DIV_CASHFLOW; print('total_assets' in DART_ACCOUNT_ID_MAP, 'operating_cash_flow' in DART_ACCOUNT_ID_MAP, SJ_DIV_BALANCE_SHEET, SJ_DIV_CASHFLOW)"` | ❌ W0 | ⬜ pending |
| 07-02-02 | 02 | 2 | FUND-07 | T-07-06 | 결손 value=None(0/-999999 아님), 기존 fetch_edgar_raw 불변, 네트워크 0(mock) | unit | `python -m pytest tests/test_edgar_quarterly.py -x -q` | ❌ W0 | ⬜ pending |
| 07-02-03 | 02 | 2 | FUND-07 | T-07-04 / T-07-05 / T-07-06 | `_parse_amount` 재사용(파싱 실패=None); 예외 타입명만 로그(crtfc_key 미보간); 결손=None | unit | `python -m pytest tests/test_dart_quarterly.py -x -q` | ❌ W0 | ⬜ pending |
| 07-03-01 | 03 | 3 | FUND-08 | T-07-07 | full-fetch 호출 카운트 spy/counter 단언(≈0 검증 스캐폴드) | unit (spy scaffold) | `python -m pytest tests/test_fundamentals_delta.py -q 2>&1 \| grep -E "error\|failed\|collected"` | ❌ W0 | ⬜ pending |
| 07-03-02 | 03 | 3 | FUND-08 | T-07-07 / T-07-08 / T-07-09 / T-07-10 | probe 실패→SKIP(기존 DB 유지); 예외 타입명만; DART `_get_dart()` 싱글톤; delta_state write는 store _store_lock | unit (spy) | `python -m pytest tests/test_fundamentals_delta.py -x -q` | ❌ W0 | ⬜ pending |
| 07-04-01 | 04 | 4 | FUND-07, FUND-08 | T-07-13 | `data/fundamentals.db` `.gitignore` (미커밋) | integration (config) | `git check-ignore data/fundamentals.db && echo IGNORED` | ✅ | ⬜ pending |
| 07-04-02 | 04 | 4 | FUND-07, FUND-08 | T-07-11 / T-07-12 | 종목별 try/except로 시트1 산출물 보호; 요약 로그 카운트·심볼만(API 키·원문 미포함) | integration | `python -m pytest tests/test_history_integration.py -x -q` | ❌ W0 | ⬜ pending |
| 07-04-03 | 04 | 4 | FUND-07, FUND-08 | T-07-11 | 평소 실행 full-fetch 호출==0(SC3); 시트1 불변 스냅샷; `.cache/` 파일 목록 불변(SC5) | integration (spy) | `python -m pytest tests/test_history_integration.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_fundamentals_store.py` — FUND-07 (upsert/보존/NULL/정정 덮어쓰기 6종) — 07-01 Task 1
- [ ] `tests/conftest.py` — 신규 autouse fixture `_isolated_fundamentals_db` (tmp_path로 `_DB_PATH`·`_conn` 격리 + teardown `conn.close()`, 기존 `_isolated_disk_cache` 패턴 복제). 운영 `data/fundamentals.db` 오염 방지 — 필수 — 07-01 Task 1
- [ ] `tests/test_edgar_quarterly.py` + `tests/fixtures/edgar_aapl_facts.py` 분기 BS/CF/shares 행 확장 — EDGAR per-quarter 추출(네트워크 0) — 07-02 Task 2
- [ ] `tests/test_dart_quarterly.py` + `tests/fixtures/dart_005930_finstate.py` sj_div='BS'/'CF' 행 확장 — DART 분기 백필(네트워크 0) — 07-02 Task 3
- [ ] `tests/test_fundamentals_delta.py` — FUND-08 + SC3 (probe/skip/refetch/probe실패/≈0 spy 5종) — 07-03 Task 1
- [ ] `tests/test_history_integration.py` — 히스토리 경로 통합(≈0 호출·시트1 불변·DB 생성·실패 격리 4종) — 07-04 Task 3
- [ ] Framework install: 불필요 (pytest 8.x 기존 dev 의존).

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 40s (full suite)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
