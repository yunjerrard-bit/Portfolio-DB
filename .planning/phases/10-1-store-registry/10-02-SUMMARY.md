---
phase: 10-1-store-registry
plan: 02
subsystem: io
tags: [fundamentals, store-registry, rewire, single-source, FUND-11]
requires:
  - "fundamentals_view.matrix_to_fundamentals (Plan 10-01)"
  - "metrics_engine.compute_matrix / inject_prices_for_quarter (Plan 10-01/Phase 8)"
  - "fundamentals_delta.sync_ticker_history (Phase 7)"
  - "runner.run_all (fundamentals_fn=None 하위호환) / TickerResult (frozen 아님 → res.fundamentals 재할당)"
provides:
  - "main_run.run 재배선 흐름 — PASS1(시세·기업명) → SYNC(DB 적재) → READ(어댑터) → PASS2(시트1 write)"
  - "단일 원천 시트1 — 외부 펀더멘털 fetch 호출 0(store SQLite 읽기만)"
affects:
  - "Plan 10-03 (구 fetch 죽은 코드 제거 — 본 plan으로 호출자 소멸)"
  - "tests/test_freeze_panes.py / test_smoke_n_tickers.py (구 fetch_fundamentals stub → sync_ticker_history stub 재배선)"
tech-stack:
  added: []
  patterns:
    - "오케스트레이션 흐름 역전 — fetch→write 를 sync→read→write 로 재배선"
    - "TickerResult.fundamentals 사후 재할당 → sheet_portfolio writer 무변경 소비"
    - "인증 skip 은 SYNC 루프에만(L7) — store 읽기는 인증 무관"
key-files:
  created: []
  modified:
    - "src/stocksig/main_run.py"
    - "tests/test_history_integration.py"
    - "tests/test_freeze_panes.py"
    - "tests/test_smoke_n_tickers.py"
decisions:
  - "D-01 흐름 순서 = PASS1(시세·기업명 fan-out, fundamentals_fn=None) → SYNC(sync_ticker_history) → READ(compute_matrix→inject_prices_for_quarter→matrix_to_fundamentals, res.fundamentals 재할당) → PASS2(write_portfolio_sheet 무변경)"
  - "D-03 _fundamentals_with_auth 클로저·fetch_fundamentals 시트1 경로 호출 제거 → store/registry 읽기로 대체"
  - "L7 인증 결합 금지 — skip_edgar/skip_dart 는 SYNC/ping 영역에만, READ(compute_matrix)에는 미적용(store 읽기 인증 무관)"
  - "요약 '펀더멘털 HIT/MISS' 줄은 본 plan 미제거(Plan 03 캐시 제거와 함께 정리 — 지금 제거 시 stats KeyError 위험)"
metrics:
  duration: ~28 min (executor 중단 후 orchestrator close-out 포함)
  tasks: 2
  files: 4
  completed: 2026-06-23
---

# Phase 10 Plan 02: main_run 펀더멘털 경로 재배선 (단일 원천) Summary

`main_run.run`의 펀더멘털 산출을 구 fetch 흐름에서 store/registry 읽기로 역전했다. PASS1은 시세·기업명만 fan-out하고, SYNC가 접수번호 델타로 DB를 적재한 뒤, READ 단계가 store 매트릭스를 어댑터로 `FundamentalsResult`로 변환해 `res.fundamentals`에 재할당한다. 시트1 writer(`sheet_portfolio.py`)는 0줄 수정으로 store 단일 원천 값을 무변경 소비한다(Core Value 보호).

## What Was Built

**Task 1 — run 흐름 재배선 PASS1 → SYNC → READ(어댑터) → PASS2 (D-01/D-03)** · commit `c226730`
- `_fundamentals_with_auth` 클로저 제거(grep 0), `run_all(..., fundamentals_fn=None)`으로 전환 — fan-out은 시세·기업명만 확보(runner.py:147 하위호환, `fundamentals=None` 안전 경로).
- SYNC 루프(`sync_ticker_history`)를 `write_portfolio_sheet` 앞으로 이동(L302 < L344, 소스 순서 단언 통과). 인증 실패 소스는 SYNC에서만 skip, 종목별 try/except + `type(exc).__name__`만 로깅(CR-01/T-10-04).
- SYNC 직후·PASS2 직전 **신규 READ 단계** 삽입: 종목별 `compute_matrix(sym)`(외부 호출 0, SQLite SELECT) → `latest_q` 도출 → `last_close = res.enriched_df.iloc[-1].get("Close")`(L4 parity) → `inject_prices_for_quarter(...)`(L1 순서) → `res.fundamentals = matrix_to_fundamentals(matrix, latest_q)`(TickerResult 재할당).
- **L7 준수:** READ/compute_matrix에 `skip_edgar`/`skip_dart` 미적용(grep 결과 L314 주석 1건뿐 — store 읽기는 인증 무관).

**Task 2 — 단일원천·외부호출 0 통합 테스트 (no_legacy_fetch / single_source)** · commit `4280974`
- `tests/test_history_integration.py`에 두 테스트 추가(+113줄). `no_legacy_fetch`: `mocker.spy`로 `fetch_fundamentals`·`fetch_edgar_cached`·`fetch_dart_cached` 감싸고 run 1회 후 세 spy `call_count == 0` 단언. `single_source`: store 적재 종목이 시트1 펀더멘털을 채우되 외부 fetch 0. 네트워크 0(yfinance mock·fixture·격리 DB).

**부수 수정 — freeze/smoke 스텁 재배선 (T1 collateral)** · commit `a428096`
- 재배선으로 `main_run.fetch_fundamentals` 바인딩이 소멸 → `test_freeze_panes.py`·`test_smoke_n_tickers.py`의 구 `fetch_fundamentals` stub이 무효. `sync_ticker_history` stub으로 교체해 네트워크 0 보장 유지(격리 store 빈 매트릭스 → 4셀 빈칸). `test_ping_failure_propagates_skip_edgar` → `test_ping_failure_skips_edgar_sync_not_sheet1`로 의미 갱신(L7 — ping 실패는 SYNC skip만, 시트1 READ 경로는 인증 무관).

## Verification

| 항목 | 결과 |
|------|------|
| 전 스위트 (repo root on PYTHONPATH) | **386 passed, 0 failed** (10-01 baseline 384 + 통합 2) |
| `_fundamentals_with_auth` grep | 0 (클로저 제거) |
| READ 배선 grep (`matrix_to_fundamentals`/`inject_prices_for_quarter`/`compute_matrix`) | 7건 (각 ≥1) |
| SYNC vs write 순서 | `sync_ticker_history` L302 < `write_portfolio_sheet` L344 ✓ |
| `skip_edgar`/`skip_dart` 위치 | L314 주석 1건뿐(L7 — store 읽기 미적용) |
| `no_legacy_fetch`/`single_source` | 2개 테스트 GREEN |
| `git diff src/stocksig/output/sheet_portfolio.py` | 빈 출력 (Core Value 색 신호 0줄 변경) |

## Deviations from Plan

### Recovery note (orchestrator close-out)
- executor가 T1(`c226730`)·T2(`4280974`) 두 태스크 커밋 후 **세션 한도로 중단** — SUMMARY 작성·tracking 갱신·부수 수정 커밋 전. orchestrator가 `safe_resume_gate`의 `close out manually` 경로로 마감: (1) 전 스위트 386 GREEN 재확인 → (2) 부수 테스트 수정 커밋(`a428096`) → (3) 본 SUMMARY 작성 → (4) STATE/ROADMAP 갱신. 중복 재실행 없음(태스크 커밋 보존).

### Auto-fixed Issues
- **[Rule 1 - 재배선 collateral] freeze/smoke 픽스처 stub 교체** — main_run 재배선으로 `fetch_fundamentals` 심볼이 사라져 두 스모크 테스트 픽스처가 무효 stub을 참조. 선언 외(`files_modified` 미포함) 파일이나 재배선이 강제한 필수 수정. `sync_ticker_history` stub으로 교체. commit `a428096`.

## Threat Surface

신규 보안 surface 0 — 순수 내부 흐름 이관. T-10-04 준수: SYNC·READ 종목별 try/except가 `type(exc).__name__`만 로깅(예외 원문·URL·OPENDART_API_KEY·EDGAR UA 미보간). T-10-05: `fundamentals_fn=None` 전환은 runner.py:147 하위호환 안전 경로. T-10-06(L7): 인증 skip 은 SYNC 루프에만. 신규 SQL·패키지 0.

## Notes for Next Plan

- **Plan 10-03 죽은 코드 제거 대상:** 본 plan으로 `fundamentals.fetch_fundamentals`/`_fill_us`/`_fill_kr`/`_default_edgar`/`_default_dart`, `edgar_client.fetch_edgar_cached`/`dart_client.fetch_dart_cached`, `cache.py`의 `.cache/fundamentals` 헬퍼군의 **호출자가 시트1 경로에서 소멸**. 안전 제거 가능. 보존: 공유 계약(D-04), store per-quarter 추출기(`fetch_edgar/dart_quarterly_raw`, L2), OHLCV/기업명 캐시(L3).
- **요약 '펀더멘털 HIT/MISS' 줄** 은 본 plan에서 미제거 — Plan 03이 캐시 stats 제거와 함께 정리(지금 제거 시 KeyError).

## Self-Check: PASSED

- 커밋 3건 존재(`c226730` T1 feat · `4280974` T2 test · `a428096` 부수).
- 전 스위트 386 passed/0 failed. 시트1 writer 0줄 변경(Core Value 불변).
- 수용 기준 grep 전부 통과.
