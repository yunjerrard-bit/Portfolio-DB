---
phase: 09-trend-render
verified: 2026-06-22T09:30:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/9
  gaps_closed:
    - "동종 산업군 표본<3 또는 산업='' 셀은 상대색이 무색이다 (D-07) — commit fcd58ad: `<=`→`<` 경계 수정"
    - "밸류에이션(PER/PEG/PBR/PCR/PSR)은 낮을수록 초록·수익성(ROE/ROA/GPM/OPM)은 높을수록 초록 (D-06) — 동일 루트 CR-01 해소"
  gaps_remaining: []
  regressions: []
human_verification: []
---

# Phase 09: 트렌드 렌더 재검증 보고서

**Phase Goal:** 사용자가 `fundamentals_history.xlsx`(기존 `portfolio_YYYYMMDD.xlsx`와 별도 파일)를 열어 펀더멘털의 분기 트렌드, 원천 데이터, 최신 스냅샷을 육안으로 확인할 수 있다. 기존 시트1 색 신호(Core Value)는 전혀 건드리지 않는다.
**Verified:** 2026-06-22T09:30:00Z
**Status:** passed
**Re-verification:** Yes — CR-01 갭 클로저 후 재검증

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 분기말 종가가 OHLCV에서 분기키(YYYYQn)별로 조달되고 최신=현재가가 분리된다 (D-09/SC4) | VERIFIED | `src/stocksig/io/quarter_price.py`: `resample("QE").last()` + `to_period("Q").astype(str)`. 테스트 `tests/test_quarter_price.py` 4건 GREEN. |
| 2 | 동종 산업군 표본<3 또는 산업='' 셀은 상대색이 무색이다 (D-07) | VERIFIED | commit fcd58ad — `lower_frac < 1.0/3.0`, `upper_frac < 1.0/3.0` (strict). 실증: `relative_bucket("PER", 20.0, [10.0, 20.0, 30.0], "tech")` == `"무색"`. `test_median_of_three_is_neutral` GREEN (12/12). |
| 3 | 밸류에이션(PER/PEG/PBR/PCR/PSR)은 낮을수록 초록·수익성(ROE/ROA/GPM/OPM)은 높을수록 초록 (D-06) | VERIFIED | CR-01 동일 루트 해소. `relative_bucket("PER", 5.0, [5.0,20.0,30.0,40.0], "tech")` == `"초록"`. `relative_bucket("ROE", 40.0, [5.0,20.0,30.0,40.0], "tech")` == `"초록"`. 방향 상수 LOWER_IS_BETTER / HIGHER_IS_BETTER 모두 정상 동작. |
| 4 | 전년동기(4분기 전) 대비 ↑/↓ 화살표가 산출되고 전년 결손 시 생략된다 (D-08) | VERIFIED | `yoy_glyph` 구현 확인. `test_yoy_glyph` + `test_yoy_glyph_prior_missing` GREEN. |
| 5 | 네트워크 0 fixture(compute_matrix fetch_fn stub + OHLCV monkeypatch)로 모든 테스트가 외부 호출 없이 돈다 | VERIFIED | `tests/fixtures/history_fixtures.py`: `fetch_fn_stub` + `build_ohlcv` 존재. 전 Phase 09 테스트 monkeypatch 기반. 전 스위트 376 passed (외부 호출 0). |
| 6 | 지표별 시트가 식별 5열(티커·기업명·시장·티어·산업) + 분기 열(최신 왼쪽)로 그려진다 (D-01/02/SC2) | VERIFIED | `sheet_metric_matrix.py` `_IDENT_COLUMNS` 5열 + `display_quarters` reversed. `test_matrix_layout_latest_left` GREEN. |
| 7 | history 서브커맨드 실행 시 fundamentals_history_YYYYMMDD.xlsx가 DB에서 별도 파일로 렌더된다 (D-14/D-15/SC1) | VERIFIED | `main.py` `add_subparsers` + `run_history` 늦은 import. `test_separate_file_sheet1_untouched` + `test_history_cli_help` GREEN. |
| 8 | [원천] 시트가 raw long 7-tuple, [최신 스냅샷] 시트가 종목 1행×전 지표 최신값 (D-13/SC3) | VERIFIED | `sheet_raw.py` + `sheet_snapshot.py` 존재 및 wired. `test_raw_and_snapshot_sheets` GREEN. |
| 9 | 기존 portfolio 흐름·시트1 색 신호는 회귀 없이 동작 (Core Value 불변) | VERIFIED | `git diff 4b6a3f7..HEAD -- sheet_portfolio.py color_rules.py writer.py main_run.py` → 변경 0줄. 전 스위트 **376 passed** (회귀 0). |

**Score:** 9/9 truths verified

---

## Re-verification: Gap Closure 상세

### CR-01 수정 검증

**수정 커밋:** `fcd58ad` (2026-06-22T17:31:22+09:00)

**변경 내용 (2줄):**
```
- if lower_frac <= 1.0 / 3.0:
+ if lower_frac < 1.0 / 3.0:
- elif upper_frac <= 1.0 / 3.0:
+ elif upper_frac < 1.0 / 3.0:
```

`upper_frac` 분기도 동시에 `<`로 수정됨 — 하위 경계와 동일한 근거(median-of-3에서 `upper_frac == 1/3`도 동일하게 발생)로 올바른 수정이다.

**실증 검증 결과:**

| 케이스 | 호출 | 이전(버그) | 현재 | 기대치 |
|--------|------|-----------|------|--------|
| median-of-3 PER | `relative_bucket("PER", 20.0, [10.0,20.0,30.0], "tech")` | 초록 | 무색 | 무색 |
| median-of-3 ROE | `relative_bucket("ROE", 20.0, [10.0,20.0,30.0], "tech")` | 빨강 | 무색 | 무색 |
| 최저-of-4 PER | `relative_bucket("PER", 5.0, [5.0,20.0,30.0,40.0], "tech")` | 초록 | 초록 | 초록 |
| 최고-of-4 ROE | `relative_bucket("ROE", 40.0, [5.0,20.0,30.0,40.0], "tech")` | 초록 | 초록 | 초록 |

**회귀 테스트:** `a2834ce` — `test_median_of_three_is_neutral` 추가 (PER + ROE 각 1건, 12번째 테스트)

---

## Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `src/stocksig/io/quarter_price.py` | `quarter_end_prices(ticker) -> ({YYYYQn: close}, current_price)` | VERIFIED | 존재, substantive, wired to `fetch_ohlcv_cached`. `resample("QE")` 사용 확인. |
| `src/stocksig/compute/trend_color.py` | `relative_bucket(metric, value, peer_values, industry) + yoy_glyph(cell_q, cell_q_prior)` | VERIFIED | CR-01 수정 완료. L56/L58 strict `<` 경계. 12건 테스트 GREEN. |
| `tests/fixtures/history_fixtures.py` | 다종목·다산업 raw_quarters stub + 합성 OHLCV builder | VERIFIED | `fetch_fn_stub` + `build_ohlcv` + `TICKER_INDUSTRY` 존재. |
| `tests/test_quarter_price.py` | 분기말 종가·현재가 단언 | VERIFIED | 존재, 4건 GREEN. |
| `tests/test_trend_color.py` | 상대색 방향/표본 게이트/YoY 글리프 + median-of-3 단언 | VERIFIED | 12건 GREEN (신규: `test_median_of_three_is_neutral`). |
| `src/stocksig/output/history_workbook.py` | `make_history_workbook(path) -> (Workbook, formats)` | VERIFIED | 존재, `constant_memory` 파라미터 포함. green/red/plain/header Format. |
| `src/stocksig/output/sheet_metric_matrix.py` | `write_metric_sheet(wb, ws, metric, rows, display_quarters, formats, peer_lookup, prior_lookup)` | VERIFIED | 존재, `peer_lookup`/`prior_lookup` 주입 인자 있음. freeze_panes(0,1) 확인. |
| `src/stocksig/output/sheet_raw.py` | [원천] long 시트 writer | VERIFIED | 존재, 7-tuple 헤더 한국어, `_is_missing` 재사용. |
| `src/stocksig/output/sheet_snapshot.py` | [최신 스냅샷] 종목 1행×지표 writer | VERIFIED | 존재, 9지표 최신 셀 재사용, 결손 "-" + 코멘트. |
| `src/stocksig/io/history_render.py` | `run_history(tickers_path, output_dir) -> Path\|None` | VERIFIED | 존재, DB 미적재 게이트, 종목 정렬, 가격 주입, 9시트 + 원천 + 스냅샷 배선. |
| `main.py` | `add_subparsers` history 서브커맨드 | VERIFIED | `sub = parser.add_subparsers(dest="cmd")` + `p_hist`. 하위호환 확인. |
| `tests/test_history_render.py` | SC1~4·D-09/10/11·시트1 불변 통합 단언 | VERIFIED | 14건 GREEN. |

---

## Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `quarter_price.py` | `stocksig.io.market.fetch_ohlcv_cached` | `import + resample("QE").last()` | WIRED | L18 import 확인, `resample("QE")` 사용 확인 |
| `trend_color.py` | `stocksig.io.fundamentals._is_missing` | 결손 게이트 재사용 | WIRED | L17 `from stocksig.io.fundamentals import MetricCell, _is_missing`. |
| `history_workbook.py` | `stocksig.compute.color_rules (GREEN_100/GREEN_900/RED_100/RED_900)` | `from stocksig.compute.color_rules import` | WIRED | L34-39 import 확인. |
| `sheet_metric_matrix.py` | `stocksig.compute.trend_color (relative_bucket/yoy_glyph)` | 셀 색 bucket + 화살표 결합 | WIRED | L21 import 확인. L123 `relative_bucket`, L128 `yoy_glyph` 호출. CR-01 수정 완료로 출력 정확도 복구. |
| `sheet_metric_matrix.py` | `stocksig.io.fundamentals._is_missing` | 결손 '-' 게이트 | WIRED | L22 import 확인. |
| `history_render.py` | `stocksig.io.metrics_engine (compute_matrix/price_ratio/compute_peg_cell)` | 지표 매트릭스 소비 + 가격 주입 | WIRED | L27-32 import, L135 compute_matrix, L84/94 price_ratio/compute_peg_cell 호출 확인. |
| `history_render.py` | `stocksig.io.quarter_price.quarter_end_prices` | 분기말 종가 + 현재가 주입 (D-09) | WIRED | L108 import, L136 호출 확인. |
| `main.py` | `stocksig.io.history_render.run_history` | history 서브커맨드 늦은 import | WIRED | L76-77 조건부 import + L79 호출 확인. |
| `history_render.py` | `main_run` | D-15 분리 — 참조 금지 | NOT WIRED (정상) | `grep main_run history_render.py` = 0건. |

---

## Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `sheet_metric_matrix.py` | `bucket` (상대색 결과) | `relative_bucket(metric, value, peer_values, industry)` | CR-01 수정으로 median-of-3 오분류 해소 | FLOWING |
| `history_render.py` | `per_ticker[sym]` | `compute_matrix(sym)` → DB stub(테스트)/실 DB(런타임) | 테스트: fixture stub, 런타임: fetch_raw_quarters→DB | FLOWING |
| `history_render.py` | `qmap, current` | `quarter_end_prices(sym)` | 테스트: build_ohlcv monkeypatch, 런타임: fetch_ohlcv_cached | FLOWING |

---

## Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| median-of-3 PER은 무색이어야 함 | `relative_bucket("PER", 20.0, [10.0, 20.0, 30.0], "tech")` | "무색" | PASS |
| median-of-3 ROE는 무색이어야 함 | `relative_bucket("ROE", 20.0, [10.0, 20.0, 30.0], "tech")` | "무색" | PASS |
| 최저-of-4 PER은 초록이어야 함 | `relative_bucket("PER", 5.0, [5.0, 20.0, 30.0, 40.0], "tech")` | "초록" | PASS |
| 최고-of-4 ROE는 초록이어야 함 | `relative_bucket("ROE", 40.0, [5.0, 20.0, 30.0, 40.0], "tech")` | "초록" | PASS |
| history 서브커맨드 help | `python main.py history --help` → returncode 0 | 테스트 GREEN | PASS |
| DB 미적재 시 안내 후 None 반환 | `count_rows==0 monkeypatch → run_history returns None` | 테스트 GREEN | PASS |
| 전체 테스트 스위트 | `uv run python -m pytest --tb=no -q` | 376 passed, 0 failed (419s) | PASS |

---

## Probe Execution

해당 없음 — 이 페이즈에 `scripts/*/tests/probe-*.sh` 형태의 프로브가 존재하지 않는다.

---

## Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| FUND-10 | 09-01, 09-02, 09-03 | 사용자가 `fundamentals_history.xlsx`를 열어 분기 트렌드·원천·스냅샷 확인 | SATISFIED | 파일 생성·시트 구조·원천·스냅샷 모두 구현. 트렌드 매트릭스 상대색 정확도(CR-01) 수정 완료. 9/9 truths VERIFIED. |

---

## Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `src/stocksig/io/history_render.py` | 145-149 | `except Exception` + `type(exc).__name__`만 로깅 (WR-02) | WARNING | 종목 실패 시 원인 없이 행이 누락됨. Phase 09 범위 내 수용. |
| `src/stocksig/io/history_render.py` | 137-141 | `quarters` 계산이 `_inject_prices` 전에 수행됨 (WR-03) | WARNING | `latest_q` 선택이 가격 의존 지표 주입 전 상태에 의존 — 분기 비대칭 시 잠재 불일치. Phase 09 범위 내 수용. |
| `src/stocksig/output/sheet_metric_matrix.py` | 124 | `_bucket_formats` 첫 번째 반환값(숫자 Format) 미사용 (IN-01) | INFO | dead code — 향후 numeric 셀 모드 추가 시 혼동 가능. |

이전 BLOCKER(`trend_color.py` L56/L58 `<=` 경계)는 commit `fcd58ad`에서 제거됨.

---

## Human Verification Required

없음

---

## Gaps Summary

없음. Phase 09의 단일 블로커(CR-01)가 해소되어 모든 9개 진실이 VERIFIED 상태로 전환됐다.

**CR-01 해소 경로:**
- commit `a2834ce`: RED 회귀 테스트 `test_median_of_three_is_neutral` 추가 (PER + ROE 각 1건)
- commit `fcd58ad`: `trend_color.py` L56/L58 `<=` → `<` strict 경계 수정
- 실증: `relative_bucket("PER", 20.0, [10.0, 20.0, 30.0], "tech")` == `"무색"` 확인
- 회귀 없음: 전 스위트 376 passed (이전 375 + 신규 1건)

---

_Verified: 2026-06-22T09:30:00Z_
_Verifier: Claude (gsd-verifier)_
