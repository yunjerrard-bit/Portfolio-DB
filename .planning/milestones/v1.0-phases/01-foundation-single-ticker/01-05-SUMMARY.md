---
phase: 01-foundation-single-ticker
plan: 05
subsystem: orchestration
tags: [orchestration, entrypoint, walking-skeleton, smoke-test, manual-verify-pending]
requires: [01-02, 01-03, 01-04]
provides:
  - "stocksig.main_run.run(tickers_path, env_path, output_dir) -> Path"
  - "main.py CLI: --tickers --env --output-dir"
  - "stocksig.main re-export shim (smoke test contract)"
affects: [tests/test_smoke_end_to_end.py]
tech-stack:
  added: []
  patterns:
    - "try/finally + wb.close() (T-01-EXC mitigation)"
    - "sys.stdout.reconfigure(encoding=utf-8) on win32 (T-01-UTF mitigation)"
    - "argparse late-import of stocksig.main_run (--help fast path)"
key-files:
  created:
    - main.py
    - src/stocksig/main.py
    - src/stocksig/main_run.py
  modified:
    - tests/test_smoke_end_to_end.py
decisions:
  - "stocksig.main as re-export shim — Wave 0 smoke test imports `from stocksig.main import run` but PLAN names module `main_run`; shim keeps both contracts"
  - "Same-day overwrite (output/portfolio_YYYYMMDD.xlsx) — RESEARCH Open Question #2 recommendation"
  - "Open column NOT in DATA_COLS (40 cols = 4 OHLCV{Close,High,Low,Volume} + 36 EMA family)"
metrics:
  duration_minutes: ~12
  completed: "2026-05-21"
  tasks_completed: 1
  tasks_total: 2
  files_created: 3
  files_modified: 1
manual_verify_pending: true
---

# Phase 1 Plan 05: Walking Skeleton Orchestration Summary

`main.py` 엔트리포인트 + `stocksig.main_run.run()`이 Wave 1~3의 모든 공개 시그니처를 연결하여 Walking Skeleton 자동 검증 경로(2 smoke tests)를 GREEN으로 닫음.

## 흐름 다이어그램

```
main.py (argparse, UTF-8 reconfigure, basicConfig)
  └── stocksig.main_run.run(tickers_path, env_path, output_dir)
        1. load_env(env_path)                # INPUT-05 fail-fast
        2. read_tickers(tickers_path)        # INPUT-01/02/03
        3. make_workbook(output/portfolio_YYYYMMDD.xlsx)
        4. for ticker in tickers:
             fetch_ohlcv(ticker)             # MKTD-01~03 (curl_cffi + tenacity)
             add_ema_columns(df)             # +36 cols (EMA/DIFF/dailychg)
             add_expanding_stats(df, DATA_COLS=40)
             cumulative_scalars(df, DATA_COLS) -> scalars dict (3행/4행)
             stoch_slow(df); rsi_wilder(df)  # TECH-01/02
             write_sheet_for_ticker(...)     # SHEET-01~08 + 정적 색 베이킹
        5. finally: wb.close()               # T-01-EXC mitigation
        6. return output_path
```

## Tasks 실행

| Task | Status | Commit |
|------|--------|--------|
| Task 1: main_run.run() + main.py + smoke GREEN | ✅ done | `28ffc3f` |
| Task 2: 수기 검증 6 포인트 (checkpoint:human-verify) | ⏸ pending user | — |

## 자동 검증 결과

- `uv run pytest -x -q` → **26 passed, 0 xfailed** (plan에서 19/19 예상했으나 prior wave가 추가 테스트 보강 — 무해)
- `tests/test_smoke_end_to_end.py::test_single_ticker_workbook` → **GREEN**
- `tests/test_smoke_end_to_end.py::test_color_at_three_rows` → **GREEN**

## 수기 검증 6 포인트 (User Action Required)

본 plan의 Task 2 (`checkpoint:human-verify`)는 자율 실행자가 수행 불가 — 실제 yfinance 네트워크 호출, Excel UI 색 시각 확인, 동적 CF 부재 검증 등은 사용자만 수행 가능. VALIDATION.md §Manual-Only Verifications 표 그대로:

1. **파일 생성 (OUT-01/02)** — `uv run python main.py` 실행 → `output/portfolio_YYYYMMDD.xlsx` 존재 확인 (.env에 `EDGAR_USER_AGENT_EMAIL`/`OPENDART_API_KEY` 채워져야 함).
2. **시트 구조 (SHEET-01~06)** — Excel에서 `AAPL` 시트: A1=`AAPL`, 3행/4행 숫자, 5행 한국어 헤더, 6행~ 날짜 내림차순.
3. **색 정합성 (COLOR-01~07)** — 3개 행(최신/중간/오래된) Close 셀의 `(종가 - 중앙값)/표준편차` 수기 계산 → D-04 색 표와 시각 일치.
4. **동적 CF 부재** — Excel "조건부 서식 → 규칙 관리" 항목 **0개**.
5. **Stoch/RSI 색 (TECH-04/05)** — Stoch≤20 셀 초록, ≥80 셀 빨강, RSI 30/70 동일.
6. **에러 경로 (INPUT-03)** — `tickers.txt` 비우고 실행 → 한국어 에러 + `$LASTEXITCODE` ≠ 0.

**추가:** `.env` 키 하나 비우고 실행 → 한국어 fail-fast + exit ≠ 0 (Success Criteria #5).

## Deviations from Plan

### Rule 3 - Blocking Issue (auto-fixed)

**1. [Rule 3] `stocksig.main` re-export shim 추가**
- **Issue:** Wave 0의 `tests/test_smoke_end_to_end.py`는 `from stocksig.main import run`을 이미 import 함. PLAN 01-05는 모듈명을 `stocksig.main_run`으로 명시 — 두 경로가 불일치.
- **Fix:** `src/stocksig/main.py`에 `from stocksig.main_run import run` re-export 한 줄. 정식 모듈은 `main_run` 유지, smoke test 계약도 동시에 보존.
- **Files added:** `src/stocksig/main.py` (re-export shim)
- **Commit:** `28ffc3f`

### Rule 2 - Critical Functionality (auto-added)

**2. [Rule 2] `try/finally` wb.close() (T-01-EXC mitigation)**
- **Issue:** PLAN은 ticker loop 안에서 `except: wb.close(); raise` 패턴을 제시 — 정상 경로에서도 wb.close()가 단일 지점에서 호출되도록 try/finally가 더 안전.
- **Fix:** 전체 ticker loop을 `try: ... finally: wb.close()`로 감싸 — 정상/예외 모두에서 워크북이 디스크에 닫힘 (T-01-EXC 위협 모델 명시 mitigation).
- **Commit:** `28ffc3f`

## Phase 2 진입 시 변경 지점

`stocksig.main_run.run()` 시그니처는 N 티커 스케일링에도 변경 없이 유지 가능:

- **Loop → ThreadPoolExecutor:** `for ticker in tickers:` 블록을 `concurrent.futures.ThreadPoolExecutor(max_workers=4)`로 감싸기. 단, `wb.add_worksheet`는 단일 스레드에서 호출(XlsxWriter 제약) — 워커는 df 계산만 병렬화, sheet write는 main 스레드 직렬화.
- **Cache 삽입 위치:** `fetch_ohlcv(ticker)` 직전 — `cache.get_or_fetch(ticker, fetch_ohlcv)` 형태.
- **MKTD-04 (다중 티커 fail-isolation):** 현재 `try/finally`만 있음 — Phase 2에서 ticker별 `try/except` + skip + 마지막에 실패 ticker 목록 로깅으로 확장.

## Known Stubs

None.

## Self-Check: PASSED

- ✓ `main.py` exists
- ✓ `src/stocksig/main.py` exists
- ✓ `src/stocksig/main_run.py` exists
- ✓ Commit `28ffc3f` exists in `git log`
- ✓ 26/26 tests GREEN (0 xfailed)
