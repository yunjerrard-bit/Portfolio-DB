---
phase: 8
slug: registry
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-19
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (+ pytest-mock, freezegun) |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`, testpaths=["tests"], pythonpath=["src"]) |
| **Quick run command** | `uv run pytest tests/test_metrics_engine.py tests/test_metrics_registry.py -x -q` |
| **Full suite command** | `uv run pytest -q` |
| **Estimated runtime** | ~quick <10s / full ~30-40s (308+ 테스트) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest tests/test_metrics_engine.py tests/test_metrics_registry.py tests/test_raw_semantics_spike.py -x -q`
- **After every plan wave:** `uv run pytest -q` (전 스위트 — 기존 fundamentals/store/delta 회귀 포함)
- **Before `/gsd:verify-work`:** Full suite green. 시트1 회귀(test_sheet_portfolio·test_history_integration·test_fundamentals) 반드시 그린 (Core Value 불변)
- **Max feedback latency:** <40s

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 1 | FUND-09 | T-08-02 | raw 분기값 진실 확정 | unit(spike) | `uv run pytest tests/test_raw_semantics_spike.py -x -q` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 1 | FUND-09 | T-08-01 | fetch_raw_quarters ?-바인딩 | unit | `uv run pytest tests/test_metrics_engine.py -k fetch_raw_quarters -x -q` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 1 | FUND-09 (SC1/SC3) | T-08-03 | field 어휘·소스매핑 정합 | unit | `uv run pytest tests/test_metrics_registry.py -x -q` | ❌ W0 | ⬜ pending |
| 08-03-01 | 03 | 2 | FUND-09 (SC2/SC4) | T-08-04/05 | TTM 결손 게이트·분기산술 | unit | `uv run pytest tests/test_metrics_engine.py -k "prior_4_quarters or type_rules or ttm_missing or dart_quarter or edgar_q4" -x -q` | ❌ W0 | ⬜ pending |
| 08-03-02 | 03 | 2 | FUND-09 (SC3/SC5) | T-08-05/06 | 재현·per-share·sanity·provenance | unit | `uv run pytest tests/test_metrics_engine.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_raw_semantics_spike.py` — DART thstrm_amount 분기/누적 + EDGAR Q4 갭 진실 단언 (08-01 Task 1)
- [ ] `tests/fixtures/raw_quarters.py` — 분기 raw 행 builder (EDGAR 3개월·DART 분기·BS instant·결손) (08-01 Task 2)
- [ ] `tests/test_metrics_engine.py` — 엔진 테스트 RED 스캐폴드 (-k 마커별), fetch_raw_quarters GREEN (08-01 Task 2)
- [ ] `tests/test_metrics_registry.py` — registry 정의 무결성 (08-02 Task 1)
- 프레임워크: 기존 pytest 인프라가 전 phase 요구를 커버 (신규 설치 없음)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| (없음) | FUND-09 | — | All phase behaviors have automated verification (순수 계산 층, 시각 검증 불필요 — Phase 9 렌더에서 발생) |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (test_raw_semantics_spike / raw_quarters fixture / test_metrics_engine / test_metrics_registry)
- [x] No watch-mode flags
- [x] Feedback latency < 40s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-19
