---
gsd_state_version: 1.0
milestone: v1.3
milestone_name: 펀더멘털 히스토리 & 델타 추출
status: completed
last_updated: "2026-06-23T07:50:36.338Z"
last_activity: 2026-06-23 -- Phase 10 marked complete
progress:
  total_phases: 6
  completed_phases: 6
  total_plans: 16
  completed_plans: 16
  percent: 100
---

# STATE: 표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트

**Last updated:** 2026-07-02

## Project Reference

- **Core Value:** 중앙값 ± 표준편차를 기준으로 한 색상 신호가 통합 포트폴리오 시트에서 정확하고 직관적으로 보여야 한다.
- **Mode:** Vertical MVP
- **Granularity:** standard
- **Current focus:** Phase 10 — 1-store-registry

## Current Position

Phase: 10 — COMPLETE
Plan: 3 of 3 (완료)
Status: Phase 10 complete
Last activity: 2026-07-02 -- Completed quick task 260702-nrs: 펀더멘털 트렌드 엑셀 전 탭 헤더행 freeze + ROE/ROA 퍼센트 표기

## Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260617-ijf | WR-01 펀더멘털 NaN 가드 — `_is_missing(None/NaN)` 게이트로 NaN PER/PEG/GPM/OPM 시트 기록 차단 | 2026-06-17 | 222a37b | [260617-ijf-wr-01-nan-is-missing-none-nan-per-peg-gp](./quick/260617-ijf-wr-01-nan-is-missing-none-nan-per-peg-gp/) |
| 260617-k34 | WR-02~06 안정성 — auth ping 재시도+401/403 한정+구조적 403(IN-02 F841), 캐시 싱글톤 double-checked lock, freeze/smoke 테스트 네트워크 0 stub | 2026-06-17 | ddff54b | [260617-k34-wr-02-06-ping-401-403-403-lock-freeze-sm](./quick/260617-k34-wr-02-06-ping-401-403-403-lock-freeze-sm/) |
| 260627-vpn | 트렌드 렌더 FY-라벨 버그 — `_calendar_quarter_key` YYYYQn fullmatch 가드(아니면 None, docstring 계약 일치) + `raw_facts` FY-라벨 오염행 6건 삭제. CRDO/LEU/NKE/SIRI/TTWO 트렌드 ValueError 해소(362 passed) | 2026-06-27 | 51f044a | [260627-vpn-fix-trend-fy-label-quarter-key-guard-plu](./quick/260627-vpn-fix-trend-fy-label-quarter-key-guard-plu/) |
| 260629-hec | edgartools 5.35.0 `by_period_type` 마이그레이션 — duration/instant 폐기 ValidationError 가 `_query_facts` 조용한 except 에 삼켜져 US 전 결손이던 버그 수정(quarterly + 파이썬 instant 필터 + period_end 분기키 + WARNING 로깅 + filing_date 정렬). delta_state EDGAR 정리 후 US 125종목 재적재 → 105종목 분기×9필드 회복(368 passed, 시트1 0줄). 후속: EDGAR Q4 갭 별개 인계(edgar-q4-gap-ttm-none.md) | 2026-06-29 | 6586935 | [260629-hec-edgartools-5-35-0-by-period-type-migrati](./quick/260629-hec-edgartools-5-35-0-by-period-type-migrati/) |
| 260702-nrs | 펀더멘털 트렌드 엑셀 표시 수정 — 전 탭 헤더행(1행) freeze(지표·스냅샷 `freeze_panes(1,1)`=B2, 원천 `freeze_panes(1,0)`=A2) + ROE/ROA display 층 `_PERCENT_METRICS` 퍼센트 표기(레지스트리 `is_ratio_0_1` 불변). AAPL ROE 115.1%는 자사주 매입발 정상값 검증(수정 없음). 25 passed | 2026-07-02 | 2561b6d | [260702-nrs-fund-roe-roa-pct-header-freeze](./quick/260702-nrs-fund-roe-roa-pct-header-freeze/) |

## Performance Metrics

| Metric | Value |
|--------|-------|
| Phases planned (v1.3) | 4 |
| Phases complete (v1.3) | 0 |
| v1.3 requirements | 5 (FUND-07~11) |
| Requirements mapped | 5 (100%) |
| Requirements shipped | 0 |
| Phase 07 P02 | ~20 min | 3 tasks | 7 files |
| Phase 07 P03 | ~9 min | 2 tasks | 2 files |
| Phase 07 P04 | ~13 min | 3 tasks | 3 files |
| Phase 08 P02 | ~10 min | 1 task | 2 files |
| Phase 08 P03 | ~15 min | 2 tasks | 2 files |
| Phase 08 P04 | 18 min | 2 tasks | 3 files |
| Phase 09 P01 | ~12 min | 3 tasks | 5 files |
| Phase 09 P02 | ~18 min | 3 tasks | 5 files |
| Phase 10 P01 | ~27 min | 2 tasks | 6 files |
| Phase 10 P03 | 50min | 2 tasks | 13 files |

## Accumulated Context

### v1.3 기술 컨텍스트 (로드맵 — phase discuss/plan 입력)

- **의존 fetch 층 (Phase 3, 존재 확인):** `src/stocksig/io/edgar_client.py`, `dart_client.py`, `fundamentals.py`, `yf_fundamentals.py`, `naver_scraper.py`, `dart_account_map.py`(account_id 1차/account_nm 2차 — 지표 registry 소스별 매핑 시작점).
- **신규 저장소:** `data/fundamentals.db` (SQLite, `.gitignore`, TTL 없음, 기존 `.cache/` OHLCV 7일 TTL과 별개). raw long 테이블 `(ticker, source, quarter, accession_or_rcept, field, value, fetched_at)` + state 테이블 `(ticker, source, last_accession, last_checked_at)`.
- **델타 키:** EDGAR accession number / DART rcept_no. 가벼운 조회 = DART `list` API / EDGAR 메타. 같으면 전체호출 생략(평소 ≈0), 다르면 새 분기 또는 정정공시 → 전체 facts 재추출·누적.
- **지표 유형:** 저량(최근 분기값) / 유량(TTM 4분기 합) / 하이브리드(분자 TTM ÷ 분모 최근값). 최종 지표가 아닌 분기별 원천 raw 누적 → 신규 지표 무재호출 계산.
- **렌더 산출물:** `fundamentals_history.xlsx`(별도 파일, 매 실행 DB에서 렌더). 지표별 시트(행=종목·열=분기) + `[원천]` + `[최신 스냅샷]`. 과거 PER/PBR=분기말 종가, 최신 열만 현재가.
- **불변(Core Value 보호):** 시트1 `portfolio_YYYYMMDD.xlsx` 레이아웃·색 신호 — 절대 변경 금지. 히스토리는 완전 분리.
- **구현 디테일 메모(discuss-phase에서 확정):** EDGAR Q4=FY−9M 보정, DART YTD 누적→분기 분해(thisQ−직전Q), TTM 결손 분기 = 빈값+사유(0 금지, D-05 일관), 서식·파일 분리/덮어쓰기 정책.
- **권위 입력:** `.planning/backlog/fundamentals-history-delta.md` (D-H1~D-H4 locked).

### Decisions (locked, from PROJECT.md / backlog)

- 델타 감지 키 = 접수번호(EDGAR accession / DART rcept_no) — 분기 라벨만으로는 정정공시 누락 (D-H1).
- 저장 = 최종 지표가 아닌 분기별 원천 raw 누적 → 신규 지표 무재호출 계산 (D-H2).
- 저장소 = SQLite `data/fundamentals.db` (raw + state), JSONL/Parquet 기각 (D-H3).
- 사람용 출력 = 별도 `fundamentals_history.xlsx`, 시트1 불변 (D-H4).
- 가격 의존 지표 과거 열 = 분기말 종가 고정, 최신만 현재가 (트렌드 일관성, raw 저장으로 추후 변경 가능).
- xlsx writer = XlsxWriter (정적 색 베이킹, 인플레이스 미사용).
- **Plan 07-01 구현**: `fundamentals_store.py` raw_facts PK `(ticker,source,quarter,field)` — D-09 정정공시 `ON CONFLICT DO UPDATE` 최신값 덮어쓰기(이력 미보존), TTL/expire 컬럼 없음(D-H3), 결손=NULL(D-05), 전 SQL `?` 바인딩(ASVS V5). WAL + `_store_lock` write 직렬화 (commit 898bf3f, FUND-07 ✓).
- **Plan 07-02 구현**: per-quarter raw 추출기 — `fetch_edgar_quarterly_raw`(get_facts 1회 공짜 backfill, D-01)·`fetch_dart_quarterly_raw`(years=3 finstate_all 루프 차등, D-01). EDGAR duration(손익·CF)/instant(BS) query 분리·DART SJ_DIV_BALANCE_SHEET/CASHFLOW 필터(D-04), 캘린더 분기키 "YYYYQn"(D-08), 결손=None(D-05), OpenDartReader `_dart_singleton` double-checked lock(Pitfall 1, 07-03 공유). 시트1 TTM 경로(`fetch_edgar_raw`/`fetch_dart_raw`) 불변(D-06). dart_account_map BS/CF/shares 매핑+SJ_DIV 상수 additive. 전 스위트 297 passed(회귀 0). commits 9ff6a93/de9fa7f/0437640.
- **Plan 07-03 구현**: `fundamentals_delta.sync_ticker_history` — probe(EDGAR `Company.latest("10-Q").accession_number` / DART `list(kind="A").iloc[0]["rcept_no"]`) → `get_last_accession` 비교 → 같으면 `mark_delta_hit`·SKIP(full-fetch·신규 저장 0, SC3) / 다르면 `mark_delta_miss`·재추출·upsert·`set_last_accession`(forward 누적, D-02/SC4). probe·fetch 실패 안전 흡수(기존 DB 유지, Pitfall 2/T-07-07), DART `_get_dart()` 싱글톤 공유 import(Pitfall 1/T-07-09), 예외 로그 `type(exc).__name__` 만(T-07-08). dict 11key→12-tuple(+fetched_at) 변환. FUND-08 ✓, 전 스위트 303 passed(회귀 0). commits 1c6966d/bfc8837.
- **Plan 07-04 구현**: `main_run.run()` 히스토리 경로 배선 — PASS1/PASS2 시트1 경로(D-06 불변) 이후·요약 직전에 **별도 순차 루프**(D-07)로 종목별 `sync_ticker_history(US→EDGAR / KR→DART)` 호출, 종목별 try/except 로 시트1 산출물 보호(T-07-11). run 시작부 `fund_store.reset_delta_stats()`(cache.reset 옆), 요약 블록에 "히스토리: 델타 HIT/MISS · full-fetch" 줄(정수만, T-04-01). `.gitignore` `data/`(SC5, T-07-13). 인증 실패 소스·US/KR 외 폴백 종목 skip. 통합 5종(SC1 누적/SC3 full-fetch 0/D-07 시트1 on·off 셀 불변/SC5 .cache/ 불변/T-07-11 실패 격리) GREEN, 전 스위트 308 passed(회귀 0). FUND-07/08 ✓. commits 971e544/42336e6/fce2e79.
- **Plan 08-02 구현**: 선언적 지표 registry. `metrics_registry.py` — `MetricType(Enum)` STOCK/FLOW_TTM/HYBRID/PER_SHARE/DERIVED(한국어 값) + `@dataclass(frozen=True) MetricDef(name, mtype, numerator, denominator, is_ratio_0_1=False, price_denominator=None)` + `REGISTRY` 9종(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA) + 가격 의존 4종이 참조할 주당 분모 metric 4종(EPS_ttm/BPS/SPS/OCF_ps) = 13 MetricDef. **산식=mtype enum이 결정** → 신규 지표=튜플 1줄(SC3). GPM/OPM FLOW_TTM(0~1), ROE/ROA HYBRID(분자TTM÷분모최근값 D-03, net_income/total_equity·total_assets), 주당4종 분모=shares_outstanding, **가격 의존 4종(PER/PBR/PCR/PSR)은 numerator/denominator=None·price_denominator만**(D-07 가격 비결합 — 가격은 08-03 호출자 주입), PEG=DERIVED(08-03 _compute_peg). **EPS_ttm=net_income TTM÷최근shares**(A4 — eps 4합 부정확 회피). **새 매핑 dict 미정의** — `dart_account_map.DART_ACCOUNT_ID_MAP`·`edgar_client._EDGAR_*_CONCEPTS` import 재사용(SC1), numerator/denominator 논리 field는 store 어휘 그대로(T-08-03 정합). FCF·EV/EBITDA는 raw 부재로 제외하되 REGISTRY append 1줄 확장형(D-02). TDD: 11 단언(RED bd61516 / GREEN 9b95a82), 전 스위트 323 passed/5 skipped(회귀 0). FUND-09 ✓.
- **Plan 08-03 구현**: `metrics_engine.py` — 저장 raw만으로 9종 분기 매트릭스 전체를 외부 재호출 0으로 산출하는 순수 엔진(FUND-09 핵심). `compute_matrix(ticker, fetch_fn=fetch_raw_quarters) -> {metric: {quarter: MetricCell}}`(D-06, 분기 축=raw 등장 분기 오름차순·최신값=마지막 열) / `compute_cell(mdef, quarter, raw_by_qf)`(mtype 분기: FLOW_TTM=분자·분모 모두 TTM 마진 / HYBRID=분자TTM÷분모최근 ROE·ROA / PER_SHARE 주당 분모=분자÷최근shares — **분자가 stock field(total_equity 등 `_STOCK_FIELDS`)면 최근, 유량이면 TTM** [Rule1 버그수정: BPS 등 저량 분자 TTM 오적용→최근]) / `price_ratio(denom_cell, price)`(D-07 가격 주입 — 분모None/≤0·price결손=빈값+사유, PCR OCF<0 자연 차단). 분기 산술 `_calendar_quarter_offset`/`_prior_4_quarters`(Q1−1=전년Q4 경계, Pitfall 5), `_ttm_sum`(직전 4분기 합 — 1개 결손=None, 부분합산·0 대체 금지 SC4/D-05, rolling 미사용), `_normalize_quarters`(fetch 7-tuple→{(q,field):(value,source)}, DART 분기 단독값 그대로·EDGAR Q4 자연 결손 08-01 방침). provenance `_merge_provenance`(동일 source 단일·혼합 정렬 "+"결합 D-08, 예 "EDGAR+yf"). sanity bounds(ASSUMED): GPM −0.5~1.5/OPM −2~1.5/ROE ±2/ROA ±1/PER 0~1000/PEG 0~10/PBR·PSR·PCR 0~100, 밖=빈값+사유. fundamentals `_is_missing`/`MetricCell`/`_empty_cell`/`_compute_peg` **재사용**(신규 정의 없음, Phase 10 계약 동일). D-04 canonical 드리프트 수용(registry 4분기 합=단일 원천, 레거시 시트1 미세차 '더 일관된 값'). TDD: Task1 RED 0e8a09a/GREEN c51a565, Task2 GREEN 30fe528. engine 14 passed(08-01 RED 스캐폴드 5종 전부 GREEN, skip 0), 전 스위트 **335 passed/0 skipped**(회귀 0, 시트1 불변). FUND-09 ✓.
- **Plan 08-04 구현 (gap closure)**: 검증 단일 블로커(PEG 계산 경로 부재) 해소. **`compute_peg_cell(per_value, eps_ttm, eps_prior) -> MetricCell`** 공개 2단계 API를 `metrics_engine.py`에 추가 — PER `price_ratio`와 대칭. 본문이 `fundamentals._compute_peg`를 **실제 호출**(재수출만이 아님, grep `_compute_peg(` 1건) + sanity bounds("PEG":0~10) `_apply_sanity` 재사용. PEG value 더 이상 무조건 None 아님(검증 진실 #8·#9 충족). `compute_matrix` docstring에 **Phase 9/10 PEG 소비 계약 3단** 박제(① `price_ratio(matrix["EPS_ttm"][q], price)`로 PER → ② `eps_now=matrix["EPS_ttm"][q].value`·`eps_prior=matrix["EPS_ttm"][_calendar_quarter_offset(q,-4)].value` → ③ `compute_peg_cell(per.value, eps_now, eps_prior)`). `__all__`에서 `_compute_peg` 제거·`compute_peg_cell` 추가(IN-01 미사용 재수출 정리, `_compute_peg`는 내부 호출 import 유지). **옵션 B 채택**(엔진 후처리 옵션 A 아님 — D-07 가격 비결합 정합). 기존 L181 `"PEG" in matrix` 키-존재-만 단언 → `compute_peg_cell(20,12,10).value==approx(1.0)` value 단언 강화(결함 은닉 제거). **WR-01 결정성**: `fetch_raw_quarters` ORDER BY에 `CASE source WHEN 'EDGAR' THEN 0 WHEN 'DART' THEN 1 WHEN 'yf' THEN 2 ELSE 3 END DESC` 2차 정렬키 추가 — 소비측 `_normalize_quarters` 마지막-행-우선과 합쳐 EDGAR가 항상 결정적 선택(provenance 오염·수치 드리프트 차단). 방향 DESC 이유=마지막-행-우선(REVIEW ASC와 반대), 진실원천=결정성 단언 테스트. `?`-바인딩·`get_store()` 재사용 유지(T-08-01 불변, source는 SQL 리터럴). TDD: Task1 RED 4b6a3f7/GREEN 223cdc8, Task2 1b626ba. 신규 6 테스트(4 PEG + 2 source priority), 전 스위트 **341 passed**(baseline 335 + 6, 회귀 0, 시트1 불변 — fundamentals.py 시트1 경로·portfolio xlsx 미수정). FUND-09 ✓(블로커 해소).
- **Plan 09-01 구현**: 트렌드 렌더 순수 계산 기반 + 네트워크 0 fixture (FUND-10 선행). **`quarter_price.quarter_end_prices(ticker) -> ({YYYYQn: 분기말종가}, current_price)`**(D-09/SC4) — `fetch_ohlcv_cached` 소비(캐시 HIT 시 외부호출 0)·`resample("QE").last()`(구 "Q" 금지)·키 `to_period("Q").astype(str)`(`_calendar_quarter_offset` 출력 일치 Pitfall 4)·current=`Close.dropna().iloc[-1]`(시트1 동일 진입점)·빈 시계열 `({}, None)`. 신규 분기 산술 0(resample 위임). **`compute/trend_color.py`** — `LOWER_IS_BETTER={PER,PEG,PBR,PCR,PSR}`/`HIGHER_IS_BETTER={ROE,ROA,GPM,OPM}`(D-06)·`relative_bucket(metric,value,peer_values,industry)→"초록"|"무색"|"빨강"`(industry=="" or 유효 peer<3 무색 D-07, value 결손/동률 무색, strict below/above 비율 3분위 lower/upper_frac≤1/3, LOWER_IS_BETTER 방향 반전)·`yoy_glyph(cell_q,cell_q_prior)`(None/value 결손 → "" D-08, >▲/<▼/==''). `_is_missing` 재사용(신규 정의 0)·순수 함수·색 hex 미정의(Plan 02가 color_rules 상수 import). **`tests/fixtures/history_fixtures.py`** — `fetch_fn_stub`(US AAPL/tech EDGAR · KR 005930.KS/semiconductors DART 5분기 7-tuple → compute_matrix 주입)·`build_ohlcv`(monkeypatch용 합성 OHLCV)·`TICKER_INDUSTRY`. 결정성·외부호출 0(T-09-02 mitigate). TDD: T1 8e19163·T2 c152666·T3 00b1acf. 전 스위트 **354 passed**(baseline 341 + 13, 회귀 0, 시트1 미접근 — Core Value 색 신호 불변). FUND-10 선행 ✓. 결정: 동률→무색 중립(A4), 분위=strict below/above 비율, quarter_price 빈 시계열 ({},None) note는 호출자.
- **Plan 08-01 구현**: Phase 8 산식 선행. raw 진실 2건 fixture spike로 확정·박제(`test_raw_semantics_spike.py`, 네트워크 0) — (1) **DART 손익 thstrm_amount = 분기 단독값**(누적은 thstrm_add_amount, DS003+005930 fixture 교차) → 08-03 단순 4분기 합 TTM, **YTD 분해 미구현**(STATE "DART YTD 분해" 가정 철회). (2) **EDGAR raw에 캘린더 Q4·FY duration 부재**(by_period_length(3)만 저장) → 08-03 **Q4=빈값+사유**(D-05), FY−9M 보정 미구현(자연 결손), FY 저장은 범위 밖. `fundamentals_store.fetch_raw_quarters(ticker)` 추가 — `(quarter,source,field,value,period_type,reprt_code,unit)` quarter 오름차순 ?-바인딩 SELECT(ASVS V5/T-08-01, count_rows analog). `tests/fixtures/raw_quarters.py::raw_row` 12-tuple builder + `tests/test_metrics_engine.py`(fetch_raw_quarters 2종 GREEN + 엔진 -k 마커 5종 RED skip 스캐폴드). FUND-09 선행. 전 스위트 312 passed/5 skipped(회귀 0). commits 021a15e/48e32b9.

- **Plan 10-01 구현**: 시트1 펀더멘털 단일 원천 이관의 **계산·변환 계층**(FUND-11 선행). **`metrics_engine.inject_prices_for_quarter(matrix, q, price, eps_map)`** — 단일 분기 가격 의존 4종(PER/PBR/PCR/PSR) `price_ratio` + PEG 3단 `compute_peg_cell` in-place 공유 코어(D-06). `_PRICE_DEPENDENT`를 metrics_engine REGISTRY 단일 도출 → `history_render` import 재사용(사본·드리프트 0). `history_render._inject_prices`(다분기 루프) **비파괴 재배선** — 시그니처·외부 동작 유지, 본문이 공유 코어만 호출(직접 price_ratio/compute_peg_cell 0). **`fundamentals_view.matrix_to_fundamentals(matrix, latest_q) -> FundamentalsResult`**(신규 모듈) — 최신열 PER/PEG/GPM/OPM 무변환 매핑(`FundamentalsResult`/`MetricCell`/`_empty_cell`/`_is_missing` import 재사용, 신규 dataclass·산식 0, D-04/D-08). PEG.source=PER.source 승계(L5), `"소스 · 최신분기"` 라벨 합성(D-09, 결손 셀은 한국어 사유 보존 D-10), 빈 DB(latest_q=None/빈 matrix)=4셀 빈칸+"조회 실패: DB 분기 데이터 없음"(D-02). 호출순서 강제 docstring(L1: compute_matrix→inject_prices_for_quarter→matrix_to_fundamentals). TDD: T1 RED 565bb26/GREEN ac39b75, T2 RED efbebf5/GREEN 53bf344. 신규 8 테스트(inject 2 + 어댑터 6: 매핑·드리프트0·PEG승계·빈DB·가격parity·라벨합성). 전 스위트 **384 passed**(repo root on path, 회귀 0). `git diff sheet_portfolio.py` 빈 출력(Core Value 색 신호 0줄 변경). store 추출기(`fetch_edgar/dart_quarterly_raw`) 존치(L2). **[Rule1]** `test_history_render.py` import `tests.fixtures`→`fixtures` collection 차단 해소(선존 버그). **deferred**: 동 파일 CLI 디스패치 3종 = 레포 루트 sys.path 부재 경로 아티팩트(PYTHONPATH 추가 시 통과, 본 plan 무관 — deferred-items.md). 결정: 어댑터 가격 미주입(L1 호출자 책임)·PEG source 승계·_PRICE_DEPENDENT 단일 도출.
- **Plan 10-02 구현**: `main_run.run` 펀더멘털 경로 재배선 — 단일 원천(FUND-11). PASS1(시세·기업명 fan-out, `fundamentals_fn=None`) → SYNC(`sync_ticker_history` DB 적재, write 앞으로 이동) → **신규 READ**(종목별 `compute_matrix`(SQLite SELECT)→`latest_q`→`last_close=res.enriched_df.iloc[-1].get("Close")` L4 parity→`inject_prices_for_quarter` L1 순서→`res.fundamentals=matrix_to_fundamentals(...)` 재할당) → PASS2(`write_portfolio_sheet` 무변경). `_fundamentals_with_auth` 클로저·`fetch_fundamentals` 시트1 호출 제거(D-03, grep 0). **L7 준수**: skip_edgar/skip_dart 는 SYNC/ping 영역에만(store 읽기 인증 무관). 통합 2종(no_legacy_fetch/single_source) GREEN. freeze/smoke 스텁 재배선(collateral, sync_ticker_history stub). 전 스위트 386 passed(회귀 0). 시트1 writer 0줄(Core Value). 요약 "펀더멘털 HIT/MISS" 줄은 Plan 03 캐시 제거와 함께 정리(지금 제거 시 KeyError). commits c226730(T1)/4280974(T2)/a428096(collateral).
- **Plan 10-03 구현 (Phase 10 완료)**: 구 펀더멘털 fetch·캐시 죽은 코드 제거 + 시트1 색 회귀 잠금 — FUND-11 단일 원천 완성(SC2). Plan 02 가 호출자를 소멸시킨 구 경로를 **grep 호출자 0 확인 후** 안전 제거: `fundamentals.py` `fetch_fundamentals`/`_fill_us`/`_fill_kr`/`_empty_result`/`_log_*` 제거(389→~130줄, 공유 계약만 잔류) · `edgar_client.fetch_edgar_cached`/`dart_client.fetch_dart_cached` + `cache` import 제거 · `cache.py` 펀더멘털 캐시 헬퍼군(`_FUND_DIR`/`get_fund`/`put_fund`/`make_fund_key`)·`fund_hit`/`fund_miss` 통계 키 제거 · `main_run` 요약 펀더멘털 HIT/MISS 토막·`stats["fund_*"]` 참조 정리(L6 KeyError 방지). **보존 grep 단언**: D-04 계약(`MetricCell`/`FundamentalsResult`/`_empty_cell`/`_is_missing`/`_compute_*` 6건)·L2 store 추출기(`fetch_edgar/dart_quarterly_raw` 1건씩)·L3 OHLCV/기업명 캐시(`_DEFAULT_DIR`/`get_ohlcv`/`make_key` ≥3) 무손상. Task2 TDD 회귀-잠금: `test_sigma_color_unchanged_after_migration`(σ·tech-bucket 폰트색 hex 바이트 일치 + 펀더멘털 4셀 색 누출 0·num_fmt 보존)·`test_missing_db_fund_cells_blank`(`matrix_to_fundamentals({},None)`→4셀 빈칸+한국어 사유, σ 색 무영향 D-02). `git diff sheet_portfolio.py` 빈 출력(Core Value 0줄, L9). **collateral(Rule3)**: 죽은 심볼 참조 7파일 정리 — conftest/`test_cache`/`test_cache_isolation` fund 격리 제거, `test_fundamentals` 보존계약 산식만 잔류(41→16), edgar/dart cached 테스트·fund 픽스처 제거, `test_history_integration` no_legacy_fetch/single_source 를 spy→심볼-부재(hasattr) 단언으로 강화. 전 스위트 **353 passed**(회귀 0, 죽은-코드 테스트 -32 +신규 2). 선존 deferred 3종(`test_history_render` CLI 디스패치 = `No module named 'main'` sys.path 아티팩트, 본 plan 무관). commits 2db5fae(T1 refactor+collateral)/aabd526(T2 test). 결정: grep 호출자-0 후 제거·보존 grep 가드·요약 줄·통계키 동시 정리·통합 테스트 심볼-부재 강화.
- **Plan 09-02 구현**: 트렌드 워크북 작성 층 — 별도 워크북 팩토리 + 3종 시트 writer (FUND-10). **`history_workbook.make_history_workbook(path, *, constant_memory=False) -> (Workbook, formats)`** — 시트1 `make_workbook` 45키 캐시와 **완전 비결합** 신설(Pitfall 5/T-09-03), `color_rules`에서 GREEN_100/GREEN_900/RED_100/RED_900 **상수만** import(decide_* 미참조), formats 7키(green/red/plain 무색 D-07 + green_text/red_text/plain_text YoY 글리프 결합용 텍스트 셀 num_format 미적용 RESEARCH 방법 A + header), `{"constant_memory": False, "nan_inf_to_errors": True}`. **`sheet_metric_matrix.write_metric_sheet(wb,ws,metric,ticker_rows,display_quarters,formats,peer_lookup,prior_lookup)`** — 식별 5열 트렌드 전용 리터럴 재정의(sheet_portfolio `_COL` import 0, D-02) + 분기열 최신 왼쪽(D-01) + `relative_bucket`(D-05/06/07) green/red/plain 정적 베이킹 + `yoy_glyph` 셀 텍스트 결합(D-08) + 결손/미보유(`.get` None Pitfall 2) "-"+사유 코멘트(D-11) + provenance 코멘트(D-12) + 비율 지표(`_IS_RATIO`=REGISTRY is_ratio_0_1) 퍼센트·비-비율 소수(WARNING-2 시트1 정합·신규 산식 0) + `freeze_panes(0,1)` A열만 헤더행 미고정(D-04). peer/prior 호출자 주입(WARNING-3 — writer 모집단 자체 구성 0, wave3 시그니처 재작업 방지). **`sheet_raw.write_raw_sheet(ws,raw_by_ticker,formats,sorted_tickers)`** [원천] — 한국어 8열 헤더 + `fetch_raw_quarters` 7-tuple long 행·결손 "-" 일관(D-12 중심). **`sheet_snapshot.write_snapshot_sheet(ws,snapshot_rows,formats)`** [최신 스냅샷] — 식별 5열 + 9지표 + 종목 1행 매트릭스 최신 열 셀 **재사용**(재계산 0, D-13/Open Q2)·PEG 결손 "-". `_is_missing` 재사용(신규 게이트 0). 시트명 `[]` sanitize는 호출자(Plan 03) 책임(T-09-04). TDD: T1 f6e1785·T2 75f3c5a·T3 84eb511. 신규 read-back 7종(matrix 5+raw 1+snapshot 1), 전 스위트 **361 passed**(baseline 354 + 7, 회귀 0). 시트1 portfolio/color_rules/writer 0줄 수정(`git diff HEAD~3` 빈, Core Value 색 신호 불변). FUND-10 진행 ✓. 결정: 시트명 sanitize 호출자 책임, freeze A열만(0,1) 매트릭스·스냅샷 일관, 텍스트 셀 분리(글리프 결합 num_format 미적용).
- **Plan 09-03 구현 (Phase 9 완료)**: 트렌드 렌더 오케스트레이션 + CLI 서브커맨드 (FUND-10 엔드투엔드). **`io/history_render.py::run_history(tickers_path, output_dir) -> Path|None`** — Phase 8 엔진·Plan 01 가격·Plan 02 writer 배선, 신규 산식·외부 펀더멘털 호출 0. ① DB 미적재 게이트 `count_rows()==0` → 한국어 안내 print 후 `return None`(예외 아님 D-15) ② `_sorted_tickers` US→KR 그룹·그룹 내 알파벳순(D-03) ③ ticker별 `compute_matrix`(외부 0)+`quarter_end_prices` → `_inject_prices` in-place: 가격 의존 4종 `price_ratio(matrix[denom][q], price)`(최신 분기=현재가/그 외=분기말 종가 `qmap.get` Pitfall 2)·분기별 PEG 3단 `compute_peg_cell(per.value, eps_now, eps_prior=eps_map.get(_calendar_quarter_offset(q,-4)))`(D-10) ④ 다종목 분기 합집합→`reversed`(최신 왼쪽 D-01)·`peer_lookup(metric,quarter,industry)`=같은 산업 유효값(`_is_missing` 제외)·`prior_lookup`=4분기 전 셀 주입(WARNING-3 분기열×산업 2차원) ⑤ `make_history_workbook` → 9 지표 `write_metric_sheet` + [원천](sanitize "원천", `fetch_raw_quarters`) + [최신 스냅샷](sanitize "최신 스냅샷", 매트릭스 최신 열 재사용 D-13) → `fundamentals_history_YYYYMMDD.xlsx`(D-14). 시트명 `_sanitize_sheet_name`([]:*?/\\ 제거). 종목별 try/except 격리(`type(exc).__name__`만 T-09-07/08). **`main.py`** `add_subparsers` history(--tickers/--output-dir, description="펀더멘털 트렌드…") → 늦은 import `run_history`(None 시 종료코드 0); 서브커맨드 없으면 기존 `main_run.run` portfolio 하위호환. 통합 14종(SC1 별도파일·시트1 불변/SC2 9시트·최신왼쪽/SC3 원천·스냅샷/SC4 분기별 PEG 동치/D-04 freeze B1/D-15 DB게이트·CLI 4종) 네트워크·실DB 0(monkeypatch+fixture). 커밋: T1 8a0f155(run_history+통합테스트)·T2 0491f2f(main.py). 전 스위트 **375 passed**(baseline 361 + 14, 회귀 0). Core Value 불변: `git diff 4b6a3f7..HEAD` sheet_portfolio/color_rules/writer/main_run 0줄. FUND-10 ✓ 완료. 결정: 시트명 sanitize [] 제거 후 strip·history 서브커맨드 description 부여(자체 --help 노출)·분기별 가격 종목별 최신=현재가·스냅샷 최신 열 종목별 분기 최대 기준.

### Todos

- [ ] `/gsd:discuss-phase 7` — 백로그 fundamentals-history-delta.md 입력, SQLite 스키마·델타 가벼운 조회 API·파일 정책 세부 확정
- [ ] `/gsd:plan-phase 7` — Phase 7 plans 결정 (저장·델타 인프라)

### Blockers

(none)

## Session Continuity

Last session: 2026-06-23T07:28:23.368Z

**Next action:** Phase 10 검증(`/gsd:verify-phase 10`) — 전 스위트 353 passed(+선존 deferred 3)·시트1 σ-bucket 색 불변·`git diff sheet_portfolio.py` 빈 출력·`uv run python main.py` 시트1 펀더멘털 store 단일 원천 산출 확인. FUND-11 단일 원천 완성 → v1.3(Phase 7~10) 전 plan 완료. 다음 Phase 후보: Std-dev swing strategy 백테스트(MEMORY 참조) 또는 OHLCV 캐시 델타 최적화. **선존 deferred(권고)**: `test_history_render` CLI 디스패치 3종 sys.path 아티팩트 quick 정리.

**Resume context:**

- Read `.planning/ROADMAP.md` for v1.3 구조 (Phases 7-10, FUND-07~11, vertical-slice; 단일 원천 + 단계적 이관).
- Read `.planning/REQUIREMENTS.md` for v1.3 requirements (5 items, 100% mapped: FUND-07/08→P7, FUND-09→P8, FUND-10→P9, FUND-11→P10).
- Read `.planning/backlog/fundamentals-history-delta.md` for locked 설계 (권위 입력).
- 의존: Phase 3 fetch 층 위에 저장·델타·계산·렌더 추가. Core Value(시트1 색 신호) 불변.

---
*State initialized: 2026-05-19 · v1.1 roadmapped: 2026-06-15 · v1.3 roadmapped: 2026-06-17*

## Deferred Items

v1.0 마일스톤 종료(2026-06-12)에 인정·연기된 항목:

| Category | Item | Status |
|----------|------|--------|
| quick_task | 260605-kfy-ohlcv-nan-close | done (commit 23b01a7, OHLCV NaN 종가 트리밍) |
| code_review | 04-REVIEW WR-01 펀더멘털 NaN 가드 (Core Value 직결) | done (quick 260617-ijf, commit 222a37b, _is_missing 게이트) |
| code_review | 04-REVIEW WR-02~06 (ping 재시도·403 매칭·캐시 lock·테스트 네트워크) + IN-02 | done (quick 260617-k34, commit ddff54b) |
| verification | Phase 1·2 VERIFICATION.md 부재 (기능은 통합+UAT 사후 입증) | deferred |
| verification | Phase 2 200티커 실환경 부하 실증 | pending |

→ IN-01/03/04/05/06 위생 항목은 v1.3 종료 후 또는 별도 quick task로 처리 권장. 상세: v1.0-MILESTONE-AUDIT.md
