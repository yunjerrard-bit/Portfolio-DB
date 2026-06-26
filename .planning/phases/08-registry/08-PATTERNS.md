# Phase 8: 지표 registry 계산 - Pattern Map

**Mapped:** 2026-06-19
**Files analyzed:** 4 (신규 2 모듈 + 신규 2 테스트) + 1 수정(store SELECT 헬퍼 추가)
**Analogs found:** 5 / 5 (전 신규 파일에 강한 코드베이스 analog 존재 — 신규 외부 의존 0)

> 핵심: Phase 8은 새 라이브러리가 없는 순수 계산 층이다. 거의 모든 패턴이 기존
> `fundamentals.py`(셀 모델·결손 게이트·산식)·`fundamentals_store.py`(조회·동시성)·
> `dart_account_map.py`(소스별 매핑 dict)·기존 테스트(mock 주입·fixture)에서 그대로
> 복사된다. 플래너는 "새 패턴 발명"이 아니라 "기존 패턴 이식"으로 계획해야 한다.

---

## File Classification

| 신규/수정 파일 | Role | Data Flow | Closest Analog | Match Quality |
|----------------|------|-----------|----------------|---------------|
| `src/stocksig/io/metrics_registry.py` (신규) | config/registry (선언적 메타데이터) | transform (정적 정의) | `src/stocksig/io/dart_account_map.py` (소스별 매핑 dict) + `fundamentals.py` MetricCell | exact (역할·구조 일치) |
| `src/stocksig/io/metrics_engine.py` (신규) | service (순수 계산 엔진) | transform / batch (raw rows → 분기 매트릭스) | `src/stocksig/io/fundamentals.py` (`_compute_*`·`_is_missing`·`MetricCell`) | exact (산식·셀 모델 재현 대상) |
| `src/stocksig/io/fundamentals_store.py` (수정 — SELECT 헬퍼 추가) | model/store (SQLite 조회) | request-response (DB read) | 동일 파일 기존 `count_rows`/`get_last_accession` SELECT 패턴 | exact (self-analog) |
| `tests/test_metrics_registry.py` (신규) | test (unit) | request-response | `tests/test_fundamentals.py` (순수 헬퍼 단언) | exact |
| `tests/test_metrics_engine.py` (신규) | test (unit, mock 주입 + fixture) | request-response | `tests/test_fundamentals.py` + `tests/test_dart_quarterly.py` (fixture builder) + `conftest.py` (`_isolated_fundamentals_db`) | exact |

---

## Pattern Assignments

### `src/stocksig/io/metrics_registry.py` (config/registry, transform)

**Analog:** `src/stocksig/io/dart_account_map.py` (소스별 매핑 dict 패턴) + `src/stocksig/io/fundamentals.py` (MetricCell dataclass)

**모듈 상수 dict 패턴** — `dart_account_map.py` L31-72. registry의 source별 원천필드
매핑은 이 dict-of-tuple 구조를 그대로 따른다. 신규 매핑 dict를 만들지 말고 이 두
dict(`DART_ACCOUNT_ID_MAP`/`DART_ACCOUNT_MAP`)와 `edgar_client._EDGAR_DURATION_CONCEPTS`
/`_EDGAR_INSTANT_CONCEPTS`를 **시작점으로 재사용**(SC1, RESEARCH "Don't Hand-Roll").

```python
# Source: dart_account_map.py L31-50 — 논리 field명 → 소스별 태그 tuple
DART_ACCOUNT_ID_MAP: dict[str, tuple[str, ...]] = {
    "revenue": ("ifrs-full_Revenue", "dart_OperatingRevenue", ...),
    "net_income": ("ifrs-full_ProfitLoss", ...),
    "total_equity": ("ifrs-full_Equity", ...),
    ...
}
```

```python
# Source: edgar_client.py L100-114 — (concept, 논리 field) tuple 매핑
_EDGAR_DURATION_CONCEPTS = (("Revenue","revenue"), ("NetIncomeLoss","net_income"), ...)
_EDGAR_INSTANT_CONCEPTS  = (("StockholdersEquity","total_equity"), ("Assets","total_assets"), ...)
```

**MetricDef dataclass + frozen 패턴** — `fundamentals.py` L32-44 `MetricCell`의 `@dataclass`
스타일을 그대로 따른다(RESEARCH Pattern 1은 `@dataclass(frozen=True)` + `MetricType` enum
권장). 논리 field명("revenue","net_income","total_equity"...)은 이미 store/매핑이 쓰는
**동일 어휘**를 재사용한다 — fundamentals_store SCHEMA 주석 L57 `field` 열거와 일치.

```python
# Source: fundamentals.py L32-44 dataclass 스타일 (RESEARCH Pattern 1 확장)
from dataclasses import dataclass
from enum import Enum

class MetricType(Enum):
    STOCK = "저량"; FLOW_TTM = "유량"; HYBRID = "하이브리드"
    PER_SHARE = "주당"; DERIVED = "파생"

@dataclass(frozen=True)
class MetricDef:
    name: str
    mtype: MetricType
    numerator: str | None      # 논리 field명 (store field 어휘와 동일)
    denominator: str | None
    is_ratio_0_1: bool = False  # GPM/OPM sanity 게이트
```

**모듈 docstring 컨벤션** — `dart_account_map.py` L1-25 / `fundamentals_store.py` L1-20처럼
한국어 + locked decision 참조(D-01~D-09) + [VERIFIED] 라벨 스타일을 따른다.

---

### `src/stocksig/io/metrics_engine.py` (service, transform/batch)

**Analog:** `src/stocksig/io/fundamentals.py` (`_compute_per`/`_compute_peg`/`_compute_margin`·`_is_missing`·`MetricCell`)

**결손 게이트 (이식, 신규 작성 금지)** — `fundamentals.py` L72-78 `_is_missing`. None/NaN
단일 게이트(WR-01). 새 None 체크를 산재시키지 말고 이 함수를 재사용/이식(RESEARCH
"Don't Hand-Roll": NaN이 `is None` 통과해 새는 버그가 이미 해결됨).

```python
# Source: fundamentals.py L72-78
def _is_missing(x: float | None) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))
```

**셀 모델 재사용** — `fundamentals.py` L32-44 `MetricCell(value, source, note)`. 신규
dataclass를 만들지 말 것 — Phase 10 시트1 계약과 **동일 구조여야 이관 마찰 0**. `value=None`
= 결손(0/-999999 금지, D-05), `source`=provenance 라벨, `note`=한국어 사유.

**비율/마진 산식 (이식)** — `fundamentals.py` L112-118 `_compute_margin`. GPM/OPM/ROE/ROA
하이브리드 비율의 시작점. 분자 결손·분모 결손/0 → 빈값+한국어 사유 순서를 그대로 따른다.
PER/PEG는 L81-109 `_compute_per`/`_compute_peg`의 엣지케이스(EPS≤0·성장률≤0·전년EPS 0/None)를
재현 대상으로 삼는다.

```python
# Source: fundamentals.py L112-118 — 비율 셀 산식 + 결손 사유 (RESEARCH Code Example로 확장)
def _compute_margin(numer, denom) -> MetricCell:
    if _is_missing(numer):
        return _empty_cell("조회 실패: 분자 미존재")
    if _is_missing(denom) or denom == 0:
        return _empty_cell("조회 실패: 매출(분모) 미존재")
    return MetricCell(value=numer / denom, source=None, note=None)
```

```python
# Source: fundamentals.py L81-89 — 가격÷per-share 분모 산식(PER), D-07 price_ratio의 원형
def _compute_per(last_close, eps_ttm) -> MetricCell:
    if _is_missing(eps_ttm): return _empty_cell("조회 실패: EPS TTM 미존재")
    if eps_ttm <= 0:         return _empty_cell("조회 실패: EPS ≤ 0")
    if _is_missing(last_close): return _empty_cell("조회 실패: 종가 미존재")
    return MetricCell(value=last_close / eps_ttm, source=None, note=None)
```

**`_empty_cell` placeholder 헬퍼** — `fundamentals.py` L56-57. 결손 셀 생성 단일 헬퍼.
신규 엔진의 모든 빈값 경로(TTM 결손·sanity 밖·분모 0)가 이 패턴을 따른다.

**캘린더 분기 키 산술 (TTM 직전 4분기)** — RESEARCH Pattern 3 `_prior_4_quarters`. 코드베이스
analog: `dart_client.py` L187 `_REPRT_TO_QUARTER` + `_calendar_quarter_key`(L195),
`edgar_client.py` L117 `_calendar_quarter_key`가 모두 "YYYYQn" 캘린더 키를 생성한다.
신규 ±N 분기 산술 헬퍼는 이 "YYYYQn" 형식을 입출력으로 쓰고, `pd.Period(q, freq="Q")`
또는 stdlib 산술로 구현 — 경계(Q1→전년 Q4) 단위 테스트 필수(Pitfall 5).

**per-metric provenance 라우팅 (이식)** — `fundamentals.py` L153-176 (US) / L232-271 (KR).
"채운 지표에 source/note 부여" → "결손 지표만 보완" 루프 구조가 per-metric provenance의
표준 패턴. 단 Phase 8 엔진은 **fetch/폴백을 하지 않는다**(D-09) — 저장 raw의 `source`
라벨만 병합한다. 혼합 source는 "+" 결합(RESEARCH Pattern 5, fundamentals.py L289 `"+".join(used)` 패턴).

**Anti-pattern 차단(RESEARCH):** TTM은 pandas `rolling(4).sum()` 무비판 사용 금지(부분합산 →
SC4 위반) — `any(_is_missing)` 명시 게이트. as-reported raw 변형 저장 금지(분기 분해는 계산
시점만). registry가 외부 fetch 호출 금지(store만 read).

---

### `src/stocksig/io/fundamentals_store.py` (model/store — SELECT 헬퍼 추가)

**Analog:** 동일 파일 기존 SELECT 패턴 (self-analog)

raw 조회 헬퍼(`fetch_raw_quarters(ticker)`)는 신규 connection을 만들지 말고
`get_store()`(L107-120 더블체크 락 + WAL) + `?` 파라미터 바인딩(ASVS V5/T-07-01)을
그대로 따른다. analog = `count_rows`(L155-163)·`get_last_accession`(L137-144).

```python
# Source: fundamentals_store.py L155-163 (count_rows) / L139-144 (get_last_accession)
# 신규 헬퍼는 이 SELECT + ? 바인딩 + fetchall 패턴을 복제 (f-string SQL 금지)
def fetch_raw_quarters(ticker: str) -> list[tuple]:
    cur = get_store().execute(
        "SELECT quarter, source, field, value, period_type, reprt_code, unit "
        "FROM raw_facts WHERE ticker=? ORDER BY quarter",
        (ticker,),
    )
    return cur.fetchall()
```

> 필드 어휘는 SCHEMA L52-66 그대로: ticker/source/quarter/field/value/unit/accession/
> period_start/period_end/period_type/reprt_code. 결손 = NULL(D-05)이 그대로 Python None으로
> 읽혀 `_is_missing` 게이트에 직결된다.

---

### `tests/test_metrics_registry.py` (test, unit)

**Analog:** `tests/test_fundamentals.py` (순수 헬퍼 단언) + `tests/test_dart_quarterly.py` L45-52 (소스 문자열 단언)

순수 정의 무결성(9종 MetricDef 존재·유형 정확·소스 매핑 연결)은 `test_fundamentals.py`
L23-90 스타일의 작은 함수별 단언으로 작성. registry가 dart_account_map/edgar concept에
연결되는지(SC1)는 `test_dart_quarterly.py` L45-52처럼 import 후 키 존재 단언으로 검증.

```python
# Source: test_fundamentals.py L11-18 import + L23-27 단언 스타일
from stocksig.io.metrics_registry import REGISTRY, MetricType, MetricDef

def test_registry_has_nine_metrics():
    names = {m.name for m in REGISTRY}
    assert {"PER","PEG","GPM","OPM","PBR","PCR","PSR","ROE","ROA"} <= names

def test_roe_is_hybrid():
    roe = next(m for m in REGISTRY if m.name == "ROE")
    assert roe.mtype is MetricType.HYBRID
    assert roe.numerator == "net_income" and roe.denominator == "total_equity"
```

---

### `tests/test_metrics_engine.py` (test, unit — fixture builder + 격리 DB)

**Analog:** `tests/test_fundamentals.py` (헬퍼 단언) + `tests/test_dart_quarterly.py` L21-23 (fixture DataFrame builder) + `tests/conftest.py` L24-42 (`_isolated_fundamentals_db`)

**격리 DB(자동)** — `conftest.py` L24-42 `_isolated_fundamentals_db`는 autouse라 신규
테스트가 store를 쓰면 자동으로 tmp_path DB로 격리된다(추가 작업 불필요). store에 raw를
`upsert_quarters`로 심고 엔진을 돌리는 통합 스타일도 가능.

**fixture builder 패턴** — `test_fundamentals_store.py` L22-44 `_row(...)` 12-tuple 헬퍼가
분기 raw 행 builder의 직접 analog. RESEARCH Wave 0 Gap "분기 raw 행 builder(EDGAR 3개월·
DART 분기·BS instant·결손 분기 포함)"는 이 `_row` 디폴트-인자 팩토리 스타일로 작성.

```python
# Source: test_fundamentals_store.py L22-44 — 디폴트 인자 12-tuple 행 빌더
def _row(ticker="AAPL", source="EDGAR", quarter="2026Q1",
         field="revenue", value=1000.0, accession="acc-0001") -> tuple:
    return (ticker, source, quarter, field, value, "USD", accession,
            "2026-01-01", "2026-03-31", "duration", None, "2026-06-18T00:00:00")
```

**유형별 계산·TTM 결손 단언** — `test_fundamentals.py` L43-90 엣지케이스 단언 스타일.
SC4 TTM 결손(4분기 중 1개 None → 전체 빈값+사유, 부분합산 금지)·sanity bounds·provenance
병합을 각 `-k` 마커(RESEARCH Test Map L447-454: `type_rules`/`ttm_missing`/`reproduce`/
`provenance_or_pershare`/`edgar_q4`/`dart_quarter_semantics`)로 분리.

**mock 주입(필요 시)** — `test_dart_quarterly.py` L36-42 `mocker.patch` + 싱글톤 리셋
(L26-33) 패턴. 단 Phase 8 엔진은 순수(네트워크 0)라 대부분 fixture 직접 주입으로 충분 —
mock은 spike(DART thstrm_amount 의미 확인, Open Q1) 등 예외 경로에만.

---

## Shared Patterns

### 결손 게이트 (None/NaN 단일 판정)
**Source:** `src/stocksig/io/fundamentals.py` L72-78 `_is_missing`
**Apply to:** `metrics_engine.py` 전 산식 + TTM 합산 게이트
```python
def _is_missing(x: float | None) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))
```
모든 결손 = `None`(0/-999999 sentinel 절대 금지, D-05). NaN이 `<=0` 비교를 통과해 값 셀로
새는 버그(WR-01)를 단일 게이트로 차단. Core Value(색 신호) 정확성 보호.

### 셀 모델 (값 + 출처 + 한국어 사유)
**Source:** `src/stocksig/io/fundamentals.py` L32-44 `MetricCell` + L56-57 `_empty_cell`
**Apply to:** `metrics_engine.py` 모든 산출 셀
```python
@dataclass
class MetricCell:
    value: float | None   # None = 결손 (0 금지, D-05)
    source: str | None    # "EDGAR"|"DART"|"yf"|"Naver"|"EDGAR+yf" provenance
    note: str | None      # "조회 실패: <사유>" 한국어
```
Phase 10 시트1 계약과 동일 구조 → 이관 마찰 0. 신규 dataclass 발명 금지.

### DB 조회 + 동시성 (단일 연결 + ? 바인딩)
**Source:** `src/stocksig/io/fundamentals_store.py` L107-120 `get_store` + L139-163 SELECT 패턴
**Apply to:** 신규 `fetch_raw_quarters` 헬퍼
```python
get_store().execute("SELECT ... FROM raw_facts WHERE ticker=?", (ticker,))
```
WAL/busy_timeout/더블체크 락 재사용. f-string/`%` SQL 금지(ASVS V5/T-07-01) — ticker/field
보간 SQL injection 차단.

### 소스별 원천필드 매핑 (논리 field → 소스 태그 tuple)
**Source:** `src/stocksig/io/dart_account_map.py` L31-94 + `edgar_client.py` L100-114
**Apply to:** `metrics_registry.py` 소스 매핑 (신규 매핑 dict 만들지 말 것 — SC1 "기존 매핑 시작점")
```python
{"net_income": ("ifrs-full_ProfitLoss", ...), "total_assets": ("ifrs-full_Assets",), ...}
```

### 캘린더 분기 키 "YYYYQn" (정렬·TTM 산술 기준)
**Source:** `dart_client.py` L187 `_REPRT_TO_QUARTER`+L195 / `edgar_client.py` L117 `_calendar_quarter_key`
**Apply to:** `metrics_engine.py` TTM 직전 4분기 산술 + 매트릭스 열 정렬
기존 추출기가 이미 "YYYYQn" 정규화해 저장(D-08) → 엔진은 동일 키로 ±N 분기 산술만 추가.

### per-metric provenance 병합 + "+" 결합 라벨
**Source:** `src/stocksig/io/fundamentals.py` L153-176 (채운 셀 source/note 부여) + L289 `"+".join(used)`
**Apply to:** `metrics_engine.py` 복수 source raw 혼합 시(예 ROE: net_income=DART, total_equity=DART)
**주의:** Phase 8은 fetch/폴백 안 함(D-09) — 저장 raw의 source 라벨만 병합. 동일 → 그 source,
혼합 → "+" 결합(예 "EDGAR+yf").

---

## No Analog Found

없음. 전 신규 파일이 강한 코드베이스 analog를 가진다(순수 계산 층, 신규 의존 0).

다만 **analog가 직접 답을 주지 않는 2개 raw-data 진실**은 planner가 spike로 확정해야 한다
(코드 패턴 문제가 아니라 데이터 의미 문제):

| 갭 | 성격 | planner 조치 |
|----|------|--------------|
| DART `thstrm_amount` = 분기값 vs 누적값 (Open Q1) | raw 의미 — analog 없음 | 005930 반기/3분기 1회 spike. `test_dart_quarterly.py` mock 패턴으로 spike 테스트 작성. 결과로 "YTD 분해" 작업 채택/삭제 |
| EDGAR raw에 Q4/FY 손익 부재 (Open Q2, Pitfall 1) | raw 완전성 — `by_period_length(3)`만 저장 | 실 DB 1회 조회. Q4 빈값+사유 수용 vs FY duration 추가(Phase 7 재확장) 택1 |

이 2건은 RESEARCH Open Q1·Q2와 동일. analog 코드는 정확하나 입력 raw의 분기값 의미가
TTM 산식의 옳고 그름을 좌우 — planner 첫 task로 확정 권장.

---

## Metadata

**Analog search scope:** `src/stocksig/io/` (fundamentals.py, fundamentals_store.py, dart_account_map.py, edgar_client.py, dart_client.py, cache.py), `tests/` (test_fundamentals.py, test_fundamentals_store.py, test_dart_quarterly.py, conftest.py)
**Files scanned:** 10 (소스 6 + 테스트 4)
**Pattern extraction date:** 2026-06-19
