---
phase: 08-registry
plan: 04
subsystem: api
tags: [metrics, peg, provenance, sqlite, fundamentals, registry]

# Dependency graph
requires:
  - phase: 08-03
    provides: compute_matrix·price_ratio·compute_cell·_normalize_quarters 엔진 코어
  - phase: 08-02
    provides: REGISTRY 9종 MetricDef + MetricType(DERIVED=PEG)
  - phase: 08-01
    provides: fetch_raw_quarters store 헬퍼 + raw_facts PK(ticker,source,quarter,field)
provides:
  - "compute_peg_cell — PEG 2단계 공개 API(price_ratio 대칭). _compute_peg 실제 호출 경로"
  - "compute_matrix docstring에 Phase 9/10 PEG 소비 계약 3단 박제"
  - "fetch_raw_quarters 결정적 source 우선순위 ORDER BY(EDGAR→DART→yf, WR-01)"
affects: [09-render, 10-sheet1, fundamentals_history]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "PEG 2단계 공개 API(compute_peg_cell) — PER price_ratio와 대칭, 가격 비결합(D-07)"
    - "store SQL ORDER BY CASE source 우선순위 + 소비측 마지막-행-우선 = 결정적 멀티소스 선택"

key-files:
  created: []
  modified:
    - src/stocksig/io/metrics_engine.py
    - src/stocksig/io/fundamentals_store.py
    - tests/test_metrics_engine.py

key-decisions:
  - "옵션 B 채택 — compute_peg_cell 공개 래퍼 + docstring 소비 계약(compute_matrix 내부 PEG 후처리 아님). PER 2단계 계약과 일관, D-07 가격 비결합 유지"
  - "PEG sanity bounds(0~10)는 compute_peg_cell에서 _apply_sanity 재사용으로 적용 — 범위 밖 빈값+사유"
  - "source 우선순위 ORDER BY 방향=DESC — _normalize_quarters 마지막-행-우선이므로 EDGAR가 정렬상 마지막에 와야 이김. 소비측 무변경"

patterns-established:
  - "2차 파생 지표(가격 의존)는 공개 cell 래퍼 + compute_matrix docstring 호출 계약으로 노출 — 엔진 내부 후처리 미사용(D-07 비결합)"
  - "멀티소스 결정성 = store ORDER BY CASE 우선순위(DESC) + 소비측 마지막-행-우선 단일 모델"

requirements-completed: [FUND-09]

# Metrics
duration: ~18min
completed: 2026-06-22
---

# Phase 8 Plan 4: PEG 계산 경로 + 멀티소스 결정성 (gap closure) Summary

**compute_peg_cell 2단계 공개 API로 PEG가 _compute_peg를 실제 호출해 산출되고(검증 진실 #8·#9 블로커 해소), fetch_raw_quarters의 결정적 source 우선순위(EDGAR→DART→yf)로 멀티소스 비결정성 제거(WR-01)**

## Performance

- **Duration:** ~18 min
- **Tasks:** 2 (Task 1 TDD: RED→GREEN)
- **Files modified:** 3
- **전 스위트:** 341 passed (baseline 335 + 신규 6) — 회귀 0

## Accomplishments

- **PEG 블로커 해소(진실 #8·#9):** `compute_peg_cell(per_value, eps_ttm, eps_prior) -> MetricCell` 공개 2단계 API 추가. 본문이 `fundamentals._compute_peg`를 **실제 호출**(재수출만이 아님) + sanity bounds(0~10) 적용. PEG value가 더 이상 무조건 None이 아님.
- **Phase 9/10 소비 계약 박제:** `compute_matrix` docstring에 PEG 산출 3단(① price_ratio로 PER → ② matrix["EPS_ttm"] 현재·4분기전(`_calendar_quarter_offset(q,-4)`) value 추출 → ③ compute_peg_cell 호출) + 코드 예시 명시.
- **IN-01 정리:** `__all__`에서 미사용 재수출 `_compute_peg` 제거, `compute_peg_cell` 추가(`_compute_peg`는 모듈 내부 호출용 import 유지).
- **WR-01 결정성(진실 외 안정성):** `fetch_raw_quarters` ORDER BY에 `CASE source ... DESC` 2차 정렬키 추가 — 동일 (quarter, field) 멀티소스 시 EDGAR가 항상 결정적으로 선택. provenance 오염·수치 드리프트 차단.
- **결함 은닉 제거:** 기존 L181 `"PEG" in matrix` 키-존재-만 단언을 `compute_peg_cell(20.0, 12.0, 10.0).value == approx(1.0)` value 단언으로 강화.

## Task Commits

1. **Task 1 RED: PEG value 단언 테스트 4종 + L181 강화** - `4b6a3f7` (test)
2. **Task 1 GREEN: compute_peg_cell 2단계 공개 API + _compute_peg 호출 경로** - `223cdc8` (feat)
3. **Task 2: fetch_raw_quarters 결정적 source 우선순위 ORDER BY** - `1b626ba` (feat)

_Task 1은 TDD — RED(테스트 먼저 실패)→GREEN(구현) 분리 커밋. REFACTOR 불필요._

## Files Created/Modified

- `src/stocksig/io/metrics_engine.py` — `compute_peg_cell` 공개 래퍼 추가(`_compute_peg` 실제 호출 + sanity bounds), `compute_matrix` docstring에 Phase 9/10 PEG 소비 계약 3단·예시, `__all__` 정리(`_compute_peg`→`compute_peg_cell`), `compute_cell` DERIVED 분기 사유 갱신.
- `src/stocksig/io/fundamentals_store.py` — `fetch_raw_quarters` ORDER BY에 `CASE source WHEN 'EDGAR' THEN 0 WHEN 'DART' THEN 1 WHEN 'yf' THEN 2 ELSE 3 END DESC` 2차 정렬키 추가(?-바인딩·get_store() 재사용 유지).
- `tests/test_metrics_engine.py` — PEG value 단언 4종(value·엣지·end-to-end·sanity) + L181 강화 + 멀티소스 결정성 단언 2종(EDGAR 우선 반복 동일·DART>yf).

## 필수 기록 (Phase 9/10 직접 입력)

### compute_peg_cell 시그니처·위임
```python
def compute_peg_cell(
    per_value: float | None,   # price_ratio(matrix["EPS_ttm"][q], price).value (가격 주입 후 PER)
    eps_ttm: float | None,     # matrix["EPS_ttm"][q].value (현재 분기 per-share EPS, 최근 TTM)
    eps_prior: float | None,   # matrix["EPS_ttm"][q-4].value (_calendar_quarter_offset(q,-4))
) -> MetricCell
```
- 본문: `cell = _compute_peg(per_value, eps_ttm, eps_prior)` → value 결손이면 그대로 반환, 아니면 `_apply_sanity("PEG", value)` 적용(범위 밖=빈값+사유).
- 산식·엣지 4종(PER 없음/전년 EPS 미존재/전년 EPS 0/성장률 ≤ 0)은 fundamentals._compute_peg에 위임(신규 산식 작성 없음).
- provenance: per_value만 받으므로 source=None(fundamentals와 동일). 호출자가 PER 셀 source 보존 시 별도 주입.

### Phase 9/10 PEG 소비 계약 (호출 3단)
```python
matrix = compute_matrix("AAPL")
per = price_ratio(matrix["EPS_ttm"]["2026Q1"], price=48.0)        # ① PER 확보
qp  = _calendar_quarter_offset("2026Q1", -4)                     # ② "2025Q1"
peg = compute_peg_cell(                                          # ③ PEG 산출
    per.value,
    matrix["EPS_ttm"]["2026Q1"].value,
    matrix["EPS_ttm"][qp].value,
)
```

### sanity bounds
- PEG: 0~10 (`_SANITY_BOUNDS`, compute_peg_cell에서 `_apply_sanity` 재사용). 범위 밖 → value None + "sanity 범위 밖(0.0~10.0): ..." 사유.

### fetch_raw_quarters source 우선순위 ORDER BY 최종 형태
```sql
SELECT quarter, source, field, value, period_type, reprt_code, unit
FROM raw_facts WHERE ticker=?
ORDER BY quarter,
  CASE source WHEN 'EDGAR' THEN 0 WHEN 'DART' THEN 1 WHEN 'yf' THEN 2 ELSE 3 END
  DESC
```
- 방향 DESC 이유: 소비측 `_normalize_quarters`가 마지막-행-우선 덮어쓰기 → 우선순위 높은 EDGAR가 정렬상 마지막에 와야 이김. 소비측 코드 무변경.

### 전 스위트 회귀 결과
- **341 passed, 0 failed** (baseline 335 + 신규 6 = 4 PEG + 2 source priority). 시트1 회귀(test_sheet_portfolio·test_history_integration·test_fundamentals) 그린 유지 — Core Value 불변(fundamentals.py 시트1 경로·portfolio xlsx 미수정).
- 경고 4건은 pre-existing edgartools UserWarning(dei:EntityCommonStockSharesOutstanding) — 본 플랜 무관, 범위 밖.

## Decisions Made

- **옵션 B(검증·리뷰 양쪽 권장) 채택** — compute_matrix 내부 PEG 후처리(옵션 A)가 아니라 공개 래퍼 + docstring 계약. PER 2단계 계약과 일관되고 D-07(가격 비결합)과 모순 없음(가격 주입 후 PER 존재해야 PEG 산출 가능 → 호출자 주입이 설계 정합).
- **ORDER BY DESC** — REVIEW WR-01 예시의 ASC와 방향 반대. 이유는 소비측이 마지막-행-우선이기 때문. 방향 정확성의 진실원천은 결정성 단언 테스트(EDGAR 최종 선택·반복 동일).

## Deviations from Plan

None - plan executed exactly as written. (Rules 1-4 트리거 없음. 신규 패키지 없음, 아키텍처 변경 없음.)

## Issues Encountered

None. RED 테스트가 의도대로 `AttributeError: ... no attribute 'compute_peg_cell'`로 실패 후 GREEN 통과. 멀티소스 테스트는 raw_facts PK(ticker,source,quarter,field)가 source별 별도 행을 허용하므로 세 source 공존 검증 정상 동작.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- **Phase 9(트렌드 엑셀 매트릭스 렌더):** `compute_matrix` + `compute_peg_cell` 소비 계약으로 PEG 포함 9종 전부 산출 가능. 멀티소스 provenance 결정적.
- **Phase 10(시트1 최신열·가격/PEG 주입):** price_ratio(가격 의존 4종) + compute_peg_cell(PEG) 2단계 계약 확정. Core Value(시트1 색 신호) 불변 보증.
- 블로커 없음 — 검증 진실 #8·#9 충족으로 Phase 08 gap 닫힘.

## Self-Check: PASSED

- 파일 4종 모두 존재(SUMMARY·metrics_engine·fundamentals_store·test_metrics_engine).
- 커밋 3건 존재(4b6a3f7 RED / 223cdc8 GREEN / 1b626ba T2).
- `_compute_peg(` 실제 호출 1건(재수출만이 아님). `__all__`에 compute_peg_cell 존재·_compute_peg 재수출 제거.
- 전 스위트 341 passed(회귀 0).

---
*Phase: 08-registry*
*Completed: 2026-06-22*
