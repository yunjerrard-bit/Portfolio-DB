# Phase 9: 트렌드 엑셀 렌더 (FUND-10) - Research

**Researched:** 2026-06-22
**Domain:** XlsxWriter 매트릭스 렌더링 · 이중 시각 인코딩(상대색+YoY 화살표) · 분기말 종가 조달 · CLI 서브커맨드
**Confidence:** HIGH (기존 코드 시그니처·반환형은 직접 read로 확정 / XlsxWriter·openpyxl·pandas는 설치본에서 실행 검증)

---

<user_constraints>
## User Constraints (from 09-CONTEXT.md)

### Locked Decisions (D-01 ~ D-15)

**매트릭스 레이아웃**
- **D-01:** 분기 열 = 전체 저장 분기, **최신을 맨 왼쪽**(내림차순). 식별 선두 열 다음부터 분기 열이 왼←오 = 최신←과거.
- **D-02:** 선두 식별 열 = 시트1 portfolio의 A~E열을 그대로 재사용 — 순서·헤더 동일: **티커 · 기업명 · 시장 · 티어 · 산업**. 그 뒤 분기 열(D-01).
- **D-03:** 종목 행 정렬 = **미국 → 한국 그룹화 후 각 그룹 내 알파벳(티커)순**.
- **D-04:** Freeze panes = **A열(티커)만 고정**(헤더행 freeze 안 함). 시장(C)·티어(D) 열은 글자 보이는 최소 너비.

**트렌드 시각 인코딩 (이중·직교 — 핵심)**
- **D-05:** 셀 배경색 = 동종 산업군 상대 비교, 3단계 **초록/무색/빨강**. 의미 = **좋을수록 초록·나쁠수록 빨강**(finviz 모델). 비교 단위 = **분기 열 단위**로 같은 `산업(E열)` 그룹 내 종목들끼리.
- **D-06:** 지표별 좋음/나쁨 방향:
  - 낮을수록 좋음(낮을 때 초록): **PER · PEG · PBR · PCR · PSR** (밸류에이션)
  - 높을수록 좋음(높을 때 초록): **ROE · ROA · GPM · OPM** (수익성/마진)
- **D-07(표본 게이트):** 동종 산업군 표본이 **N 미만(권장 N=3)** 이면 상대색 = **무색**. `산업`이 빈 문자열("")인 종목도 무색.
- **D-08:** 화살표 = 전년동기(YoY) 증감 — 각 셀을 **4분기 전(동일 지표의 4칸 오른쪽 열, D-01 내림차순이므로 오른쪽이 과거)** 과 비교해 ↑/↓ 표시. 상대색이 무색이어도 화살표는 유지. 전년 동기 값 결손 시 화살표 생략. 구현 방식 = Claude 재량.

**가격 의존 지표 & PEG**
- **D-09:** 가격 의존 4종(PER/PBR/PCR/PSR) 과거 열 = 그 분기 마지막 거래일 종가(보유 10년치 OHLCV), 최신 열만 현재가. `price_ratio(denom_cell, price)`에 주입.
- **D-10:** PEG도 분기별 산출 — `compute_peg_cell(per_value, eps_ttm, eps_prior)` 2단계 API. 과거 분기 PEG = 분기말 종가 기준 PER 사용.

**결손·출처 표기**
- **D-11:** 결손/sanity-밖 셀 = `"-"` 표시 + 마우스오버 셀 코멘트(사유). 0 대체·부분합산 금지.
- **D-12:** per-metric provenance = `[원천]` 시트 중심 + 지표 셀 코멘트 보조.

**시트 구성**
- **D-13:** 지표별 시트(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA) + `[원천]`(분기별 raw long) + `[최신 스냅샷]`(종목 1행 × 전 지표 최신값).

**파일·배선**
- **D-14:** 파일명 = `fundamentals_history_YYYYMMDD.xlsx`(날짜 스탬프, 매 실행 새 파일).
- **D-15:** 진입점 = 독립 서브커맨드/플래그 — 시트1 산출 흐름(main_run)과 완전 분리. 평소 main 실행(Phase 7 sync가 DB 적재) 후 별도 호출로 렌더.

### Claude's Discretion (planner/executor 재량)
- 화살표 구현 기법(XlsxWriter iconset vs 글리프 vs 별도 열)·상대색 구현(conditional_format vs Python 사전계산 후 정적 베이킹).
- 표본 게이트 N의 최종값(권장 3) 및 동순위/동값 처리.
- `[원천]`/`[최신 스냅샷]` 시트의 구체 열 구성·정렬.
- 분기 열 헤더 라벨 형식(`2026Q1` 등 — Phase 8 캘린더 분기 키 그대로 권장).
- 서브커맨드/플래그의 정확한 CLI 형태 및 DB 미존재 시 안내 메시지.
- 시장(C)·티어(D) 열 "최소 너비"의 구체 산정(autofit 근사).

### Deferred Ideas (OUT OF SCOPE)
- 헤더행 freeze(현재 A열만) · 스파크라인/미니차트 · FCF·EV/EBITDA 시트(raw 부재) · 상대비교 기준 확장(시총·티어) · 기초·기말 평균 분모(ROE/ROA 정밀).
- (다른 phase) 시트1 store/registry 이관 = Phase 10(FUND-11). 시트1 색 신호 **불변**.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FUND-10 | 사용자가 `fundamentals_history_YYYYMMDD.xlsx`(시트1과 별도)를 열어 지표별 분기 트렌드(행=종목·열=분기), 분기별 원천, 종목별 최신 스냅샷을 육안 확인. 과거 PER/PBR=분기말 종가, 최신만 현재가. | `compute_matrix`/`price_ratio`/`compute_peg_cell`(metrics_engine, 실측 시그니처) + `fetch_raw_quarters`([원천]) + OHLCV `resample('QE').last()`(분기말 종가, 실행검증) + XlsxWriter 3.2.9 `add_format`/`write_rich_string`/`conditional_format`/`write_comment`(설치본 검증) + 식별 열 모델(sheet_portfolio `_COL`) |
</phase_requirements>

## Summary

Phase 9는 **순수 렌더 층**이다. 외부 호출·계산 로직 신규 작성이 거의 없다: Phase 8 엔진(`compute_matrix`/`price_ratio`/`compute_peg_cell`)과 Phase 7 store(`fetch_raw_quarters`)가 모든 데이터를 공급하고, Phase 9는 (1) 다종목 매트릭스 재구성, (2) 분기말 종가 주입, (3) XlsxWriter 워크북 작성만 담당한다. 분기말 종가는 보유 10년치 OHLCV Close 시계열에 `resample('QE').last()`를 적용해 분기키(`YYYYQn`)별 마지막 거래일 종가를 뽑으면 휴장일 자동 처리된다(실행 검증 완료).

이중 시각 인코딩은 **두 채널을 직교로 베이킹**하는 것이 권장이다. (1) **상대색**은 Python에서 분기 열·산업 그룹별로 사전 순위 계산 후 정적 `Format`(font_color+bg_color)을 셀에 베이킹 — CLAUDE.md의 "정적 색 베이킹" 선호와 정합하고, `conditional_format` 3_color_scale은 "지표별 좋음/나쁨 방향 반전"·"산업 그룹 분할"·"표본<3 무색 게이트"를 표현할 수 없어 부적합하다. (2) **YoY 화살표**는 셀 값 텍스트에 유니코드 글리프(▲/▼)를 결합하는 방식이 권장 — XlsxWriter icon_set은 "셀 자기 값 기준"이라 "4분기 전 대비"라는 YoY 의미를 표현할 수 없다. 숫자 서식과 화살표를 한 셀에 공존시키려면 값을 문자열로 포맷(`f"{v:.2f} ▲"`)하거나 `write_rich_string`으로 색만 분리한다.

CLI 배선(D-15)은 `main.py` argparse에 서브커맨드/플래그를 추가하고 `main_run.run`과 완전 분리된 새 엔트리 함수를 호출한다. DB 미존재 시 "먼저 main을 실행해 DB를 적재하라"는 한국어 안내 후 깔끔히 종료한다.

**Primary recommendation:** Python 사전계산 → 정적 Format 베이킹(상대색) + 유니코드 글리프 셀 텍스트(YoY 화살표). OHLCV는 `resample('QE').last()`로 분기말 종가 조달. `compute_matrix`는 ticker별 호출 → Phase 9가 행=종목·열=분기로 전치 재구성. 새 파일 `fundamentals_history_YYYYMMDD.xlsx`, 새 워크북 팩토리(시트1 포맷 캐시와 분리), 별도 CLI 서브커맨드.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 분기 매트릭스 계산(9지표) | 계산 엔진(Phase 8 `metrics_engine`) | — | 이미 완성·단일 원천. Phase 9는 소비만. |
| raw long 조회 | store(Phase 7 `fundamentals_store`) | — | `fetch_raw_quarters` 그대로 [원천] 시트 공급. |
| 분기말 종가 추출 | 신규 가격 헬퍼(Phase 9) | OHLCV 캐시(`market`) | OHLCV 시계열은 캐시에서, 분기 경계 매핑은 Phase 9 신규 로직. |
| 상대 순위·색 결정 | 신규 색 결정(Phase 9 compute) | — | 분기 열·산업 그룹 상대 비교는 렌더 전용 로직(시트1 `color_rules`와 별개). |
| 워크북·시트 작성 | 신규 output 모듈(Phase 9) | `writer.make_workbook` 패턴 차용 | XlsxWriter 작성. 시트1 writer는 읽기만(불변). |
| 식별 열(티커/기업명/시장/티어/산업) | TickerSpec·company·market_kind | — | 기존 입력 소스 재사용. |
| CLI 진입 | `main.py` argparse(신규 서브커맨드) | `main_run`(완전 분리) | D-15 — 시트1 흐름과 비결합. |

## Standard Stack

이 phase는 **신규 외부 패키지 0**이다. 전부 기설치·검증된 스택을 재사용한다.

### Core
| Library | Version (검증) | Purpose | Why Standard |
|---------|---------------|---------|--------------|
| XlsxWriter | 3.2.9 [VERIFIED: 설치본 `import xlsxwriter.__version__`] | 워크북·매트릭스 시트·정적 색 Format·코멘트 | CLAUDE.md 결정 라이브러리. `add_format`(font_color+bg_color+num_format 결합)·`write_rich_string`·`conditional_format`·`write_comment` 전부 설치본에서 존재 확인. |
| pandas | 2.2+ [CITED: pyproject.toml `pandas>=2.2`] | OHLCV 분기말 리샘플(`resample('QE').last()`)·정렬 | EMA/통계와 동일 스택. `to_period('Q')`로 `YYYYQn` 키 생성(실행 검증). |
| openpyxl | 3.1.5 [VERIFIED: 설치본 `import openpyxl.__version__`] | **테스트 전용** — 워크북 셀 값/색/코멘트 read-back 검증 | dev 의존(pyproject `[dependency-groups] dev`). `Cell.value/fill/font/comment` 노출 확인. |
| pytest | 8.x [CITED: pyproject.toml `pytest>=8.0`] | 테스트 | 기존 스위트(341 passed) 동일 러너. |

### Supporting (전부 기존 모듈 import — 신규 import 없음)
| 모듈 | 재사용 함수/객체 | 용도 (실측 시그니처) |
|------|------------------|----------------------|
| `stocksig.io.metrics_engine` | `compute_matrix(ticker, fetch_fn=fetch_raw_quarters) -> dict[str, dict[str, MetricCell]]` | ticker별 `{metric_name: {quarter: MetricCell}}`. 분기축 = raw 등장 분기 **오름차순**(L330 `sorted(...)`) → D-01 표시 시 **역순**(reversed) 필요. |
| | `price_ratio(denom_cell: MetricCell, price: float\|None) -> MetricCell` | PER/PBR/PCR/PSR 가격 주입. 분모 None/≤0·price 결손 → 빈값+사유. |
| | `compute_peg_cell(per_value, eps_ttm, eps_prior) -> MetricCell` | PEG 2차 산출. sanity("PEG":0~10) 적용. |
| | `_calendar_quarter_offset(q, n) -> str` | `("2026Q1",-4) -> "2025Q1"` — YoY 4분기 전 키·PEG 전년 EPS. |
| `stocksig.io.fundamentals` | `MetricCell(value, source, note)` dataclass · `_is_missing(x) -> bool` | 셀 표현·결손 게이트(None/NaN). **신규 정의 금지(재사용)**. |
| `stocksig.io.fundamentals_store` | `fetch_raw_quarters(ticker) -> list[tuple]` | 행=`(quarter, source, field, value, period_type, reprt_code, unit)`. **주의: period_end 미포함**(아래 D-09 참조). [원천] 시트 직공급. |
| | `count_rows(ticker=None) -> int` | DB 존재/적재 여부 판정(D-15 안내 분기). |
| `stocksig.io.metrics_registry` | `REGISTRY: tuple[MetricDef,...]`(9 지표 + 4 분모 metric) · `MetricType` | 지표 시트 목록·방향(D-06). `MetricDef.name`/`mtype`/`price_denominator`/`is_ratio_0_1`. |
| `stocksig.io.input` | `read_tickers_extended(path) -> list[TickerSpec]` · `TickerSpec(symbol, tier, industry)` | 산업(상대비교 그룹·D-05)·티어. 미입력 시 `industry=""`. |
| `stocksig.io.company` | `fetch_company_name(ticker) -> str` | 식별 열 기업명(캐시 우선, 30일 TTL). |
| `stocksig.io.market_kind` | `classify_market(symbol) -> "US"\|"KR"` | 식별 열 시장·종목 그룹 정렬(D-03). |
| `stocksig.io.market` | `fetch_ohlcv_cached(ticker) -> pd.DataFrame` | 10년치 OHLCV(분기말 종가 소스). 캐시 HIT 시 무호출. columns=[Open,High,Low,Close,Volume], index=DatetimeIndex. |
| `stocksig.output.writer` | `make_workbook(path) -> (Workbook, formats)` 패턴 | 워크북 팩토리 **패턴** 차용. 단, 트렌드 전용 Format 캐시는 별도(시트1 45키와 비결합). |

### Alternatives Considered
| Instead of | Could Use | Tradeoff (왜 기각) |
|------------|-----------|---------------------|
| Python 사전계산 + 정적 Format 베이킹(상대색) | `conditional_format` 3_color_scale/icon_set | **기각.** ① 지표별 좋음/나쁨 방향 반전(PER 낮을수록 초록 ↔ ROE 높을수록 초록)을 셀 단위로 표현 불가. ② 산업 그룹 분할(같은 분기 열이라도 산업마다 다른 비교 모집단)을 1개 column-range 규칙으로 못 나눔. ③ 표본<3 무색 게이트가 데이터 의존이라 정적 규칙으로 못 막음. ④ CLAUDE.md "정적 색 베이킹·인플레이스 미사용" 명시. |
| 유니코드 글리프(▲▼) 셀 텍스트(YoY) | `conditional_format` icon_set | **기각.** icon_set은 "셀 자기 값"을 임계로 아이콘 매핑 → "4분기 전 대비 증감"(YoY)을 표현 불가(직교 신호 D-08 위반). |
| 새 워크북 팩토리(트렌드 전용) | `writer.make_workbook` 직접 호출 | make_workbook은 시트1·종목시트용 45키 Format 캐시를 만든다(SigmaBucket 등). 트렌드는 다른 Format 셋 필요 → 패턴만 차용하고 별도 팩토리 권장(결합 회피). |

**Installation:** 신규 설치 없음. 전부 기설치(pyproject 확인). `uv sync`만으로 충분.

## Package Legitimacy Audit

> 신규 외부 패키지 0 — 본 phase는 기설치 의존만 재사용. slopcheck 대상 없음.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (신규 없음) | — | N/A — 전부 기존 pyproject 의존(XlsxWriter/pandas/openpyxl/pytest) 재사용 |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none

## Architecture Patterns

### System Architecture Diagram

```
[CLI: main.py 서브커맨드 --history]
        │  (D-15 독립 진입 — main_run.run 호출 안 함)
        ▼
[history_render.run_history()]  ← 신규 엔트리 함수
        │
        ├─► read_tickers_extended(tickers.txt) ──► list[TickerSpec(symbol,tier,industry)]
        │
        ├─► count_rows() == 0 ? ──► [한국어 안내 + 종료]  (DB 미적재)
        │
        ├─ per ticker (정렬: US→KR, 그룹 내 알파벳 D-03):
        │     ├─► compute_matrix(ticker) ──► {metric:{quarter:MetricCell}}   (외부호출 0)
        │     ├─► fetch_ohlcv_cached(ticker).Close.resample('QE').last()      (분기말 종가)
        │     │        └─► to_period('Q') → {YYYYQn: close}  (+ 현재가 = Close.iloc[-1])
        │     ├─► 가격 의존 4종: price_ratio(matrix["EPS_ttm"|"BPS"|...][q], price[q])
        │     ├─► PEG: compute_peg_cell(per[q].value, eps[q].value, eps[q-4].value)
        │     ├─► fetch_company_name(ticker) ──► 식별 열 기업명
        │     └─► fetch_raw_quarters(ticker) ──► [원천] 시트 long 행
        │
        ▼
[다종목 매트릭스 재구성]  metric별 행=종목·열=분기(D-01 최신 왼쪽)
        │
        ├─► [상대색 결정]  분기 열 × 산업 그룹별 순위 → 초록/무색/빨강 (D-05/06/07)
        │        표본<3 또는 산업="" → 무색
        ├─► [YoY 화살표]  cell[q] vs cell[q-4] → ▲/▼/(생략) (D-08)
        │
        ▼
[XlsxWriter 워크북 작성]  fundamentals_history_YYYYMMDD.xlsx
        ├─ 지표 시트 ×9 (식별 5열 + 분기 열, 정적 Format 베이킹 + 코멘트)
        ├─ [원천] 시트  (raw long)
        ├─ [최신 스냅샷] 시트  (종목 1행 × 전 지표 최신값)
        └─ freeze_panes(헤더행, A열)  → D-04
```

### Recommended Project Structure (신규 파일)
```
src/stocksig/
├── output/
│   ├── history_workbook.py     # 트렌드 전용 make_workbook + Format 캐시 (writer.py 패턴 차용)
│   ├── sheet_metric_matrix.py  # 지표별 매트릭스 시트 writer (식별열 + 분기열 + 색/화살표)
│   ├── sheet_raw.py            # [원천] long 시트
│   └── sheet_snapshot.py       # [최신 스냅샷] 시트
├── compute/
│   └── trend_color.py          # 분기열×산업 상대 순위 → bucket 결정 (D-05/06/07) + YoY 화살표 (D-08)
└── io/
    ├── quarter_price.py        # OHLCV → {YYYYQn: 분기말 종가} + 현재가 (D-09)
    └── history_render.py       # 오케스트레이션 엔트리 (다종목 매트릭스 재구성 + 시트 배선)
```
*(파일 분할은 planner 재량 — 위는 단일책임 가이드. 시트1 `sheet_portfolio.py`·`color_rules.py`는 절대 수정 금지.)*

### Pattern 1: 분기말 종가 조달 (D-09 — 핵심·실행 검증)
**What:** OHLCV Close 시계열을 분기 경계로 리샘플해 각 분기 "마지막 거래일 종가"를 뽑는다. 휴장일은 `last()`가 자동 처리(분기 내 마지막 실제 거래일).
**When to use:** 가격 의존 4종(PER/PBR/PCR/PSR)의 과거 분기 열 가격 주입.
```python
# Source: 설치본 pandas 2.x 실행 검증 (resample('QE').last() + to_period('Q'))
import pandas as pd
from stocksig.io.market import fetch_ohlcv_cached

def quarter_end_prices(ticker: str) -> tuple[dict[str, float], float]:
    """반환: ({YYYYQn: 분기말 종가}, 현재가). 현재가 = 최신 거래일 Close."""
    df = fetch_ohlcv_cached(ticker)            # 캐시 HIT 시 무호출 (24h TTL)
    close = df["Close"].dropna()
    qe = close.resample("QE").last()           # 분기말(달력 분기 종료) 마지막 거래일 종가
    keys = qe.index.to_period("Q").astype(str) # ['2024Q1', '2024Q2', ...]  ← 매트릭스 분기키와 동일
    qmap = dict(zip(keys, qe.to_numpy()))
    current_price = float(close.iloc[-1])      # 최신 열 주입용 현재가
    return qmap, current_price
```
**주의:** `'QE'`(quarter-end)는 pandas 2.2+ 표기. 구 `'Q'`는 deprecated. [VERIFIED: 설치본 실행 — `['2024Q1','2024Q2','2024Q3','2024Q4']` 정상 산출]

### Pattern 2: compute_matrix 다종목 → 행=종목·열=분기 전치 (데이터 흐름)
**What:** `compute_matrix`는 **ticker별 단일 호출**(L299 `compute_matrix(ticker, ...)`)이며 `{metric: {quarter: cell}}`를 반환한다(분기축 = 그 종목 raw 등장 분기 오름차순). 다종목 매트릭스 시트는 종목마다 호출해 모으고, **분기 열 합집합**을 만들어 전치한다.
```python
# Source: metrics_engine.py L299-338 (직접 read 확정)
from stocksig.io.metrics_engine import compute_matrix, price_ratio, compute_peg_cell, _calendar_quarter_offset

per_ticker = {t: compute_matrix(t) for t in sorted_tickers}   # 외부 호출 0 (Phase 8 보증)

# 분기 열 합집합 (종목마다 보유 분기가 다를 수 있음) → D-01 최신 왼쪽
all_quarters = sorted({q for m in per_ticker.values() for cells in m.values() for q in cells})
display_quarters = list(reversed(all_quarters))   # 내림차순: 최신←과거 (D-01)
```
**핵심 사실:** 분기축 정렬은 엔진이 **오름차순**(L330)으로 준다 → D-01 표시(최신 왼쪽)는 `reversed()`로 뒤집어야 한다. YoY 4분기 전(D-08)은 표시 순서와 무관하게 `_calendar_quarter_offset(q, -4)` 키로 조회.

### Pattern 3: 가격 의존 지표 + PEG 분기별 주입 (D-09/D-10)
```python
# Source: metrics_engine.py docstring L309-324 (PEG 소비 계약) + price_ratio L251
def price_for_quarter(q: str, qmap: dict, current_price: float, is_latest: bool) -> float | None:
    return current_price if is_latest else qmap.get(q)   # D-09: 과거=분기말 종가 / 최신=현재가

# 가격 의존 4종 (price_denominator로 분모 metric 참조)
for name, denom_metric in (("PER","EPS_ttm"),("PBR","BPS"),("PCR","OCF_ps"),("PSR","SPS")):
    for q in display_quarters:
        price = price_for_quarter(q, qmap, current_price, is_latest=(q == display_quarters[0]))
        cell = price_ratio(matrix[denom_metric][q], price)   # 분모 None/≤0·price 결손 → 빈값+사유

# PEG 분기별 (3단 계약)
for q in display_quarters:
    per_cell = price_ratio(matrix["EPS_ttm"][q], price_for_quarter(q, qmap, current_price, q==display_quarters[0]))
    q_prior = _calendar_quarter_offset(q, -4)
    eps_now = matrix["EPS_ttm"][q].value
    eps_prior = matrix["EPS_ttm"].get(q_prior, _empty).value if q_prior in matrix["EPS_ttm"] else None
    peg_cell = compute_peg_cell(per_cell.value, eps_now, eps_prior)
```
**주의:** `matrix["EPS_ttm"]`은 그 종목 보유 분기만 키로 가짐 → `q_prior`가 없으면 `eps_prior=None` → `compute_peg_cell`이 자연히 빈값+사유 반환(D-11). KeyError 가드 필수.

### Pattern 4: 이중 시각 인코딩 — 상대색(정적 베이킹) + YoY 화살표(글리프)
**상대색 (D-05/06/07):** 분기 열마다, 각 산업 그룹 안에서 값을 모아 순위를 매기고 3-bucket으로 나눈다.
```python
# Source: 신규 로직 (CLAUDE.md 정적 색 베이킹 정합). REGISTRY로 방향 결정 (D-06)
LOWER_IS_BETTER = {"PER","PEG","PBR","PCR","PSR"}   # 낮을수록 초록 (D-06)
# HIGHER_IS_BETTER = {"ROE","ROA","GPM","OPM"}

def relative_bucket(metric, value, peer_values, industry):
    if industry == "" or len([v for v in peer_values if v is not None]) < 3:   # D-07 게이트
        return "무색"
    # peer_values 내 value의 분위 → 상/중/하 3분할, LOWER_IS_BETTER면 방향 반전
    ...  # 동값/동순위 처리는 planner 재량 (권장: 동률은 무색 또는 중위)
    return "초록" | "무색" | "빨강"
```
3개 정적 Format을 워크북 생성 시 미리 만든다(시트1 GREEN_100/RED_100 색상 재사용 가능 — `compute.color_rules`에서 색 상수 import만, 시트1 로직 미수정):
```python
fmt_green = wb.add_format({"bg_color": GREEN_100, "font_color": GREEN_900, "num_format": "#,##0.00"})
fmt_red   = wb.add_format({"bg_color": RED_100,   "font_color": RED_900,   "num_format": "#,##0.00"})
fmt_plain = wb.add_format({"num_format": "#,##0.00"})   # 무색
```
**YoY 화살표 (D-08):** 셀 값 텍스트에 글리프 결합. icon_set은 YoY 표현 불가(기각).
```python
# 방법 A (권장 — 단순): 값을 문자열로 포맷 + 글리프 (정렬·평균 비대상 시트라 허용)
def yoy_glyph(cell_q, cell_q_prior) -> str:
    if cell_q is None or cell_q_prior is None or _is_missing(cell_q.value) or _is_missing(cell_q_prior.value):
        return ""   # 전년 동기 결손 → 화살표 생략 (D-08)
    return " ▲" if cell_q.value > cell_q_prior.value else (" ▼" if cell_q.value < cell_q_prior.value else "")
# write_string(row, col, f"{cell.value:.2f}{glyph}", fmt_<bucket>)
#   → 색(상대) = Format, 화살표(YoY) = 텍스트 글리프 → 직교 (D-08)
```
**대안 B (write_rich_string):** 숫자는 number-format 유지, 화살표만 별도 font_color로 분리하고 싶을 때. XlsxWriter 3.2.9 `write_rich_string` 존재 확인. 단, rich_string은 셀을 문자열로 만들어 number-format이 안 먹으므로 숫자 포맷은 문자열 포맷으로 직접 처리해야 한다. **권장은 방법 A**(단순·검증 용이) — 트렌드 시트는 정렬·집계 대상이 아니므로 문자열 셀 허용.

### Anti-Patterns to Avoid
- **시트1 모듈 수정:** `sheet_portfolio.py`·`color_rules.py`(로직)·`writer.make_workbook` 시그니처 변경 = Core Value 위반(D 불변). 색 **상수**만 import 허용, 함수/로직 미수정.
- **`conditional_format`로 상대색:** 위 Alternatives 4종 사유로 부적합. 정적 베이킹 강제(CLAUDE.md).
- **icon_set으로 YoY 화살표:** 셀 자기 값 기준이라 "4분기 전 대비" 표현 불가.
- **0/sentinel 대체:** 결손 = `"-"` + 코멘트(D-11). `_is_missing` 게이트 우회 금지.
- **분기축 오름차순 그대로 표시:** 엔진은 오름차순 반환 → D-01(최신 왼쪽)은 `reversed` 필수.
- **신규 MetricCell/_compute_peg/_is_missing 정의:** 재사용만(엔진/`fundamentals`에서 import). Don't Hand-Roll.
- **분기말 종가를 raw `period_end`에서 조달:** `fetch_raw_quarters` 반환 튜플에 period_end **미포함**(아래 참조). 종가는 OHLCV 리샘플에서.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 분기말 마지막 거래일 종가 | 날짜별 수동 분기 경계 루프·휴장일 보정 | `close.resample("QE").last()` | pandas가 휴장일·월말 경계 자동 처리(실행 검증). |
| 분기키 `YYYYQn` 생성 | 문자열 포맷 수동 조립 | `DatetimeIndex.to_period("Q").astype(str)` | 엔진/store 분기키와 동일 표기 보장. |
| YoY 4분기 전 키 산술 | `int(q[:4])-1` 등 수동 | `metrics_engine._calendar_quarter_offset(q, -4)` | Q1−4=전년 Q1 경계 정확(이미 검증·테스트됨). |
| PER/PBR/PCR/PSR 비율 | `price/denom` 직접 | `metrics_engine.price_ratio(cell, price)` | 분모 None/≤0·price 결손 빈값+사유 일관(D-11). |
| PEG 산식 | 성장률·엣지 4종 재구현 | `metrics_engine.compute_peg_cell(...)` | sanity·엣지케이스 이미 위임·테스트됨. |
| 결손 판정 | `x is None` (NaN 누수) | `fundamentals._is_missing(x)` | None+NaN 동시 게이트(WR-01). |
| 워크북 셀 검증(테스트) | xlsx 바이너리 파싱 | `openpyxl.load_workbook` → `cell.value/fill/font/comment` | dev 의존 기설치(3.1.5). 시트1 테스트 동일 패턴. |

**Key insight:** Phase 9의 신규 "계산"은 사실상 (1) OHLCV 리샘플과 (2) 분기열×산업 상대 순위뿐이다. 나머지는 전부 Phase 7/8 검증된 함수 소비. 신규 코드 표면을 최소화하면 회귀 위험과 드리프트(시트1 vs 트렌드 값 불일치)가 사라진다.

## Runtime State Inventory

> Phase 9는 신규 파일 추가 + 새 .xlsx 산출의 **greenfield 렌더 층**이다(rename/refactor 아님). 그래도 입력 상태 의존을 명시한다.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `data/fundamentals.db`(raw_facts/delta_state) — Phase 7 sync가 적재. Phase 9는 **읽기 전용**. | 없음 — `fetch_raw_quarters`/`count_rows` 읽기만. |
| Live service config | 없음 — 외부 서비스 호출 0(OHLCV는 캐시 우선). | None — 검증: Phase 9 코드 경로에 신규 API 호출 없음(엔진·store 모두 DB/캐시). |
| OS-registered state | 없음. | None. |
| Secrets/env vars | `OPENDART_API_KEY`/`EDGAR_USER_AGENT_EMAIL` — Phase 9 직접 사용 안 함(DB가 진실). | None — 렌더는 키 불필요. (단 OHLCV 캐시 MISS 시 yfinance 호출 발생 가능 — 키 불요.) |
| Build artifacts | 신규 `output/fundamentals_history_YYYYMMDD.xlsx`(매 실행 새 파일, gitignore 대상 — `output/` 이미 존재). | None — 기존 `output/` 디렉터리 재사용. |

**핵심 검증 결과:** `fetch_raw_quarters(ticker)` 반환 = `(quarter, source, field, value, period_type, reprt_code, unit)` — **`period_end`/`period_start`/`accession` 미포함**(store SCHEMA에는 있으나 SELECT 컬럼에서 제외, L182-183 직접 read). 따라서 [원천] 시트는 이 7-tuple로 구성하고, 분기말 종가는 OHLCV 리샘플에서 별도 조달(raw에서 못 꺼냄).

## Common Pitfalls

### Pitfall 1: 분기축 정렬 방향 혼동 (D-01)
**무엇이 잘못되나:** `compute_matrix`가 분기를 **오름차순**(과거→최신)으로 주는데 D-01은 **최신 왼쪽**(내림차순) 요구. 그대로 쓰면 좌우가 뒤집힌다.
**근본 원인:** 엔진 L330 `sorted({...})` 오름차순.
**회피:** 표시 분기열 = `list(reversed(sorted_quarters))`. YoY는 표시순과 독립으로 `_calendar_quarter_offset(q,-4)` 키 조회.
**조기 경보:** 최신 열이 가장 오래된 분기를 가리키면 즉시 발견 — 테스트에서 첫 분기열 헤더 == 최신 분기키 단언.

### Pitfall 2: 종목마다 분기 집합이 다름 (다종목 매트릭스)
**무엇이 잘못되나:** ticker A는 2020Q1~2026Q1, ticker B는 2023Q2~2026Q1. 단순 dict 접근 시 KeyError.
**회피:** 분기 열 = 전 종목 분기 **합집합**. 셀 조회는 `matrix[metric].get(q)` → 없으면 `"-"`(미보유 분기). YoY/PEG의 `q_prior`도 `.get` 가드.

### Pitfall 3: 상대색 모집단 정의 오류 (D-05/07)
**무엇이 잘못되나:** 전 종목·전 분기를 한 모집단으로 순위 매기면 finviz 모델(같은 분기·같은 산업) 위반.
**근본 원인:** 비교 단위 = **(분기 열, 산업 그룹)** 2차원.
**회피:** 색 결정 루프 = `for q in quarters: for industry_group in groups: peers = 그 분기·그 산업의 유효값들`. `len(peers) < 3` 또는 `industry == ""` → 그 그룹 셀 전부 무색(D-07).
**조기 경보:** 산업이 1종목인 그룹의 셀이 칠해지면 게이트 버그.

### Pitfall 4: 분기말 종가 키 불일치
**무엇이 잘못되나:** OHLCV 리샘플 키(`to_period("Q")`)와 엔진 분기키(`YYYYQn`)가 다르면 가격 주입이 전부 결손.
**근본 원인:** 표기 차이(예: `2026Q1` vs `2026-Q1`).
**회피:** `to_period("Q").astype(str)` → `"2026Q1"` (실행 검증, 엔진 `_calendar_quarter_offset` 출력과 동일 표기). 분기키 일치 단언 테스트 추가.

### Pitfall 5: 시트1 Format 캐시 오염
**무엇이 잘못되나:** `writer.make_workbook`을 트렌드에 직접 쓰면 시트1용 45키 Format/SigmaBucket이 섞이고, 트렌드 요구 색이 없어 키 누락.
**회피:** 트렌드 전용 워크북 팩토리 신설(패턴만 차용). 색 상수(`GREEN_100` 등)는 import 가능하나 `make_workbook`/`write_portfolio_sheet`는 호출/수정 금지.

### Pitfall 6: 한국 종목 분기 OHLCV와 펀더멘털 분기 시차
**무엇이 잘못되나:** DART 분기 종료일과 yfinance `.KS` 거래일 캘린더가 미묘하게 다를 수 있음(공휴일·결산월). `resample("QE").last()`는 **달력 분기 종료** 기준이라 회계 분기와 1:1이 아닐 수 있다.
**회피:** 본 프로젝트 분기키는 **캘린더 분기**(`YYYYQn`, store D-08/Phase 7 확정)로 통일돼 있으므로 OHLCV도 캘린더 분기 리샘플이 정합. 회계연도≠역년 기업의 미세 오차는 D-09 "트렌드 일관성" 범위 내 수용(시트1과 별도 파일, raw 저장으로 추후 보정 가능). ASSUMED — planner가 한국 1종목·미국 1종목으로 수기 시각 확인 권장.

## Code Examples

### CLI 서브커맨드 배선 (D-15) — argparse subparsers
```python
# Source: main.py L37-77 (기존 argparse 구조) + argparse 표준
# main.py 에 서브커맨드 추가 (기존 옵션 흐름 = 기본 동작, 'history' = 트렌드 렌더)
import argparse
parser = argparse.ArgumentParser(description="표준편차 기반 주식 매매신호 워크북 생성")
sub = parser.add_subparsers(dest="cmd")
# 기존 플래그는 유지(하위호환 — 서브커맨드 없으면 기존 portfolio 흐름)
p_hist = sub.add_parser("history", help="펀더멘털 트렌드 엑셀 렌더 (DB → fundamentals_history_*.xlsx)")
p_hist.add_argument("--tickers", default="tickers.txt")
p_hist.add_argument("--output-dir", default="output")
args = parser.parse_args()

if args.cmd == "history":
    from stocksig.io.history_render import run_history   # 늦은 import (의존성 격리)
    path = run_history(args.tickers, args.output_dir)
    print(f"완료: {path}")
else:
    from stocksig.main_run import run                     # 기존 흐름 불변
    ...
```
*(서브커맨드 vs 단일 `--history` 플래그는 Claude 재량 — subparsers가 출력 디렉터리·도움말 분리에 더 깔끔. 단순함 우선 시 `main_run.run`과 별 엔트리만 분리해도 D-15 충족.)*

### DB 미존재/미적재 안내 (D-15 재량)
```python
# Source: fundamentals_store.count_rows L155 (직접 read)
from stocksig.io.fundamentals_store import count_rows
def run_history(tickers_path, output_dir):
    if count_rows() == 0:
        # data/fundamentals.db 가 없거나 비어 있음 → get_store()가 빈 DB 생성 후 0 반환
        print("펀더멘털 DB가 비어 있습니다. 먼저 `uv run python main.py` 를 실행해 "
              "분기 펀더멘털을 적재한 뒤 다시 `history` 를 실행하세요.")
        return None
    ...
```

### 워크북 셀 검증 (테스트 — openpyxl read-back)
```python
# Source: tests/test_sheet_portfolio.py L13 (openpyxl import) + 설치본 Cell 속성 검증
import openpyxl
wb = openpyxl.load_workbook(path)
ws = wb["PER"]
assert ws["F6"].value == "-"                          # 결손 셀 (D-11)
assert ws["F6"].comment.text.startswith("...")        # 사유 코멘트
cell = ws["B6"]
assert cell.fill.start_color.rgb endswith("E8F5E9"|"C8E6C9")  # 초록 bg (상대색 베이킹)
assert "▲" in ws["C6"].value                          # YoY 화살표 (D-08)
assert wb["PER"].freeze_panes == "B6"                 # A열+헤더행 고정 (또는 D-04에 맞춘 좌표)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| pandas `resample("Q")` | `resample("QE")` | pandas 2.2 | 구 `"Q"`는 FutureWarning/deprecated. 분기말 종가는 `"QE"` 사용(실행 검증). |
| `conditional_format` 색조 스케일로 상대비교 | Python 사전계산 정적 베이킹 | 프로젝트 결정(CLAUDE.md) | 방향 반전·그룹 분할·표본 게이트 표현 가능. |

**Deprecated/outdated:** 없음(스택 전부 최신·기설치).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 표본 게이트 N=3이 적절 | D-07 / Pattern 4 | 너무 크면 개인 포트폴리오 대부분 무색(정보 손실), 작으면 1:1 비교로 오해. planner가 최종 결정(CONTEXT가 N=3 권장 명시). |
| A2 | YoY 화살표 = 값 문자열 결합(방법 A)이 rich_string보다 단순·검증 용이 | Pattern 4 | rich_string이 더 깔끔할 수 있으나 number-format 손실. 트렌드 시트가 집계 비대상이라 문자열 셀 허용 가정. |
| A3 | 캘린더 분기 OHLCV 리샘플이 회계 분기와 정합(특히 비12월 결산) | Pitfall 6 / D-09 | 회계연도≠역년 기업에서 분기말 종가가 1분기 어긋날 수 있음. 본 프로젝트가 캘린더 분기키로 통일했으므로 일관(수용). 수기 시각 확인 권장. |
| A4 | 동값/동순위는 무색 또는 중위 처리 | Pattern 4 | 동률 다수 시 색 분포 왜곡 가능. planner가 정책 확정(CONTEXT 재량). |
| A5 | sanity bounds(엔진 `_SANITY_BOUNDS`, ASSUMED 표기됨)가 트렌드 표시에도 적정 | 엔진 재사용 | bounds 밖 = 빈값+사유로 `"-"` 표시. 과도하게 좁으면 정상값이 누락될 수 있음(엔진 단계 이슈, Phase 9 신규 위험 아님). |

## Open Questions

1. **현재가(최신 열) 소스 일관성 — 트렌드 vs 시트1**
   - 아는 것: 시트1은 `last_close`(OHLCV iloc[-1])로 PER 산출. 트렌드 최신 열도 `current_price = close.iloc[-1]`(Pattern 1).
   - 불확실: 두 파일이 동일 캐시·동일 시점이면 일치하나, OHLCV 캐시 TTL(24h) 경계에서 미세 차이 가능.
   - 권장: 둘 다 `fetch_ohlcv_cached`의 `Close.iloc[-1]` 사용 → 동일 캐시 진입점이면 드리프트 0. Phase 10이 시트1을 엔진으로 이관하면 완전 통일(설계노트 D-04 canonical).

2. **[최신 스냅샷] 시트의 PEG 표시**
   - 아는 것: PEG는 2단계 산출(PER + EPS 성장률). 최신 열 PEG = 현재가 PER + 최신/4분기전 EPS.
   - 불확실: 최신 분기의 4분기 전 EPS가 결손이면 PEG 빈값 — 스냅샷에서 `"-"` 표시.
   - 권장: 스냅샷도 매트릭스 최신 열 셀을 그대로 재사용(재계산 없이 일관).

3. **분기 열 개수 상한 (10년 = 최대 40분기)**
   - 아는 것: D-01은 "전체 저장 분기". 10년 × 4 = 40 열 × 5 식별 열 = 45 열.
   - 불확실: 가독성. 사용자 미제약(전체 표시 결정).
   - 권장: 전체 표시(D-01 준수). 성능 무문제(아래).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| XlsxWriter | 워크북 작성 | ✓ | 3.2.9 [VERIFIED] | — |
| openpyxl | 테스트 read-back | ✓ | 3.1.5 [VERIFIED] | — |
| pandas | OHLCV 리샘플 | ✓ | ≥2.2 [CITED pyproject] | — |
| pytest | 테스트 | ✓ | ≥8.0 [CITED pyproject] | — |
| `data/fundamentals.db` | compute_matrix/fetch_raw 입력 | 런타임 의존 | — | 없음 — DB 미적재 시 D-15 안내 후 종료(`count_rows()==0`) |
| `.cache/ohlcv` | 분기말 종가(캐시 HIT) | 런타임 | — | 캐시 MISS 시 yfinance 호출(키 불요·throttle 적용) |

**Missing dependencies with no fallback:** `data/fundamentals.db` 미적재 시 렌더 불가 → 한국어 안내 후 정상 종료(예외 아님, D-15).
**Missing dependencies with fallback:** OHLCV 캐시 MISS → `fetch_ohlcv_cached`가 yfinance로 자동 보충(기존 throttle/retry).

## 성능 (200종목 × 9지표 × 다분기)

- **외부 호출:** 펀더멘털 = **0**(전부 DB·엔진). OHLCV = 캐시 HIT 시 0, MISS 시 종목당 1회(기존 throttle 2 RPS). 평소 main 실행 직후 트렌드 렌더 시 OHLCV 캐시 전부 HIT(24h TTL).
- **DB 읽기:** `compute_matrix`/`fetch_raw_quarters`가 종목당 1 SELECT(인덱스 `idx_raw_ticker_q`). 200 SELECT = 무시 가능.
- **계산:** 종목당 9지표 × ~40분기 순수 산술 + OHLCV 리샘플 1회. 200종목 = 수만 셀 산술 → 1초 미만 예상(ASSUMED — 벤치 미실행, pandas 벡터 연산).
- **워크북:** 9 매트릭스 시트 × (200행 × 45열) + [원천](200종목 × 분기 × 필드 long, 수만 행 가능) + 스냅샷. `make_workbook`은 현재 `constant_memory=False`. 트렌드 [원천] 시트가 수만 행이면 `constant_memory=True` 검토(메모리↓, 단 행 순차 작성 강제). **권장:** 우선 `False`로 시작, [원천] 행수가 크면 전용 워크북 팩토리에서 `True` 옵션화. [CITED: writer.py L86-88 — 현재 False, 합리적 워크북 크기 가정]

## Validation Architecture

> `workflow.nyquist_validation: true` (config.json 확인) → 본 섹션 포함. VALIDATION.md 생성 트리거.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (+ pytest-mock, openpyxl, freezegun — dev group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=src) |
| Quick run command | `.venv/Scripts/python.exe -m pytest tests/test_history_render.py -x -q` |
| Full suite command | `.venv/Scripts/python.exe -m pytest -q` (현재 baseline 341 passed) |

### Phase Requirements → Test Map
| Req / SC | Behavior | Test Type | Automated Command | File Exists? |
|----------|----------|-----------|-------------------|-------------|
| SC1 | 별도 파일 생성 + 시트1 불변 | integration | `pytest tests/test_history_render.py::test_separate_file_sheet1_untouched -x` | ❌ Wave 0 |
| SC2 | 지표별 매트릭스 행=종목·열=분기(최신 왼쪽 D-01) | unit(openpyxl) | `pytest tests/test_history_render.py::test_matrix_layout_latest_left -x` | ❌ Wave 0 |
| SC3 | [원천]·[최신 스냅샷] 시트 존재·내용 | unit(openpyxl) | `pytest tests/test_history_render.py::test_raw_and_snapshot_sheets -x` | ❌ Wave 0 |
| SC4 | 과거=분기말 종가·최신=현재가 (D-09) | unit | `pytest tests/test_quarter_price.py::test_quarter_end_close_and_current -x` | ❌ Wave 0 |
| D-05/06/07 | 상대색 방향·표본 게이트 무색 | unit | `pytest tests/test_trend_color.py -x` | ❌ Wave 0 |
| D-08 | YoY 화살표 ▲/▼·전년결손 생략 | unit | `pytest tests/test_trend_color.py::test_yoy_glyph -x` | ❌ Wave 0 |
| D-10 | 분기별 PEG 산출 | unit | `pytest tests/test_history_render.py::test_peg_per_quarter -x` | ❌ Wave 0 |
| D-11 | 결손 `"-"` + 코멘트 | unit(openpyxl) | `pytest tests/test_history_render.py::test_missing_dash_comment -x` | ❌ Wave 0 |
| D-04 | freeze panes (A열+헤더) | unit(openpyxl) | `pytest tests/test_history_render.py::test_freeze -x` | ❌ Wave 0 |
| 회귀 | 시트1 전 스위트 그린 | regression | `pytest -q` | ✅ 기존 341 passed |

### Sampling Rate
- **Per task commit:** `pytest tests/test_history_render.py tests/test_trend_color.py tests/test_quarter_price.py -x -q`
- **Per wave merge:** `pytest -q` (full — 시트1 회귀 무손상 보장)
- **Phase gate:** full suite green + 수기 시각 검증(한국 1·미국 1 종목으로 분기말 종가·색·화살표 육안 확인) before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_history_render.py` — 오케스트레이션·매트릭스 레이아웃·결손·freeze (SC1~3, D-04/10/11)
- [ ] `tests/test_trend_color.py` — 상대색 방향/표본 게이트/YoY 글리프 (D-05/06/07/08) — **순수 함수, 네트워크 0**
- [ ] `tests/test_quarter_price.py` — 분기말 종가 리샘플 (D-09) — 합성 OHLCV fixture
- [ ] `tests/fixtures/` — 합성 raw_quarters(기존 `tests/fixtures/raw_quarters.py::raw_row` 재사용) + 합성 OHLCV(기존 `_make_ohlcv` 패턴 차용) + 다종목·다산업 fixture
- [ ] 네트워크 0 전략: `compute_matrix(ticker, fetch_fn=<stub>)`로 DB 비결합 주입(엔진이 fetch_fn 파라미터 노출 — L301). OHLCV는 `fetch_ohlcv_cached` monkeypatch(test_freeze_panes 패턴).

## Security Domain

> `security_enforcement` 미설정(=enabled). Phase 9는 로컬 파일 렌더·DB 읽기 전용 — 공격면 최소.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | 렌더는 인증 불요(DB가 진실). |
| V3 Session Management | no | — |
| V4 Access Control | no | 로컬 단일 사용자. |
| V5 Input Validation | yes (경미) | tickers.txt 파싱은 기존 `read_tickers_extended`(검증됨). DB SELECT는 `?` 바인딩(`fetch_raw_quarters`·`count_rows` 기검증, T-08-01). 신규 SQL 작성 금지. |
| V6 Cryptography | no | — |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection | Tampering | 신규 SQL 미작성 — 기존 `?`-바인딩 함수만 호출(store). |
| 시트명 인젝션(Excel 금지 문자) | Tampering | 지표 시트명은 고정 리터럴(PER/PEG/...). 산업/티커가 시트명에 안 들어감(셀 값만). 만약 동적 시트명 필요 시 `sheet_portfolio._sanitize_sheet_name` 패턴 재사용. |
| 비밀 누설(로그) | Info Disclosure | 예외 로그는 `type(exc).__name__`만(기존 main_run 패턴 L349). |

## Project Constraints (from CLAUDE.md)

- **XlsxWriter 정적 색 베이킹·인플레이스 미사용** — 상대색은 Python 사전계산 후 `add_format` 베이킹(conditional_format 색조 미사용). 워크북은 write-only(openpyxl 인플레이스 수정 금지).
- **한국어 우선** — 시트 헤더·로그·코멘트·안내 메시지 한국어. 코드/API/경로/분기키(`YYYYQn`)는 영어 유지.
- **Core Value 불변** — 시트1 `portfolio_*.xlsx` 레이아웃·색 신호 절대 미수정. 트렌드는 완전 별도 파일.
- **Tech stack** — Python 3.13 / XlsxWriter / pandas / pytest / uv. 신규 외부 의존 추가 금지(전부 기설치).
- **데이터 소스 우선순위** — 재무 = EDGAR→DART→yf (이미 store에 반영, `fetch_raw_quarters` source 정렬 WR-01).
- **성능** — 200종목 비현실적 지연 금지. 트렌드는 외부 호출 ≈0(DB·캐시)이라 충족.

## Sources

### Primary (HIGH confidence)
- 직접 코드 read (확정): `metrics_engine.py`(compute_matrix L299/price_ratio L251/compute_peg_cell L267/_calendar_quarter_offset L69), `metrics_registry.py`(REGISTRY 9+4 L79), `fundamentals_store.py`(fetch_raw_quarters L166 반환 7-tuple/count_rows L155/SCHEMA L48), `fundamentals.py`(MetricCell L33/_is_missing L72/_compute_peg L92), `sheet_portfolio.py`(_COL L63/PORTFOLIO_COLUMNS L37/freeze_panes(5,1) L336), `writer.py`(make_workbook L70/constant_memory=False L86), `main.py`(argparse L37)·`main_run.py`(run L235/히스토리 루프 L334), `input.py`(TickerSpec/read_tickers_extended), `company.py`(fetch_company_name L97), `market_kind.py`(classify_market L15), `market.py`(fetch_ohlcv_cached L101), `cache.py`(OHLCV 24h TTL).
- 설치본 실행 검증: `xlsxwriter 3.2.9`(write_rich_string/conditional_format/write_comment 존재), `openpyxl 3.1.5`(Cell.value/fill/font/comment), `pandas resample('QE').last() + to_period('Q')` → `['2024Q1'...]` 정상.
- `pyproject.toml`(의존 버전), `config.json`(nyquist_validation:true), `09-CONTEXT.md`(D-01~D-15), `08-CONTEXT`/`STATE.md`(엔진 계약).

### Secondary (MEDIUM confidence)
- CLAUDE.md Technology Stack 섹션 — XlsxWriter conditional_format/icon_set/Format 능력(HIGH 출처 인용표 포함), pandas ewm·resample.

### Tertiary (LOW confidence)
- XlsxWriter 공식 docs WebFetch 시도 — HTTP 429(rate-limited) 미취득. 대신 설치본 method 존재 검증 + CLAUDE.md 인용 출처로 대체(동등 신뢰).

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 신규 0, 전부 설치본·pyproject 검증.
- Architecture (데이터 흐름·분기말 종가·이중 인코딩): HIGH — 엔진 시그니처 직접 read, 리샘플 실행 검증.
- Pitfalls: HIGH — 분기축 방향·키 일치·모집단 정의는 코드 근거.
- 상대색/YoY 구현 선택: MEDIUM-HIGH — 정적 베이킹은 CLAUDE.md 정합·실측 가능, 세부(동값 처리·rich_string vs 문자열)는 planner 재량 ASSUMED.

**Research date:** 2026-06-22
**Valid until:** 2026-07-22 (안정 스택 — 30일). 단 pandas `'QE'` 표기는 2.x 고정.

---

## RESEARCH COMPLETE

**Phase:** 9 - 트렌드 엑셀 렌더 (FUND-10)
**Confidence:** HIGH

### Key Findings
- **신규 외부 의존 0** — 전부 기설치(XlsxWriter 3.2.9 / openpyxl 3.1.5 / pandas ≥2.2, 설치본 실행 검증). Phase 9는 순수 렌더 층.
- **분기말 종가(D-09)** = `fetch_ohlcv_cached(t).Close.resample("QE").last()` + `to_period("Q").astype(str)` → `{YYYYQn: 종가}`, 최신=`Close.iloc[-1]`. 휴장일 자동 처리(실행 검증). **주의:** `fetch_raw_quarters` 반환 튜플에 `period_end` 미포함 → 종가는 raw가 아닌 OHLCV에서.
- **이중 인코딩 권장:** 상대색 = Python 사전계산 정적 Format 베이킹(conditional_format 기각 — 방향 반전·산업 그룹 분할·표본 게이트 표현 불가, CLAUDE.md 정합). YoY 화살표 = 유니코드 글리프(▲▼) 셀 텍스트(icon_set 기각 — 셀 자기값 기준이라 YoY 불가).
- **데이터 흐름:** `compute_matrix`는 **ticker별 호출**, 분기축 **오름차순** 반환 → D-01(최신 왼쪽)은 `reversed` 필수. 다종목은 분기 **합집합**으로 전치(`.get` 가드).
- **CLI(D-15):** `main.py` argparse 서브커맨드(`history`) + 새 엔트리 `run_history`(main_run 비결합). DB 미적재 시 `count_rows()==0` → 한국어 안내 후 종료.

### File Created
`.planning/phases/09-trend-render/09-RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | 신규 0, 설치본·pyproject 검증 |
| Architecture | HIGH | 엔진 시그니처 직접 read, 리샘플 실행 검증 |
| Pitfalls | HIGH | 분기축 방향·키 일치·모집단 코드 근거 |
| 구현 선택(색/화살표) | MEDIUM-HIGH | 정적 베이킹 CLAUDE.md 정합, 세부 planner 재량(A1/A2/A4) |

### Open Questions
1. 현재가(최신 열) 트렌드 vs 시트1 일관성 — 동일 `fetch_ohlcv_cached` 진입점이면 드리프트 0(Phase 10이 완전 통일).
2. [최신 스냅샷] PEG = 매트릭스 최신 열 셀 재사용(재계산 없이 일관).
3. 분기 열 상한(최대 40) — 전체 표시(D-01), 성능 무문제.

### Ready for Planning
Research 완료. VALIDATION.md 생성 트리거(nyquist_validation:true) — Validation Architecture 섹션에 SC1~4·D-05~11 테스트 맵·Wave 0 갭(3 신규 테스트 파일 + fixture) 포함. Planner는 PLAN.md 작성 가능.
