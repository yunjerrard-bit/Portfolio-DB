# Phase 7: 펀더멘털 SQLite 저장 + 접수번호 델타 - Pattern Map

**Mapped:** 2026-06-18
**Files analyzed:** 6 (신규 1~2 / 수정 4)
**Analogs found:** 6 / 6 (전 파일 강한 analog 확보)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/stocksig/io/fundamentals_store.py` **(신규)** | store / persistence | CRUD (upsert + SELECT) | `src/stocksig/io/cache.py` | role-match (싱글톤+lock+카운터 구조 동형, 저장 엔진만 diskcache→sqlite3) |
| `src/stocksig/io/fundamentals_delta.py` **(신규, planner 분리 재량)** | service / delta-probe orchestrator | request-response (probe) + CRUD (state 비교) | `src/stocksig/io/edgar_client.py` + `cache.py` 카운터 | role-match (throttle 페치 + hit/miss 집계 합성) |
| `src/stocksig/io/edgar_client.py` **(수정·additive)** | client (API/backend) | request-response → batch raw 추출 | 자기 자신 `fetch_edgar_raw` (동일 파일) | exact (per-quarter 함수는 TTM 함수의 query-빌더 확장) |
| `src/stocksig/io/dart_client.py` **(수정·additive)** | client (API/backend) | request-response → batch raw 추출 | 자기 자신 `fetch_dart_raw` (동일 파일) | exact (분기 백필은 단일연도 fetch의 루프 확장) |
| `src/stocksig/io/dart_account_map.py` **(수정·additive)** | config / 매핑 상수 | transform (lookup table) | 자기 자신 `DART_ACCOUNT_ID_MAP`/`DART_ACCOUNT_MAP` | exact (신규 필드 행 추가) |
| `src/stocksig/main_run.py` **(수정)** | orchestrator (entry point) | event-driven (run 종료부 hook) | 자기 자신 `run()` PASS1/요약 블록 | exact (별도 순차 루프 + 요약 줄 추가) |
| `.gitignore` **(수정)** | config | n/a | 기존 `.cache/` 라인 | exact |

---

## Pattern Assignments

### `src/stocksig/io/fundamentals_store.py` (store, CRUD) — 신규

**Analog:** `src/stocksig/io/cache.py` (1차) — diskcache 싱글톤을 sqlite3 연결 싱글톤으로 치환. 구조(모듈 레벨 싱글톤 + `_cache_lock` double-checked locking + `_stats`/`_stats_lock` hit/miss 카운터 + reset/get 카운터 함수)는 그대로 복제한다.

**모듈 docstring + import 패턴** (analog `cache.py` L1-21 스타일 — 모듈 책임 한국어 docstring + `from __future__ import annotations`):
```python
from __future__ import annotations
import logging, sqlite3, threading
from datetime import datetime
from pathlib import Path
logger = logging.getLogger(__name__)
```

**싱글톤 + double-checked lock** — `cache.py` `_get_cache()` L65-72를 직접 복제. **RESEARCH §"연결 싱글톤" L347-366이 이미 이 패턴을 sqlite3로 옮겨놓음**:
```python
# cache.py L65-72 (복제 원본):
def _get_cache() -> Cache:
    global _cache
    if _cache is None:                 # fast-path (lock 없음)
        with _cache_lock:
            if _cache is None:         # double-checked
                _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
                _cache = Cache(str(_DEFAULT_DIR))
    return _cache
```
→ 신규 `get_store()`는 `Cache(...)` 대신 `sqlite3.connect(str(_DB_PATH), check_same_thread=False)` + `conn.executescript(SCHEMA)` (RESEARCH L357-365). `_store_lock = threading.Lock()`은 **초기화 + write 직렬화 겸용**(Pitfall 5).

**hit/miss 카운터** — `cache.py` `_stats`/`_stats_lock` L33-62를 델타용으로 복제:
```python
# cache.py L33-62 (복제 원본):
_stats: dict[str, int] = {"ohlcv_hit": 0, "ohlcv_miss": 0, ...}
_stats_lock = threading.Lock()
def reset_cache_stats() -> None:
    with _stats_lock:
        for k in _stats: _stats[k] = 0
def get_cache_stats() -> dict[str, int]:
    with _stats_lock:
        return dict(_stats)        # 복사본 반환 (내부 상태 오염 방지)
```
→ 신규 키: `delta_hit`(probe 동일 → SKIP), `delta_miss`(probe 변경 → full-fetch), `full_fetch`. `read-modify-write +=`는 반드시 `_stats_lock` 안에서(`cache.py` L91-96 패턴 — ThreadPoolExecutor lost-update 방지).

**스키마 DDL / upsert / SELECT** — RESEARCH §Code Examples L310-415가 완성 시드 제공(SCHEMA L313-344, UPSERT L371-388, get/set_last_accession L392-407, count_rows L409-414). **ASVS V5**: 모든 SQL은 `?` 파라미터 바인딩만(f-string/`%` 금지).

**규약:**
- TTL/expire 컬럼 **금지** (D-H3 TTL 없음 — diskcache `expire=` 발상 가져오지 말 것; cache.py의 `_TTL_SECONDS`는 복제 대상 아님).
- value 컬럼 NULL 허용 (결손=`None`, D-05). 0/-999999 금지.
- write는 `with _store_lock:` + `conn.commit()` (RESEARCH L385-387).

---

### `src/stocksig/io/fundamentals_delta.py` (service, probe + state 비교) — 신규 (planner 분리 재량)

**Analog:** `edgar_client.py`/`dart_client.py` throttle 페치 함수 + `cache.py` 카운터.

**probe 함수 + throttle 데코레이터** — `edgar_client.py` `fetch_edgar_raw` L63-93 / `dart_client.py` `fetch_dart_raw` L114-161 시그니처 스타일 복제. RESEARCH Pattern 2 L216-235:
```python
@throttled_edgar
def probe_edgar_accession(ticker: str) -> str | None:
    latest = Company(ticker).latest("10-Q")
    return latest.accession_number if latest else None   # [A4] 속성명 1회 introspect

@throttled_dart
def probe_dart_rcept(ticker: str) -> str | None:
    df = _get_dart().list(ticker.split(".")[0], kind="A")   # 정기공시만
    return df.iloc[0]["rcept_no"] if not df.empty else None
```

**델타 비교 + 카운터** — RESEARCH L231-234 시드:
```python
last = store.get_last_accession(ticker, source)
if last is not None and last == latest:
    store.mark_delta_hit(); return        # SKIP — full-fetch 생략 (≈0)
# else: full-fetch → store.upsert_quarters(...) → store.set_last_accession(...)
```

**probe 실패 처리 (Pitfall 2 권고 — 잠긴 결정 아님, planner 확정용)**: probe 실패 → **SKIP + 기존 DB 유지** (보수적 재추출 금지 — DART 쿼터 초과 연쇄 방지). `last_checked_at` 미갱신 또는 `last_probe_failed_at` 관측 컬럼. (RESEARCH L279-288)

**규약:**
- `OpenDartReader(api_key)`를 종목마다 생성 금지 → **모듈 싱글톤** `_get_dart()` (Pitfall 1; cache.py double-checked lock 패턴 재사용). 기존 `dart_client.py` L129는 fetch마다 생성하나 신규 경로에서는 싱글톤화.
- 예외 메시지에 API 키/원문 보간 금지(T-04-03) — `crtfc_key`가 URL 포함. 타입명만 로그.

---

### `src/stocksig/io/edgar_client.py` (client, batch raw 추출) — 수정·additive

**Analog:** 동일 파일 `fetch_edgar_raw` L63-93. **기존 함수 불변** — `fetch_edgar_quarterly_raw` / `probe_edgar_accession` **신규 추가**.

**throttle + None-safe + 한국어 로그 규약** (L63-93 복제):
```python
@throttled_edgar
def fetch_edgar_raw(ticker: str) -> dict:
    facts = Company(ticker).get_facts()                # EntityFacts 1회
    ...
    logger.info("%s | EDGAR facts 수신 완료", ticker)
```
→ 신규 함수도 `@throttled_edgar` + `Company(ticker).get_facts()` 1회(D-01 "공짜") + 한국어 완료 로그. 차이: TTM accessor(`get_ttm_revenue`) 대신 **`facts.query().by_concept(...).by_period_type(...).execute()` 빌더**로 per-quarter 리스트 추출 (RESEARCH Pattern 1 L179-213).

**None-safe 패턴** — 기존 `_ttm_value` L56-60 + 주석 "결손 지표는 None(0/-999999 금지, D-05)" L68 그대로. 신규 행 `value`는 `f.numeric_value` (None-safe).

**set_identity import-time 1회** — L43-45 패턴 불변 재사용 (per-call 금지). 신규 함수가 추가 set_identity 호출하지 않음.

**규약:**
- 손익/현금흐름 = `by_period_type("duration").by_period_length(3)`, BS/발행주식수 = `by_period_type("instant")` (Pitfall 3 — instant/duration 혼동 금지).
- 캘린더 분기 키 = `f.get_display_period_key()` (D-08, edgartools 내장 — 직접 구현 금지).
- as-reported 그대로 저장, Q4 보정·분기 분해는 **Phase 8** (D-05).
- [A5] concept 빈 결과 시 `get_total_assets`/`get_shareholders_equity` 등 헬퍼 fallback.

---

### `src/stocksig/io/dart_client.py` (client, batch raw 추출) — 수정·additive

**Analog:** 동일 파일 `fetch_dart_raw` L114-161. **기존 함수 불변** — `fetch_dart_quarterly_raw` / `probe_dart_rcept` **신규 추가**.

**재사용 헬퍼 (그대로 호출, 수정 없음):**
- `_parse_amount` L60-71 — 쉼표 문자열 → int, None-safe (T-03-10, ASVS V5).
- `_match_amount` L80-103 — account_id 1차 / account_nm 2차 매핑.
- `_income_rows` L73-77 — sj_div 필터. → BS/CF용 `_balance_sheet_rows`/`_cashflow_rows`를 동형으로 신규 추가(`SJ_DIV_BALANCE_SHEET`/`SJ_DIV_CASHFLOW` 사용).
- status 가드 `_STATUS_NOTES` L43-47 + `isinstance(resp, dict)` 검사 L134-138 + 빈 df 가드 L141-143 — 분기 루프 각 호출에 재사용.

**분기 백필 루프** — RESEARCH §"DART 분기 백필" L417-438이 시드. 기존 단일연도 `fetch_dart_raw(ticker, year)`를 `for year in range(...) for code in QUARTER_CODES` 루프로 확장:
```python
QUARTER_CODES = ["11013", "11012", "11014", "11011"]   # 1Q/반기/3Q/연간
resp = dart.finstate_all(stock_code, year, reprt_code=code, fs_div="CFS")
rcept = resp.iloc[0]["rcept_no"]   # 매 행 동일 (fixture COLUMNS[0] [VERIFIED])
```

**규약:**
- stock_code 파싱 = `ticker.split(".")[0]` L127 패턴.
- DART YTD 누적값 as-reported 그대로 저장 + period 메타(reprt_code, bsns_year) 보존 (Pitfall 4, D-05). `thstrm_add_amount`(fixture COLUMNS에 존재)도 함께 저장 권고(Phase 8 입력).
- 결손=`None` (`_empty_raw` L106-111 발상 유지).
- `@throttled_dart` 적용 (2 RPS). OpenDartReader 인스턴스는 신규 경로에서 모듈 싱글톤(Pitfall 1).

---

### `src/stocksig/io/dart_account_map.py` (config, lookup table) — 수정·additive

**Analog:** 동일 파일 `DART_ACCOUNT_ID_MAP` L31-51 / `DART_ACCOUNT_MAP` L55-65. **신규 필드 행 추가**(기존 5종 불변):

**확장 키** (D-03 슈퍼셋): `total_equity`(자본총계), `total_liabilities`(부채총계), `total_assets`(총자산), `operating_cash_flow`(영업현금흐름), `shares_outstanding`(발행주식수).

**패턴** (L31-51 구조 그대로 — id 1차 tuple / nm 2차 tuple, `[VERIFIED]` 주석 컨벤션):
```python
# 1차 account_id 후보(표준 IFRS 태그) + 2차 account_nm 한글 후보 tuple.
"total_assets": ("ifrs-full_Assets", ...),       # [Open Q2 — 005930 실응답 1회 확정 후 [VERIFIED]]
```

**신규 상수 추가** — `SJ_DIV_INCOME_STATEMENT` L69 옆에:
```python
SJ_DIV_BALANCE_SHEET: tuple[str, ...] = ("BS",)
SJ_DIV_CASHFLOW: tuple[str, ...] = ("CF",)
```

**규약:** account_id(표준 태그) 1차 / account_nm(한글) 2차 (업종 간 안정성). **[Open Q2]** BS/CF/shares account_id는 미검증 — executor가 005930 `finstate_all(sj_div='BS','CF')` 실응답 1회로 확정. 발행주식수가 finstate_all에 없으면 별도 처리(planner 범위 결정).

---

### `src/stocksig/main_run.py` (orchestrator, 진입점) — 수정

**Analog:** 동일 파일 `run()` L234-351.

**카운터 reset/요약 패턴** — L252 `cache.reset_cache_stats()` + L325-345 요약 블록 복제. 히스토리 경로용:
```python
# L252 패턴 → run 시작부에 store.reset_delta_stats() 추가
# L337-345 패턴 → 요약 블록에 델타 hit/miss/full-fetch 줄 추가:
logger.info("히스토리: 델타 HIT %d/MISS %d · full-fetch %d", ...)
```
→ T-04-01 준수: 카운트(정수)·티커 심볼만 출력, API 키/예외 원문 미포함 (L324 주석).

**진입 시점** — RESEARCH Open Q3 L474-477 권고: PASS1/PASS2 시트1 경로(L277-314) **불변**, run() 종료부 근처(요약 블록 L325 직전)에 **별도 순차 루프**로 히스토리 경로 호출(시트1 회귀 위험 0 우선; SQLite write는 `_store_lock` 직렬화라 동시성 이득 적음).

**규약:** D-06 — 시트1 fundamentals 경로·`.cache/fundamentals` 불변. 히스토리 경로는 additive.

---

### `.gitignore` — 수정

기존 `.cache/` 라인 옆에 `data/` 또는 `data/fundamentals.db` 추가 (SC5 — DB 미커밋). 현재 `data/` 미등재.

---

## Shared Patterns

### 모듈 싱글톤 + double-checked locking
**Source:** `src/stocksig/io/cache.py` L44-72 (`_cache_lock` + `_get_cache`)
**Apply to:** `fundamentals_store.get_store()`(sqlite 연결), `fundamentals_delta._get_dart()`(OpenDartReader 인스턴스)
```python
if _x is None:                 # fast-path
    with _x_lock:
        if _x is None:         # double-checked
            _x = <생성>
return _x
```

### hit/miss 카운터 (lock-protected read-modify-write)
**Source:** `src/stocksig/io/cache.py` L33-62, L91-96
**Apply to:** `fundamentals_store` 델타 카운터(`delta_hit`/`delta_miss`/`full_fetch`), `main_run` 요약 블록
- `+=`는 반드시 `with _stats_lock:` 안에서 (ThreadPoolExecutor lost-update 방지).
- `get_*_stats()`는 `dict(...)` 복사본 반환.

### throttle 데코레이터
**Source:** `src/stocksig/io/throttle.py` L35-58 (`@throttled_edgar` 8 RPS / `@throttled_dart` 2 RPS)
**Apply to:** 신규 `fetch_*_quarterly_raw`, `probe_*` 함수 전부 (외부 호출 함수에 직접 데코레이트).

### 결손 = None (0/-999999 금지)
**Source:** `edgar_client.py` L68/L88 주석 + `dart_client.py` `_parse_amount` L60-71 / `_empty_raw` L106-111
**Apply to:** 전 raw 추출 + sqlite `value` 컬럼(NULL 허용). D-05 잠긴 결정.

### SQL 파라미터 바인딩 (ASVS V5)
**Source:** RESEARCH §Code Examples (전 SQL이 `?` 바인딩)
**Apply to:** `fundamentals_store` 전 쿼리. f-string/`%` SQL 금지(SQL injection 차단).

### 테스트 격리 fixture (운영 store 오염 방지 — 필수)
**Source:** `tests/conftest.py` `_isolated_disk_cache` L23-47 (autouse, tmp_path monkeypatch + teardown `close()`)
**Apply to:** 신규 `_isolated_fundamentals_db` fixture — `_DB_PATH`를 tmp_path로 monkeypatch + `_conn=None` 리셋 + teardown `conn.close()`(Windows tmp 정리 PermissionError 방지, Pitfall 5). RESEARCH Wave 0 Gaps L538 필수 명시.

### DART 매핑 lookup (id 1차 / nm 2차)
**Source:** `dart_client.py` `_match_amount` L80-103 + `dart_account_map.py` L31-65
**Apply to:** 신규 BS/CF/shares 추출 — 동일 2단 매핑 헬퍼 재사용.

---

## No Analog Found

전 파일 강한 codebase analog 확보. 단 아래 **세부 기법**은 코드베이스 선례가 없어 RESEARCH 시드를 따른다:

| 항목 | 역할 | 데이터 흐름 | 사유 / 출처 |
|------|------|-------------|-------------|
| sqlite3 `INSERT...ON CONFLICT DO UPDATE` upsert | store | CRUD | 코드베이스에 raw sqlite3 사용처 없음(diskcache만). → RESEARCH L371-388 시드 + sqlite.org/lang_UPSERT |
| EDGAR `facts.query().by_period_type()` 빌더 | client | batch | 기존 `edgar_client.py`는 TTM accessor만 사용. per-quarter query 빌더는 신규. → RESEARCH Pattern 1 L179-213 |
| WAL + busy_timeout PRAGMA | store | — | 코드베이스 선례 없음(diskcache 내부 처리). → RESEARCH SCHEMA L314-315 + Pitfall 5 |

---

## Metadata

**Analog search scope:** `src/stocksig/io/` (cache, edgar_client, dart_client, dart_account_map, throttle), `src/stocksig/main_run.py`, `tests/conftest.py`, `tests/fixtures/dart_005930_finstate.py`
**Files scanned:** 8 (전 1차 analog 직접 read)
**Pattern extraction date:** 2026-06-18
