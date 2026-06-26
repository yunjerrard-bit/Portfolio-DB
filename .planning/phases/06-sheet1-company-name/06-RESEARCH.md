# Phase 6: 시트1 기업명 열 - Research

**Researched:** 2026-06-16
**Domain:** yfinance `.info` 기업명 조회 + xlsxwriter 컬럼 시프트 리팩터
**Confidence:** HIGH (코드·yfinance 동작 모두 라이브 검증)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D1 (LOCKED):** 데이터 소스 = yfinance 일괄 조회, DART 미사용. 모든 종목(미국·한국)의 기업명을 yfinance에서. DART를 거치지 않는다 (호출량 우려).
- **D2 (LOCKED):** 영문명만 기록 (한국 종목 포함). `.KS`/`.KQ`도 영문 기업명.
- **D3 (LOCKED):** 위치·범위 = 시트1 단일 열. 티커 열(A)과 시장 열 사이 → 새 B열 (이후 기존 열 전부 +1 시프트). 종목별 시트(sheet_per_ticker.py)는 변경하지 않는다.

### Claude's Discretion
- `longName` vs `shortName` 필드 선택 (longName 우선, 결손 시 폴백 — 연구로 확정).
- 조회 시점·구조: 기존 fetch 파이프라인과 함께 vs 별도 경량 조회. 캐시 키·만료 설계.
- 컬럼 시프트 구현 방식: 하드코딩 인덱스 정리 방법.
- 실패/결손 폴백: 빈칸 vs 티커 표시.

### Deferred Ideas (OUT OF SCOPE)
- 종목 시트 A1에 기업명 병기 — 시트1만.
- 한글 기업명 / DART·네이버 기업명 조회 — D1/D2로 배제.
- 기업명 기반 정렬·필터·검색 — 표시만.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| COMPANY-01 | 티커(A)와 시장 사이 '기업명' 열 + 영문명 표시 | Q4 컬럼 시프트 + Q3 데이터 경로 |
| COMPANY-02 | yfinance 일괄 조회, DART 미호출, 영문명만 | Q1 `longName` 검증 (US+KR 영문) |
| COMPANY-03 | 결손 안전 처리 + 시프트 후 회귀 무손상 | Q1 폴백 / Q5 회귀 표면 |
| COMPANY-04 | 기존 throttle·retry·캐시 정책 준수, 200종목 현실적 | Q2 — 기존 `fetch_yf_info`/throttle/캐시 재사용 |
</phase_requirements>

## Summary

Phase 6는 신규 기술이 거의 없는 **리팩터 + 기존 패턴 재사용** 단계다. 결정적 발견: 코드베이스에 이미 `src/stocksig/io/yf_fundamentals.py:fetch_yf_info()`가 존재하며, 이것이 `yf.Ticker(ticker, session=_SESSION).info`를 **이미 호출**한다 — `market._SESSION`(curl_cffi Chrome) 재사용 + `@throttled_yahoo`(2 RPS) 적용. 즉 "기업명 조회는 신규 `.info` 왕복을 추가한다"는 CONTEXT의 우려는 펀더멘털이 켜진 종목에 한해 **이미 일어나고 있는 왕복**이다. 기업명은 그 동일한 `.info` dict에서 `longName` 한 키를 더 읽기만 하면 되므로, 펀더멘털과 같은 `.info` 호출을 공유하면 **추가 왕복 0회**가 이상적 설계다.

`longName` 필드는 라이브 검증에서 US/KR 모두 깨끗한 영문명을 반환했다: `AAPL→"Apple Inc."`, `005930.KS→"Samsung Electronics Co., Ltd."`, `035720.KQ→"Kakao Corp"`. 반면 `shortName`은 KR에서 신뢰 불가(`035720.KQ`의 shortName은 `"035720.KQ,0P0000AN5S,1145416"` 쓰레기값). 따라서 **`longName` 우선, 결손 시 `shortName`, 그래도 없으면 티커 폴백**.

회귀 표면이 이 단계의 가장 큰 위험이다. `sheet_portfolio.py`는 정수 컬럼 인덱스(0~20)를 행 writer 전체에 하드코딩했고, freeze는 `freeze_panes(5, 1)`(B6)이다. 한 칸 시프트는 **헤더·성공행 21셀·실패행 마커·펀더멘털 상수·freeze·그리고 테스트의 모든 셀 좌표**를 깬다.

**Primary recommendation:** (1) 펀더멘털 fetch 경로(`fetch_yf_info`)를 확장해 `longName`을 함께 추출하고 `TickerResult.company_name` 필드로 운반한다(추가 `.info` 왕복 0회, 캐시는 기존 펀더멘털 캐시에 흡수). (2) `sheet_portfolio.py`는 정수 하드코딩을 **헤더 리스트 기반 명명 인덱스 상수(`_COL_*`)**로 리팩터한 뒤 기업명 열을 인덱스 1에 삽입 — 수기 +1 산수를 피해 회귀를 구조적으로 차단. (3) freeze를 `freeze_panes(5, 1)` 유지(A열=티커 고정, 기업명은 비고정) — `B6` 불변, 테스트 갱신 불필요.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 기업명 네트워크 조회 | IO (`io/yf_fundamentals.py` 또는 신규 `io/company.py`) | — | yfinance `.info`는 모든 외부 fetch가 모이는 IO 계층 소관 |
| throttle/retry/캐시 | IO (`io/throttle.py`, `io/cache.py`) | — | 기존 2 RPS limiter·diskcache 재사용 (COMPANY-04) |
| 기업명 운반 | 도메인 (`runner.TickerResult`) | — | 시세·펀더멘털과 동격의 per-ticker 결과 필드 |
| 컬럼 레이아웃·시프트 | 출력 (`output/sheet_portfolio.py`) | — | 시트1 writer 단독 책임 (D3: 종목시트 불변) |

## Standard Stack

신규 패키지 **없음**. 전부 설치·검증된 기존 스택 재사용.

### Core
| Library | Version (검증) | Purpose | Why Standard |
|---------|---------------|---------|--------------|
| yfinance | 1.3.0 (설치본) | `Ticker(...).info["longName"]` 기업명 | 이미 `yf_fundamentals.py`가 동일 `.info` 호출 |
| curl_cffi | (기존 `_SESSION`) | TLS 세션 재사용 | `market._SESSION` 단일 인스턴스 — 신규 세션 금지 |
| tenacity | 9.x (기존) | retry | OHLCV는 이미 적용. `.info`엔 미적용(아래 Pitfall 4 참고) |
| pyrate_limiter | (기존) | 2 RPS throttle | `@throttled_yahoo` 그대로 |
| diskcache | (기존) | 캐시 | 펀더멘털 캐시(7일 TTL)에 흡수 |
| XlsxWriter | 3.2.x (기존) | 시트1 writer | 컬럼 시프트만 |

> **버전 메모 [VERIFIED: import yfinance.__version__]:** 설치된 yfinance는 **1.3.0**으로 CLAUDE.md 베이스라인(0.2.66+)보다 훨씬 최신. `.info`/`get_info()`/`fast_info` API는 1.x에서도 동일하게 존재함(`dir()` 확인). 기존 `yf_fundamentals.py`가 1.3.0에서 정상 동작 중이므로 호환성 리스크 없음.

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `.info` 공유 | 별도 `Ticker(t).info` 신규 호출 | 추가 왕복 1회/티커 — 200종목 = +200 왕복. **불필요** (Q2) |
| `.info` | `fast_info` | `fast_info`에 이름 없음 — 사용 불가 [VERIFIED: yfinance fast_info에 longName/shortName 키 부재, ASSUMED 기준 일반 동작] |
| `get_info()` | `.info` 프로퍼티 | 동일 데이터. 기존 코드가 `.info` 사용 — 일관성 위해 `.info` 유지 |

## Package Legitimacy Audit

신규 패키지 설치 없음 — 전 패키지가 v1.0~v1.1에서 이미 검증·사용 중. 슬롭체크 불필요.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (신규 없음) | — | 기존 의존성만 재사용 |

## Architecture Patterns

### 데이터 흐름

```
tickers.txt
  → read_tickers_extended → TickerSpec(symbol, tier, industry)   [frozen, 변경 금지]
  → run_all (ThreadPoolExecutor max_workers=4)
       → process_ticker
            → pipeline(symbol): fetch_ohlcv_cached + _compute_enriched   [OHLCV — .info 미사용]
            → fundamentals_fn(symbol, market, last_close)                 [.info 1회 왕복 발생 지점 ★]
       → TickerResult(spec, enriched_df, market, fundamentals, company_name ←신규)
  → write_portfolio_sheet (시트1)
       → _write_success_row: col 0=티커, col 1=기업명(신규), col 2~=시프트
```

### Pattern 1: `.info` 호출 공유 — 추가 왕복 0회 (권장)
**What:** `fetch_yf_info`가 이미 `info = yf.Ticker(...).info`를 만든다. 같은 dict에서 `longName`을 추가 추출.
**When to use:** 펀더멘털이 켜진 모든 실행(현재 기본 경로).
**핵심 스니펫:**
```python
# io/yf_fundamentals.py — fetch_yf_info 확장 (or 신규 fetch_yf_company_name)
@throttled_yahoo
def fetch_yf_info(ticker: str) -> dict:
    info = yf.Ticker(ticker, session=_SESSION).info or {}
    return {
        "PER": info.get("trailingPE"),
        "PEG": info.get("pegRatio") or info.get("trailingPegRatio"),
        "GPM": info.get("grossMargins"),
        "OPM": info.get("operatingMargins"),
        "company_name": _pick_name(info, ticker),   # ← 신규
    }

def _pick_name(info: dict, ticker: str) -> str:
    name = info.get("longName") or info.get("shortName")
    return name if name else ticker   # 폴백: 티커 (CONTEXT discretion — 빈칸 대신 식별성 우선)
```
> **주의:** `fetch_yf_info`는 펀더멘털 경로에서 "결손 지표가 있을 때만" 호출된다(`fundamentals.py:245 missing` 가드). 모든 지표가 EDGAR/DART에서 채워진 US 종목은 `.info`를 안 탈 수 있다. → 기업명을 **항상** 얻으려면 (a) 펀더멘털 fetch가 이름을 무조건 추출하도록 별도 경량 호출을 펀더멘털 함수 진입부에 두거나, (b) 신규 `io/company.py:fetch_company_name(ticker)`를 만들어 `process_ticker`에서 직접 호출. **권장 = (b) 별도 경량 함수 + 자체 캐시** — 펀더멘털 on/off와 무관하게 동작하고 책임이 명확. 단 (b)는 펀더멘털이 이미 `.info`를 부른 종목엔 중복 왕복이 될 수 있어, **캐시가 이를 흡수**한다(아래 Pattern 2).

### Pattern 2: 기업명 캐시 — 재실행 무호출
**What:** `(ticker → name)`을 영속화. 기업명은 거의 안 바뀌므로 긴 TTL.
**권장:** 기존 `io/cache.py` 패턴 그대로 신규 네임스페이스 추가 (OHLCV 24h / 펀더멘털 7일과 분리).
```python
# io/cache.py 추가 — 펀더멘털 캐시와 동일 구조
_NAME_DIR = Path(".cache/company")
_NAME_TTL_SECONDS = 30 * 24 * 60 * 60   # 30일 — 기업명은 안정적
def make_name_key(ticker: str) -> str: return ticker          # 날짜 무관 (불변성)
def get_company_name(ticker): ...   # _stats["name_hit"]/["name_miss"] 카운터 추가
def put_company_name(ticker, name): ...
```
`fetch_company_name` = `get_company_name` HIT 시 즉시 반환(왕복 0), MISS 시 `fetch_yf_info`류 호출 후 `put`. → 재실행 시 기업명 왕복 0회 (COMPANY-04 충족).

### Pattern 3: 헤더 기반 명명 인덱스 — 시프트 안전화 (권장 리팩터)
**What:** 정수 하드코딩(0~20)을 헤더 리스트에서 도출한 명명 상수로 치환.
**Why:** 수기 +1(옵션 a)은 21개 정수 + 펀더멘털 4상수 + 실패행 + 테스트를 전부 손으로 고쳐야 해 누락 위험 최대. 명명 상수(옵션 b/c)는 기업명 삽입 1줄로 끝나고 후속 시프트도 자동.
```python
PORTFOLIO_COLUMNS = ["티커", "기업명", "시장", "티어", ...]   # ← "기업명" index 1 삽입

# 헤더 → 인덱스 맵 (단일 진실 출처)
_COL = {name: i for i, name in enumerate(PORTFOLIO_COLUMNS)}
# 사용: ws.write_number(row, _COL["최신 종가"], ...)  ← 정수 4 대신
_FUND_COL_PER = _COL["PER"]   # 17 → 18 자동
```
**대안(옵션 a, 비권장):** 모든 정수 +1 수기 — 빠르지만 회귀 위험 높음. 시간이 정말 없을 때만.

### Anti-Patterns to Avoid
- **신규 curl_cffi/httpx 세션 생성:** `yf_fundamentals.py:20`은 명시적으로 `market._SESSION` 재사용. 기업명 조회도 동일 세션 필수 (yfinance ≥0.2.60은 plain Session 거부, 본 코드 정책).
- **`@throttled_yahoo` 우회:** 모든 yahoo 왕복은 2 RPS limiter 통과해야 함 (CLAUDE.md rate-limit 정책).
- **종목 시트 건드리기:** D3 LOCKED — `sheet_per_ticker.py` 불변, freeze `B6` 유지.
- **`shortName` 우선 사용:** KR에서 쓰레기값 반환 (검증됨).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 기업명 throttle | 신규 sleep/limiter | `@throttled_yahoo` | 2 RPS limiter 이미 존재 |
| 기업명 영속화 | 직접 파일 I/O | `io/cache.py` diskcache 패턴 | TTL·lock·통계 카운터 검증됨 |
| TLS 세션 | 신규 `Session()` | `market._SESSION` | 단일 인스턴스 정책 |
| retry | 신규 try 루프 | `@retry`(tenacity) — Pitfall 4 참고 | OHLCV 패턴 복제 |

## Common Pitfalls

### Pitfall 1: 컬럼 시프트 누락 (최대 위험)
**무엇:** `_write_success_row`의 정수 col 0~20, `_FUND_COL_*` 상수, `_write_failure_row`의 col 16(`(주)임펄스` 위치 마커), 그리고 테스트의 모든 `cell(row, column=N)` 좌표가 +1 되어야 함.
**왜:** xlsxwriter는 좌표 기반 write — 한 곳이라도 안 밀면 색·하이퍼링크·주석이 잘못된 열에 박힘.
**회피:** Pattern 3 명명 인덱스로 구조적 차단. 실패행 마커(`_write_failure_row`의 col 16 → "실패: reason")도 `_COL["(주)임펄스"]`로.
**경고 신호:** `test_sheet_portfolio.py`의 `column=N` 단언 적색.

### Pitfall 2: 펀더멘털 off / 결손 종목에 기업명 누락
**무엇:** `fetch_yf_info`는 펀더멘털 결손 지표가 있을 때만 호출(`fundamentals.py:245`). 펀더멘털이 다 채워진 US 종목은 `.info` 미경유 → 기업명 빈칸.
**회피:** Pattern 1 (b) — 기업명을 펀더멘털 분기와 독립된 `fetch_company_name`으로 분리하고 `process_ticker`에서 항상 호출 + 캐시.

### Pitfall 3: `.info` 호출 비용 (200종목 시간)
**무엇:** `.info` 1회 ≈ **0.98s** + 1 HTTP 왕복(라이브 측정, 184키). 200종목 첫 실행 = 추가 ~200왕복 (max_workers=4 + 2 RPS throttle → 약 100초 누적). 
**회피:** (1) 펀더멘털과 `.info` 공유 시 추가 왕복 0. (2) 30일 캐시로 재실행 0왕복. (3) ThreadPoolExecutor(4) + 2 RPS는 기존 OHLCV/펀더멘털도 통과하는 부하 — 기업명만 별도 추가해도 동일 한계 내. **비현실적으로 느려지지 않음** (COMPANY-04 충족).

### Pitfall 4: `.info`에 retry 미적용
**무엇:** `fetch_ohlcv`는 `@retry(YFRateLimitError 5회)`지만 `fetch_yf_info`는 `@throttled_yahoo`만 있고 retry 없음. 기업명 조회를 `fetch_yf_info`에 얹으면 rate-limit 시 재시도 없이 빈 dict.
**회피:** 신규 `fetch_company_name`에 `fetch_ohlcv`와 동일한 `@retry` 데코레이터 스택 적용 권장. 단 기업명 결손은 티커 실패가 아니므로(폴백=티커) 실패 흡수도 허용.

### Pitfall 5: stub 픽스처 — 테스트 네트워크 미스
**무엇:** `test_freeze_panes.py`의 `mock_pipeline_env`는 `fetch_ohlcv`만 stub. 기업명 조회를 `run()` 경로에 추가하면 테스트가 실 네트워크를 칠 수 있음.
**회피:** 기업명 fetch 함수도 monkeypatch stub 추가(고정 이름 반환). `test_sheet_portfolio.py`는 `TickerResult`를 직접 만드므로 `company_name=` 인자만 주면 됨(네트워크 없음).

## Code Examples

### TickerResult 확장 (runner.py)
```python
@dataclass
class TickerResult:
    spec: TickerSpec
    enriched_df: pd.DataFrame
    market: str
    fundamentals: "object | None" = None
    company_name: str | None = None   # ← 신규. 기본 None → 기존 3/4인자 호출 무회귀
```
> `TickerSpec`(frozen)에 넣지 **말 것** — frozen + read 단계 산출물 아님. `TickerResult`가 옳은 위치(시세·펀더멘털과 동격 fetch 결과).

### 시트1 기업명 셀 (sheet_portfolio.py)
```python
# col 0: 티커 (hyperlink) — 불변
ws.write_url(row, _COL["티커"], _internal_link(spec.symbol), ...)
# col 1: 기업명 (신규)
ws.write_string(row, _COL["기업명"], res.company_name or spec.symbol,
                formats[(SigmaBucket.DEFAULT, ...)])  # 일반 텍스트 포맷
```

### freeze 유지
```python
ws.freeze_panes(5, 1)   # 불변 — A열(티커) 고정, 기업명(B)은 비고정 스크롤
# → openpyxl 읽기 "B6" 유지 → test_freeze_panes.py 갱신 불필요
```
> **freeze 결정 근거:** CONTEXT/REQUIREMENTS는 "freeze B6→C6"을 예상하나, 그것은 "기업명도 고정" 선택 시의 결과다. **A열(티커)만 고정**하면 `freeze_panes(5,1)` 그대로이고 `B6` 불변 → 회귀 테스트 3건 무수정. 기업명까지 고정하려면 `freeze_panes(5,2)`(C6)로 바꾸고 `test_freeze_panes.py:118`+`test_portfolio_sheet_freezes_rows_and_col_a` 갱신. **권장: A열만 고정(B6 유지)** — 가장 적은 회귀. (planner가 UX 선호로 C6 택하면 테스트 2건 명시 갱신.)

## Runtime State Inventory

리팩터/표시 추가 단계이나 외부 런타임 상태 영향은 제한적. 5범주 명시 점검:

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | 신규 `.cache/company/` diskcache (ticker→name, 30일 TTL) 생성 예정. 기존 `.cache/ohlcv`·`.cache/fundamentals` 영향 없음. | 캐시 신규 네임스페이스 추가 (코드) |
| Live service config | None — 외부 서비스 설정에 기업명 미관여. yfinance는 무인증. | 없음 |
| OS-registered state | None — Task Scheduler `uv run python main.py` 무변경(CLAUDE.md). | 없음 |
| Secrets/env vars | None — yfinance 무키. `OPENDART_API_KEY`는 D1로 미사용 경로. | 없음 |
| Build artifacts | None — 신규 모듈 추가뿐, pyproject/패키지명 무변경. | 없음 |

**캐시 호환:** 기존 캐시 키 포맷 불변. 신규 `company` 네임스페이스는 독립 디렉토리 → 기존 OHLCV/펀더멘털 캐시와 충돌 없음.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `longName`이 KR `.KQ` 전 종목에 영문 반환 | Q1 | 일부 소형 KQ 종목 longName None → shortName(쓰레기)·티커 폴백. 폴백 체인이 흡수하나 일부 행에 티커만 표시. (3종목만 검증; 200종목 전수 미검증) |
| A2 | `.info` 1회 ≈1s가 200종목에서 선형 | Pitfall 3 | yahoo 부하/시간대에 따라 변동. 캐시가 재실행 비용 0으로 만들어 위험 완화 |
| A3 | `fast_info`에 이름 키 없음 | Stack/Alternatives | 있더라도 영향 없음 — `.info` 사용 결정 불변 |

## Open Questions (RESOLVED)

1. **RESOLVED: 기업명 fetch를 펀더멘털과 공유(왕복 0) vs 독립 함수(명확·캐시흡수)?**
   - 아는 것: 공유는 왕복 0이나 펀더멘털 결손 분기에만 호출됨(Pitfall 2). 독립은 항상 호출되나 중복 왕복 가능(캐시가 흡수).
   - 결정: **독립 `fetch_company_name` + 30일 캐시** — 정확성·명확성 우선. 캐시로 비용 상쇄.

2. **RESOLVED: freeze A열 고정(B6 유지) vs 기업명까지 고정(C6)?**
   - 결정: **B6 유지(티커 열만 고정)** — 사용자 확정. `test_freeze_panes.py` 무수정.

3. **RESOLVED: 결손 폴백 = 빈칸 vs 티커?**
   - 결정: **티커 폴백** — 빈칸은 "어느 종목?" 혼란. 티커는 최소 식별성 보장 (CONTEXT discretion).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| yfinance | `.info` 기업명 | ✓ | 1.3.0 | — |
| curl_cffi `_SESSION` | TLS | ✓ | 기존 | — |
| diskcache | 기업명 캐시 | ✓ | 기존 | — |
| 네트워크(Yahoo) | 첫 실행 조회 | 런타임 의존 | — | 캐시 HIT / 티커 폴백 |

미충족·차단 의존성 없음.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x |
| Config file | pyproject.toml `[tool.pytest...]` |
| Quick run | `uv run pytest tests/test_sheet_portfolio.py tests/test_freeze_panes.py -x` |
| Full suite | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| COMPANY-01 | col 1 = 기업명, col 2 = 시장(시프트) | unit | `pytest tests/test_sheet_portfolio.py -k company -x` | ❌ Wave 0 (신규) |
| COMPANY-01 | 헤더 22열, [1]=="기업명" | unit | `pytest tests/test_sheet_portfolio.py::test_column_count -x` | ⚠️ 갱신(21→22) |
| COMPANY-02 | longName 우선, shortName/티커 폴백 | unit | `pytest tests/test_company_name.py -x` | ❌ Wave 0 (신규, `.info` mock) |
| COMPANY-03 | 결손 시 티커 폴백, 후속 셀·하이퍼링크·색·freeze 무회귀 | unit | `pytest tests/test_sheet_portfolio.py tests/test_freeze_panes.py` | ⚠️ 좌표 +1 갱신 |
| COMPANY-04 | 캐시 HIT 시 무호출 | unit | `pytest tests/test_company_name.py -k cache -x` | ❌ Wave 0 (신규) |

### Wave 0 Gaps
- [ ] `tests/test_company_name.py` — longName/shortName/티커 폴백 + 캐시 HIT/MISS (`.info` mock, 네트워크 없음). COMPANY-02/04.
- [ ] `test_sheet_portfolio.py` 갱신 — `test_column_count_is_21`→22, 모든 `column=N` 좌표 +1, 신규 `test_company_name_column`.
- [ ] `test_freeze_panes.py` — **B6 유지 선택 시 무수정**. C6 선택 시 2건 갱신.
- [ ] `mock_pipeline_env`(test_freeze_panes) — 기업명 fetch stub 추가.

## Security Domain

> 개인용 로컬 도구. 외부 입력 = `tickers.txt`(사용자 본인 작성) + yfinance 응답.

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | `longName`은 외부 문자열 → 시트 셀에 그대로 write(xlsxwriter는 수식 인젝션 미실행, write_string 안전). 제어문자 우려 시 strip 가능 |
| V6 Cryptography | no | 해당 없음 |
| V2/V3/V4 | no | 무인증·단일 사용자 |

| Pattern | STRIDE | Mitigation |
|---------|--------|-----------|
| yfinance 응답 신뢰 | Tampering | longName은 표시 전용, 정렬/수식 미사용 (D3 표시만) |
| 예외 원문 누설 | Info Disclosure | 기존 정책 준수 — `type(e).__name__`만 로그(`runner.py:99` 패턴), 키/UA 미노출 |

## Sources

### Primary (HIGH confidence)
- 라이브 검증 `yf.Ticker(...).info` — longName/shortName US+KR 반환값, `.info` 1회 0.98s/184키 [VERIFIED: 본 세션 실행]
- `import yfinance.__version__` → 1.3.0 [VERIFIED]
- 코드베이스 grep `.info`/`Ticker(` — `yf_fundamentals.py:32`가 이미 `.info` 호출 [VERIFIED: codebase grep]
- `src/stocksig/{io/yf_fundamentals,io/market,io/cache,io/throttle,io/input,runner,main_run,output/sheet_portfolio}.py` 정독 [VERIFIED]
- `tests/test_sheet_portfolio.py`, `tests/test_freeze_panes.py` 정독 — 회귀 좌표 [VERIFIED]

### Secondary (MEDIUM confidence)
- CLAUDE.md yfinance rate-limit 정책 (threads=False/2 + tenacity) [CITED: CLAUDE.md]

## Metadata

**Confidence breakdown:**
- 데이터 소스/필드(Q1): HIGH — longName US+KR 라이브 검증, 기존 `.info` 패턴 존재
- 호출량/캐시(Q2): HIGH — 기존 throttle/캐시 재사용, `.info` 비용 측정
- 파이프라인 훅(Q3): HIGH — `fundamentals_fn`/`TickerResult` 경로 확인
- 컬럼 시프트(Q4): HIGH — 하드코딩 인덱스 전수 확인
- 회귀 표면(Q5): HIGH — 테스트 좌표 전수 매핑
- KQ 전수 영문(A1): MEDIUM — 3종목만 검증

**Research date:** 2026-06-16
**Valid until:** 2026-07-16 (yfinance `.info` 키 변동 가능 — `pegRatio` 등 과거 변동 이력)
