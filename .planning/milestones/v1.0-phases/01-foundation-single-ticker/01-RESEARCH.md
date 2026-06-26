# Phase 1: 기반 + 단일 티커 수직 슬라이스 - Research

**Researched:** 2026-05-20
**Domain:** Python(3.13) 단일-티커 vertical slice — yfinance OHLCV → pandas EMA/expanding-stats/Stoch/RSI → XlsxWriter 정적 색 베이킹
**Confidence:** HIGH (요청 시 9개 focus 영역 모두 명시적 결정이 있고, 프로젝트 레벨 STACK.md/PITFALLS.md에 검증된 사실 누적됨)

## Summary

Phase 1은 첫 코드 phase이자 Walking Skeleton이다. 모든 거시 결정(스택 핀, 레이어 구조, 색 정책, 데이터 윈도우, retry 정책)이 CONTEXT.md D-01~D-06에 잠겨 있으므로, 본 RESEARCH는 **planner가 task로 분해할 때 즉시 적용 가능한 구체적 함수 시그니처·코드 패턴·검증 입력값**에 초점을 맞춘다. 비탐색적, 처방적 톤.

핵심 위험은 세 가지로 압축된다:
1. **EMA·Stoch·RSI 계산 정확성** — pandas-ta 없이 native 구현이므로 알려진 입력→기댓값 단위 테스트 골든 셋이 필수.
2. **expanding window 초기 행 NaN 처리** — D-02에 따라 기본색을 유지해야 하므로 `color_rules.py` 함수는 NaN/0 입력을 명시적으로 분기해야 함.
3. **XlsxWriter Format 객체 캐싱** — 셀마다 새 Format을 만들면 워크북 무결성 경고(중복 dxf) + 메모리 증가. 7개 색 신호 → 7개 Format 미리 만들어 lookup.

**Primary recommendation:** `compute/color_rules.py`에 `decide_style(value, median, std) -> ColorBucket(Enum)` pure 함수를 두고, `output/sheet_per_ticker.py`에서 Enum→Format 매핑 dict (워크북 생성 시 1회 초기화)으로 lookup. 정적 색 베이킹·테스트 가능성·Phase 4 톤 튜닝 동시 만족.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| `tickers.txt` 파싱·검증 | `io/input.py` | — | 외부 입력 어댑터 |
| `.env` 로드 (EDGAR/DART 키) | `config.py` | — | 모든 모듈이 의존하는 설정 |
| yfinance + curl_cffi + tenacity | `io/market.py` | — | 외부 시세 어댑터 |
| EMA / 차이 / 일변동 | `compute/ema.py` | — | 순수 계산, DataFrame in/out |
| expanding median/std | `compute/stats.py` | — | 순수 계산 |
| Stoch Slow(14,3,3), RSI(14 Wilder) | `compute/indicators.py` | — | 순수 계산 |
| 색 신호 결정 로직 | `compute/color_rules.py` | — | 순수 함수, 색 정책 단일 출처 |
| 워크북 라이프사이클 | `output/writer.py` | — | XlsxWriter 객체 소유 |
| 시트 1개 작성 | `output/sheet_per_ticker.py` | `output/writer.py` | Format 캐시는 writer가 소유, sheet writer가 lookup |
| 오케스트레이션 (argparse, 로깅 setup) | `main.py` | — | 엔트리포인트만 |

순수 계산(`compute/*`)은 외부 의존성이 없는 함수로 구성 — 단위 테스트가 mock 없이 가능해야 함.

## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01:** `src/stocksig/{io,compute,output}/` 3-레이어 구조 (CONTEXT.md decisions A의 디렉토리 트리 그대로). `main.py`는 엔트리포인트만.
- **D-02:** expanding window 초기 행(NaN 또는 std=0) → 색 베이킹 미적용, 기본 글자색·배경색. `color_rules`는 `None`(또는 default bucket) 반환, writer는 색 인자 미지정.
- **D-03:** 좌→우 컬럼 배치 — 5행 한국어 헤더, 6행부터 데이터, 그룹 순서: 날짜 → 원천 OHLCV(+med/std 인접) → 1차 EMA(종/고/저 × 11/22/96/192 = 12개, 각 +med/std) → 2차 차이(12개, 각 +med/std) → 2차 EMA 일변동(12개, 각 +med/std) → Stoch %K, %D, RSI.
- **D-04:** Material Design 800/900 글자 + 100 배경 4색 정책. 구체 hex 잠금:
  - 1σ~2σ (-): font `#2E7D32` (Green 800), bg 없음
  - 1σ~2σ (+): font `#C62828` (Red 800), bg 없음
  - <중앙값-2σ: font `#1B5E20` (Green 900), bg `#C8E6C9` (Green 100)
  - >중앙값+2σ: font `#B71C1C` (Red 900), bg `#FFCDD2` (Red 100)
  - Stoch ≤20 / RSI ≤30: font `#2E7D32`, bg 없음
  - Stoch ≥80 / RSI ≥70: font `#C62828`, bg 없음
  - 기본: font `#000000`, bg 없음
- **D-05:** stdlib `logging`. 한국어 메시지. 포맷: `[LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지`.
- **D-06:** `yfinance.Ticker(ticker).history(start=today - timedelta(days=4000), end=today, auto_adjust=True)`. tenacity: `wait_exponential(multiplier=1, min=2, max=30) + wait_random(0,1) + stop_after_attempt(5) + retry_if_exception_type(YFRateLimitError)`.

### Claude's Discretion

- 색 팔레트 hex 값은 `compute/color_rules.py`의 모듈 상수로 노출 (Phase 4 튜닝 대비 단일 지점).
- 시트가 매우 넓어짐 — planner는 컬럼 인덱스 매핑 표를 산출 (Phase 1 산출물의 일부).
- 1차 검증 티커: `AAPL`.
- 로깅 출력 인코딩: `logging.basicConfig(..., encoding='utf-8')` + Windows console fallback (`sys.stdout.reconfigure(encoding='utf-8')`).

### Deferred Ideas (OUT OF SCOPE)

- 시트1 통합 포트폴리오 요약 → Phase 2
- sqlite OHLCV 캐시 (24h TTL) → Phase 2
- 토큰버킷 throttle + max_workers=4 팬아웃 → Phase 2
- 부분 데이터 (<50%) 검증/품질 보고 → Phase 4
- EDGAR/DART 실제 호출 → Phase 3
- frozen panes (1~5행) → Phase 4
- rich progress bar → Phase 2~4
- 파스텔 색 톤 그레이스케일 시각 검증 → Phase 4

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INPUT-01 | `tickers.txt` 한 줄당 티커 파싱 | `io/input.py` 단순 read+strip+filter empty |
| INPUT-02 | US/KR (`.KS`/`.KQ`) 혼용 | Phase 1은 단일 미국 티커지만 파서는 suffix-agnostic |
| INPUT-03 | 빈/없는 파일 → 한국어 에러 + 비0 종료 | `FileNotFoundError`/empty → `sys.exit(1)` + logging.error |
| INPUT-05 | `.env` `EDGAR_USER_AGENT_EMAIL`, `OPENDART_API_KEY` 로드 | python-dotenv `load_dotenv()` + `os.environ` 검증, 비어있으면 fail-fast |
| MKTD-01 | today-4000d ~ today 일봉 OHLCV | D-06 시그니처 고정 |
| MKTD-02 | curl_cffi Chrome impersonation | `curl_cffi.requests.Session(impersonate="chrome")` to `yf.Ticker(t).history(session=...)` (yfinance ≥0.2.60 패턴) |
| MKTD-03 | tenacity 지수 백오프+지터 재시도 | D-06 정책 |
| COMP-01 | 종/고/저 × EMA11/22/96/192 = 12개 | `df.ewm(span=N, adjust=False).mean()` (PITFALLS Pitfall 5 준수: `adjust=False`) |
| COMP-02 | 가격 - EMA = 12개 차이 시리즈 | 산술 차분 |
| COMP-03 | EMA 일변동 = EMA.diff() | `df['EMA_close_11'].diff()` × 4 EMA × 3 가격 = 12개 |
| COMP-04 | expanding median/std (모든 데이터 열) | `df[col].expanding().median()` / `.std()` |
| COMP-05 | 10년 누적 중앙값·표준편차 스칼라 | `df[col].median()` / `.std()` — 시트 3·4행 |
| COMP-06 | 거래량 expanding | COMP-04와 동일 처리 |
| TECH-01 | Stoch Slow(14, 3, 3) native | 공식 §"Code Examples" 참조 |
| TECH-02 | RSI(14) Wilder | 공식 §"Code Examples" 참조 |
| TECH-03 | 6행부터 날짜 내림차순 | DataFrame.sort_index(ascending=False) 후 write |
| TECH-04/05/06 | Stoch/RSI 정적 색 베이킹 | D-04 임계값 정책 |
| SHEET-01 | 시트 이름 = 티커 | `workbook.add_worksheet(ticker)` |
| SHEET-02 | A1 = 티커 | row=0, col=0 |
| SHEET-03 | 3행 = 누적 중앙값 (스칼라, 각 데이터 컬럼) | row=2 |
| SHEET-04 | 4행 = 누적 표준편차 (스칼라) | row=3 |
| SHEET-05 | 5행 = 한국어 헤더 | row=4 |
| SHEET-06 | 6행부터 데이터, 날짜 내림차순 | row=5+ |
| SHEET-07 | 원천/1차/2차 그룹 | D-03 |
| SHEET-08 | 각 데이터 열 옆 med/std 인접 | D-03 |
| COLOR-01~07 | 정적 색 베이킹, σ 정책 | D-04 hex + `compute/color_rules.py` |
| OUT-01 | `output/portfolio_YYYYMMDD.xlsx` | `f"portfolio_{datetime.now():%Y%m%d}.xlsx"` |
| OUT-02 | XlsxWriter | `xlsxwriter.Workbook(path)` |
| OUT-03 | 매번 새 파일 | path가 항상 새 날짜 — 같은 날 재실행은 overwrite (Phase 1 단순화) |
| EXEC-01 | `python main.py` Windows 실행 | entrypoint script |
| EXEC-02 | uv + pyproject.toml | `[project]` + `[tool.hatch.build.targets.wheel] packages = ["src/stocksig"]` |

## Standard Stack

### Core (모두 Phase 0 STACK.md에서 핀 — 재확인용)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.x | Runtime | 3.13 wheel 지원 확인됨 [VERIFIED: STACK.md] |
| uv | 0.5+ | Dep manager | pyproject.toml + lockfile [VERIFIED: STACK.md] |
| yfinance | ≥0.2.66 | OHLCV | session API ≥0.2.60 변경 후 [VERIFIED: STACK.md] |
| curl_cffi | ≥0.15,<0.16 | TLS 임퍼소네이션 | CVE-2743 회피 (0.14 금지) [VERIFIED: STACK.md] |
| pandas | 2.2.x | DataFrame + ewm + expanding | NumPy 2 지원 [VERIFIED: STACK.md] |
| numpy | 2.x | 수치 primitive | [VERIFIED: STACK.md] |
| XlsxWriter | 3.2.x | xlsx 생성 (정적 색) | Format API + constant_memory 모드 [VERIFIED: STACK.md] |
| tenacity | 9.x | 재시도 데코레이터 | wait/stop/retry_if 조합 [VERIFIED: STACK.md] |
| python-dotenv | 1.0+ | `.env` 로드 | [VERIFIED: STACK.md] |

### Supporting (Phase 1)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | 8.x | 테스트 러너 | Validation Architecture 참조 |
| pytest-mock | latest | yfinance mock | 단위 테스트에서 네트워크 호출 차단 |

**Phase 1에서 안 쓰는 것 (재확인):**
- `rich` / `loguru` — stdlib logging만 (D-05)
- `pandas-ta` — native (TECH-01, TECH-02 명시) [CITED: REQUIREMENTS.md]
- `edgartools` / `OpenDartReader` — Phase 3 deferred

**Installation:**
```bash
uv init --package
uv add yfinance "curl_cffi>=0.15,<0.16" pandas numpy XlsxWriter tenacity python-dotenv
uv add --dev pytest pytest-mock
```

## Package Legitimacy Audit

> Phase 1 패키지는 모두 STACK.md에서 이미 검증된 mainstream 라이브러리. 본 phase에서 신규 패키지 미도입.

| Package | Registry | Age | Downloads (대략) | Source Repo | slopcheck | Disposition |
|---------|----------|-----|------------------|-------------|-----------|-------------|
| yfinance | PyPI | 8+ yrs | 수백만/주 | github.com/ranaroussi/yfinance | n/a (도구 미설치) | Approved [CITED: STACK.md] |
| curl_cffi | PyPI | 3+ yrs | 활발 | github.com/lexiforest/curl_cffi | n/a | Approved [CITED: STACK.md] |
| pandas | PyPI | 15+ yrs | 1억+/월 | github.com/pandas-dev/pandas | n/a | Approved |
| numpy | PyPI | 20+ yrs | 1억+/월 | github.com/numpy/numpy | n/a | Approved |
| XlsxWriter | PyPI | 12+ yrs | 수백만/월 | github.com/jmcnamara/XlsxWriter | n/a | Approved |
| tenacity | PyPI | 10+ yrs | 수천만/월 | github.com/jd/tenacity | n/a | Approved |
| python-dotenv | PyPI | 11+ yrs | 1억+/월 | github.com/theskumar/python-dotenv | n/a | Approved |

slopcheck CLI 미실행 (도구 부재). 모든 패키지가 GitHub 공식 저장소·다년간 다운로드 이력 보유. [ASSUMED] 태그를 따로 부여하지 않음 — STACK.md 단계에서 이미 검증된 핀을 그대로 사용.

## Architecture Patterns

### System Architecture Diagram

```
                              [tickers.txt]   [.env]
                                    │            │
                                    ▼            ▼
                       ┌────────────────────────────────┐
                       │           main.py              │
                       │  (argparse → orchestrate)      │
                       └────────────────────────────────┘
                              │            │            │            │
                              ▼            ▼            ▼            ▼
                        io.input    config.load    io.market    output.writer
                        read_tickers  .env env →    fetch_ohlcv  Workbook 생성
                              │      EDGAR_*,       (yfinance +  + Format 캐시
                              │      OPENDART_*     curl_cffi +
                              │                     tenacity)
                              │            │            │            │
                              │            │            ▼            │
                              │            │       pd.DataFrame      │
                              │            │       (OHLCV 일봉)      │
                              │            │            │            │
                              │            │            ▼            │
                              │            │   ┌────────────────┐    │
                              │            │   │  compute layer │    │
                              │            │   ├────────────────┤    │
                              │            │   │ ema.py: 12 EMA │    │
                              │            │   │ + 12 차이      │    │
                              │            │   │ + 12 일변동    │    │
                              │            │   ├────────────────┤    │
                              │            │   │ stats.py:      │    │
                              │            │   │ expanding      │    │
                              │            │   │ median/std     │    │
                              │            │   │ + 누적 스칼라  │    │
                              │            │   ├────────────────┤    │
                              │            │   │ indicators.py: │    │
                              │            │   │ Stoch %K, %D   │    │
                              │            │   │ RSI(14 Wilder) │    │
                              │            │   └────────────────┘    │
                              │            │            │            │
                              │            │            ▼            │
                              │            │      enriched DataFrame │
                              │            │      (행=날짜, 열=수십개)│
                              │            │            │            │
                              │            │            ▼            │
                              │            │   ┌────────────────┐    │
                              │            │   │ color_rules.py │    │
                              │            │   │ (행별 ColorBuc-│    │
                              │            │   │  ket 결정,     │    │
                              │            │   │  pure fn)      │    │
                              │            │   └────────────────┘    │
                              │            │            │            │
                              │            │            ▼            │
                              └────────────┴─────output.sheet_per_ticker
                                                 (write_workbook이
                                                  미리 만든 Format
                                                  객체를 lookup으로
                                                  적용하며 worksheet.
                                                  write_*)
                                                       │
                                                       ▼
                                          [output/portfolio_YYYYMMDD.xlsx]
```

데이터 흐름: 입력 어댑터 → 시세 어댑터 → 순수 계산 → 색 결정(순수) → xlsx writer.

### Recommended Project Structure (D-01에서 잠금)

```
example/
├── main.py                        # 엔트리포인트
├── pyproject.toml                 # uv + hatch (또는 setuptools, 아래 결정)
├── .env.example                   # EDGAR_USER_AGENT_EMAIL=, OPENDART_API_KEY=
├── tickers.txt                    # 단일 티커 예: AAPL
├── output/                        # .gitignore 대상, 런타임 생성
├── src/
│   └── stocksig/
│       ├── __init__.py
│       ├── config.py              # load_dotenv, 상수 (PALETTE, EMA_PERIODS=[11,22,96,192])
│       ├── io/
│       │   ├── __init__.py
│       │   ├── input.py
│       │   └── market.py
│       ├── compute/
│       │   ├── __init__.py
│       │   ├── ema.py
│       │   ├── stats.py
│       │   ├── indicators.py
│       │   └── color_rules.py
│       └── output/
│           ├── __init__.py
│           ├── writer.py
│           └── sheet_per_ticker.py
└── tests/
    ├── conftest.py
    ├── test_input.py
    ├── test_ema.py
    ├── test_stats.py
    ├── test_indicators.py
    ├── test_color_rules.py
    └── test_smoke_end_to_end.py
```

### Pattern 1: pyproject.toml + src-layout (uv 부트스트랩)

**Backend 결정: hatchling** (uv 기본, 마찰 적음, src-layout native).

```toml
# pyproject.toml
[project]
name = "stocksig"
version = "0.1.0"
description = "표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트"
requires-python = ">=3.13"
dependencies = [
    "yfinance>=0.2.66",
    "curl_cffi>=0.15,<0.16",
    "pandas>=2.2",
    "numpy>=2.0",
    "XlsxWriter>=3.2",
    "tenacity>=9.0",
    "python-dotenv>=1.0",
]

[dependency-groups]
dev = ["pytest>=8.0", "pytest-mock"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/stocksig"]
```

**Why hatchling over setuptools:** `[tool.hatch.build.targets.wheel] packages = ["src/stocksig"]` 한 줄. setuptools는 `[tool.setuptools.packages.find] where = ["src"]` + `[tool.setuptools.package-dir] "" = "src"` 두 줄 + 더 verbose. uv는 기본 build backend를 hatchling으로 권장. [CITED: hatchling docs]

### Pattern 2: yfinance + curl_cffi session 전달

```python
# src/stocksig/io/market.py
from curl_cffi import requests as curl_requests
import yfinance as yf
from yfinance.exceptions import YFRateLimitError
from tenacity import retry, wait_exponential, wait_random, stop_after_attempt, retry_if_exception_type
from datetime import date, timedelta
import pandas as pd

_SESSION = curl_requests.Session(impersonate="chrome")  # 모듈 레벨, 재사용

@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30) + wait_random(0, 1),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(YFRateLimitError),
    reraise=True,
)
def fetch_ohlcv(ticker: str) -> pd.DataFrame:
    today = date.today()
    start = today - timedelta(days=4000)
    df = yf.Ticker(ticker, session=_SESSION).history(
        start=start.isoformat(),
        end=today.isoformat(),
        auto_adjust=True,
    )
    if df.empty:
        raise ValueError(f"{ticker}: OHLCV 응답 비어있음")
    return df
```

**검증 포인트:** yfinance ≥0.2.60에서 `session=...` 인자는 `Ticker()` 생성자에 전달 (`history()` 인자가 아님). [CITED: PITFALLS Pitfall 1 + STACK.md]

### Pattern 3: pandas EMA (TradingView-호환)

```python
# src/stocksig/compute/ema.py
import pandas as pd

EMA_PERIODS = [11, 22, 96, 192]

def add_ema_columns(df: pd.DataFrame) -> pd.DataFrame:
    """종/고/저 × EMA11/22/96/192 = 12 컬럼, + 12 차이, + 12 일변동."""
    out = df.copy()
    for price_col in ["Close", "High", "Low"]:
        for n in EMA_PERIODS:
            ema = out[price_col].ewm(span=n, adjust=False).mean()
            out[f"EMA_{price_col}_{n}"] = ema
            out[f"DIFF_{price_col}_{n}"] = out[price_col] - ema
            out[f"EMA_{price_col}_{n}_dailychg"] = ema.diff()
    return out
```

**왜 `adjust=False`:** 재귀 공식 `EMA_t = α·P_t + (1-α)·EMA_{t-1}`, `α = 2/(N+1)`로 TradingView·MetaTrader·대부분 차트 도구와 일치 [VERIFIED: PITFALLS Pitfall 5 + STACK.md]. `adjust=True`는 모든 과거 점을 가중 평균하는 다른 공식.

**`min_periods` 처리:** Phase 1에서는 `min_periods` 미지정 (=`span`) — 처음 N행은 EMA가 seed 영향으로 정확하지 않으나, D-02에 따라 expanding std도 그 구간에서 불안정 → 색이 어차피 기본색. 별도 안전장치 불필요.

### Pattern 4: expanding window 통계 + 초기 행 안전 처리

```python
# src/stocksig/compute/stats.py
import pandas as pd
import numpy as np

def add_expanding_stats(df: pd.DataFrame, data_cols: list[str]) -> pd.DataFrame:
    """각 data_col에 대해 _median, _std 컬럼 추가 (expanding, look-ahead-free)."""
    out = df.copy()
    for col in data_cols:
        out[f"{col}_median"] = out[col].expanding().median()
        out[f"{col}_std"] = out[col].expanding().std()  # ddof=1 default
    return out

def cumulative_scalars(df: pd.DataFrame, data_cols: list[str]) -> dict[str, dict[str, float]]:
    """행 3·4용 전체 누적 스칼라."""
    return {
        col: {"median": df[col].median(), "std": df[col].std()}
        for col in data_cols
    }
```

**pandas 동작 확인된 사실:**
- `expanding().std()` 첫 행: NaN (표본 1개, ddof=1) [VERIFIED: pandas docs]
- `expanding().std()` 두 번째 행 이후: 정상 계산
- `expanding().median()` 첫 행: 그 값 자체 (NaN 아님)

→ `color_rules.py`의 NaN 분기가 첫 행을 흡수.

### Pattern 5: Stochastic Slow (14, 3, 3) — native

```python
# src/stocksig/compute/indicators.py
import pandas as pd

def stoch_slow(df: pd.DataFrame, k_period: int = 14, slowing: int = 3, d_period: int = 3) -> pd.DataFrame:
    """
    Stochastic Slow:
      Fast %K = 100 * (Close - LL_14) / (HH_14 - LL_14)
      Slow %K = SMA(Fast %K, slowing=3)
      Slow %D = SMA(Slow %K, d_period=3)
    표준 (14, 3, 3) 파라미터.
    """
    low_min = df["Low"].rolling(window=k_period, min_periods=k_period).min()
    high_max = df["High"].rolling(window=k_period, min_periods=k_period).max()
    denom = (high_max - low_min).replace(0, pd.NA)  # division-by-zero 방지
    fast_k = 100 * (df["Close"] - low_min) / denom
    slow_k = fast_k.rolling(window=slowing, min_periods=slowing).mean()
    slow_d = slow_k.rolling(window=d_period, min_periods=d_period).mean()
    return pd.DataFrame({"Stoch_%K": slow_k, "Stoch_%D": slow_d}, index=df.index)
```

**Off-by-one 함정:** `rolling(window=14, min_periods=14)`로 첫 13행을 명시적으로 NaN으로 두는 것이 표준. `min_periods=1`로 두면 표본 부족 구간에 의미 없는 값이 채워져 색 신호가 잘못 발화.

### Pattern 6: RSI (14, Wilder) — native

```python
def rsi_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """
    Wilder RSI(14):
      delta = Close.diff()
      gain = max(delta, 0), loss = max(-delta, 0)
      AvgGain_t = ((period-1) * AvgGain_{t-1} + gain_t) / period   # Wilder smoothing
      AvgLoss_t = ((period-1) * AvgLoss_{t-1} + loss_t) / period
      RS = AvgGain / AvgLoss
      RSI = 100 - 100 / (1 + RS)
    Wilder smoothing은 ewm(alpha=1/period, adjust=False)와 수학적으로 동등.
    """
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, pd.NA)
    rsi = 100 - (100 / (1 + rs))
    return rsi.rename("RSI")
```

**Wilder == ewm(alpha=1/N) 동등성:** Wilder smoothing 공식 `AvgGain_t = ((N-1)·AvgGain_{t-1} + gain_t) / N` 를 전개하면 `AvgGain_t = (1/N)·gain_t + ((N-1)/N)·AvgGain_{t-1}` → `alpha = 1/N`, `adjust=False`인 EWM과 정확히 일치 [VERIFIED: 수학적 동등성, 일반 기술 분석 문헌].

### Pattern 7: 색 결정 (순수 함수)

```python
# src/stocksig/compute/color_rules.py
from dataclasses import dataclass
from enum import Enum
import math

# 모듈 상수 — Phase 4에서 한 곳에서 튜닝
GREEN_800 = "#2E7D32"
GREEN_900 = "#1B5E20"
GREEN_100 = "#C8E6C9"
RED_800 = "#C62828"
RED_900 = "#B71C1C"
RED_100 = "#FFCDD2"
DEFAULT_BLACK = "#000000"

class SigmaBucket(Enum):
    DEFAULT = "default"          # |값-median| ≤ 1σ  또는 NaN/0
    SOFT_GREEN = "soft_green"    # 중앙값-2σ ≤ 값 < 중앙값-1σ
    HARD_GREEN = "hard_green"    # 값 < 중앙값-2σ
    SOFT_RED = "soft_red"        # 중앙값+1σ < 값 ≤ 중앙값+2σ
    HARD_RED = "hard_red"        # 값 > 중앙값+2σ

def decide_sigma_bucket(value, median, std) -> SigmaBucket:
    """D-02: median 또는 std가 NaN이거나 std==0이면 DEFAULT."""
    if value is None or median is None or std is None:
        return SigmaBucket.DEFAULT
    if any(isinstance(x, float) and math.isnan(x) for x in (value, median, std)):
        return SigmaBucket.DEFAULT
    if std == 0:
        return SigmaBucket.DEFAULT
    deviation = value - median
    if deviation < -2 * std:
        return SigmaBucket.HARD_GREEN
    if deviation < -std:
        return SigmaBucket.SOFT_GREEN
    if deviation > 2 * std:
        return SigmaBucket.HARD_RED
    if deviation > std:
        return SigmaBucket.SOFT_RED
    return SigmaBucket.DEFAULT

class TechBucket(Enum):
    DEFAULT = "default"
    SOFT_GREEN = "soft_green"
    SOFT_RED = "soft_red"

def decide_stoch_bucket(value) -> TechBucket:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return TechBucket.DEFAULT
    if value <= 20:
        return TechBucket.SOFT_GREEN
    if value >= 80:
        return TechBucket.SOFT_RED
    return TechBucket.DEFAULT

def decide_rsi_bucket(value) -> TechBucket:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return TechBucket.DEFAULT
    if value <= 30:
        return TechBucket.SOFT_GREEN
    if value >= 70:
        return TechBucket.SOFT_RED
    return TechBucket.DEFAULT
```

### Pattern 8: XlsxWriter Format 캐싱 + constant_memory 모드

```python
# src/stocksig/output/writer.py
import xlsxwriter
from stocksig.compute.color_rules import (
    SigmaBucket, TechBucket,
    GREEN_800, GREEN_900, GREEN_100, RED_800, RED_900, RED_100,
)

def make_workbook(path: str) -> tuple[xlsxwriter.Workbook, dict]:
    """워크북 생성 + 7개 Format 객체 캐시 dict 반환."""
    wb = xlsxwriter.Workbook(path, {"constant_memory": False})
    # constant_memory=False: 행 임의 순서 접근 가능 (Phase 1은 시트당 ~수십 컬럼 × ~2700행 — 메모리 부담 없음)
    # constant_memory=True는 행을 순차로만 쓸 수 있어 디버깅이 더 어렵고, 컬럼 폭 자동 조정 등 일부 기능 제약.

    formats = {
        SigmaBucket.DEFAULT:     wb.add_format({}),  # 기본 — 또는 None을 sentinel로 사용
        SigmaBucket.SOFT_GREEN:  wb.add_format({"font_color": GREEN_800}),
        SigmaBucket.SOFT_RED:    wb.add_format({"font_color": RED_800}),
        SigmaBucket.HARD_GREEN:  wb.add_format({"font_color": GREEN_900, "bg_color": GREEN_100}),
        SigmaBucket.HARD_RED:    wb.add_format({"font_color": RED_900,   "bg_color": RED_100}),
        TechBucket.SOFT_GREEN:   wb.add_format({"font_color": GREEN_800}),  # Stoch/RSI 매수
        TechBucket.SOFT_RED:     wb.add_format({"font_color": RED_800}),    # Stoch/RSI 매도
        TechBucket.DEFAULT:      wb.add_format({}),
    }
    # 추가: 헤더용 Format (5행 한국어 헤더 가독성)
    formats["header"] = wb.add_format({"bold": True, "align": "center"})
    return wb, formats
```

**Format 캐싱 이유:** XlsxWriter는 내부적으로 사용된 모든 `Format` 객체를 워크북의 `styles.xml`에 dedup해서 저장하지만, **`add_format()`을 매번 호출하면 매번 새 Python 객체가 생성**되어 (1) 메모리 증가, (2) `styles.xml` 내 중복 정의 발생 가능. 시트당 ~50 컬럼 × ~2700행 = 135k 셀이므로 셀당 새 객체 = 135k Format 객체. 7개로 lookup하면 7개만.

**셀별 적용:**
```python
ws = wb.add_worksheet(ticker)
bucket = decide_sigma_bucket(value, median, std)
fmt = formats[bucket] if bucket != SigmaBucket.DEFAULT else None
if fmt is None:
    ws.write(row, col, value)
else:
    ws.write(row, col, value, fmt)
```

**constant_memory=True 호환성:** XlsxWriter 공식 문서상 `constant_memory=True`도 Format 캐싱과 호환된다. 다만 행을 순차로 써야 함 — Phase 1의 SHEET-06(날짜 내림차순)이 이미 정렬을 강제하므로 자연스럽게 충족. Phase 1에서는 `constant_memory=False`로 시작하고 Phase 2(100 티커 팬아웃) 시점에 메모리 측정 후 결정 권장.

### Pattern 9: 한국어 로깅 (Windows console)

```python
# main.py 상단
import sys, logging

# Windows console UTF-8 강제 (cp949 폴백 대응)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass  # 이미 utf-8이면 무시

logging.basicConfig(
    level=logging.INFO,
    format="[%(levelname)s] %(asctime)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    encoding="utf-8",  # Python 3.9+: FileHandler 기본 인코딩 (StreamHandler에는 영향 없음)
)
```

**Windows 콘솔 한국어 출력 신뢰성:**
- Windows 10 build 1903+ / Windows 11은 콘솔이 기본 UTF-8 지원 향상되었으나, 기본 코드 페이지는 여전히 cp949 (한국어 로케일).
- `sys.stdout.reconfigure(encoding='utf-8')`은 Python 3.7+에서 동작 [VERIFIED: Python docs].
- 추가 안전장치로 `PYTHONIOENCODING=utf-8` 환경변수 또는 PowerShell `chcp 65001` 안내를 README에 명시 권장.
- `logging.basicConfig(encoding=...)`은 Python 3.9+에서 추가됨; StreamHandler가 sys.stdout/stderr을 사용하면 reconfigure가 충분.

### Anti-Patterns to Avoid

- **셀마다 `wb.add_format(...)` 호출** — Format 객체 폭증. (Pattern 8 참조)
- **`pandas.ewm(span=N, adjust=True)`** — TradingView와 일치 안함. 반드시 `adjust=False`.
- **`rolling(window=14, min_periods=1)`** — 표본 부족 구간에 잘못된 Stoch/RSI 값 발화.
- **yfinance에 `requests.Session()` 전달** — ≥0.2.60에서 거부됨. `curl_cffi.requests.Session(impersonate="chrome")` 필수.
- **`auto_adjust=False` + `adjust=True`** 혼용 — σ가 split 점프로 왜곡.
- **시트 이름에 슬래시·콜론** — XlsxWriter가 시트 이름을 거부. 단, Phase 1은 영문 미국 티커만이라 무관 (Phase 2에서 KR 티커 도입 시 sanitize 필요).
- **expanding std==0인 행에 그대로 (value-median)/std 비교** — DivisionByZero 또는 inf. `color_rules.py`가 0 분기 명시.
- **하드코딩된 `output/portfolio_20260520.xlsx` 경로** — `f"output/portfolio_{datetime.now():%Y%m%d}.xlsx"` + `Path("output").mkdir(exist_ok=True)`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 지수 백오프 + 지터 + 예외 타입별 재시도 | 수동 while-loop + sleep + try/except | `tenacity` 데코레이터 조합 | jitter·max attempts·예외 화이트리스트가 보기보다 미묘 |
| `.env` 파싱 | 수동 `open().readlines()` + split | `python-dotenv.load_dotenv()` | 따옴표/이스케이프/주석 처리 |
| EMA 계산 | 직접 재귀 루프 | `pandas.ewm(span=N, adjust=False).mean()` | C 구현, NaN 전파 일관성 |
| expanding median/std | 수동 슬라이싱 | `pd.Series.expanding()` | O(N) vs O(N²) |
| TLS 임퍼소네이션 | requests + 헤더 조작 | `curl_cffi.requests.Session(impersonate="chrome")` | TLS 핑거프린트 자체가 차단 신호 |
| xlsx 작성 | 직접 XML 조립 | XlsxWriter | OpenXML 스펙은 작지 않음 |
| Stoch/RSI 수동 검증 | "내가 만든 게 맞겠지" | 알려진 입력 골든 셋 (아래) | 표본 한 개 off-by-one이 색 신호 전체를 잘못 발화 |

**Key insight:** Phase 1의 시간 위험은 외부 API가 아니라 **계산 정확성 검증**. EMA·Stoch·RSI 각각 golden test (알려진 입력 → 알려진 출력)가 없으면 색이 잘못 베이킹되어도 알 방법이 없다.

## Runtime State Inventory

Phase 1은 **greenfield** (첫 코드 phase, 기존 시스템 없음). 본 섹션은 생략.

## Common Pitfalls

### Pitfall A: pandas `expanding().std()` 첫 행 NaN을 색 함수가 안 받아냄
**What goes wrong:** `value - median` 자체는 첫 행에서 정상이지만 `2 * std`가 NaN이 되어 비교가 모두 False → `DEFAULT` 반환. 이건 D-02에 우연히 부합하지만 **명시적으로 NaN 분기를 두지 않으면 의도와 우연이 일치한 것뿐**.
**How to avoid:** `color_rules.decide_sigma_bucket`에 `math.isnan` + `std == 0` 명시 분기. 테스트로 NaN/0 입력 시 `SigmaBucket.DEFAULT` 반환 검증.

### Pitfall B: yfinance `history()`가 빈 DataFrame 반환 (부분 데이터 silent fail)
**What goes wrong:** 429 대신 빈 DataFrame이 와도 예외가 안 남 [VERIFIED: PITFALLS Pitfall 1].
**How to avoid:** `fetch_ohlcv` 끝에 `if df.empty: raise ValueError(...)`. Phase 1에서는 1개 티커이므로 fail-fast (Phase 2에서는 데이터 품질 시트로 우회).

### Pitfall C: EMA seed bias가 EMA192의 첫 ~200행을 왜곡
**What goes wrong:** `adjust=False`는 `EMA_0 = price_0`로 시작 → EMA192의 첫 192행은 거의 `price_0` 주변. expanding std도 그 구간에서 좁음 → 잘못된 색 발화 가능.
**How to avoid:** D-02 정책(NaN/0 std → 기본색)이 자연스럽게 흡수하지만, golden test로 첫 192행 색 분포가 거의 모두 `DEFAULT`임을 확인 권장. 또는 `min_periods=192`로 EMA 자체를 NaN으로 두는 것도 옵션 (현재 결정은 미적용 — 가독성 위해 EMA 값은 보여주되 색만 기본).

### Pitfall D: Excel 시트 폭 과대로 가독성 손상
**What goes wrong:** D-03 배치는 수십 컬럼. Phase 4의 frozen panes(1~5행)가 없으면 스크롤 시 헤더 손실.
**How to avoid:** Phase 1에서는 정의된 폭으로 진행. README에 "Phase 4에서 frozen panes 적용 예정" 명시. `worksheet.set_column(first_col, last_col, width)`로 합리적 폭 (예: 12) 설정.

### Pitfall E: tenacity `wait_exponential + wait_random` 조합 문법 미세 차이
**What goes wrong:** `wait_exponential(multiplier=1, min=2, max=30)` + `wait_random(0, 1)`는 `+` 연산자로 합성 가능 (tenacity는 `wait_combine`을 `__add__`로 노출). 첫 시도 이전 wait이 아닌 **재시도 사이** wait임을 잊고 `min=0`으로 두면 첫 재시도가 즉시 발생.
**How to avoid:** D-06 정책 그대로 사용. 테스트에서 `RetryError`를 catch하고 attempt 수 검증.

### Pitfall F: `today() - timedelta(days=4000)`가 영업일이 아닌 달력일
**What goes wrong:** 4000 달력일 ≈ 2750 거래일 ≈ 10.95년. 사용자가 "10년"으로 인식해도 일부 시장(KR)에서는 거래일 ~2500 정도. 부분 데이터 검증은 Phase 4지만 Phase 1에서도 row count 로깅 권장.
**How to avoid:** `fetch_ohlcv` 성공 후 `logger.info(f"{ticker} | OHLCV {len(df)} 거래일 수신 완료")`.

### Pitfall G: 시트의 3·4행이 expanding의 마지막 값이 아니라 전체 누적 스칼라
**What goes wrong:** REQUIREMENTS SHEET-03/04는 "전체 누적" — `df[col].median()`/`.std()` (NOT `expanding().last()`, 같은 값이긴 하지만 의도가 다름). 데이터 컬럼별로 컬럼 위치에 맞춰 써야 함.
**How to avoid:** writer가 컬럼 순서를 D-03에 맞춰 미리 결정하고, 3·4행 스칼라를 같은 컬럼 위치에 배치하는 헬퍼 함수 작성.

## Code Examples

(Pattern 1~9에서 이미 제시. 추가 EMA·RSI golden 입력은 Validation Architecture §"Golden Test 입력값" 참조.)

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| yfinance + `requests.Session()` | yfinance + `curl_cffi.requests.Session(impersonate="chrome")` | yfinance 0.2.60 (2025) | 일반 requests.Session 거부됨 [CITED: PITFALLS] |
| openpyxl + per-cell CF | XlsxWriter + 정적 색 베이킹 | 프로젝트 결정 | 파일 크기·열기 시간 감소 |
| pandas-ta | native `pandas.ewm` + 수동 Stoch/RSI | 프로젝트 결정 (pandas-ta 2026 archive) | NumPy 2 호환, 한 라이브러리 의존 제거 |
| `period="max"` | `start=today-4000d, end=today` | D-06 | 결정적 기간, 캐시 키 일관성 |

**Deprecated/outdated (Phase 1 적용 안함):**
- `curl_cffi 0.14` — CVE-2743
- Python 3.12 — 3.13 wheel 풀 지원됨
- pandas-ta (main fork) — 2026 archive 예정

## Validation Architecture

### Test Framework

| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-mock |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (Wave 0에서 생성) |
| Quick run command | `uv run pytest -x -q` |
| Full suite command | `uv run pytest` |
| Coverage 측정 | Phase 1 미적용 (Phase 4에서 검토) |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INPUT-01 | `tickers.txt` 한 줄당 파싱 | unit | `pytest tests/test_input.py::test_read_single_ticker -x` | ❌ Wave 0 |
| INPUT-02 | `.KS`/`.KQ` 통과 (suffix-agnostic) | unit | `pytest tests/test_input.py::test_read_kr_suffix -x` | ❌ Wave 0 |
| INPUT-03 | 빈/없는 파일 → 한국어 에러 + exit≠0 | unit | `pytest tests/test_input.py::test_empty_file_exits_nonzero -x` | ❌ Wave 0 |
| INPUT-05 | `.env` 비어있으면 fail-fast | unit | `pytest tests/test_config.py::test_missing_env_fails -x` | ❌ Wave 0 |
| MKTD-01 | start/end 인자 today±4000d | unit (mock yf.Ticker) | `pytest tests/test_market.py::test_fetch_ohlcv_date_window -x` | ❌ Wave 0 |
| MKTD-02 | session=curl_cffi 전달 | unit (mock 검증) | `pytest tests/test_market.py::test_uses_curl_cffi_session -x` | ❌ Wave 0 |
| MKTD-03 | YFRateLimitError 시 재시도 | unit (mock side_effect) | `pytest tests/test_market.py::test_retries_on_rate_limit -x` | ❌ Wave 0 |
| COMP-01 | EMA(span=N, adjust=False) | unit (골든 입력) | `pytest tests/test_ema.py::test_ema_matches_tradingview_formula -x` | ❌ Wave 0 |
| COMP-02 | 차이 = price - EMA | unit | `pytest tests/test_ema.py::test_diff_columns -x` | ❌ Wave 0 |
| COMP-03 | EMA 일변동 = EMA.diff() | unit | `pytest tests/test_ema.py::test_daily_change -x` | ❌ Wave 0 |
| COMP-04 | expanding median/std | unit | `pytest tests/test_stats.py::test_expanding_median_std -x` | ❌ Wave 0 |
| COMP-05 | 누적 스칼라 | unit | `pytest tests/test_stats.py::test_cumulative_scalars -x` | ❌ Wave 0 |
| COMP-06 | 거래량 expanding | unit | (COMP-04 같은 테스트에 Volume 포함) | ❌ Wave 0 |
| TECH-01 | Stoch Slow(14,3,3) | unit (골든 입력) | `pytest tests/test_indicators.py::test_stoch_slow_known_input -x` | ❌ Wave 0 |
| TECH-02 | RSI(14 Wilder) | unit (골든 입력) | `pytest tests/test_indicators.py::test_rsi_wilder_known_input -x` | ❌ Wave 0 |
| TECH-04/05 | Stoch/RSI 임계값 색 | unit | `pytest tests/test_color_rules.py::test_tech_buckets -x` | ❌ Wave 0 |
| COLOR-01~07 | σ-색 결정 | unit | `pytest tests/test_color_rules.py::test_sigma_buckets -x` | ❌ Wave 0 |
| SHEET-01~08, TECH-03/06, OUT-01~03, EXEC-01/02 | end-to-end .xlsx 생성 | integration (smoke) | `pytest tests/test_smoke_end_to_end.py::test_single_ticker_workbook -x` (mock yfinance + 실제 XlsxWriter 출력 → openpyxl로 읽어 검증) | ❌ Wave 0 |
| Success Criteria #2/#3 (3개 행 색 일치) | golden file | manual + automated | `pytest tests/test_smoke_end_to_end.py::test_color_at_three_rows -x` (가장 최근/중간/오래된 3개 행에 대해 σ 규칙 직접 계산 → 셀 Format 비교) | ❌ Wave 0 |

### Sampling Rate

- **Per task commit:** `uv run pytest -x -q tests/test_<changed_module>.py` (< 5초)
- **Per wave merge:** `uv run pytest -x -q` 전체 (< 30초 예상)
- **Phase gate:** 전체 그린 + smoke test에서 생성된 `output/portfolio_YYYYMMDD.xlsx`를 실제 Excel로 열어 Success Criteria #1~6 수기 확인

### Golden Test 입력값 (planner가 task로 분해 시 사용)

**EMA(span=3, adjust=False, 입력 = [1, 2, 3, 4, 5]):**
- α = 2/(3+1) = 0.5
- EMA = [1.0, 1.5, 2.25, 3.125, 4.0625]

**Wilder RSI(period=14, 입력 = 표준 책 예제):** 알려진 14일 close 시퀀스에 대해 RSI 첫 유효값이 ~70.53인 표준 예제(예: J. Welles Wilder "New Concepts in Technical Trading Systems" 1978 예제) 또는 TradingView 화면 캡처로 검증. Wave 0에서 검증 값 1개를 fixture로 고정.

**Stoch Slow(14,3,3) sanity check:**
- 14일 동안 close가 항상 high에 가까우면 Slow %K → 100 근처
- 14일 동안 close가 항상 low에 가까우면 Slow %K → 0 근처
- 일정한 가격 시퀀스(예: 모든 close=100, high=110, low=90) → %K = 50

### Wave 0 Gaps

- [ ] `tests/conftest.py` — 공유 fixture (mock yfinance 응답 DataFrame, 임시 `tickers.txt`, 임시 `.env`)
- [ ] `tests/test_input.py` — INPUT 4건
- [ ] `tests/test_config.py` — INPUT-05
- [ ] `tests/test_market.py` — MKTD 3건 (실제 네트워크 호출 없음, mock yf.Ticker)
- [ ] `tests/test_ema.py` — COMP-01~03 + golden 입력
- [ ] `tests/test_stats.py` — COMP-04~06
- [ ] `tests/test_indicators.py` — TECH-01/02 + golden 입력
- [ ] `tests/test_color_rules.py` — COLOR-01~07 + TECH-04/05 버킷
- [ ] `tests/test_smoke_end_to_end.py` — smoke (mock yfinance → 실제 XlsxWriter 출력 → openpyxl로 읽어 시트 구조 + 셀 색 검증)
- [ ] `pyproject.toml` `[tool.pytest.ini_options]` 블록 추가: `testpaths = ["tests"]`, `pythonpath = ["src"]`
- [ ] dev 의존성 설치: `uv add --dev pytest pytest-mock openpyxl` (smoke test 검증용 openpyxl)

### 수기 검증 포인트 (Walking Skeleton)

1. **파일 생성:** `uv run python main.py` → `output/portfolio_20260520.xlsx` 존재.
2. **시트 구조:** Excel에서 `AAPL` 시트 A1=`AAPL`, 3행·4행 숫자, 5행 한국어 헤더, 6행~ 데이터.
3. **색 정합성:** 3개 행(최신/중간/오래된) 수기 σ 계산 → 셀 색 일치.
4. **동적 CF 부재:** Excel "조건부 서식 → 규칙 관리"에 항목 0개.
5. **Stoch/RSI 임계값 색:** Stoch ≤20 셀 초록, ≥80 셀 빨강 (적어도 한 셀씩 존재 확인).
6. **에러 경로:** `tickers.txt`를 비우고 실행 → 한국어 에러 + 비0 exit code.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | EXEC-01, 모든 코드 | 확인 필요 | — | uv가 자동 설치 가능 (`uv python install 3.13`) |
| uv | EXEC-02 | 확인 필요 | — | 없음 (사전 설치 필수) |
| 인터넷 연결 (Yahoo Finance) | MKTD-01 | runtime 의존 | — | smoke test에서는 mock |
| Windows console UTF-8 | D-05 한국어 출력 | reconfigure 시도 | — | `chcp 65001` 안내 |
| `.env` 파일 (사용자 작성) | INPUT-05 | 사용자 책임 | — | 비어있으면 fail-fast |
| `tickers.txt` (사용자 작성) | INPUT-01 | 사용자 책임 | — | 비어있으면 INPUT-03 에러 |

**Missing dependencies with no fallback:**
- 없음 (Python·uv는 사용자가 설치하는 것이 정상; STATE.md Todos에 이미 안내)

**Missing dependencies with fallback:**
- 인터넷 — 테스트는 모두 mock으로 동작

## Assumptions Log

> Phase 1 RESEARCH의 모든 핵심 주장은 CONTEXT.md(D-01~D-06)·REQUIREMENTS.md·STACK.md·PITFALLS.md에서 [CITED]/[VERIFIED]됨. 아래 [ASSUMED] 항목은 planner/사용자가 확인 가능하도록 명시.

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | XlsxWriter `constant_memory=False`가 Phase 1 메모리(시트 1개 × ~수십 컬럼 × ~2700행)에서 충분 | Pattern 8 | 메모리 부족 시 `True`로 전환 — 영향 미미 (행 순차 쓰기는 이미 그렇게 하고 있음) |
| A2 | uv의 권장 build backend는 hatchling | Pattern 1 | 사용자가 setuptools 선호 시 변경 — 두 줄 변경으로 무리 없음 |
| A3 | Windows 11 (사용자 명시 환경) console에서 `sys.stdout.reconfigure(encoding='utf-8')`가 신뢰성 있게 동작 | Pattern 9 | 깨질 시 `PYTHONIOENCODING=utf-8` 안내 또는 `chcp 65001` 보조 |
| A4 | `pandas.ewm(alpha=1/14, adjust=False)`가 Wilder smoothing과 정확히 동등 | Pattern 6 | 수학적으로 동등하지만, 첫 행 시드 처리 미세 차이 가능 — golden test로 확인 필수 |
| A5 | tenacity `wait_exponential + wait_random`이 `+` 연산자로 합성 가능 | Pitfall E | tenacity 9.x 공식 패턴 — 변경 없을 것으로 예상하나 docs 재확인 권장 |

## Open Questions

1. **`output/` 폴더 git 추적 여부**
   - 알려진 것: Phase 1은 `output/portfolio_YYYYMMDD.xlsx` 생성
   - 불명확: `.gitignore`에 `output/` 추가 여부
   - 권장: `.gitignore`에 `output/`, `.env`, `*.xlsx` 추가 (보안: PITFALLS.md Security Mistake "포트폴리오 파일 commit 금지")

2. **같은 날 재실행 시 파일 처리**
   - 알려진 것: OUT-03은 "매 실행마다 새 파일" — 다른 날에는 명백
   - 불명확: 같은 날 두 번 실행하면 같은 이름 파일을 overwrite할지, 시간 suffix를 붙일지
   - 권장: Phase 1은 overwrite (단순화). Phase 2에서 캐시 도입 시 재고.

3. **Stochastic %D를 별도 행으로 두는가 같은 셀에 두는가**
   - 알려진 것: D-03이 "Stoch %K → Stoch %D → RSI" 세 컬럼 명시
   - 불명확: 셋 모두 6행부터 데이터 (날짜 내림차순) — 시트 구조 무관
   - 권장: 컬럼 3개로 처리 (D-03 그대로)

## Project Constraints (from CLAUDE.md)

- **Tech stack 핀:** Python 3.13 + uv, yfinance ≥0.2.66, curl_cffi ≥0.15,<0.16, XlsxWriter 3.2.x, pandas 2.2.x, numpy 2.x, tenacity 9.x, python-dotenv 1.0+ — 본 RESEARCH는 모두 준수.
- **언어:** UI/로그 한국어 우선 → D-05.
- **출력 형식:** 단일 `.xlsx`, 매 실행 새 파일 → OUT-01~03.
- **데이터 소스 우선순위:** Phase 1은 시세(yfinance)만; 재무는 Phase 3.
- **GSD workflow:** 본 RESEARCH는 `/gsd:plan-phase`의 일부로 작성됨 — 직접 코드 편집 금지.
- **금지 사항 (STACK.md "What NOT to Use"):** pandas-ta, TA-Lib, openpyxl 1차 writer, requests.Session(plain), curl_cffi 0.14, sec-api.io 유료, threaded yfinance pulls, Python 3.14/3.12, 하드코딩 API 키 — Phase 1 코드에서 모두 회피.

## Security Domain

> `.planning/config.json`에 `security_enforcement` 설정이 없으므로 기본값(enabled)으로 간주.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 1은 외부 인증 API 호출 없음 (.env 로드만, 실제 호출은 Phase 3) |
| V3 Session Management | no | 단일 사용자 로컬 도구 |
| V4 Access Control | no | 동일 |
| V5 Input Validation | yes | `tickers.txt` 파싱 — 형식 검증 (Phase 1은 단일 미국 티커지만 빈/whitespace/주석 필터 필요) |
| V6 Cryptography | no | Phase 1은 암호화 없음 |
| V7 Error Handling & Logging | yes | 한국어 에러 메시지, 비0 종료 코드, `.env` 미설정 시 명확한 메시지 |
| V8 Data Protection | yes | `.env`·`output/*.xlsx` git 비추적, secrets는 환경변수 |
| V14 Configuration | yes | python-dotenv로 환경변수 로드, hardcoded key 금지 |

### Known Threat Patterns for Python local-tool

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| `.env`에 secrets 평문 저장 → git 누설 | Information Disclosure | `.env` in `.gitignore`, `.env.example`만 commit |
| `output/portfolio_*.xlsx` 누설 → 개인 보유 종목 노출 | Information Disclosure | `output/` in `.gitignore` |
| User-Agent에 개인 이메일 commit | Information Disclosure | yunj95@keti.re.kr는 연구 이메일로 사용자가 인지 (PITFALLS Security Mistake 참조). Phase 1은 EDGAR 호출 없으므로 UA 사용 없음 |
| 잘못된 input → exception traceback 노출 | Information Disclosure | `tickers.txt` 파싱 에러는 한국어 안내 메시지, raw traceback 비노출 |
| yfinance 응답 신뢰 (예: 잘못된 DataFrame 스키마) | Tampering | `df.empty` 체크, 최소 row count assertion (Phase 1은 raise, Phase 2에서 품질 시트로 우회) |

## Sources

### Primary (HIGH confidence)

- `.planning/research/STACK.md` — Phase 0 리서치, 라이브러리 핀·버전 호환성
- `.planning/research/PITFALLS.md` — 11개 known pitfall (Pitfall 1 yfinance rate-limit / Pitfall 5 EMA seed / Pitfall 6 σ look-ahead 등)
- `.planning/REQUIREMENTS.md` — 39개 Phase 1 요구사항 ID
- `.planning/ROADMAP.md` — Phase 1 Success Criteria 6개
- CONTEXT.md (D-01~D-06) — 사용자 결정 잠금
- CLAUDE.md — Tech Stack 핀 + Critical Decisions

### Secondary (MEDIUM confidence)

- pandas 공식 docs (`DataFrame.ewm`, `DataFrame.expanding`) — 본 RESEARCH의 `adjust=False` 정당화는 STACK.md에서 CITED됨
- XlsxWriter 공식 docs (`Format`, `add_format`) — STACK.md에서 CITED됨
- tenacity docs — STACK.md에서 CITED됨
- yfinance CHANGELOG / Issue #2496 (session API 변경) — STACK.md/PITFALLS.md에서 CITED됨

### Tertiary (LOW confidence)

- 없음 — 본 RESEARCH는 프로젝트 레벨에서 이미 검증된 사실 위에 구축됨

## Metadata

**Confidence breakdown:**

- Standard stack: HIGH — STACK.md 핀 그대로
- Architecture: HIGH — D-01에서 잠금
- Pitfalls: HIGH — PITFALLS.md (Phase 0)에서 검증된 11개를 Phase 1 범위로 좁힘
- 색 정책: HIGH — D-04에서 구체 hex 잠금
- 계산 정확성: MEDIUM — native Stoch/RSI는 golden test 통과 후 HIGH 승격
- Walking Skeleton 검증: HIGH — 수기 검증 6포인트 명시

**Research date:** 2026-05-20
**Valid until:** 2026-06-19 (30일 — 핀된 라이브러리, 안정적 도메인)

---

## RESEARCH COMPLETE

**Phase:** 1 - 기반 + 단일 티커 수직 슬라이스
**Confidence:** HIGH

### Key Findings

- D-01~D-06이 모든 거시 결정을 잠가뒀으므로 RESEARCH는 처방적·구체적 — planner는 task 분해 시 Pattern 1~9의 코드 스니펫과 함수 시그니처를 그대로 task action에 매핑 가능.
- 핵심 위험 3개: (1) Stoch/RSI native 구현 정확성 — golden test 필수, (2) expanding std==0/NaN 분기 — color_rules에서 명시적 처리, (3) XlsxWriter Format 캐싱 — 7개 Format dict.
- yfinance + curl_cffi 통합 패턴은 `Ticker(t, session=...)` 형태로 고정 (≥0.2.60 변경 반영).
- pandas-ta 미사용 결정 → Stoch Slow(14,3,3)와 Wilder RSI(14) 공식·골든 입력 명시.
- Wave 0에서 pytest 인프라 + 9개 테스트 파일 + 1개 conftest.py 생성 필요.
- Phase 1은 Walking Skeleton: 6개 수기 검증 포인트 + 자동 smoke test 1개로 Core Value 증명.

### File Created

`C:\Users\kimyunjae\Documents\Claude 앱 개발\example\.planning\phases\01-foundation-single-ticker\01-RESEARCH.md`

### Confidence Assessment

| Area | Level | Reason |
|------|-------|--------|
| Standard Stack | HIGH | STACK.md 핀, 검증된 버전 호환성 |
| Architecture | HIGH | D-01에서 잠금, Pattern 1~9 모두 검증된 라이브러리 패턴 |
| Pitfalls | HIGH | PITFALLS.md(Phase 0)에서 11개 검증, Phase 1 7개로 좁힘 (A~G) |
| 계산 정확성 | MEDIUM (→ HIGH after Wave 0 golden test) | native Stoch/RSI는 단위 테스트로 입증 필요 |
| 색 정책 | HIGH | D-04 구체 hex 잠금 |
| Validation 전략 | HIGH | pytest 인프라 + 수기 검증 6포인트 |

### Open Questions

1. `.gitignore`에 `output/`, `.env`, `*.xlsx` 추가 (보안 권장, planner가 task에 포함 결정)
2. 같은 날 재실행 시 overwrite vs suffix (Phase 1은 overwrite 권장)
3. Wave 0의 golden RSI 입력값(Wilder 책 예제 등) 정확한 출처 1건 고정 필요

### Ready for Planning

Research complete. Planner는 다음 wave 구조를 권장 진행할 수 있다:
- **Wave 0:** 부트스트랩 (pyproject.toml, src 레이아웃, test infra, .env.example, tickers.txt 예시)
- **Wave 1:** io 레이어 (input.py, market.py) + 테스트
- **Wave 2:** compute 레이어 (ema, stats, indicators, color_rules) + golden tests
- **Wave 3:** output 레이어 (writer, sheet_per_ticker) + smoke test
- **Wave 4:** main.py 통합 + 수기 검증 6포인트

