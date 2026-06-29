---
phase: quick-260629-hec
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/stocksig/io/edgar_client.py
  - tests/fixtures/edgar_aapl_facts.py
  - tests/test_edgar_quarterly.py
autonomous: true
requirements: [FUND-07, FUND-11]

must_haves:
  truths:
    - "by_period_type(\"duration\") / by_period_type(\"instant\") 호출이 edgar_client.py 에서 완전히 사라진다 (grep 0건)."
    - "유량 6종은 by_period_type(\"quarterly\")로 조회되고 by_period_length(3) 위임 호출은 제거된다(quarterly=length3 동치)."
    - "저량 3종(BS)은 by_concept(C).execute() 후 파이썬에서 period_type=='instant' 필터로 추출된다(_instant_fallback 유지)."
    - "_calendar_quarter_key 가 fact.period_end 의 월 기준 (month-1)//3+1 로 YYYYQn 을 산출하고, period_end 부재 시 기존 display 경로 차선책, 비분기/비-YYYYQn 입력엔 None(fullmatch 가드 유지)."
    - "_query_facts 가 예외를 조용히 삼키지 않고 concept·예외타입을 WARNING 로깅한다(여전히 빈 리스트 반환으로 추출 전체는 죽지 않음)."
    - "같은 (quarter, field) 에 다중 fact 가 올 때 filing_date(실재 속성, 없으면 period_end) 오름차순 정렬로 최신/정정값이 마지막에 와 upsert 마지막-쓰기 승과 정합한다."
    - "전체 pytest GREEN — 회귀 0 (기존 + 신규 회귀 테스트)."
    - "시트1 portfolio 색 신호·레이아웃 0줄 변경 — git diff 로 sheet_portfolio.py·color_rules·writer 빈 출력."
  artifacts:
    - path: "src/stocksig/io/edgar_client.py"
      provides: "edgartools 5.35.0 by_period_type 마이그레이션된 fetch_edgar_quarterly_raw·_query_facts·_calendar_quarter_key"
      contains: "by_period_type(\"quarterly\")"
    - path: "tests/test_edgar_quarterly.py"
      provides: "마이그레이션 회귀 테스트 (quarterly 경로·instant 파이썬 필터·period_end 분기키·정렬·WARNING)"
      contains: "period_end"
  key_links:
    - from: "edgar_client._query_facts/_fact_to_row"
      to: "raw_facts.quarter(YYYYQn)"
      via: "_calendar_quarter_key(period_end 월 기반)"
      pattern: "period_end"
    - from: "raw_facts.quarter"
      to: "metrics_engine.compute_matrix 분기축"
      via: "fetch_raw_quarters quarter 오름차순"
      pattern: "compute_matrix"
    - from: "compute_matrix 분기 매트릭스"
      to: "fundamentals_history xlsx 트렌드 셀"
      via: "history_render.run_history"
      pattern: "run_history"
---

<objective>
edgartools 5.35.0 의 `FactQuery.by_period_type` 어휘 변경(`{annual,quarterly,monthly,ttm,ytd}` 만 유효, `"duration"`·`"instant"` 폐기 → ValidationError)으로 US(EDGAR) 전 종목 펀더멘털(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA)이 전 결손된 버그를 수정한다.

핵심 수정(백로그 6단계 + LOCKED FACTS 정정):
1. 유량 6종: `by_period_type("quarterly")` 로 마이그레이션 + `by_period_length(3)` 제거(quarterly=length3 동치, LOCKED FACT 3).
2. 저량 3종(BS): `by_period_type` 미사용 — `by_concept(C).execute()` 후 파이썬에서 `period_type=='instant'` 필터(LOCKED FACT 5). `_instant_fallback` 유지.
3. `_calendar_quarter_key`: 키 소스를 `get_display_period_key()` 대신 `fact.period_end` 의 월 기준 `(month-1)//3+1` → "YYYYQn". period_end 부재 시 display 차선책. YYYYQn fullmatch 최종 가드 유지(260627-vpn 도입분).
4. `_query_facts` 의 조용한 `except Exception: return []` → WARNING 로깅(향후 API 변경 가시화). 결손은 여전히 빈 리스트.
5. 중복 facts 정렬: filing_date(LOCKED FACT 6의 실재 속성, 없으면 period_end) 오름차순 → 최신/정정값이 마지막에 오게(upsert 마지막-쓰기 승 정합).
6. 재적재(별도 태스크): delta_state EDGAR 행 비우고 표본 재동기화로 raw_facts 채워짐 확인.

Purpose: Core Value(시트1 색 신호)와 무관한 history/store 경로 전용 버그. US 펀더멘털 트렌드 전부 무의미한 상태를 복구한다.
Output: 마이그레이션된 edgar_client.py + 네트워크 0 회귀 테스트(커밋 가능 핵심 산출물) + 시트1 색 불변 잠금 + 표본 재적재 검증.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md

실행 모드: 메인 트리 순차(워크트리 비활성). commit_docs=false →
**코드만** 원자 커밋(.planning 문서·STATE.md·PLAN/SUMMARY 커밋 금지 — 오케스트레이터가 처리).
검증 자동화 명령은 이 PC 경로: `uv run python -m pytest`.
</execution_context>

<context>
@.planning/STATE.md
@.planning/backlog/edgar-fundamentals-us-broken.md
@CLAUDE.md
@src/stocksig/io/edgar_client.py
@src/stocksig/io/fundamentals_delta.py
@src/stocksig/io/fundamentals_store.py
@tests/fixtures/edgar_aapl_facts.py
@tests/test_edgar_quarterly.py
@tests/test_edgar_client.py
@tests/conftest.py

<locked_facts>
오케스트레이터가 이 PC `.venv` 의 edgartools 5.35.0 소스를 직접 읽어 확정한 사실. 재조사 금지:
1. edgartools 5.35.0 설치 확정.
2. `by_period_type(p)` 는 `validate_period_type` 로 검증 — 유효값 = {annual, quarterly, monthly, ttm, ytd}. `"duration"`·`"instant"` 은 ValidationError(ValueError 서브클래스) → US 전 결손의 근본 원인.
3. `by_period_type("quarterly")` 는 내부적으로 정확히 `by_period_length(3)` 로 위임(period_mapping={'annual':12,'quarterly':3,'monthly':1}). 따라서 quarterly 마이그레이션 후 현행 `.by_period_length(3)` 는 중복 → 제거.
4. `by_period_length(months)` 실제 구현 = `fact.period_start and fact.period_type=='duration'` 이고 개월수 months±1 통과. 즉 백로그 1단계의 "period_length=None 때문에 0" 은 부정확 — 실제 결손 원인은 오직 `by_period_type("duration")` 예외. 조치(quarterly 마이그레이션)는 그대로 옳다.
5. instant(BS) 전용 깨끗한 빌트인 없음. `latest_instant()` 는 concept당 최신 1개만 남겨 분기 히스토리에 부적합. → `facts.query().by_concept(C).execute()` 후 파이썬에서 `getattr(fact,'period_type',None)=='instant'` 필터가 정답.
6. FinancialFact 보고일 속성명은 코드에서 grep 확인 필요(filing_date / filed / accession 등). `_fact_to_row` 가 이미 읽는 속성(accession, period_end)과 실재 속성을 grep 으로 확인하고, 없으면 period_end 차선책으로 오름차순 정렬(최신이 마지막).
</locked_facts>

<interfaces>
<!-- 추출기·store 계약 (executor 가 직접 사용 — 코드베이스 탐색 불필요) -->

src/stocksig/io/edgar_client.py 현행 표면:
- _EDGAR_DURATION_CONCEPTS: tuple[(concept, field)] — Revenue/GrossProfit/OperatingIncomeLoss/NetIncomeLoss/EarningsPerShareDiluted/NetCashProvidedByUsedInOperatingActivities (6종)
- _EDGAR_INSTANT_CONCEPTS: tuple[(concept, field)] — StockholdersEquity/Liabilities/Assets (3종, field=total_equity/total_liabilities/total_assets)
- _query_facts(facts, concept, period_type, period_length) -> list  [현행: by_concept→by_period_type→by_period_length→execute, except 삼킴]
- _calendar_quarter_key(fact) -> str|None  [현행: get_display_period_key() 기반, YYYYQn fullmatch 최종 가드]
- _fact_to_row(ticker, field, fact, period_type) -> dict|None  [읽는 속성: numeric_value, unit, accession, period_start, period_end]
- _instant_fallback(facts, field) -> list  [유지 — total_assets/total_equity 헬퍼]
- fetch_edgar_quarterly_raw(ticker) -> list[dict]  [@throttled_edgar, get_facts 1회]

tests/fixtures/edgar_aapl_facts.py 현행 mock 표면:
- FakeQuery: by_concept/by_period_type/by_period_length/execute. store 키 = (concept, period_type).
- FakeFinancialFact: numeric_value/accession/unit/period_start/period_end/period_type/_display_key, get_display_period_key().
- AAPL_QUARTERLY_STORE: {(concept, period_type): [FakeFinancialFact]} — 유량 키 period_type="duration", BS 키 period_type="instant".

tests/conftest.py:
- _isolated_fundamentals_db (autouse): SQLite store 를 tmp_path 로 격리 — 운영 data/fundamentals.db 무오염.

fundamentals_store.fetch_raw_quarters(ticker) -> list[(quarter,source,field,value,period_type,reprt_code,unit)] (quarter 오름차순).
metrics_engine.compute_matrix(ticker) — fetch_raw_quarters 소비, 분기축 = raw 등장 분기 오름차순(최신=마지막 열).
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: edgartools 5.35.0 by_period_type 마이그레이션 + period_end 분기키 + WARNING + 정렬 (RED→GREEN)</name>
  <files>src/stocksig/io/edgar_client.py, tests/fixtures/edgar_aapl_facts.py, tests/test_edgar_quarterly.py</files>
  <behavior>
    네트워크 0(mocker.patch Company / FakeQuarterlyFacts·FakeFinancialFact 스텁만). 구조화된 값 단언만(렌더 텍스트 단언 금지). RED 먼저(마이그레이션 전 실패) → GREEN.

    - test_no_duration_instant_period_type_in_source: src 텍스트에 `by_period_type("duration")`·`by_period_type("instant")` 문자열이 0건이고 `by_period_type("quarterly")` 가 ≥1건(소스 단언, test_edgar_client.py L31 analog).
    - test_flow_concepts_use_quarterly: 유량 6종 추출 후 revenue/operating_cash_flow 등 행이 존재하고 period_type 라벨이 "duration"(저장값은 실제 fact.period_type 반영 — LOCKED FACT 1: quarterly 로 조회해도 fact 자체는 duration). FakeQuery 가 "quarterly" 키로 유량 행을 반환하도록 fixture 갱신.
    - test_instant_extracted_via_concept_filter: BS 3종(total_assets/total_equity/total_liabilities)이 by_concept 만으로(period_type 인자 없이) 취득되고 파이썬 instant 필터를 거쳐 period_type=="instant" 행으로 추출됨. concept 결과에 instant·duration 혼재 fact 를 넣어 instant 만 통과함을 단언.
    - test_calendar_quarter_key_from_period_end: period_end="2026-03-28" 인 fact → "2026Q1"(3월=Q1, (3-1)//3+1=1). period_end="2026-06-30" → "2026Q2". period_end 부재 + get_display_period_key="Q2 2026" → "2026Q2"(display 차선책). period_end·display 모두 부재 또는 "FY 2026" → None(fullmatch 가드).
    - test_query_facts_logs_warning_on_exception: _query_facts 가 내부 예외 시 빈 리스트를 반환하되 caplog 에 WARNING + concept 명이 남음(조용한 삼킴 제거). 단언은 caplog.records 의 levelno/message 구조값(렌더 텍스트 아님).
    - test_duplicate_facts_sorted_ascending: 같은 (quarter, field) 에 filing_date(또는 period_end) 가 다른 2 fact 를 줄 때, 반환 행에서 최신 fact 가 마지막에 오도록 정렬됨(upsert 마지막-쓰기 승 정합). 정렬 키는 LOCKED FACT 6 grep 으로 확인한 실재 속성.
    - 기존 test_edgar_quarterly.py 8종 + 260627-vpn _calendar_quarter_key 7종 회귀 유지(필요 시 period_end 기반으로 _FakeFact·단언 갱신 — 단 FY 라벨 거부·빈/None None 가드는 불변).
  </behavior>
  <action>
LOCKED FACTS 와 백로그 6단계(1~5단계, 6단계 재적재는 Task 3) 를 그대로 구현. RED 먼저 작성해 마이그레이션 전 실패 확인 후 GREEN.

1단계 — 유량: `fetch_edgar_quarterly_raw` 의 `_EDGAR_DURATION_CONCEPTS` 루프에서 `_query_facts(facts, concept, "quarterly", None)` 로 호출(period_type 인자 "quarterly", period_length 인자 제거). `_query_facts` 시그니처에서 `period_length` 파라미터와 `by_period_length` 분기를 제거(LOCKED FACT 3: quarterly=length3 동치 → 중복 제거). `_fact_to_row(..., "duration")` 의 저장 라벨은 유지(실제 fact.period_type 가 'duration' 이므로 — LOCKED FACT 1). period_type 라벨을 하드코딩 대신 `getattr(fact,'period_type',"duration")` 로 실제값 반영하는 것이 더 정확하나, 기존 테스트가 "duration" 을 기대하므로 유량은 "duration" 라벨 유지.

2단계 — 저량(BS): `_EDGAR_INSTANT_CONCEPTS` 루프를 `by_period_type` 미사용으로 변경. `facts.query().by_concept(concept).execute()` 결과를 받아 파이썬에서 `getattr(fact,'period_type',None)=='instant'` 인 fact 만 필터(LOCKED FACT 5). 빈 결과 시 기존 `_instant_fallback(facts, field)` 경로 유지. 이 concept-only 조회를 위해 `_query_facts` 를 재사용하되 period_type 필터를 옵션화하거나(예: period_type 인자가 None 이면 by_period_type 미적용), 별도 인라인 조회를 쓴다. 단순성을 위해 `_query_facts(facts, concept, period_type=None)` 호출 시 by_period_type 를 건너뛰고 by_concept→execute 만 하도록 정리하고, 호출부에서 파이썬 instant 필터를 적용.

3단계 — `_calendar_quarter_key`: 키 소스를 period_end 우선으로 교체. `getattr(fact,'period_end',None)` 가 있으면 ISO/date 파싱해 월 → `(month-1)//3+1` 분기, "YYYYQn" 산출. period_end 부재 시 기존 `get_display_period_key()` 차선책 경로(현행 "Q2 2026"/"2026 Q2"/"2026Q2" 정규화) 유지. 마지막 `re.fullmatch(r"\d{4}Q[1-4]", disp)` 가드는 그대로 유지(260627-vpn). docstring 을 'period_end 종료일 월 기준 캘린더 분기' 로 구현과 일치시킴. period_end 가 str("2026-03-28")·date 객체 양쪽 다 안전 파싱(이미 _iso_or_none 로 row 에 str 저장되나 fact.period_end 원본은 date 일 수 있음 — getattr 후 str() + 앞 7자 "YYYY-MM" 슬라이스 또는 datetime.fromisoformat 으로 robust 파싱, 실패 시 display 차선책으로 폴백).

4단계 — `_query_facts`: `except Exception: return []` 를 `except Exception as exc: logger.warning("EDGAR query 실패 concept=%s (%s)", concept, type(exc).__name__); return []` 로 변경. 결손은 여전히 빈 리스트(추출 전체가 죽지 않음). 예외 원문/PII 보간 금지 — concept·예외타입명만(코드베이스 T-04-03 컨벤션).

5단계 — 중복 정렬: LOCKED FACT 6 대로 먼저 grep 으로 FinancialFact 의 보고일 실재 속성 확인(`grep -rn "filing_date\|filed\|accession" .venv/Lib/site-packages/edgar/entity/` 또는 edgartools FinancialFact 정의). 실재 속성(filing_date 우선)이 있으면 그 키로, 없으면 period_end 로 동일 (quarter, field) 묶음을 오름차순 정렬해 최신/정정값이 마지막에 오게(upsert 마지막-쓰기 승 정합). 정렬은 fetch_edgar_quarterly_raw 가 rows 를 쌓은 뒤, 또는 _query_facts 결과 fact 리스트 단계에서 안정 정렬(sorted with key, None-safe — 키 부재 fact 는 빈 문자열로 최하위). field 별로 같은 quarter 가 여러 fact 면 마지막이 최신이 되도록.

fixture 갱신(tests/fixtures/edgar_aapl_facts.py):
- AAPL_QUARTERLY_STORE 의 유량 키를 (concept, "duration") → (concept, "quarterly") 로 이동(유량은 이제 quarterly 로 조회). FakeQuery.by_period_type 가 "quarterly" 를 받도록 — 현 FakeQuery 는 period_type 을 그대로 키로 쓰므로 store 키만 바꾸면 동작.
- BS(instant) 는 이제 by_concept 만으로 조회되고 period_type 인자가 없음 → FakeQuery.execute 가 period_type=None 일 때 concept 의 모든 period_type 행을 반환하도록 store 구조/조회 로직 조정. 단순화: BS concept 행을 (concept, None) 또는 concept 단독 키로 저장하거나, FakeQuery 가 period_type 미설정 시 해당 concept 의 전체 fact(instant+duration 혼재 가능) 반환 → 추출기 파이썬 instant 필터가 instant 만 통과시킴을 fixture 로 입증(혼재 fact 1개 추가).
- FakeFinancialFact 에 보고일 속성(예: filing_date) 추가 정렬 검증용. period_end 가 정렬·분기키 양쪽에 쓰이므로 기존 period_end 값 유지하되 일부 분기를 period_end 로 명확화(예 Revenue 2026Q1=period_end "2025-12-31", 2026Q2="2026-03-28").
- 기존 8 테스트가 기대하는 "2026Q2"/"2026Q1" quarter 가 period_end 기반으로도 동일하게 나오는지 확인(2026-03-28→Q1, 2025-12-31→Q4 주의! 캘린더 월 기준이면 12월=Q4=2025Q4). **중요**: 기존 테스트 test_quarter_key_normalized_yyyyqn 이 "2026Q1"·"2026Q2" 를 기대하는데 period_end 캘린더 월 기준으로 바뀌면 fiscal AAPL 분기가 달라질 수 있음 → fixture period_end 값을 캘린더 분기와 정합하게 조정하고, 테스트 단언도 period_end 기반 캘린더 분기로 갱신(예: period_end "2026-03-28"→"2026Q1", "2026-06-30"→"2026Q2"). docstring 계약(period_end 월 기준)이 진실원천이므로 테스트를 그에 맞춤.

코드베이스 컨벤션 엄수: 한국어 주석/로그, 결손=None(0/-999999 금지), 네트워크 0 테스트, 구조화된 값 단언.
  </action>
  <verify>
    <automated>uv run python -m pytest tests/test_edgar_quarterly.py tests/test_edgar_client.py -x -q</automated>
  </verify>
  <done>마이그레이션 회귀 테스트 RED→GREEN 통과. `by_period_type("duration")`/`("instant")` grep 0건, `by_period_type("quarterly")` ≥1건. _calendar_quarter_key period_end 월 기반 YYYYQn 산출(부재 시 display 차선책, FY/빈/None→None). _query_facts WARNING 로깅(빈 리스트 반환 유지). 중복 (quarter,field) 정렬로 최신 마지막. fixture 갱신 후 기존 단언 정합.</done>
</task>

<task type="auto">
  <name>Task 2: 전 스위트 GREEN + 시트1 색 신호 0줄 변경 잠금 (Core Value 불변)</name>
  <files>tests/test_edgar_quarterly.py</files>
  <action>
Task 1 의 마이그레이션이 다른 경로(metrics_engine·history_render·시트1)에 회귀를 일으키지 않는지 전 스위트로 확인하고, Core Value(시트1 색 신호) 불변을 git diff 로 잠근다.

1. 전 스위트 실행: `uv run python -m pytest -q`. 회귀 0(GREEN). 실패 시 Task 1 로 돌아가 수정(이 plan 범위 내). baseline 은 직전 커밋 353 passed(+선존 deferred 3종 — test_history_render CLI 디스패치 `No module named 'main'` sys.path 아티팩트는 본 plan 무관, 사전 존재 → 무시·동일 재현 확인).

2. Core Value 불변 git diff 잠금: 본 수정은 history/store 경로 전용이므로 시트1 산출물 코드가 한 줄도 바뀌지 않아야 한다. `git diff --stat HEAD -- src/stocksig/output/sheet_portfolio.py src/stocksig/output/writer.py` 와 color_rules(`git ls-files | grep color_rules` 로 실경로 확인 후 동일 diff)가 빈 출력임을 확인. 변경이 잡히면 즉시 되돌림.

3. (선택, 이미 존재하면 재사용) 260627-vpn 이 도입한 시트1 σ-bucket 색 불변 회귀 테스트(test_sigma_color_unchanged_after_migration analog)가 여전히 GREEN 인지 확인 — 펀더멘털 경로 변경이 시트1 폰트색 hex 에 누출되지 않음. 신규 시트1 색 테스트는 추가하지 않는다(기존 잠금 재사용 — 중복 회피). test_edgar_quarterly.py 에는 Task 1 신규 테스트만 둔다.

코드 수정은 Task 1 에 한정 — 이 태스크는 검증·잠금 전용(시트1 코드 0줄 변경 보장). .planning/STATE.md·문서 커밋 금지(commit_docs=false).
  </action>
  <verify>
    <automated>uv run python -m pytest -q && git diff --stat HEAD -- src/stocksig/output/sheet_portfolio.py src/stocksig/output/writer.py</automated>
  </verify>
  <done>전 스위트 GREEN(회귀 0, 선존 deferred 3종 동일 재현). `git diff sheet_portfolio.py·writer.py·color_rules` 빈 출력 — 시트1 색 신호·레이아웃 0줄 변경(Core Value 불변). Task 1 코드만 변경됨.</done>
</task>

<task type="auto">
  <name>Task 3: delta_state EDGAR 행 정리 + 표본 재적재 검증 (라이브 — best-effort)</name>
  <files>(데이터 단계 — 코드 산출물 없음. data/fundamentals.db 갱신은 라이브 의존)</files>
  <action>
**라이브 EDGAR 네트워크 의존 데이터 단계.** 시도하고, 네트워크/rate-limit 실패 시 안전 흡수 + SUMMARY 에 명기(코드·테스트 산출물은 Task 1~2 로 이미 완료·커밋 가능).

전제(LOCKED): delta_state(TSLA,EDGAR).last_accession 이 현재 최신 10-Q accession 과 동일 → sync_ticker_history 가 무조건 SKIP. EDGAR 행을 먼저 비워야 재추출됨.

1. delta_state EDGAR 행 정리 — quick 260627-vpn 선례처럼 **표준 라이브러리 sqlite3 인라인 스크래치 일회성**(레포에 스크립트 영구 추가 금지). 운영 DB 경로는 `data/fundamentals.db`(상대경로, 프로젝트 루트 실행). 예: `uv run python -c "import sqlite3; c=sqlite3.connect('data/fundamentals.db'); n=c.execute(\"DELETE FROM delta_state WHERE source='EDGAR'\").rowcount; c.commit(); print('deleted', n); c.close()"`. (또는 last_accession=NULL UPDATE — 둘 다 다음 sync 가 델타 MISS 로 재추출하게 함.)

2. 표본 재동기화 — 전수(~88종목)는 throttle 로 수 분 소요 가능하므로 검증은 **표본(AAPL, TSLA, MSFT 등 소수)** 으로 충분(검증 기준 "AAPL 등"). 표본 재동기화는 sync_ticker_history 를 직접 호출하는 스크래치 인라인으로:
   `uv run python -c "from stocksig.io.fundamentals_delta import sync_ticker_history; [sync_ticker_history(t,'EDGAR') for t in ('AAPL','TSLA','MSFT')]"`
   (라이브 EDGAR — set_identity 는 import-time 1회 적용됨. throttle 자동.)

3. 검증 — store 에서 표본의 raw_facts 가 분기×9필드(EDGAR 자연결손 Q4 제외한 유효 분기×필드)를 갖는지 구조 확인:
   `uv run python -c "from stocksig.io import fundamentals_store as s; import collections; rows=s.fetch_raw_quarters('AAPL'); f=collections.Counter(r[2] for r in rows); print('AAPL fields:', dict(f)); print('quarters:', sorted({r[0] for r in rows}))"`
   기대: revenue/gross_profit/op_income/net_income/eps/operating_cash_flow/total_equity/total_liabilities/total_assets(+shares_outstanding) 다수 분기. 종전 종목당 1행(shares_outstanding 만)에서 분기×다필드로 회복.

4. (선택, 라이브 성공 시) history xlsx 재생성으로 US 트렌드 셀이 더 이상 전부 "-" 가 아님 확인:
   `uv run python main.py history` → `output/fundamentals_history_YYYYMMDD.xlsx` 의 US 종목 지표 셀 채워짐(육안/구조 확인). 라이브 실패 시 생략.

5. 전수(~88종목) 재동기화 + 갱신된 data/fundamentals.db 커밋은 라이브 의존 — 실행자가 `uv run python main.py`(SYNC 단계가 재추출·upsert) 로 시도하고, 성공 시 data/fundamentals.db 변경을 **코드 커밋과 별개의 데이터 커밋**(commit_docs=false 는 .planning 문서 금지이며 data/ 는 git 추적 — STATE 명시 "git 추적, 멀티 PC 동기화")으로 남기되, 실패/중단 시 안전 흡수하고 SUMMARY 에 "표본만 검증·전수 재동기화는 다음 main.py 실행에서 forward 누적" 으로 명기.

**안전 규칙:** 모든 라이브 단계는 try 후 실패 시 흡수(기존 DB 유지 — sync_ticker_history 가 이미 부분추출/예외 안전 흡수). delta_state EDGAR 행 삭제는 멱등(다음 sync 가 재기록). 라이브 0회 성공이어도 Task 1~2 의 코드·테스트 산출물은 독립적으로 완료·커밋 가능(이 plan 의 핵심 deliverable).
  </action>
  <verify>
    <automated>uv run python -c "from stocksig.io import fundamentals_store as s; import collections; rows=s.fetch_raw_quarters('AAPL'); print('field_count', len(set(r[2] for r in rows)), 'quarter_count', len(set(r[0] for r in rows)))"</automated>
  </verify>
  <done>delta_state EDGAR 행 정리(삭제 또는 last_accession NULL) 후 표본(AAPL 등) 재동기화 시도. 성공 시 AAPL 등이 raw_facts 에 분기×다필드(≥6 field, 다수 분기)를 가짐 — 종전 종목당 1행에서 회복. 라이브 실패 시 안전 흡수 + SUMMARY 명기(코드·테스트는 독립 완료). 전수 재동기화/data/fundamentals.db 데이터 커밋은 main.py 시도 후 best-effort.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| edgartools API → 추출기 | 외부 라이브러리 어휘 변경(by_period_type)이 조용히 결손을 유발 — 이번 사고의 근본. WARNING 로깅으로 가시화. |
| 라이브 EDGAR → data/fundamentals.db | 네트워크/rate-limit 실패가 데이터 단계(Task 3)에 영향. sync_ticker_history 안전 흡수로 기존 DB 보존. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-hec-01 | Tampering | _calendar_quarter_key period_end 파싱 | mitigate | period_end 파싱 실패 시 display 차선책 + YYYYQn fullmatch 가드(비분기 입력 None) — metrics_engine 분기축 int() 오염 차단 |
| T-hec-02 | Denial of Service | _query_facts 예외 | mitigate | 예외를 WARNING 로깅 후 빈 리스트 반환 — 단일 concept 실패가 추출 전체를 죽이지 않음 |
| T-hec-03 | Information Disclosure | 예외/probe 로그 | accept | type(exc).__name__·concept 만 로깅(원문/PII 보간 금지, T-04-03 컨벤션) |
| T-hec-04 | Tampering | data/fundamentals.db 라이브 재적재 | mitigate | sync_ticker_history 부분추출/예외 안전 흡수(기존 DB 유지) + delta_state 삭제 멱등 |
| T-hec-SC | Tampering | 패키지 설치 | accept | 신규 패키지 설치 0(edgartools 5.35.0 이미 설치·확정, 표준 라이브러리 sqlite3 인라인만) — 설치 게이트 불필요 |
</threat_model>

<verification>
- `uv run python -m pytest -q` GREEN (회귀 0, 선존 deferred 3종 동일 재현).
- `by_period_type("duration")`·`by_period_type("instant")` grep 0건 / `by_period_type("quarterly")` ≥1건.
- `_calendar_quarter_key` period_end 월 기반 YYYYQn (부재 시 display 차선책, FY/빈/None → None — fullmatch 가드 유지).
- `_query_facts` WARNING 로깅(빈 리스트 반환 유지).
- 중복 (quarter, field) 정렬 — 최신/정정값이 마지막(upsert 마지막-쓰기 승 정합).
- `git diff sheet_portfolio.py·writer.py·color_rules` 빈 출력 — 시트1 색 신호·레이아웃 0줄 변경 (Core Value 불변).
- (라이브 best-effort) 표본 raw_facts 가 분기×다필드 회복.
</verification>

<success_criteria>
- US(EDGAR) 펀더멘털 결손 근본 원인(by_period_type "duration"/"instant" ValidationError) 제거 — quarterly 마이그레이션 + by_concept+파이썬 instant 필터.
- _calendar_quarter_key period_end 월 기반 + WARNING 로깅 + 중복 정렬.
- 전 스위트 GREEN, 회귀 0.
- Core Value(시트1 색 신호) 0줄 변경 — git diff 빈 출력.
- 표본 재적재로 US 종목 raw_facts 회복(라이브 성공 시) 또는 안전 흡수 + SUMMARY 명기.
</success_criteria>

<output>
Create `.planning/quick/260629-hec-edgartools-5-35-0-by-period-type-migrati/260629-hec-SUMMARY.md` when done.
실행자는 **코드만** 원자 커밋(.planning 문서·STATE.md·PLAN/SUMMARY 커밋 금지 — 오케스트레이터 처리). data/fundamentals.db 데이터 갱신은 라이브 성공 시 별개 데이터 커밋(best-effort).
</output>
