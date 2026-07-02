# BACKLOG: EDGAR Q4 갭 → US 트렌드 지표 대부분 None (TTM 연속 4분기 불가)

**상태:** ✅ 해결 (debug 세션 edgar-q4-gap-ttm-none, 2026-07-02) — 커밋 8ff1c2e·e809320·75a8383·49b2b06·7d7ef17. 상세: `.planning/debug/edgar-q4-gap-ttm-none.md`.
**우선순위:** 높음 (US 트렌드 시트의 핵심 가치가 여전히 미작동)

> **해결 요약 (2026-07-02):** (1) 추출단계 `Q4=annual−9M` 도출로 EDGAR 회계 Q4 갭 해소 → TTM 복구. (2) fuzzy concept 매칭 오염(CostOfRevenue·LiabilitiesAndStockholdersEquity·sub-line)을 필드별 정규 concept 화이트리스트로 정확 선별. (3) shares us-gaap 분기 폴백 + shares-only 분기 제거로 per-share 분모·최신열 복구. 클린 전수 재적재(raw_facts EDGAR DELETE 후 refetch, ok=125). **최신분기 GPM/OPM/ROE/ROA ≥1 수치 = 97/105(수정 전 ~3), 최근4분기 104/105.** metrics_engine 0줄·Core Value 0-diff. 전 스위트 385 passed. 잔여: OXY(우선주 net-income-to-common 전환) 1종목 net_income 화이트리스트 미스 — 소폭 후속 후보.
**선행:** quick 260629-hec(by_period_type 마이그레이션 + 전수 재적재) 완료 — raw_facts 는 채워짐. 이 문서는 그 **다음 층** 문제다.

> 자족 핸드오프(콜드 픽업용). edgartools 5.35.0 by_period_type 버그(별건, 해결됨)가 US raw_facts 를 비워 가려져 있던 기존 설계 한계가, 재적재 후 드러났다.

---

## 증상

quick 260629-hec 로 `data/fundamentals.db` raw_facts 에 US 105종목 분기×9필드를 전수 적재했음에도, `uv run python main.py history` 가 만드는 `output/fundamentals_history_*.xlsx` 의 **유량/하이브리드 지표(GPM/OPM/ROE/ROA/PER/PEG/PSR/PCR/EPS_ttm) 최근 분기 셀이 여전히 대부분 "-"**. GOOGL 등 12월 결산 기업은 **전 분기 None**. raw 데이터는 있는데 계산 결과가 빈다.

## 근본 원인 (라이브 재현 확정)

1. **EDGAR Q4 갭:** EDGAR EntityFacts 의 3개월 단독(duration, ~3M) 손익 fact 는 회계 Q1·Q2·Q3 만 존재하고 **회계 Q4 는 없다**(10-K 는 연간 12M, 별도 3개월 Q4 미제공 → 연간−9M 으로 도출해야 함). `by_period_type("quarterly")`(=`by_period_length(3)`)는 3개월만 통과시키므로 캘린더상 매년 한 분기가 영구 결손.
   - 캘린더 매핑(quick 260629-hec, period_end 월 기준): 9월 결산(AAPL)→캘린더 Q3 결손, 12월 결산(GOOGL)→캘린더 Q4 결손.
2. **TTM 연속 4분기 + 결손 불관용(잠긴 D-05):** `metrics_engine._ttm_sum` 은 직전 4분기 중 1개라도 결손이면 None(부분합산·0 대체 금지, SC4/D-05). 4 연속 분기는 반드시 갭 분기 1개를 포함 → **거의 모든 TTM = None** → GPM/OPM/EPS_ttm/SPS/OCF_ps 및 그 파생(PER/PEG/PSR/PCR) 연쇄 None. HYBRID(ROE/ROA)도 분자 net_income TTM 결손으로 None.
   - 과거 일부 연도는 정정공시 등으로 갭 분기에 데이터가 있어 GPM/ROE 가 부분 계산되나(AAPL GPM 46/73, ROE 45/73), **최근 분기는 갭으로 None.**
3. **shares_outstanding 희소성(부차):** `facts.shares_outstanding_fact` 가 종목당 1행만 적재(일부 종목은 0행 — `dei:EntityCommonStockSharesOutstanding` concept 부재 경고). PER_SHARE(EPS_ttm/BPS/SPS/OCF_ps)·가격의존(PER/PBR/PCR/PSR) 분모가 비어 BPS 같은 저량 기반 지표마저 None.

**증거(2026-06-29 라이브):**
- 비-None TTM 셀 수: AAPL `{GPM:46, OPM:4, ROE:45, ROA:1, EPS_ttm:0, BPS:0, SPS:0, PER:0, PBR:0}`, GOOGL `전부 0`, NVDA `{GPM:40, ROE:40, 나머지 0}`, CAT `{GPM:45, ROE:48, 나머지 0}`.
- AAPL revenue 분기(최근): `2024Q2, 2024Q4, 2025Q1, 2025Q2, 2025Q4, 2026Q1` — `2024Q3·2025Q3` 영구 결손(= 회계 Q4).

## 왜 별건인가

quick 260629-hec 의 by_period_type 버그는 "raw_facts 가 빈다"였고 해결됐다. 이 문제는 "raw_facts 는 있는데 TTM 산식이 갭으로 None"이다 — **다른 근본원인**이고, 잠긴 결정(D-05 TTM 결손 불관용)과 Phase 8 엔진을 건드리므로 정식 진단/계획이 필요하다. STATE Plan 08-01 이 이미 "EDGAR 캘린더 Q4·FY duration 부재 → Q4=빈값+사유, FY−9M 보정 **미구현**(자연 결손), FY 저장 범위 밖"으로 명시 — 즉 의도된 deferred 였으나, US 데이터 공백에 가려 영향이 드러나지 않았다.

## 수정 방향 (조사 필요 — 미확정)

1. **Q4 도출(핵심):** EDGAR 에서 **연간(12M, `by_period_type("annual")`=`by_period_length(12)`) + 9M YTD(`by_period_length(9)`)** fact 를 추가 추출하고, **Q4(3M) = 연간 − 9M** 으로 도출해 raw_facts(또는 엔진 계산 시점)에 채운다. 이러면 4 연속 분기가 완성돼 TTM 복구.
   - 결정 필요: 도출을 (a) 추출 단계(store 에 파생 Q4 행 적재) vs (b) 엔진 단계(compute_matrix 에서 on-the-fly). D-02(원천 raw 누적) 정신상 (a)가 정합적이나 "as-reported 만" 원칙(Plan 08-01)과 충돌 가능 → 진단에서 결론.
   - 누적 누계(YTD) 기업/일부 비표준 태깅 주의(DART YTD 분해 선례 참조).
2. **D-05 재검토:** TTM 결손 불관용을 유지하되 Q4 도출로 결손 자체를 없앤다(권장). D-05 를 완화(부분합산 허용)하는 길은 지표 왜곡 위험 — 비권장.
3. **shares_outstanding 보강:** `dei:EntityCommonStockSharesOutstanding` 외 `us-gaap:CommonStockSharesOutstanding`/`WeightedAverageNumberOfDilutedSharesOutstanding` 등 폴백 concept 로 분기별 shares 확보 → PER_SHARE/가격의존 지표 분모 복구.
4. **재적재·검증:** 수정 후 delta_state EDGAR 정리 → 재동기화 → history 재생성으로 GOOGL/AAPL 최근 분기 GPM/PER 등이 수치로 채워짐 확인.

## 검증 기준 (안)

- GOOGL·AAPL 등 대표 종목의 **최근 4~8분기 GPM/OPM/ROE/PER 가 None 아님**(육안 + 구조 단언).
- `metrics_engine` 단위 테스트: Q4 도출 fixture(연간·9M·3M)로 TTM 복구를 네트워크 0 으로 단언.
- 전 스위트 GREEN(회귀 0).
- **Core Value 불변:** 시트1 `portfolio_*.xlsx` 색 신호·레이아웃 0줄(history 경로 전용).

## 관련 파일

- `src/stocksig/io/edgar_client.py` — `_EDGAR_DURATION_CONCEPTS`, `fetch_edgar_quarterly_raw`, `_query_facts`(annual/9M 추출 추가 지점), `_quarter_key_from_period_end`.
- `src/stocksig/io/metrics_engine.py` — `_ttm_sum`, `compute_cell`, `compute_matrix`(Q4 도출 후처리 후보), `_calendar_quarter_offset`, `_prior_4_quarters`.
- `src/stocksig/io/fundamentals_store.py` — raw_facts 스키마(파생 Q4 행 적재 시), `fetch_raw_quarters`.
- `tests/fixtures/*` , `tests/test_metrics_engine.py` — Q4 도출 fixture·단언.
- 권위 입력: STATE Plan 08-01/08-03(TTM·Q4 결정), `.planning/backlog/fundamentals-history-delta.md`(D-H1~4).

## 다른 PC에서 이어받는 법

1. `git pull` 후 `uv run python -m pytest` 환경 확인.
2. quick 260629-hec SUMMARY(`.planning/quick/260629-hec-.../260629-hec-SUMMARY.md`) 로 선행 맥락 파악.
3. `/gsd-debug` 또는 `/gsd-quick --discuss` 로 착수(Q4 도출 위치 (a)/(b) 결정이 핵심 그레이존).
