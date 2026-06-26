---
phase: 3
slug: edgar-dart-yfinance-naver
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-02
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: 03-RESEARCH.md §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (+ pytest-mock, freezegun) |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=src) |
| **Quick run command** | `uv run pytest tests/test_fundamentals.py -x` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~120-260 초 (전 스위트, Phase 2 기준 130+ tests) |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/test_<module>.py -x`
- **After every plan wave:** Run `uv run pytest`
- **Before `/gsd:verify-work`:** 전 스위트 green + 실데이터 검증 스파이크(A1~A7) 완료
- **Max feedback latency:** ~260 초 (full suite)

---

## Per-Task Verification Map

| Req ID | Behavior | Test Type | Automated Command | File Exists | Status |
|--------|----------|-----------|-------------------|-------------|--------|
| FUND-01 | EDGAR facts → PER/PEG/GPM/OPM raw 산출 | unit (mock edgar) | `uv run pytest tests/test_edgar_client.py -x` | ❌ W0 | ⬜ pending |
| FUND-02 | `set_identity` UA 형식 호출 | unit | `uv run pytest tests/test_edgar_client.py::test_set_identity -x` | ❌ W0 | ⬜ pending |
| FUND-03 | DART `finstate_all` → account_nm 매핑 (stock_code 직접) | unit (mock dart) | `uv run pytest tests/test_dart_client.py -x` | ❌ W0 | ⬜ pending |
| FUND-04 | 7d TTL 캐시 HIT/MISS, 키 `(source,ticker,quarter)` | unit | `uv run pytest tests/test_cache.py::test_fund_cache -x` | ⚠️ 확장 | ⬜ pending |
| FUND-05 | 폴백 체인 + provenance 라벨 | unit | `uv run pytest tests/test_fundamentals.py::test_fallback_chain -x` | ❌ W0 | ⬜ pending |
| FUND-06 | EDGAR 8 RPS / DART 2 RPS limiter | unit | `uv run pytest tests/test_throttle.py -x` | ⚠️ 확장 | ⬜ pending |
| PORT-05 | 시트1 col 17~20 값+주석, 빈셀+주석 | unit (openpyxl readback) | `uv run pytest tests/test_sheet_portfolio.py::test_fund_cols -x` | ⚠️ 확장 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_edgar_client.py` — FUND-01/02 (edgar mock fixture)
- [ ] `tests/test_dart_client.py` — FUND-03 (OpenDartReader mock)
- [ ] `tests/test_naver_scraper.py` — KR PER 폴백 (정적 HTML fixture, EUC-KR 인코딩 주의)
- [ ] `tests/test_yf_fundamentals.py` — yfinance `.info` 키 mock
- [ ] `tests/test_fundamentals.py` — 폴백 체인·provenance·PEG 엣지케이스(성장률≤0 / 0분모)
- [ ] `tests/test_cache.py` 확장 — `_FUND_CACHE` 7d TTL
- [ ] `tests/test_throttle.py` 확장 — `@throttled_edgar` / `@throttled_dart` limiter
- [ ] `tests/test_sheet_portfolio.py` 확장 — 21열 + `write_comment` readback (openpyxl `ws.cell().comment`)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 실데이터 상수 확정 스파이크 (A1~A7) | FUND-01/03 | 외부 API 라이브 응답은 mock으로 대체 불가, concept tag/account_nm/Naver 셀렉터를 1회 실호출로 확정해야 함 | AAPL/MSFT/GOOGL EDGAR + 005930 DART + 005930 Naver 각 1회 실호출 → concept tag·account_nm·셀렉터 상수 확정 → mock fixture 작성 |
| `.env` 인증 로드 | FUND-02 | 실제 키 주입 후 EDGAR 403 회피·DART 응답 확인은 사용자 환경 필요 | `python main.py` 1회 실행 후 시트1 R/S/T/U 4값 + 출처 주석 육안 확인 |
| 같은 주 2회 실행 캐시 HIT | FUND-04 | 디스크 캐시 7d TTL 실동작은 실행 환경 콘솔 로그 확인 | 같은 주 내 재실행 시 EDGAR/DART 호출 0건 콘솔 로그 확인 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 260s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
