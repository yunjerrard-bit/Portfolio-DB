---
phase: 08-registry
plan: 02
subsystem: 펀더멘털 지표 registry
tags: [FUND-09, registry, metrics, declarative, TDD]
requires:
  - "dart_account_map.DART_ACCOUNT_ID_MAP (논리 field → DART account_id 매핑, SC1 시작점)"
  - "edgar_client._EDGAR_DURATION_CONCEPTS / _EDGAR_INSTANT_CONCEPTS (논리 field → EDGAR concept)"
  - "store field 어휘 (raw_facts.field: revenue/net_income/total_equity/...)"
provides:
  - "metrics_registry.MetricType (STOCK/FLOW_TTM/HYBRID/PER_SHARE/DERIVED enum)"
  - "metrics_registry.MetricDef (frozen dataclass: name/mtype/numerator/denominator/is_ratio_0_1/price_denominator)"
  - "metrics_registry.REGISTRY (9종 지표 + 주당 분모 4종 = 13 MetricDef tuple)"
affects:
  - "08-03 metrics_engine — REGISTRY를 순회하며 mtype별 계산 (직접 계약)"
tech-stack:
  added: []
  patterns:
    - "선언적 registry: 산식=유형 enum이 결정, 신규 지표=튜플 1줄 추가 (SC3)"
    - "frozen dataclass 상수 (writer._NUM_FORMAT_MAP / dart_account_map 모듈 상수 스타일)"
    - "가격 비결합: 가격 의존 지표는 price_denominator로 분모 metric 이름만 참조 (D-07)"
key-files:
  created:
    - "src/stocksig/io/metrics_registry.py"
    - "tests/test_metrics_registry.py"
  modified: []
decisions:
  - "EPS_ttm = net_income TTM ÷ 최근 shares (A4 — eps per-share 4합 대신 분자 net_income, 주식수 변동 부정확 회피)"
  - "가격 의존 4종(PER/PBR/PCR/PSR) numerator/denominator=None, price_denominator만 (D-07 가격 비결합)"
  - "PEG=DERIVED (08-03 _compute_peg 2차 계산), registry는 유형만 선언"
  - "FCF·EV/EBITDA 제외 (D-02 — 저장 raw 부재), REGISTRY append로 1줄 확장 가능"
  - "새 매핑 dict 미정의 — dart_account_map/edgar concept import 재사용 (SC1)"
metrics:
  duration: "~10 min"
  completed: "2026-06-19"
  tasks: 1
  files: 2
  tests: "11 new (323 passed / 5 skipped 전 스위트, 회귀 0)"
---

# Phase 8 Plan 02: 펀더멘털 지표 registry Summary

9종 펀더멘털 지표(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA)를 선언적 registry(`MetricType` enum + frozen `MetricDef` dataclass + `REGISTRY` 튜플)로 정의하고, 각 논리 field를 기존 `dart_account_map`/`edgar concept` 매핑에 import 재사용으로 연결했다. 산식은 유형 enum이 결정하므로 신규 지표는 REGISTRY 튜플 1줄 추가로 끝난다(SC3).

## 무엇을 만들었나

- **`MetricType(Enum)`** — 한국어 값: `STOCK="저량"` / `FLOW_TTM="유량"` / `HYBRID="하이브리드"` / `PER_SHARE="주당"` / `DERIVED="파생"`. 엔진(08-03)이 이 유형으로 계산 방식을 분기한다.
- **`@dataclass(frozen=True) MetricDef`** — 필드 시그니처:
  `name: str`, `mtype: MetricType`, `numerator: str | None`, `denominator: str | None`, `is_ratio_0_1: bool = False`, `price_denominator: str | None = None`.
- **`REGISTRY: tuple[MetricDef, ...]`** — 9종 핵심 + 가격 의존 4종이 참조할 주당 분모 metric 4종 = 13 항목.

### REGISTRY 내용 (08-03 엔진 직접 계약)

| name | mtype | numerator | denominator | is_ratio_0_1 | price_denominator |
|------|-------|-----------|-------------|--------------|-------------------|
| GPM | FLOW_TTM | gross_profit | revenue | True | — |
| OPM | FLOW_TTM | op_income | revenue | True | — |
| ROE | HYBRID | net_income | total_equity | False | — |
| ROA | HYBRID | net_income | total_assets | False | — |
| EPS_ttm | PER_SHARE | net_income | shares_outstanding | False | — |
| BPS | PER_SHARE | total_equity | shares_outstanding | False | — |
| SPS | PER_SHARE | revenue | shares_outstanding | False | — |
| OCF_ps | PER_SHARE | operating_cash_flow | shares_outstanding | False | — |
| PER | PER_SHARE | None | None | False | EPS_ttm |
| PBR | PER_SHARE | None | None | False | BPS |
| PCR | PER_SHARE | None | None | False | OCF_ps |
| PSR | PER_SHARE | None | None | False | SPS |
| PEG | DERIVED | None | None | False | — |

**가격 의존 4종(PER/PBR/PCR/PSR)**: 비율을 계산하지 않고 `price_denominator`에 분모 metric 이름만 박는다(D-07). 가격은 08-03 호출자가 주입 → registry와 가격 비결합(과거=분기말 종가 / 최신=현재가 분리 가능).

## 검증 방법

```bash
uv run pytest tests/test_metrics_registry.py -x -q   # 11 passed
uv run pytest -q                                      # 323 passed / 5 skipped (회귀 0)
```

테스트 단언(11종): 9종 name 집합 / ROE·ROA HYBRID / GPM·OPM FLOW_TTM(0~1) / 주당 4종 분모=shares_outstanding / PER·PBR·PCR·PSR price_denominator 참조 + numerator/denominator None / PEG DERIVED / field 어휘↔store 정합(T-08-03) / dart_account_map 키 연결(SC1) / 1줄 확장 불변(SC3) / frozen 불변.

## 성공 기준 충족

- ✓ 9종 MetricDef 선언 + 유형 정확 (FUND-09 SC1)
- ✓ numerator/denominator가 store field 어휘와 일치 (오계산 방지, T-08-03)
- ✓ 소스 매핑이 기존 dart_account_map/edgar concept에 연결 — import 재사용, 새 dict 미정의 (SC1 grep 확인)
- ✓ 신규 지표 1줄 추가 확장성 증명 (SC3, test_add_new_metric_is_one_line)

## Deviations from Plan

None — plan executed exactly as written. registry_spec 표 9종 + 주당 분모 4종을 그대로 구현했다.

## TDD Gate Compliance

- RED: `test(08-02)` commit `bd61516` — 11 단언, ModuleNotFoundError로 실패 확인.
- GREEN: `feat(08-02)` commit `9b95a82` — 11 passed, 전 스위트 323 passed 회귀 0.
- REFACTOR: 불필요(구현이 처음부터 선언적·단순, 변경 없음).

## Known Stubs

None — 선언적 상수 모듈, 데이터 소스 stub 없음. PEG numerator/denominator=None은 stub이 아니라 DERIVED 유형의 의도된 정의(08-03 엔진이 2차 계산).

## Self-Check: PASSED

- FOUND: src/stocksig/io/metrics_registry.py
- FOUND: tests/test_metrics_registry.py
- FOUND commit: bd61516 (RED), 9b95a82 (GREEN)
