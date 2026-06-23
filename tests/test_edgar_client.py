"""Phase 3 Wave 3 (03-03 Task 2): edgar_client.py — EDGAR facts + set_identity + throttle.

`mocker.patch("stocksig.io.edgar_client.Company")` 로 외부 호출 차단(test_market.py L33 analog),
edgar_aapl_facts fixture 로 fetch_edgar_raw 산출 dict 단언. set_identity 호출 형식(FUND-02).

Plan 10-03(FUND-11): 구 cache-first 페치 `fetch_edgar_cached`(7d `.cache/fundamentals`)가
제거되며 cache HIT 재호출 테스트·`_isolated_fund_cache` 픽스처도 함께 제거됐다.
`fetch_edgar_raw`·`fetch_edgar_quarterly_raw`(store 경로) 테스트는 무손상 유지.

SPIKE-FINDINGS A1/A2 확정 경로:
  facts = Company(tk).get_facts()
  facts.get_ttm("EarningsPerShareDiluted").value  # EPS_TTM
  facts.get_ttm_revenue().value                    # Revenue (get_ttm("Revenues")는 stale 금지)
  facts.get_gross_profit()                          # float | None (GOOGL None)
  facts.get_operating_income()
"""

from __future__ import annotations

from pathlib import Path

from fixtures.edgar_aapl_facts import (
    AAPL_ANNUAL,
    AAPL_TTM_EPS_DILUTED,
    AAPL_TTM_REVENUE,
)


def test_source_uses_edgar_import():
    # 소스 단언: from edgar import (NOT import edgartools), @throttled_edgar, set_identity
    src = Path("src/stocksig/io/edgar_client.py").read_text(encoding="utf-8")
    assert "from edgar import" in src
    assert "import edgartools" not in src
    assert "@throttled_edgar" in src
    assert "set_identity(" in src


def test_set_identity():
    # FUND-02: import-time set_identity 가 "<이름> <이메일>" 형식 인자로 1회 호출됨.
    import stocksig.io.edgar_client as ec

    assert ec._SET_IDENTITY_ARG  # 기록된 인자 존재
    arg = ec._SET_IDENTITY_ARG
    # 이름 + 이메일(@ 포함) 형식
    assert "@" in arg
    parts = arg.split()
    assert len(parts) >= 2  # 이름 토큰 + 이메일 토큰


def _build_fake_facts(gross_profit=AAPL_ANNUAL["gross_profit"]):
    """EntityFacts mock — typed accessor 반환값 구성."""

    class FakeFacts:
        def get_ttm(self, concept):
            assert concept == "EarningsPerShareDiluted"
            return AAPL_TTM_EPS_DILUTED

        def get_ttm_revenue(self):
            return AAPL_TTM_REVENUE

        def get_gross_profit(self):
            return gross_profit

        def get_operating_income(self):
            return AAPL_ANNUAL["operating_income"]

    return FakeFacts()


def test_fetch_edgar_raw_returns_keys(mocker):
    # FUND-01: fetch_edgar_raw 가 EPS/Revenue/GrossProfit/OpIncome raw dict 반환.
    from stocksig.io.edgar_client import fetch_edgar_raw

    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = _build_fake_facts()

    raw = fetch_edgar_raw("AAPL")

    assert raw["eps_ttm"] == AAPL_TTM_EPS_DILUTED.value
    assert raw["revenue"] == AAPL_TTM_REVENUE.value
    assert raw["gross_profit"] == AAPL_ANNUAL["gross_profit"]
    assert raw["op_income"] == AAPL_ANNUAL["operating_income"]
    assert raw["quarter_label"]  # 비어있지 않음
    # eps_prior 키 존재 (PEG 입력)
    assert "eps_prior" in raw


def test_fetch_edgar_raw_quarter_label(mocker):
    # A7: quarter_label 이 TTMMetric.periods 최근값 → "2026Q2".
    from stocksig.io.edgar_client import fetch_edgar_raw

    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = _build_fake_facts()

    raw = fetch_edgar_raw("AAPL")
    assert raw["quarter_label"] == "2026Q2"


def test_fetch_edgar_raw_gross_profit_none(mocker):
    # A2: GOOGL get_gross_profit()=None → raw dict 에 gross_profit=None (GPM 폴백 트리거).
    from stocksig.io.edgar_client import fetch_edgar_raw

    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = _build_fake_facts(gross_profit=None)

    raw = fetch_edgar_raw("GOOGL")
    assert raw["gross_profit"] is None
