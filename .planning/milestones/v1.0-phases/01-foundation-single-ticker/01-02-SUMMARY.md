---
phase: 01-foundation-single-ticker
plan: 02
subsystem: io
tags: [python, yfinance, curl-cffi, tenacity, dotenv]
requires: [01-01]
provides:
  - stocksig.config.load_env
  - stocksig.io.input.read_tickers
  - stocksig.io.market.fetch_ohlcv
  - stocksig.io.market._SESSION
affects: []
tech_stack_added:
  - python-dotenv
  - tenacity 9.x
  - curl_cffi 0.15.x (Chrome impersonation)
patterns:
  - "module-level curl_cffi Session (single instance, reused by downstream waves)"
  - "Korean fail-fast via logging.error + sys.exit(1) (D-05 format)"
  - "tenacity @retry exposed as function attribute (fetch_ohlcv.retry.wait override-able in tests)"
key_files_created:
  - src/stocksig/__init__.py
  - src/stocksig/config.py
  - src/stocksig/io/__init__.py
  - src/stocksig/io/input.py
  - src/stocksig/io/market.py
key_files_modified:
  - tests/test_input.py
  - tests/test_config.py
  - tests/test_market.py
decisions:
  - "fetch_ohlcv uses date.today() inside function (not module import) so tests can freeze date if needed"
  - "empty DataFrame -> ValueError (not SystemExit) — caller decides exit policy (Phase 1 single ticker fail-fast OK)"
  - "tenacity wait overridden to wait_none() in tests via autouse fixture — keeps full suite < 1s"
metrics:
  duration_minutes: 4
  tasks_completed: 2
  files_created: 5
  files_modified: 3
  tests_green: 14
  tests_xfail_remaining: 12
completed: 2026-05-21
---

# Phase 1 Plan 02: Wave 1 io 레이어 (INPUT/MKTD) Summary

io 레이어 — `tickers.txt` 리더 + `.env` 로더 + curl_cffi/tenacity 기반 yfinance OHLCV 어댑터 — 가 GREEN으로 전환되어 단일 미국 티커가 외부 시세까지 도달하는 vertical 통로의 시작점을 확보했다.

## Public Signatures

```python
# src/stocksig/config.py
def load_env(env_path: str | Path | None = None) -> dict[str, str]
    # 반환: {"EDGAR_USER_AGENT_EMAIL": ..., "OPENDART_API_KEY": ...}
    # 비어있으면 logging.error + sys.exit(1)

# src/stocksig/io/input.py
def read_tickers(path: str | Path) -> list[str]
    # tickers.txt: 한 줄당 1 티커, '#' 주석/빈 줄 skip, suffix 보존
    # 파일 부재 / 유효 0개 -> sys.exit(1)

# src/stocksig/io/market.py
_SESSION: curl_cffi.requests.Session  # impersonate="chrome", 모듈 레벨

@retry(wait=wait_exponential(min=2,max=30)+wait_random(0,1),
       stop=stop_after_attempt(5),
       retry=retry_if_exception_type(YFRateLimitError),
       reraise=True)
def fetch_ohlcv(ticker: str) -> pd.DataFrame
    # today-4000d ~ today, auto_adjust=True
    # 빈 DataFrame -> ValueError
```

## Korean Error Messages (후속 Phase 2 INPUT-04 톤 참고용)

| 모듈 | 트리거 | 메시지 (logging.error 포맷) |
|------|--------|----------------------------|
| config | EDGAR_USER_AGENT_EMAIL blank | `config | .env의 EDGAR_USER_AGENT_EMAIL 값이 비어있습니다.` |
| config | OPENDART_API_KEY blank | `config | .env의 OPENDART_API_KEY 값이 비어있습니다.` |
| io.input | 파일 부재 | `tickers.txt | tickers.txt 파일을 찾을 수 없습니다: {path}` |
| io.input | 유효 티커 0개 | `tickers.txt | tickers.txt 파일이 비어있습니다.` |
| io.market | 빈 OHLCV | `{ticker} | yfinance가 빈 OHLCV를 반환했습니다 (티커 확인 필요).` (ValueError msg) |
| io.market | 성공 로그 (info) | `{ticker} | OHLCV {N} 거래일 수신 완료` |

톤 일관성 규칙: 모듈명 `|` ticker `|` 한국어 메시지 — D-05 포맷. 종결은 마침표.

## Tests Turned GREEN

7 target requirements (INPUT-01/02/03/05, MKTD-01/02/03) + 7 behavior-block coverage tests = 14 total GREEN. 12 future-wave tests remain `xfail` per plan.

| File | New GREEN Count | Tests |
|------|----------------|-------|
| tests/test_input.py | 5 | single, kr_suffix, skips_blank_and_comments, empty_file_exits, missing_file_exits |
| tests/test_config.py | 3 | missing_env_fails, blank_opendart_key_fails, valid_env_returns_dict |
| tests/test_market.py | 6 | date_window, curl_cffi_session, retries_on_rate_limit, retries_exhausted_reraises, empty_dataframe_raises, logs_trading_day_count |

## Commits

- `9265113` feat(01-02): implement config.load_env + io.input.read_tickers (INPUT-01/02/03/05 GREEN)
- `d4875ba` feat(01-02): implement io.market.fetch_ohlcv with curl_cffi + tenacity (MKTD-01/02/03 GREEN)

## Deviations from Plan

None — plan executed exactly as written. Minor expansion only: added 7 behavior-coverage tests beyond the 7 required RED stubs to lock additional cases listed in the `<behavior>` blocks (blank/comment skip, missing file, valid-env happy path, retry-exhaustion failure, empty-DataFrame ValueError, success-log content). All additions are positive coverage — no scope creep beyond plan behavior specifications.

## Threat Mitigations Applied

- **T-01-V1**: `read_tickers` strips + skips blank/`#` lines (mitigation).
- **T-01-DoS**: tenacity `stop_after_attempt(5)` + `wait_exponential(max=30)` cap (mitigation).
- **T-01-INFO**: `load_env` logs key names only, never `.env` values (mitigation).

## Self-Check: PASSED

- src/stocksig/__init__.py — FOUND
- src/stocksig/config.py — FOUND
- src/stocksig/io/__init__.py — FOUND
- src/stocksig/io/input.py — FOUND
- src/stocksig/io/market.py — FOUND
- Commit 9265113 — FOUND
- Commit d4875ba — FOUND
- 14 tests GREEN, 12 xfailed (target met)
