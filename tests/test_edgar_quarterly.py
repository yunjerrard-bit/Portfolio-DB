"""Plan 07-02 Task 2 + 260629-hec: edgar_client.fetch_edgar_quarterly_raw 추출 + 5.35.0 마이그레이션.

`mocker.patch("stocksig.io.edgar_client.Company")` 로 외부 호출 차단(test_edgar_client.py
analog). FakeQuarterlyFacts(query 빌더 mock)로 분기별 손익(quarterly)·BS(by_concept→instant
필터)·CF·shares 행을 구성하고 추출기가:
  - get_facts() 1회만 호출(D-01 공짜 backfill, 추가 set_identity 없음)
  - period_end 월 기반 캘린더 분기 "YYYYQn" 정규화
  - instant/duration 필드 구분(Pitfall 3, D-04 BS vs 손익)
  - 결손 value=None(D-05, 0/-999999 아님)
  - accession 보존
를 단언한다. 네트워크 0(mock).

260629-hec(edgartools 5.35.0): by_period_type("duration"/"instant") → ValidationError 로
US 전 결손이던 버그 수정. 유량은 by_period_type("quarterly")로, 저량(BS)은 by_concept 후
파이썬 instant 필터로 조회. _calendar_quarter_key 는 period_end 월 기반. _query_facts 는
예외를 WARNING 로깅. 중복 (quarter, field)는 filing_date 오름차순(최신 마지막).
"""

from __future__ import annotations

import logging

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
    # 260629-hec: 같은 (2026Q2, revenue)에 정정 fact 2건 — filing_date 오름차순 후 마지막이
    # 최신 정정값(accession ...050). 정렬 검증은 test_duplicate_facts_sorted_ascending 가 강화.
    assert rev_q2[-1]["accession"] == "0000320193-26-000050"


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


# --- 260629-hec Task 1: edgartools 5.35.0 by_period_type 마이그레이션 회귀 ---

import re  # noqa: E402 — 소스 단언용(아래 테스트 전용)
from pathlib import Path  # noqa: E402


class _FakeFactPE:
    """period_end(+선택 display_key) 보유 최소 스텁 — _calendar_quarter_key period_end 경로용."""

    def __init__(self, period_end=None, display_key=None):
        self.period_end = period_end
        self._display_key = display_key

    def get_display_period_key(self):
        return self._display_key


def test_no_duration_instant_period_type_in_source():
    # 핵심(LOCKED FACT 2): by_period_type("duration")·("instant") 문자열 0건,
    # by_period_type("quarterly") ≥1건 (US 전 결손 근본 원인 제거).
    src = Path("src/stocksig/io/edgar_client.py").read_text(encoding="utf-8")
    assert 'by_period_type("duration")' not in src
    assert 'by_period_type("instant")' not in src
    assert src.count('by_period_type("quarterly")') >= 1


def test_flow_concepts_use_quarterly(mocker):
    # 유량 6종(quarterly 조회) 추출 후 revenue/operating_cash_flow 행 존재 +
    # 저장 period_type 라벨 "duration"(실 fact.period_type 반영, LOCKED FACT 1).
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")
    by_field = {r["field"]: r for r in rows}

    assert "revenue" in by_field
    assert "operating_cash_flow" in by_field
    assert by_field["revenue"]["period_type"] == "duration"
    assert by_field["operating_cash_flow"]["period_type"] == "duration"


def test_instant_extracted_via_concept_filter(mocker):
    # BS 3종이 by_concept 만으로 취득되고 파이썬 instant 필터를 거쳐 period_type=="instant".
    # StockholdersEquity concept 에 duration 오염 fact 가 있어도 total_equity 행은 instant 만.
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")
    eq_rows = [r for r in rows if r["field"] == "total_equity"]

    assert eq_rows, "total_equity 행 존재"
    # 혼재 duration fact(999_999_999) 는 걸러지고 instant 행만 통과.
    for r in eq_rows:
        assert r["period_type"] == "instant"
    values = {r["value"] for r in eq_rows}
    assert 999_999_999.0 not in values  # duration 오염 fact 미통과
    assert 66_708_000_000.0 in values   # instant fact 통과


def test_calendar_quarter_key_from_period_end():
    # period_end 월 기반 캘린더 분기 (3월→Q1, 6월→Q2). 부재 시 display 차선책. FY/None→None.
    from stocksig.io.edgar_client import _calendar_quarter_key

    assert _calendar_quarter_key(_FakeFactPE(period_end="2026-03-28")) == "2026Q1"
    assert _calendar_quarter_key(_FakeFactPE(period_end="2026-06-30")) == "2026Q2"
    assert _calendar_quarter_key(_FakeFactPE(period_end="2026-12-31")) == "2026Q4"
    # period_end 부재 + display "Q2 2026" → 차선책으로 "2026Q2".
    assert _calendar_quarter_key(_FakeFactPE(period_end=None, display_key="Q2 2026")) == "2026Q2"
    # period_end·display 모두 부재 → None.
    assert _calendar_quarter_key(_FakeFactPE(period_end=None, display_key=None)) is None
    # display "FY 2026" → None (fullmatch 가드).
    assert _calendar_quarter_key(_FakeFactPE(period_end=None, display_key="FY 2026")) is None


def test_query_facts_logs_warning_on_exception(mocker, caplog):
    # _query_facts 가 내부 예외 시 빈 리스트 반환 + WARNING 로깅(조용한 삼킴 제거).
    from stocksig.io import edgar_client

    class _BoomFacts:
        def query(self):
            raise RuntimeError("boom")

    with caplog.at_level(logging.WARNING, logger=edgar_client.logger.name):
        result = edgar_client._query_facts(_BoomFacts(), "Revenue", "quarterly")

    assert result == []
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert warnings, "WARNING 레코드 존재"
    # concept 명·예외 타입명이 구조값으로 남음(렌더 텍스트 단언 아님).
    joined = " ".join(r.getMessage() for r in warnings)
    assert "Revenue" in joined
    assert "RuntimeError" in joined


def test_duplicate_facts_sorted_ascending(mocker):
    # 같은 (2026Q2, revenue)에 filing_date 다른 2 fact → 최신(filing_date 늦은)이 마지막.
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_company(mocker)
    rows = fetch_edgar_quarterly_raw("AAPL")
    rev_q2 = [r for r in rows if r["field"] == "revenue" and r["quarter"] == "2026Q2"]

    assert len(rev_q2) == 2, "정정 fact 2건 모두 추출"
    # filing_date 오름차순 → 마지막이 최신 정정값(95_359..., accession ...050).
    assert rev_q2[-1]["value"] == 95_359_000_000.0
    assert rev_q2[-1]["accession"] == "0000320193-26-000050"
    # 첫 행은 더 이른 filing_date 의 원본(94_000..., accession ...040).
    assert rev_q2[0]["value"] == 94_000_000_000.0
