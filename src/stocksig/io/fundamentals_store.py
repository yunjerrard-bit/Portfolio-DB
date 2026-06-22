"""펀더멘털 영구 store (SQLite WAL, `data/fundamentals.db`).

책임: 분기별 원천 raw long 테이블(`raw_facts`)과 델타용 state 테이블
(`delta_state`)을 단일 진원지로 제공한다. Phase 8(지표 계산)·Phase 9(트렌드
엑셀)의 백엔드이며, 추출(Plan 02)·델타(Plan 03)·오케스트레이션(Plan 04)이
이 store 위에서 동작한다.

설계 불변 (locked):
  - D-H3: 영구 누적, **TTL 없음**. `expire`/`ttl` 컬럼을 절대 추가하지 않는다
    (기존 `.cache/` OHLCV 7일 TTL과 별개). 과거 분기가 사라지지 않는 것이 Core.
  - D-09: raw_facts 유니크 키 = `(ticker, source, quarter, field)`. 정정공시(같은
    분기·새 accession) 재추출 시 ON CONFLICT DO UPDATE로 최신값 덮어쓰기
    (정정 이력 미보존, 매트릭스 = 최신 진실).
  - D-05: 결손값은 NULL로 저장 (0/-999999 sentinel 금지) → Phase 8 계산 오염 차단.
  - ASVS V5(T-07-01): 전 SQL은 `?` 파라미터 바인딩만. f-string/`%` SQL 금지.

동시성 (Pitfall 5 / T-07-03): `PRAGMA journal_mode=WAL` + `busy_timeout=5000` +
`check_same_thread=False`, write는 `_store_lock`으로 직렬화. 싱글톤 초기화는
cache.py `_cache_lock` 더블체크 락 패턴을 복제한다.
"""
from __future__ import annotations

import logging
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_DB_PATH = Path("data/fundamentals.db")
_conn: sqlite3.Connection | None = None

# 연결 초기화(더블체크 락) + write 직렬화 겸용 (cache.py `_cache_lock` 패턴).
_store_lock = threading.Lock()

# --- 델타 hit/miss 카운터 (cache.py L33-62 복제) -------------------------
# read-modify-write `+=` 는 ThreadPoolExecutor fan-out 하에서 lost-update
# 가능 → _stats_lock 으로 보호. 싱글톤 lock(_store_lock)과는 분리한다.
_stats: dict[str, int] = {
    "delta_hit": 0,
    "delta_miss": 0,
    "full_fetch": 0,
}
_stats_lock = threading.Lock()

# --- 스키마 DDL (D-H3 TTL 없음 + D-05 NULL + D-09 유니크 키) -------------
SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA busy_timeout=5000;

CREATE TABLE IF NOT EXISTS raw_facts (
    ticker        TEXT NOT NULL,
    source        TEXT NOT NULL,          -- 'EDGAR' | 'DART' | 'yf' | 'Naver'
    quarter       TEXT NOT NULL,          -- 캘린더 분기 'YYYYQn' (D-08)
    field         TEXT NOT NULL,          -- 'revenue','gross_profit','op_income',...
    value         REAL,                   -- NULL 허용 (D-05 결손=NULL, 0 금지)
    unit          TEXT,                   -- 'USD' | 'KRW' | 'shares'
    accession     TEXT,                   -- EDGAR accession / DART rcept_no (정정 메타)
    period_start  TEXT,                   -- ISO date (duration 시작)
    period_end    TEXT,                   -- ISO date (분기 종료일)
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

# --- upsert SQL (정정공시 덮어쓰기 — D-09) ------------------------------
# 컬럼 순서 = upsert_quarters rows 12-tuple 순서 (Plan 02/03/04 계약).
_UPSERT = """
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

_SET_ACCESSION = """
INSERT INTO delta_state (ticker, source, last_accession, last_checked_at)
VALUES (?,?,?,?)
ON CONFLICT(ticker, source) DO UPDATE SET
   last_accession=excluded.last_accession,
   last_checked_at=excluded.last_checked_at;
"""


def _now_iso() -> str:
    """현재 시각 ISO 문자열 (fetched_at / last_checked_at 메타용)."""
    return datetime.now().isoformat(timespec="seconds")


def get_store() -> sqlite3.Connection:
    """단일 sqlite3 연결 반환 (더블체크 락 + WAL/스키마 멱등 적용).

    cache.py `_get_cache()` L65-72 패턴 복제. fast-path는 lock 없이 hot path
    비용 0, 미초기화 시에만 `_store_lock` 하에서 디렉터리 생성 + 연결 + 스키마.
    """
    global _conn
    if _conn is None:  # fast-path (lock 없음)
        with _store_lock:
            if _conn is None:  # double-checked (lock 내 재확인)
                _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
                _conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
                _conn.executescript(SCHEMA)
    return _conn


def upsert_quarters(rows: list[tuple]) -> None:
    """raw_facts 분기 행 upsert (D-09 정정공시 덮어쓰기).

    rows 각 원소는 12-tuple (ticker, source, quarter, field, value, unit,
    accession, period_start, period_end, period_type, reprt_code, fetched_at).
    같은 유니크 키 재추출 시 행 수 불변·최신값 덮어쓰기, 새 키는 행 추가만.
    write는 `_store_lock`으로 직렬화 (fan-out 안전, Pitfall 5).
    """
    conn = get_store()
    with _store_lock:
        conn.executemany(_UPSERT, rows)
        conn.commit()


def get_last_accession(ticker: str, source: str) -> str | None:
    """delta_state의 last_accession 조회. 미존재 시 None."""
    cur = get_store().execute(
        "SELECT last_accession FROM delta_state WHERE ticker=? AND source=?",
        (ticker, source),
    )
    row = cur.fetchone()
    return row[0] if row else None


def set_last_accession(ticker: str, source: str, accession: str) -> None:
    """delta_state에 last_accession upsert (정정공시 갱신 시 행 추가 없음)."""
    conn = get_store()
    with _store_lock:
        conn.execute(_SET_ACCESSION, (ticker, source, accession, _now_iso()))
        conn.commit()


def count_rows(ticker: str | None = None) -> int:
    """raw_facts 행 수 (과거 분기 보존 회귀 검증용). ticker 지정 시 해당 종목만."""
    if ticker is not None:
        cur = get_store().execute(
            "SELECT COUNT(*) FROM raw_facts WHERE ticker=?", (ticker,)
        )
    else:
        cur = get_store().execute("SELECT COUNT(*) FROM raw_facts")
    return cur.fetchone()[0]


def fetch_raw_quarters(ticker: str) -> list[tuple]:
    """raw_facts 분기 행을 quarter 오름차순 + source 우선순위로 조회 (Phase 8 엔진 입력).

    각 행 = (quarter, source, field, value, period_type, reprt_code, unit).
    value는 결손 시 None(D-05). 미존재 ticker는 빈 list.
    `count_rows`(L155-163) analog — `get_store()` 재사용(신규 connection 금지),
    전 SQL `?` 파라미터 바인딩(ASVS V5, f-string/`%` SQL 금지, T-08-01).

    **결정적 source 우선순위(WR-01 — EDGAR→DART→yf):** 동일 `(quarter, field)`에 복수
    source 행이 있을 때, 소비 측 `metrics_engine._normalize_quarters`가 마지막-행-우선
    덮어쓰기(L101 `out[(q,field)]=...`)이므로, **우선순위가 높은 source(EDGAR)가 정렬상
    마지막에 오도록** 2차 정렬키를 `DESC`로 둔다. CASE source ... 는 SQL 리터럴이며 사용자
    입력 미진입(T-08-01 불변 — `?`-바인딩·`get_store()` 재사용 유지). 방향 정확성의 단일
    진실원천은 결정성 단언 테스트(EDGAR 최종 선택·반복 동일)이다.
    """
    cur = get_store().execute(
        "SELECT quarter, source, field, value, period_type, reprt_code, unit "
        "FROM raw_facts WHERE ticker=? "
        "ORDER BY quarter, "
        "CASE source WHEN 'EDGAR' THEN 0 WHEN 'DART' THEN 1 WHEN 'yf' THEN 2 ELSE 3 END "
        "DESC",
        (ticker,),
    )
    return cur.fetchall()


# --- 델타 hit/miss 카운터 API (cache.py reset/get_stats 복제) -----------


def reset_delta_stats() -> None:
    """run 시작 시 델타 카운터 초기화."""
    with _stats_lock:
        for k in _stats:
            _stats[k] = 0


def get_delta_stats() -> dict[str, int]:
    """현재 델타 카운터의 *복사본* 반환 (반환값 변형이 내부 상태를 오염시키지 않음)."""
    with _stats_lock:
        return dict(_stats)


def mark_delta_hit() -> None:
    """델타 조회 결과 = 변동 없음(외부 전체호출 생략)."""
    with _stats_lock:
        _stats["delta_hit"] += 1


def mark_delta_miss() -> None:
    """델타 조회 결과 = 변동 감지(새 분기/정정공시 → 전체 facts 재추출)."""
    with _stats_lock:
        _stats["delta_miss"] += 1


def mark_full_fetch() -> None:
    """델타 state 부재 등으로 전체 백필 수행."""
    with _stats_lock:
        _stats["full_fetch"] += 1
