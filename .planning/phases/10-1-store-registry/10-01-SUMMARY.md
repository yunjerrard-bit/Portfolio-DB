---
phase: 10-1-store-registry
plan: 01
subsystem: io
tags: [fundamentals, store-registry, adapter, drift-prevention, FUND-11]
requires:
  - "metrics_engine.compute_matrix / price_ratio / compute_peg_cell / _calendar_quarter_offset (Phase 8)"
  - "fundamentals.FundamentalsResult / MetricCell / _empty_cell / _is_missing (보존 계약 D-04)"
  - "metrics_registry.REGISTRY (price_denominator 도출)"
provides:
  - "metrics_engine.inject_prices_for_quarter — 단일분기 가격 주입 공유 코어 (시트1·트렌드 공통, D-06)"
  - "metrics_engine._PRICE_DEPENDENT — 가격 의존 4종→주당 분모 단일 도출 상수"
  - "fundamentals_view.matrix_to_fundamentals — 최신열→FundamentalsResult 어댑터 (D-08)"
affects:
  - "history_render._inject_prices (비파괴 재배선 — 공유 코어 위임)"
  - "Plan 10-02/03 (main_run READ 단계가 어댑터·코어를 호출)"
tech-stack:
  added: []
  patterns:
    - "단일분기 코어 추출 → 다분기 루프가 코어 호출(드리프트 구조적 차단)"
    - "얇은 어댑터(import 재사용, 신규 dataclass·산식 0) → writer 계약 보존"
key-files:
  created:
    - "src/stocksig/io/fundamentals_view.py"
    - "tests/test_fundamentals_view.py"
  modified:
    - "src/stocksig/io/metrics_engine.py"
    - "src/stocksig/io/history_render.py"
    - "tests/test_metrics_engine.py"
    - "tests/test_history_render.py"
decisions:
  - "D-06 추출 경계 = 단일분기 코어(inject_prices_for_quarter). 트렌드 다분기 루프가 코어 호출, 시그니처·외부 동작 유지(비파괴)"
  - "_PRICE_DEPENDENT를 metrics_engine REGISTRY 단일 도출 → history_render import 재사용(사본 0)"
  - "어댑터는 가격 주입 미수행(L1) — 호출자가 compute_matrix→inject_prices_for_quarter→matrix_to_fundamentals 순서 강제"
  - "PEG.source = PER.source 승계(L5), '소스 · 최신분기' 라벨 합성(D-09), 결손 셀은 한국어 사유 보존(D-10)"
metrics:
  duration: ~27 min
  tasks: 2
  files: 6
  completed: 2026-06-23
---

# Phase 10 Plan 01: 시트1 펀더멘털 단일 원천 계산·변환 계층 Summary

`compute_matrix` 최신열과 단일분기 가격 주입을 시트1·트렌드가 동일 코드로 공유하게 만들어 두 산출물 값 드리프트를 구조적으로 차단하고, 매트릭스 최신열을 `FundamentalsResult`로 무변환 매핑하는 얇은 어댑터를 신설했다(신규 산식·dataclass 0).

## What Was Built

**Task 1 — `inject_prices_for_quarter` 단일분기 공유 코어 (D-06)**
- `metrics_engine.inject_prices_for_quarter(matrix, q, price, eps_map)` 추가 — 단일 분기에 가격 의존 4종(PER/PBR/PCR/PSR) `price_ratio` 주입 + PEG 3단 `compute_peg_cell` in-place. 신규 산식 0(기존 엔진 함수 재사용).
- `_PRICE_DEPENDENT`(가격 의존 4종 → 주당 분모)를 `metrics_engine`에서 REGISTRY로 단일 도출. `history_render`가 이를 import 재사용(중복 정의·드리프트 제거).
- `history_render._inject_prices`(다분기 루프)를 **비파괴 재배선** — 시그니처·외부 동작(matrix in-place, quarters/qmap/current/latest_q) 유지하고 본문 루프가 공유 코어만 호출하도록 치환. 기존 트렌드 통합 테스트 무손상.

**Task 2 — `matrix_to_fundamentals` 어댑터 + provenance 라벨 (D-08/D-09)**
- 신규 모듈 `src/stocksig/io/fundamentals_view.py`. `matrix_to_fundamentals(matrix, latest_q) -> FundamentalsResult` — PER/PEG/GPM/OPM 최신열 셀을 무변환 매핑(`FundamentalsResult`/`MetricCell`/`_empty_cell`/`_is_missing` import 재사용, 신규 dataclass·산식 0).
- provenance 라벨 합성 `_provenance_note` — 값 있는 셀 note = `"{source} · {latest_q}"`(예 "EDGAR · 2026Q1"), source 없는 결손 셀은 기존 한국어 사유 note 보존(D-10).
- **L5 LANDMINE 처리:** `compute_peg_cell`은 source=None을 반환하므로, PEG value가 있으면 `peg.source = per.source` 승계 후 라벨 합성.
- **L1 호출순서 강제:** 모듈 docstring에 `compute_matrix → inject_prices_for_quarter → matrix_to_fundamentals` 순서 명시(어기면 PER/PEG 빈 셀).
- **D-02 빈 DB:** `latest_q=None` 또는 빈 matrix → 4셀 value=None + "조회 실패: DB 분기 데이터 없음".

## Verification

| 항목 | 결과 |
|------|------|
| `test_metrics_engine.py` (inject 2종) | GREEN |
| `test_fundamentals_view.py` (어댑터 6종) | GREEN — 매핑·드리프트0·PEG승계·빈DB·가격parity·라벨합성 |
| `test_history_render.py` 비CLI 통합 11종 | GREEN (리팩터 회귀 0) |
| 전 스위트 (repo root on PYTHONPATH) | **384 passed, 0 failed** (baseline 375 + 신규 8 + collection 복구) |
| `git diff sheet_portfolio.py` | 빈 출력 (Core Value 색 신호 0줄 변경) |
| store 추출기 `fetch_edgar/dart_quarterly_raw` | 존치 확인 (L2 오삭제 방지) |

acceptance grep: `def inject_prices_for_quarter` 1건 · history_render `inject_prices_for_quarter` 호출 ≥1(직접 price_ratio/compute_peg_cell 호출 0) · `def matrix_to_fundamentals` 1건 · 신규 class/_compute_ 정의 0.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] test_history_render.py 모듈 collection 차단 import 버그 수정**
- **Found during:** Task 1 (history_render 리팩터 회귀 확인)
- **Issue:** `tests/test_history_render.py`가 `from tests.fixtures.history_fixtures import ...`를 사용 — pytest `pythonpath=["src"]` 환경에서 `ModuleNotFoundError: No module named 'tests'`로 **모듈 전체 collection 실패**. clean tree(565bb26 이전)에서도 동일 — 본 plan 리팩터와 무관한 선존 버그. 이 파일이 collect되지 않으면 플랜이 요구하는 "기존 history_render 통합 테스트 무손상" 회귀 검증 자체가 불가능.
- **Fix:** 레포 컨벤션(`from fixtures.` — 다른 모든 테스트 파일과 동일)에 맞춰 import 1줄 수정. collection 복구 후 13 통과.
- **Files modified:** tests/test_history_render.py
- **Commit:** ac39b75 (Task 1 GREEN에 포함)

### Out-of-scope (deferred, NOT fixed)

**test_history_render.py CLI 디스패치 3종 (`test_history_cli_dispatch`/`test_default_cli_dispatch`/`test_history_cli_db_empty_exit0`)**
- import 버그 수정으로 collection이 복구되며 드러난 **선존 환경/경로 아티팩트**. `importlib.import_module("main")`·`subprocess [..., "main.py", ...]`가 레포 루트가 sys.path에 없어 `ModuleNotFoundError: No module named 'main'`. 본 plan 변경 코드(metrics_engine/history_render/fundamentals_view)가 일으킨 회귀 아님.
- **증거:** `PYTHONPATH="<repo-root>;src" uv run pytest <3종>` → 3 passed. 전 스위트도 repo root on path에서 384 passed/0 failed.
- 상세·후속 권장: `.planning/phases/10-1-store-registry/deferred-items.md`.

## Threat Surface

신규 보안 surface 0 — 순수 내부 이관. T-10-01(provenance 라벨) 준수: `_provenance_note`는 `cell.source`(상수 라벨)·`latest_q`("YYYYQn")만 보간 — EDGAR UA·OPENDART_API_KEY 미참조(CR-01 보존). 신규 SQL·신규 패키지 0(T-10-SC slopcheck 대상 없음).

## Notes for Next Plan

- **Plan 10-02/03 READ 단계 계약:** `matrix = compute_matrix(sym)` → `latest_q = sorted(quarters)[-1]` → `inject_prices_for_quarter(matrix, latest_q, last_close, matrix["EPS_ttm"])` → `res.fundamentals = matrix_to_fundamentals(matrix, latest_q)`. 이 순서를 어기면 PER/PEG 빈 셀(L1).
- last_close는 시트1 runner 경로(`res.enriched_df.iloc[-1].get("Close")`)에서 꺼내야 트렌드 `current`와 동일(L4 — parity 테스트로 가드됨).

## Self-Check: PASSED

- 생성 파일 3종 모두 존재(fundamentals_view.py · test_fundamentals_view.py · 10-01-SUMMARY.md).
- 커밋 4건 모두 존재(565bb26 RED · ac39b75 GREEN · efbebf5 RED · 53bf344 GREEN).
