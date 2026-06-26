# Phase 7: 펀더멘털 SQLite 저장 + 접수번호 델타 - Research

**Researched:** 2026-06-18
**Domain:** SQLite 영구 히스토리 저장 + 접수번호(EDGAR accession / DART rcept_no) 기반 델타 추출, EDGAR EntityFacts per-quarter 추출, DART finstate_all 분기 백필
**Confidence:** HIGH (의존 라이브러리 API를 설치본 소스에서 직접 검증 — edgartools 5.35.0 / OpenDartReader 0.3.2)

## Summary

Phase 7은 기존 Phase 3 fetch 층(`edgar_client.py`/`dart_client.py`) 위에 **additive**로 두 개의 신규 모듈(`fundamentals_store.py` SQLite 저장/델타 + per-quarter raw 추출 함수)을 얹는다. 기존 시트1 펀더멘털 경로·`.cache/` 7일 캐시는 건드리지 않는다(D-06). 핵심 기술은 (1) `sqlite3` 표준 라이브러리 + WAL + `INSERT ... ON CONFLICT ... DO UPDATE` upsert, (2) edgartools `EntityFacts.query()` 빌더로 BS/CF/발행주식수의 per-quarter 값을 accession·period_end와 함께 추출, (3) DART `list` API(`list.json`)로 최신 `rcept_no`만 싸게 probe.

**가장 중요한 발견 3가지 (모두 설치본 소스 검증):**
1. **EDGAR per-quarter 추출은 사실상 공짜 (D-01 검증됨)** — `Company(ticker).get_facts()`가 반환하는 `EntityFacts`의 모든 `FinancialFact`는 이미 `period_start/period_end/period_type('instant'|'duration')/fiscal_year/fiscal_period/filing_date/accession/numeric_value`를 들고 있다. `facts.query().by_concept(...).by_period_type('duration').execute()`로 분기별 손익/현금흐름, `by_period_type('instant')`로 BS 시점값과 발행주식수를 한 번의 facts fetch에서 전부 추출한다. **별도 호출 없음.**
2. **D-08 캘린더 분기 정규화는 edgartools가 이미 구현** — `FinancialFact.get_display_period_key()`가 `period_end.month → Q1(1-3)/Q2(4-6)/Q3(7-9)/Q4(10-12)` 매핑을 정확히 수행한다(`models.py` L131-170). DART 측은 `bsns_year` + `reprt_code`(11013=1Q/11012=반기/11014=3Q/11011=연간)에서 동일 로직을 직접 구현하면 된다.
3. **접수번호는 full-fetch에 무료로 딸려온다** — EDGAR는 각 `FinancialFact.accession`, DART `finstate_all` 응답은 매 행에 `rcept_no` 컬럼(검증: fixture `dart_005930_finstate.py` COLUMNS[0]). 따라서 full-fetch 시 `last_accession` 갱신은 추가 호출 0.

**Primary recommendation:** 신규 모듈 `src/stocksig/io/fundamentals_store.py`(sqlite3 WAL 싱글톤 + upsert + 델타 비교)와, `edgar_client.py`/`dart_client.py`에 `fetch_*_quarterly_raw()` + `probe_*_accession()` 함수를 **추가**. `cache.py`의 double-checked locking 싱글톤 패턴을 SQLite 연결에 재사용. DART 델타 probe는 `dart.list(corp, kind='A')`의 최신 `rcept_no` 1건 비교. EDGAR 델타 probe는 `Company(ticker).latest("10-Q")` accession 비교(또는 facts 1회 fetch가 어차피 필요하면 probe 생략). delta probe 실패 시 **"갱신 생략, 기존 DB 유지"** 권고(아래 §Common Pitfalls 참조).

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** 소스별 차등 backfill. 첫 실행(DB 빈 상태)에서 EDGAR는 `EntityFacts` fetch에 딸려오는 과거 분기를 **전부 저장**(별도 호출 없음 — 사실상 공짜), DART는 **최근 3년(~12분기)** 만 backfill.
- **D-02:** backfill 이후에는 매 실행 forward 누적(델타가 없으면 신규 저장 없음).
- **D-03:** 분기별 raw 저장 원천 = 슈퍼셋+: 매출·매출총이익·영업이익·순이익·EPS·자본총계·부채총계·발행주식수 + **영업현금흐름·총자산**.
- **D-04:** 현재 `edgar_client.py`는 손익 4종 TTM만 → BS(StockholdersEquity·Liabilities·shares outstanding)·현금흐름·총자산의 **신규 분기 추출 경로** 필요.
- **D-05:** raw 테이블에는 **소스가 보고한 원뎌(as-reported)** 그대로 저장 — EDGAR는 period 단위 값, DART는 YTD 누적값 + period 메타. 분기 분해는 **Phase 8(계산 시점)**. 결손값 = `None`(0/-999999 금지), value 컬럼 NULL 허용.
- **D-06:** 완전 별도 **additive 경로**. 기존 시트1 fundamentals 경로·`.cache/fundamentals` 7일 TTL은 **건드리지 않음**. ≈0 호출 주장은 히스토리 경로에 적용.
- **D-07:** 분기 경계에서 히스토리 경로와 시트1 경로의 **이중 외부 호출 허용**.
- **D-08:** canonical 분기 키 = **캘린더 분기 정규화**(period 종료일 기준, 2026Q2=4~6월).
- **D-09:** raw 테이블 유니크 키 = `(ticker, source, 캘린더분기, field)`. 정정공시 재추출 시 **최신값 upsert(덮어쓰기)** + accession 메타 갱신. 정정 이력 보존 안 함.
- **(LOCKED 백로그 D-H1~H4 / STATE.md):**
  - 저장소 = SQLite `data/fundamentals.db`, TTL 없음, `.gitignore`, 기존 `.cache/`와 별개 (D-H3).
  - 델타 키 = 접수번호(EDGAR accession / DART `rcept_no`) (D-H1).
  - 가벼운 조회 = DART `list` API / EDGAR 메타(filings). 같으면 전체호출 생략, 다르면 재추출 (D-H1).
  - raw 컬럼 시작점: `(ticker, source, quarter, accession_or_rcept, field, value, fetched_at)` / state: `(ticker, source, last_accession, last_checked_at)` (D-H3).
  - 폴백 소스(yf/Naver)는 접수번호 개념 없음 → 분기 라벨 보완, "다음 1차 성공 시 갱신" (D-H1, D-07 소수 전용).

### Claude's Discretion
- delta probe 실패(네트워크/DART 쿼터 초과/EDGAR 메타 오류) 시 처리: 안전 폴백("변경 불확실 → 갱신 생략, 기존 DB 유지") vs 보수적 재추출 — researcher가 트레이드오프 조사 후 planner 결정. **→ 본 RESEARCH 권고: §Common Pitfalls Pitfall 2 참조.**
- SQLite 스키마 세부(PK/인덱스, value 타입 REAL vs TEXT, period 메타 컬럼명, source enum), 동시 쓰기 lock(`cache.py` double-checked lock 패턴 참고), upsert SQL 구문 — planner/executor 재량. **→ 본 RESEARCH 권고: §Standard Stack, §Code Examples.**
- 신규 모듈 분리(`fundamentals_store.py` + `fundamentals_delta.py` 등) 및 호출 진입점(main_run) — planner 결정.

### Deferred Ideas (OUT OF SCOPE)
- 지표 registry(저량/유량/하이브리드) + PER/PEG/GPM/OPM·ROE·PBR 계산 → **Phase 8(FUND-09)**.
- `fundamentals_history.xlsx` 트렌드 엑셀 렌더 → **Phase 9(FUND-10)**.
- 시트1 PER/PEG/GPM/OPM 통합 store/registry 이관 + 구 `_compute_*`·7일 캐시 중복 제거 → **Phase 10(FUND-11)**.
- 정정공시 이력 보존(audit trail) — 이번엔 최신값 upsert. (raw 원천 보존되므로 추후 비파괴 도입 가능)
- 폴백 소스(yf/Naver) 분기 라벨 보완 세부 정책 — 소수 종목, planner 검토.
- **분기 분해 계산 (DART YTD−직전Q, EDGAR Q4=FY−9M) → Phase 8.** Phase 7은 as-reported 원천만 저장(D-05).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FUND-07 | 매 실행 시 분기별 펀더멘털 원천 항목이 `data/fundamentals.db`에 영구 누적, 과거 분기 보존(TTL 없음) | sqlite3 WAL + `INSERT...ON CONFLICT DO UPDATE`(§Code Examples), EDGAR `facts.query().by_period_type` per-quarter 추출, DART `finstate_all` 분기 백필. TTL 없음 = expire 컬럼 없음(diskcache 패턴과 정반대). |
| FUND-08 | `last_accession`과 최신 접수번호 비교로 변경 없으면 전체 호출 생략, 변경 시만 재추출 — 평소 외부 호출 ≈0 | EDGAR `Company.latest("10-Q").accession_number` / DART `dart.list(corp,kind='A')`의 최신 `rcept_no` 1건 probe. state 테이블 `last_accession` SELECT 1회 비교(§Architecture Pattern 2). |
</phase_requirements>

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 분기별 raw 원천 영구 저장 | Database/Storage (sqlite3 `data/fundamentals.db`) | — | 200종목 규모 비교·집계·델타 SELECT 1회. 단일 파일·표준 라이브러리(D-H3 근거). |
| EDGAR per-quarter facts 추출 | API/Backend (`edgar_client.py` 신규 함수) | — | EntityFacts query 빌더. 기존 TTM 함수는 시트1용으로 유지(additive). |
| DART 분기 finstate_all 백필 | API/Backend (`dart_client.py` 신규 함수) | — | finstate_all + reprt_code 분기 코드. 기존 손익 추출 헬퍼 재사용. |
| 접수번호 델타 probe | API/Backend (신규 probe 함수) | Database/Storage (state 비교) | 가벼운 메타 호출 후 state 테이블 비교. |
| 동시 쓰기 직렬화 | Database/Storage (WAL + 연결 싱글톤 lock) | — | ThreadPoolExecutor(max_workers=4) fan-out 하 lost-update 방지. |
| 히스토리 경로 오케스트레이션 | API/Backend (`main_run.run`에서 종목별 호출) | — | 시트1·OHLCV 파이프라인과 분리된 별도 경로(D-06). |

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` (stdlib) | Python 3.13 내장 | raw long + state 테이블, upsert, 델타 SELECT | [VERIFIED: Python stdlib] 추가 의존성 0. `INSERT...ON CONFLICT`(SQLite 3.24+, Python 3.13 번들 SQLite는 3.45+) 지원. WAL 모드로 동시 read/write. D-H3 근거: diskcache가 이미 sqlite 기반이라 일관. |
| `edgartools` (import `edgar`) | 5.35.0 (설치본) | EntityFacts per-quarter 추출 + 최신 accession probe | [VERIFIED: 설치본 소스 `.venv/.../edgar/entity/`] `FinancialFact`에 period/accession 메타 내장. `query()` 빌더 + `by_period_type`. |
| `OpenDartReader` (import `opendartreader`) | 0.3.2 (설치본) | DART `finstate_all` 분기 백필 + `list` rcept_no probe | [VERIFIED: 설치본 소스 `.venv/.../opendartreader/dart.py`] `list()`/`finstate_all()` 시그니처 직접 확인. |
| `tenacity` | 9.x | EDGAR/DART probe·fetch retry | [CITED: CLAUDE.md] 기존 스택. probe 실패 시 재시도 정책(아래 Pitfall 2). |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `threading` (stdlib) | — | SQLite 연결 싱글톤 double-checked lock | `cache.py` `_cache_lock` 패턴 재사용(WR-04). |
| `pyrate_limiter` (`throttle.py`) | 3.x | EDGAR 8 RPS / DART 2 RPS throttle | 신규 probe/fetch 함수에 `@throttled_edgar`/`@throttled_dart` 적용. |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| sqlite3 stdlib | SQLModel/SQLAlchemy ORM | 200종목 long 테이블에 ORM 과잉. 추가 의존성·러닝커브. **기각**. |
| sqlite3 stdlib | diskcache(기존) 재사용 | diskcache는 key-value + TTL 만료 모델 → long 테이블·SQL 집계·TTL 없음 요건에 부적합. **기각**(D-H3 명시). |
| `Company.latest("10-Q")` probe | data.sec.gov `submissions/CIK.json` 직접 httpx | edgartools가 이미 submissions를 캐시/파싱하므로 raw httpx는 중복. **edgartools 경로 권고**. |

**Installation:** 신규 외부 패키지 **없음** (sqlite3·threading은 stdlib, edgartools/opendartreader/tenacity는 기존 설치본).

**Version verification:**
```bash
# 설치본 직접 검증 완료:
#   .venv/Lib/site-packages/edgartools-5.35.0.dist-info     → edgartools 5.35.0
#   .venv/Lib/site-packages/opendartreader-0.3.2.dist-info  → OpenDartReader 0.3.2
python -c "import sqlite3; print(sqlite3.sqlite_version)"   # 번들 SQLite 버전 확인 (ON CONFLICT는 3.24+)
```

## Package Legitimacy Audit

> Phase 7은 신규 외부 패키지를 설치하지 않는다(sqlite3/threading stdlib). 아래는 의존하는 기존 패키지의 확인 기록(`slopcheck scan pyproject.toml` 실행).

| Package | Registry | slopcheck | Disposition |
|---------|----------|-----------|-------------|
| edgartools | PyPI | [OK] | Approved (기존 의존, 설치본 5.35.0) |
| opendartreader | PyPI | [OK] ("No source repository linked" 주의) | Approved (기존 의존, 설치본 0.3.2) |
| tenacity | PyPI | [OK] | Approved (기존 의존) |
| sqlite3 / threading | stdlib | n/a | stdlib — 검증 불필요 |

**Packages removed due to slopcheck [SLOP] verdict:** none
**Packages flagged as suspicious [SUS]:** none (opendartreader는 [OK]이나 소스 저장소 미연결 — 이미 검증된 기존 의존이며 GitHub `FinanceData/OpenDartReader` 존재)

## Architecture Patterns

### System Architecture Diagram

```
main_run.run()
   │
   ├─ (기존) PASS1 fan-out: OHLCV+compute → runner.run_all → 시트1 (불변, D-06)
   │
   └─ [신규] 히스토리 경로 (종목별, 별도 호출)
            │
            ▼
      fundamentals_store.get_store()  ──init──▶  data/fundamentals.db (WAL)
            │                                        ├─ raw_facts  (long)
            │                                        └─ delta_state
            ▼
      종목 루프:
        ① probe_latest_accession(ticker, source)   ← 가벼운 메타 호출
        │     EDGAR: Company(t).latest("10-Q").accession_number
        │     DART : dart.list(corp, kind='A').iloc[0].rcept_no
        ▼
        ② store.get_last_accession(ticker, source)  ← SELECT 1회
        ▼
        ③ 비교 ──같음──▶ SKIP (full-fetch 생략, hit++)         ──┐
        │       │                                                 │
        │       └─다름/state없음──▶ ④ full-fetch                  │
        │                              EDGAR: fetch_edgar_quarterly_raw(t)  ←get_facts() 1회
        │                              DART : 3년 백필 fetch_dart_quarterly_raw(t, year×3)
        ▼                                   │
        ⑤ store.upsert_quarters(rows)  ──ON CONFLICT DO UPDATE──▶ raw_facts
        ⑥ store.set_last_accession(...) ─────────────────────────▶ delta_state
        │
        └─ probe 실패 ──▶ 갱신 생략 + 기존 DB 유지 (Pitfall 2 권고)
```
*파일↔구현 매핑은 아래 Component Responsibilities 참조 — 다이어그램은 데이터 흐름만.*

### Component Responsibilities
| 파일 (신규/수정) | 책임 |
|------------------|------|
| `src/stocksig/io/fundamentals_store.py` **(신규)** | sqlite3 연결 싱글톤(WAL), 스키마 DDL, `upsert_quarters()`, `get_last_accession()`/`set_last_accession()`, `count_rows()`(검증용), 델타 hit/miss 카운터. |
| `src/stocksig/io/edgar_client.py` **(수정·additive)** | `fetch_edgar_quarterly_raw(ticker) -> list[QuarterRow]` + `probe_edgar_accession(ticker) -> str|None` 추가. 기존 `fetch_edgar_raw`(TTM) 불변. |
| `src/stocksig/io/dart_client.py` **(수정·additive)** | `fetch_dart_quarterly_raw(ticker, years) -> list[QuarterRow]` + `probe_dart_rcept(ticker) -> str|None` 추가. `_parse_amount`/`_match_amount` 재사용, BS/CF sj_div 추가. 기존 `fetch_dart_raw` 불변. |
| `src/stocksig/io/dart_account_map.py` **(수정·additive)** | `DART_ACCOUNT_ID_MAP`/`DART_ACCOUNT_MAP`에 자본총계·부채총계·총자산·영업현금흐름·발행주식수 매핑 추가. `SJ_DIV_BALANCE_SHEET=("BS",)`, `SJ_DIV_CASHFLOW=("CF",)` 신규 상수. |
| `src/stocksig/main_run.py` **(수정)** | run() 종료부 근처에서 히스토리 경로 오케스트레이션 호출(종목별). 시트1 PASS1/PASS2 불변. |
| `.gitignore` **(수정)** | `data/` 또는 `data/fundamentals.db` 라인 추가. |

### Recommended Project Structure
```
src/stocksig/io/
├── fundamentals_store.py   # [신규] SQLite store + 델타 state + upsert
├── edgar_client.py         # [수정] + fetch_edgar_quarterly_raw / probe_edgar_accession
├── dart_client.py          # [수정] + fetch_dart_quarterly_raw / probe_dart_rcept
├── dart_account_map.py     # [수정] + BS/CF/shares 매핑 + sj_div 상수
└── cache.py                # (불변 — 패턴만 참고)
data/
└── fundamentals.db         # [신규, .gitignore]
```

### Pattern 1: EDGAR per-quarter 추출 (D-04 핵심 — facts 1회 fetch)
**What:** `Company(ticker).get_facts()`로 `EntityFacts` 1회 취득 후, `query()` 빌더로 분기별 손익(duration)·BS(instant)·발행주식수(instant)를 전부 추출. 각 fact의 `accession`·`period_end`·`fiscal_period`를 그대로 raw 행에 저장.
**When to use:** 델타 다름(새 분기/정정공시) 시 full-fetch.
**Example:**
```python
# Source: 설치본 .venv/.../edgar/entity/entity_facts.py + query.py + models.py [VERIFIED 5.35.0]
from edgar import Company

facts = Company(ticker).get_facts()    # EntityFacts — 과거 분기 전부 포함 (D-01 "공짜")

# 유량(손익·현금흐름): period_type='duration', 분기 길이 ≈3개월
rev_q = (facts.query()
         .by_concept("Revenue")
         .by_period_type("duration")
         .by_period_length(3)          # 분기(3개월) duration만 — 9M/FY 제외
         .execute())                   # -> list[FinancialFact]

# 저량(BS·발행주식수): period_type='instant'
equity_q = facts.query().by_concept("StockholdersEquity").by_period_type("instant").execute()
assets_q = facts.query().by_concept("Assets").by_period_type("instant").execute()
shares   = facts.shares_outstanding_fact   # FinancialFact (accession 포함) 또는 facts.shares_outstanding (float)
ocf_q    = facts.query().by_concept("NetCashProvidedByUsedInOperatingActivities").by_period_type("duration").by_period_length(3).execute()

for f in rev_q:
    cal_quarter = f.get_display_period_key()   # "Q2 2026" — D-08 캘린더 정규화 (라이브러리 내장)
    row = {
        "ticker": ticker, "source": "EDGAR",
        "quarter": cal_quarter, "field": "revenue",
        "value": f.numeric_value,              # None-safe (D-05)
        "period_start": f.period_start, "period_end": f.period_end,
        "period_type": f.period_type, "fiscal_period": f.fiscal_period,
        "accession": f.accession,              # 델타 키
        "unit": f.unit,
    }
```
> **주의 (CITED + ASSUMED):** EDGAR Q4는 별도 분기 10-Q가 없어 instant BS는 FY 10-K에만 존재할 수 있고, duration 손익의 Q4 = FY−9M 보정이 필요하다 — 그러나 **그 보정은 Phase 8(D-05)**. Phase 7은 facts가 보고한 instant/duration as-reported 그대로 저장한다. `by_period_length(3)`로 분기 duration만 거르는 정확한 동작은 종목별로 다를 수 있어 [ASSUMED A1] — executor가 AAPL/GOOGL 실호출로 분기 행 개수를 확인할 것.

### Pattern 2: 접수번호 델타 probe + SELECT 1회 비교 (FUND-08 핵심)
**What:** full-fetch 전에 가벼운 메타 호출로 최신 accession/rcept_no만 얻어 state 테이블과 비교.
**When to use:** 매 실행, 종목·소스별 1회.
**Example:**
```python
# EDGAR probe — Source: 설치본 edgar/entity/core.py L541 [VERIFIED]
latest = Company(ticker).latest("10-Q")        # Filing (또는 get_filings(form=...).latest())
edgar_accession = latest.accession_number if latest else None

# DART probe — Source: 설치본 opendartreader/dart.py L54 + dart_list.py [VERIFIED]
dart = OpenDartReader(api_key)                 # ⚠️ corp_codes 캐시 1회/일 (Pitfall 1)
df = dart.list(stock_code, kind="A")           # 정기공시(A)만 — list.json, 100/page
latest_rcept = df.iloc[0]["rcept_no"] if not df.empty else None   # rcept_dt desc 정렬

# 비교 (state 테이블)
last = store.get_last_accession(ticker, source)    # SELECT last_accession ... LIMIT 1
if last is not None and last == latest:
    store.mark_delta_hit(); return   # SKIP — full-fetch 생략 (≈0 호출)
# else: full-fetch → upsert → set_last_accession
```
> **DART 비용 절감 (CITED + ASSUMED):** `dart.list()`는 종료일 기준 1년 범위 기본 + `final=True`. `kind='A'`(정기공시)로 좁히면 분기/사업보고서 접수만 반환. 최신 1건만 필요하므로 page 1로 충분(라이브러리는 total_page까지 페이징하지만 정기공시 1년치는 대개 1~2건). [ASSUMED A2] — executor가 005930 실호출로 정기공시 정렬·rcept_no 최신성 확인.

### Anti-Patterns to Avoid
- **종목마다 `OpenDartReader(api_key)` 새로 생성:** 생성자가 `corp_codes` zip을 매번 점검/캐시(`docs_cache/`). 인스턴스를 **모듈 싱글톤으로 1회 생성**해 재사용(기존 `dart_client.py`는 fetch마다 생성 — Phase 7 신규 경로에서는 싱글톤화 검토). [VERIFIED: 설치본 dart.py L26-49]
- **`facts.query()` 없이 `get_revenue()`만 반복:** `get_revenue(annual=False)`는 단일 최신 분기값만 — 과거 분기 누적 backfill(D-01)에는 `query().execute()` 전체 리스트가 필요.
- **TTL/expire 컬럼 추가:** D-H3 "TTL 없음". diskcache의 `expire=` 발상을 SQLite store에 가져오지 말 것.
- **시트1 경로 수정:** D-06 위반. 신규 모듈만 추가하고 `fundamentals.py`/`.cache/fundamentals`는 불변.
- **fetched_at으로 upsert 충돌 회피:** D-09 유니크 키는 `(ticker, source, quarter, field)`. fetched_at은 값 컬럼이지 키가 아님 — 정정공시는 같은 분기를 덮어써야 함.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| 캘린더 분기 정규화(D-08) | period_end → 분기 매핑 직접 구현 | EDGAR: `FinancialFact.get_display_period_key()` / DART: reprt_code→분기 직접 매핑 | edgartools가 이미 정확 구현(month→Q). DART는 reprt_code가 분기를 직접 지정. |
| EDGAR XBRL period/accession 파싱 | data.sec.gov companyfacts JSON 직접 파싱 | `EntityFacts.query()` + `FinancialFact` 속성 | edgartools가 instant/duration·accession·period_end를 typed로 노출. raw JSON 재파싱은 회귀 위험. |
| upsert (정정공시 덮어쓰기) | SELECT-then-INSERT/UPDATE 2단계 | `INSERT ... ON CONFLICT(...) DO UPDATE SET ...` | 원자적, race-free. 2단계는 fan-out 하 race. |
| 동시 쓰기 직렬화 | 수동 파일 lock | sqlite3 WAL + 단일 연결 싱글톤(serialized) + `_store_lock` | SQLite WAL이 동시 read 허용, 쓰기는 lock. cache.py 패턴 재사용. |
| 최신 접수번호 조회 | EDGAR 전체 facts fetch 후 max(accession) | `Company.latest("10-Q")` (메타만) / DART `list` | full-fetch가 곧 호출 비용 — probe는 가벼워야 ≈0 달성. |

**Key insight:** Phase 7의 모든 "어려운" 부분(분기 정규화, instant/duration 구분, accession 추출)은 edgartools 5.35.0이 이미 typed로 제공한다. 신규 코드는 **저장(sqlite upsert) + 델타 비교(SELECT) + DART 매핑 확장**에 집중하면 된다.

## Runtime State Inventory

> rename/refactor가 아닌 신규 저장 기능이므로 대부분 N/A. 단 신규 영구 상태가 **생성**되므로 명시.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | **신규 생성:** `data/fundamentals.db`(raw_facts + delta_state). 기존 `.cache/`(diskcache)와 별개. | DDL로 스키마 생성(CREATE TABLE IF NOT EXISTS). 기존 데이터 마이그레이션 없음(첫 실행 backfill). |
| Live service config | None — 외부 서비스 설정 변경 없음. EDGAR/DART는 기존 fetch 층 재사용. | None |
| OS-registered state | None — Windows Task Scheduler 등 변경 없음. `uv run python main.py` 그대로(CLAUDE.md). | None |
| Secrets/env vars | None 신규 — `OPENDART_API_KEY`/`EDGAR_USER_AGENT_EMAIL` 기존 키 재사용(코드만). | None |
| Build artifacts | None — pyproject 의존성 변화 없음(신규 패키지 0). | None |

**검증:** `data/fundamentals.db`는 신규 파일이며 `.gitignore`에 추가되어야 한다(현재 `.gitignore`에 `data/` 미등재 — SC5).

## Common Pitfalls

### Pitfall 1: OpenDartReader 인스턴스 생성 비용 (IN-06 deferred 연관)
**What goes wrong:** `OpenDartReader(api_key)` 생성자가 매번 `corp_codes` zip(전 상장사 고유번호) 존재를 점검하고, 당일 캐시(`docs_cache/opendartreader_corp_codes_YYYYMMDD.pkl`)가 없으면 다운로드. 종목마다 생성하면 점검 오버헤드 반복.
**Why it happens:** [VERIFIED: 설치본 dart.py L26-49] `__init__`이 `docs_cache_dir` 생성 + glob + 당일 pkl 캐시 로직 수행.
**How to avoid:** OpenDartReader 인스턴스를 **모듈 싱글톤으로 1회 생성**(double-checked lock). corp_codes 다운로드는 하루 1회로 수렴 — 이것은 "≈0 펀더멘털 호출"의 호출 카운트에 포함되지 않는 일회성 메타 비용임을 검증 로그에 명시.
**Warning signs:** `docs_cache/` 디렉토리가 계속 갱신되거나 실행마다 zip 다운로드 로그.

### Pitfall 2: delta probe 실패 처리 (CONTEXT Claude's Discretion — 권고)
**What goes wrong:** 네트워크 단절 / DART 쿼터 초과("020") / EDGAR 메타 오류로 최신 accession을 못 얻으면 "변경 여부 불확실".
**Why it happens:** probe도 외부 호출이라 실패 가능.
**How to avoid — 권고: "갱신 생략, 기존 DB 유지" (보수적 재추출 아님).**
| 옵션 | 정확도 | 비용 | 위험 |
|------|--------|------|------|
| **(권고) probe 실패 → SKIP + 기존 DB 유지** | 이번 실행에서 새 분기 1회 놓칠 수 있음(다음 실행에서 자연 복구) | 0 (full-fetch 안 함) | 낮음 — raw 영구 보존이라 데이터 손실 없음. 다음 성공 probe에서 따라잡음. |
| 보수적 재추출(probe 실패=무조건 full-fetch) | 항상 최신 | 높음 — probe 실패가 곧 전 종목 full-fetch 폭주(쿼터 초과 시 연쇄) | 높음 — DART 쿼터 초과 상황에서 재추출 시도는 쿼터를 더 소진, "≈0 호출" 주장 붕괴. |
**근거:** D-02(forward 누적) + TTL 없음(D-H3)이므로 한 실행을 건너뛰어도 데이터는 보존되고 다음 실행이 따라잡는다. probe 실패 시 재추출은 쿼터 초과 상황을 악화시킨다. **state 테이블 `last_checked_at`만 갱신하지 않거나, 별도 `last_probe_failed_at`을 남겨 관측**하는 것을 권고.
**Warning signs:** probe 실패가 반복되는데 full-fetch가 폭증.

### Pitfall 3: instant vs duration 혼동 (EDGAR)
**What goes wrong:** `Assets`/`StockholdersEquity`(저량=instant)를 duration으로, `Revenue`(유량=duration)를 instant로 query하면 빈 결과.
**Why it happens:** XBRL은 시점값(instant)과 기간값(duration)을 구분. `FinancialFact.period_type`이 이를 구별.
**How to avoid:** 손익/현금흐름 = `by_period_type("duration")` + `by_period_length(3)`(분기), BS·발행주식수 = `by_period_type("instant")`. [VERIFIED: models.py L44 `period_type: Literal['instant','duration']`]
**Warning signs:** BS 필드가 항상 None, 또는 매출이 누적 9M/FY 값으로 들어옴.

### Pitfall 4: DART YTD 누적값을 분기값으로 오인
**What goes wrong:** DART 손익은 YTD 누적(thstrm_amount = 기초~분기말 누적). 이를 분기 단독값으로 저장하면 Phase 8 계산이 틀어짐.
**Why it happens:** DART 보고 관행.
**How to avoid:** D-05대로 **as-reported(YTD) 그대로 저장** + period 메타(reprt_code, bsns_year) 보존. 분기 분해(YTD−직전Q)는 Phase 8. `thstrm_add_amount`(분기 add 컬럼, fixture COLUMNS에 존재)도 함께 저장해두면 Phase 8 입력 확장.
**Warning signs:** 분기 매출이 직전 분기보다 단조 증가만 함(누적 신호).

### Pitfall 5: SQLite WAL 동시성 + Windows 파일 핸들
**What goes wrong:** ThreadPoolExecutor(max_workers=4) 워커가 동시에 같은 연결로 write → lost update 또는 `database is locked`. Windows에서 연결 미종료 시 tmp_path 정리 실패(테스트).
**Why it happens:** sqlite3 연결은 기본 스레드 바운드. fan-out 하 공유 위험.
**How to avoid:** (a) `PRAGMA journal_mode=WAL` + `PRAGMA busy_timeout=5000`, (b) write를 `_store_lock`(threading.Lock)으로 직렬화하거나 단일 writer 연결 사용, (c) 연결 생성 시 `check_same_thread=False` + lock, (d) 테스트 teardown에서 `conn.close()`(conftest의 diskcache close 패턴 모방). [VERIFIED: cache.py `_cache_lock` 패턴]
**Warning signs:** `sqlite3.OperationalError: database is locked`, Windows tmp 정리 PermissionError.

## Code Examples

### 스키마 DDL (D-H3 시작점 + D-08/D-09 + D-03 슈퍼셋)
```python
# Source: SQLite ON CONFLICT (CITED: sqlite.org/lang_UPSERT) + D-H3/D-08/D-09 [VERIFIED: stdlib]
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS raw_facts (
    ticker        TEXT NOT NULL,
    source        TEXT NOT NULL,          -- 'EDGAR' | 'DART' | 'yf' | 'Naver'
    quarter       TEXT NOT NULL,          -- 캘린더 분기 'YYYYQn' (D-08)
    field         TEXT NOT NULL,          -- 'revenue','gross_profit','op_income','net_income',
                                          --   'eps','total_equity','total_liabilities',
                                          --   'shares_outstanding','operating_cash_flow','total_assets'
    value         REAL,                   -- NULL 허용 (D-05 결손=NULL, 0 금지)
    unit          TEXT,                   -- 'USD' | 'KRW' | 'shares'
    accession     TEXT,                   -- EDGAR accession / DART rcept_no (정정 메타)
    period_start  TEXT,                   -- ISO date (EDGAR duration 시작)
    period_end    TEXT,                   -- ISO date (분기 종료일 — 캘린더 정규화 근거)
    period_type   TEXT,                   -- 'instant' | 'duration'
    reprt_code    TEXT,                   -- DART 분기코드 (11013/11012/11014/11011)
    fetched_at    TEXT NOT NULL,          -- ISO datetime
    PRIMARY KEY (ticker, source, quarter, field)   -- D-09 유니크 키
);

CREATE TABLE IF NOT EXISTS delta_state (
    ticker          TEXT NOT NULL,
    source          TEXT NOT NULL,
    last_accession  TEXT,
    last_checked_at TEXT,
    PRIMARY KEY (ticker, source)
);

CREATE INDEX IF NOT EXISTS idx_raw_ticker_q ON raw_facts(ticker, quarter);
"""
```

### 연결 싱글톤 (cache.py double-checked lock 패턴 재사용)
```python
# Source: 설치본 cache.py L65-72 패턴 [VERIFIED] + sqlite3 stdlib
import sqlite3, threading
from pathlib import Path

_DB_PATH = Path("data/fundamentals.db")
_conn: sqlite3.Connection | None = None
_store_lock = threading.Lock()        # 연결 초기화 + write 직렬화

def get_store() -> sqlite3.Connection:
    global _conn
    if _conn is None:                              # fast-path
        with _store_lock:
            if _conn is None:                      # double-checked
                _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
                _conn.executescript(SCHEMA)
    return _conn
```

### upsert (정정공시 덮어쓰기 — D-09)
```python
# Source: SQLite UPSERT (CITED: sqlite.org/lang_UPSERT) [VERIFIED: stdlib 지원]
UPSERT = """
INSERT INTO raw_facts
  (ticker, source, quarter, field, value, unit, accession,
   period_start, period_end, period_type, reprt_code, fetched_at)
VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
ON CONFLICT(ticker, source, quarter, field) DO UPDATE SET
   value=excluded.value, unit=excluded.unit, accession=excluded.accession,
   period_start=excluded.period_start, period_end=excluded.period_end,
   period_type=excluded.period_type, reprt_code=excluded.reprt_code,
   fetched_at=excluded.fetched_at;
"""

def upsert_quarters(rows: list[tuple]) -> None:
    conn = get_store()
    with _store_lock:                       # fan-out write 직렬화 (Pitfall 5)
        conn.executemany(UPSERT, rows)
        conn.commit()
```

### 델타 state 비교
```python
def get_last_accession(ticker: str, source: str) -> str | None:
    cur = get_store().execute(
        "SELECT last_accession FROM delta_state WHERE ticker=? AND source=?",
        (ticker, source))
    row = cur.fetchone()
    return row[0] if row else None

def set_last_accession(ticker: str, source: str, accession: str) -> None:
    conn = get_store()
    with _store_lock:
        conn.execute(
            "INSERT INTO delta_state (ticker, source, last_accession, last_checked_at) "
            "VALUES (?,?,?,?) ON CONFLICT(ticker, source) DO UPDATE SET "
            "last_accession=excluded.last_accession, last_checked_at=excluded.last_checked_at",
            (ticker, source, accession, _now_iso()))
        conn.commit()

def count_rows(ticker: str | None = None) -> int:   # 검증용 (과거 분기 보존 회귀)
    sql = "SELECT COUNT(*) FROM raw_facts"
    args = ()
    if ticker:
        sql += " WHERE ticker=?"; args = (ticker,)
    return get_store().execute(sql, args).fetchone()[0]
```

### DART 분기 백필 (최근 3년 — D-01)
```python
# Source: 설치본 opendartreader/dart.py L124 finstate_all [VERIFIED]
# reprt_code: 11013=1Q, 11012=반기, 11014=3Q, 11011=연간(사업보고서)
import datetime as dt
QUARTER_CODES = ["11013", "11012", "11014", "11011"]   # 분기별 보고서

def fetch_dart_quarterly_raw(ticker: str, years: int = 3) -> list[QuarterRow]:
    stock_code = ticker.split(".")[0]
    dart = _get_dart()                       # 모듈 싱글톤 (Pitfall 1)
    this_year = dt.date.today().year
    rows = []
    for year in range(this_year - years, this_year + 1):     # 최근 ~3년 = ~12분기
        for code in QUARTER_CODES:
            resp = dart.finstate_all(stock_code, year, reprt_code=code, fs_div="CFS")
            if not isinstance(resp, pd.DataFrame) or resp.empty:
                continue                     # status/빈응답 가드 (기존 _STATUS_NOTES 재사용)
            rcept = resp.iloc[0]["rcept_no"] # rcept_no는 매 행 동일 (fixture COLUMNS[0]) [VERIFIED]
            rows += _extract_dart_fields(resp, ticker, year, code, rcept)  # IS/CIS/BS/CF
    return rows
```
> **DART 분기 호출 비용:** 3년 × 4분기 = 최대 12 finstate_all 호출/종목 (첫 backfill 1회만, D-01). 2 RPS throttle 하 종목당 ~6초. backfill 이후엔 델타 probe(list 1회) + 변경 시만 1년 fetch. [ASSUMED A3] — executor가 실제 분기 보고서 가용성(일부 연도 빈 응답) 확인.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `facts.to_pandas()` | `facts.query().to_dataframe()` / `.execute()` | edgartools 5.x | `EntityFacts.to_pandas` 부재(03-02 스파이크 A1 확정). query 빌더 사용. |
| `get_ttm("Revenues")` | `get_ttm_revenue()` / `query().by_concept("Revenue")` | 5.x | "Revenues" concept은 stale FY 선택. |
| EDGAR raw JSON 직접 파싱 | `FinancialFact` typed 속성 | edgartools 5.x | period/accession/instant-duration 메타 typed 노출. |

**Deprecated/outdated:**
- CLAUDE.md는 edgartools "4.x"라 적었으나 **설치본은 5.35.0** (pyproject `edgartools>=5,<6`). RESEARCH는 5.35.0 기준. [VERIFIED: dist-info]
- pandas-ta / TA-Lib: Phase 7 무관(저장 phase).

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `by_period_length(3)`로 EDGAR 분기 duration만 정확히 거를 수 있고 종목 전반에 일관 | Pattern 1 | 분기/9M/FY 혼입 시 raw 행 오염 — executor가 AAPL/GOOGL 실호출 분기 행 수 확인으로 해소. Phase 8 분해가 어차피 period_type/length로 재필터하므로 영향 제한적. |
| A2 | `dart.list(corp, kind='A')` 최신 행이 가장 최근 정기공시 rcept_no | Pattern 2 | 정렬/필터 어긋나면 잘못된 accession 비교 → 불필요 재추출 또는 누락. 005930 실호출 1회로 검증. |
| A3 | DART 분기 보고서(11013/11012/11014)가 최근 3년 대부분 가용 | DART 백필 | 일부 연도 빈 응답이면 백필 깊이 < 12분기. 빈 응답은 가드로 skip하므로 안전(데이터만 적음). |
| A4 | `Company(ticker).latest("10-Q").accession_number` 속성명 정확 | Pattern 2 | edgartools Filing 속성명이 `accession_number`/`accession_no` 중 무엇인지 executor가 1회 확인(설치본 filing 객체 introspect). |
| A5 | EDGAR BS/CF/shares concept 표준 태그(`StockholdersEquity`,`Assets`,`NetCashProvidedByUsedInOperatingActivities`, dei shares) | Pattern 1 | concept 변형 시 빈 결과 — `get_total_assets`/`get_shareholders_equity` 등 edgartools 헬퍼가 concept 매핑을 내장하므로 fallback로 사용 가능(설치본 L930-1017 [VERIFIED]). |

## Open Questions (RESOLVED)

1. **EDGAR Q4 BS instant 가용성** — **RESOLVED (D-05)**
   - 알고 있는 것: 10-Q는 Q1~Q3, Q4 BS는 FY 10-K에만 instant로 존재할 수 있음.
   - 결정: as-reported 그대로 저장(D-05). Q4 보정·분기 분해는 Phase 8. Phase 7은 가용한 instant 행을 전부 그대로 저장한다. 종목별 Q4 instant 별도 행 여부와 무관하게 raw 슈퍼셋 누적이므로 본 phase 산출물에 영향 없음.

2. **DART 발행주식수·총자산·영업현금흐름 account_id 표준 태그** — **RESOLVED (executor 실호출 검증 + 슈퍼셋 저장)**
   - 알고 있는 것: 손익 5종은 03-02 스파이크에서 005930 실데이터로 [VERIFIED]. BS/CF/shares는 미검증.
   - 결정: executor가 `dart.finstate_all("005930", ..., fs_div="CFS")`(sj_div='BS','CF') 실응답 1회로 BS/CF account_id를 확정해 `dart_account_map.py`를 갱신한다(불가 시 후보 tuple 유지). **발행주식수(shares_outstanding)가 finstate_all에 없으면 본 phase에서는 매핑 placeholder만 두고 Phase 8 또는 yf 보완으로 위임한다.** 본 phase는 finstate_all에서 가능한 필드만 D-03 슈퍼셋으로 저장한다(결손 필드는 None). 07-02 Task 1 acceptance_criteria에 이 분기 결정을 명시.

3. **히스토리 경로 main_run 진입 시점** — **RESOLVED (별도 순차 루프)**
   - 알고 있는 것: 시트1 PASS1/PASS2와 분리(D-06).
   - 결정: 별도 순차 루프(PASS2 write 이후·요약 직전). 시트1 회귀 위험 0이 최우선이며 SQLite write는 `_store_lock`으로 직렬화되므로 ThreadPool 동시성 이득이 적다. 07-04 Task 2가 이 배선을 구현.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| sqlite3 (stdlib) | raw/state 저장 | ✓ | Python 3.13 번들 | — |
| edgartools (`edgar`) | EDGAR per-quarter | ✓ | 5.35.0 (dist-info) | — |
| OpenDartReader | DART 백필/probe | ✓ | 0.3.2 (dist-info) | — |
| tenacity | probe/fetch retry | ✓ | 9.x (pyproject) | — |
| `OPENDART_API_KEY` (env) | DART 호출 | 런타임 .env 필요 | — | DART 종목은 결손 note(기존 패턴) |
| `EDGAR_USER_AGENT_EMAIL` (env) | EDGAR set_identity | 기본값 있음 | — | `_DEFAULT_EMAIL` 폴백 |

**Missing dependencies with no fallback:** 없음 (신규 외부 패키지 0).
**Missing dependencies with fallback:** API 키 미설정 시 해당 소스 결손(기존 auth_check/skip 패턴 재사용).

## Validation Architecture

> `workflow.nyquist_validation: true` (config.json) — 본 섹션 포함.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-mock + freezegun (pyproject dev group) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| Quick run command | `python -m pytest tests/test_fundamentals_store.py -x -q` |
| Full suite command | `python -m pytest -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUND-07 | 실행 후 `data/fundamentals.db` 생성 + raw_facts 누적 | unit | `pytest tests/test_fundamentals_store.py::test_upsert_creates_db -x` | ❌ Wave 0 |
| FUND-07 | 과거 분기 보존 (재실행 후 행 수 불변/증가만) | regression | `pytest tests/test_fundamentals_store.py::test_rerun_preserves_past_quarters -x` | ❌ Wave 0 |
| FUND-07 | 정정공시 upsert (같은 분기 새 accession → 값 덮어쓰기, 행 수 불변) | unit | `pytest tests/test_fundamentals_store.py::test_amendment_upsert_overwrites -x` | ❌ Wave 0 |
| FUND-07 | 결손값 NULL 저장 (0/-999999 아님, D-05) | unit | `pytest tests/test_fundamentals_store.py::test_none_stored_as_null -x` | ❌ Wave 0 |
| FUND-08 | accession 동일 → full-fetch 생략 (호출 카운터 0) | unit (spy) | `pytest tests/test_fundamentals_delta.py::test_same_accession_skips_fetch -x` | ❌ Wave 0 |
| FUND-08 | accession 변경 → 재추출 + last_accession 갱신 | unit (spy) | `pytest tests/test_fundamentals_delta.py::test_changed_accession_refetches -x` | ❌ Wave 0 |
| FUND-08 | probe 실패 → 갱신 생략 + 기존 DB 유지 (Pitfall 2) | unit | `pytest tests/test_fundamentals_delta.py::test_probe_failure_keeps_db -x` | ❌ Wave 0 |
| SC3 | "≈0 호출" — 변경 없는 평소 실행 full-fetch 호출 = 0 (probe만) | integration (spy) | `pytest tests/test_fundamentals_delta.py::test_steady_state_zero_full_calls -x` | ❌ Wave 0 |
| SC5 | EDGAR/DART per-quarter 추출 정확성 (fixture 기반, 네트워크 0) | unit | `pytest tests/test_edgar_quarterly.py tests/test_dart_quarterly.py -x` | ❌ Wave 0 |
| SC5 | 기존 회귀 무손상 (시트1·캐시 전 스위트 그린) | regression | `python -m pytest -q` | ✅ 기존 |

### "외부 호출 ≈0" 검증 방법 (SC3 핵심)
- **호출 스파이/카운터:** `fetch_edgar_quarterly_raw`/`fetch_dart_quarterly_raw`를 `mocker.spy` 또는 monkeypatch counter로 감싸고, probe는 통과시키되 **full-fetch 호출 횟수 == 0**을 단언. (기존 `tests/test_smoke_*`의 네트워크 0 stub 패턴 재사용 — quick-260617-k34 커밋의 "freeze/smoke fixture 네트워크 0 stub"와 동일 발상.)
- **delta_state 사전 시드:** 테스트에서 `set_last_accession(ticker, src, "ACC1")` 후, probe가 "ACC1" 반환하도록 mock → SKIP 경로 검증.
- **store 델타 hit/miss 카운터:** `cache.py`의 `_stats` 패턴을 store에 복제(`delta_hit`/`delta_miss`) → 요약 로그에서 평소 실행 `delta_hit == 종목수`, `full_fetch == 0` 관측.

### "과거 분기 보존" 검증 방법 (SC1 핵심)
- backfill 1회 → `count_rows(ticker)` 기록 → 같은 accession으로 재실행(probe SKIP) → `count_rows` **불변** 단언.
- 새 분기 시뮬레이션(다른 accession + 신규 분기 행) → `count_rows` **증가만**(기존 분기 행 삭제 없음) 단언.

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_fundamentals_store.py tests/test_fundamentals_delta.py -x -q`
- **Per wave merge:** `python -m pytest -q` (전 스위트 — 시트1 회귀 포함)
- **Phase gate:** Full suite green + `data/fundamentals.db` 미커밋(`.gitignore`) 확인 후 `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_fundamentals_store.py` — FUND-07 (upsert/보존/NULL/정정 덮어쓰기)
- [ ] `tests/test_fundamentals_delta.py` — FUND-08 + SC3 (probe/skip/refetch/probe실패/≈0)
- [ ] `tests/test_edgar_quarterly.py` — EDGAR per-quarter 추출 (fixture 확장: `edgar_aapl_facts.py`에 BS/CF/shares 분기 행 추가)
- [ ] `tests/test_dart_quarterly.py` — DART 분기 백필 (fixture 확장: `dart_005930_finstate.py`에 BS/CF sj_div 행 추가)
- [ ] `tests/conftest.py` — 신규 fixture: `_isolated_fundamentals_db`(tmp_path로 `_DB_PATH` 격리 + teardown `conn.close()`, 기존 `_isolated_disk_cache` 패턴 복제). **운영 `data/fundamentals.db` 오염 방지 — 필수.**
- [ ] Framework install: 불필요 (pytest 기존).

## Security Domain

> `security_enforcement` 키 부재 = 활성. 본 섹션 포함.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | 신규 인증 없음 (기존 EDGAR set_identity / DART API 키 재사용) |
| V3 Session Management | no | — |
| V4 Access Control | no | 로컬 단일 사용자 도구 |
| V5 Input Validation | yes | DART `thstrm_amount` 파싱 = 기존 `_parse_amount`(쉼표 제거 + int try/except, T-03-10) 재사용. SQL = 파라미터 바인딩(`?`)만 — 문자열 포매팅 금지. |
| V6 Cryptography | no | — |

### Known Threat Patterns for {sqlite3 + EDGAR/DART fetch}
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| SQL injection (ticker/field 보간) | Tampering | sqlite3 파라미터 바인딩(`?`) 전용. f-string/`%` SQL 금지. |
| API 키 누설 (예외 메시지·로그) | Information Disclosure | 기존 T-04-03 패턴 — 예외 원문 보간 금지, 타입명만 로그. `crtfc_key`가 URL에 포함되므로 probe/fetch 예외도 동일 가드. |
| DB 파일 커밋 (데이터·경로 노출) | Information Disclosure | `data/fundamentals.db` `.gitignore`(SC5). |
| 신뢰 불가 값으로 산식 오염 | Tampering | 결손=NULL(D-05). 0/-999999 금지로 후속 계산(Phase 8) 오염 차단. |

## Sources

### Primary (HIGH confidence)
- 설치본 소스 `.venv/Lib/site-packages/edgar/entity/{models.py,query.py,entity_facts.py,core.py}` — edgartools 5.35.0 `FinancialFact`/`FactQuery`/`EntityFacts`/`Company` API 직접 검증.
- 설치본 소스 `.venv/Lib/site-packages/opendartreader/{dart.py,dart_list.py,dart_finstate.py}` — OpenDartReader 0.3.2 `list()`/`finstate_all()` 시그니처 직접 검증.
- 프로젝트 소스 `src/stocksig/io/{edgar_client,dart_client,dart_account_map,cache,fundamentals}.py`, `runner.py`, `main_run.py`, `throttle.py` — 의존 패턴 직접 확인.
- 프로젝트 fixture `tests/fixtures/{edgar_aapl_facts.py,dart_005930_finstate.py}`, `tests/conftest.py` — 실데이터 mock 표면 + 격리 패턴.
- 백로그 `fundamentals-history-delta.md`, CONTEXT.md, REQUIREMENTS.md, ROADMAP.md — locked 결정.

### Secondary (MEDIUM confidence)
- edgartools 공식 문서 (readthedocs) — `query()` 빌더·`to_dataframe` 컬럼(WebSearch 요약; readthedocs는 429로 직접 fetch 불가하나 설치본 소스로 교차검증 완료).
- SEC EDGAR submissions API (data.sec.gov) — accession 메타 구조(WebSearch 요약).

### Tertiary (LOW confidence)
- DART `list` 정기공시 정렬·rcept_no 최신성(A2), 분기 보고서 가용성(A3) — 실호출 미수행, executor 검증 권고.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — 모든 라이브러리 설치본 소스 직접 검증, 신규 패키지 0.
- Architecture (스키마/upsert/델타): HIGH — sqlite3 stdlib + 검증된 API, cache.py 패턴 복제.
- EDGAR per-quarter 추출: HIGH (API) / MEDIUM (concept 태그·by_period_length 동작 A1/A5) — 실호출 1회로 확정 권고.
- DART BS/CF/shares 매핑: MEDIUM — 손익 5종 [VERIFIED], BS/CF/shares account_id 미검증(Open Q2).
- Pitfalls: HIGH — 설치본 소스 + 기존 코드 패턴 근거.

**Research date:** 2026-06-18
**Valid until:** 2026-07-18 (안정 — stdlib + 핀고정 라이브러리. edgartools 5.x 마이너 업데이트 시 query 빌더 표면 재확인.)
