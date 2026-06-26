---
phase: 02-scaling-portfolio-summary
plan: 02
wave: 2
type: execute
status: complete
completed_date: 2026-05-26
dependency_graph:
  requires: [02-01]
  provides: [TickerSpec, read_tickers_extended, fetch_ohlcv_cached, run_all, TickerResult, TickerFailure]
  affects: [src/stocksig/io/input.py, src/stocksig/io/market.py]
tech_stack:
  added: []
  patterns:
    - "ThreadPoolExecutor(max_workers=4) + as_completed + per-future try/except (RESEARCH Pattern 4)"
    - "Decorator stack: throttled_yahoo → tenacity.retry → fetch_ohlcv (each retry attempt acquires a 2 RPS token)"
    - "Cache-first wrapper: cache.get → miss → throttled fetch → cache.put"
    - "Frozen @dataclass for input spec; mutable @dataclass for result/failure"
key_files:
  created:
    - src/stocksig/runner.py
    - tests/test_input_extended.py
    - tests/test_runner.py
  modified:
    - src/stocksig/io/input.py
    - src/stocksig/io/market.py
    - tests/test_market.py
decisions:
  - "D-06 enforced: rows < 50% of 2500 → ValueError('부분 데이터: ...') in process_ticker, caught by run_all → TickerFailure"
  - "fetch_ohlcv decorator order: @throttled_yahoo above @retry — token acquired before each retry"
  - "read_tickers (1-column legacy) kept as wrapper over read_tickers_extended — Phase 1 main_run.py:99 unaffected until Wave 4"
metrics:
  duration_minutes: ~25
  tasks_completed: 3
  files_changed: 6
  tests_added: 21
  tests_total: 97
tags: [python, concurrency, error-isolation, threadpool, cache, throttle]
---

# Phase 2 Plan 02: Multi-ticker Fan-out Runner Summary

**One-liner:** Wave 1 modules (cache, throttle, market_kind) composed into a cache-first throttled fetcher + a `ThreadPoolExecutor(4)` runner that isolates per-ticker exceptions (including D-06 partial-data) into Korean-labeled `TickerFailure` results.

## What Built

| Task | Module/File | Purpose | Commit |
|------|-------------|---------|--------|
| 1 | `src/stocksig/io/input.py` | `TickerSpec(symbol, tier, industry)` dataclass + `read_tickers_extended` (tab/whitespace agnostic via `line.split()`) + back-compat `read_tickers` | `15cebea` |
| 1 | `tests/test_input_extended.py` | 11 cases (single-col back-compat, tab, whitespace, mixed, multi-word industry, Korean industry, comments, blanks, missing file, empty file, read_tickers wrapper) | `15cebea` |
| 2 | `src/stocksig/io/market.py` | `@throttled_yahoo` applied above `@retry` (2 RPS enforced per retry attempt); new `fetch_ohlcv_cached(ticker)` — cache-first wrapper | `4079e19` |
| 2 | `tests/test_market.py` | +3 tests: `cache_miss_calls_fetch`, `cache_hit_skips_fetch`, `throttle_applied` (10 calls ≥4.5s wall-clock) | `4079e19` |
| 3 | `src/stocksig/runner.py` (NEW) | `run_all` orchestrator + `process_ticker` worker + `_validate_row_count` (D-06) + dataclasses `TickerResult`, `TickerFailure` | `3cbc333` |
| 3 | `tests/test_runner.py` | 7 tests: all-success, isolation (ValueError + ConnectionError), partial-data failure (D-06), Korean progress log, failure summary log, max_workers=4 spy | `3cbc333` |

## Sample I/O Round-trip

**Input** (`tickers.txt`):
```
# 데모 헤더
AAPL	1	Technology
005930.KS	2	반도체
```

**`read_tickers_extended(path)`** →
```python
[
  TickerSpec(symbol='AAPL', tier='1', industry='Technology'),
  TickerSpec(symbol='005930.KS', tier='2', industry='반도체'),
]
```

**`run_all(specs, classify_market, pipeline)`** with `pipeline('005930.KS')` returning 1000-row DataFrame →
```python
results  = [TickerResult(spec=TickerSpec('AAPL','1','Technology'),
                         enriched_df=<2500 rows>, market='US')]
failures = [TickerFailure(spec=TickerSpec('005930.KS','2','반도체'),
                          reason='부분 데이터: 1000 거래일 (예상 2500의 40%)')]
```

Console log emitted (caplog-verified substrings):
```
[1/2] OK AAPL
[2/2] FAIL 005930.KS | 부분 데이터: 1000 거래일 (예상 2500의 40%)
총 2 티커 중 성공 1 / 실패 1
실패 티커: 005930.KS
```

## Verification

- `pytest tests/test_input.py tests/test_input_extended.py tests/test_market.py tests/test_runner.py -q` → **27 green**
- `pytest -q` full suite → **97 passed in 78s** (76 baseline + 21 new)
- All success criteria from frontmatter `must_haves.truths` satisfied:
  - [x] `read_tickers_extended` honors tab/whitespace/`#`/back-compat
  - [x] `read_tickers` legacy signature returns `list[str]` (Phase 1 main_run unaffected)
  - [x] `fetch_ohlcv_cached` hits cache on 2nd same-day call; throttled at ≤2 RPS (4.5s for 10 calls)
  - [x] `run_all` exception isolation per future
  - [x] Partial-data → `TickerFailure(reason='부분 데이터: ...')` (D-06)
  - [x] Korean `[k/N] OK`/`FAIL` + failure summary appear in caplog

## Deviations from Plan

**None — plan executed exactly as written.** No Rule 1/2/3/4 fixes needed.

Notes:
- `functools.wraps` propagates the `.retry` attribute through `@throttled_yahoo` because `WRAPPER_UPDATES` includes `__dict__` — Phase 1 fixture `_no_retry_wait` (in test_market.py) continues to work unmodified.
- pyrate-limiter's blocking `try_acquire("yahoo")` proved out: 10-call throttle test took ≈5s, within the ≥4.5s budget.
- curl_cffi `_SESSION` module-level singleton not refactored in this wave (per prompt direction); no thread-sharing issues observed across 4-worker `test_all_success`. Phase 3 may revisit if MKTD blockers surface.

## Threat Mitigations Applied

| Threat ID | Status |
|-----------|--------|
| T-02-04 (one bad ticker aborts run) | **Mitigated** — per-future try/except in `run_all` (test_invalid_ticker_isolated, test_network_error_isolated) |
| T-02-06 (silent partial-data truncation) | **Mitigated** — `_validate_row_count` ≥50% raises → `TickerFailure` (test_partial_data_marked_failure) |

## Known Stubs

None. `main_run.py` is intentionally untouched (Wave 4 refactor will wire `run_all` into the pipeline).

## Self-Check: PASSED

- `src/stocksig/runner.py` FOUND
- `src/stocksig/io/input.py` FOUND (modified)
- `src/stocksig/io/market.py` FOUND (modified)
- `tests/test_input_extended.py` FOUND
- `tests/test_runner.py` FOUND
- Commits `15cebea`, `4079e19`, `3cbc333` FOUND on master
