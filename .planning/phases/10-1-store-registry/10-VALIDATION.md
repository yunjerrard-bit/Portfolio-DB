---
phase: 10
slug: 1-store-registry
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-23
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> 출처: `10-RESEARCH.md` §Validation Architecture (HIGH confidence).

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (+ pytest-mock) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| **Quick run command** | `uv run pytest tests/test_metrics_engine.py tests/test_history_render.py tests/test_fundamentals_view.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~5초 (quick) / 전체 ≥375 passed (Phase 9 baseline) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_metrics_engine.py tests/test_history_render.py tests/test_fundamentals_view.py -x -q` (어댑터·헬퍼·엔진 < 5초)
- **After every plan wave:** `uv run pytest tests/test_sheet_portfolio.py tests/test_history_integration.py tests/test_cache.py tests/test_cache_isolation.py -q` (색 회귀·이관·캐시 분리)
- **Before `/gsd:verify-work`:** `uv run pytest -q` 전체 녹색 (≥375, 회귀 0) + `git diff src/stocksig/output/sheet_portfolio.py` 빈 출력 확인
- **Max feedback latency:** ~5초 (quick), 전체 스위트 ~수십초

---

## Per-Task Verification Map

| Item | Requirement | Behavior | Test Type | Automated Command | File Exists |
|------|-------------|----------|-----------|-------------------|-------------|
| 어댑터 매핑 | FUND-11 | matrix 최신열 → `FundamentalsResult{per,peg,gpm,opm}` | unit | `pytest tests/test_fundamentals_view.py::test_adapter_maps_latest_column -x` | ❌ W0 |
| 공유 헬퍼 | FUND-11 | `inject_prices_for_quarter` 단일분기 동작 | unit | `pytest tests/test_metrics_engine.py::test_inject_prices_for_quarter -x` | ❌ W0 |
| 드리프트 0 (SC1) | FUND-11 | 어댑터 4셀 == 스냅샷 최신열 (동일 fixture·가격) | unit | `pytest tests/test_fundamentals_view.py::test_sheet1_matches_snapshot -x` | ❌ W0 |
| 가격 parity (L4) | FUND-11 | `last_close` == `quarter_price.current` 동일성 가드 | unit | `pytest tests/test_fundamentals_view.py::test_price_source_parity -x` | ❌ W0 |
| PEG provenance (L5) | FUND-11 | PEG `source = PER.source` 승계 | unit | `pytest tests/test_fundamentals_view.py::test_peg_provenance_inherited -x` | ❌ W0 |
| 색 신호 회귀 0 | FUND-11 | σ-bucket 셀 서식 불변 (Core Value 보호) | integration | `pytest tests/test_sheet_portfolio.py -k color -x` | ✅ 확장 |
| run 순서·호출 0 | FUND-11 | sync→read→write, 외부 펀더멘털 호출 0 | integration | `pytest tests/test_history_integration.py -k single_source -x` | ✅ 확장 |
| D-02 빈 DB | FUND-11 | DB 분기 결손 종목 → 4셀 빈칸+한국어 사유 | unit | `pytest tests/test_fundamentals_view.py::test_missing_db_blank -x` | ❌ W0 |
| 구 경로 미호출 | FUND-11 | `fetch_fundamentals`/`fetch_*_cached` 시트1 경로 호출 0 | integration | `pytest tests/test_history_integration.py -k no_legacy_fetch -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_fundamentals_view.py` — 신규 어댑터/공유헬퍼 모듈 테스트 (어댑터 매핑·드리프트 동치·가격 parity·PEG provenance·빈 DB). 모듈/파일명은 어댑터 위치에 맞춰 Claude 재량.
- [ ] `tests/test_history_integration.py` 확장 — 시트1 단일원천 단언(`no_legacy_fetch`/`single_source`): `fetch_fundamentals`·`fetch_edgar_cached`·`fetch_dart_cached` mock 호출 카운트 0.
- [ ] `tests/test_sheet_portfolio.py` 확장 — 색 신호(σ-bucket) 셀 서식 불변 단언(이관 전후 비교 또는 고정 기대값).
- [ ] fixture 재사용: `tests/fixtures/history_fixtures.py`의 `fetch_fn_stub`/`build_ohlcv`/`TICKER_INDUSTRY` (네트워크 0); conftest `_isolated_fundamentals_db`/`_isolated_disk_cache` 유지.
- [ ] 프레임워크 설치: 불필요 (pytest 기존 설치).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 실제 `portfolio_YYYYMMDD.xlsx` 시각 확인 (색 신호·하이퍼링크·기업명 열·freeze) | FUND-11 / Core Value | 엑셀 렌더 결과의 시각적 회귀는 자동화 곤란 | 실 데이터 1회 `uv run python main.py` 후 시트1 PER/PEG/GPM/OPM 값·셀 색·호버 주석을 `fundamentals_history.xlsx` 최신 스냅샷과 대조 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s (quick)
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
