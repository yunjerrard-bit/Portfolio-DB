# Phase 3 실데이터 검증 스파이크 결과 (A1~A7)

**실행:** 2026-06-04 (03-02 Task 1)
**환경:** uv 0.11.15, edgartools **5.35.0**, OpenDartReader 0.3.x, beautifulsoup4 4.14.3, lxml, yfinance 0.2.66+
**호출 대상:** EDGAR=AAPL/MSFT/GOOGL · DART=005930(삼성전자, 2025 사업보고서 연결) · Naver=005930 · yfinance=AAPL·005930.KS
**전제:** Task 0 체크포인트(.env 키 + 네트워크) 오케스트레이터 사전 승인. EDGAR/DART/Naver/yfinance 전부 라이브 호출 성공.

> 비밀 취급(T-03-03): OPENDART_API_KEY·UA 이메일 평문 미기록. 본 문서·fixture·로그에 키 0건 노출.

---

## 확정 요약표 (A1~A7)

| # | 항목 | 확정값 | 상태 | 출처 |
|---|------|--------|------|------|
| A1 | edgartools 5.x facts 취득 경로 | `Company(tk).get_facts()` → `EntityFacts` 타입드 접근자 (`get_revenue/get_gross_profit/get_operating_income/get_net_income/get_ttm_revenue/get_ttm_net_income/get_ttm(concept)`). **`facts.to_pandas()` 는 5.35.0에 부재.** | **[VERIFIED]** | AAPL/MSFT/GOOGL |
| A2 | XBRL concept / 지표 매핑 | EPS=`get_ttm("EarningsPerShareDiluted")`(=us-gaap:EarningsPerShareDiluted), Revenue=`get_ttm_revenue()`(=RevenueFromContractWithCustomerExcludingAssessedTax), GrossProfit=`get_gross_profit()`, OpIncome=`get_operating_income()`. **GOOGL get_gross_profit()=None → GPM 결손 케이스 존재.** | **[VERIFIED]** | AAPL/MSFT/GOOGL |
| A3 | DART account_nm/account_id·sj_div·fs_div | 매핑 1차키=`account_id`(표준태그), 2차키=`account_nm`(한글). 005930: 매출액=ifrs-full_Revenue, 매출총이익=ifrs-full_GrossProfit, 영업이익=dart_OperatingIncomeLoss, 당기순이익=ifrs-full_ProfitLoss, 기본주당이익=ifrs-full_BasicEarningsLossPerShare. sj_div="IS"(손익)/"CIS"(포괄). fs_div 는 **요청 파라미터**(응답 컬럼은 None). | **[VERIFIED]** | 005930 |
| A4 | yfinance .info 키 | US(AAPL): trailingPE/pegRatio/trailingPegRatio/grossMargins/operatingMargins 전부 존재. KR(005930.KS): **trailingPE=None(결손)**, forwardPE/pegRatio/grossMargins/operatingMargins 존재. PEG=`pegRatio` 우선·`trailingPegRatio` 폴백. | **[VERIFIED]** | AAPL·005930.KS |
| A5 | Naver 셀렉터·인코딩 | `#_per`=28.94, `#_eps`=12,372(쉼표→strip), `#_pbr`=4.98. **인코딩=UTF-8** (RESEARCH의 euc-kr 가정 폐기 — charset=utf-8, euc-kr/cp949 디코드 시 에러). GPM/OPM 미노출 → KR 폴백은 PER만. | **[VERIFIED]** | 005930 |
| A6 | OpenDartReader stock_code 직접 수용 | `finstate_all("005930", 2025, reprt_code="11011", fs_div="CFS")` 6자리 stock_code 직접 수용, corp_code(00126380) 내부 해석. 229행 반환. | **[VERIFIED]** | 005930 |
| A7 | quarter_label 산출 | EDGAR: `TTMMetric.periods[-1]`=(2026,"Q2") → `"2026Q2"`, 또는 `available_periods()` 최상단 `"2026-Q2"`, latest 10-Q period_of_report=2026-03-28. DART: `bsns_year`+`reprt_code` → `"2025-11011"`. | **[VERIFIED]** | AAPL·005930 |

---

## A1 — edgartools 5.x facts 경로 (메서드 시그니처)

**확정:** `Company(ticker).get_facts()` → `EntityFacts` 객체. RESEARCH Pattern 1의 세 경로 중:

- **(A) `get_financials().income_statement().to_dataframe()`** — 존재하고 동작(shape ~47×19). 단 반환 DataFrame의 `concept` 컬럼이 기대 us-gaap 태그와 직접 매칭 안 됨(라벨/계층 위주) → 4지표 추출엔 부적합.
- **(B) `get_facts().to_pandas("us-gaap:...")`** — **부재.** `EntityFacts` 에 `to_pandas` 속성 없음(AttributeError, 3종목 전부). RESEARCH A1 가정 **반증.**
- **(C) `XBRL.from_filing(...).facts.query()`** — 미사용(아래 타입드 접근자가 더 견고).

**채택 경로:** `EntityFacts` 타입드 접근자 (5.35.0 `dir(EntityFacts)` 로 발견):
```
facts = Company(tk).get_facts()
facts.get_revenue()           -> float  (최신 연간)
facts.get_gross_profit()      -> float | None
facts.get_operating_income()  -> float
facts.get_net_income()        -> float
facts.get_ttm_revenue()       -> TTMMetric(concept, value, periods, as_of_date, has_gaps, ...)
facts.get_ttm_net_income()    -> TTMMetric
facts.get_ttm("EarningsPerShareDiluted") -> TTMMetric(value=8.07)   # EPS_TTM
facts.available_periods()     -> PeriodSummary
```
`TTMMetric` 공개 attr: `value, concept, as_of_date, periods(list[(year,"Qn")]), has_calculated_q4, has_gaps, label, period_facts, unit, warning`.

**실측값(AAPL FY2025):** revenue=416,161,000,000 / gross_profit=195,201,000,000 / op_income=133,050,000,000 / net_income=112,010,000,000 / EPS_TTM(diluted)=8.07 / TTM revenue=451,442,000,000.

## A2 — concept tag 우선순위 + 결손

- EPS: `get_ttm("EarningsPerShareDiluted")` 정상(AAPL 8.07, MSFT 17, GOOGL 13 — 정수 표시는 repr 반올림, 실 .value는 float). `get_concept("EarningsPerShareDiluted")`/`get_fact(...)` 는 **bare name 미인식**(경고: 정식 태그 `us-gaap:EarningsPerShareDiluted`) → 반드시 `get_ttm(...)` 사용.
- Revenue: `get_ttm_revenue()` 의 concept = `RevenueFromContractWithCustomerExcludingAssessedTax`(3종목 공통). **`get_ttm("Revenues")` 는 stale 기간(FY2010/2018) 선택 → 사용 금지.**
- GrossProfit: AAPL/MSFT 정상, **GOOGL `get_gross_profit()`=None** → GPM은 yf 폴백 필요(D-03). 결손 케이스 확인됨.
- OperatingIncome/NetIncome: 3종목 전부 정상.

## A3/A6 — DART (005930, 2025 사업보고서 연결)

**A6:** `finstate_all("005930", 2025, reprt_code="11011", fs_div="CFS")` → 6자리 stock_code 직접 수용, 내부 corp_code=00126380 해석, **229행** 반환. 수동 corp_code 매핑 불필요 확인.

**A3 매핑(account_id 1차 / account_nm 2차):**

| 지표 | account_id | account_nm | sj_div | thstrm_amount (2025, KRW) |
|------|------------|-----------|--------|---------------------------|
| revenue | `ifrs-full_Revenue` | 매출액 | IS | 333,605,938,000,000 |
| gross_profit | `ifrs-full_GrossProfit` | 매출총이익 | IS | 131,370,425,000,000 |
| op_income | `dart_OperatingIncomeLoss` | 영업이익 | IS | 43,601,051,000,000 |
| net_income | `ifrs-full_ProfitLoss` | 당기순이익 | IS/CIS | 45,206,805,000,000 |
| eps | `ifrs-full_BasicEarningsLossPerShare` | 기본주당이익 | IS | 6,605 (원) |

추가 확정:
- 반환 컬럼 18종: rcept_no, reprt_code, bsns_year, corp_code, sj_div, sj_nm, account_id, account_nm, account_detail, thstrm_nm, thstrm_amount, frmtrm_nm, frmtrm_amount, bfefrmtrm_nm, bfefrmtrm_amount, ord, currency, thstrm_add_amount.
- `fs_div` 컬럼은 응답에서 채워지지 않음(None) — fs_div("CFS"/"OFS")는 **요청 파라미터**일 뿐 응답 식별에 못 씀. 연결/별도 구분은 호출 파라미터로 통제.
- `thstrm_amount` = 쉼표 없는 digit 문자열("333605938000000"). 단 RESEARCH 경고대로 일부 항목/응답은 쉼표 포함 가능 → dart_client는 **항상 `.replace(",", "")` 후 int**.
- `frmtrm_amount`(전기) 동시 제공 → PEG의 EPS_prior(전년 기본주당이익=4,950) 산출 가능.
- **매핑은 account_id 우선:** account_nm은 회사 재량 한글 라벨이라 업종 간 변동, account_id는 IFRS/DART 표준 태그라 안정적. (T-03-04 가드: 텍스트만 추출, 파싱 try/except.)

## A4 — yfinance .info

| 키 | AAPL(US) | 005930.KS(KR) |
|----|----------|----------------|
| trailingPE | 37.607 | **None (결손)** |
| forwardPE | 32.292 | 6.416 |
| pegRatio | 2.53 | 0.20 |
| trailingPegRatio | 2.5336 | 0.1996 |
| grossMargins | 0.4786 | 0.4768 |
| operatingMargins | 0.3228 | 0.4275 |

- KR `.info` 부분지원: trailingPE 결손이나 GPM/OPM/PEG는 존재 → D-04 체인 최후 폴백으로 유효. KR PER은 DART→Naver 우선(yf trailingPE 결손이므로).
- PEG는 `pegRatio` 우선, 부재 시 `trailingPegRatio`. 두 키 모두 존재 확인.
- grossMargins/operatingMargins는 0~1 비율 → 시트 `0.00%` 포맷(저장값 ×100).
- 세션: `market._SESSION`(curl_cffi) 재사용. 신규 세션 미생성.

## A5 — Naver finance (005930)

- **인코딩 정정(deviation Rule 1):** 페이지가 `charset=utf-8` 선언, euc-kr/cp949 디코드 시 `UnicodeDecodeError`. RESEARCH A5의 `r.encoding="euc-kr"` 가정 **반증** → naver_scraper는 `r.content.decode("utf-8")`(또는 httpx 기본 charset 신뢰).
- 셀렉터: `#_per`=28.94, `#_eps`=12,372(쉼표 포함 → `float(t.replace(",",""))`), `#_pbr`=4.98, `#_cns_per`=8.00, `#_dvr`=0.47. `select_one(...).get_text(strip=True)`.
- Naver는 **GPM/OPM 미노출** → KR에서 Naver 폴백은 PER만 현실적(GPM/OPM은 DART→yf).
- status 200, server-rendered 정적 HTML(headless 불필요 — A 가정 확인).

## A7 — quarter_label 산출

- **EDGAR:** `TTMMetric.periods` 의 가장 최근 `(year, "Qn")` → `f"{year}{q}"` = `"2026Q2"`. 보조: `available_periods()` 최상단 라벨 `"2026-Q2"`, latest 10-Q `period_of_report=2026-03-28`. `as_of_date`도 동일 분기 가리킴.
- **DART:** `bsns_year`("2025") + `reprt_code`("11011") → 캐시 키 `"2025-11011"`. reprt_code 11011=연간/11014=3Q/11012=반기/11013=1Q.
- 같은 분기 재실행 시 캐시 무조건 HIT(D-disc-4) — 라벨이 분기 단위로 안정.

---

## 산출물

- `src/stocksig/io/dart_account_map.py` — `DART_ACCOUNT_ID_MAP`(1차) + `DART_ACCOUNT_MAP`(2차, 한글) + `SJ_DIV_INCOME_STATEMENT`. [VERIFIED 005930]
- `tests/fixtures/edgar_aapl_facts.py` — `FakeTTMMetric`, AAPL 연간/TTM 값, `quarter_label_from_periods`, GOOGL GPM 결손 케이스.
- `tests/fixtures/dart_005930_finstate.py` — `COLUMNS`, `IS_CIS_ROWS`(9행), `EXPECTED_VALUES`, account_id/account_nm 정확 문자열.
- `tests/fixtures/naver_005930.html` — UTF-8 PER/EPS 표 발췌(#_per/#_eps 파싱 검증됨).
- `tests/fixtures/yf_info_sample.py` — `AAPL_INFO`, `SAMSUNG_INFO`(trailingPE None), `YF_KEY_MAP`.

## RESEARCH 대비 정정 사항 (Wave 3/4 반영 필수)

1. **A1:** `facts.to_pandas("us-gaap:...")` 부재. → `EntityFacts.get_revenue/get_gross_profit/get_operating_income/get_net_income/get_ttm_revenue/get_ttm_net_income/get_ttm(eps)` 사용.
2. **A2:** Revenue는 `get_ttm("Revenues")`(stale) 금지 → `get_ttm_revenue()`. EPS는 `get_concept`/`get_fact` bare name 미인식 → `get_ttm("EarningsPerShareDiluted")`.
3. **A5:** Naver 인코딩 **UTF-8**(euc-kr 아님). naver_scraper 인코딩 라인 정정 필수.
4. **A2/A4:** GPM 결손(GOOGL get_gross_profit=None, KR DART 미표기 가능) → D-03/D-04 폴백 체인에서 GPM은 yf grossMargins 보완.
5. **A3:** 매핑 1차키는 account_nm이 아닌 **account_id**(표준태그). account_nm은 2차 폴백.

## [UNVERIFIED] / 미확정

- 없음. A1~A7 전부 라이브 호출로 확정([VERIFIED]). follow-up 재검증 불필요.
- 잔존 리스크(코드화 시 가드): ① 업종별 account_nm/account_id 변동(2차 매핑·yf 폴백으로 흡수) ② OpenDartReader corp_code 내부 캐시 staleness(신규상장 종목) ③ Naver/yfinance 페이지·키 변경(7d 캐시 + None-safe `.get()`).
