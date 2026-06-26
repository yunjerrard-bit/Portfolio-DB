---
phase: 08-registry
plan: 03
subsystem: 펀더멘털 분기 매트릭스 계산 엔진 (순수 함수, 단일 원천)
tags: [FUND-09, metrics, engine, ttm, per-share, provenance, sanity, TDD, wave2]
requires:
  - "fundamentals_store.fetch_raw_quarters (08-01 — raw 조회 진입점)"
  - "metrics_registry.REGISTRY / MetricType / MetricDef (08-02 — 9종+주당 분모 4종)"
  - "fundamentals._is_missing / MetricCell / _empty_cell / _compute_peg (재사용, Phase 10 계약 동일)"
provides:
  - "metrics_engine.compute_matrix(ticker, fetch_fn) → {metric: {quarter: MetricCell}}"
  - "metrics_engine.compute_cell(mdef, quarter, raw_by_qf) → MetricCell"
  - "metrics_engine.price_ratio(denom_cell, price) → MetricCell (가격 주입, D-07)"
  - "분기 산술 _calendar_quarter_offset/_prior_4_quarters + 유형 코어 _recent/_ttm_sum"
affects:
  - "Phase 9 (트렌드 엑셀 매트릭스 렌더) — compute_matrix 직접 소비"
  - "Phase 10 (시트1 최신열·가격 주입) — compute_matrix 최신 분기 열 + price_ratio"
tech-stack:
  added: []
  patterns:
    - "순수 함수 엔진 — fetch_fn 주입(DB 비결합·테스트 격리)"
    - "결손 단일 게이트 _is_missing(WR-01) — TTM 4분기 부분합산·0 대체 절대 금지"
    - "가격 비결합: per-share 분모 산출 + price_ratio 가격 주입 분리(D-07)"
    - "provenance \"+\".join 정렬 병합(fundamentals L289 패턴, D-08)"
key-files:
  created:
    - "src/stocksig/io/metrics_engine.py"
  modified:
    - "tests/test_metrics_engine.py (08-01 RED 스캐폴드 5종 → GREEN + Task1·Task2 신규 단언)"
decisions:
  - "PER_SHARE 분자 유량/저량 구분: net_income/revenue/operating_cash_flow=TTM, total_equity(BPS)=최근 시점값 (_STOCK_FIELDS) — Rule1 버그수정"
  - "sanity bounds(RESEARCH 권고 ASSUMED): GPM −0.5~1.5·OPM −2~1.5·ROE ±2·ROA ±1·PER 0~1000·PEG 0~10·PBR/PSR/PCR 0~100. 밖=빈값+사유"
  - "compute_matrix 분기 축 = raw에 등장한 모든 분기(오름차순). 최신값=마지막 열"
  - "D-04 canonical 드리프트 수용: registry 4분기 합이 단일 원천, 레거시 시트1 표시값과 미세차는 '더 일관된 값'"
metrics:
  duration: "~15 min"
  completed: "2026-06-19"
  tasks: 2
  files: 2
  tests: "14 engine (전 스위트 335 passed / 0 skipped, 회귀 0)"
---

# Phase 8 Plan 03: 펀더멘털 분기 매트릭스 계산 엔진 Summary

저장된 분기별 raw로부터 **9종 지표(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA)의 분기 매트릭스
전체**를 외부 재호출 없이 산출하는 순수 엔진을 구현했다(FUND-09 핵심). 유형별 산출 규칙
(저량/유량 TTM/하이브리드), TTM 4분기 결손 빈값+사유, per-share 분모/가격 분리, sanity
bounds, per-metric provenance를 모두 충족하며 Phase 9/10이 공통으로 읽는 단일 원천 계약을
완성했다.

## 무엇을 만들었나

- **분기 산술** `_calendar_quarter_offset(q, n)` / `_prior_4_quarters(q)` — "YYYYQn" ±N,
  Q1−1=전년 Q4 경계 정확(Pitfall 5). 절대 분기 인덱스(`year*4+(q-1)+n`) divmod 산술.
- **유형 코어** `_recent`(저량=분기 시점값, D-03) / `_ttm_sum`(유량=직전 4분기 합 — 1개라도
  결손 시 None, 부분합산·0 대체 절대 금지 SC4/D-05. pandas rolling 미사용).
- **분기 정규화** `_normalize_quarters(rows)` — fetch_raw_quarters 7-tuple 행 →
  `{(quarter, field): (value, source)}`. DART thstrm_amount=분기 단독값을 그대로 소비
  (누적 분해 없음), EDGAR Q4는 raw 부재대로 자연 결손(FY−9M 보정 미구현) — 08-01 방침.
- **`compute_cell(mdef, quarter, raw_by_qf)`** — mtype 분기 산출.
- **`compute_matrix(ticker, fetch_fn=fetch_raw_quarters)`** — REGISTRY 13종 × 전 분기 순회.
- **`price_ratio(denom_cell, price)`** — 가격 의존 비율 가격 주입(D-07).
- **provenance** `_merge_provenance` — 동일 source 단일 라벨, 혼합 정렬 "+"결합(D-08).
- **sanity** `_apply_sanity` — 범위 밖=빈값+"sanity 범위 밖(...)" 사유.

## Phase 9/10 직접 입력 (필수 기록)

### 시그니처
```python
compute_matrix(ticker: str, fetch_fn=fetch_raw_quarters) -> dict[str, dict[str, MetricCell]]
compute_cell(mdef: MetricDef, quarter: str, raw_by_qf: dict) -> MetricCell
price_ratio(denom_cell: MetricCell, price: float | None) -> MetricCell
```

### 매트릭스 반환 구조
`{metric_name: {quarter: MetricCell}}`. metric_name = REGISTRY 13종(9 지표 + 주당 분모
EPS_ttm/BPS/SPS/OCF_ps). 분기 축 = raw에 등장한 모든 분기(오름차순). **최신값 = 마지막
분기 열.** MetricCell = `fundamentals.MetricCell(value, source, note)` 재사용(Phase 10 동일).

### mtype별 산출 규칙 (compute_cell)
| mtype | 분자 | 분모 | 예 |
|-------|------|------|----|
| FLOW_TTM | _ttm_sum | _ttm_sum | GPM=gross_profit TTM÷revenue TTM |
| HYBRID | _ttm_sum | _recent(최근) | ROE=net_income TTM÷total_equity 최근 (D-03) |
| PER_SHARE(유량 분자) | _ttm_sum | _recent shares | EPS_ttm/SPS/OCF_ps |
| PER_SHARE(저량 분자) | _recent | _recent shares | BPS=total_equity 최근÷shares (_STOCK_FIELDS) |
| PER_SHARE(가격 의존) | — | — | PER/PBR/PCR/PSR → compute_cell 빈 셀, price_ratio 주입 |
| DERIVED | — | — | PEG → 2차 파생(PER + EPS 성장률, _compute_peg) |

### 가격 주입(D-07)
`price_ratio(denom_cell, price)`: 분모 None/≤0 또는 price 결손 → 빈값+사유, else
`price/denom`. PCR의 OCF<0은 분모≤0 게이트로 자연 차단. provenance = 분모 셀 source 보존.
PER=price/EPS_ttm, PBR=price/BPS, PCR=price/OCF_ps, PSR=price/SPS.

### provenance 병합 규칙(D-08)
`_merge_provenance(sources)`: distinct 집합이 1개면 그 라벨, 혼합이면 정렬 "+"결합
(예 "EDGAR+yf"). None/빈값 제외. TTM 분자는 4분기 윈도 source 전부, 저량은 시점 source.

### sanity bounds 적용값 (RESEARCH 권고 ASSUMED — 느슨)
GPM −0.5~1.5 · OPM −2~1.5 · ROE −2~2 · ROA −1~1 · PER 0~1000 · PEG 0~10 ·
PBR 0~100 · PSR 0~100 · PCR 0~100. 범위 밖 → value=None + note "sanity 범위 밖(...)".

### DART/EDGAR 분기 처리 최종 방침 (08-01 확정 그대로)
- **DART**: thstrm_amount=분기 단독값 → 단순 4분기 합=TTM. YTD 분해 미구현.
- **EDGAR**: 캘린더 Q4 손익·FY duration raw 부재 → Q4 포함 TTM 윈도 자연 결손(빈값+사유).
  FY−9M 보정 미구현.

### D-04 canonical 드리프트 수용
registry(저장 raw 4분기 합)가 새 단일 원천(canonical). 레거시 시트1 표시값(과거 단일
fetch 기반)과의 미세 차이는 '더 일관된 값'으로 수용·문서화. Phase 9/10 두 출력은 동일
compute_matrix를 읽으므로 상호 드리프트 0.

## 검증 결과

- `uv run pytest tests/test_metrics_engine.py -q` → **14 passed, 0 skipped** (08-01 RED 스캐폴드 5종 전부 GREEN).
- `uv run pytest -q` 전 스위트 → **335 passed, 0 skipped** (회귀 0 — 시트1/history/fundamentals 불변, Core Value 보호. Phase 8은 fundamentals.py 미수정).
- compute_matrix 외부 네트워크 호출 0 (fetch_fn=주입 lambda로 호출 1회 단언, test_reproduce).
- grep `or 0`/`fillna(0)`/`rolling(`/`-999999` → 실사용 0건 (D-05 결손=None, 문서 주석만 매치).

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] PER_SHARE 저량 분자(BPS) TTM 오적용 수정**
- **Found during:** Task 2 (test_new_metrics RED — BPS=None)
- **Issue:** 초기 compute_cell이 PER_SHARE 분자를 일괄 `_ttm_sum`으로 처리 → BS instant
  field인 total_equity(BPS 분자)는 4분기 데이터가 없어 None 반환. 플랜 action의
  "분자(유량은 TTM·저량은 최근)" 규칙 위반.
- **Fix:** `_STOCK_FIELDS`(total_equity/total_assets/total_liabilities/shares_outstanding)
  도입 — PER_SHARE 분자가 stock field면 `_recent`(최근), 아니면 `_ttm_sum`(TTM).
- **Files modified:** src/stocksig/io/metrics_engine.py
- **Commit:** 30fe528

**2. [Rule 3 - Blocking] 테스트 fixture 12-tuple↔7-tuple 어댑터**
- **Found during:** Task 1 (test_type_rules — ValueError: too many values to unpack)
- **Issue:** 08-01 `raw_row` fixture는 12-tuple(SCHEMA UPSERT 순서) 반환, 엔진
  `_normalize_quarters`는 fetch_raw_quarters 7-tuple을 받음 — 직접 주입 시 unpack 실패.
- **Fix:** 테스트에 `_to_fetch_row` 어댑터(12→7 tuple 매핑) + `_by_qf` 헬퍼 추가.
  엔진 코드는 fetch_raw_quarters 계약(7-tuple) 그대로 유지.
- **Files modified:** tests/test_metrics_engine.py
- **Commit:** c51a565

신규 패키지 설치 없음, 외부 네트워크/인증 호출 없음.

## TDD Gate Compliance

`type: tdd` plan — RED/GREEN gate 충족:
- Task1 RED: `test(08-03)` 0e8a09a (5종 단언, ImportError로 실패 확인).
- Task1 GREEN: `feat(08-03)` c51a565 (분기 산술·TTM·유형 코어 — 5종 GREEN).
- Task2 GREEN: `feat(08-03)` 30fe528 (compute_matrix·per-share·sanity·provenance — 14종 GREEN).
- REFACTOR: 불필요(구현 단순·선언적 순회).

## Known Stubs

None — compute_matrix는 저장 raw를 균일 소비하는 순수 계산. 가격 의존 4종의
compute_cell 빈 셀은 stub이 아니라 D-07 가격 비결합의 의도된 설계(price_ratio로 주입).
PEG(DERIVED) 미산출도 의도된 2차 파생 정의(Phase 9/10 _compute_peg 후처리).

## Self-Check: PASSED

- FOUND: src/stocksig/io/metrics_engine.py (compute_matrix/compute_cell/price_ratio)
- FOUND: tests/test_metrics_engine.py (test_ttm_missing 등 14 단언)
- FOUND commit: 0e8a09a (T1 RED), c51a565 (T1 GREEN), 30fe528 (T2 GREEN)
