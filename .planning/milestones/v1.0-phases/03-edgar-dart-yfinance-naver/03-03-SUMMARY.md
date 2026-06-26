---
phase: 03-edgar-dart-yfinance-naver
plan: 03
subsystem: io/fundamentals (US 수직 슬라이스)
tags: [edgar, yfinance, fundamentals, per-peg-gpm-opm, provenance, tdd]
requires:
  - "io/throttle.throttled_edgar (03-01)"
  - "io/cache.get_fund/put_fund (03-01)"
  - "io/market._SESSION (Phase 2)"
  - "io/market_kind.classify_market"
  - "config.load_env (EDGAR_USER_AGENT_EMAIL)"
  - "tests/fixtures/edgar_aapl_facts.py + yf_info_sample.py (03-02)"
provides:
  - "io/fundamentals.MetricCell/FundamentalsResult + fetch_fundamentals (US 라우팅 + PEG 산식 + provenance)"
  - "io/edgar_client.fetch_edgar_raw/fetch_edgar_cached (set_identity + throttle + 7d cache)"
  - "io/yf_fundamentals.fetch_yf_info (.info 폴백, _SESSION 재사용)"
affects:
  - "03-04 (KR 경로 — 같은 fetch_fundamentals 확장)"
  - "runner.py (fundamentals_fn 주입 통합 — 후속)"
  - "output/sheet_portfolio.py (R/S/T/U 셀 — 후속)"
tech-stack:
  added: ["edgartools 5.35.0 (from edgar import Company, set_identity)"]
  patterns: ["market.py module-singleton + throttle + cache-first", "runner.py dataclass 결과모델", "test_runner.py callable 주입"]
key-files:
  created:
    - "src/stocksig/io/fundamentals.py"
    - "src/stocksig/io/edgar_client.py"
    - "src/stocksig/io/yf_fundamentals.py"
    - "tests/test_fundamentals.py"
    - "tests/test_edgar_client.py"
    - "tests/test_yf_fundamentals.py"
  modified: []
decisions:
  - "eps_prior(US PEG 입력): edgartools 5.35.0 EntityFacts 에 전년 EPS TTM 확정 accessor 부재 → fetch_edgar_raw 는 eps_prior=None 반환, PEG 는 '전년 EPS 미존재' 사유로 안전 처리(향후 prior-EPS 경로 검증 시 보강)"
  - "fetch_fundamentals 에 edgar_fn/yf_fn 콜러블 주입 인자 추가 — 테스트 격리 + DI(기본값은 lazy import 한 실클라이언트)"
  - "fixture import 경로: pytest prepend 모드 기준 'from fixtures.X import' (tests 디렉터리가 sys.path 선두)"
metrics:
  duration: "약 25분"
  completed: "2026-06-04"
---

# Phase 3 Plan 03: US 펀더멘털 수직 슬라이스 Summary

EDGAR(edgartools 5.35.0 EntityFacts typed accessor) 1차 → 결손 지표만 yfinance.info 로 보완하는 미국 종목 PER/PEG/GPM/OPM 수직 슬라이스. per-metric provenance(EDGAR/yf 라벨) + PEG 4종 엣지케이스 한국어 사유 + 7일 캐시 + import-time set_identity(FUND-02).

## What Was Built

### Task 1 — fundamentals.py (commit 3590746)
- `MetricCell(value, source, note)` / `FundamentalsResult(per, peg, gpm, opm)` dataclass (runner.py 스타일).
- 순수 산식 헬퍼:
  - `_compute_per(last_close, eps_ttm)` — eps None/≤0 시 빈값+사유.
  - `_compute_peg(per, eps_ttm, eps_prior)` — 엣지케이스 4종(성장률≤0 / 0분모 / 전년없음 / PER없음) 각각 빈값 + 한국어 note.
  - `_compute_margin(numer, denom)` — GPM/OPM 공용, 분모 0/None·분자 None 가드.
- `fetch_fundamentals(ticker, market, last_close, edgar_fn=None, yf_fn=None)`:
  - US 분기: EDGAR 1차 산식 → 결손 *개별 지표만* yf 보완(1차 채운 지표 덮어쓰기 금지) → per-metric `source`("EDGAR"|"yf") + note.
  - KR 분기: 빈 결과 placeholder("KR 미구현 (03-04 예정)") — SCOPE 축소 아님, 03-04 가 같은 함수 확장.
  - 전 경로 try/except 흡수(D-disc-10: 펀더멘털 결손 ≠ 티커 실패) + 한국어 로그 `fund OK <t> (EDGAR)` / `(EDGAR→yf)`.
- 18 테스트 GREEN (`test_fallback_chain` 포함 — FUND-05).

### Task 2 — edgar_client.py + yf_fundamentals.py (commit 200ed2e)
- `edgar_client.py`: `from edgar import Company, set_identity`. import-time `_SET_IDENTITY_ARG=_resolve_identity()`(.env EDGAR_USER_AGENT_EMAIL 우선, 없으면 기본) → `set_identity(...)` 1회. `@throttled_edgar fetch_edgar_raw` — EntityFacts typed accessor(`get_ttm("EarningsPerShareDiluted")` / `get_ttm_revenue()` / `get_gross_profit()` / `get_operating_income()`, A1/A2) + `_quarter_label`(periods[-1] → "2026Q2", A7) None-safe. `fetch_edgar_cached(ticker, quarter_label)` cache-first(7d, "EDGAR|ticker|quarter").
- `yf_fundamentals.py`: `from stocksig.io.market import _SESSION`(신규 세션 금지) + `@throttled_yahoo`. `fetch_yf_info` — trailingPE/pegRatio→trailingPegRatio 폴백/grossMargins/operatingMargins None-safe `.get()`(A4).
- 13 테스트 GREEN (`test_set_identity` FUND-02, `test_fetch_edgar_raw_returns_keys` FUND-01, cache HIT call_count==1, 소스 단언).

## Verification

- `uv run pytest tests/test_fundamentals.py tests/test_edgar_client.py tests/test_yf_fundamentals.py -x` → **31 passed**.
- 전체 회귀 `uv run pytest` → **164 passed** (회귀 0건).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] fixture import 경로 정정**
- **Found during:** Task 2 RED.
- **Issue:** plan/fixture docstring 의 `from tests.fixtures.X import ...` 는 `tests` 패키지 미존재(`__init__.py` 없음, pythonpath=["src"])로 `ModuleNotFoundError`.
- **Fix:** pytest prepend import 모드 기준 `from fixtures.X import ...` 로 변경(tests 디렉터리가 sys.path 선두에 자동 추가됨). 검증 후 적용.
- **Files modified:** tests/test_edgar_client.py, tests/test_yf_fundamentals.py.
- **Commit:** 200ed2e.

### Scope/Design Notes (deviation 아님)

**eps_prior (US PEG 입력) — 의도된 limitation**
- edgartools 5.35.0 `EntityFacts` 에 전년 EPS TTM 의 확정 accessor 가 SPIKE-FINDINGS 에 명시되지 않음. `fetch_edgar_raw` 는 `eps_prior=None` 반환.
- 결과: US PEG 는 현재 EDGAR 단독으로는 "조회 실패: 전년 EPS 미존재" 사유로 빈 셀 → yf 폴백(`pegRatio`/`trailingPegRatio`)이 PEG 를 채움. per-metric 폴백 체인이 정확히 이 케이스를 처리(테스트 `test_fallback_chain` 의 GPM 폴백과 동형).
- 향후 prior-EPS EntityFacts 경로가 검증되면 `fetch_edgar_raw` 에 보강 가능(함수 시그니처 불변).

## Known Stubs

- KR 분기(`fetch_fundamentals` market != "US"): 빈 `FundamentalsResult` + note "KR 미구현 (03-04 예정)". plan 의 명시적 SCOPE(본 plan US 전용, 03-04 가 같은 함수 확장)에 따른 의도된 placeholder.

## Authentication Gates

- 없음. 모든 외부 호출(EDGAR `Company`, yfinance `Ticker`)은 테스트에서 mock 으로 차단. set_identity 는 import-time 1회 호출되나 인자 형식만 단언(실 SEC 호출 없음).

## Self-Check: PASSED

- 파일 존재: src/stocksig/io/fundamentals.py, edgar_client.py, yf_fundamentals.py, tests/test_fundamentals.py, test_edgar_client.py, test_yf_fundamentals.py — 전부 FOUND.
- 커밋 존재: 3590746 (Task 1), 200ed2e (Task 2) — 전부 FOUND.
- 테스트: 플랜 3파일 31 passed + 전체 164 passed.
