# Phase 3: 기본적 분석 데이터 (EDGAR/DART/yfinance·Naver 보완) - Context

**Gathered:** 2026-05-27
**Status:** Ready for planning

<domain>
## Phase Boundary

미국 종목은 EDGAR(edgartools), 한국 종목은 DART(OpenDartReader)를 1차 소스로 사용해 **PER · PEG · GPM · OPM** 4개 기본적 분석 지표를 산출하고, 시트1 우측에 4셀로 표시한다. 각 셀의 값 출처는 Excel 셀 주석(comment)으로 표시. 결손 시 정의된 폴백 체인을 거치고, 모든 소스가 결손되면 빈 셀로 둔다. 캐시 7일 TTL + 토큰버킷(EDGAR ≤8 RPS, DART ≤2 RPS) 적용.

**In scope (이 phase가 다루는 것):**
- FUND-01 ~ FUND-06, PORT-05 (REQUIREMENTS.md 기준 총 7 requirements)
- 시트1 컬럼 17 → 21 확장 (R/S/T/U 추가)
- 신규 모듈: `io/edgar_client.py`, `io/dart_client.py`, `io/naver_scraper.py`, `io/yf_fundamentals.py` (또는 등가)
- 기존 모듈 확장: `io/cache.py` (7d TTL 모드), `io/throttle.py` (EDGAR/DART limiter), `runner.py` (펀더멘털 fetch 단계 통합), `output/sheet_portfolio.py` (R/S/T/U + 주석)
- `.env` 사전: `EDGAR_USER_AGENT_EMAIL=yunjerrard@gmail.com`, `OPENDART_API_KEY` 채워져 있어야 함

**Out of scope (다음 phase 또는 미루기):**
- "데이터 품질" 별도 시트 (Phase 4, EXEC-04)
- frozen panes 1~5행 (Phase 4, OUT-04)
- 종목별 시트의 펀더멘털 컬럼 (D-06: 시트1만 노출)
- 분기별 펀더멘털 시계열 (D-06: 최신 1개만)
- 펀더멘털 σ 색 신호 (PORT-05 요구는 "값 + 출처"만)

</domain>

<decisions>
## Implementation Decisions

### 시트1 컬럼 배치 + 출처 표시

- **D-01 (컬럼 위치):** PER/PEG/GPM/OPM 4셀을 시트1 **R/S/T/U** 에 추가 — (주)임펄스(Q) 직후 우측 끝. 시트1 총 컬럼 수 17 → **21열**. "시각 신호 그룹 → 펀더멘털 그룹" 분리가 명확.
- **D-02 (출처 표시 방식):** Excel 셀 주석(`xlsxwriter.write_comment`)으로 표시. 값 셀은 숫자만 (`#,##0.00` 또는 `0.00%` num_format 유지). 주석 형식: `"<SOURCE>"` 단순 라벨 또는 `"<SOURCE> · <짧은 메타>"` (예: `EDGAR · 2026Q3 10-Q`). 컬럼 수는 21로 고정, 가독성 손상 없음.

### 폴백 우선순위 + 결손 표시

- **D-03 (미국 폴백 체인):** **EDGAR → yfinance**. EDGAR에서 결손된 *개별 지표만* yfinance.info에서 보완. yfinance도 결손이면 빈 셀.
- **D-04 (한국 폴백 체인):** **DART → Naver Finance → yfinance**. DART에서 결손 시 Naver 금융 스크래핑(단 D-07 제약 준수 — PER만, 소수만), 그래도 결손 시 yfinance.info (.KS/.KQ 일부 지원). 모두 결손 시 빈 셀. ⚠️ yfinance 한국 펀더멘털은 대형주 PER 정도만 가끔 채워지고 PEG·중소형주는 결손이 잦음 — 보조 그물일 뿐 주력 아님. 한국 펀더멘털 신뢰도는 사실상 DART 1차에 달려 있음.
- **D-05 (결손 셀 표시):** 빈 셀 + 주석에 `"조회 실패: <이유>"` 기록 (예: `조회 실패: EDGAR concept tag 없음`, `조회 실패: 분기 데이터 미존재`). 0 또는 특수값(`-999999`) 비사용 — 평균/정렬 오염 위험.

### 네이버 사용 제약 (사용자 결정 2026-06-02)

- **D-07 (네이버는 소수 폴백 전용, 대량 사용 금지):** 네이버 금융은 공식 API가 없는 **HTML 스크래핑**이며 ToS·IP 차단 리스크가 상존한다. 따라서:
  - **용도 제한:** PER 단일 지표의 **DART 결손 폴백으로만** 사용. GPM/OPM/PEG에는 네이버를 절대 쓰지 않음(이미 D-04에서 GPM/OPM은 DART→yf 직행).
  - **호출량 상한:** 한 실행(run)당 네이버 스크래핑 호출 수를 **기본 20건으로 캡**(`NAVER_FALLBACK_CAP`, 설정 가능). 상한 초과분은 네이버를 **건너뛰고 yfinance로 직행**하며 사유 주석 `"Naver 대량 사용 제한(폴백 상한 초과)"`.
  - **격리·보수성:** 전용 보수적 호출 유지(현 2 RPS, 야후 버킷 공유). 429/403·빈 페이지(소프트 블록)는 **결손으로 안전 처리**(시세·실행 흐름에 전파 금지). 네이버 결과는 가능하면 7d 캐시로 재스크래핑 최소화.
  - **운영 원칙:** 만약 한 run에서 네이버 폴백이 캡에 도달할 정도로 빈번하다면 그것은 네이버 문제가 아니라 **DART 1차가 깨졌다는 신호** — 네이버 스크래핑을 늘리지 말고 DART 경로를 점검할 것.

### 종목별 시트 노출

- **D-06 (종목별 시트):** 변경 없음. 종목별 시트(97열, 시계열 전용) 그대로 유지. 펀더멘털은 **시트1에만 노출**. 종목 상세는 시트1의 하이퍼링크 → 종목 시트 흐름으로 충분. Phase 3 수행 부담 최소화.

### Claude's Discretion (research-phase/plan-phase에서 결정)

다음 항목은 사용자가 명시 지시하지 않았고, downstream 에이전트(researcher/planner)가 다음 기준으로 처리:

1. **PEG 산식:** 기본 채택 `PEG = PER / (EPS_TTM / EPS_prior_year_TTM − 1) × 100` (SUMMARY.md L241 권장). researcher가 EDGAR XBRL 실제 데이터로 검증 후 plan-phase에서 fallback 산식 정의 (예: 성장률 음수 시 N/A 처리).
2. **EDGAR XBRL concept tag 매핑:** PER용 EPS 후보 = `EarningsPerShareBasic` / `EarningsPerShareDiluted`. GPM용 = `GrossProfit` / `Revenues` (또는 `RevenueFromContractWithCustomerExcludingAssessedTax`). OPM용 = `OperatingIncomeLoss` / 같은 revenue. researcher가 3개 large-cap 종목으로 fallback 우선순위 정함.
3. **DART account_nm 매핑:** Samsung(005930.KS) 등 큰 회사로 시범 매핑 후 `dart_account_map.py` 상수화. researcher 책임.
4. **캐시 키:** `(ticker, quarter_label)` — 분기 단위 변동에 맞춤. 예: `("AAPL", "2026Q3")`. 7d TTL과 함께. 같은 분기 내 재실행은 무조건 HIT.
5. **토큰버킷 limiter:** 기존 `io/throttle.py` 패턴 확장. `@throttled_edgar` (8 RPS) + `@throttled_dart` (2 RPS) 데코레이터 추가.
6. **출처 라벨 표기:** 짧은 코드 `'EDGAR' / 'yf' / 'DART' / 'Naver'` 사용. 주석에 그대로 들어감.
7. **Naver scraping 구현:** `httpx` + BeautifulSoup4 (또는 lxml). 단순 페이지(`https://finance.naver.com/item/main.naver?code=005930`)에서 PER/PBR/등 파싱. 실패 시 fallback 정상 동작.
8. **신규 의존성:** `edgartools>=4`, `OpenDartReader>=0.2`, `beautifulsoup4>=4.12`, `lxml` (Naver용). `uv add` 적용. STACK.md 권장 그대로.
9. **실패 분류:** 한국어 사유 매핑 — `"EDGAR concept tag 없음"`, `"DART corp_code 매핑 실패"`, `"EDGAR rate-limit 초과"`, `"Naver 페이지 변경"`, `"분기 데이터 미존재"` 등.
10. **runner.py 통합:** 기존 per-ticker 파이프라인의 PASS 1에서 OHLCV fetch 직후 펀더멘털 fetch 추가. 펀더멘털 결손은 *티커 실패*가 아님 — 시세 데이터는 정상이면 시트 생성하고 펀더멘털만 빈 셀로 둠. (시세 결손과 펀더멘털 결손 분리 처리.)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 프로젝트 기준 문서
- `.planning/PROJECT.md` — Core Value, Constraints, Key Decisions (EDGAR UA email, DART API key 위치 등)
- `.planning/REQUIREMENTS.md` §FUND, §PORT-05 — 7개 Phase 3 requirements 전문 (FUND-01~06 + PORT-05)
- `.planning/ROADMAP.md` §"Phase 3" — Goal, Success Criteria, Dependencies

### 이전 phase 결정 (재사용)
- `.planning/phases/02-scaling-portfolio-summary/02-CONTEXT.md` — D-01 (입력 포맷), D-02 (단일 σ 진원지), D-03 (실패 행), D-04 (Yahoo throttle), D-05 (캐시 패턴), D-07 (uv add 패턴), D-08 (시트1 17열 baseline)

### 스택/패턴 권장
- `CLAUDE.md` §Technology Stack — edgartools 4.x, OpenDartReader 0.2.x 권장 + REJECTED 대안 (sec-api.io, pandas-ta 등)
- `.planning/research/STACK.md` §"EDGAR client", §"DART client" — 동등 내용 (의존성 결정 근거)
- `.planning/research/PITFALLS.md` §"DART/EDGAR" 관련 — corp_code 매핑·EDGAR User-Agent 정책 등 실패 패턴
- `.planning/research/SUMMARY.md` §D2, §"Open implementation-time questions" — 캐시 7d 권장, EDGAR XBRL tag 미정 항목

### 기존 코드 (확장 대상)
- `src/stocksig/io/cache.py` — 24h TTL diskcache → 7d 모드 추가
- `src/stocksig/io/throttle.py` — 2 RPS Yahoo limiter → EDGAR 8 RPS / DART 2 RPS 추가
- `src/stocksig/io/market_kind.py` — `classify_market()` 그대로 사용 (US/KR 라우팅)
- `src/stocksig/runner.py` — `run_all` per-ticker 파이프라인에 펀더멘털 fetch 통합
- `src/stocksig/output/sheet_portfolio.py` — 17열 → 21열 확장 + `write_comment` 출처 표시

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **`io/cache.py`**: diskcache sqlite 백엔드. 24h TTL 패턴 그대로. 새 인스턴스 `_FUND_CACHE`를 7d TTL로 만들거나 같은 cache에 다른 namespace 키 사용. 캐시 키 디자인은 `(source, ticker, quarter_label)` 권장.
- **`io/throttle.py`**: `@throttled_yahoo` 데코레이터. pyrate-limiter 4.x 패턴 그대로. 새 `@throttled_edgar` / `@throttled_dart` 추가.
- **`io/market_kind.classify_market(ticker) → "US"|"KR"`**: 라우팅 분기 그대로 사용. 미국은 edgar_client로, 한국은 dart_client로.
- **`runner.run_all + TickerFailure`**: 펀더멘털 결손은 `TickerFailure`가 아닌 *부분 누락*으로 처리. 시세 정상이면 시트 생성. 펀더멘털 fetch 자체 예외는 try/except로 흡수해 시세 처리 흐름 보호.
- **`output/writer.py`**: Format 캐시. PER/PEG는 `#,##0.00`, GPM/OPM은 `0.00%` (백분율). 기존 `price` / `percent_literal` / `percent_ratio` 중 적절히 선택.

### Established Patterns
- **단일 진원지(D-02 from Phase 2):** 색 결정은 `compute/color_rules`에서만. Phase 3은 색 신호 없음 → 영향 없음.
- **Korean logging:** `[k/N] OK <ticker>` 패턴. 펀더멘털 fetch 진행도 같은 형식으로 추가 가능 (선택). 예: `[k/N] fund OK AAPL (EDGAR)`, `[k/N] fund FALLBACK MSFT (EDGAR→yf)`, `[k/N] fund MISS GOOG`.
- **`.cache/` 디렉터리:** Phase 2 D-05에서 결정. 같은 위치 그대로 사용.

### Integration Points
- **`runner.run_all` 안의 per-ticker 파이프라인:** PASS 1 (현재: fetch_ohlcv_cached + _compute_enriched). 펀더멘털 fetch를 어디에 끼울지 — `_compute_enriched` 이전(병렬) 또는 이후(순차) 결정 필요. researcher 판단.
- **`output/sheet_portfolio._write_success_row`:** R/S/T/U 4셀 추가. `ws.write_comment(row, col, source_text)` 호출. 결손 시 `ws.write_blank` + 주석.
- **`config.py.load_env`:** `.env`에서 `EDGAR_USER_AGENT_EMAIL`, `OPENDART_API_KEY` 로드 — Phase 1에서 이미 구현. 없으면 한국어 에러로 종료. Phase 3 시작 전 사용자가 채웠는지 확인 필요.

</code_context>

<specifics>
## Specific Ideas

- **EDGAR User-Agent:** `"Yunjae Kim yunjerrard@gmail.com"` 형식 (SEC 정책 — 이름 + 이메일). `edgartools.set_identity()` 사용.
- **분기 라벨 형식:** `"2026Q3"` 같은 ISO 분기 표기. 캐시 키 + 주석 메타 양쪽에 활용.
- **PEG 음수 성장률 처리:** EPS 성장률 ≤ 0 → PEG 산출 불가 → 빈 셀 + 주석 `"PEG 산출 불가: EPS 성장률 ≤ 0"`.
- **사용자 본인 `.env`:** EDGAR_USER_AGENT_EMAIL은 PROJECT.md에 명시(`yunjerrard@gmail.com`), OPENDART_API_KEY는 사용자 보유. 실행 전 채워져 있어야 함.

</specifics>

<deferred>
## Deferred Ideas

- **"데이터 품질" 별도 시트:** Phase 4 (EXEC-04). 펀더멘털 결손 사유 집계를 한 시트에 정리. 현재 Phase 3은 셀 주석으로 개별 표시만.
- **펀더멘털 σ 색 신호:** PORT-05는 "값과 출처"만 요구 → 색 신호는 정의 없음. 추후 v2/ADV 슬롯에 PER 등에 대한 ±σ 색을 추가할 수 있음.
- **분기별 펀더멘털 시계열:** D-06에서 거부. 추후 ADV-03 ("다중 timeframe 신호") 슬롯과 묶을 수 있음.
- **`pandas-ta` 미사용 유지:** Phase 1/2와 동일 — pandas.ewm만 사용. Phase 3은 추가 지표 라이브러리 도입 안 함.
- **edgartools "Companies" API로 종목 메타데이터 확장 (시장가치, 발행주식수 등):** PORT-05는 PER/PEG/GPM/OPM 4개만. 메타 확장은 별도 phase / backlog.
- **API 키 / UA email 자동 검증:** 시작 시 EDGAR ping + DART /list.json ping으로 인증 살아있는지 확인. 깔끔하지만 Phase 3 핵심 기능 아님 — Phase 4에 묶을 수 있음.

### Reviewed Todos (not folded)
없음 — `gsd-sdk query todo.match-phase 3` 매치 0건.

</deferred>

---

*Phase: 3-edgar-dart-yfinance-naver*
*Context gathered: 2026-05-27*
