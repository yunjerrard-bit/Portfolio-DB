---
phase: 08-registry
verified: 2026-06-22T00:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 7/9
  gaps_closed:
    - "PER/PEG/GPM/OPM가 저장 raw로 재현된다(SC3) — PEG 공개 2단계 API compute_peg_cell로 value 산출(진실 #8)"
    - "PER/PEG/GPM/OPM 및 신규 지표를 외부 재호출 없이 계산한다(FUND-09 요건 문구) — _compute_peg 실제 호출 + Phase 9/10 소비 계약 docstring(진실 #9)"
  gaps_remaining: []
  regressions: []
---

# Phase 08: 지표 Registry 검증 보고서 (재검증)

**Phase 목표:** 저량/유량(TTM)/하이브리드 유형의 지표 registry를 정의하고, 저장된 원천
raw로부터 PER/PEG/GPM/OPM 및 신규 지표(ROE·PBR 등)를 외부 재호출 없이 계산한다.
**검증일:** 2026-06-22
**상태:** passed
**재검증 여부:** 예 — 갭 클로징(08-04) 후 재검증. 이전 7/9(단일 블로커: PEG 계산 경로 부재) → 현 9/9.

---

## 재검증 요약

이전 검증(2026-06-19)에서 진실 #8·#9가 FAILED였다. 단일 블로커는 **PEG(DERIVED) 계산
경로 부재** — `compute_cell`이 DERIVED를 항상 `_empty_cell` 반환, `compute_matrix`에 PEG
후처리 없음, `_compute_peg`는 `__all__`에만 재수출되고 엔진 내부 미호출, 테스트는 키 존재만
단언.

08-04(gap closure)가 **옵션 B**를 채택해 닫았다: PER `price_ratio`와 대칭인 공개 2단계 API
`compute_peg_cell`을 추가하고, `_compute_peg`를 실제 호출 경로에 연결, Phase 9/10 소비 계약을
docstring에 박제, PEG value 단언 테스트 추가. 함께 WR-01(멀티소스 비결정성)을 `fetch_raw_quarters`
ORDER BY source 우선순위로 닫았다.

**재검증은 SUMMARY 주장을 신뢰하지 않고 코드·테스트 실행으로 직접 확인했다.** 두 실패 진실은
모두 VERIFIED로 전환됐고, 회귀 0(341 passed), Core Value(시트1 경로) 불변이 확인됐다.

---

## 목표 달성 판정

### 관찰 가능한 진실 (Observable Truths)

| # | 진실 | 상태 | 근거 |
|---|------|------|------|
| 1 | DART thstrm_amount 분기/누적 의미가 확정·박제됨(FUND-09 산식 선행, 08-01) | ✓ VERIFIED | test_dart_quarter_semantics_applied — 단순 4분기 합=TTM 단언 통과(전 스위트 GREEN). 회귀 없음. |
| 2 | EDGAR Q4 갭 확정·Q4=빈값+사유 박제(D-05, 08-01) | ✓ VERIFIED | test_edgar_q4 — 2025Q4 부재→TTM None 단언 통과. 회귀 없음. |
| 3 | 9종 지표가 MetricDef로 선언되고 각 유형 정확(D-01, 08-02) | ✓ VERIFIED | test_metrics_registry 11종(전체 스위트 341 passed 내 그린). 미수정. |
| 4 | 저장 raw만으로 분기 매트릭스 전체가 외부 재호출 없이 산출(D-06) | ✓ VERIFIED | test_reproduce: called["n"]==1 통과. compute_matrix(L299-338) fetch_fn 주입·네트워크 0. |
| 5 | TTM 4분기 결손→빈값+사유, 0 대체·부분합산 없음(SC4·D-05) | ✓ VERIFIED | test_ttm_missing 통과. _ttm_sum(L117-133) 1개 결손→None. 미수정. |
| 6 | 가격 의존 4종은 per-share 분모만 산출, 비율은 price_ratio로 가격 주입(D-07) | ✓ VERIFIED | compute_cell L204-205 price_denominator→_empty_cell. price_ratio(L251-264) 존재. test_new_metrics·test_provenance_or_pershare 통과. |
| 7 | per-metric provenance 라벨(혼합="+") MetricCell.source 보존(SC5/D-08) | ✓ VERIFIED | test_provenance_or_pershare: eps.source=="EDGAR+yf" 통과. _merge_provenance(L160-168) 미수정. |
| 8 | **PER/PEG/GPM/OPM가 저장 raw로 재현된다(SC3)** | **✓ VERIFIED** | (이전 FAILED→해소) compute_peg_cell(L267-296)이 `_compute_peg`(L290) 실제 호출 + sanity(0~10, L293) 적용. test_compute_peg_cell_value: `.value==approx(1.0)`(value 단언, 키 존재 아님). L230-233 키-존재-만 단언→value 산출 단언으로 강화. |
| 9 | **PER/PEG/GPM/OPM 및 신규 지표를 외부 재호출 없이 계산한다(FUND-09 요건 문구)** | **✓ VERIFIED** | (이전 FAILED→해소) `_compute_peg` 공개 래퍼 통해 실제 호출(grep: 호출 1건). `__all__`(L341-352)에 compute_peg_cell 추가·_compute_peg 제거. compute_matrix docstring(L309-324)에 Phase 9/10 소비 계약 3단+코드예시 박제. test_peg_end_to_end_from_matrix: called["n"]==1(외부 재호출 0)·peg.value==approx(0.5) 통과. |

**점수:** 9/9 진실 검증됨 (이전 7/9 → +2)

---

## 갭 클로징 검증 (진실 #8·#9 집중 재검증)

### 진실 #8 — PEG value 산출 (SC3)

**코드 근거 (metrics_engine.py L267-296):**
```python
def compute_peg_cell(per_value, eps_ttm, eps_prior) -> MetricCell:
    cell = _compute_peg(per_value, eps_ttm, eps_prior)   # L290 — 실제 호출
    if _is_missing(cell.value):
        return cell
    ok, reason = _apply_sanity("PEG", cell.value)        # L293 — sanity 0~10
    if not ok:
        return MetricCell(value=None, source=cell.source, note=reason)
    return cell
```
- PER `price_ratio(denom_cell, price)`와 대칭인 공개 2단계 API. PEG는 더 이상 영구 None 아님.
- **테스트 value 단언(키 존재만 아님):** test_compute_peg_cell_value(L339-343) `cell.value == pytest.approx(1.0)`.
  test_compute_matrix_shape L230-233도 이전 "PEG" in matrix 키-존재-만 단언을 value 산출 단언으로 강화.
- 엣지 4종 위임 검증: test_compute_peg_cell_edges(L346-361) — 성장률≤0/전년EPS=0/PER없음 각각 value None+한국어 사유.
- sanity bounds: test_peg_sanity_bounds(L413-418) — PEG=100>10 상한→빈값+"sanity" 사유.

### 진실 #9 — 외부 재호출 없는 계산 경로 + 소비 계약 (FUND-09)

- **_compute_peg 실제 호출 (재수출만 아님):** `grep _compute_peg\( metrics_engine.py` → L290 단 1건 호출 site 확인.
- **`__all__` 정리 (IN-01):** L341-352에 `compute_peg_cell` 존재, `_compute_peg` 부재. import은 모듈 내부 호출용으로만 유지(L36-41).
- **Phase 9/10 소비 계약 박제:** compute_matrix docstring L309-324에 3단(① price_ratio로 PER → ② matrix["EPS_ttm"] 현재·4분기전 `_calendar_quarter_offset(q,-4)` → ③ compute_peg_cell) + 실행 가능 예시.
- **외부 재호출 0:** test_peg_end_to_end_from_matrix(L364-410) — fetch 1회 단언 + 현·4분기전 EPS_ttm(4.8/4.0)→PER(10.0)→PEG(0.5) 산식값 일치.

### WR-01 — 멀티소스 결정성 (추가 확인)

**코드 근거 (fundamentals_store.py L181-188):**
```sql
SELECT quarter, source, field, value, period_type, reprt_code, unit
FROM raw_facts WHERE ticker=?
ORDER BY quarter,
  CASE source WHEN 'EDGAR' THEN 0 WHEN 'DART' THEN 1 WHEN 'yf' THEN 2 ELSE 3 END
  DESC
```
- `?`-바인딩·`get_store()` 재사용 유지 (T-08-01 SQL injection 게이트 불변 — CASE는 SQL 리터럴).
- DESC 방향 정합: 소비측 `_normalize_quarters`(L99-102) 마지막-행-우선이므로 EDGAR가 정렬상 마지막에 와야 이김.
- 결정성 단언: test_fetch_raw_quarters_source_priority_deterministic(L77-104) — 삽입 순서를 우선순위와 반대로 넣고 3회 반복 실행 모두 source=="EDGAR"·value==100.0. test_fetch_raw_quarters_dart_over_yf(L108-123) — EDGAR 부재 시 DART>yf.
- 기존 quarter 오름차순 정렬 회귀 없음: test_fetch_raw_quarters_returns_sorted 통과(전 스위트 GREEN).

---

## 필수 아티팩트

| 아티팩트 | 제공 목적 | 상태 | 비고 |
|----------|----------|------|------|
| `src/stocksig/io/metrics_engine.py` | compute_matrix/compute_cell/price_ratio + **compute_peg_cell** | ✓ VERIFIED | 353줄. compute_peg_cell(L267-296)·_compute_peg 호출(L290)·docstring 계약(L309-324)·__all__ 정리(L341-352) 모두 존재. |
| `src/stocksig/io/fundamentals_store.py` | fetch_raw_quarters + **source 우선순위 ORDER BY** | ✓ VERIFIED | L181-188 CASE source DESC + ?-바인딩 유지. |
| `src/stocksig/io/fundamentals.py` | _compute_peg 산식(위임 대상) | ✓ VERIFIED (미수정) | L92-109 엣지 4종 그대로. Core Value 시트1 경로 불변. |
| `src/stocksig/io/metrics_registry.py` | REGISTRY 9종·MetricType | ✓ VERIFIED (미수정) | 회귀 없음. |
| `tests/test_metrics_engine.py` | PEG value 단언 + 멀티소스 결정성 단언 | ✓ VERIFIED | compute_peg_cell value 단언 4종(L339-418) + source 결정성 2종(L77-123) + L230-233 강화. 20 passed. |

---

## 핵심 링크 검증

| From | To | Via | 상태 | 근거 |
|------|----|-----|------|------|
| metrics_engine.compute_peg_cell | fundamentals._compute_peg | 공개 래퍼가 내부 산식 실제 호출 | ✓ WIRED | L290 `cell = _compute_peg(...)` — grep 호출 1건(재수출만 아님). 이전 NOT_WIRED→해소. |
| tests/test_metrics_engine.py | metrics_engine.compute_peg_cell | PEG value 단언 | ✓ WIRED | L343 `.value==approx(1.0)`, L408-410 end-to-end value 단언. |
| fundamentals_store.fetch_raw_quarters | raw_facts.source 우선순위 | ORDER BY CASE source DESC | ✓ WIRED | L184-186. test 결정성 단언 통과. |
| metrics_engine | fundamentals_store.fetch_raw_quarters | import | ✓ WIRED | L42. 회귀 없음. |
| metrics_engine | metrics_registry.REGISTRY | import | ✓ WIRED | L43. 회귀 없음. |

---

## 데이터 흐름 추적 (Level 4)

| 아티팩트 | 데이터 변수 | 원천 | 실 데이터 생성 | 상태 |
|----------|------------|------|----------------|------|
| compute_matrix → GPM/OPM/ROE/ROA/EPS_ttm 등 | raw_by_qf[(q,field)] | fetch_raw_quarters → raw_facts DB | _ttm_sum/_recent | ✓ FLOWING |
| compute_matrix → PER/PBR/PCR/PSR | 분모 셀(가격 주입 후) | price_ratio 호출자 주입 | 설계 의도(D-07) | ✓ FLOWING |
| **compute_peg_cell → PEG** | **per_value·eps_ttm·eps_prior** | **price_ratio(PER) + matrix["EPS_ttm"] 현·4분기전** | **_compute_peg 산식 → value** | **✓ FLOWING** (이전 DISCONNECTED→해소) |

---

## 행동 스팟 체크 (Behavioral Spot-Checks)

| 동작 | 명령 | 결과 | 상태 |
|------|------|------|------|
| PEG·source 결정성 테스트 | uv run pytest tests/test_metrics_engine.py -k "peg or source or priority or determin" -q | 5 passed, 15 deselected | ✓ PASS |
| test_metrics_engine.py 전체 | uv run pytest tests/test_metrics_engine.py -q | 20 passed in 1.31s | ✓ PASS |
| _compute_peg 실제 호출 grep | grep `_compute_peg\(` metrics_engine.py | L290 — 호출 1건 | ✓ PASS |
| 전 스위트(회귀 검증) | uv run pytest -q --tb=short | **341 passed, 4 warnings in 425s** | ✓ PASS |
| Core Value 불변(변경 파일) | git show --stat (3 commits) | metrics_engine.py·fundamentals_store.py·test_metrics_engine.py만. fundamentals.py 시트1·portfolio xlsx 미수정 | ✓ PASS |

경고 4건은 pre-existing edgartools UserWarning(dei:EntityCommonStockSharesOutstanding) — 본 단계 무관.

---

## 요건 커버리지

| 요건 ID | 원천 플랜 | 설명 | 상태 | 근거 |
|---------|----------|------|------|------|
| FUND-09 | 08-01, 08-02, 08-03, 08-04 | 지표가 유형별 registry로 정의되어, 저장 raw로부터 PER/PEG/GPM/OPM 및 신규 지표를 외부 재호출 없이 계산 | ✓ SATISFIED | 9종 전부 계산 경로 존재. PEG는 compute_peg_cell 2단계 공개 API로 산출(이전 PARTIAL→완성). |

---

## 안티패턴 스캔

| 파일 | 라인 | 패턴 | 심각도 | 영향 |
|------|------|------|--------|------|
| metrics_engine.py | L209-210 | compute_cell DERIVED 분기 `_empty_cell` | ℹ️ Info | 의도된 설계 — DERIVED는 compute_cell 단독 미산출, compute_peg_cell 공개 API로 산출(docstring 사유 갱신됨). 더 이상 블로커 아님. |
| metrics_engine.py | L290 | `_compute_peg(` 호출 | ℹ️ Info | 정상 위임(Don't Hand-Roll). 산식 fundamentals 재사용. |
| tests/fixtures/raw_quarters.py | — | period_start/end 하드코딩 | ℹ️ Info | WR-04(deferred) — 현 _normalize_quarters 날짜 무시로 엔진 무영향. 08-04 범위 밖 명시. |

**부채 마커(TBD/FIXME/XXX):** 변경 3개 파일에서 미발견. 부채 마커 게이트 통과.

**이전 블로커 해소 확인:** 이전 검증의 🛑 Blocker(L207-209 PEG 영구 None)·⚠️ Warning(L302 미사용 재수출·docstring API 미정의·L181 키 존재만 단언)이 모두 코드/테스트로 해소됨.

---

## 인간 검증 필요 항목

없음 — 이 단계의 모든 진실은 코드·테스트 실행으로 프로그래밍적으로 확인됐다. (PEG·source 결정성·전 스위트 회귀 0·변경 파일 범위 모두 자동 검증.)

---

## 갭 요약

**갭 없음 — Phase 08 목표 달성 (9/9).**

이전 단일 블로커(PEG 계산 경로 부재)가 08-04로 닫혔다:
- `compute_peg_cell` 공개 2단계 API가 `_compute_peg`를 실제 호출(L290) — value 더 이상 영구 None 아님(진실 #8).
- `__all__` 정리 + compute_matrix docstring에 Phase 9/10 소비 계약 박제 — 외부 재호출 없는 계산 경로 명시(진실 #9, FUND-09).
- 테스트가 PEG value를 단언(키 존재만 아님) — 결함 은닉 제거.
- WR-01: fetch_raw_quarters ORDER BY source 우선순위(EDGAR→DART→yf, DESC)로 멀티소스 결정성 확보.

**회귀 0(341 passed) + Core Value 불변** — fundamentals.py 시트1 경로·portfolio xlsx 미수정 확인.
이전 VERIFIED 7개 진실 모두 회귀 없이 유지. Phase 9(매트릭스 렌더)·Phase 10(시트1 PEG/가격 주입) 진행 준비 완료.

---

_검증일: 2026-06-22 (재검증 — 갭 클로징 후)_
_검증자: Claude (gsd-verifier)_
