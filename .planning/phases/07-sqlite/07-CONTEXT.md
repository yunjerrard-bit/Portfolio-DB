# Phase 7: 펀더멘털 SQLite 저장 + 접수번호 델타 - Context

**Gathered:** 2026-06-18
**Status:** Ready for planning

<domain>
## Phase Boundary

매 실행 시 각 종목의 **분기별 펀더멘털 원천(raw)** 을 `data/fundamentals.db`(SQLite)에 영구 누적 저장하고(FUND-07), 저장된 `last_accession`(EDGAR accession / DART `rcept_no`)과 최신 접수번호를 가벼운 조회로 비교해 **변경이 있을 때만** 전체 facts를 재추출·누적하는 저장·델타 인프라(FUND-08). 평소(변경 없음) 실행에서 히스토리 경로의 외부 펀더멘털 호출이 ≈0에 수렴한다.

**In scope:** raw long 테이블 + state 테이블 생성/누적, 접수번호 기반 델타 감지·가벼운 probe, 첫 실행 backfill, `.gitignore` 처리, 기존 `.cache/`와 분리.

**Out of scope (다른 phase):** 지표 registry 계산(PER/PEG/ROE/PBR 등) = Phase 8 / 트렌드 엑셀 렌더 = Phase 9 / 시트1 통합 store·registry 이관 + 7일 캐시 제거 = Phase 10. 시트1 `portfolio_*.xlsx` 레이아웃·색 신호(Core Value)는 **불변**.

</domain>

<decisions>
## Implementation Decisions

### 첫 실행 backfill 깊이
- **D-01:** 소스별 차등 backfill. 첫 실행(DB 빈 상태)에서 EDGAR는 `EntityFacts` fetch에 딸려오는 과거 분기를 **전부 저장**(별도 호출 없음 — 사실상 공짜), DART는 **최근 3년(~12분기)** 만 backfill(연도별 `finstate_all` 호출 비용·쿼터 고려).
- **D-02:** backfill 이후에는 매 실행 forward 누적(델타가 없으면 신규 저장 없음).

### raw 원천 필드 범위
- **D-03:** 분기별 raw로 저장할 원천 = 슈퍼셋+: 매출·매출총이익·영업이익·순이익·EPS·자본총계·부채총계·발행주식수 + **영업현금흐름·총자산**. 미래 지표(ROE/PBR/부채비율/ROA/FCF 등)를 외부 재호출 없이 Phase 8에서 계산하기 위함(백로그 D-H2 슈퍼셋 권고 + ROA/FCF 확장).
- **D-04:** 현재 EDGAR 클라이언트(`edgar_client.py`)는 손익 4종 TTM만 가져옴 → BS 항목(StockholdersEquity·Liabilities·shares outstanding)·현금흐름·총자산의 **신규 분기 추출 경로** 필요.
- **D-05:** raw 테이블에는 **소스가 보고한 원뎌(as-reported)** 를 그대로 저장 — EDGAR는 period 단위 값, DART는 YTD 누적값 + period 메타. 분기 분해(DART YTD−직전Q, EDGAR Q4=FY−9M)는 **계산 시점(Phase 8)** 에서 수행. 원천은 복원 가능하게 보존(잘못 분해해도 원천 안전).

### 7일 캐시와 공존 방식
- **D-06:** 완전 별도 **additive 경로**. Phase 7은 새 store/델타 모듈(히스토리 전용)만 추가하고, 기존 시트1 fundamentals 경로·`.cache/fundamentals` 7일 TTL은 **건드리지 않음**. ≈0 호출 주장은 히스토리 경로에 적용. 통합·중복 제거는 Phase 10(FUND-11) 범위.
- **D-07:** 분기 경계(새 공시/정정공시)에서 히스토리 경로와 시트1 경로의 **이중 외부 호출 허용** — 드문 이벤트이고 구현 단순·시트1 회귀 위험 0. Phase 10 단일 원천 통합 시 자연 해소.

### 분기 키 정규화
- **D-08:** canonical 분기 키 = **캘린더 분기 정규화**. period 종료일 기준으로 해당 캘린더 분기(2026Q2 = 4~6월)에 매핑. 모든 종목 열이 같은 시점으로 정렬(교차 비교·매트릭스 가독성). fiscal≠calendar 기업(예 9월 결산)도 일관 정렬.
- **D-09:** raw 테이블 유니크 키 = `(ticker, source, 캘린더분기, field)`. 정정공시(같은 분기·새 accession) 재추출 시 **최신값 upsert(덮어쓰기)** + accession 메타 갱신. 정정 이력은 보존하지 않음(매트릭스 = 최신 진실).

### 잠긴 결정 (백로그 D-H1~H4 / STATE.md — 재논의 안 함, planner 입력)
- 저장소 = SQLite `data/fundamentals.db`, TTL 없음, `.gitignore`, 기존 `.cache/`(OHLCV 24h / fund 7d / company 30d)와 별개 (D-H3).
- 델타 키 = 접수번호(EDGAR accession / DART `rcept_no`); 단순 분기 라벨은 정정공시 누락 → 접수번호 사용 (D-H1).
- 가벼운 조회 = DART `list` API / EDGAR 메타(filings). 같으면 전체호출 생략, 다르면 새 분기 또는 정정공시 → 전체 facts 재추출·누적·`last_accession` 갱신 (D-H1).
- raw 테이블 컬럼 시작점: `(ticker, source, quarter, accession_or_rcept, field, value, fetched_at)` / state: `(ticker, source, last_accession, last_checked_at)` (D-H3).
- 폴백 소스(yf/Naver)는 접수번호 개념 없음 → 분기 라벨로 보완, 폴백 값은 "다음 1차 성공 시 갱신" (D-H1, D-07 소수 전용).

### Claude's Discretion
- delta probe 실패(네트워크/DART 쿼터 초과/EDGAR 메타 오류) 시 처리: 안전 폴백(probe 실패 = "변경 불확실 → 이번 실행 갱신 생략, 기존 DB 유지" 또는 보수적 재추출) — researcher가 비용·정확도 트레이드오프 조사 후 planner 결정.
- SQLite 스키마 세부(PK/인덱스, value 타입 REAL vs TEXT, period 메타 컬럼명, source enum), 동시 쓰기 lock(기존 `cache.py` double-checked lock 패턴 참고 — ThreadPoolExecutor fan-out 하 lost-update 방지), upsert SQL 구문 — 모두 planner/executor 재량.
- 신규 모듈 분리(`fundamentals_store.py` + `fundamentals_delta.py` 등) 및 호출 진입점(main_run) — planner 결정.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 권위 설계 입력 (LOCKED)
- `.planning/backlog/fundamentals-history-delta.md` — D-H1~D-H4 locked 설계(델타 키·원천 저장·SQLite·엑셀 출력). 본 phase의 1차 권위 입력. raw/state 스키마, TTM 유형(저량/유량/하이브리드), 구현 디테일 메모(EDGAR Q4 보정·DART YTD 분해·TTM 결손 정책) 포함.
- `.planning/ROADMAP.md` §"Phase 7" — Goal·Success Criteria 5종·의존(Phase 3).
- `.planning/REQUIREMENTS.md` §"FUND-07 / FUND-08" — 본 phase 수용 요구사항.
- `.planning/STATE.md` §"v1.3 기술 컨텍스트" / "Decisions (locked)" — 의존 fetch 층 목록·델타 키·지표 유형·불변 제약.

### 의존 코드 (Phase 3 fetch 층 — 그 위에 저장·델타 추가)
- `src/stocksig/io/edgar_client.py` — EDGAR `EntityFacts` 취득(현재 손익 4종 TTM만; BS·현금흐름·발행주식수·per-quarter raw 추출 신규 필요). set_identity import-time 1회 패턴.
- `src/stocksig/io/dart_client.py` — DART `finstate_all` + account 매핑 + status 가드 + YTD 처리 시작점.
- `src/stocksig/io/dart_account_map.py` — `DART_ACCOUNT_ID_MAP`(account_id 1차)/`DART_ACCOUNT_MAP`(account_nm 2차) — 신규 raw 필드의 소스별 매핑 확장 기준점.
- `src/stocksig/io/fundamentals.py` — 현 펀더멘털 오케스트레이터(MetricCell/provenance/폴백 라우팅). **Phase 7은 건드리지 않음**(additive). Phase 10 통합 시 진입점.
- `src/stocksig/io/cache.py` — diskcache 7d fund 캐시 + double-checked locking 싱글톤 패턴(WR-04). SQLite store 동시성·hit/miss 카운터 설계 참고. SQLite store는 이와 **별개**.
- `.gitignore` — `data/fundamentals.db` 추가 대상(현재 `.cache/` 등재됨, `data/` 미등재 → 신규 라인 필요).

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cache.py` double-checked locking 싱글톤(`_cache_lock`) + 모듈 레벨 hit/miss 카운터(`_stats` + `_stats_lock`): SQLite 연결 싱글톤·델타 hit(생략)/miss(재추출) 집계에 동일 패턴 재사용 가능.
- `dart_account_map.py` 매핑 구조(id 1차/nm 2차): 신규 raw 필드(자본총계·부채총계·총자산·영업현금흐름·발행주식수)의 DART account 매핑 확장 시작점.
- `dart_client.py`의 `_parse_amount`(쉼표 문자열 → int, None-safe), `_income_rows`(sj_div 필터), status 가드(`_STATUS_NOTES`): 신규 BS/CF 행 추출에 재사용.

### Established Patterns
- 결손값 = `None`(0/-999999 금지, D-05) — raw 저장 시에도 동일 유지. value 컬럼 NULL 허용.
- import-time set_identity 1회(per-call 금지, edgar_client.py); throttle 데코레이터(`@throttled_edgar`/`@throttled_dart` 2 RPS).
- `diskcache.Cache`가 이미 SQLite 기반 — `sqlite3` 표준 라이브러리 직접 사용과 일관(백로그 D-H3 근거).

### Integration Points
- 신규 store/델타 모듈 → main 실행 흐름(`main.py`/runner)에서 종목별로 호출(히스토리 전용 경로). 시트1 펀더멘털 셀·OHLCV 파이프라인과는 분리.
- EDGAR/DART 클라이언트에 **per-quarter raw 추출** 함수 신규 추가(기존 TTM 함수는 시트1용으로 유지).

</code_context>

<specifics>
## Specific Ideas

- "평소 실행 외부 호출 ≈0"의 정확한 의미: 변경 없는 종목은 **가벼운 list/메타 probe만** 발생(전체 facts 호출 생략). probe 자체는 호출로 인정하되 비용이 낮음.
- 첫 실행 후 DB는 EDGAR 종목은 수년치, DART 종목은 ~3년치 분기가 채워져 Phase 9 트렌드 매트릭스가 즉시 의미 있게 표시될 수 있어야 함.
- raw 슈퍼셋은 "추후 신규 지표 추가 시 재호출 0"이 목적 — 필드를 인색하게 잡지 말 것(현금흐름·총자산까지 포함 결정).

</specifics>

<deferred>
## Deferred Ideas

- 지표 registry(저량/유량 TTM/하이브리드) 정의 + PER/PEG/GPM/OPM·ROE·PBR 계산 → **Phase 8(FUND-09)**.
- `fundamentals_history.xlsx` 트렌드 엑셀 렌더(지표별 매트릭스 + [원천] + [최신 스냅샷]) → **Phase 9(FUND-10)**.
- 시트1 PER/PEG/GPM/OPM을 통합 store/registry로 이관 + 구 `_compute_*`·7일 캐시 중복 제거(단일 원천) → **Phase 10(FUND-11)**.
- 정정공시 이력 보존(audit trail) — 이번엔 최신값 upsert로 결정. 필요해지면 별도 이력 테이블 추가 가능(raw 원천 보존되므로 추후 도입 비파괴적).
- 폴백 소스(yf/Naver) 분기 라벨 보완의 세부 정책(분기 추정·다음 1차 성공 시 갱신) — 주로 소수 종목, planner 검토.

</deferred>

---

*Phase: 7-sqlite*
*Context gathered: 2026-06-18*
