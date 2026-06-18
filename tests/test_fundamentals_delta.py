"""FUND-08 / SC3 회귀 테스트 — fundamentals_delta 접수번호 델타 오케스트레이션.

검증 대상(Wave 0 RED → Task 2 GREEN):
  - D-02: 저장된 last_accession == 최신 접수번호(probe) → full-fetch 생략·신규 저장 0,
    mark_delta_hit (test_same_accession_skips_fetch).
  - D-02: 접수번호 변경 시에만 재추출 → fetch 1회·upsert·set_last_accession 갱신
    (forward 누적), mark_delta_miss + mark_full_fetch (test_changed_accession_refetches).
  - delta_state 부재 → 첫 backfill 경로(full-fetch) (test_no_state_triggers_first_fetch).
  - probe 실패(예외/None) → fetch 0·count_rows 불변·last_accession 미갱신
    (Pitfall 2, T-07-07, test_probe_failure_keeps_db).
  - SC3(≈0): 여러 종목 전부 동일 accession → fetch 총 0·full_fetch==0·delta_hit==종목수
    (test_steady_state_zero_full_calls).

probe 는 `mocker.patch("...probe_edgar_accession")` 로 반환값 지정(네트워크 0),
full-fetch spy 는 `mocker.spy(edgar_client, "fetch_edgar_quarterly_raw")` 의
`.call_count` 단언. delta_state 시드는 `fs.set_last_accession(...)`,
≈0 검증은 `fs.reset_delta_stats()` → sync 루프 → `fs.get_delta_stats()`.
운영 DB 는 conftest `_isolated_fundamentals_db` 로 tmp_path 격리됨.
"""

from __future__ import annotations

from stocksig.io import edgar_client
from stocksig.io import fundamentals_delta as fd
from stocksig.io import fundamentals_store as fs

# 추출기가 반환하는 11-key dict 행(quarter raw). delta 가 12-tuple(+fetched_at)로
# 변환해 upsert 한다 — Plan 02 계약(Notes for Downstream Plans).
_FETCH_ROW = {
    "ticker": "AAPL",
    "source": "EDGAR",
    "quarter": "2026Q1",
    "field": "revenue",
    "value": 1000.0,
    "unit": "USD",
    "accession": "ACC2",
    "period_start": "2026-01-01",
    "period_end": "2026-03-31",
    "period_type": "duration",
    "reprt_code": None,
}


def test_same_accession_skips_fetch(mocker):
    """D-02: 저장된 last_accession == probe → full-fetch 0, 신규 저장 0, delta_hit 1회."""
    fs.set_last_accession("AAPL", "EDGAR", "ACC1")
    mocker.patch.object(fd, "probe_edgar_accession", return_value="ACC1")
    spy = mocker.spy(edgar_client, "fetch_edgar_quarterly_raw")
    fs.reset_delta_stats()

    fd.sync_ticker_history("AAPL", "EDGAR")

    assert spy.call_count == 0  # 델타 없음 → full-fetch 생략
    assert fs.count_rows("AAPL") == 0  # 신규 저장 없음
    stats = fs.get_delta_stats()
    assert stats["delta_hit"] == 1
    assert stats["full_fetch"] == 0


def test_changed_accession_refetches(mocker):
    """D-02: probe 가 다른 접수번호 → fetch 1회·upsert·set_last_accession 갱신(forward 누적)."""
    fs.set_last_accession("AAPL", "EDGAR", "ACC1")
    mocker.patch.object(fd, "probe_edgar_accession", return_value="ACC2")
    mocker.patch.object(
        edgar_client, "fetch_edgar_quarterly_raw", return_value=[dict(_FETCH_ROW)]
    )
    fs.reset_delta_stats()

    fd.sync_ticker_history("AAPL", "EDGAR")

    assert edgar_client.fetch_edgar_quarterly_raw.call_count == 1
    assert fs.count_rows("AAPL") == 1  # upsert 발생
    assert fs.get_last_accession("AAPL", "EDGAR") == "ACC2"  # forward 누적 갱신
    stats = fs.get_delta_stats()
    assert stats["delta_miss"] == 1
    assert stats["full_fetch"] == 1


def test_no_state_triggers_first_fetch(mocker):
    """delta_state 부재 + probe "ACC1" → 첫 backfill(full-fetch) 경로."""
    assert fs.get_last_accession("AAPL", "EDGAR") is None
    mocker.patch.object(fd, "probe_edgar_accession", return_value="ACC1")
    row = dict(_FETCH_ROW, accession="ACC1")
    mocker.patch.object(edgar_client, "fetch_edgar_quarterly_raw", return_value=[row])
    fs.reset_delta_stats()

    fd.sync_ticker_history("AAPL", "EDGAR")

    assert edgar_client.fetch_edgar_quarterly_raw.call_count == 1
    assert fs.count_rows("AAPL") == 1
    assert fs.get_last_accession("AAPL", "EDGAR") == "ACC1"


def test_probe_failure_keeps_db(mocker):
    """Pitfall 2 / T-07-07: probe 예외 → fetch 0·count_rows 불변·last_accession 미갱신."""
    fs.set_last_accession("AAPL", "EDGAR", "ACC1")
    # 기존 DB 1행 시드
    fs.upsert_quarters(
        [(
            "AAPL", "EDGAR", "2025Q4", "revenue", 900.0, "USD", "ACC1",
            "2025-10-01", "2025-12-31", "duration", None, "2026-06-18T00:00:00",
        )]
    )
    before = fs.count_rows("AAPL")
    mocker.patch.object(
        fd, "probe_edgar_accession", side_effect=RuntimeError("EDGAR 메타 실패")
    )
    spy = mocker.spy(edgar_client, "fetch_edgar_quarterly_raw")
    fs.reset_delta_stats()

    fd.sync_ticker_history("AAPL", "EDGAR")  # 예외 흡수, 갱신 생략

    assert spy.call_count == 0  # 보수적 재추출 금지
    assert fs.count_rows("AAPL") == before  # 기존 DB 유지
    assert fs.get_last_accession("AAPL", "EDGAR") == "ACC1"  # 미갱신


def test_probe_none_keeps_db(mocker):
    """probe 가 None(빈 메타) → fetch 0·기존 DB 유지(보수적 재추출 안 함)."""
    fs.set_last_accession("AAPL", "EDGAR", "ACC1")
    mocker.patch.object(fd, "probe_edgar_accession", return_value=None)
    spy = mocker.spy(edgar_client, "fetch_edgar_quarterly_raw")
    fs.reset_delta_stats()

    fd.sync_ticker_history("AAPL", "EDGAR")

    assert spy.call_count == 0
    assert fs.count_rows("AAPL") == 0
    assert fs.get_last_accession("AAPL", "EDGAR") == "ACC1"


def test_steady_state_zero_full_calls(mocker):
    """D-02/SC3: 여러 종목 전부 동일 accession → fetch 총 0·full_fetch==0·delta_hit==종목수."""
    tickers = ["AAPL", "MSFT", "GOOG"]
    for t in tickers:
        fs.set_last_accession(t, "EDGAR", f"ACC-{t}")
    # probe 가 저장된 값과 동일 반환 → 전부 SKIP
    mocker.patch.object(
        fd, "probe_edgar_accession", side_effect=lambda t: f"ACC-{t}"
    )
    spy = mocker.spy(edgar_client, "fetch_edgar_quarterly_raw")
    fs.reset_delta_stats()

    for t in tickers:
        fd.sync_ticker_history(t, "EDGAR")

    assert spy.call_count == 0  # 평소 실행 외부 전체호출 ≈0 (SC3)
    stats = fs.get_delta_stats()
    assert stats["full_fetch"] == 0
    assert stats["delta_hit"] == len(tickers)
