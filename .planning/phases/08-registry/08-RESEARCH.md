# Phase 8: 지표 registry 계산 - Research

**Researched:** 2026-06-19
**Domain:** 순수 계산 층 — SQLite 저장 raw로부터 9종 펀더멘털 지표(저량/유량 TTM/하이브리드) registry 계산. 외부 호출 없음.
**Confidence:** HIGH (코드베이스·CONTEXT·로컬 코드는 직접 검증) / MEDIUM (DART YTD 의미는 공식 가이드로 정정 — Phase 7 가정과 충돌, 실데이터 1회 확인 권장)

> response_language: 한국어. 본 문서 전체 한국어.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** Phase 8 산출 지표 = **9종**. 재현 4종(PER/PEG/GPM/OPM) + 신규 5종(PBR·PCR·PSR·ROE·ROA).
  - PBR = 주가 ÷ BPS(total_equity ÷ shares_outstanding) — 저량·가격
  - PCR = 주가 ÷ OCF-per-share(operating_cash_flow TTM ÷ shares) — 유량·가격
  - PSR = 주가 ÷ SPS(revenue TTM ÷ shares) — 유량·가격
  - ROE = net_income TTM ÷ total_equity — 하이브리드
  - ROA = net_income TTM ÷ total_assets — 하이브리드
- **D-02:** **FCF·EV/EBITDA는 연기.** 저장 raw에 없는 필드 필요 → 별도 phase. registry는 신규 지표 추가가 쉽도록 설계하되 이 2종은 원천 확장 후 추가.
- **D-03:** 하이브리드 지표(ROE·ROA)의 분모(자본·자산) = **최근 분기 시점값**(기초·기말 평균 아님). raw 한 분기만 있어도 산출 가능.
- **D-04:** registry(저장 raw 4분기 합산)가 **새 단일 원천(canonical)**. 현 시트1 표시값과 미세 차이는 "더 일관된 값"으로 수용 — Phase 10 이관 시 표시값이 약간 변할 수 있으며 문서화.
- **D-05:** 검증은 **합리적 범위(sanity bounds)** 로 수행 — 레거시 값과의 **정확 일치는 강제하지 않는다**.
- **D-06:** **분기 매트릭스 전체** 산출 — 매 분기별로 전 지표 시계열 계산. 최신값 = 매트릭스 마지막 열. Phase 9는 매트릭스 그대로, Phase 10은 최신열만 읽는다.
- **D-07:** 가격 의존 지표(PER·PBR·PCR·PSR)는 registry가 **가격 비의존 per-share 분모(EPS_ttm·BPS·SPS·OCF-ps)를 분기별로 산출**하고, 비율 = price ÷ 분모로 **가격은 호출자가 주입**한다. 최신=현재가 / 과거=분기말 종가. 계산 층은 가격 파이프라인과 비결합.
- **D-08:** registry = **순수 계산 + per-metric provenance 라벨**. 각 metric의 provenance = 계산에 사용한 raw 필드들의 `source` 라벨(EDGAR/DART/yf/Naver).
- **D-09:** **폴백 체인 fetch는 registry 책임 아님** — 오케스트레이션(Phase 10) 책임. registry는 어떤 source의 저장 raw든 균일 수용해 계산하고, 1차 raw 결손 시 해당 metric은 **빈값 + 사유**(0 대체 금지). SC5 "폴백 의미 보존/수용" = fetch 구현이 아니라 폴백-소스 값을 수용 가능해야 한다는 계약.
- **TTM 결손 처리 (SC4 — 잠긴 정책):** TTM 4분기 중 결손 분기가 있으면 해당 TTM 지표는 **빈값 + 사유**(0 대체 금지). 부분 합산 금지.

### Claude's Discretion

- registry 자료구조·모듈 위치(예: `metrics_registry.py` + 계산 엔진 분리), 지표 정의 표현(dataclass vs dict).
- EDGAR Q4=FY−9M 보정·DART YTD 분해(thisQ누적−직전Q누적)의 구체 구현 — 백로그 D-H2 기반, raw는 as-reported 보존이므로 분해는 계산 시점 수행.
- 분기 분해 시 직전 분기 결손/정렬 엣지케이스 처리.
- provenance 라벨이 metric별 복수 source raw 혼합 시 라벨링 규칙.
- sanity bounds 검증의 구체 임계(어떤 지표를 어떤 합리 범위로 체크할지) — researcher 조사 후 planner 결정.

### Deferred Ideas (OUT OF SCOPE)

- **FCF** 지표 — CapEx 미저장 → Phase 7 raw 추출 확장 선행 필요.
- **EV/EBITDA** 지표 — 현금잔액·D&A·이자성부채 미저장 → raw 확장 필요.
- 폴백 체인(DART→Naver→yf) **fetch 오케스트레이션** 및 폴백-소스 값 DB 적재 → Phase 10(FUND-11).
- 기초·기말 평균 분모(ROE/ROA) — 이번엔 최근값(D-03). 추후 registry 옵션 도입 가능.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FUND-09 | 지표가 유형별(저량=최근 분기값 / 유량=TTM 4분기 합 / 하이브리드=유량분자÷저량분모) registry로 정의되어, 저장된 원천 raw로부터 PER/PEG/GPM/OPM 및 신규 지표(ROE·PBR 등)를 외부 재호출 없이 계산할 수 있다. | registry 자료구조 패턴(Architecture Pattern 1) · 유형별 계산 엔진(Pattern 2) · TTM 합산+결손 정책(Pattern 3) · per-share 분모 분리(Pattern 4) · EDGAR Q4 보정(Pitfall 1) · DART 분기/누적 의미(Pitfall 2) · sanity bounds(별도 섹션) · provenance 병합(Pattern 5) |
</phase_requirements>

## Summary

Phase 8은 **새 외부 라이브러리가 사실상 0개**인 순수 계산 층이다. 입력은 `data/fundamentals.db`의 `raw_facts` long 테이블(이미 Phase 7에서 구축), 출력은 9종 지표의 분기 매트릭스다. 핵심 기술은 라이브러리가 아니라 **계산 규칙의 정확성**이다: (1) 유형별 산출 규칙(저량=최근값/유량=TTM 4분기 합/하이브리드), (2) source별 분기값 의미 정규화(EDGAR는 Q4 단독값 부재, DART는 분기/누적 컬럼 선택), (3) 결손 시 빈값+사유의 일관 적용, (4) 가격 비의존 per-share 분모 분리.

연구 중 **Phase 7의 핵심 가정 하나가 공식 OpenDART 가이드와 충돌**함을 발견했다. 프로젝트 전반(STATE.md·백로그 D-H2·07-CONTEXT D-05·dart_client.py 주석)은 "DART finstate_all 손익 항목은 YTD 누적이라 분기 분해(thisQ−직전Q) 필요"라고 전제한다. 그러나 OpenDART 공식 개발가이드(DS003 단일회사 전체 재무제표)는 **"분/반기 보고서이면서 (포괄)손익계산서일 경우 `thstrm_amount`는 [3개월] 금액"** 이라고 명시한다 — 즉 분기 단독값이며, 누적값은 별도 컬럼 `thstrm_add_amount`다. 현 Phase 7 추출기는 `thstrm_amount`만 저장하므로, **DART 손익 raw는 이미 분기 단독값일 가능성이 높다.** 이 경우 "DART YTD 분해" 자체가 불필요하거나, 거꾸로 누적이 필요한 곳에서 단독값을 쓰게 된다. 실데이터 1회 확인(005930 반기/3분기 보고서)으로 반드시 검증해야 한다.

또 하나의 raw-data 갭: EDGAR 추출기는 `query().by_period_length(3)`(3개월 duration)만 저장한다. 미국 10-K의 Q4는 XBRL에 3개월 duration fact가 **존재하지 않고** 연간(FY, 12개월 duration)만 보고된다. 따라서 **저장된 raw에 Q4 손익 단독값도, FY 연간값도 없다** → 현 raw만으로는 Q4 손익을 복원할 수 없다. Q4=FY−9M 보정을 하려면 FY duration fact를 추가로 저장하거나 Phase 8이 EDGAR를 재호출해야 하는데, 재호출은 본 phase 목표("외부 재호출 없이")에 위배된다. 이는 planner가 반드시 처리 방침을 정해야 할 갭이다.

**Primary recommendation:** 표준 라이브러리 + 기존 pandas로 `metrics_registry.py`(지표 정의: dataclass)와 `metrics_engine.py`(분기 매트릭스 계산)를 분리 구현하라. **착수 전 2개 raw-data 진실을 1회 실데이터로 확정**할 것 — (1) DART `thstrm_amount`가 분기 단독값인지 누적인지, (2) EDGAR raw에 FY/Q4 손익이 저장돼 있는지. 이 2개가 Q4 보정·TTM 합산 산식의 옳고 그름을 좌우한다.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| raw_facts 조회 | Database/Storage (`fundamentals_store.py`) | — | 단일 진원지. 신규 SELECT 헬퍼는 store에 추가(ASVS V5 `?` 바인딩 유지) |
| 지표 정의 (이름/유형/산식/원천필드) | 계산 층 (`metrics_registry.py` 신규) | — | 선언적 메타데이터. 신규 지표 = registry 항목 추가 1줄 |
| 분기 매트릭스 계산 (저량/유량 TTM/하이브리드) | 계산 층 (`metrics_engine.py` 신규) | — | 순수 함수. 입력=raw rows, 출력=분기×지표 셀. 네트워크·가격 비결합 |
| source별 분기 정규화 (EDGAR Q4 / DART 분기·누적) | 계산 층 (전처리 단계) | — | as-reported→canonical 분기값 변환. raw는 불변 |
| per-share 분모 산출 (EPS_ttm/BPS/SPS/OCF-ps) | 계산 층 | — | 가격 비의존. 비율은 호출자가 price 주입(D-07) |
| 가격 주입 (현재가/분기말 종가) | 호출자 (Phase 9 렌더 / Phase 10 시트1) | OHLCV 파이프라인 | Phase 8 밖. registry는 분모만 노출 |
| 폴백 fetch 오케스트레이션 | 오케스트레이션 (Phase 10) | — | registry는 저장 raw만 균일 소비(D-09) |
| sanity bounds 검증 | 계산 층 (셀 산출 직후) | — | 범위 밖 값 = 빈값+사유 또는 경고 라벨 |

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python stdlib (`sqlite3`, `dataclasses`, `math`) | 3.13/3.x | registry 정의·결손 게이트·DB 조회 | 신규 의존 0. 기존 `fundamentals.py`/`fundamentals_store.py` 패턴 그대로 [VERIFIED: 로컬 코드] |
| pandas | 3.0.3 (설치됨) | 분기 매트릭스 정렬·TTM rolling 합 | 이미 의존. `groupby`/`rolling(4).sum()`/`pivot`으로 TTM·매트릭스 산출 가능 [VERIFIED: `uv pip list`] |
| numpy | 2.4.6 (설치됨) | NaN 게이트·수치 프리미티브 | pandas 동반. `_is_missing` NaN 판정에 사용 [VERIFIED: `uv pip list`] |

> **신규 패키지 설치 없음.** 본 phase는 Package Legitimacy Audit이 비어 있다(아래 참조).
> 참고: 설치된 pandas 3.0.3·numpy 2.4.6은 CLAUDE.md 권고(pandas 2.2.x)보다 신버전이나 stable이며 기존 코드가 이미 사용 중 — 회귀 위험은 본 phase가 새로 도입하는 게 아님.

### Supporting

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `logging` (stdlib) | — | 한국어 진행/결손 사유 로그 | 기존 `logger = logging.getLogger(__name__)` 패턴 |
| `dataclasses` (stdlib) | — | `MetricCell`(재사용) + 신규 `MetricDef` registry 항목 | `fundamentals.py` `MetricCell(value, source, note)` 그대로 재사용 권장 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| 순수 pandas TTM 합 | 수동 dict 루프 4분기 합 | dict 루프가 결손 판정·"4분기 모두 존재" 게이트를 더 명시적으로 제어 가능. 200종목×~40분기×9지표 규모는 둘 다 충분히 빠름. **권장: dict 기반 — TTM 결손 정책(부분합산 금지)을 pandas `rolling().sum()`(NaN 전파 옵션 까다로움)보다 정확히 표현** |
| dataclass registry | dict registry | dict가 더 가볍지만 dataclass가 타입·필드 강제·IDE 지원 우수. CONTEXT가 둘 다 허용 |
| callable 산식 | 선언적(유형 enum) 산식 | 9종 중 대부분이 "분자/분모" 패턴 → 유형 enum + 분자·분모 field 지정이 더 선언적·확장 쉬움. PEG만 특수(2차 파생) → callable 혼용 |

**Installation:** 신규 설치 없음.

**Version verification:**
- pandas 3.0.3 [VERIFIED: `uv pip list`, 2026-06-19]
- numpy 2.4.6 [VERIFIED: `uv pip list`, 2026-06-19]
- edgartools 5.35.0 [VERIFIED: `uv pip list`] — Phase 8은 직접 import 안 함(저장 raw만 읽음). Q4 갭 처리 방침에 따라 재등장 가능성만 존재.

## Package Legitimacy Audit

> 본 phase는 **신규 외부 패키지를 설치하지 않는다**(순수 계산 층, stdlib + 기존 pandas/numpy). slopcheck 대상 없음.

| Package | Registry | Age | Downloads | Source Repo | slopcheck | Disposition |
|---------|----------|-----|-----------|-------------|-----------|-------------|
| — (신규 설치 없음) | — | — | — | — | — | N/A |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
data/fundamentals.db (raw_facts)            [Phase 7 산출 — 입력]
   │  SELECT (ticker, source, quarter, field, value, period_type, reprt_code, unit, accession)
   ▼
┌────────────────────────────────────────────────────────────┐
│ metrics_engine.py — 분기 매트릭스 계산 (순수)                  │
│                                                              │
│  1. 조회: store.fetch_raw_quarters(ticker)                   │
│         → {(quarter, field): cell(value, source)}            │
│                                                              │
│  2. source별 분기 정규화 (as-reported → canonical 분기값)      │
│     ├ EDGAR 손익: 3개월 duration 그대로. Q4 = 갭(아래 Pitfall1)│
│     ├ DART 손익: thstrm_amount 의미 확정 후 분기값화(Pitfall2) │
│     └ 저량(BS/instant): 분기말 시점값 그대로                   │
│                                                              │
│  3. 분기별 산출 ── registry 순회 (metrics_registry.MetricDef) │
│     ├ 저량   → 해당 분기 최근값                                │
│     ├ 유량   → TTM = 직전 4분기 합 (4개 모두 있을 때만, SC4)   │
│     └ 하이브리드 → 분자 TTM ÷ 분모 최근값 (D-03)              │
│                                                              │
│  4. per-share 분모 산출 (가격 비의존, D-07)                    │
│     EPS_ttm / BPS / SPS / OCF-ps  ← shares_outstanding       │
│                                                              │
│  5. sanity bounds 게이트 → 범위 밖 = 빈값+사유 / 경고 라벨     │
│                                                              │
│  6. provenance 병합 (metric별 사용 raw field source 라벨)      │
└────────────────────────────────────────────────────────────┘
   │  MetricMatrix: {metric: {quarter: MetricCell}}  +  per-share 분모
   ▼
호출자가 가격 주입 (Phase 8 밖)
   ├ Phase 9 렌더: 과거열=분기말 종가, 최신열=현재가 → 매트릭스 전체
   └ Phase 10 시트1: 최신열만, 현재가
```

### Recommended Project Structure

```
src/stocksig/io/
├── fundamentals_store.py    # [기존] raw_facts 조회 — 신규 SELECT 헬퍼 추가 (?바인딩)
├── metrics_registry.py      # [신규] MetricDef 9종 선언 + MetricType enum + source 매핑
├── metrics_engine.py        # [신규] 분기 매트릭스 계산 엔진 (순수 함수)
└── fundamentals.py          # [불변] 시트1 경로 — Phase 8은 건드리지 않음(통합은 Phase 10)
tests/
├── test_metrics_registry.py # [신규] registry 정의 무결성·신규 지표 추가 용이성
└── test_metrics_engine.py   # [신규] 유형별 계산·TTM 결손·Q4·per-share·sanity·provenance
```

### Pattern 1: 선언적 registry (MetricDef dataclass + MetricType enum)

**What:** 각 지표를 `{이름, 유형, 분자 field(s), 분모 field, 단위/비율}`로 선언. 산식은 유형 enum이 결정하고, 비표준 산식(PEG)만 callable.
**When to use:** 신규 지표 추가가 "원천만 있으면 즉시"여야 한다는 SC3·CONTEXT specifics 요구.
**Example:**
```python
# Source: 로컬 패턴(fundamentals.py MetricCell) + CONTEXT D-H2 registry 스키마
from dataclasses import dataclass
from enum import Enum

class MetricType(Enum):
    STOCK = "저량"        # 최근 분기값
    FLOW_TTM = "유량"     # 직전 4분기 합
    HYBRID = "하이브리드"  # 분자 TTM ÷ 분모 최근값
    PER_SHARE = "주당"     # 분모만 노출(가격 호출자 주입, D-07)
    DERIVED = "파생"       # 다른 metric에서 2차 계산(PEG)

@dataclass(frozen=True)
class MetricDef:
    name: str                 # "ROE", "GPM", ...
    mtype: MetricType
    numerator: str | None     # raw field 논리명 (예 "net_income")
    denominator: str | None   # raw field 논리명 (예 "total_equity")
    is_ratio_0_1: bool = False # GPM/OPM 등 0~1 비율 sanity 게이트용
    # source별 원천필드는 기존 dart_account_map / edgar concept 매핑 재사용

REGISTRY: tuple[MetricDef, ...] = (
    MetricDef("GPM", MetricType.FLOW_TTM, "gross_profit", "revenue", is_ratio_0_1=True),
    MetricDef("OPM", MetricType.FLOW_TTM, "op_income", "revenue", is_ratio_0_1=True),
    MetricDef("ROE", MetricType.HYBRID, "net_income", "total_equity"),
    MetricDef("ROA", MetricType.HYBRID, "net_income", "total_assets"),
    MetricDef("EPS_ttm", MetricType.FLOW_TTM, "net_income", "shares_outstanding"),  # PER 분모
    MetricDef("BPS", MetricType.STOCK, "total_equity", "shares_outstanding"),        # PBR 분모
    MetricDef("SPS", MetricType.FLOW_TTM, "revenue", "shares_outstanding"),          # PSR 분모
    MetricDef("OCF_ps", MetricType.FLOW_TTM, "operating_cash_flow", "shares_outstanding"),  # PCR 분모
    # PER/PBR/PCR/PSR 자체 = 가격÷분모 → 호출자(D-07). PEG = DERIVED(PER, EPS 성장률).
)
```
> 주의: EPS는 raw에 `eps`(주당) field로도 저장됨. EPS_ttm을 `net_income TTM ÷ shares`로 재계산할지 `eps` 분기값 4합으로 할지는 planner 결정 — 후자는 EDGAR가 EPS를 per-share로 보고하므로 합산이 회계적으로 부정확(주식수 변동 시). **권장: net_income TTM ÷ 최근 shares** 또는 분기별 eps 단독값 4합. raw 진실 확정 후 결정.

### Pattern 2: 유형별 계산 엔진 (순수 함수)

**What:** registry 항목 + 분기 정렬된 raw → 분기별 MetricCell. 유형이 합산 규칙을 분기.
**Example:**
```python
# Source: CONTEXT D-H2 유형 정의 + SC2/SC4
def compute_cell(mdef, quarter, raw_by_qf):
    if mdef.mtype is MetricType.STOCK:
        num = _recent(raw_by_qf, mdef.numerator, quarter)   # 해당 분기 최근값
        den = _recent(raw_by_qf, mdef.denominator, quarter)
    elif mdef.mtype is MetricType.FLOW_TTM:
        num = _ttm_sum(raw_by_qf, mdef.numerator, quarter)   # 직전 4분기 합(결손 시 None)
        den = _recent(raw_by_qf, mdef.denominator, quarter)  # 분모가 shares면 최근값
    elif mdef.mtype is MetricType.HYBRID:
        num = _ttm_sum(raw_by_qf, mdef.numerator, quarter)   # 분자 TTM
        den = _recent(raw_by_qf, mdef.denominator, quarter)  # 분모 최근값 (D-03)
    return _ratio_cell(num, den, mdef)  # _is_missing 게이트 + sanity bounds
```

### Pattern 3: TTM 4분기 합 + 결손 빈값 정책 (SC4 — 핵심)

**What:** 직전 4분기(현 분기 포함 q, q-1, q-2, q-3)가 **모두 존재할 때만** 합산. 하나라도 결손이면 빈값+사유.
```python
# Source: CONTEXT SC4 / D-05 (부분합산 금지, 0 대체 금지)
def _ttm_sum(raw_by_qf, field, quarter):
    qs = _prior_4_quarters(quarter)          # ["2026Q2","2026Q1","2025Q4","2025Q3"]
    vals = [raw_by_qf.get((q, field)) for q in qs]
    if any(_is_missing(v) for v in vals):    # 4분기 중 하나라도 결손 → 전체 빈값
        return None                          # 호출부가 "TTM 결손: N개 분기 누락" 사유 부여
    return sum(vals)
```
> `_prior_4_quarters`는 캘린더 분기 키 산술 필요: "2026Q1" → "2025Q4". 헬퍼 1개 추가(분기 라벨 ±N). pandas `PeriodIndex(freq="Q")`로도 가능하나 stdlib 산술이 더 명시적.

### Pattern 4: per-share 분모 / 가격 주입 분리 (D-07)

**What:** registry는 EPS_ttm·BPS·SPS·OCF-ps를 분기별로 산출만. PER/PBR/PCR/PSR 비율은 노출하지 않거나 `compute_ratio(metric, price, quarter)` 함수로 호출자가 price를 넘김.
```python
# Source: CONTEXT D-07
def price_ratio(denom_cell, price):
    if _is_missing(denom_cell.value) or denom_cell.value <= 0 or _is_missing(price):
        return MetricCell(None, denom_cell.source, "조회 실패: 분모 미존재/≤0 또는 가격 없음")
    return MetricCell(price / denom_cell.value, denom_cell.source, denom_cell.note)
```
> Phase 9는 과거 분기에 분기말 종가를, 최신 분기에 현재가를 주입. Phase 10은 최신 분기에 현재가만. OHLCV 10년치는 이미 파이프라인에 존재(CONTEXT).

### Pattern 5: per-metric provenance 병합 (D-08, Discretion)

**What:** metric이 복수 raw field를 쓰고 source가 다를 때(예 ROE: net_income=DART, total_equity=DART) 라벨 규칙.
**권장 규칙:** 모든 입력 field source가 동일 → 그 source. 혼합 → `"+"` 결합("EDGAR+yf") 또는 주 source 우선 + note에 보조. 결손 분기가 끼면 note에 사유. `MetricCell.source`/`note` 구조 재사용.

### Anti-Patterns to Avoid

- **TTM에 pandas `rolling(4).sum()` 무비판 적용:** 기본 `min_periods` 설정에 따라 부분합산(결손 분기를 0 취급)될 수 있음 → SC4 위반. 결손 게이트를 명시적으로 두라.
- **결손 0 대체:** D-05 절대 금지. `_is_missing`(None|NaN) 단일 게이트로 차단(기존 WR-01 패턴).
- **as-reported raw 변형 저장:** 분기 분해·Q4 보정은 **계산 시점만** 수행, `raw_facts`는 불변(Phase 7 D-05).
- **registry가 외부 fetch 호출:** D-09 위반. registry는 store만 읽는다.
- **EPS per-share 값 단순 4합으로 TTM:** 주식수 변동 시 부정확. net_income TTM ÷ shares 권장(아래 Open Question).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 결손 게이트(None/NaN) | 새 None 체크 산재 | `fundamentals.py._is_missing` 재사용/이식 | NaN이 `is None` 통과해 새는 버그(WR-01) 이미 해결됨 |
| 셀 모델(값+출처+사유) | 새 dataclass | `MetricCell(value, source, note)` 재사용 | Phase 10 시트1 계약과 동일 구조 → 이관 마찰 0 |
| DB 조회·동시성 | 새 connection | `fundamentals_store.get_store()` + 신규 SELECT 헬퍼 | WAL/busy_timeout/락 이미 구축. ASVS V5 `?` 바인딩 패턴 존재 |
| source별 원천필드 매핑 | 새 매핑 dict | `dart_account_map.py` + `edgar_client._EDGAR_*_CONCEPTS` | SC1 "기존 매핑을 시작점으로" 명시 |
| 비율/마진 산식 | 새 산식 | `_compute_margin`/`_compute_per`/`_compute_peg` 산식 이식 | 엣지케이스·한국어 사유 검증됨(재현 대상 기준) |

**Key insight:** Phase 8의 위험은 "새 코드"가 아니라 **"분기값의 의미를 잘못 해석하는 것"**(EDGAR Q4·DART 분기/누적). 산식은 trivial하고 인프라는 재사용 가능 — 연구 노력의 90%는 raw 분기값의 정확한 의미 확정에 써야 한다.

## Runtime State Inventory

> 본 phase는 **순수 계산 층(신규 모듈 추가, raw 불변)** 이므로 rename/migration 아님. 그러나 입력 raw의 의미·완전성이 산출 정확도를 좌우하므로 "저장 raw 진실" 인벤토리를 대신 수행한다.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data (입력 raw) | `data/fundamentals.db raw_facts`: field ∈ {revenue, gross_profit, op_income, net_income, eps, operating_cash_flow, total_equity, total_liabilities, total_assets, shares_outstanding}. EDGAR 손익=3개월 duration(`by_period_length(3)`), DART 손익=`thstrm_amount`(의미 미확정), BS=instant | **2건 실데이터 확인 필요**(아래 Open Q1·Q2) — 코드 변경 전 진실 확정 |
| EDGAR Q4 손익 | **저장 raw에 부재** — `by_period_length(3)`만 추출 → Q4 단독값 없음, FY(12개월) duration도 미저장 | planner 결정 필요: (a) Phase 7 추출에 FY duration 추가(별도 미니 작업) / (b) Q4 행은 빈값+사유로 두기 / (c) FY−9M 보정 불가 명시 |
| DART shares_outstanding | finstate_all 통상 부재(dart_account_map.py placeholder) → KR PBR/PSR/PCR 분모 결손 가능 | KR per-share 지표는 결손+사유 흔할 것. planner가 yf shares 보완 위임 여부 결정(D-09: 보완 fetch는 Phase 10) |
| Live service config | None — 외부 서비스·UI 설정 없음(로컬 SQLite 계산만) | None |
| OS/Secrets/Build | None — registry는 키·OS 등록 상태 불사용. set_identity/API키는 Phase 8 경로 미진입 | None — 확인됨 |

**핵심 질문:** raw_facts에 저장된 각 source의 분기 `value`는 **분기 단독값인가 누적값인가?** 이것이 TTM 합산·Q4 보정의 옳고 그름을 전부 결정한다.

## Common Pitfalls

### Pitfall 1: EDGAR Q4 손익 단독값이 raw에 없음 (HIGH 위험)
**What goes wrong:** US 종목의 Q4 유량 지표(GPM/OPM/매출 TTM 등)가 영구 결손되거나, 잘못 보정됨.
**Why it happens:** 미국 10-K는 연간(FY, 12개월 duration)만 XBRL 보고 — Q4 3개월 duration fact가 존재하지 않음 [VERIFIED: edgartools docs `by_period_length` + SEC 10-K/10-Q 구조, web]. 현 추출기는 `by_period_length(3)`만 저장 → **Q4 단독값도 FY값도 raw에 없음** [VERIFIED: edgar_client.py L206].
**How to avoid:** Q4 = FY − (Q1+Q2+Q3). 단, FY duration fact가 raw에 있어야 가능. 현재 없음 → planner가 (a) FY 저장 추가 또는 (b) Q4 빈값+사유 중 택1. non-calendar fiscal year 종목(예 AAPL 9월 결산)은 `get_display_period_key()`가 이미 캘린더 분기로 정규화(D-08) → Q4 보정 시에도 캘린더 분기 정렬 유지 확인.
**Warning signs:** US 종목 매트릭스에서 매년 4분기째 유량 지표만 빈값 / TTM이 4분기 경계마다 점프.

### Pitfall 2: DART thstrm_amount의 분기 vs 누적 의미 혼동 (HIGH 위험 — Phase 7 가정과 충돌)
**What goes wrong:** DART 손익 TTM이 2~4배 과대/과소 계산됨.
**Why it happens:** 프로젝트 전반은 "DART 손익=YTD 누적 → thisQ−직전Q 분해 필요"로 전제(STATE.md L64·백로그 D-H2·07-CONTEXT D-05·dart_client.py L224·L261 주석). 그러나 OpenDART 공식 가이드(DS003 단일회사 전체 재무제표)는 **"분/반기 보고서이면서 (포괄)손익계산서일 경우 `thstrm_amount`는 [3개월] 금액"** — 즉 분기 단독값, 누적은 `thstrm_add_amount` 별도 컬럼 [CITED: opendart.fss.or.kr/guide/detail.do DS003]. 현 추출기는 `thstrm_amount`만 저장(dart_client.py `_match_amount` 기본 `column="thstrm_amount"`) → **저장값이 이미 분기 단독일 가능성 높음**.
**How to avoid:** **착수 전 005930 반기(11012)·3분기(11014) 실호출 1회**로 thstrm_amount가 분기값인지 누적인지 확정(Open Q1). 결과에 따라:
- 분기 단독값 확정 → DART도 EDGAR처럼 단순 4분기 합 TTM. "YTD 분해" 작업 **삭제**(SC 산식 단순화).
- 만약 누적값으로 확인되면 → thisQ누적 − 직전Q누적 분해(11013=Q1단독, 11012=H1누적, 11014=9M누적, 11011=FY누적; Q2=11012−11013, Q3=11014−11012, Q4=11011−11014). 직전 분기 결손 시 해당 분기 빈값+사유.
**reprt_code↔분기:** 11013=1분기, 11012=반기, 11014=3분기, 11011=사업보고서(연간) [CITED: opendart.fss.or.kr; 로컬 `_REPRT_TO_QUARTER` 일치]. 현 코드는 11012→Q2, 11014→Q3, 11011→Q4 캘린더 매핑.
**Warning signs:** KR 종목 매출 TTM이 동일 종목 EDGAR 미국 동종 대비 비현실적 / GPM/OPM이 0~1 범위를 크게 벗어남.

### Pitfall 3: TTM 부분 합산 (SC4 위반)
**What goes wrong:** 4분기 중 1개 결손인데 3개만 합산해 "그럴듯하지만 틀린" TTM 산출.
**Why it happens:** pandas `rolling(4).sum(min_periods=1)` 또는 결손=0 취급.
**How to avoid:** Pattern 3 — `any(_is_missing)` 시 전체 None+사유. 0 대체 절대 금지(D-05).
**Warning signs:** TTM이 분기 결손 구간에서 부드럽게 이어짐(점프·빈칸 없이) = 부분합산 의심.

### Pitfall 4: shares_outstanding 결손으로 per-share 지표 광범위 빈값
**What goes wrong:** PBR/PSR/PCR가 KR 종목 대부분에서 빈값.
**Why it happens:** DART finstate_all에 발행주식수 통상 부재(dart_account_map.py L66 placeholder). EDGAR는 `shares_outstanding_fact` 있으면 저장.
**How to avoid:** per-share 분모는 shares 결손 시 빈값+"발행주식수 미존재" 사유(정상 동작). KR shares 보완(yf)은 D-09상 Phase 10 오케스트레이션 책임 — Phase 8은 결손 수용만.
**Warning signs:** KR PBR/PSR/PCR 열 전체 빈값 — 예상된 동작(버그 아님). note로 사유 명확화.

### Pitfall 5: 캘린더 분기 키 산술 오류
**What goes wrong:** `_prior_4_quarters("2026Q1")`이 "2025Q4"가 아닌 "2026Q0" 등 잘못 산출 → TTM 분기 누락.
**How to avoid:** 분기 라벨 ±N 헬퍼를 단위 테스트로 경계 검증(Q1→직전=전년 Q4). pandas `pd.Period(q, freq="Q")` 활용 가능.

## Code Examples

### raw_facts 조회 헬퍼 (store에 추가, ASVS V5 `?` 바인딩)
```python
# Source: 로컬 fundamentals_store.py 기존 SELECT 패턴(L139, L158)
def fetch_raw_quarters(ticker: str) -> list[tuple]:
    """ticker의 전 분기 raw 행. (quarter, source, field, value, period_type, reprt_code, unit)."""
    cur = get_store().execute(
        "SELECT quarter, source, field, value, period_type, reprt_code, unit "
        "FROM raw_facts WHERE ticker=? ORDER BY quarter",
        (ticker,),
    )
    return cur.fetchall()
```

### 결손 게이트 + 비율 셀 (기존 패턴 이식)
```python
# Source: 로컬 fundamentals.py _is_missing(L72) + _compute_margin(L112)
def _ratio_cell(numer, denom, mdef):
    if _is_missing(numer):
        return MetricCell(None, None, "조회 실패: 분자(원천) 미존재")
    if _is_missing(denom) or denom == 0:
        return MetricCell(None, None, "조회 실패: 분모(원천) 미존재/0")
    value = numer / denom
    if mdef.is_ratio_0_1 and not (-0.5 <= value <= 1.5):  # sanity (아래 표)
        return MetricCell(None, None, f"sanity 범위 밖: {value:.3f}")
    return MetricCell(value, None, None)
```

## Sanity Bounds 권고 (D-05 — 정확 일치 대신 합리 범위)

> 목적: 분기값 의미 오해(Pitfall 1·2)·단위 오류·이상치를 빈값+사유로 차단. **하한/상한 밖 = 빈값+사유(권장)** 또는 경고 라벨(planner 선택). 모두 ASSUMED 기본값 — planner/사용자가 조정 가능.

| 지표 | 유형 | 권장 sanity 범위 | 음수 처리 | 근거(ASSUMED) |
|------|------|----------------|----------|--------------|
| GPM | 유량비율 | 0 ~ 1 (여유 -0.5~1.5) | 음수=원가>매출(드묾) → 경고 | 마진은 본질적으로 0~1; 음수는 적자/특이 |
| OPM | 유량비율 | -1 ~ 1 (여유 -2~1.5) | 음수 허용(영업적자 흔함) | 영업이익률 음수 정상 |
| ROE | 하이브리드 | -2 ~ 2 (±200%) | 음수 허용(순손실) | 극단 ROE(자본 0근접)는 노이즈 → 캡 |
| ROA | 하이브리드 | -1 ~ 1 (±100%) | 음수 허용 | 총자산 대비 → ROE보다 좁음 |
| PER | 가격÷EPS | 0 < PER < ~1000 | EPS≤0 → 빈값("EPS≤0", 기존 산식) | 음수 PER=적자 → 표시 안 함(기존 정책) |
| PEG | 파생 | 0 < PEG < ~10 | 성장률≤0 → 빈값(기존) | 기존 _compute_peg 엣지케이스 재사용 |
| PBR | 가격÷BPS | 0 < PBR < ~100 | BPS≤0(자본잠식) → 빈값 | 자본잠식 종목 PBR 무의미 |
| PSR | 가격÷SPS | 0 < PSR < ~100 | SPS≤0 → 빈값 | 매출 음수 불가 |
| PCR | 가격÷OCF-ps | OCF-ps≠0; 음수 OCF면 빈값+사유 권장 | 음수 OCF=현금소진 → 비율 무의미 | OCF 음수 시 PCR 해석 불가 |

> **권장 적용 방식:** 비율 0~1 강제(GPM)는 엄격, 나머지는 "극단 캡(빈값)"으로. 단위 오류 탐지가 1차 목적이므로 느슨한 여유 범위로 시작하고 실데이터 분포 보며 조이기.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| edgartools `get_ttm()` accessor(라이브러리 TTM) — 시트1 현 경로 | 저장 raw 4분기 직접 합산(registry canonical) | Phase 8(D-04) | 미세 차이 가능 — D-05상 수용. Phase 10에서 시트1 표시값 약간 변동 문서화 |
| "DART 손익=YTD 누적" 가정 | OpenDART 공식: finstate_all thstrm_amount=분기 단독값(누적은 thstrm_add_amount) | 본 연구(2026-06-19) | **분기 분해 작업이 불필요할 수 있음 — 실데이터 확인 후 확정** |

**Deprecated/outdated:**
- "DART YTD 분해(thisQ−직전Q)" 작업 — 공식 가이드상 `thstrm_amount` 사용 시 불필요할 가능성. 단정 금지, Open Q1로 검증.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | DART finstate_all `thstrm_amount`(손익, 분/반기)는 분기 단독 3개월 값 (누적 아님) | Pitfall 2 / State of Art | **HIGH** — 틀리면 DART TTM 전부 오계산. 실데이터 1회 확인 필수(Open Q1) |
| A2 | EDGAR raw에 Q4·FY 손익 duration 미저장 → Q4 보정 불가(현 raw만으로) | Pitfall 1 / Runtime Inventory | **HIGH** — US Q4 유량 지표 정확도. 실데이터 확인(Open Q2) |
| A3 | sanity bounds 권장 임계값(GPM 0~1, ROE ±200% 등) | Sanity Bounds 표 | MEDIUM — 너무 엄격하면 정상값 탈락. 느슨하게 시작 권장 |
| A4 | EPS_ttm = net_income TTM ÷ 최근 shares 권장(eps per-share 4합 부정확) | Pattern 1 주석 / Open Q3 | MEDIUM — PER 분모 정의. raw 진실 확정 후 결정 |
| A5 | KR shares_outstanding 결손 흔함 → KR per-share 지표 빈값 정상 | Pitfall 4 | LOW — 예상 동작. yf 보완은 Phase 10 |
| A6 | provenance 혼합 source는 "+" 결합 라벨 | Pattern 5 | LOW — 표시 규칙, 계산 무영향 |

## Open Questions

1. **DART `thstrm_amount`는 분기값인가 누적값인가?** (최우선)
   - 알고 있는 것: 공식 가이드는 "분/반기 손익=3개월 값"[CITED]. 현 추출기는 `thstrm_amount`만 저장.
   - 불명: 실제 OpenDartReader 0.3.x finstate_all 응답에서 005930 반기/3분기 손익이 단독값으로 오는지(라이브러리가 컬럼을 가공하지 않는지).
   - 권장: planner가 첫 task로 005930 reprt_code=11012(반기)·11014(3분기) 1회 실호출 → revenue thstrm_amount가 분기값(≈한분기)인지 누적(≈2·3분기)인지 단언하는 spike/test. 결과로 "YTD 분해" 작업 채택/삭제 결정.

2. **EDGAR raw에 FY/Q4 손익이 있는가?** (최우선)
   - 알고 있는 것: 추출기 `by_period_length(3)`만 → 3개월 fact만. FY는 12개월 duration.
   - 불명: 저장된 raw에 Q4 캘린더 분기 행이 존재하는지(0행이면 Q4 영구 결손).
   - 권장: 실 DB(또는 AAPL backfill) 1회 조회 — `SELECT DISTINCT quarter FROM raw_facts WHERE ticker='AAPL' AND field='revenue'`로 Q4 누락 확인. 누락이면 (a) Phase 7 추출에 FY duration 1줄 추가 / (b) Q4 빈값+사유 정책 중 택1.

3. **EPS_ttm 산식: net_income TTM ÷ shares vs eps 분기값 4합?**
   - 알고 있는 것: raw에 `eps`(per-share) + `net_income` 둘 다 저장. EDGAR `eps`는 per-share, 합산은 주식수 변동 시 부정확.
   - 권장: net_income TTM ÷ 최근 shares 우선. 단, 기존 시트1 PER는 edgartools `get_ttm("EPS")` → 재현 정합은 D-05상 sanity만. planner가 둘 중 택1 후 sanity 비교.

4. **Q4 보정 raw 갭 처리 방침** (Open Q2 연계)
   - FY duration 저장을 Phase 8이 추가할지(Phase 7 추출 수정 = scope 경계 모호) vs Q4 빈값 수용. 사용자/planner 결정 필요.

## Environment Availability

> 본 phase는 외부 의존(네트워크·서비스)이 없는 순수 계산 층. 입력은 로컬 SQLite.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| python (uv-managed) | 전체 | ✓ | uv 0.11.15 관리 (PATH엔 미노출) | `uv run python` |
| pandas | 분기 매트릭스 | ✓ | 3.0.3 | dict 기반 수동 합 |
| numpy | NaN 게이트 | ✓ | 2.4.6 | math.isnan |
| sqlite3 | raw 조회 | ✓ | stdlib | — |
| pytest / pytest-mock / freezegun | 테스트 | ✓ | pytest 8+ | — |
| data/fundamentals.db (raw 입력) | 계산 입력 | △ | Phase 7 산출 — 실행 시 생성 | 테스트는 격리 tmp DB(conftest `_isolated_fundamentals_db`) |

**Missing dependencies with no fallback:** 없음.
**Missing dependencies with fallback:** 실 DB raw는 종목 backfill 실행 후 채워짐 — 테스트는 fixture/격리 DB로 충분.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8+ (+ pytest-mock, freezegun) [VERIFIED: pyproject.toml] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| Quick run command | `uv run pytest tests/test_metrics_engine.py -x -q` |
| Full suite command | `uv run pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUND-09 | registry에 9종 MetricDef 정의·유형 정확 | unit | `uv run pytest tests/test_metrics_registry.py -x` | ❌ Wave 0 |
| FUND-09 (SC1) | 소스별 원천필드가 dart_account_map/edgar concept에 연결 | unit | `uv run pytest tests/test_metrics_registry.py -k mapping` | ❌ Wave 0 |
| FUND-09 (SC2) | 저량=최근값/유량=TTM 4합/하이브리드=분자TTM÷분모최근 | unit | `uv run pytest tests/test_metrics_engine.py -k type_rules` | ❌ Wave 0 |
| FUND-09 (SC3) | 저장 raw만으로 PER/PEG/GPM/OPM 재현 + ROE/PBR 신규 산출 | unit | `uv run pytest tests/test_metrics_engine.py -k reproduce` | ❌ Wave 0 |
| FUND-09 (SC4) | TTM 4분기 중 결손 → 빈값+사유, 0 대체 안 됨, 부분합산 안 됨 | unit | `uv run pytest tests/test_metrics_engine.py -k ttm_missing` | ❌ Wave 0 |
| FUND-09 (SC5) | per-metric provenance 라벨 + per-share 분모/가격 주입 분리 | unit | `uv run pytest tests/test_metrics_engine.py -k provenance_or_pershare` | ❌ Wave 0 |
| (Open Q1) | DART thstrm_amount 분기/누적 의미 spike | unit(spike) | `uv run pytest tests/test_metrics_engine.py -k dart_quarter_semantics` | ❌ Wave 0 |
| (Pitfall 1) | EDGAR Q4 raw 갭 — Q4 빈값+사유 또는 FY−9M 보정 | unit | `uv run pytest tests/test_metrics_engine.py -k edgar_q4` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_metrics_engine.py tests/test_metrics_registry.py -x -q`
- **Per wave merge:** `uv run pytest -q` (전 스위트 — 기존 fundamentals/store/delta 회귀 포함)
- **Phase gate:** Full suite green before `/gsd:verify-work`. 시트1 회귀(test_sheet_portfolio·test_history_integration) 반드시 그린(Core Value 불변).

### Wave 0 Gaps
- [ ] `tests/test_metrics_registry.py` — registry 정의 무결성·소스 매핑·신규 지표 추가 용이성 (FUND-09 SC1)
- [ ] `tests/test_metrics_engine.py` — 유형별 계산/TTM 결손/Q4/DART 분기의미/per-share/sanity/provenance (FUND-09 SC2~5)
- [ ] fixture: 분기 raw 행 builder (EDGAR 3개월·DART 분기·BS instant·결손 분기 포함) — `tests/fixtures/`에 추가
- [ ] (선택) 실데이터 spike 스크립트: 005930 반기/3분기 thstrm_amount 의미 확인 (Open Q1) — 1회용, 네트워크 사용 → 별도 마킹

## Security Domain

> `security_enforcement` 키 부재 → 활성으로 간주. 본 phase는 네트워크·인증·사용자 입력 없는 순수 계산 — 표면이 좁다.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 8 경로는 EDGAR/DART 인증 미진입(저장 raw만 읽음) |
| V3 Session Management | no | 세션 없음 |
| V4 Access Control | no | 로컬 단일 사용자 도구 |
| V5 Input Validation | yes | raw 조회 SQL은 `?` 파라미터 바인딩만(기존 store 패턴). field/ticker 문자열 f-string SQL 금지 |
| V6 Cryptography | no | 암호 미사용 |

### Known Threat Patterns for 본 stack

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection (ticker/field 보간) | Tampering | `?` 바인딩 강제(store 헬퍼). 기존 `fundamentals_store` 전 SQL 바인딩 준수 |
| API 키 누설 | Info Disclosure | 해당 없음 — registry는 API 미호출. (기존 fundamentals.py T-04-03 예외 원문 보간 금지 패턴은 Phase 10 통합 시만 관련) |
| 결손 0 오염 → 잘못된 매매 신호 | (데이터 무결성) | D-05 결손=None 게이트(`_is_missing`). 0/-999999 sentinel 금지 — Core Value(색 신호) 정확성 보호 |

## Project Constraints (from CLAUDE.md)

- Tech stack = Python(표준 라이브러리 + pandas/numpy). 신규 외부 라이브러리 도입 지양 — 본 phase는 부합(신규 0).
- 결손 = `None` (0/-999999 금지). registry 산출 전면 적용.
- 언어 = 한국어 우선(로그·사유 note). MetricCell.note는 한국어.
- Windows 로컬 실행. 경로·동시성은 기존 store(WAL/락) 재사용.
- GSD Workflow: Edit/Write는 GSD 명령(`/gsd-execute-phase`) 경유.
- 단일 `.xlsx` 출력·Core Value(시트1 색 신호) 불변 — Phase 8은 시트1 미접촉(통합은 Phase 10).

## Sources

### Primary (HIGH confidence)
- 로컬 코드: `fundamentals_store.py`, `fundamentals.py`, `edgar_client.py`, `dart_client.py`, `dart_account_map.py` — 직접 read [VERIFIED]
- CONTEXT/STATE/ROADMAP/REQUIREMENTS/백로그 — 직접 read [VERIFIED]
- `uv pip list` — pandas 3.0.3 / numpy 2.4.6 / edgartools 5.35.0 [VERIFIED]
- pyproject.toml — pytest 설정·의존 [VERIFIED]
- [OpenDART 개발가이드 DS003 단일회사 전체 재무제표](https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020) — thstrm_amount=분기 3개월값, thstrm_add_amount=누적, reprt_code 의미 [CITED]

### Secondary (MEDIUM confidence)
- [edgartools EntityFacts/Query 문서](https://edgartools.readthedocs.io/en/latest/xbrl-querying/) — by_period_length 3개월 필터, 분기 fact 의미
- [SEC 10-K/10-Q 구조 (StockFit blog)](https://developer.stockfit.io/blog/sec-forms-explained) — Q4=FY−9M 관행, 10-K가 연간 보고

### Tertiary (LOW confidence)
- WebSearch reprt_code 매핑 결과 — 일부 혼동(11014를 명확히 3분기로 기술하지 않음) → 공식 가이드·로컬 `_REPRT_TO_QUARTER`로 교차 확정함

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 신규 의존 0, 설치 버전 직접 확인
- Architecture(registry/엔진 패턴): HIGH — 로컬 MetricCell/store 패턴 + CONTEXT D-H2 스키마 직접 기반
- 산식 정확성(EDGAR Q4·DART 분기의미): MEDIUM — 공식 가이드로 방향 확정했으나 실데이터 1회 검증 권장(Open Q1·Q2가 산식의 옳고 그름 좌우)
- sanity bounds: MEDIUM(ASSUMED 임계 — 느슨하게 시작·실분포로 조정)
- Pitfalls: HIGH — Q4 갭·DART 의미는 코드·공식 가이드 교차로 확인

**Research date:** 2026-06-19
**Valid until:** 2026-07-19 (안정 — stdlib/기존 라이브러리. 단 OpenDART/edgartools 응답 형식 변동 시 Open Q 재확인)
