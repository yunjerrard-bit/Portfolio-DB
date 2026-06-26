# Phase 3: 기본적 분석 데이터 (EDGAR/DART/yfinance·Naver 보완) - Research

**Researched:** 2026-06-02
**Domain:** 미국(SEC EDGAR / edgartools) + 한국(OpenDART / OpenDartReader) 펀더멘털 데이터 취득, yfinance·Naver 폴백, XBRL concept tag / DART account_nm 매핑, XlsxWriter 셀 주석으로 출처 표기
**Confidence:** HIGH (라이브러리 선택·API 표면·throttle/cache 확장 패턴) / MEDIUM (EDGAR XBRL concept tag 우선순위·DART account_nm 정확 문자열·Naver 셀렉터 — 실데이터 검증 필요, 본 환경에서 라이브 호출 불가)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (컬럼 위치):** PER/PEG/GPM/OPM 4셀을 시트1 **R/S/T/U** 에 추가 — (주)임펄스(Q) 직후 우측 끝. 시트1 총 컬럼 수 17 → **21열**.
- **D-02 (출처 표시 방식):** Excel 셀 주석(`xlsxwriter.write_comment`)으로 표시. 값 셀은 숫자만 (`#,##0.00` 또는 `0.00%` num_format 유지). 주석 형식: `"<SOURCE>"` 단순 라벨 또는 `"<SOURCE> · <짧은 메타>"` (예: `EDGAR · 2026Q3 10-Q`).
- **D-03 (미국 폴백 체인):** **EDGAR → yfinance**. EDGAR에서 결손된 *개별 지표만* yfinance.info에서 보완. yfinance도 결손이면 빈 셀.
- **D-04 (한국 폴백 체인):** **DART → Naver Finance → yfinance**. DART 결손 시 Naver 금융 스크래핑, 그래도 결손 시 yfinance.info. 모두 결손 시 빈 셀.
- **D-05 (결손 셀 표시):** 빈 셀 + 주석에 `"조회 실패: <이유>"` 기록. 0/특수값(-999999) 비사용.
- **D-06 (종목별 시트):** 변경 없음. 펀더멘털은 **시트1에만 노출**.

### Claude's Discretion (researcher가 채움 — 아래 본문에서 권고 확정)

1. PEG 산식: `PEG = PER / ((EPS_TTM / EPS_prior_year_TTM − 1) × 100)`. 성장률 ≤ 0 → N/A.
2. EDGAR XBRL concept tag 매핑: EPS=`EarningsPerShareDiluted` 우선, GPM=`GrossProfit`/`RevenueFromContractWithCustomerExcludingAssessedTax`, OPM=`OperatingIncomeLoss`.
3. DART account_nm 매핑: 005930로 시범 후 `dart_account_map.py` 상수화.
4. 캐시 키: `(source, ticker, quarter_label)`, 7d TTL.
5. 토큰버킷 limiter: `@throttled_edgar` (8 RPS) + `@throttled_dart` (2 RPS).
6. 출처 라벨: `'EDGAR' / 'yf' / 'DART' / 'Naver'`.
7. Naver scraping: `httpx` + BeautifulSoup4 + lxml.
8. 신규 의존성: `edgartools`, `OpenDartReader`, `beautifulsoup4`, `lxml`.
9. 실패 분류: 한국어 사유 문자열 매핑.
10. runner.py 통합: PASS 1에서 OHLCV fetch 직후 펀더멘털 fetch. 펀더멘털 결손 ≠ 티커 실패.

### Deferred Ideas (OUT OF SCOPE)

- "데이터 품질" 별도 시트 (Phase 4, EXEC-04).
- frozen panes 1~5행 (Phase 4, OUT-04). **단주의:** 기존 `sheet_portfolio.py`는 이미 `ws.freeze_panes(5, 1)` 호출 중 — Phase 3은 이 라인을 건드리지 않는다.
- 종목별 시트의 펀더멘털 컬럼 (D-06).
- 분기별 펀더멘털 시계열 (D-06: 최신 1개만).
- 펀더멘털 σ 색 신호 (PORT-05는 "값 + 출처"만).
- `pandas-ta` 미사용 유지. edgartools "Companies" API 메타 확장. API 키/UA 자동 검증.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FUND-01 | 미국 티커는 edgartools로 EDGAR에서 PER/PEG/GPM/OPM raw facts(EPS, Revenues, GrossProfit, OperatingIncomeLoss) 취득 | §"EDGAR (미국) — edgartools 5.x" 코드 경로 + concept tag 매핑표 |
| FUND-02 | EDGAR 호출 UA에 사용자 이메일 포함 | `set_identity("Yunjae Kim yunjerrard@gmail.com")` — §"EDGAR User-Agent" |
| FUND-03 | 한국 티커는 OpenDartReader로 DART 재무 취득(corp_code 매핑 포함) | §"DART (한국) — OpenDartReader" — `finstate_all('005930', year)` 가 stock_code 직접 수용, corp_code 내부 해석 |
| FUND-04 | EDGAR/DART 응답 7d TTL sqlite 캐시 | §"캐시 확장" — `_FUND_CACHE` 7d, 키 `(source\|ticker\|quarter_label)` |
| FUND-05 | 1차 결손 항목은 yfinance/Naver 보완 + 사용 소스 기록 | §"폴백 체인 + 출처 추적" — per-metric provenance dict |
| FUND-06 | 토큰버킷 EDGAR ≤8 RPS, DART ≤2 RPS | §"throttle 확장" — `@throttled_edgar`/`@throttled_dart` pyrate_limiter 4.x |
| PORT-05 | 시트1 각 티커 행에 PER/PEG/GPM/OPM 값 + 출처 표시 | §"시트1 21열 + 셀 주석" — col 17~20 + `write_comment` |
</phase_requirements>

## Summary

Phase 3은 **데이터 취득 4소스(EDGAR/DART/yfinance/Naver) + 폴백 체인 + 시트1 4셀 표시**의 통합이다. 좋은 소식은 두 1차 라이브러리가 매우 깔끔한 표면을 제공한다는 점이다:

- **edgartools** 최신은 **5.33.0** (2026-05-29 릴리스). 패키지명은 `edgartools`이지만 **import 이름은 `edgar`**다. `set_identity(...)` 한 줄로 SEC UA 정책을 충족하고, `Company("AAPL").get_facts().to_pandas("us-gaap:Revenues")` 또는 `xbrl.facts.query().by_concept(...)`로 raw XBRL facts를 DataFrame으로 꺼낸다. **CLAUDE.md/CONTEXT.md가 "4.x"로 가정한 것은 stale다 — 5.x로 진행하되 API 표면은 동일 계열이며 본 문서가 5.x 경로를 명시한다.**
- **OpenDartReader** 최신은 **0.3.2** (CONTEXT.md "0.2.x" 하한은 만족하나 0.3.x 사용 권장). 결정적으로 `finstate(corp, year)` / `finstate_all(corp, year)`가 **6자리 stock_code("005930")를 직접 수용하고 corp_code를 내부에서 해석**한다. 따라서 PITFALLS.md #3이 경고한 "corp_code 수동 매핑·corpCode.xml 다운로드" 부담은 라이브러리가 흡수한다 — `.KS`/`.KQ` 접미사만 제거하면 된다. (단 라이브러리 corp_code 캐시 staleness는 잔존 리스크.)

기존 코드 재사용도 명확하다: `io/throttle.py`(pyrate_limiter **4.1.0** 확인)에 limiter 2개 추가, `io/cache.py`에 7d TTL 인스턴스 추가, `io/market_kind.classify_market`로 US/KR 라우팅, `runner.py` PASS 1에 try/except로 감싼 펀더멘털 fetch 1줄 삽입, `output/sheet_portfolio.py`에 col 17~20 + `write_comment` 추가.

**Primary recommendation:** 신규 모듈 `io/fundamentals.py`(또는 4개 분리: `edgar_client.py`/`dart_client.py`/`naver_scraper.py`/`yf_fundamentals.py`)에서 **per-metric 폴백 + provenance dict**(`{"PER": (value, "EDGAR"), "PEG": (None, "조회 실패: EPS 성장률 ≤ 0"), ...}`)를 반환하는 단일 함수 `fetch_fundamentals(ticker, market) -> FundamentalsResult`를 만들고, `runner`는 이를 try/except로 흡수해 `TickerResult`에 첨부, `sheet_portfolio`는 dict를 col 17~20에 풀어 쓴다. **edgartools 5.x·DART account_nm·Naver 셀렉터는 executor가 실데이터(AAPL/MSFT/GOOGL, 005930, 005930 Naver 페이지)로 1회 검증 후 상수 확정**해야 한다(본 환경 라이브 호출 불가).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| US 펀더멘털 취득 | API client (`io/edgar_client`) | — | EDGAR는 외부 SEC API. yfinance(시세)와 별개 클라이언트. |
| KR 펀더멘털 취득 | API client (`io/dart_client`) | Scraper(`io/naver_scraper`) | DART 1차, Naver 스크래핑 2차 폴백. |
| 보완(폴백) 취득 | API client (`io/yf_fundamentals`) | — | yfinance `.info`는 양국 공통 최후 폴백. |
| 폴백 라우팅 + provenance | Orchestration (`io/fundamentals` 또는 `runner`) | — | per-metric 결손 판정·소스 라벨 부착은 한 곳에서. |
| Rate-limit 강제 | I/O cross-cutting (`io/throttle`) | — | 소스별 토큰버킷. 기존 단일 진원지 확장. |
| 응답 캐시 | I/O cross-cutting (`io/cache`) | — | 7d TTL, `(source,ticker,quarter)` 키. |
| 시트1 값 + 출처 렌더 | Output (`output/sheet_portfolio`) | Output(`output/writer` Format) | 숫자 셀 + `write_comment` 주석. 색 신호 없음(PORT-05). |
| US/KR 분기 라우팅 | Domain (`io/market_kind`) | — | 기존 `classify_market` 재사용. |

## Standard Stack

### Core
| Library | Version (확인) | Purpose | Why Standard |
|---------|----------------|---------|--------------|
| edgartools | **5.33.0** (2026-05-29) `[VERIFIED: PyPI]` | SEC EDGAR US 펀더멘털 (XBRL facts) | MIT, 무료, API 키 불필요, typed 객체+DataFrame. CLAUDE.md CHOSEN. **import 이름은 `edgar`.** |
| OpenDartReader | **0.3.2** `[VERIFIED: PyPI]` | DART KR 펀더멘털 | CLAUDE.md CHOSEN primary. stock_code 직접 수용·corp_code 내부 해석. |
| beautifulsoup4 | **4.14.3** `[VERIFIED: PyPI]` | Naver Finance HTML 파싱 | KR D-04 2차 폴백 스크래핑. |
| lxml | **6.1.1** `[VERIFIED: PyPI]` | bs4 파서 백엔드 | `BeautifulSoup(html, "lxml")` — 빠르고 견고. |

### Supporting (이미 설치됨 — 추가 불필요)
| Library | Version | Purpose | Note |
|---------|---------|---------|------|
| httpx | edgartools 의존성으로 자동 설치 (0.28.x) | Naver GET / EDGAR raw 폴백 | edgartools가 httpx≥0.25를 끌어옴 — Naver 스크래핑에 재사용. 별도 `requests` 도입 불필요. |
| yfinance | 0.2.66+ (설치됨) | `.info` 펀더멘털 폴백 | `Ticker(t, session=_SESSION).info` 의 `trailingPE`/`pegRatio`/`grossMargins`/`operatingMargins`. |
| diskcache | 5.6+ (설치됨) | 7d TTL 캐시 | 기존 `io/cache.py` 패턴 확장. |
| pyrate-limiter | **4.1.0** (uv env 확인) | 토큰버킷 | 기존 `io/throttle.py` 4.x API 확장. `pyproject` 핀 `>=3`은 4.x 허용. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| edgartools | raw `data.sec.gov` JSON (httpx) | 특정 비표준 concept tag 누락 시 FALLBACK ONLY. CLAUDE.md 명시. |
| OpenDartReader | dart-fss | OpenDartReader가 stale/엔드포인트 누락 시. 0.3.2가 2026 기준 활성 → 현재 불필요. |
| bs4+lxml | Playwright headless | Naver `item/main.naver`는 server-rendered HTML — headless 불필요. (검색 결과 일부가 "Naver는 JS 필요"라 했으나 이는 검색/쇼핑 페이지 한정. finance item/main은 정적.) `[ASSUMED — executor가 정적 렌더 확인]` |

**Installation:**
```bash
uv add "edgartools>=5,<6" "OpenDartReader>=0.3" "beautifulsoup4>=4.12" "lxml>=5"
```
> CONTEXT.md D-08은 `edgartools>=4`였으나 stale. 5.x가 현재 안정 최신이며 동일 API 계열. planner는 핀을 `>=5,<6`로 갱신할지 결정 (안전: `>=5,<6`).

**Version verification (2026-06-02 실행):**
- `pip index versions edgartools` → 5.33.0 (최신), 4.x 계열 존재 (4.0.0~4.35.1)
- `pip index versions OpenDartReader` → 0.3.2 (최신)
- `pip index versions beautifulsoup4` → 4.14.3 / lxml → 6.1.1
- `pyrate_limiter.__version__` (uv env) → **4.1.0** (throttle.py가 의존하는 4.x API 유효)

## Package Legitimacy Audit

> slopcheck 0.6.1 실행 (2026-06-02). `slopcheck install edgartools OpenDartReader beautifulsoup4 lxml`.

| Package | Registry | Age/최신 | Source Repo | slopcheck | Disposition |
|---------|----------|----------|-------------|-----------|-------------|
| edgartools | PyPI | 5.33.0 (2026-05-29) | github.com/dgunning/edgartools | [OK] | Approved |
| OpenDartReader | PyPI | 0.3.2 | (slopcheck: "No source repository linked") — 실제 github.com/FinanceData/OpenDartReader 존재하나 PyPI 메타에 미링크 | [OK] (경고 1) | Approved (메타 경고만) |
| beautifulsoup4 | PyPI | 4.14.3 | crummy.com / launchpad | [OK] | Approved |
| lxml | PyPI | 6.1.1 | github.com/lxml/lxml | [OK] | Approved |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none. (OpenDartReader는 PyPI 메타에 repo 링크가 없다는 경고만 — 실제 FinanceData/OpenDartReader 저장소 존재, CLAUDE.md CHOSEN. SLOP/SUS 아님.)

전 패키지 `[OK]`. 추가 checkpoint:human-verify 불필요.

## Architecture Patterns

### System Architecture Diagram

```
runner.run_all (ThreadPoolExecutor, max_workers=4)
  └─ per-ticker pipeline (process_ticker)
       │
       ├─ PASS 1: fetch_ohlcv_cached(symbol)  ──► OHLCV DataFrame  (기존, 변경 없음)
       │
       ├─ PASS 1b (신규): fetch_fundamentals(symbol, market)   ◄── try/except 흡수
       │      │                                                    (예외 → 빈 결과 + 사유, 티커 실패 아님)
       │      ├─ classify_market(symbol) ─► "US" | "KR"
       │      │
       │      ├─ market=="US":  EDGAR ──결손 metric만──► yfinance.info
       │      │        edgar_client.fetch(ticker)        yf_fundamentals.fetch(ticker)
       │      │             │ @throttled_edgar (8 RPS)         │ @throttled_yahoo (2 RPS)
       │      │             │ get_facts/get_financials         │ Ticker.info
       │      │             ▼                                   ▼
       │      │        [7d cache: (EDGAR, ticker, quarter)]  [7d cache: (yf, ...)]
       │      │
       │      └─ market=="KR":  DART ──결손──► Naver ──결손──► yfinance.info
       │               dart_client       naver_scraper      yf_fundamentals
       │               @throttled_dart   @throttled_? (보수적)
       │               (2 RPS)           httpx GET
       │
       │      ▼ 반환: FundamentalsResult{ PER:(v,src), PEG:(v,src), GPM:(v,src), OPM:(v,src) }
       │
       └─ _compute_enriched(...) ─► enriched_df  (기존)
              │
              ▼
       TickerResult(spec, enriched_df, market, fundamentals)  ◄── 필드 1개 추가
              │
              ▼
output/sheet_portfolio.write_portfolio_sheet
   └─ _write_success_row: col 0..16 (기존) + col 17 PER / 18 PEG / 19 GPM / 20 OPM
         각 셀: ws.write_number(num_format) + ws.write_comment(row,col, "<SRC> · <meta>" or "조회 실패: ...")
```

### Recommended Project Structure
```
src/stocksig/io/
├── cache.py            # 확장: _FUND_CACHE (7d TTL) + get_fund/put_fund
├── throttle.py         # 확장: @throttled_edgar (8 RPS) + @throttled_dart (2 RPS)
├── market_kind.py      # 재사용 (변경 없음)
├── edgar_client.py     # 신규: EDGAR raw facts → {EPS_TTM, EPS_prior, Revenue, GrossProfit, OpIncome}
├── dart_client.py      # 신규: DART finstate_all → 동일 raw dict (account_nm 매핑)
├── dart_account_map.py # 신규: account_nm 상수 (researcher 시드, executor 실데이터 확정)
├── naver_scraper.py    # 신규: finance.naver.com PER/PBR/EPS 스크래핑
├── yf_fundamentals.py  # 신규: Ticker.info → trailingPE/pegRatio/grossMargins/operatingMargins
└── fundamentals.py     # 신규: 폴백 라우팅 + provenance + PER/PEG/GPM/OPM 산출 (오케스트레이터)
src/stocksig/
├── runner.py           # 확장: TickerResult에 fundamentals 필드 + PASS 1b 호출
└── output/sheet_portfolio.py  # 확장: PORTFOLIO_COLUMNS +4, col 17~20 + write_comment
```
> 4개 client 분리 vs 단일 `fundamentals.py` 통합은 planner 재량. **권고: client는 분리(테스트 모킹 용이), 라우팅/산식/provenance는 `fundamentals.py` 단일.**

### Pattern 1: EDGAR (미국) — edgartools 5.x raw facts 취득
**What:** SEC identity 설정 후 Company facts에서 us-gaap concept를 DataFrame으로 꺼내 EPS_TTM / EPS_prior / Revenue / GrossProfit / OperatingIncome 산출.
**When to use:** `market == "US"`, 1차 소스.
```python
# Source: https://dgunning.github.io/edgartools/getting-xbrl/ (CITED) + PyPI 5.33.0 (VERIFIED)
# 주의: import 이름은 `edgar` (패키지명 edgartools 와 다름).
from edgar import Company, set_identity

# FUND-02: SEC UA 정책 — 프로세스당 1회 (모듈 import 시 또는 config 로드 직후).
set_identity("Yunjae Kim yunjerrard@gmail.com")   # "<Name> <email>" 형식 필수

company = Company("AAPL")

# (A) 표준 재무제표 경로 (라벨 기반):
fin = company.get_financials()              # 5.x: get_financials()
inc = fin.income_statement()                # 객체
inc_df = inc.to_dataframe()                 # 다기간 DataFrame

# (B) raw XBRL facts 경로 (concept tag 기반, 폴백·교차검증용):
facts = company.get_facts()
eps_df = facts.to_pandas("us-gaap:EarningsPerShareDiluted")   # 분기/연간 시계열
rev_df = facts.to_pandas("us-gaap:Revenues")

# (C) filing 단위 XBRL 쿼리 (특정 10-Q/10-K):
from edgar.xbrl import XBRL
filing = company.get_filings(form="10-Q").latest()
xbrl = XBRL.from_filing(filing)
gp = xbrl.facts.query().by_concept("GrossProfit").to_dataframe()
```
> **`[ASSUMED — executor 실데이터 검증 필수]`** (A)/(B)/(C) 중 어느 경로가 PER/PEG/GPM/OPM 4지표를 가장 안정적으로 채우는지, 그리고 메서드명(`get_financials` vs `financials` 속성, `get_facts` vs `facts`)이 5.33.0에서 정확한지 — AAPL/MSFT/GOOGL 3종으로 1회 호출해 확정. 5.x 문서가 두 패턴을 혼용 표기.

### Pattern 2: EPS_TTM 계산 (PER 분모)
**What:** 분기 EPS 합산 또는 연간 EPS로 TTM 산출.
```python
# 최근 4개 분기 EarningsPerShareDiluted 합 = TTM (분기 데이터가 충분할 때)
# 또는 최근 연간(10-K) EPS_diluted 사용 (분기 부족·노이즈 시 폴백)
# PER = 최신_종가 / EPS_TTM
#   최신_종가는 이미 Phase 1/2 enriched_df["Close"].iloc[-1] 에 존재 (EDGAR엔 주가 없음).
```
> **PER 분자(주가)는 EDGAR에 없다.** 이미 보유한 `res.enriched_df.iloc[-1]["Close"]`(시트1 col 4 "최신 종가")를 재사용. `fundamentals.py`가 `last_close`를 인자로 받아 PER 계산. `[VERIFIED: 코드 — sheet_portfolio col 4]`

### Pattern 3: PEG 산식 (D-disc-1 확정 권고)
**What:** CONTEXT 권장식 + 엣지 케이스.
```python
# PEG = PER / ((EPS_TTM / EPS_prior_year_TTM − 1) × 100)
#   EPS_prior_year_TTM = 1년 전 동일 시점 TTM (직전 4분기) 또는 직전 연간 EPS_diluted.
growth_pct = (eps_ttm / eps_prior - 1) * 100 if eps_prior not in (None, 0) else None
if growth_pct is None or growth_pct <= 0:
    peg = None                      # D-spec: "PEG 산출 불가: EPS 성장률 ≤ 0"
    peg_note = "조회 실패: EPS 성장률 ≤ 0" if growth_pct is not None else "조회 실패: 전년 EPS 미존재"
else:
    peg = per / growth_pct
```
> **권고 fallback 규칙:** ① `eps_prior is None` → "전년 EPS 미존재" ② `eps_prior == 0` → 0분모, "전년 EPS 0" ③ `growth_pct <= 0` → "EPS 성장률 ≤ 0" ④ `per is None` → PEG 불가(PER 없음). 모두 빈 셀 + 한국어 주석.

### Pattern 4: DART (한국) — OpenDartReader, stock_code 직접 수용
**What:** `.KS`/`.KQ` 제거 → 6자리 stock_code로 `finstate_all` 호출 → account_nm 매핑.
```python
# Source: https://github.com/FinanceData/OpenDartReader README (CITED)
import OpenDartReader
dart = OpenDartReader(api_key)            # config.load_env()["OPENDART_API_KEY"]

stock_code = ticker.split(".")[0]         # "005930.KS" → "005930"
# finstate_all 은 stock_code 직접 수용 — corp_code 내부 해석 (PITFALLS #3 수동매핑 부담 흡수)
df = dart.finstate_all(stock_code, 2025, reprt_code="11011", fs_div="CFS")
#   reprt_code: "11011"=사업보고서(연간), "11014"=3분기, "11012"=반기, "11013"=1분기
#   fs_div:     "CFS"=연결재무제표(권장, 그룹 대표), "OFS"=별도
# 반환 컬럼: account_nm, thstrm_amount(당기금액), sj_div(BS/IS/CIS...), fs_div, ...
```
**account_nm 매핑 (시드 — executor 실데이터 확정):**
| 지표 raw | 예상 account_nm (한글) | sj_div | 비고 |
|----------|------------------------|--------|------|
| 매출액 | `"매출액"` / `"수익(매출액)"` / `"영업수익"` | IS/CIS | 업종별 표기 상이 — 후보 리스트 필요 |
| 매출총이익 | `"매출총이익"` | IS | 금융업 등 미표기 가능 → 결손 시 폴백 |
| 영업이익 | `"영업이익"` / `"영업이익(손실)"` | IS | |
| 당기순이익 | `"당기순이익"` / `"당기순이익(손실)"` | IS/CIS | EPS 산출 또는 직접 EPS account |
| 주당순이익(EPS) | `"기본주당이익"` / `"기본주당순이익"` | IS | PER 분모. 단위 원. |
> **`[ASSUMED — executor 실데이터 검증 필수]`** 위 account_nm 정확 문자열·sj_div·fs_div 조합을 005930(삼성전자, 연결) 1회 호출로 확정 후 `dart_account_map.py` 상수화. `thstrm_amount`는 문자열(쉼표 포함) → `int(s.replace(",",""))` 파싱 필요.

**KR 지표 산출:**
```python
# GPM = 매출총이익 / 매출액   (0~1 비율 → 0.00% 포맷)
# OPM = 영업이익 / 매출액
# PER = 최신_종가(KRW, enriched_df Close) / 기본주당이익(KRW)
# PEG = Pattern 3 동일 (EPS_prior = 전년 사업보고서 기본주당이익)
```

### Pattern 5: yfinance .info 폴백 (양국 공통)
```python
# Source: yfinance Ticker.info (CITED — 키 이름 ASSUMED, executor 확인)
from stocksig.io.market import _SESSION   # curl_cffi 세션 재사용 (새 세션 만들지 말 것)
info = yf.Ticker(ticker, session=_SESSION).info
per = info.get("trailingPE")            # PER (TTM)
peg = info.get("pegRatio") or info.get("trailingPegRatio")  # PEG (키 변동 이력)
gpm = info.get("grossMargins")          # 0~1 비율
opm = info.get("operatingMargins")      # 0~1 비율
```
> **`[ASSUMED]`** yfinance `.info` 키 이름은 버전별 변동(`pegRatio` → 일부 버전 `trailingPegRatio`). `.info`는 rate-limited·stale 가능(PITFALLS Integration Gotchas). **per-metric 폴백 — 1차에서 채운 지표는 yf로 덮어쓰지 않는다.** `@throttled_yahoo`(기존 2 RPS) 통과.

### Pattern 6: Naver Finance 스크래핑 (KR D-04 2차)
```python
# Source: finance.naver.com/item/main.naver (training-knowledge structure — ASSUMED)
import httpx
from bs4 import BeautifulSoup
code = ticker.split(".")[0]
url = f"https://finance.naver.com/item/main.naver?code={code}"
r = httpx.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
r.encoding = "euc-kr"                    # 네이버 금융 = EUC-KR (UTF-8 가정 시 깨짐)
soup = BeautifulSoup(r.text, "lxml")
per = soup.select_one("#_per")           # <em id="_per"> 안 텍스트
pbr = soup.select_one("#_pbr")
eps = soup.select_one("#_eps")
```
> **`[ASSUMED — executor 실데이터 검증 필수]`** `#_per`/`#_pbr`/`#_eps` id는 네이버 금융 종목 메인의 전통적 구조이나 변경 가능. Naver는 GPM/OPM을 직접 노출하지 않음 → **Naver 폴백은 PER만 현실적**(GPM/OPM은 빈 셀). encoding EUC-KR 확정 필요. robots/rate: 폴백 전용(1차 결손 시만), 보수적 호출. 셀렉터 변경 시 D-disc-9 사유 `"Naver 페이지 변경"`.

### Anti-Patterns to Avoid
- **펀더멘털 결손 → 티커 실패 처리:** 금지. D-disc-10 — 시세 정상이면 시트 생성, 펀더멘털만 빈 셀. `fetch_fundamentals`는 절대 raise하지 않거나 호출부가 try/except로 전량 흡수.
- **결손에 0/-999999 채우기:** 금지(D-05). 평균/정렬 오염.
- **`set_identity()`를 per-call 호출:** 비효율·불필요. 프로세스당 1회. ThreadPool worker 안에서 매번 호출 금지.
- **EDGAR/DART를 ThreadPool로 고동시성 호출:** PITFALLS #2/#3 — throttle은 RPS 상한이지 동시성 허용이 아님. 기존 max_workers=4 + 토큰버킷으로 충분. EDGAR 403 시 15분 차단.
- **새 curl_cffi/httpx 세션 남발:** yf 폴백은 `io/market._SESSION` 재사용. (모듈 레벨 단일 인스턴스 규칙 — market.py 주석 명시.)
- **corp_code 수동 매핑 재구현:** 불필요. OpenDartReader가 stock_code 직접 수용.
- **`write_comment` 후 number format 손상:** 주석은 셀 값/포맷과 독립. `write_number(row,col,v,fmt)` 후 `write_comment(row,col,text)` 순서 — 포맷 유지됨.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ticker → corp_code 매핑 | corpCode.xml 다운로드·파싱·캐시 | `OpenDartReader.finstate_all(stock_code, ...)` 직접 호출 | 라이브러리가 내부 해석. PITFALLS #3 부담 제거. |
| XBRL 파싱 | data.sec.gov JSON 직접 파싱 | `edgartools` Company.get_facts/get_financials | typed + DataFrame. raw httpx는 FALLBACK ONLY. |
| EDGAR UA 헤더·CIK 룩업 | requests 세션에 UA 수동 설정 | `edgar.set_identity(...)` | 라이브러리가 정책 헤더·CIK·rate 처리. |
| 토큰버킷 | time.sleep 수동 throttle | 기존 `pyrate_limiter` (throttle.py 확장) | 4.1.0 설치됨. 재시도와 합성. |
| 7d 캐시 | dict + 타임스탬프 | 기존 `diskcache.Cache(expire=...)` | sqlite 백엔드, 프로세스 간 공유. |
| EUC-KR 디코딩 | 수동 바이트 변환 | `httpx` `r.encoding="euc-kr"` + bs4 | 검증된 경로. |

**Key insight:** Phase 3의 외부 데이터 복잡도(corp_code 3-ID 혼동, XBRL 태그 다양성, UA 정책)는 전부 1차 라이브러리가 흡수하도록 설계됐다. 직접 만들면 PITFALLS #2/#3의 silent-failure 함정에 그대로 빠진다.

## Common Pitfalls

### Pitfall 1: edgartools import 이름 혼동 + 버전 가정 stale
**What goes wrong:** `import edgartools` 시도 → ImportError. CLAUDE.md/CONTEXT "4.x" 핀으로 설치 후 5.x 문서 참조 시 메서드 불일치.
**Why:** 패키지명 `edgartools` ≠ import 이름 `edgar`. 최신은 5.33.0.
**How to avoid:** `from edgar import Company, set_identity`. 핀 `>=5,<6`. executor가 설치 직후 `import edgar; edgar.__version__` 확인.
**Warning signs:** ImportError; `get_financials` AttributeError(메서드명 5.x 확정 필요).

### Pitfall 2: SEC EDGAR 403 + 10분 IP 차단 (PITFALLS #2)
**What goes wrong:** UA 미설정/오설정 시 403, IP 10분 소프트 차단. 일부 래퍼가 403을 삼켜 None 반환 → 펀더멘털 silent 결손.
**Why:** SEC 정책 — `"<Name> <email>"` UA 필수. `Mozilla/5.0` 위장은 정책 위반.
**How to avoid:** `set_identity("Yunjae Kim yunjerrard@gmail.com")` 프로세스당 1회. 8 RPS throttle. 403 발견 시 EDGAR 트래픽 15분 정지. (FUND-06은 ≤8 RPS — PITFALLS는 10 RPS 하드캡 언급하나 **FUND-06 8 RPS가 locked**, 더 보수적이므로 안전.)
**Warning signs:** 첫 US 티커는 OK, 다음 99개 결손; 로그에 403.

### Pitfall 3: DART corp_code staleness + 일일 쿼터 (PITFALLS #3)
**What goes wrong:** OpenDartReader 내부 corp_code 캐시가 신규상장/사명변경 종목 미반영. 일일 쿼터(약 20,000/key) 초과 시 `{"status":"020"}` 에러.
**Why:** corp_code는 stock_code와 다른 식별자. 쿼터는 key당.
**How to avoid:** finstate_all 응답 `status` 필드 확인(`"000"`=정상, `"013"`=데이터없음, `"020"`=쿼터초과). 7d 캐시로 재호출 최소화. 쿼터 초과 시 한국어 사유 `"DART 쿼터 초과"` + Naver 폴백. 신규 종목 결손 시 사유 `"DART corp_code 매핑 실패"`.
**Warning signs:** KR만 결손, US 정상; 신규 IPO 종목만 실패.

### Pitfall 4: yfinance .info partial/stale + rate-limit (PITFALLS Integration)
**What goes wrong:** `.info`는 rate-limited·stale·키 변동(`pegRatio`/`trailingPegRatio`). 폴백 남용 시 yf 차단 전파(시세 fetch까지).
**How to avoid:** per-metric 폴백(1차에서 채운 건 건드리지 않음). `@throttled_yahoo` 통과. `.info` 호출도 7d 캐시. None-safe `.get()`.
**Warning signs:** PEG만 전부 결손(키 이름 변경); yf 차단이 시세까지 번짐.

### Pitfall 5: Naver 셀렉터/인코딩 깨짐
**What goes wrong:** UTF-8 가정 시 한글 깨짐; id 변경 시 None; GPM/OPM 미노출인데 기대.
**How to avoid:** `r.encoding="euc-kr"` 명시. `select_one` None 가드. Naver는 **PER만** 현실적 폴백. 셀렉터는 executor 실페이지 검증.
**Warning signs:** 깨진 텍스트; KR PER만 가끔 채워지고 나머지 결손.

### Pitfall 6: write_comment 성능/개수
**What goes wrong:** 200 티커 × 4셀 = 최대 800 주석. xlsxwriter 주석은 셀당 1개, 과다 시 파일 약간 비대.
**How to avoid:** 800 수준은 무해(시트1만, 종목별 시트 제외 D-06). 결손 셀도 주석 1개. constant_memory=False 유지(writer.py 기존).
**Warning signs:** 파일 비대(시트1에 수천 주석 — 발생 불가 규모).

## Code Examples

### FundamentalsResult 반환 형태 (provenance 포함, FUND-05/PORT-05)
```python
# 권고 데이터 모델 (executor 확정)
from dataclasses import dataclass, field

@dataclass
class MetricCell:
    value: float | None
    source: str | None     # "EDGAR"|"DART"|"yf"|"Naver"|None
    note: str | None       # "EDGAR · 2026Q3 10-Q" | "조회 실패: EPS 성장률 ≤ 0"

@dataclass
class FundamentalsResult:
    per: MetricCell
    peg: MetricCell
    gpm: MetricCell
    opm: MetricCell
```

### throttle.py 확장 (FUND-06)
```python
# 기존 pyrate_limiter 4.x 패턴 그대로 (throttle.py 4.1.0 확인)
_EDGAR_RATE = Rate(8, Duration.SECOND)
_edgar_limiter = Limiter(_EDGAR_RATE)
def throttled_edgar(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        _edgar_limiter.try_acquire("edgar")
        return fn(*a, **k)
    return wrapper

_DART_RATE = Rate(2, Duration.SECOND)
_dart_limiter = Limiter(_DART_RATE)
def throttled_dart(fn):
    @wraps(fn)
    def wrapper(*a, **k):
        _dart_limiter.try_acquire("dart")
        return fn(*a, **k)
    return wrapper
```

### cache.py 확장 (FUND-04)
```python
# 별도 인스턴스 + 7d TTL. 키 = "{SOURCE}|{TICKER}|{QUARTER}".
_FUND_DIR = Path(".cache/fundamentals")
_FUND_TTL_SECONDS = 7 * 24 * 60 * 60
_fund_cache: Optional[Cache] = None

def _get_fund_cache() -> Cache:
    global _fund_cache
    if _fund_cache is None:
        _FUND_DIR.mkdir(parents=True, exist_ok=True)
        _fund_cache = Cache(str(_FUND_DIR))
    return _fund_cache

def make_fund_key(source: str, ticker: str, quarter_label: str) -> str:
    return f"{source}|{ticker}|{quarter_label}"   # 예: "EDGAR|AAPL|2026Q3"

def get_fund(source, ticker, quarter_label):
    return _get_fund_cache().get(make_fund_key(source, ticker, quarter_label))

def put_fund(source, ticker, quarter_label, value):
    _get_fund_cache().set(make_fund_key(source, ticker, quarter_label), value,
                          expire=_FUND_TTL_SECONDS)
```
> **quarter_label 산출:** 최신 분기 라벨이 응답에 따라 달라짐. 권고: EDGAR는 latest filing의 period_of_report → `"2026Q3"`; DART는 reprt_code → `"2025-11011"`. 같은 분기 재실행은 무조건 HIT(D-disc-4).

### sheet_portfolio.py — col 17~20 + 주석 (PORT-05, D-01/D-02/D-05)
```python
# PORTFOLIO_COLUMNS 끝에 4개 추가 → 21열
PORTFOLIO_COLUMNS = [... , "(주)임펄스",  # index 16 (기존 끝)
                     "PER", "PEG", "GPM", "OPM"]   # index 17,18,19,20

def _write_fund_cell(ws, row, col, cell: MetricCell, num_fmt, formats):
    if cell.value is not None and not _nan(cell.value):
        ws.write_number(row, col, float(cell.value), formats[(SigmaBucket.DEFAULT, num_fmt)])
        if cell.source:
            ws.write_comment(row, col, cell.note or cell.source)
    else:
        ws.write_blank(row, col, None)                 # 빈 셀 (D-05)
        ws.write_comment(row, col, cell.note or "조회 실패")
    # ws.set_column 폭은 write_portfolio_sheet에서 0..20 일괄 14 → 자동 적용

# _write_success_row 끝(col 16 다음)에:
f = res.fundamentals
_write_fund_cell(ws, row, 17, f.per, "price",           formats)  # PER  #,##0.00
_write_fund_cell(ws, row, 18, f.peg, "price",           formats)  # PEG  #,##0.00
_write_fund_cell(ws, row, 19, f.gpm, "percent_ratio",   formats)  # GPM  0.00% (0~1 비율)
_write_fund_cell(ws, row, 20, f.opm, "percent_ratio",   formats)  # OPM  0.00% (0~1 비율)
```
> **포맷 매핑:** PER/PEG → `"price"`(`#,##0.00`); GPM/OPM → `"percent_ratio"`(`0.00%`, 저장값 0.0~1.0 비율 → Excel ×100). 기존 Format 캐시 재사용 — 신규 Format 0개 추가. **`ws.set_column(0, len-1, 14)`이 0..20 자동 적용**(PORTFOLIO_COLUMNS 길이로 계산). **`write_comment`는 셀 값/num_format와 독립** → 포맷 손상 없음. `freeze_panes(5,1)` 기존 라인 유지.

### runner.py 통합 (D-disc-10)
```python
@dataclass
class TickerResult:
    spec: TickerSpec
    enriched_df: pd.DataFrame
    market: str
    fundamentals: "FundamentalsResult | None" = None   # 신규 필드 (기본 None)

def process_ticker(spec, classify_market, pipeline, fundamentals_fn=None):
    market = classify_market(spec.symbol)
    df = pipeline(spec.symbol)                  # PASS 1 (기존)
    reason = _validate_row_count(spec.symbol, df)
    if reason is not None:
        raise ValueError(reason)                # 시세 결손 = 티커 실패 (기존)
    fund = None
    if fundamentals_fn is not None:
        try:
            last_close = df.iloc[-1].get("Close")
            fund = fundamentals_fn(spec.symbol, market, last_close)  # PASS 1b
        except Exception as e:                  # 펀더멘털 결손 ≠ 티커 실패 (D-disc-10)
            logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", spec.symbol, e)
            fund = None
    return TickerResult(spec=spec, enriched_df=df, market=market, fundamentals=fund)
```
> **하위호환:** `fundamentals_fn` 기본 None — Phase 1/2 테스트(3-인자 호출)는 그대로 통과. `sheet_portfolio._write_success_row`는 `res.fundamentals is None` 가드(전 셀 빈칸+주석 "펀더멘털 미수집"). Korean 로그: `[k/N] fund OK AAPL (EDGAR)` / `[k/N] fund FALLBACK 005930.KS (DART→Naver)` / `[k/N] fund MISS GOOGL`.

## Runtime State Inventory

> Phase 3은 rename/refactor가 아닌 기능 추가 phase. 단 외부 상태·캐시 영향이 있어 핵심 항목만 점검.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `.cache/ohlcv` (24h, 기존). 신규 `.cache/fundamentals` (7d) 추가 — 별 디렉터리. | 신규 디렉터리 생성(코드). 기존 OHLCV 캐시 무영향. |
| Live service config | 없음 — 외부 서비스 설정 변경 없음. EDGAR/DART는 stateless API. | None. |
| OS-registered state | 없음 — Task Scheduler 등 미사용. | None — verified by CLAUDE.md(수동 실행, v2 SCHED 보류). |
| Secrets/env vars | `.env`의 `EDGAR_USER_AGENT_EMAIL`, `OPENDART_API_KEY` — Phase 1에서 이미 `config.load_env`가 필수 검증. **이름 변경 없음.** | None(코드). 단 **실행 전 사용자가 OPENDART_API_KEY 실제 값을 채웠는지 확인** 필요(현재 fail-fast). |
| Build artifacts | `pyproject.toml` 의존성 4종 추가 → `uv lock`/`uv sync` 후 venv 갱신. | `uv add` 후 `uv sync`. 기존 egg-info/wheel 무영향(hatchling 빌드). |

## State of the Art

| Old Approach (CLAUDE.md/CONTEXT 가정) | Current (2026-06-02 확인) | Impact |
|---------------------------------------|---------------------------|--------|
| `edgartools>=4` | edgartools **5.33.0** 최신 (2026-05-29). import 이름 `edgar`. | 핀 `>=5,<6` 권장. 메서드명 5.x 실데이터 확정 필요. |
| `OpenDartReader>=0.2` | **0.3.2** 최신. stock_code 직접 수용 확인. | 0.3.x 사용. corp_code 수동 매핑 불필요. |
| corp_code 사전 다운로드(PITFALLS #3) | 라이브러리 내부 해석 | 부담 제거(잔존: 내부 캐시 staleness). |
| EDGAR 10 RPS 하드캡(PITFALLS) | FUND-06 locked **8 RPS** | 더 보수적 — 안전. |

**Deprecated/outdated:**
- CONTEXT D-08 `edgartools>=4` 하한: 만족하나 stale. 5.x 권장.
- PITFALLS의 "corpCode.xml 수동 다운로드/파싱" 권고: OpenDartReader 0.3.x에서는 불필요(라이브러리 흡수). 단 staleness 모니터링은 유효.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | edgartools 5.x 정확 메서드명 `get_financials()`/`get_facts()`/`facts.query().by_concept()` | Pattern 1 | API 호출 실패 → US 펀더멘털 전량 결손. executor가 AAPL 1회 호출로 확정. |
| A2 | EPS=`EarningsPerShareDiluted` 우선, GPM=`GrossProfit`, OPM=`OperatingIncomeLoss`, Rev=`Revenues`/`RevenueFromContractWithCustomerExcludingAssessedTax` | Pattern 1, 매핑표 | 일부 종목 결손/오값. 3 large-cap 교차검증 후 폴백 우선순위 확정. |
| A3 | DART account_nm 정확 문자열(매출액/매출총이익/영업이익/기본주당이익)·sj_div·fs_div="CFS" | Pattern 4 매핑표 | KR 지표 결손. 005930 실호출로 확정 후 상수화. |
| A4 | yfinance `.info` 키 `trailingPE`/`pegRatio`/`grossMargins`/`operatingMargins` | Pattern 5 | 폴백 결손. executor가 키 존재 확인(`pegRatio` vs `trailingPegRatio`). |
| A5 | Naver `#_per`/`#_pbr`/`#_eps`, EUC-KR, server-rendered 정적 HTML | Pattern 6 | KR PER 폴백 결손. 005930 실페이지 검증. Naver는 GPM/OPM 미노출 — 그 두 지표는 Naver 폴백 불가. |
| A6 | OpenDartReader `finstate_all`/`finstate`가 6자리 stock_code 직접 수용·corp_code 내부 해석 | Pattern 4 | corp_code 수동 매핑 필요해질 수 있음. README 근거(CITED)이나 0.3.2 실호출 확인 권장. |
| A7 | `quarter_label` 산출 방식(EDGAR period_of_report / DART reprt_code) | cache 확장 | 캐시 키 충돌/미스. executor가 실응답 필드로 확정. |

> A1~A7은 **본 sandbox에서 라이브러리 라이브 호출이 불가**(uv venv 미활성)하여 검증 못 함. planner는 Wave 0/초기 태스크에 "edgartools·OpenDartReader·Naver 실데이터 1회 검증 → 상수 확정" 스파이크를 배치할 것.

## Open Questions

1. **edgartools 5.x: financials 경로 vs facts 경로 — 어느 것이 4지표를 안정적으로 채우나?**
   - 알고 있음: 두 경로 모두 존재(`get_financials().income_statement().to_dataframe()` / `get_facts().to_pandas("us-gaap:...")`).
   - 불명: 5.33.0 정확 메서드 시그니처, 다기간(분기) 취득 최선 경로, TTM 4분기 합산 가능 여부.
   - 권고: executor가 AAPL/MSFT/GOOGL로 두 경로 모두 호출해 비교, 더 견고한 경로 채택. yfinance EPS와 교차검증.

2. **DART 연결(CFS) vs 별도(OFS), 분기 vs 연간 reprt_code 선택.**
   - 권고: 대표성 위해 CFS + 최신 가용 보고서. 분기 EPS 노이즈 시 연간(11011) 폴백. 005930로 확정.

3. **PEG의 EPS_prior 정의: 직전 4분기 TTM vs 직전 연간.**
   - 권고: 1차 = 1년 전 동일 TTM. 분기 부족 시 직전 연간 EPS_diluted. Pattern 3 fallback 규칙 적용.

4. **Naver로 GPM/OPM 폴백 불가 — KR에서 DART 결손 시 GPM/OPM은 yf로만, yf도 결손 시 빈 셀.**
   - 권고: D-04 체인에서 GPM/OPM은 사실상 DART→yf(Naver 건너뜀), PER은 DART→Naver→yf. metric별 체인 차등 — planner 명시.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| edgartools (`edgar`) | FUND-01/02 | ✗ (현재 venv 미설치) | 설치 대상 5.33.0 | raw data.sec.gov httpx (FALLBACK ONLY) |
| OpenDartReader | FUND-03 | ✗ | 0.3.2 | dart-fss (대안), Naver, yf |
| beautifulsoup4 + lxml | Naver 폴백 | ✗ | 4.14.3 / 6.1.1 | — (없으면 Naver 폴백 비활성, KR은 DART→yf) |
| httpx | Naver GET / EDGAR raw | edgartools 의존성으로 동반 설치 | 0.28.x | — |
| pyrate_limiter | FUND-06 throttle | ✓ (uv env) | **4.1.0** | — |
| diskcache | FUND-04 cache | ✓ | 5.6+ | — |
| yfinance + curl_cffi | yf 폴백 | ✓ | 0.2.66+ / 0.15.x | — |
| `.env` EDGAR_USER_AGENT_EMAIL | FUND-02 | (PROJECT.md 명시 `yunjerrard@gmail.com`) | — | 없으면 config fail-fast |
| `.env` OPENDART_API_KEY | FUND-03 | (사용자 보유, 실행 전 확인) | — | 없으면 config fail-fast |

**Missing dependencies with no fallback:** 없음 — 4종 모두 `uv add`로 설치 가능(slopcheck [OK]).
**Missing dependencies with fallback:** lxml 미설치 시 bs4 기본 파서(`html.parser`)로 대체 가능하나 lxml 권장.
**런타임 키:** `OPENDART_API_KEY` 실제 값이 `.env`에 채워졌는지 **실행 전 사용자 확인 필수**(현재 빈 값이면 `sys.exit(1)`).

## Validation Architecture

> nyquist_validation 설정 미확인 → 활성 가정(absent = enabled). pytest 8.x 기존 인프라 존재.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (+ pytest-mock, freezegun) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=tests, pythonpath=src) |
| Quick run command | `uv run pytest tests/test_fundamentals.py -x` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUND-01 | EDGAR facts → PER/PEG/GPM/OPM raw 산출 | unit (mock edgar) | `uv run pytest tests/test_edgar_client.py -x` | ❌ Wave 0 |
| FUND-02 | set_identity UA 형식 호출 | unit | `uv run pytest tests/test_edgar_client.py::test_set_identity -x` | ❌ Wave 0 |
| FUND-03 | DART finstate_all → account_nm 매핑 (stock_code 직접) | unit (mock dart) | `uv run pytest tests/test_dart_client.py -x` | ❌ Wave 0 |
| FUND-04 | 7d TTL 캐시 HIT/MISS, 키 포맷 | unit | `uv run pytest tests/test_cache.py::test_fund_cache -x` | ⚠️ test_cache.py 확장 |
| FUND-05 | 폴백 체인 + provenance 라벨 | unit | `uv run pytest tests/test_fundamentals.py::test_fallback_chain -x` | ❌ Wave 0 |
| FUND-06 | EDGAR 8/DART 2 RPS limiter | unit | `uv run pytest tests/test_throttle.py -x` | ⚠️ test_throttle.py 확장 |
| PORT-05 | 시트1 col 17~20 값+주석, 빈셀+주석 | unit (openpyxl readback) | `uv run pytest tests/test_sheet_portfolio.py::test_fund_cols -x` | ⚠️ 확장 |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_<module>.py -x`
- **Per wave merge:** `uv run pytest`
- **Phase gate:** 전 스위트 green + 실데이터 검증 스파이크(A1~A7) 완료 후 `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_edgar_client.py` — FUND-01/02 (edgar mock fixture)
- [ ] `tests/test_dart_client.py` — FUND-03 (OpenDartReader mock)
- [ ] `tests/test_naver_scraper.py` — KR PER 폴백 (정적 HTML fixture)
- [ ] `tests/test_yf_fundamentals.py` — `.info` 키 mock
- [ ] `tests/test_fundamentals.py` — 폴백 체인·provenance·PEG 엣지케이스(성장률≤0/0분모)
- [ ] `tests/test_cache.py` 확장 — `_FUND_CACHE` 7d
- [ ] `tests/test_throttle.py` 확장 — edgar/dart limiter
- [ ] `tests/test_sheet_portfolio.py` 확장 — 21열 + write_comment readback (openpyxl `ws.cell().comment`)
- [ ] **실데이터 스파이크**(테스트 아닌 1회 검증, A1~A7): AAPL/MSFT/GOOGL EDGAR, 005930 DART, 005930 Naver — 상수 확정 후 위 mock fixture 작성

## Security Domain

> security_enforcement 명시 false 아님 → 포함. 개인용 read-only 도구.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | 사용자 인증 없음(로컬 단일 사용자). |
| V3 Session Management | no | — |
| V4 Access Control | no | — |
| V5 Input Validation | yes | ticker → stock_code 파싱 시 `.split(".")[0]` 후 6자리/형식 검증. EDGAR/DART/Naver 응답 None-safe `.get()`. `thstrm_amount` 문자열 파싱 가드. |
| V6 Cryptography | no | 암호화 없음. |
| V7 Secrets | yes | `OPENDART_API_KEY`·UA email은 `.env`+python-dotenv(기존 config.py). 소스 하드코딩 금지. `.env` gitignore. 출력 .xlsx gitignore(개인 보유종목). |

### Known Threat Patterns for {Python 외부 API 클라이언트 + HTML 스크래핑}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API 키 git 유출 | Information Disclosure | `.env` + .gitignore (PITFALLS Security 표). 기존 준수. |
| Naver 응답 신뢰(파싱 주입) | Tampering | bs4 텍스트만 추출, `float()` 파싱 try/except. eval 금지. |
| EDGAR UA에 실이메일 → SEC 로그 노출 | Information Disclosure | 개인 도구 수용(PITFALLS 명시). 공개 repo에 .env 미커밋. |
| 결손값 0/특수값 오염 → 잘못된 신호 | (도메인 무결성) | D-05 빈 셀 + 주석. Core Value 보호. |
| DART 쿼터 소진(2번째 키 발급 = 정책 위반) | (가용성) | 단일 key, 7d 캐시, 쿼터 80% bail. PITFALLS #3. |

## Sources

### Primary (HIGH confidence)
- edgartools PyPI 5.33.0 (2026-05-29) — `pip index versions edgartools` (VERIFIED 버전·존재)
- edgartools docs — https://dgunning.github.io/edgartools/getting-xbrl/ (CITED — facts.query/to_pandas/XBRL.from_filing)
- OpenDartReader README — https://github.com/FinanceData/OpenDartReader (CITED — finstate/finstate_all stock_code 직접 수용, find_corp_code)
- OpenDartReader PyPI 0.3.2, beautifulsoup4 4.14.3, lxml 6.1.1 — `pip index versions` (VERIFIED)
- pyrate_limiter 4.1.0 — `uv run python -c "import pyrate_limiter"` (VERIFIED)
- slopcheck 0.6.1 — 4 패키지 전부 [OK]
- 코드: `io/cache.py`, `io/throttle.py`, `io/market_kind.py`, `io/market.py`, `runner.py`, `output/sheet_portfolio.py`, `output/writer.py`, `config.py`, `pyproject.toml` (VERIFIED — 직접 read)
- `.planning/research/PITFALLS.md` #2 (EDGAR UA/403), #3 (DART corp_code/쿼터) (CITED)

### Secondary (MEDIUM confidence)
- OpenDART 개발가이드 fnlttSinglAcntAll — fs_div CFS/OFS, reprt_code 11011 등 (WebSearch, 공식 도메인 교차)
- edgartools financial-data 가이드 — get_financials/income_statement (WebSearch, readthedocs)

### Tertiary (LOW confidence — 실데이터 검증 필요)
- Naver finance item/main `#_per`/`#_pbr`/`#_eps`, EUC-KR (training knowledge — A5)
- DART account_nm 정확 문자열 (A3)
- edgartools 5.x 정확 메서드 시그니처 (A1)
- yfinance .info 키 이름 (A4)

## Metadata

**Confidence breakdown:**
- Standard stack / 버전: HIGH — PyPI·slopcheck·런타임 직접 확인.
- 기존 코드 확장 패턴(throttle/cache/runner/sheet): HIGH — 소스 직접 read, API 표면 일치.
- edgartools API 경로: MEDIUM — 문서 CITED이나 5.x 정확 시그니처 라이브 미검증(A1).
- DART account_nm / Naver 셀렉터: MEDIUM-LOW — 실데이터 검증 필수(A3/A5).
- PEG/EPS_TTM 산식·엣지케이스: HIGH(산식) / MEDIUM(데이터 취득 경로).

**Research date:** 2026-06-02
**Valid until:** 2026-06-16 (edgartools 빠른 릴리스 cadence — 주 단위. 14일 후 버전 재확인 권장)
