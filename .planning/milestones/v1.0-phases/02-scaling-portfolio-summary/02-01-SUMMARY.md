---
phase: 02-scaling-portfolio-summary
plan: 01
subsystem: io
tags: [python, sqlite, rate-limit, caching]
requires: [phase-01-code-complete]
provides:
  - io.cache (24h TTL OHLCV pickle cache)
  - io.throttle (Yahoo 2 RPS token bucket decorator)
  - io.market_kind (US/KR suffix classifier)
affects: []
tech_added:
  - diskcache>=5.6
  - pyrate-limiter>=3
  - freezegun>=1.5 (dev)
patterns: [token-bucket, write-through-cache, suffix-classifier]
key_files_created:
  - src/stocksig/io/cache.py
  - src/stocksig/io/throttle.py
  - src/stocksig/io/market_kind.py
  - tests/test_cache.py
  - tests/test_throttle.py
  - tests/test_market_kind.py
key_files_modified:
  - pyproject.toml
  - uv.lock
  - .gitignore
decisions:
  - "Use pyrate-limiter 4.x default blocking try_acquire (no max_delay kwarg in 4.x; was 3.x-only)"
  - "Cache key includes ISO date so day-boundary tick yields automatic miss (defense in depth alongside 24h TTL)"
  - "Korean + English HIT/MISS substrings in same log line (satisfies MKTD-05 + user-facing 한국어 우선)"
metrics:
  tasks_completed: 2
  tests_added: 17
  files_created: 6
  files_modified: 3
  duration: ~10 min
  completed: 2026-05-26
commits:
  - 7be330d  feat(02-01): add diskcache OHLCV cache with 24h TTL
  - 9446d61  feat(02-01): add Yahoo throttle (2 RPS) + US/KR market classifier
---

# Phase 2 Plan 01: Foundation IO Infrastructure Summary

**One-liner:** Disk-based 24h OHLCV cache (diskcache) + Yahoo 2-RPS token-bucket throttle (pyrate-limiter) + US/KR ticker classifier, all pure modules with isolated unit tests.

## What Was Built

Two atomic commits across the IO foundation layer that Phase 2 Wave 2 will compose into `io/market.py`:

### Task 1 — `feat(02-01): add diskcache OHLCV cache with 24h TTL` (`7be330d`)
- Added `diskcache>=5.6`, `pyrate-limiter>=3`, `freezegun>=1.5` (dev) to `pyproject.toml` / `uv.lock`.
- `.gitignore`: appended `.cache/` so pickle store stays out of repo (D-05).
- `src/stocksig/io/cache.py`:
  - `make_key(ticker, today=None) -> "{TICKER}|{YYYY-MM-DD}"`.
  - `get_ohlcv(ticker)` / `put_ohlcv(ticker, df)` with `expire=86400`.
  - Lazy `_get_cache()` creates `.cache/ohlcv/` and instantiates `diskcache.Cache`.
  - HIT/MISS logged via `logging.INFO` with both Korean (`캐시 HIT`) and English (`cache HIT`) substrings per MKTD-05.
- `tests/test_cache.py`: 7 tests — dir creation, put/get roundtrip, miss → None, within-TTL hit (freezegun 23h58m, same day), across-day miss (freezegun 24h1m), key format, HIT/MISS Korean log assertion. All use `tmp_path` + monkeypatched `_DEFAULT_DIR` for isolation.

### Task 2 — `feat(02-01): add Yahoo throttle (2 RPS) + US/KR market classifier` (`9446d61`)
- `src/stocksig/io/throttle.py`: `@throttled_yahoo` decorator wrapping `Limiter(Rate(2, Duration.SECOND))`; relies on pyrate-limiter 4.x `try_acquire("yahoo", blocking=True)` default. `functools.wraps` preserves signature.
- `src/stocksig/io/market_kind.py`: `KR_SUFFIXES = (".KS", ".KQ", ".KOSDAQ", ".KOSPI")`; `classify_market(symbol) -> Literal["US","KR"]`, uppercases input, falls through to `"US"` for non-KR suffixes (`.T`, `.HK`, etc.) per L-14.
- `tests/test_throttle.py`: 3 tests — return value preserved, `__name__` preserved (functools.wraps), 10-call wall-clock ≥ 4.0s.
- `tests/test_market_kind.py`: 7 tests — US default, KS/KQ/KOSPI/KOSDAQ all KR, case-insensitive, `.T` → US fallback, `KR_SUFFIXES` constant exposed.

## Verification

```
pytest tests/test_cache.py tests/test_throttle.py tests/test_market_kind.py -q
17 passed in 5.61s
```

- `uv pip show diskcache pyrate-limiter` — both non-empty (4.1.0 / 5.6.x).
- `.gitignore` contains exactly one `^.cache` line.
- `python -c "from stocksig.io import cache, throttle, market_kind; from stocksig.io.market_kind import classify_market; print(classify_market('005930.KS'))"` → `KR`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] pyrate-limiter 4.x dropped `max_delay` kwarg**
- **Found during:** Task 2, first test run.
- **Issue:** Plan/RESEARCH Pattern 3 assumed pyrate-limiter 3.x API with `Limiter(rate, max_delay=...)`. Installed version is 4.1.0; `Limiter.__init__` signature is `(argument, buffer_ms=50)`.
- **Fix:** Drop `max_delay` kwarg. Rely on `try_acquire`'s default `blocking=True` (4.x exposes blocking semantics directly on the acquire call rather than the limiter constructor). Behavior identical: caller blocks until token available.
- **Files modified:** `src/stocksig/io/throttle.py`
- **Commit:** `9446d61` (included in Task 2 commit; no separate fix commit since this was caught pre-commit during RED→GREEN iteration).

**2. [Rule 3 - Test design] freezegun + diskcache TTL interaction**
- **Found during:** Task 1, first run of `test_hit_within_ttl`.
- **Issue:** freezegun does not influence diskcache's internal TTL clock, and a 23h59m tick from 09:00 crosses calendar boundary → `make_key()` returns a different key → false negative.
- **Fix:** Set freeze origin to `00:01` and tick `23h58m` to stay within the same calendar day (key invariant) for the within-TTL test. The across-day miss test relies on key change at midnight rather than diskcache's TTL — which is correct behavior since `make_key` embeds the date, providing defense in depth alongside the 24h expire.
- **Files modified:** `tests/test_cache.py`
- **Commit:** `7be330d`.

Neither deviation required user input — both Rule 3 (blocking issues for current task).

## Known Stubs

None. All three modules are fully wired; Wave 2 will import and compose them.

## Threat Flags

None. New surface (`diskcache` pickle deserialization, `pyrate-limiter` in-process token bucket) is internal-only with no external trust boundary expansion beyond what the threat model already accepts (T-02-01, T-02-02). No new network endpoints or auth paths introduced.

## Self-Check: PASSED

- `src/stocksig/io/cache.py` — FOUND
- `src/stocksig/io/throttle.py` — FOUND
- `src/stocksig/io/market_kind.py` — FOUND
- `tests/test_cache.py` — FOUND
- `tests/test_throttle.py` — FOUND
- `tests/test_market_kind.py` — FOUND
- Commit `7be330d` — FOUND in `git log`
- Commit `9446d61` — FOUND in `git log`
- 17/17 tests GREEN
