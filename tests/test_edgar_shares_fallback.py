"""260701 커밋2: shares_outstanding us-gaap 폴백 TDD (네트워크 0).

부차 결손(백로그 근본원인 3): facts.shares_outstanding_fact 가 종목당 1행(dei concept)
또는 0행(dei:EntityCommonStockSharesOutstanding 부재)만 적재 → per-share 분모
(EPS_ttm/BPS/SPS/OCF_ps)·가격의존(PER/PBR/PCR/PSR) 분모가 비어 None.

수정: dei 단일행 폴백으로 us-gaap:CommonStockSharesOutstanding 등 분기별 instant fact
를 추가 추출해 분기별 shares 를 확보한다. 커밋1(Q4 도출)과 분리 커밋2(회귀 격리).

구조값 단언(렌더텍스트 금지):
  - shares_outstanding_fact=None 이어도 us-gaap 폴백으로 shares 행 존재.
  - 분기별(2025Q3·2025Q4) shares 행이 각각 있고 period_type="instant".
  - 기존 dei 단일행 경로는 회귀 없음(dei 존재 시 그대로 사용).
"""

from __future__ import annotations

from fixtures.edgar_q4_derive import (
    SHARES_Q4_EXPECTED,
    make_facts_shares_fallback,
)


def _patch_fallback(mocker):
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = make_facts_shares_fallback()
    return mock_company


def test_shares_fallback_when_dei_absent(mocker):
    """dei shares_outstanding_fact 부재 시 us-gaap 폴백으로 shares 행 확보."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_fallback(mocker)
    rows = fetch_edgar_quarterly_raw("GOOG")

    shares = [r for r in rows if r["field"] == "shares_outstanding"]
    assert shares, "us-gaap 폴백으로 shares_outstanding 행 존재(dei 부재에도)"
    for r in shares:
        assert r["period_type"] == "instant"


def test_shares_fallback_per_quarter(mocker):
    """폴백 shares 가 분기별(2025Q3·2025Q4)로 확보됨 — 단일행이 아니라 분기별."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch_fallback(mocker)
    rows = fetch_edgar_quarterly_raw("GOOG")

    sh_quarters = {r["quarter"] for r in rows if r["field"] == "shares_outstanding"}
    assert {"2025Q3", "2025Q4"} <= sh_quarters, "분기별 shares 확보(per-share 분모 복구)"

    sh_q4 = [
        r for r in rows
        if r["field"] == "shares_outstanding" and r["quarter"] == "2025Q4"
    ]
    assert sh_q4
    assert sh_q4[-1]["value"] == SHARES_Q4_EXPECTED


def test_dei_single_fact_path_unchanged(mocker):
    """회귀: dei shares_outstanding_fact 존재 시 기존 경로 그대로(폴백 미개입)."""
    from fixtures.edgar_aapl_facts import (
        AAPL_QUARTERLY_STORE,
        AAPL_SHARES_FACT,
        FakeQuarterlyFacts,
    )
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = FakeQuarterlyFacts(
        AAPL_QUARTERLY_STORE, shares_fact=AAPL_SHARES_FACT
    )
    rows = fetch_edgar_quarterly_raw("AAPL")

    shares = [r for r in rows if r["field"] == "shares_outstanding"]
    assert shares, "dei 단일 fact 경로 유지"
    # dei fact 값(14.84B)이 그대로 — 폴백이 dei 를 덮지 않음.
    assert any(r["value"] == 14_840_000_000.0 for r in shares)
