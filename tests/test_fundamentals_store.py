"""FUND-07 회귀 테스트 — fundamentals_store SQLite 영구 store 계약.

검증 대상(Wave 0 → Wave 1 GREEN):
  - upsert_quarters 후 raw_facts 행 생성 (count_rows)
  - 재실행(같은 rows 재upsert) 시 과거 분기 보존 — 행 수 불변
  - 정정공시(같은 유니크 키 (ticker,source,quarter,field) + 다른 accession/value)
    upsert 시 행 수 불변·최신값 덮어쓰기 (D-09)
  - 새 분기 추가 시 행 수 증가만, 기존 분기 보존
  - 결손값 None → SQLite NULL 저장 (0/-999999 금지, D-05)
  - last_accession set/get 라운드트립 + 미존재 시 None

12-tuple rows 컬럼 순서(SCHEMA UPSERT 순서):
  ticker, source, quarter, field, value, unit, accession,
  period_start, period_end, period_type, reprt_code, fetched_at
"""

from __future__ import annotations

from stocksig.io import fundamentals_store as fs


def _row(
    ticker: str = "AAPL",
    source: str = "EDGAR",
    quarter: str = "2026Q1",
    field: str = "revenue",
    value: float | None = 1000.0,
    accession: str = "acc-0001",
) -> tuple:
    """12-tuple raw_facts 행 헬퍼 (컬럼 순서 = SCHEMA UPSERT 순서)."""
    return (
        ticker,
        source,
        quarter,
        field,
        value,
        "USD",
        accession,
        "2026-01-01",
        "2026-03-31",
        "duration",
        None,
        "2026-06-18T00:00:00",
    )


def test_upsert_creates_db():
    """upsert_quarters 1회 후 raw_facts 행이 존재 (count_rows == N)."""
    rows = [_row(field="revenue"), _row(field="net_income", value=200.0)]
    fs.upsert_quarters(rows)
    assert fs.count_rows() == 2
    assert fs.count_rows("AAPL") == 2


def test_rerun_preserves_past_quarters():
    """같은 rows 재upsert → count_rows 불변(증가/삭제 없음)."""
    rows = [_row(field="revenue"), _row(field="net_income", value=200.0)]
    fs.upsert_quarters(rows)
    n1 = fs.count_rows()
    fs.upsert_quarters(rows)  # 재실행 (동일 키)
    assert fs.count_rows() == n1 == 2


def test_amendment_upsert_overwrites():
    """D-09: 같은 (ticker,source,quarter,field) + 다른 accession/value
    → 행 수 불변, value/accession만 최신값으로 갱신."""
    fs.upsert_quarters([_row(field="revenue", value=1000.0, accession="acc-0001")])
    assert fs.count_rows() == 1

    # 정정공시: 같은 유니크 키, 새 accession + 정정된 value
    fs.upsert_quarters([_row(field="revenue", value=1234.5, accession="acc-0002")])
    assert fs.count_rows() == 1  # 행 수 불변

    cur = fs.get_store().execute(
        "SELECT value, accession FROM raw_facts "
        "WHERE ticker=? AND source=? AND quarter=? AND field=?",
        ("AAPL", "EDGAR", "2026Q1", "revenue"),
    )
    value, accession = cur.fetchone()
    assert value == 1234.5  # 최신값 덮어쓰기
    assert accession == "acc-0002"  # 정정 메타 갱신


def test_add_new_quarter_grows_only():
    """새 quarter 행 추가 → count_rows 증가만, 기존 분기 행 보존."""
    fs.upsert_quarters([_row(quarter="2026Q1", field="revenue")])
    assert fs.count_rows() == 1
    fs.upsert_quarters([_row(quarter="2026Q2", field="revenue")])
    assert fs.count_rows() == 2  # 과거(Q1) 보존 + 신규(Q2) 추가

    cur = fs.get_store().execute(
        "SELECT COUNT(*) FROM raw_facts WHERE quarter=?", ("2026Q1",)
    )
    assert cur.fetchone()[0] == 1  # Q1 행 삭제되지 않음


def test_none_stored_as_null():
    """value=None upsert → SELECT 결과 value IS NULL (0/-999999 아님, D-05)."""
    fs.upsert_quarters([_row(field="eps", value=None)])
    cur = fs.get_store().execute(
        "SELECT value FROM raw_facts WHERE ticker=? AND field=?", ("AAPL", "eps")
    )
    (value,) = cur.fetchone()
    assert value is None  # SQLite NULL — 0/-999999 sentinel 금지

    # NULL IS NULL 술어로도 검증
    cur2 = fs.get_store().execute(
        "SELECT COUNT(*) FROM raw_facts WHERE field=? AND value IS NULL", ("eps",)
    )
    assert cur2.fetchone()[0] == 1


def test_last_accession_roundtrip():
    """set_last_accession 후 get_last_accession이 동일 문자열 반환, 미존재 시 None."""
    assert fs.get_last_accession("AAPL", "EDGAR") is None  # 미존재
    fs.set_last_accession("AAPL", "EDGAR", "acc-9999")
    assert fs.get_last_accession("AAPL", "EDGAR") == "acc-9999"

    # 재설정(정정공시 갱신) → 최신값, 행 추가 없음
    fs.set_last_accession("AAPL", "EDGAR", "acc-10000")
    assert fs.get_last_accession("AAPL", "EDGAR") == "acc-10000"
    cur = fs.get_store().execute(
        "SELECT COUNT(*) FROM delta_state WHERE ticker=? AND source=?",
        ("AAPL", "EDGAR"),
    )
    assert cur.fetchone()[0] == 1
