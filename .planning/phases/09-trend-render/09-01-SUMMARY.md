---
phase: 09-trend-render
plan: 01
subsystem: 트렌드 렌더 — 순수 계산 기반 + 네트워크 0 fixture
tags: [FUND-10, quarter-price, trend-color, fixtures, tdd, network-zero]
requires:
  - stocksig.io.market.fetch_ohlcv_cached
  - stocksig.io.fundamentals._is_missing
  - stocksig.io.fundamentals.MetricCell
  - stocksig.io.metrics_engine.compute_matrix
  - stocksig.io.metrics_engine._calendar_quarter_offset
provides:
  - stocksig.io.quarter_price.quarter_end_prices
  - stocksig.compute.trend_color.relative_bucket
  - stocksig.compute.trend_color.yoy_glyph
  - stocksig.compute.trend_color.LOWER_IS_BETTER
  - stocksig.compute.trend_color.HIGHER_IS_BETTER
  - tests.fixtures.history_fixtures.fetch_fn_stub
  - tests.fixtures.history_fixtures.build_ohlcv
  - tests.fixtures.history_fixtures.TICKER_INDUSTRY
affects:
  - Plan 09-02 (history_workbook / sheet writers — bucket·glyph·분기말종가 소비)
  - Plan 09-03 (history_render 오케스트레이션 — compute_matrix + price_ratio + 본 fixture 재사용)
tech-stack:
  added: []
  patterns:
    - "resample(\"QE\").last() 분기 경계 위임 (Don't Hand-Roll — 신규 분기 산술 0)"
    - "결손 게이트 _is_missing 재사용 (신규 정의 금지)"
    - "(분기열×산업) 2차원 모집단 상대 순위 + 표본 게이트 N=3"
    - "네트워크 0 테스트 (fetch_fn stub + fetch_ohlcv_cached monkeypatch)"
key-files:
  created:
    - src/stocksig/io/quarter_price.py
    - src/stocksig/compute/trend_color.py
    - tests/fixtures/history_fixtures.py
    - tests/test_quarter_price.py
    - tests/test_trend_color.py
  modified: []
decisions:
  - "동률(strict 분리 0) → 무색 중립 (RESEARCH A4)"
  - "분위 판정 = 유효 peer 대비 strict below/above 비율 3분위 (lower/upper_frac ≤ 1/3)"
  - "quarter_price 빈 시계열 → ({}, None), note 부여는 호출자 책임"
metrics:
  duration: ~12 min
  completed: 2026-06-22
  tasks: 3
  files: 5
---

# Phase 09 Plan 01: 트렌드 렌더 순수 계산 기반 + 네트워크 0 fixture Summary

분기말 종가/현재가 분리(`quarter_end_prices`, D-09)와 (분기열×산업) 상대색 3-bucket + 전년동기 YoY 글리프(`trend_color`, D-05/06/07/08)를 신규 산식·외부 호출 0으로 구현하고, 다종목·다산업 결정적 fixture(`fetch_fn` stub + 합성 OHLCV builder)로 두 모듈을 네트워크 0으로 검증했다 — 다운스트림 Plan 02/03 소비 계약 확정.

## What Was Built

### Task 1 — `quarter_price.quarter_end_prices` (D-09 / SC4)
- `fetch_ohlcv_cached(ticker)` 소비(캐시 HIT 시 외부 호출 0) → `Close.dropna().resample("QE").last()`로 분기말 마지막 거래일 종가.
- 키 = `index.to_period("Q").astype(str)` → 엔진 `_calendar_quarter_offset` 출력("YYYYQn")과 정확 일치(Pitfall 4).
- `current_price = float(close.iloc[-1])` (시트1 동일 진입점 → 드리프트 0).
- 빈 시계열 가드 `({}, None)`. 신규 분기 경계 산술 0(resample 위임).
- 커밋 8e19163.

### Task 2 — `trend_color.relative_bucket` + `yoy_glyph` (D-05/06/07/08)
- `LOWER_IS_BETTER={PER,PEG,PBR,PCR,PSR}` / `HIGHER_IS_BETTER={ROE,ROA,GPM,OPM}` 방향 상수(D-06).
- `relative_bucket(metric, value, peer_values, industry)`: `industry==""` 또는 유효 peer(`_is_missing` 제외) < 3 → "무색"(D-07 표본 게이트). value 결손/동률 → "무색". 유효 peer 대비 strict below/above 비율로 3분위 → 방향별 초록/빨강.
- `yoy_glyph(cell_q, cell_q_prior)`: 둘 중 하나라도 None 또는 value 결손 → ""(전년 결손 생략, D-08). `>`→" ▲", `<`→" ▼", `==`→"".
- 결손 게이트 `_is_missing` 재사용(신규 정의 0), 순수 함수·네트워크 0. 색 hex 미정의(Plan 02가 color_rules 상수 import).
- 커밋 c152666.

### Task 3 — 다종목·다산업 네트워크 0 fixture
- `tests/fixtures/history_fixtures.py`:
  - `fetch_fn_stub(ticker)`: US(AAPL/tech, EDGAR)·KR(005930.KS/semiconductors, DART) 5분기 7-tuple raw 시계열 → `compute_matrix(ticker, fetch_fn=stub)` 주입. 미등록 ticker → 빈 리스트.
  - `build_ohlcv(...)`: `fetch_ohlcv_cached` monkeypatch용 합성 OHLCV(영업일 DatetimeIndex, 분기별 단조 증가 Close).
  - `TICKER_INDUSTRY`: 종목→산업 매핑.
- Task 1·2 테스트를 fixture 사용으로 리팩터(inline 합성 제거)·다종목 YoY 통합 단언 추가.
- 검증: `compute_matrix("AAPL", fetch_fn=stub)`가 13지표 매트릭스 반환(GPM/ROE/EPS_ttm 등 KeyError 0, provenance EDGAR/DART 정확).
- 커밋 00b1acf.

## Verification

- `tests/test_quarter_price.py` + `tests/test_trend_color.py` → 13 passed.
- 전 스위트 **354 passed, 4 warnings** (baseline 341 + 신규 13, 회귀 0). edgar UserWarning은 기존 smoke 테스트 잔존(본 플랜 무관).
- `resample("QE")` 1건 사용·`resample("Q")` 0건.
- `trend_color.py` `_is_missing` 재사용 ≥1·`def _is_missing` 0건. 신규 `MetricCell`/`_compute_peg` 정의 0.
- 시트1 (`sheet_portfolio.py`·`color_rules.py` 로직·`portfolio_*.xlsx`) 미접근 — Core Value 색 신호 불변.

## Deviations from Plan

None — 플랜이 명시한 RED→GREEN·fixture 통합 순서대로 실행. TDD RED는 신규 모듈 부재(ImportError)로 확인 후 GREEN 구현, 신규 파일이라 RED/GREEN을 단일 커밋으로 통합(Task 1·2).

## Known Stubs

없음. `fetch_fn_stub`/`build_ohlcv`는 테스트 전용 결정적 fixture(합성 데이터, T-09-02 mitigate)로 의도된 산출물이며, 프로덕션 경로는 Plan 03(`history_render`)이 실제 `compute_matrix`/`fetch_ohlcv_cached`를 직접 호출한다.

## Notes for Downstream (Plan 02/03)

- 분기말 종가는 raw에서 못 꺼냄 → `quarter_end_prices(ticker)`로 별도 조달, 가격 의존 4종은 `price_ratio(matrix[denom][q], price)` 주입.
- 셀 렌더 = `ws.write_string(row, col, f"{v:.2f}{yoy_glyph(cur, prior)}", fmt_<bucket>)` — bucket Format은 history_workbook이 color_rules 상수로 베이킹.
- relative_bucket 모집단은 (분기 열 × 산업) 2차원 — 전 종목·전 분기 한 모집단 금지(Pitfall 3).
- 본 fixture(`fetch_fn_stub`/`build_ohlcv`/`TICKER_INDUSTRY`) 재사용으로 Plan 02/03 테스트 네트워크 0 유지.

## Self-Check: PASSED

- FOUND: src/stocksig/io/quarter_price.py
- FOUND: src/stocksig/compute/trend_color.py
- FOUND: tests/fixtures/history_fixtures.py
- FOUND: tests/test_quarter_price.py
- FOUND: tests/test_trend_color.py
- FOUND commit: 8e19163 (quarter_price)
- FOUND commit: c152666 (trend_color)
- FOUND commit: 00b1acf (fixtures)
