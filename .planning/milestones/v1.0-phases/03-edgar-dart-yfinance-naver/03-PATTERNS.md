# Phase 3: 기본적 분석 데이터 (EDGAR/DART/yfinance·Naver 보완) - Pattern Map

**Mapped:** 2026-06-02
**Files analyzed:** 신규 9 + 수정 5 = 14 (테스트 8 별도)
**Analogs found:** 14 / 14 (전 파일 강한 analog 보유 — 코드베이스가 동일 계열 패턴으로 일관)

> 모든 신규 I/O 클라이언트는 `src/stocksig/io/market.py`(외부 API 클라이언트 + throttle + cache 합성)를 mother analog으로 한다. throttle/cache/runner/sheet 확장은 기존 동명 모듈을 그대로 이어 쓴다.

---

## File Classification

### 신규 파일

| 신규 파일 | Role | Data Flow | Closest Analog | Match Quality |
|-----------|------|-----------|----------------|---------------|
| `src/stocksig/io/edgar_client.py` | service (API client) | request-response | `src/stocksig/io/market.py` | exact (외부 API + throttle + cache) |
| `src/stocksig/io/dart_client.py` | service (API client) | request-response | `src/stocksig/io/market.py` | exact |
| `src/stocksig/io/naver_scraper.py` | service (scraper) | request-response | `src/stocksig/io/market.py` | role-match (httpx GET 대신 yf) |
| `src/stocksig/io/yf_fundamentals.py` | service (API client) | request-response | `src/stocksig/io/market.py` | exact (`_SESSION` 재사용까지 동일) |
| `src/stocksig/io/dart_account_map.py` | config (상수 맵) | transform | `src/stocksig/output/writer.py` `_NUM_FORMAT_MAP` / `_COLOR_PROPS` | role-match (모듈 레벨 상수 dict) |
| `src/stocksig/io/fundamentals.py` | service (orchestrator) | request-response (fallback routing) | `src/stocksig/main_run.py` `_make_pipeline` + `runner.process_ticker` | role-match (라우팅 + provenance) |
| `tests/test_edgar_client.py` | test | — | `tests/test_market.py` | exact (mocker.patch 외부 클라이언트) |
| `tests/test_dart_client.py` | test | — | `tests/test_market.py` | exact |
| `tests/test_naver_scraper.py` | test | — | `tests/test_market.py` | exact (HTML fixture mock) |
| `tests/test_yf_fundamentals.py` | test | — | `tests/test_market.py` | exact |
| `tests/test_fundamentals.py` | test | — | `tests/test_runner.py` | role-match (callable 주입 + 폴백 분기) |

### 수정 파일

| 수정 파일 | Role | Data Flow | 기존 패턴 (in-file analog) | Match Quality |
|-----------|------|-----------|----------------------------|---------------|
| `src/stocksig/io/throttle.py` | middleware (rate-limit) | cross-cutting | 동일 파일 `throttled_yahoo` (L19-27) | exact (복붙 + Rate 값만 변경) |
| `src/stocksig/io/cache.py` | utility (cache) | cross-cutting | 동일 파일 `get_ohlcv/put_ohlcv` (L25-57) | exact (별 인스턴스 + 키 포맷 변경) |
| `src/stocksig/runner.py` | service (orchestrator) | request-response | 동일 파일 `process_ticker` (L63-79) + `TickerResult` (L34-41) | exact (필드 추가 + try/except 1블록) |
| `src/stocksig/output/sheet_portfolio.py` | component (writer) | transform | 동일 파일 col 4 `write_number` (L118-122) + `PORTFOLIO_COLUMNS` (L34-52) | exact (컬럼 4개 + write_comment) |
| `tests/test_cache.py`, `tests/test_throttle.py`, `tests/test_sheet_portfolio.py` | test | — | 각 동명 파일 기존 테스트 | exact (테스트 함수 추가) |
| `pyproject.toml` | config | — | 동일 파일 `dependencies` 배열 (L6-16) | exact (4 deps 추가) |

---

## Pattern Assignments

### `src/stocksig/io/edgar_client.py` (service / request-response)

**Analog:** `src/stocksig/io/market.py` (전체 — module-level singleton + throttle 데코레이터 + cache 우선 페치 2함수 구조)

**Imports pattern** (`market.py` L15-35 그대로 차용):
```python
from __future__ import annotations
import logging
from edgar import Company, set_identity          # 주의: 패키지명 edgartools ≠ import 이름 edgar
from stocksig.io import cache
from stocksig.io.throttle import throttled_edgar   # 신규 데코레이터
logger = logging.getLogger(__name__)
```

**Module-level singleton pattern** (`market.py` L37-38 `_SESSION` 패턴 차용 — set_identity는 프로세스당 1회):
```python
# market.py L37-38: "# 모듈 레벨 단일 인스턴스 (후속 wave에서 별도 session 생성 금지)"
#                   _SESSION = curl_requests.Session(impersonate="chrome")
# edgar_client는 동일하게 import-time 1회 호출 (FUND-02, RESEARCH Anti-Pattern: per-call 금지):
set_identity("Yunjae Kim yunjerrard@gmail.com")   # config.load_env()["EDGAR_USER_AGENT_EMAIL"] 사용 권장
```

**Throttle 데코레이터 + 페치 함수 구조** (`market.py` L44-86 `fetch_ohlcv` 그대로 — `@throttled_*` 위에 + 빈응답 ValueError fail-fast):
```python
# market.py L44-51 decorator stack 패턴:
#   @throttled_yahoo
#   @retry(...)
#   def fetch_ohlcv(ticker): ...
# edgar_client는 retry 생략(edgartools 내부 처리), throttle만:
@throttled_edgar
def fetch_edgar_raw(ticker: str) -> dict:
    company = Company(ticker)
    ...
    logger.info("%s | EDGAR facts 수신 완료", ticker)   # market.py L85 로그 형식
    return {...}
```

**Cache-first 페치 패턴** (`market.py` L89-102 `fetch_ohlcv_cached` 구조 그대로 — get → miss시 fetch → put):
```python
# market.py L89-102 패턴:
def fetch_edgar_cached(ticker: str, quarter_label: str) -> dict:
    cached = cache.get_fund("EDGAR", ticker, quarter_label)   # 신규 cache 함수 (아래 cache.py 참조)
    if cached is not None:
        return cached
    raw = fetch_edgar_raw(ticker)
    cache.put_fund("EDGAR", ticker, quarter_label, raw)
    return raw
```

---

### `src/stocksig/io/dart_client.py` (service / request-response)

**Analog:** `src/stocksig/io/market.py` (동일 구조) + `src/stocksig/io/market_kind.py` (티커 접미사 파싱)

**Stock_code 파싱** (`market_kind.py` L15-21 `classify_market`의 `.upper()` + suffix 매칭 발상 — 단 여기선 `.split(".")[0]`):
```python
# market_kind.py L12: KR_SUFFIXES = (".KS", ".KQ", ".KOSDAQ", ".KOSPI")
# dart_client는 접미사 제거: "005930.KS" → "005930" (RESEARCH Pattern 4)
stock_code = ticker.split(".")[0]
```

**Throttle + cache 페치** (`market.py` L89-102 동일 — `@throttled_dart`, `cache.get_fund("DART", ...)`):
```python
@throttled_dart
def fetch_dart_raw(ticker: str, year: int) -> dict:
    import OpenDartReader
    dart = OpenDartReader(api_key)                            # config.load_env()["OPENDART_API_KEY"]
    df = dart.finstate_all(ticker.split(".")[0], year, reprt_code="11011", fs_div="CFS")
    # status 필드 확인 (RESEARCH Pitfall 3): "000"=정상, "013"=데이터없음, "020"=쿼터초과
    ...
```

**account_nm → 값 매핑** — `dart_account_map.py` 상수 dict 사용 (아래 참조).

---

### `src/stocksig/io/yf_fundamentals.py` (service / request-response)

**Analog:** `src/stocksig/io/market.py` — 특히 `_SESSION` 재사용 규칙 (L37 주석: "별도 session 생성 금지")

**`_SESSION` 재사용 + throttle** (`market.py` L33,38,44 — 기존 yahoo limiter·세션 그대로):
```python
# RESEARCH Anti-Pattern: "새 curl_cffi/httpx 세션 남발 금지 — io/market._SESSION 재사용"
from stocksig.io.market import _SESSION
from stocksig.io.throttle import throttled_yahoo   # 기존 2 RPS 그대로 (신규 limiter 불필요)
import yfinance as yf

@throttled_yahoo
def fetch_yf_info(ticker: str) -> dict:
    info = yf.Ticker(ticker, session=_SESSION).info   # market.py L74 와 동일 호출 형태
    return {
        "PER": info.get("trailingPE"),
        "PEG": info.get("pegRatio") or info.get("trailingPegRatio"),   # 키 변동 가드 (A4)
        "GPM": info.get("grossMargins"),
        "OPM": info.get("operatingMargins"),
    }
```

---

### `src/stocksig/io/naver_scraper.py` (service / request-response — KR 2차 폴백)

**Analog:** `src/stocksig/io/market.py` (throttle + None-safe 가드 + 한국어 로그) — httpx GET은 신규

```python
import httpx
from bs4 import BeautifulSoup
from stocksig.io.throttle import throttled_yahoo   # 보수적 재사용 또는 신규 한도

@throttled_yahoo   # 폴백 전용 — 보수적 호출
def fetch_naver_per(ticker: str) -> float | None:
    code = ticker.split(".")[0]
    url = f"https://finance.naver.com/item/main.naver?code={code}"
    r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
    r.encoding = "euc-kr"                              # RESEARCH Pitfall 5 — EUC-KR 필수
    soup = BeautifulSoup(r.text, "lxml")
    el = soup.select_one("#_per")                      # A5 — executor 실페이지 검증
    if el is None:                                     # market.py L80 빈응답 가드 발상
        return None
    return float(el.text.replace(",", ""))             # ASVS V5: try/except float 파싱
```
> Naver는 PER만 현실적 폴백 (GPM/OPM 미노출 — RESEARCH Open Q4). `select_one` None 가드 필수.

---

### `src/stocksig/io/dart_account_map.py` (config / 상수 맵)

**Analog:** `src/stocksig/output/writer.py` `_NUM_FORMAT_MAP` (L48-53) + `_COLOR_PROPS` (L57-66) — 모듈 레벨 `dict` 상수, 대문자 `_` prefix 명명

```python
# writer.py L48-53 패턴: 모듈 상수 dict (키=논리명, 값=후보 리스트)
# account_nm은 업종별 표기 상이 → 후보 리스트 (RESEARCH Pattern 4 매핑표)
DART_ACCOUNT_MAP: dict[str, tuple[str, ...]] = {
    "revenue":     ("매출액", "수익(매출액)", "영업수익"),
    "gross_profit": ("매출총이익",),
    "op_income":   ("영업이익", "영업이익(손실)"),
    "net_income":  ("당기순이익", "당기순이익(손실)"),
    "eps":         ("기본주당이익", "기본주당순이익"),
}
```
> executor가 005930(삼성전자, CFS) 1회 실호출로 정확 문자열 확정 후 상수화 (A3).

---

### `src/stocksig/io/fundamentals.py` (service / orchestrator — 폴백 라우팅 + provenance)

**Analog:** `src/stocksig/runner.py` `process_ticker` (L63-79, 의존성 주입 + try/except 격리) + `src/stocksig/main_run.py` `_make_pipeline` (L198-211, 클로저로 fetch 합성)

**데이터 모델** (`runner.py` L34-41 `@dataclass TickerResult` 패턴 그대로):
```python
# runner.py L34-41 dataclass 스타일 — RESEARCH Code Examples FundamentalsResult
from dataclasses import dataclass

@dataclass
class MetricCell:
    value: float | None
    source: str | None     # "EDGAR"|"DART"|"yf"|"Naver"|None
    note: str | None       # "EDGAR · 2026Q3" | "조회 실패: EPS 성장률 ≤ 0"

@dataclass
class FundamentalsResult:
    per: MetricCell
    peg: MetricCell
    gpm: MetricCell
    opm: MetricCell
```

**시장 라우팅** (`runner.py` L74 `classify_market(spec.symbol)` 호출 패턴 재사용):
```python
# runner.py L74: market = classify_market(spec.symbol)
from stocksig.io.market_kind import classify_market

def fetch_fundamentals(ticker: str, market: str, last_close: float) -> FundamentalsResult:
    if market == "US":
        # EDGAR → yf per-metric 폴백 (D-03)
    else:  # "KR"
        # DART → Naver(PER만) → yf per-metric 폴백 (D-04)
    ...
```

**예외 처리 규칙** (RESEARCH Anti-Pattern — fetch_fundamentals는 raise 금지 또는 호출부 흡수). 한국어 로그 형식은 `runner.py` L114 `"[%d/%d] OK %s"` 형식 차용: `[k/N] fund OK AAPL (EDGAR)`.

---

### `src/stocksig/io/throttle.py` (수정 — middleware)

**In-file analog:** `throttled_yahoo` (L13-27) — `Rate`/`Limiter`/`@wraps` 패턴 **완전 복붙**, Rate 값과 키 문자열만 변경

**기존 패턴** (L13-27 — 그대로 2회 복제):
```python
from pyrate_limiter import Duration, Limiter, Rate
from functools import wraps

_YAHOO_RATE = Rate(2, Duration.SECOND)            # → _EDGAR_RATE = Rate(8, ...) / _DART_RATE = Rate(2, ...)
_yahoo_limiter = Limiter(_YAHOO_RATE)

def throttled_yahoo(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        _yahoo_limiter.try_acquire("yahoo")       # → "edgar" / "dart"
        return fn(*args, **kwargs)
    return wrapper
```
> 추가: `@throttled_edgar` (8 RPS, FUND-06), `@throttled_dart` (2 RPS). L7 주석("Phase 3에서 EDGAR/DART용 limiter 추가 예정")이 이미 이 확장을 예고.

---

### `src/stocksig/io/cache.py` (수정 — utility)

**In-file analog:** `get_ohlcv/put_ohlcv` + `make_key` + `_get_cache` (L19-57) — 별도 `_FUND_CACHE` 인스턴스 + 7d TTL + 3-part 키

**기존 패턴** (L19-57):
```python
_DEFAULT_DIR = Path(".cache/ohlcv")               # → _FUND_DIR = Path(".cache/fundamentals")
_TTL_SECONDS = 24 * 60 * 60                        # → _FUND_TTL_SECONDS = 7 * 24 * 60 * 60
_cache: Optional[Cache] = None                     # → _fund_cache: Optional[Cache] = None

def _get_cache() -> Cache:                          # → _get_fund_cache() (동일 lazy-init)
    global _cache
    if _cache is None:
        _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
        _cache = Cache(str(_DEFAULT_DIR))
    return _cache

def make_key(ticker, today=None) -> str:            # → make_fund_key(source, ticker, quarter_label)
    return f"{ticker}|{d.isoformat()}"              #   return f"{source}|{ticker}|{quarter_label}"

def put_ohlcv(ticker, df):                          # → put_fund(source, ticker, quarter_label, value)
    _get_cache().set(key, df, expire=_TTL_SECONDS)  #   expire=_FUND_TTL_SECONDS
```
> 별도 `.cache/fundamentals` 디렉터리 — 기존 24h OHLCV 캐시 무영향 (RESEARCH Runtime State Inventory). 키 예: `"EDGAR|AAPL|2026Q3"`.

---

### `src/stocksig/runner.py` (수정 — orchestrator)

**In-file analog:** `TickerResult` (L34-41) + `process_ticker` (L63-79)

**`TickerResult` 필드 추가** (L34-41 — 하위호환 위해 `= None` 기본값):
```python
@dataclass
class TickerResult:
    spec: TickerSpec
    enriched_df: pd.DataFrame
    market: str  # "US" | "KR"
    fundamentals: "FundamentalsResult | None" = None   # 신규 — 기본 None (Phase 1/2 테스트 통과)
```

**`process_ticker` PASS 1b 삽입** (L63-79 — 시세 검증 후, try/except로 펀더멘털 격리):
```python
# 기존 L74-79:
#   market = classify_market(spec.symbol)
#   df = pipeline(spec.symbol)
#   reason = _validate_row_count(spec.symbol, df)
#   if reason is not None: raise ValueError(reason)   # 시세 결손 = 티커 실패 (유지)
#   return TickerResult(spec=spec, enriched_df=df, market=market)
# 추가 (D-disc-10 — 펀더멘털 결손 ≠ 티커 실패):
    fund = None
    if fundamentals_fn is not None:
        try:
            last_close = df.iloc[-1].get("Close")
            fund = fundamentals_fn(spec.symbol, market, last_close)
        except Exception as e:                          # L115 run_all except 패턴 차용
            logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", spec.symbol, e)
    return TickerResult(spec=spec, enriched_df=df, market=market, fundamentals=fund)
```
> `fundamentals_fn` 인자는 `process_ticker`/`run_all` 시그니처에 `=None` 추가 — `main_run._make_pipeline`(L198-211)와 동일 클로저 주입 방식으로 `run`에서 전달.

---

### `src/stocksig/output/sheet_portfolio.py` (수정 — component)

**In-file analog:** `PORTFOLIO_COLUMNS` (L34-52) + col 4 `write_number` (L118-122) + `_nan` 가드 (L73-81) + `_write_success_row` 말미 (L185-188)

**컬럼 확장** (L34-52 — 끝에 4개 추가, L96 테스트 상수 17→21):
```python
PORTFOLIO_COLUMNS = [..., "(주)임펄스",   # index 16 (기존 끝)
                     "PER", "PEG", "GPM", "OPM"]   # index 17,18,19,20 → 총 21열 (D-01)
```

**셀 작성 + 주석** (L118-122 `write_number(row, col, float(v), formats[(SigmaBucket.DEFAULT, "price")])` 패턴 + 신규 `write_comment`):
```python
# 기존 col 4 패턴 (L118-122):
#   close = last.get("Close")
#   if not _nan(close):
#       ws.write_number(row, 4, float(close), formats[(SigmaBucket.DEFAULT, "price")])
# 신규 헬퍼 (RESEARCH Code Examples — 색 신호 없음, DEFAULT bucket 고정):
def _write_fund_cell(ws, row, col, cell, num_fmt, formats):
    if cell.value is not None and not _nan(cell.value):
        ws.write_number(row, col, float(cell.value), formats[(SigmaBucket.DEFAULT, num_fmt)])
        if cell.source:
            ws.write_comment(row, col, cell.note or cell.source)
    else:
        ws.write_blank(row, col, None)                       # D-05: 0/-999999 금지, 빈 셀
        ws.write_comment(row, col, cell.note or "조회 실패")

# _write_success_row 말미 (col 16 다음, L188 이후):
if res.fundamentals is not None:                              # None 가드 (하위호환)
    f = res.fundamentals
    _write_fund_cell(ws, row, 17, f.per, "price",         formats)  # #,##0.00
    _write_fund_cell(ws, row, 18, f.peg, "price",         formats)
    _write_fund_cell(ws, row, 19, f.gpm, "percent_ratio", formats)  # 0.00% (0~1 비율)
    _write_fund_cell(ws, row, 20, f.opm, "percent_ratio", formats)
```
> `ws.set_column(0, len(PORTFOLIO_COLUMNS)-1, 14)` (L223)이 21열 자동 적용 — 변경 불필요. `freeze_panes(5,1)` (L252) 유지. **신규 Format 0개** — 기존 캐시 재사용 (RESEARCH).

---

### Test 파일 (신규 + 확장)

**Analog:** `tests/test_market.py` (외부 클라이언트 mock) + `tests/test_runner.py` (callable 주입) + `tests/conftest.py` (fixture)

**외부 클라이언트 mock 패턴** (`test_market.py` L31-51, `mocker.patch`로 외부 호출 차단):
```python
# test_market.py L33-34 패턴 — edgar/dart/yf/naver에 동일 적용:
def test_edgar_fetch(mocker):
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = ...
    result = fetch_edgar_raw("AAPL")
    ...
```

**isolated cache fixture** (`test_market.py` L97-107 `_tmp_cache` + `test_cache.py` L15-28 `_isolated_cache_dir`) — `test_cache.py`에 `_FUND_CACHE` 7d 테스트 추가 시 동일 monkeypatch 패턴, `freeze_time`으로 TTL 검증 (L53-66).

**callable 주입 + 폴백 분기** (`test_runner.py` L23-41 — `_classify`/`pipeline` 클로저 주입) → `test_fundamentals.py`의 폴백 체인·PEG 엣지케이스(성장률≤0/0분모)에 동일 in-memory stub 주입.

**openpyxl readback** (`test_sheet_portfolio.py` L88-89 `_open` + L105-109 `ws.cell(row, column).value`) → col 17~20 값 + `ws.cell().comment` readback으로 PORT-05 검증. `test_column_count_is_17` (L95-96)은 **21로 갱신**.

---

## Shared Patterns

### 1. Throttle (rate-limit cross-cutting)
**Source:** `src/stocksig/io/throttle.py` L13-27 (`throttled_yahoo`)
**Apply to:** `edgar_client.py` (`@throttled_edgar` 8 RPS), `dart_client.py` (`@throttled_dart` 2 RPS), `naver_scraper.py`/`yf_fundamentals.py` (`@throttled_yahoo` 재사용)
```python
_EDGAR_RATE = Rate(8, Duration.SECOND); _edgar_limiter = Limiter(_EDGAR_RATE)
def throttled_edgar(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        _edgar_limiter.try_acquire("edgar")
        return fn(*a, **k)
    return wrapper
```

### 2. Cache-first fetch (I/O cross-cutting)
**Source:** `src/stocksig/io/market.py` L89-102 (`fetch_ohlcv_cached`) + `src/stocksig/io/cache.py` L25-57
**Apply to:** 모든 1차 클라이언트 (edgar/dart) — get_fund → miss시 fetch → put_fund. 키 `"{source}|{ticker}|{quarter}"`, 7d TTL.

### 3. Module-level singleton (별 세션/identity 1회)
**Source:** `src/stocksig/io/market.py` L37-38 (`_SESSION`, "별도 session 생성 금지" 주석)
**Apply to:** `edgar_client.set_identity()` (import-time 1회), `yf_fundamentals` (`market._SESSION` 재사용 — 신규 세션 금지)

### 4. 빈응답 / None-safe 가드 + fail-fast
**Source:** `src/stocksig/io/market.py` L80-83 (빈 DataFrame → ValueError) + `sheet_portfolio.py` `_nan` L73-81
**Apply to:** 모든 클라이언트는 None-safe `.get()` / `select_one` None 가드. 단 **펀더멘털은 fail-fast 아님** — `fundamentals.py`/`runner` try/except로 흡수 (D-disc-10).

### 5. 한국어 로그 형식
**Source:** `src/stocksig/io/market.py` L85 (`"%s | OHLCV %d 거래일 수신 완료"`) + `runner.py` L114 (`"[%d/%d] OK %s"`)
**Apply to:** 펀더멘털 진행 로그 — `[k/N] fund OK AAPL (EDGAR)` / `fund FALLBACK 005930.KS (DART→Naver)` / `fund MISS GOOGL`.

### 6. Format 캐시 재사용 (신규 Format 0개)
**Source:** `src/stocksig/output/writer.py` L89-94 (`formats[(bucket, fmt_type)]`) — `(SigmaBucket.DEFAULT, "price")` / `(SigmaBucket.DEFAULT, "percent_ratio")`
**Apply to:** `sheet_portfolio._write_fund_cell` — PER/PEG=`"price"`(`#,##0.00`), GPM/OPM=`"percent_ratio"`(`0.00%`). `make_workbook` 44키 불변.

### 7. dataclass 결과 모델
**Source:** `src/stocksig/runner.py` L34-49 (`TickerResult`/`TickerFailure`)
**Apply to:** `fundamentals.MetricCell` / `FundamentalsResult`.

### 8. 의존성 주입 클로저
**Source:** `src/stocksig/main_run.py` L198-211 (`_make_pipeline` 클로저) + `runner.process_ticker` L63-67 (callable 인자)
**Apply to:** `fundamentals_fn`을 `process_ticker`/`run_all`에 `=None` 인자로 주입, `main_run.run`에서 `fetch_fundamentals` 클로저 전달.

---

## No Analog Found

없음. 모든 신규 파일이 기존 코드베이스에 강한 analog 보유.

| 부분 | 신규성 | 비고 |
|------|--------|------|
| `naver_scraper.py` httpx GET + bs4 파싱 | 부분 신규 | httpx/bs4 호출 자체는 신규지만, throttle·None가드·한국어로그 구조는 `market.py` 그대로. RESEARCH Pattern 6에 코드 시드 존재. |
| `fundamentals.py` per-metric provenance 폴백 | 부분 신규 | 라우팅(`classify_market`)·dataclass·try/except 격리는 기존 패턴. 폴백 체인 로직만 신규 — RESEARCH 아키텍처 다이어그램(L137-170)·Code Examples에 명세. |

> `[ASSUMED — executor 실데이터 검증 필수]` 항목 (RESEARCH A1~A7): edgartools 5.x 정확 메서드명, DART account_nm 문자열, Naver 셀렉터/EUC-KR, yfinance `.info` 키. planner는 Wave 0에 "실데이터 1회 검증 → 상수 확정" 스파이크 배치 (RESEARCH L520, Wave 0 Gaps).

---

## Metadata

**Analog search scope:** `src/stocksig/io/` (market, throttle, cache, market_kind), `src/stocksig/` (runner, main_run, config), `src/stocksig/output/` (sheet_portfolio, writer), `tests/` (market, throttle, cache, runner, sheet_portfolio, conftest)
**Files scanned:** 14 (소스 8 + 테스트 5 + pyproject 1)
**Pattern extraction date:** 2026-06-02
