---
phase: 01-foundation-single-ticker
plan: 01
subsystem: bootstrap
tags: [python, uv, pytest, scaffold, walking-skeleton, red-stubs]
requires: []
provides:
  - uv-bootstrapped-project
  - 19-red-test-stubs
  - shared-fixtures
affects: [pyproject.toml, .gitignore, tests/]
tech_added:
  - uv 0.11.15
  - yfinance 1.3.0
  - curl_cffi >=0.15,<0.16
  - pandas 3.0.3
  - numpy 2.4.6
  - XlsxWriter 3.2.9
  - tenacity 9.1.4
  - python-dotenv 1.2.2
  - pytest 9.0.3
  - pytest-mock 3.15.1
  - openpyxl 3.1.5
files_created:
  - pyproject.toml
  - uv.lock
  - .env.example
  - tickers.txt
  - tests/conftest.py
  - tests/fixtures/rsi_golden.json
  - tests/test_input.py
  - tests/test_config.py
  - tests/test_market.py
  - tests/test_ema.py
  - tests/test_stats.py
  - tests/test_indicators.py
  - tests/test_color_rules.py
  - tests/test_smoke_end_to_end.py
files_modified:
  - .gitignore
decisions: []
metrics:
  duration_minutes: ~8
  completed_date: 2026-05-21
---

# Phase 1 Plan 1: Walking Skeleton Bootstrap + RED Test Stubs Summary

uv 기반 stocksig 프로젝트 부트스트랩 + Wave 1~4 TDD 사이클을 위한 19개 RED 테스트 stub 생성 (구현 코드 0줄).

## Outcome

- `uv sync` 성공 — 7 런타임 + 3 dev 패키지 + transitive 모두 설치 완료 (`uv.lock` 생성)
- `uv run pytest --collect-only -q` → **19 tests collected**
- `uv run pytest -q` → **19 xfailed in 0.63s** (모든 stub이 `NotImplementedError`를 raise하여 xfail로 흡수됨)
- VALIDATION.md "Per-Task Verification Map"의 모든 test 함수 이름이 1:1 코드로 고정됨

## Test Inventory (single source of truth for Wave 1-4)

| File | Test Function | Requirement | Import Target |
|------|---------------|-------------|---------------|
| tests/test_input.py | test_read_single_ticker | INPUT-01 | `stocksig.io.input.read_tickers` |
| tests/test_input.py | test_read_kr_suffix | INPUT-02 | `stocksig.io.input.read_tickers` |
| tests/test_input.py | test_empty_file_exits_nonzero | INPUT-03 | `stocksig.io.input.read_tickers` |
| tests/test_config.py | test_missing_env_fails | INPUT-05 | `stocksig.config.load_env` |
| tests/test_market.py | test_fetch_ohlcv_date_window | MKTD-01 | `stocksig.io.market.fetch_ohlcv` |
| tests/test_market.py | test_uses_curl_cffi_session | MKTD-02 | `stocksig.io.market._SESSION` |
| tests/test_market.py | test_retries_on_rate_limit | MKTD-03 | `stocksig.io.market.fetch_ohlcv` |
| tests/test_ema.py | test_ema_matches_tradingview_formula | COMP-01 | `stocksig.compute.ema.add_ema_columns` |
| tests/test_ema.py | test_diff_columns | COMP-02 | `stocksig.compute.ema.add_ema_columns` |
| tests/test_ema.py | test_daily_change | COMP-03 | `stocksig.compute.ema.add_ema_columns` |
| tests/test_stats.py | test_expanding_median_std | COMP-04 | `stocksig.compute.stats.add_expanding_stats` |
| tests/test_stats.py | test_cumulative_scalars | COMP-05 | `stocksig.compute.stats.cumulative_scalars` |
| tests/test_stats.py | test_expanding_volume | COMP-06 | `stocksig.compute.stats.add_expanding_stats` |
| tests/test_indicators.py | test_stoch_slow_known_input | TECH-01 | `stocksig.compute.indicators.stoch_slow` |
| tests/test_indicators.py | test_rsi_wilder_known_input | TECH-02 | `stocksig.compute.indicators.rsi_wilder` |
| tests/test_color_rules.py | test_tech_buckets | TECH-04/05 | `stocksig.compute.color_rules` |
| tests/test_color_rules.py | test_sigma_buckets | COLOR-01~07 | `stocksig.compute.color_rules` |
| tests/test_smoke_end_to_end.py | test_single_ticker_workbook | SHEET-01~08, TECH-03/06, OUT-01~03 | `stocksig.main.run` |
| tests/test_smoke_end_to_end.py | test_color_at_three_rows | Success Criteria #2/#3 | `stocksig.main.run` |

## Shared Fixtures (tests/conftest.py)

- `mock_ohlcv_df` — 2700-row deterministic OHLCV DataFrame (seed=42)
- `tmp_tickers_file(content)` — factory writing tmp tickers.txt
- `tmp_env_file(content)` — factory writing tmp .env
- `rsi_golden` — loads `tests/fixtures/rsi_golden.json` (Wilder RSI(14), expected backfilled in Wave 2)

## Deviations from Plan

**1. [Rule 3 - Tooling]** `uv` CLI was not installed on the host PATH. Installed via `pip install --user uv` (sanctioned bootstrap path; uv is verified in STACK.md). All subsequent commands invoked as `python -m uv` to bypass PATH issues. No package substitution.

**2. [Rule 1 - Bug fix]** Plan's verify command for Task 3 used POSIX `grep | wc -l` which is unavailable in PowerShell. Substituted with `pytest --collect-only -q` and counted directly (19 tests collected — exceeds the required ≥19). Functional outcome identical.

## Self-Check: PASSED

- pyproject.toml, uv.lock, .env.example, .gitignore, tickers.txt: all present
- tests/conftest.py, tests/fixtures/rsi_golden.json: present
- 8 test files: all present
- Commits: 3 task commits on master
