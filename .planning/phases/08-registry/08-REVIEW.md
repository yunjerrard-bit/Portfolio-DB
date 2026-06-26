---
phase: 08-registry
reviewed: 2026-06-19T00:00:00Z
depth: standard
files_reviewed: 3
files_reviewed_list:
  - src/stocksig/io/metrics_engine.py
  - src/stocksig/io/metrics_registry.py
  - src/stocksig/io/fundamentals_store.py
findings:
  critical: 1
  warning: 4
  info: 3
  total: 8
status: issues_found
---

# Phase 08: Code Review Report

**Reviewed:** 2026-06-19
**Depth:** standard
**Files Reviewed:** 3
**Status:** issues_found

## Summary

Phase 08의 핵심 산식 엔진(`metrics_engine.py`), 선언적 레지스트리(`metrics_registry.py`),
store 헬퍼(`fundamentals_store.py`)를 검토했다.

전반적으로 D-05(결손=None) 정책은 잘 지켜지고 있으며, SQL 인젝션(`?`-바인딩) 및 TTM 결손 게이트
(SC4)는 올바르게 구현됐다. 그러나 **PEG가 `compute_matrix`에서 영구적으로 계산되지 않는다**는 Critical
결함이 있다. 또한 멀티소스 중복 키 덮어쓰기 비결정성, STOCK mtype 데드코드 경로, raw_row fixture
날짜 하드코딩, `_compute_peg` 유령 export 등 Warning/Info 수준의 결함이 확인됐다.

---

## Critical Issues

### CR-01: PEG가 `compute_matrix`에서 영구 결손 — `_compute_peg`는 임포트만 되고 호출 없음

**File:** `src/stocksig/io/metrics_engine.py:38,207-209`

**Issue:**
`_compute_peg`를 `fundamentals`에서 임포트하고 `__all__`에 등록하지만, `compute_matrix`/`compute_cell`
어디에도 PEG 계산을 실제로 수행하는 코드가 없다. `compute_cell`에서 `DERIVED` mtype을 만나면
항상 `_empty_cell("파생 지표: 2차 계산(PEG)")` 를 반환하고 종료된다(L207-209). `compute_matrix`
루프 안에서도 DERIVED에 대한 후처리(PEG 2차 계산)가 전혀 없다.

08-03 SUMMARY "PEG(DERIVED) 미산출도 의도된 2차 파생 정의(Phase 9/10 _compute_peg 후처리)"라고
문서화하고 있으나, 호출자(Phase 9/10)는 `compute_matrix`가 반환한 매트릭스에서 `matrix["PEG"]`의
값이 항상 `None`이다. Phase 9/10이 PEG를 어떻게 채울지에 대한 명시적 API 계약 없이 `_compute_peg`만
`__all__`에 노출돼 있어, 소비자는 PEG가 이미 계산됐다고 잘못 가정할 위험이 있다.

**D-01 요구사항**: "9종 지표(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA) 모두 산출 경로 존재"
— 현재 PEG는 경로가 없음.

**Fix:**

옵션 A — PEG를 `compute_matrix` 내부에서 계산 (권장):
```python
# compute_matrix 루프 끝에 PEG 후처리 추가
for q in quarters:
    per_cell = matrix.get("PER_placeholder", {}).get(q)  # 실제로는 price_ratio 결과 필요
    eps_ttm_cell = matrix.get("EPS_ttm", {}).get(q)
    # PEG는 price 주입 후 계산 — compute_matrix 외부에서 수행하도록 별도 함수 제공
    matrix["PEG"][q] = _empty_cell("PEG: price_ratio 호출 후 _compute_peg 적용 필요")
```

옵션 B — `_compute_peg` import를 `__all__`에서 제거하고 Phase 9/10 사용 계약을 명시화:
```python
# __all__에서 제거하고 compute_matrix 반환 매트릭스의 PEG 항목에
# "Phase 9/10이 price_ratio 결과를 받아 _compute_peg 호출" 계약을 docstring에 명시.
# _compute_peg import는 유지하되, __all__ 노출 삭제
```

어느 옵션이든 반드시: PEG 항목이 항상 `value=None`인 채로 Phase 9/10에 전달되는 현재
동작이 의도된 것임을 `compute_matrix` docstring + Phase 9/10 소비 계약으로 명시해야 한다.

---

## Warnings

### WR-01: `_normalize_quarters`의 동일 `(quarter, field)` 멀티소스 덮어쓰기가 비결정적

**File:** `src/stocksig/io/metrics_engine.py:89-102`

**Issue:**
`fetch_raw_quarters`는 `ORDER BY quarter`만 적용하고 source 우선순위를 정하지 않는다.
같은 ticker의 동일 `(quarter, field)` 행이 EDGAR·DART·yf 등 복수 source로 존재할 경우,
`_normalize_quarters`에서 마지막으로 읽힌 source가 조용히 덮어쓴다(L101).
어떤 source가 이길지는 SQLite 내부 힙 순서에 달려 있어 실행마다 다를 수 있다.

docstring(L96)에 "마지막 행이 우선(조회 순서 의존)"이라 문서화했으나, 이 비결정성은
provenance 라벨 오염 및 수치 차이를 초래한다.

**Fix:**
```python
# fetch_raw_quarters SQL에 source 우선순위 ORDER BY 추가:
"SELECT quarter, source, field, value, period_type, reprt_code, unit "
"FROM raw_facts WHERE ticker=? ORDER BY quarter, "
"CASE source WHEN 'EDGAR' THEN 1 WHEN 'DART' THEN 2 WHEN 'yf' THEN 3 ELSE 4 END"
```
또는 `_normalize_quarters`에서 이미 존재하는 키를 `EDGAR`→`DART`→`yf` 우선순위로
병합하는 로직을 추가한다.

---

### WR-02: `MetricType.STOCK` 코드 경로가 데드코드 — `compute_cell`에 분기하지만 REGISTRY에 STOCK 항목 없음

**File:** `src/stocksig/io/metrics_engine.py:214-218`

**Issue:**
`compute_cell`의 `numer_is_stock` 분기(L214)는 `MetricType.STOCK`을 처리하지만,
`REGISTRY`에는 `STOCK` mtype의 MetricDef가 단 하나도 없다(metrics_registry.py 전체 검증).
이 경로는 현재 구성에서 절대 실행되지 않는 데드코드다.

또한 미래에 `STOCK` mtype MetricDef가 REGISTRY에 추가될 경우, 분모 처리 경로(L228 이하)에서
`FLOW_TTM`이 아니므로 `else` 분기(`_recent`)가 실행된다. 만약 해당 MetricDef의 `denominator`가
`None`이면 `raw_by_qf.get((quarter, None), (None, None))` 호출로 `denom=None`이 되고,
무증상으로 `_empty_cell`을 반환한다(잘못된 결론이지만 오류 없이 조용히 실패).

**Fix:**
```python
# 옵션 A: STOCK mtype 경로를 명시적으로 처리하거나 NotImplementedError로 차단
if mdef.mtype is MetricType.STOCK:
    # 단일 시점값 — denominator가 없으면 분자 그대로 반환
    if mdef.denominator is None:
        return MetricCell(value=numer, source=_merge_provenance(numer_sources), note=None)
    # denominator가 있으면 ratio
    denom = _recent(raw_by_qf, mdef.denominator, quarter)
    ...
```

---

### WR-03: `compute_cell`이 `STOCK` mtype에서 denominator `None` 시 `_recent(None)` 호출

**File:** `src/stocksig/io/metrics_engine.py:232`

**Issue:**
WR-02와 연계. `FLOW_TTM`이 아닌 모든 mtype(HYBRID·PER_SHARE·**STOCK**)은 L232에서
`_recent(raw_by_qf, mdef.denominator, quarter)`를 호출한다. `mdef.denominator`가 `None`이면
`raw_by_qf.get((quarter, None), (None, None))`이 호출된다. Python에서 `None`을 dict 키로
사용하는 것은 허용되나, raw_facts에는 `field=None` 행이 존재할 수 없으므로 항상
`(None, None)` 반환 → `denom=None` → `_is_missing(None)=True` → `_empty_cell("분모 미존재")`를
반환한다. 오류는 발생하지 않지만, 버그임을 드러낼 예외가 없어 잘못된 분모 설정을 조용히 감춘다.

**Fix:**
`compute_cell` 진입부에 denominator None 검사 추가:
```python
if mdef.denominator is None and mdef.price_denominator is None and mdef.mtype is not MetricType.DERIVED:
    # STOCK 단일 시점값 (ratio 아님) — 분자가 곧 최종값
    return MetricCell(value=numer, source=_merge_provenance(numer_sources), note=None)
```

---

### WR-04: `raw_row` fixture — `period_start`/`period_end` 하드코딩으로 비-Q1-2026 분기 테스트 시 날짜 불일치

**File:** `tests/fixtures/raw_quarters.py:37-39`

**Issue:**
`raw_row`는 `quarter` 파라미터를 받지만 `period_start="2026-01-01"`, `period_end="2026-03-31"`을
항상 고정값으로 반환한다. `quarter="2025Q3"` 등을 넘겨도 Q1-2026 날짜가 들어간다.

현재 `_normalize_quarters`는 `period_start`/`period_end`를 무시하므로(7-tuple에 포함 안 됨)
엔진 테스트에는 영향이 없다. 그러나 `upsert_quarters`로 DB에 저장 시, DB의 `period_start`/
`period_end` 컬럼이 실제 분기와 불일치한 값으로 채워진다. 이 fixture를 재사용해 DB 저장 후
날짜 기반 조회 테스트를 추가할 경우 잘못된 날짜로 인해 조용히 틀린 결과가 나온다.

**Fix:**
```python
import datetime

def _quarter_to_dates(quarter: str) -> tuple[str, str]:
    """'YYYYQn' → (period_start, period_end) ISO 날짜."""
    year = int(quarter[:4])
    q = int(quarter[5:])
    month_start = (q - 1) * 3 + 1
    period_start = datetime.date(year, month_start, 1)
    month_end = q * 3
    last_day = (datetime.date(year, month_end % 12 + 1, 1) - datetime.timedelta(days=1)
                if month_end < 12 else datetime.date(year, 12, 31))
    return str(period_start), str(last_day)

def raw_row(quarter: str = "2026Q1", ...):
    ps, pe = _quarter_to_dates(quarter)
    return (ticker, source, quarter, field, value, unit, accession, ps, pe, ...)
```

---

## Info

### IN-01: `_compute_peg`를 `__all__`에 포함 — 사용되지 않는 재수출로 소비자 혼란 유발

**File:** `src/stocksig/io/metrics_engine.py:302`

**Issue:**
`_compute_peg`는 `fundamentals`에서 임포트돼 `__all__`에 등록됐으나, 엔진 내부에서
한 번도 호출되지 않는다. 공개 API에 사용되지 않는 함수를 노출하면 Phase 9/10 개발자가
`metrics_engine._compute_peg`를 직접 호출하는 경향이 생기고, 올바른 사용 위치(PEG 2차
계산이 어디서 해야 하는지)에 대한 혼란을 일으킨다.

**Fix:** `__all__`에서 `"_compute_peg"` 제거. 필요한 소비자는 `fundamentals`에서 직접 임포트.

---

### IN-02: `MetricType.STOCK` enum 값은 정의되지만 REGISTRY에서 미사용 — 확장 의도 불명확

**File:** `src/stocksig/io/metrics_registry.py:50`

**Issue:**
`MetricType.STOCK = "저량"` enum 값이 정의되고 docstring에 설명됐으나, 현재 REGISTRY에는
이 유형의 MetricDef가 없다. 향후 STOCK 지표 추가를 염두에 둔 확장 준비라면 주석으로
명시해야 한다. 현재 상태에서는 dead enum value다.

**Fix:** docstring에 "(미사용 — 향후 절대값 지표(예: 주당장부가 단독) 추가 예정)" 주석 추가,
또는 실제로 STOCK 지표가 필요 없으면 enum에서 제거하여 `compute_cell`의 데드코드도 정리.

---

### IN-03: `_sources_for_ttm`은 TTM 결손(`_ttm_sum` → None) 시에도 항상 호출되어 일관성 없는 provenance 수집

**File:** `src/stocksig/io/metrics_engine.py:221-222`

**Issue:**
`compute_cell` L221-222에서 `numer = _ttm_sum(...)` 다음 줄에 `numer_sources = _sources_for_ttm(...)`를
무조건 호출한다. `_ttm_sum`이 None을 반환한 경우(일부 분기 결손), L224에서 early return하므로
`numer_sources`는 사용되지 않는다. 그러나 `_sources_for_ttm`은 결손 분기에 대해서는 source를
수집하지 않으므로 결손 분기의 원천 추적이 불가능하고, 불필요한 dict 조회 비용이 발생한다.

(성능 이슈는 v1 리뷰 범위 외이므로 Info로 분류. 단, provenance 수집 논리의 일관성 문제로 주목.)

**Fix:** `numer`가 None이 아닌 것이 확인된 이후에만 provenance 수집:
```python
numer = _ttm_sum(raw_by_qf, mdef.numerator, quarter)
if _is_missing(numer):
    return _empty_cell(f"{name}: 분자({mdef.numerator}) 미존재 또는 TTM 결손")
numer_sources = _sources_for_ttm(raw_by_qf, mdef.numerator, quarter)  # 여기로 이동
```

---

_Reviewed: 2026-06-19_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
