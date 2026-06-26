---
phase: 1
slug: foundation-single-ticker
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-20
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution. Derived from `01-RESEARCH.md` §Validation Architecture.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x + pytest-mock |
| **Config file** | `pyproject.toml` `[tool.pytest.ini_options]` (Wave 0에서 생성) |
| **Quick run command** | `uv run pytest -x -q` |
| **Full suite command** | `uv run pytest` |
| **Estimated runtime** | ~30 seconds (full suite) / <5s (per-module) |

---

## Sampling Rate

- **After every task commit:** `uv run pytest -x -q tests/test_<changed_module>.py` (< 5초)
- **After every plan wave:** `uv run pytest -x -q` 전체 (< 30초)
- **Before `/gsd:verify-work`:** Full suite must be green + Walking Skeleton 수기 검증 6포인트 통과
- **Max feedback latency:** 30 seconds

---

## Per-Task Verification Map

> Task IDs는 planner가 PLAN.md 작성 시 최종 확정. 본 표는 Req → Test 매핑의 single source of truth.

| Req ID | Wave | Behavior | Test Type | Automated Command | File Exists |
|--------|------|----------|-----------|-------------------|-------------|
| INPUT-01 | 1 | `tickers.txt` 한 줄당 파싱 | unit | `pytest tests/test_input.py::test_read_single_ticker -x` | ❌ W0 |
| INPUT-02 | 1 | `.KS`/`.KQ` suffix-agnostic 통과 | unit | `pytest tests/test_input.py::test_read_kr_suffix -x` | ❌ W0 |
| INPUT-03 | 1 | 빈/없는 파일 → 한국어 에러 + exit≠0 | unit | `pytest tests/test_input.py::test_empty_file_exits_nonzero -x` | ❌ W0 |
| INPUT-05 | 1 | `.env` 비어있으면 fail-fast (EDGAR/DART 키) | unit | `pytest tests/test_config.py::test_missing_env_fails -x` | ❌ W0 |
| MKTD-01 | 1 | yfinance start/end = today±4000d | unit (mock) | `pytest tests/test_market.py::test_fetch_ohlcv_date_window -x` | ❌ W0 |
| MKTD-02 | 1 | session=curl_cffi.Session(impersonate="chrome") | unit (mock) | `pytest tests/test_market.py::test_uses_curl_cffi_session -x` | ❌ W0 |
| MKTD-03 | 1 | YFRateLimitError 시 tenacity 재시도 | unit (mock side_effect) | `pytest tests/test_market.py::test_retries_on_rate_limit -x` | ❌ W0 |
| COMP-01 | 2 | EMA(span=N, adjust=False) 정확성 | unit (골든) | `pytest tests/test_ema.py::test_ema_matches_tradingview_formula -x` | ❌ W0 |
| COMP-02 | 2 | 차이 = price - EMA (12 시리즈) | unit | `pytest tests/test_ema.py::test_diff_columns -x` | ❌ W0 |
| COMP-03 | 2 | EMA 일변동 = EMA.diff() | unit | `pytest tests/test_ema.py::test_daily_change -x` | ❌ W0 |
| COMP-04 | 2 | expanding median/std | unit | `pytest tests/test_stats.py::test_expanding_median_std -x` | ❌ W0 |
| COMP-05 | 2 | 누적 스칼라 (3행/4행) | unit | `pytest tests/test_stats.py::test_cumulative_scalars -x` | ❌ W0 |
| COMP-06 | 2 | 거래량 expanding | unit | `pytest tests/test_stats.py::test_expanding_volume -x` | ❌ W0 |
| TECH-01 | 2 | Stoch Slow(14,3,3) | unit (골든) | `pytest tests/test_indicators.py::test_stoch_slow_known_input -x` | ❌ W0 |
| TECH-02 | 2 | RSI(14, Wilder) | unit (골든) | `pytest tests/test_indicators.py::test_rsi_wilder_known_input -x` | ❌ W0 |
| TECH-04/05 | 2 | Stoch/RSI 임계값 색 버킷 | unit | `pytest tests/test_color_rules.py::test_tech_buckets -x` | ❌ W0 |
| COLOR-01~07 | 2 | σ-색 결정 (4단 + 기본) | unit | `pytest tests/test_color_rules.py::test_sigma_buckets -x` | ❌ W0 |
| SHEET-01~08, TECH-03/06, OUT-01~03 | 3 | end-to-end .xlsx 시트 구조 | integration smoke | `pytest tests/test_smoke_end_to_end.py::test_single_ticker_workbook -x` | ❌ W0 |
| EXEC-01/02 | 4 | `uv run python main.py` 부팅 | smoke | (smoke test 안에서 main.run() 호출) | ❌ W0 |
| Success Criteria #2/#3 | 3 | 3개 행 색 일치 (최신/중간/오래된) | golden + smoke | `pytest tests/test_smoke_end_to_end.py::test_color_at_three_rows -x` | ❌ W0 |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `pyproject.toml` — `[project]` + `[tool.hatch.build.targets.wheel]` (`src/`) + `[tool.pytest.ini_options]` (`testpaths=["tests"]`, `pythonpath=["src"]`)
- [ ] `uv add --dev pytest pytest-mock openpyxl` — dev deps
- [ ] `tests/conftest.py` — 공유 fixture (mock yfinance DataFrame, 임시 `tickers.txt`, 임시 `.env`)
- [ ] `tests/test_input.py` — INPUT-01/02/03 stubs
- [ ] `tests/test_config.py` — INPUT-05 stub
- [ ] `tests/test_market.py` — MKTD-01/02/03 stubs (network 미사용)
- [ ] `tests/test_ema.py` — COMP-01/02/03 stubs + golden 입력
- [ ] `tests/test_stats.py` — COMP-04/05/06 stubs
- [ ] `tests/test_indicators.py` — TECH-01/02 stubs + golden 입력 fixture
- [ ] `tests/test_color_rules.py` — COLOR-01~07 + TECH-04/05 버킷 stubs
- [ ] `tests/test_smoke_end_to_end.py` — smoke (mock yfinance → 실제 XlsxWriter → openpyxl 검증) stub
- [ ] `.env.example`, `tickers.txt`(예시 `AAPL`), `.gitignore`(`output/`, `.env`, `__pycache__`, `.venv`)

---

## Manual-Only Verifications (Walking Skeleton)

| # | Behavior | Requirement | Why Manual | Test Instructions |
|---|----------|-------------|------------|-------------------|
| 1 | 파일 생성 | OUT-01/02 | 실제 디스크 + 날짜 파일명 검증 | `uv run python main.py` 실행 → `output/portfolio_YYYYMMDD.xlsx` 존재 확인 |
| 2 | 시트 구조 | SHEET-01~06 | Excel UI 렌더 확인 | Excel에서 `AAPL` 시트 열기 → A1=`AAPL`, 3행/4행 숫자, 5행 한국어 헤더, 6행~ 날짜 내림차순 |
| 3 | 색 정합성 | COLOR-01~07, Success Criteria #3 | 시각 검증 + 정적 베이킹 검증 | 3개 행(최신/중간/오래된)에 대해 σ 수기 계산 → 셀 색 일치 |
| 4 | 동적 CF 부재 | Success Criteria #3 | Excel UI에서만 확인 가능 | Excel "조건부 서식 → 규칙 관리"에 항목 0개 |
| 5 | Stoch/RSI 색 | TECH-04/05 | 시각 검증 | Stoch≤20 셀 초록, ≥80 셀 빨강 각 1셀 이상 존재 |
| 6 | 에러 경로 | INPUT-03 | 콘솔 한국어 출력 + exit code | `tickers.txt` 비우고 실행 → 한국어 에러 + `echo $LASTEXITCODE` ≠ 0 |

---

## Golden Test Fixtures

**EMA(span=3, adjust=False, 입력 = [1, 2, 3, 4, 5]):**
- α = 2/(3+1) = 0.5
- EMA = [1.0, 1.5, 2.25, 3.125, 4.0625]

**Wilder RSI(14):** Wave 0에서 J. Welles Wilder 1978 표준 예제 또는 TradingView 캡처 1개를 `tests/fixtures/rsi_golden.json` fixture로 고정.

**Stoch Slow(14,3,3) sanity:**
- 모든 close=high → Slow %K ≈ 100
- 모든 close=low → Slow %K ≈ 0
- close=100, high=110, low=90 일정 → %K = 50

---

## Environment Availability

| Dependency | Required By | Available | Fallback |
|------------|------------|-----------|----------|
| Python 3.13 | EXEC-01 | 사용자 설치 | `uv python install 3.13` |
| uv | EXEC-02 | 사용자 설치 (사전 필수) | 없음 |
| 인터넷 (Yahoo Finance) | MKTD-01 (runtime only) | runtime | smoke test mock |
| Windows console UTF-8 | D-05 한국어 | `sys.stdout.reconfigure(encoding='utf-8')` | `chcp 65001` 안내 |
| `.env` (사용자) | INPUT-05 | 사용자 책임 | 비어있으면 fail-fast |
| `tickers.txt` (사용자) | INPUT-01 | 사용자 책임 | 비어있으면 INPUT-03 에러 |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING test files
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter after planner closes loop

**Approval:** pending
