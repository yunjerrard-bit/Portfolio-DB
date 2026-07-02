---
slug: edgar-q4-gap-ttm-none
status: resolved
trigger: "US EDGAR 펀더멘털 재출력(fundamentals_history_20260630) 후에도 대부분 종목이 결손. by_period_type 수정(quick 260629-hec)으로 raw_facts는 채워졌으나 트렌드 지표 최신분기가 여전히 비어 있음."
created: 2026-07-01
updated: 2026-07-02
subsystem: io/edgar_client (추출) + data/fundamentals.db
goal: find_and_fix
locked_decision: "(a) 추출 단계에서 Q4 = 연간(12M) − 9M YTD 를 도출해 raw_facts 에 provenance 라벨과 함께 저장. 잠긴 엔진 D-05/_ttm_sum 0줄 수정. EDGAR 데이터를 이미 정상 작동하는 DART(분기 단독값) 경로와 동일 형태로 만든다."
authoritative_input: .planning/backlog/edgar-q4-gap-ttm-none.md
core_value_guard: "시트1 색 신호 불변 — sheet_portfolio.py / writer.py / color_rules.py git diff 빈 출력. 이 버그·수정은 history 경로 전용."
---

# Debug: EDGAR Q4 갭 → US 트렌드 지표 대부분 결손

## Symptoms

- **Expected**: `output/fundamentals_history_YYYYMMDD.xlsx` 에서 US 종목의 GPM/OPM/ROE/ROA/PER/PEG/PBR/PSR/PCR 트렌드 셀(특히 최신 분기)이 수치로 채워짐.
- **Actual**: raw_facts 는 채워졌으나(105 US 종목 ≥6필드, 36,162행) 트렌드 셀 최신분기가 대부분 "-". `[최신 스냅샷]` 시트는 거의 전부 빈칸.
- **Errors**: 예외 아님. `compute_cell` 이 정상적으로 `MetricCell(value=None, note="… TTM 결손")` 반환. 조용한 결손.
- **Timeline**: quick 260629-hec(by_period_type 마이그레이션) 로 1층(raw 빈값) 해결 후, 그에 가려져 있던 2층 문제가 드러남. STATE Plan 08-01 이 "FY−9M 보정 미구현(자연 결손)" 으로 이미 명시한 의도된 deferral.
- **Reproduction**: `uv run python main.py history` → xlsx 열어 US 종목 최신분기 확인. 또는 `compute_matrix(ticker)` 최신분기 셀 검사.

## Current Focus

- **status_note**: 단계1 스파이크 GREEN(전제 확정, relerr 0.0000%). 단계 2~5 논스톱 진행 중. edgar_client(추출)만 수정, metrics_engine 0줄, 시트1 0-diff.
- **hypothesis**: EDGAR EntityFacts 는 3개월 단독 손익 fact 를 회계 Q1·Q2·Q3 만 제공(회계 Q4 부재 — 10-K 는 연간 12M 만). `by_period_type("quarterly")`(=3M) 는 회계 Q4 를 통과시키지 못해 캘린더상 매년 한 분기가 영구 결손. `_ttm_sum` D-05 불관용 → TTM 및 파생 지표 연쇄 None.
- **next_action**: [단계 6] 표본 재적재(DB 변경) — CHECKPOINT 발행·사용자 승인 대기. 단계5 게이트 PASS: 전 스위트 377 passed(회귀 0, +9 신규). Core Value 0-diff(sheet_portfolio/writer/color_rules)·LOCKED metrics_engine.py 0-diff 확인. 커밋1 8ff1c2e·커밋2 e809320.
- **reasoning_checkpoint**:
  - hypothesis: EDGAR 회계 Q4 3M fact 부재 → by_period_type("quarterly") 갭 → _ttm_sum 4분기 결손 불관용(D-05) → TTM 및 전 파생 None. 추출단계에서 Q4=annual−9M 도출·저장하면 4연속 분기 완성 → 엔진 0줄 수정으로 TTM 복구.
  - confirming_evidence: (1) 라이브 스파이크 relerr 0.0000%(손익 3종·5개 회계연도). (2) 도출 Q4 분기키가 정확히 갭 분기(AAPL Q3·GOOGL Q4)를 메움. (3) DB raw 충분(36,162행)한데 최신분기 102/105 결손 — 계산단계 문제 확정.
  - falsification_test: 도출 Q4 저장 후에도 compute_matrix 최신 4~8분기 GPM/net_income TTM 이 여전히 None 이면 가설 오류(도출 분기키 불일치·엔진 미소비 등).
  - fix_rationale: _normalize_quarters 가 (quarter,field)만 키로 쓰므로 추출단계가 갭 분기키에 Q4 값을 채우면 엔진은 무변경으로 4연속 분기를 봄 → 근본(갭) 자체 제거(증상 억제 아님).
  - blind_spots: OCF 는 3M 단독 fact 부재(YTD 누계)라 Q4 도출만으로 완전 복구 안 됨(별건, 회귀는 없음). 정정공시 다중 accession·비차원 총액 선택(is_dimensioned) 픽스처로 검증 필요.

## Evidence

- timestamp: 2026-07-01 | DB 실측(diag.py): EDGAR 105종목 전부 field≥6, 36,162행. raw 자체는 충분 — 문제는 계산 단계.
- timestamp: 2026-07-01 | compute_matrix 실측(diag3.py): raw 보유 105종목 중 최신분기 GPM/OPM/ROE/ROA ≥1 수치 = **3종목**, 4종 전부 결손 = **102종목(97%)**. raw 전무 20종목(ETF·외국 20-F/40-F·센티넬 — CLAUDE.md 명시 범위, 정상).
- timestamp: 2026-07-01 | AAPL GPM 최근 8분기 전부 `value=None note='GPM: 분자(gross_profit) 미존재 또는 TTM 결손'`. AAPL revenue 분기: 2024Q3·2025Q3 영구 결손(=회계 Q4).
- timestamp: 2026-07-01 | AAPL EPS_ttm 전분기 None `note='분자(net_income) … TTM 결손'` → net_income TTM 결손이 1차 → per-share(EPS/BPS/SPS/OCF_ps) 전멸 → 가격의존 PER/PEG/PSR/PCR 연쇄 None.
- timestamp: 2026-07-01 | 소스 확인(quick 260629-hec SUMMARY): `by_period_type("quarterly")` ≡ `by_period_length(3)`. shares_outstanding 종목당 1행(희소) → BPS/PBR 부차 결손(NVDA·CAT만 BPS 1개).
- timestamp: 2026-07-01 | **단계1 라이브 스파이크(AAPL·GOOGL, 폐기용, 전제 확정):**
  · annual(by_period_length(12))·9M YTD(by_period_length(9)) fact 실존 확인 — 손익 3종(revenue/net_income/op_income) 전부.
  · `Q4(3M)=annual−9M` + `Q1+Q2+Q3(3M)+도출Q4` = **relerr 0.0000%**(AAPL FY2024·FY2025, GOOGL FY2023·FY2024·FY2025 전부 정확 정합).
  · 캘린더 매핑 정확: 도출 Q4 period_end 월 분기키가 정확히 갭 분기를 메움 — AAPL→2025Q3·2024Q3(캘린더 Q3), GOOGL→2024Q4·2023Q4·2025Q4(캘린더 Q4). 기존 3M 분기와 충돌 없음.
  · 9M 매칭 = period_start 동일(같은 회계연도 누계 시작). annual/9M/3M fact 는 `is_dimensioned` 속성 보유 → 비차원 총액(`is_dimensioned=False`, `dimensions=None`)만 선택해야 함(GOOGL 세그먼트 다중 fact 존재).
  · **OCF 예외:** operating_cash_flow 는 3M 단독 fact 부재(annual/9M/6M/3M 전부 YTD 누계) — 회계연도 내 3M 은 Q1 1건뿐(relerr ~46%). OCF 의 분기 TTM 은 본 갭과 무관하게 **기존부터 결손**(누계 분해 별건). Q4=annual−9M 도출은 Q4 값을 정확히 주지만 Q1~Q3 3M 부재는 못 메움 → OCF 는 회귀 없음·부분 개선. shares_outstanding 폴백(단계4)이 per-share 분모 별도 복구.
- timestamp: 2026-07-01 | 소스 재확인: revenue 는 `RevenueFromContractWithCustomerExcludingAssessedTax`(AAPL/GOOGL 단일 비차원 총액)·`Revenue`(다중 차원)·`Revenues`(구형) 혼재. 기존 추출은 `Revenue` concept+quarterly. Q4 도출은 비차원 총액 fact 만 사용해야 세그먼트 오염 회피.

## Eliminated

- hypothesis: "raw_facts 가 여전히 비어 있다" | 반증: EDGAR 105종목 field≥6, 36,162행 실측. 1층은 260629-hec 로 해결됨.
- hypothesis: "quick 260629-hec 수정이 회귀를 냈다" | 반증: 368 passed, 시트1 0줄. 결손은 US 데이터 공백에 가려져 있던 기존 설계 한계(Plan 08-01 명시 deferral)이지 회귀 아님.
- hypothesis: "가격(yfinance) 미주입 탓" | 반증: 가격 불필요 지표 GPM/OPM/ROE/ROA 도 최신분기 102/105 결손. 가격 이전 단계(TTM)에서 이미 None.

## 수정 계획 (사용자 확정 — 안정적 순서)

라이브 전수 적재(되돌리기 어려움)는 코드 GREEN 이후 맨 마지막. 값싼 것·오프라인 먼저.

0. [완료] 설계결정 확정 — (a) 추출단계 Q4 도출, provenance 라벨.
1. GOOGL·AAPL 라이브 스파이크 — annual/9M fact 실존·`Q4=연간−9M` 정합 확인(폐기용).
2. 오프라인 픽스처 TDD — Q4 도출 + TTM 복구 **구조값 단언**(렌더텍스트 금지, 컨벤션). 실패 테스트 먼저.
3. edgar_client 추출부 구현 — annual/9M concept 추출 + `Q4=연간−9M` 도출 + provenance 라벨(예: period_type='derived' 또는 source 표기). 조용한 except 미부활. → 커밋1.
4. shares_outstanding us-gaap 폴백(`us-gaap:CommonStockSharesOutstanding` 등) — per-share 분모 복구. **분리 커밋2**(회귀 격리).
5. 게이트 — 전 스위트 GREEN(회귀 0) + Core Value 0-diff(`git diff` sheet_portfolio.py·writer.py·color_rules.py 빈 출력).
6. 표본 재적재 — delta_state EDGAR 中 AAPL·GOOGL 2행만 삭제 → 2종목 재동기화 → compute_matrix 최신 4~8분기 GPM/PER 수치 확인.
7. 전수 재적재 — delta_state EDGAR 정리(멱등) → US 재동기화. DB git 추적 → 롤백 안전망.
8. history 재생성 + 정량 검증 — `main.py history` → diag3.py 재실행으로 "최신분기 4종 전부 결손" 102/105 → 대폭 감소 확인. 백로그 완료 표기 + 커밋.

## 검증 기준

- GOOGL·AAPL 등 최근 4~8분기 GPM/OPM/ROE/PER 가 None 아님(육안 + 구조 단언).
- metrics/추출 단위 테스트: Q4 도출 fixture(연간·9M·3M)로 TTM 복구를 네트워크 0 으로 단언.
- 전 스위트 GREEN(회귀 0).
- Core Value 불변: 시트1 색 신호·레이아웃 0줄.

## 단계 6 결과 — 신규 블로커 발견 (표본 재적재로 확인, DB 롤백함)

AAPL·GOOGL 2종목 표본 재적재 실행 → **Q4 도출은 정확**(AAPL 캘린더 Q3·GOOGL 캘린더 Q4 갭을 정상 값으로 메움, GPM/OPM/ROE TTM 극적 복구). **그러나 사전-존재 추출 버그가 드러남** → DB 는 `git checkout` 로 롤백(derived 0행, delta_state 복원).

**신규 블로커: 3M·instant 추출의 "총액 선택" 실패 (fuzzy concept 매칭).**
- `by_concept(concept)` 기본 fuzzy → 한 (field, 분기)에 **여러 비차원(is_dimensioned=False) fact** 반환. 현행 3M·instant 루프는 전부 append → upsert 마지막-쓰기로 **아무거나** 저장(쓰레기 가능).
- 라이브 증거(2026-07-01):
  - GOOGL revenue 3M: `Revenues`=102.3B(정답)·`CostOfRevenue`=41.4B·`RevenueNotFromContractWithCustomer`=−0.2B 공존 → −0.2B 저장됨 → revenue TTM 붕괴 → **OPM=1.13(>100%, 불가능)** 이 sanity(1.5) 통과해 유효값 렌더.
  - AAPL total_equity: `LiabilitiesAndStockholdersEquity`=379B(=총자산)·`StockholdersEquity`=88B(정답) 공존.
  - AAPL total_liabilities: `LiabilitiesAndStockholdersEquity`=379B·`Liabilities`=291B(정답)·sub-line 다수.
  - AAPL total_assets: `Assets`=379B(정답)이나 현행은 sub-line(93B) 저장.
- **max-abs 는 부적합**: total_equity/total_liabilities 에서 `LiabilitiesAndStockholdersEquity`(더 큼)를 잘못 고름. → **필드별 정규 concept 화이트리스트(정확 매칭)** 가 정답. revenue 만 회사별 상이(Revenues vs RevenueFromContractWithCustomerExcludingAssessedTax) → 화이트리스트 내 max-abs 로 CostOfRevenue 배제.

**부차: AAPL shares_outstanding 1행.** dei shares_outstanding_fact 가 present(1행)라 `_shares_fallback_rows`(us-gaap 분기별) 가 실행되지 않음 → EPS_ttm 0/8. (GOOGL 은 dei 부재 → 폴백 43행 정상.) → dei 유무와 무관하게 us-gaap 분기별 폴백을 **항상 병합**.

**→ commit 3 (사용자 승인 "수정 확장 진행"):** 필드별 정규 concept 화이트리스트 + 비차원 + (화이트리스트 내)max-abs 선택을 3M·instant·derived 경로에 통일 적용. AAPL shares 폴백 항상 병합. metrics_engine 0줄·Core Value 0-diff 유지. TDD(다중-fact fixture → 정규 총액 선택 구조 단언). 전수 재적재 전 AAPL·GOOGL 재표본으로 OPM~0.3·equity 88B·assets 379B 확인.

## Resolution

- root_cause: (확정) 2층. (1) EDGAR 회계 Q4 3M fact 부재 → by_period_type("quarterly") 갭 → _ttm_sum 4분기 결손 불관용(D-05) → TTM 연쇄 None. (2) [단계6 발견] fuzzy concept 매칭으로 3M·instant 총액 대신 세그먼트/오목(CostOfRevenue·LiabilitiesAndStockholdersEquity·sub-line) 저장 → 값 오염(전수 재적재 전 반드시 수정).
- fix: (코드 완료, 재적재 대기) 커밋1 8ff1c2e — edgar_client 추출단계에 `_derive_q4_rows`: 손익 유량 concept 별 annual(by_period_length(12))·9M(by_period_length(9)) 비차원 총액(`is_dimensioned=False`)을 period_start 로 매칭해 `Q4=annual−9M` 도출, 갭 캘린더 분기키에 period_type="derived" 라벨로 저장(as-reported 3M 존재 분기는 skip). 커밋2 e809320 — dei shares_outstanding_fact 부재 시 `_shares_fallback_rows`(us-gaap CommonStockSharesOutstanding → WeightedAverage* 순) 폴백으로 분기별 shares 확보. metrics_engine.py 0줄 수정(_normalize_quarters 가 (quarter,field)만 키로 소비 → 4연속 분기 자연 인식).
- commit3 (75a8383, 커밋3): fuzzy concept 총액 오염 수정 — _FIELD_CANONICAL_CONCEPTS 화이트리스트 + _canonical_facts 필터를 3M·instant 방출 경로에, _pick_canonical_by_period 를 derived 경로에 적용(max-abs 미사용 — LiabilitiesAndStockholdersEquity 오선택 방지). shares us-gaap 폴백 항상 병합. 전 스위트 383 passed(회귀 0). Core Value·metrics_engine 0-diff. 단계6 재검증(AAPL·GOOGL 재적재): GOOGL OPM 0.32(정상, 이전 1.13)·revenue 양수·AAPL total_assets 379B·total_equity 88B·shares 70행·EPS_ttm/ROA 복구. DB 는 AAPL·GOOGL 2종목만 재적재된 혼재 상태(나머지 103종목 미갱신) → 단계7 전수 재적재 대기.
- verification: (단계5 게이트 PASS) 전 스위트 377 passed(회귀 0, 기준 368 대비 +9 신규: q4_derive 6·shares_fallback 3). 직접 영향 영역 오프라인 53 passed(test_raw_semantics_spike 의 "AAPL 공유 fixture Q4 부재" 단언 불변 — 도출은 별도 fixture 로 격리). LOCKED metrics_engine.py 0-diff·Core Value(sheet_portfolio/writer/color_rules) 0-diff 확인. 단계6 DB 재적재(되돌리기 어려움)는 CHECKPOINT 발행 후 사용자 승인 대기 — 실 DB 정성 검증(최신분기 TTM 복구 육안)은 미수행.
- commit4 (49b2b06): 발행주식수 us-gaap 분기별 우선·dei 최후수단. dei 표지(cover-page) 단일 fact 가 재무 분기보다 앞선 quarter 를 만드는 문제 완화.
- commit5 (7d7ef17): shares-only 분기 제거 — us-gaap CommonStockSharesOutstanding 도 표지·BS 두 기준일 fact 를 담아 재무필드 없는 분기(2026Q2)에 shares 만 남겨 최신열 오염. 재무필드(flow/BS/eps) 없는 분기의 shares 행 추출 시 제외(per-share 지표는 동분기 재무 분자 필요 → 손실 0).
- **재적재 주의(중요)**: upsert 는 orphan 미제거 → 재적재는 반드시 `DELETE FROM raw_facts WHERE source='EDGAR'` + delta_state 정리 후 재fetch(클린). delta_state 만 지우면 구코드 cruft(shares-only 분기 등) 잔존.
- verification (완료, 2026-07-02): 전 스위트 **385 passed**(기준 368 +q4_derive6 +shares3 +canonical7, 회귀 0). LOCKED metrics_engine.py·Core Value(sheet_portfolio/writer/color_rules) **0-diff**. 클린 전수 재적재(ok=125 fail=0, derived 3618행/105종목). compute_matrix 실측: **최신 단일분기 GPM/OPM/ROE/ROA ≥1 수치 = 97/105**(수정 전 ~3), **최근 4분기 = 104/105**. history xlsx(fundamentals_history_20260702.xlsx) [최신 스냅샷] US 124행 중 103행 지표 표시(전체 145/169). GOOGL OPM 0.32·AAPL total_assets 379B·equity 88B·shares 70행 정상.
- 잔여(경미): revenue 0행 = GLD(금 트러스트)·OKLO(pre-revenue) — 정상 결손. 최신-단일분기 빈칸 8종목 = 대부분 엣지 분기(recent4 채움)·부분분기(BS만)·금트러스트. **OXY 1종목**만 recent4 결손 — net_income 이 2024Q1 이후 `NetIncomeLossAvailableToCommonStockholders`류(우선주 보유)로 전환돼 NetIncomeLoss 화이트리스트 미포함 + gross/op income 부재(정유사). → 향후 net_income 화이트리스트에 AvailableToCommon 변형 추가 시 개선(소폭 후속 후보).
- files_changed: [src/stocksig/io/edgar_client.py, tests/fixtures/edgar_aapl_facts.py, tests/fixtures/edgar_q4_derive.py, tests/test_edgar_q4_derive.py, tests/test_edgar_shares_fallback.py, tests/test_edgar_canonical_select.py]
- commits: 8ff1c2e(커밋1 Q4도출) · e809320(커밋2 shares폴백) · 75a8383(커밋3 정규concept) · 49b2b06(커밋4 dei최후수단) · 7d7ef17(커밋5 shares-only제거)
