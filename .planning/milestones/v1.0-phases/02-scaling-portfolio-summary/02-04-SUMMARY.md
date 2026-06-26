---
phase: 02-scaling-portfolio-summary
plan: 04
subsystem: orchestration
tags: [python, orchestration, integration, multi-ticker]
dependency_graph:
  requires: ["02-01", "02-02", "02-03"]
  provides: ["main_run.run (2-pass)", "_compute_enriched", "_make_pipeline"]
  affects: ["src/stocksig/main_run.py"]
tech_stack:
  added: []
  patterns: ["2-pass orchestration (fan-out + write)", "df.attrs scalar stash"]
key_files:
  created:
    - tests/test_smoke_n_tickers.py
  modified:
    - src/stocksig/main_run.py
decisions:
  - "PASS 1 (parallel via runner.run_all) → PASS 2 (xlsxwriter sequential write)"
  - "scalars 캐싱: df.attrs['scalars'] (pandas 2.x preserves through threading + concat — T-02-12)"
  - "시트1 FIRST 호출로 sheetnames[0] 순서 결정론적 (PORT-01)"
  - "PASS 2 iteration uses input_order (specs 순서) — as_completed 비결정성 분리"
metrics:
  duration_minutes: ~10
  tasks: 2
  files_changed: 2
  tests_added: 8
  tests_total: 123
  completed_date: 2026-05-26
---

# Phase 2 Plan 4: main_run 2-pass 오케스트레이션 Summary

**One-liner:** `main_run.run()` refactored to PASS-1 (`run_all` parallel fetch+enrich) → PASS-2 (`write_portfolio_sheet` first, then per-ticker), guaranteeing `sheetnames[0] == "시트1"` and routing failures to 시트1 only.

## Tasks Completed

| Task | Description | Commit |
| ---- | ----------- | ------ |
| 1 | Refactor main_run.py to 2-pass orchestrator | `c2535cc` |
| 2 | Smoke test — 10-ticker end-to-end with mocked yfinance | `8e0c577` |

## What Built

### `src/stocksig/main_run.py` (rewritten)

- **PASS 1:** `read_tickers_extended(path)` → `specs`. `_make_pipeline()` closes over
  `fetch_ohlcv_cached + _compute_enriched`. `run_all(specs, classify_market, pipeline)`
  returns `(results, failures)` from `ThreadPoolExecutor(max_workers=4)`.
- **PASS 2:** `make_workbook(path)` → `write_portfolio_sheet(...)` FIRST (시트1) →
  iterate `input_order` calling `write_sheet_for_ticker(...)` for each successful result.
  Scalars retrieved from `res.enriched_df.attrs["scalars"]` (no recomputation).
- **Korean logging:** `티커 N개 로드 완료`, `워크북 저장: <path>`, `실패 N개 — 시트1에 표시됨: <list>`.
  `runner.run_all` already emits per-ticker `[k/N] OK/FAIL` + `총 N 티커 중 성공 X / 실패 Y` summary.

### `_compute_enriched(raw) -> (df, scalars)`

Extracted Phase 1 compute chain (steps 1–10 from old run() body lines 113–182) into a pure helper. No behaviour change — Phase 1 smoke (21 tests) still green identically.

### `tests/test_smoke_n_tickers.py` (NEW, 8 tests)

| Test | Verifies |
| ---- | -------- |
| `test_portfolio_is_first_sheet` | PORT-01 — `sheetnames[0] == "시트1"` |
| `test_all_tickers_have_sheets` | 5 tickers → `["시트1", AAPL, MSFT, GOOG, 005930.KS, 035720.KQ]` |
| `test_failed_ticker_in_sheet1_only` | D-03 — failed ticker absent from sheet list; 시트1 row has `실패: ...` |
| `test_partial_data_marked_failure` | D-06 — 800 rows → 시트1 `실패: 부분 데이터: 800 거래일 (예상 2500의 32%)` |
| `test_cache_hit_on_second_run` | MKTD-05 — 2nd run: 0 fetch calls; caplog has `cache HIT` per ticker |
| `test_10_tickers_completes` | runner log `총 10 티커 중 성공 10 / 실패 0` present |
| `test_input_order_preserved` | PORT-02 — `[C, A, B]` input → sheets `[시트1, C, A, B]` |
| `test_scalars_roundtrip_through_attrs` | T-02-12 — `df.attrs["scalars"]` survives `run_all` future round-trip |

## Sheet Order Verification (from `test_all_tickers_have_sheets`)

```
input: AAPL MSFT GOOG 005930.KS 035720.KQ
wb.sheetnames == ["시트1", "AAPL", "MSFT", "GOOG", "005930.KS", "035720.KQ"]  ✓
```

## Sample Korean Console Output

```
INFO  stocksig.main_run | main | 티커 10개 로드 완료
INFO  stocksig.runner   | [1/10] OK AAPL
INFO  stocksig.runner   | [2/10] OK MSFT
INFO  stocksig.runner   | [3/10] OK GOOG
WARN  stocksig.runner   | [4/10] FAIL BAD | mocked failure
INFO  stocksig.runner   | [5/10] OK AMZN
...
INFO  stocksig.runner   | 총 10 티커 중 성공 9 / 실패 1
WARN  stocksig.runner   | 실패 티커: BAD
INFO  stocksig.main_run | AAPL | 시트 작성 완료
...
INFO  stocksig.main_run | main | 워크북 저장: output\portfolio_20260526.xlsx
WARN  stocksig.main_run | 실패 1개 — 시트1에 표시됨: BAD
```

## Verification

- `uv run python -c "from stocksig.main_run import run; print('import ok')"` → ok
- `uv run pytest tests/test_smoke_n_tickers.py -x -q` → 8 passed in 147s
- `uv run pytest tests/test_smoke_end_to_end.py -x -q` → 21 passed in 90s (Phase 1 unchanged)
- `uv run pytest -q` → **123 passed in 262s** (115 prior + 8 new)

## Success Criteria

- [x] `main_run.run()` is 2-pass; PORT-01 verified
- [x] Failed tickers visible only on 시트1 (D-03)
- [x] Cache hit on same-day re-run (MKTD-05)
- [x] Partial-data tickers routed to failure (D-06)
- [x] `enriched_df.attrs["scalars"]` round-trip preserved through runner (T-02-12)

## Deviations from Plan

None — plan executed verbatim. The risk flagged (`enriched.attrs["scalars"]` dropping through pandas copy) was preventively covered by adding `test_scalars_roundtrip_through_attrs` which confirms the attrs dict survives `ThreadPoolExecutor` future round-trip and `pipeline` closure — no defensive copy needed.

## Self-Check: PASSED

- src/stocksig/main_run.py — FOUND
- tests/test_smoke_n_tickers.py — FOUND
- Commit `c2535cc` — FOUND
- Commit `8e0c577` — FOUND
