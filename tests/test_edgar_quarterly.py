"""Plan 07-02 Task 2: edgar_client.fetch_edgar_quarterly_raw — per-quarter raw 추출.

`mocker.patch("stocksig.io.edgar_client.Company")` 로 외부 호출 차단(test_edgar_client.py
analog). FakeQuarterlyFacts(query 빌더 mock)로 분기별 손익(duration)·BS(instant)·CF·
shares 행을 구성하고 추출기가:
  - get_facts() 1회만 호출(D-01 공짜 backfill, 추가 set_identity 없음)
  - D-08 quarter "YYYYQn" 정규화
  - instant/duration 필드 구분(Pitfall 3, D-04 BS vs 손익)
  - 결손 value=None(D-05, 0/-999999 아님)
  - accession 보존
를 단언한다. 네트워크 0(mock).
"""

from __future__ import annotations

from fixtures.edgar_aapl_facts import (
    AAPL_QUARTERLY_STORE,
    AAPL_SHARES_FACT,
    FakeQuarterlyFacts,
)


def _patch_company(mocker, shares_fact=AAPL_SHARES_FACT):
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    fake_facts = FakeQuarterlyFacts(AAPL_QUARTERLY_STORE, shares_fact=shares_fact)
    mock_company.return_value.get_facts.return_value = fake_facts
    return mock_company


def test_returns_list_of_quarter_rows(mocker):
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")

    assert isinstance(rows, list)
    assert len(rows) > 0
    for r in rows:
        assert r["ticker"] == "AAPL"
        assert r["source"] == "EDGAR"
        assert "field" in r and "value" in r and "accession" in r


def test_get_facts_called_once(mocker):
    # D-01: get_facts 1회만(과거 분기 전부 공짜 backfill).
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    mock_company = _patch_company(mocker)
    fetch_edgar_quarterly_raw("AAPL")

    assert mock_company.return_value.get_facts.call_count == 1


def test_quarter_key_normalized_yyyyqn(mocker):
    # D-08: quarter 키가 "YYYYQn" (예 "2026Q2").
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")

    quarters = {r["quarter"] for r in rows}
    assert "2026Q2" in quarters
    assert "2026Q1" in quarters  # Revenue 에 2026Q1 행 포함
    # 모든 quarter 가 YYYYQn 형식
    for q in quarters:
        assert len(q) == 6 and q[4] == "Q" and q[:4].isdigit()


def test_instant_vs_duration_field_split(mocker):
    # D-04: BS(instant) vs 손익/CF(duration) period_type 구분.
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")
    by_field = {r["field"]: r for r in rows}

    assert by_field["total_assets"]["period_type"] == "instant"
    assert by_field["total_equity"]["period_type"] == "instant"
    assert by_field["total_liabilities"]["period_type"] == "instant"
    assert by_field["revenue"]["period_type"] == "duration"
    assert by_field["operating_cash_flow"]["period_type"] == "duration"


def test_new_d04_fields_extracted(mocker):
    # D-04 신규 필드(total_equity/total_liabilities/total_assets/operating_cash_flow/shares).
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")
    fields = {r["field"] for r in rows}

    for f in ("total_equity", "total_liabilities", "total_assets",
              "operating_cash_flow", "shares_outstanding"):
        assert f in fields, f"{f} 누락"


def test_missing_value_is_none(mocker):
    # D-05: numeric_value=None 인 GrossProfit 행은 value=None (0/-999999 아님).
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")
    gp = [r for r in rows if r["field"] == "gross_profit"]

    assert gp, "gross_profit 행 존재"
    assert gp[0]["value"] is None


def test_accession_preserved(mocker):
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")
    rev_q2 = [r for r in rows if r["field"] == "revenue" and r["quarter"] == "2026Q2"]

    assert rev_q2
    assert rev_q2[0]["accession"] == "0000320193-26-000050"


def test_shares_skipped_when_absent(mocker):
    # shares_outstanding_fact 부재 시 해당 행 skip(에러 없음).
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker, shares_fact=None)
    rows = fetch_edgar_quarterly_raw("AAPL")
    fields = {r["field"] for r in rows}

    assert "shares_outstanding" not in fields
    # 다른 필드는 정상 추출
    assert "revenue" in fields


# --- 260627-vpn Task 1: _calendar_quarter_key 최종 반환 가드 회귀 ---


class _FakeFact:
    """FinancialFact 흉내 최소 스텁 — get_display_period_key 만 보유.

    생성자 표시 키를 그대로 돌려준다. 네트워크/외부 호출 0.
    """

    def __init__(self, display_key):
        self._display_key = display_key

    def get_display_period_key(self):
        return self._display_key


def test_calendar_quarter_key_fy_label_rejected():
    # 핵심: 연간 프레임 "FY 2026" 은 분기 키가 아니므로 None (docstring '실패 시 None').
    from stocksig.io.edgar_client import _calendar_quarter_key

    assert _calendar_quarter_key(_FakeFact("FY 2026")) is None


def test_calendar_quarter_key_q_year_normalized():
    # 정상 경로 유지: "Q2 2026" → "2026Q2".
    from stocksig.io.edgar_client import _calendar_quarter_key

    assert _calendar_quarter_key(_FakeFact("Q2 2026")) == "2026Q2"


def test_calendar_quarter_key_year_q_normalized():
    # 정상 경로 유지: "2026 Q2" → "2026Q2".
    from stocksig.io.edgar_client import _calendar_quarter_key

    assert _calendar_quarter_key(_FakeFact("2026 Q2")) == "2026Q2"


def test_calendar_quarter_key_already_normalized_token():
    # 회귀 주의: 공백 없는 정상 키 "2026Q2" 는 최종 게이트를 통과해야 한다.
    from stocksig.io.edgar_client import _calendar_quarter_key

    assert _calendar_quarter_key(_FakeFact("2026Q2")) == "2026Q2"


def test_calendar_quarter_key_empty_returns_none():
    # 빈 키 가드.
    from stocksig.io.edgar_client import _calendar_quarter_key

    assert _calendar_quarter_key(_FakeFact("")) is None


def test_calendar_quarter_key_none_returns_none():
    # get_display_period_key 가 None 반환 → None.
    from stocksig.io.edgar_client import _calendar_quarter_key

    assert _calendar_quarter_key(_FakeFact(None)) is None
