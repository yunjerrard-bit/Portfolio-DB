---
phase: quick-260605-kfy
plan: 01
subsystem: io/market
tags: [bugfix, ohlcv, nan-trimming, cache, tdd]
requires:
  - src/stocksig/io/market.py:fetch_ohlcv
provides:
  - "fetch_ohlcv가 Close=NaN 후행봉을 제거한 깨끗한 프레임만 반환·캐싱"
affects:
  - src/stocksig/io/cache.py (put_ohlcv가 깨끗한 프레임 저장 — 무변경, 자동 전파)
  - src/stocksig/runner.py (D-06 가드가 트리밍된 len 사용 — 무변경, 자동 전파)
  - 시트1 최신종가/전일등락률/DIFF EMA/거래량/(일)(주) 지표
tech-stack:
  added: []
  patterns:
    - "데이터 진입 지점(fetch_ohlcv)에서 미정산봉 차단 — 캐시 저장 이전"
    - "dropna(subset=[\"Close\"])만 사용 (High/Low/Open 보존 → EWM carry-forward 경로 무손상)"
key-files:
  created: []
  modified:
    - src/stocksig/io/market.py
    - tests/test_market.py
decisions:
  - "subset=[\"Close\"]만 트리밍 — 내부 NaN-close는 일봉에 사실상 없고, Close NaN만이 실제 문제"
  - "트리밍 후 빈 df → ValueError fail-fast (빈-df 가드와 동일 취지)"
metrics:
  duration: "~6분"
  completed: "2026-06-05"
  tasks: 2
  files: 2
---

# Quick 260605-kfy: OHLCV 후행 NaN-Close 봉 트리밍 버그 수정 Summary

Yahoo Finance가 최신 일봉의 Close를 NaN(Volume만)으로 내려줄 때 `iloc[-1]`이 빈 미정산봉을 가리켜 시트1 최신값이 빈칸이 되던 버그를, `fetch_ohlcv`에 `dropna(subset=["Close"])` 트리밍을 캐시 저장 이전에 삽입해 차단했다.

## What Was Built

**Task 1 (GREEN, 23b01a7):** `src/stocksig/io/market.py:fetch_ohlcv`
- 빈-df 가드 직후·성공 로그 직전에 트리밍 삽입:
  - `original_rows = len(df)` 보관 → `df = df.dropna(subset=["Close"])`
  - `removed > 0`이면 한국어 info 로그 `"%s | 미정산/NaN 최신봉 %d개 제외"`
  - 트리밍 후 `df.empty`면 `ValueError(f"{ticker} | Close 유효 행이 없습니다 (전 봉 NaN)")` fail-fast
- 성공 로그는 트리밍 이후 `len(df)` 사용 (위치만 트리밍 아래로 보장).
- `fetch_ohlcv_cached` / `cache.put_ohlcv` / `runner.py` 무변경 — 트리밍된 df가 자동 전파.

**Task 2 (RED, d25973d):** `tests/test_market.py` (+ `import numpy as np`)
- `test_trailing_nan_close_trimmed` — 마지막 1행 Close/High/Low=NaN, Volume 유지 → `iloc[-1]["Close"]` 비-NaN, 길이 원본-1
- `test_trailing_two_nan_close_trimmed` — 2행 NaN → 길이 원본-2
- `test_clean_ohlcv_row_count_unchanged` — 정상 df 행수 불변 (회귀 가드)
- `test_trim_logs_korean_info` — caplog에 "미정산/NaN 최신봉" substring
- `test_all_nan_close_raises_value_error` — 전 봉 NaN → ValueError

## TDD Gate Compliance

- RED: `d25973d` test(...) — 신규 테스트가 트리밍 미구현 상태에서 실패 확인 (`test_trailing_nan_close_trimmed` assert False on NaN).
- GREEN: `23b01a7` fix(...) — 구현 후 `tests/test_market.py` 14 passed.
- REFACTOR: 불필요 (구현 단순, 정리 대상 없음).

게이트 순서 정상 (test → fix).

## Verification

- `uv run pytest tests/test_market.py -x -q` → **14 passed** (기존 9 + 신규 5).
- `uv run pytest -q` → **200 passed** in 246.65s (직전 195 + 신규 5). 회귀 0.
- 코드 리뷰: 트리밍이 빈-df 가드 직후·성공 로그 직전(캐시 저장 이전), `subset=["Close"]`만 사용, `fetch_ohlcv_cached`/`cache.py`/`runner.py` 무변경 확인.

## 실행 단계 (코드 아님)

- 오염된 24h OHLCV 캐시 무효화: `rm -rf .cache/ohlcv` 실행 완료 (NaN 봉이 들어간 캐시 항목 제거). `.cache/fundamentals`는 미접촉. `.cache/`는 .gitignore 대상이라 커밋 영향 없음. 다음 실행에서 `fetch_ohlcv_cached`가 깨끗한 프레임을 새로 받아 저장한다.

## Deviations from Plan

플랜은 Task 1(구현) → Task 2(테스트) 순이나, 두 task 모두 `tdd="true"`라 TDD 게이트(RED before GREEN) 준수를 위해 **테스트를 먼저 작성(RED 커밋 d25973d) → 구현(GREEN 커밋 23b01a7)** 순으로 실행했다. 산출물·동작은 플랜 명세와 동일. 그 외 deviation 없음 — 신규 의존성 없음(numpy는 conftest에서 기 사용, pandas만 사용).

## Self-Check: PASSED

- `src/stocksig/io/market.py` 수정 존재 (dropna 트리밍) — FOUND
- `tests/test_market.py` 신규 5 테스트 — FOUND (14 passed)
- 커밋 d25973d (RED) — FOUND
- 커밋 23b01a7 (GREEN) — FOUND
