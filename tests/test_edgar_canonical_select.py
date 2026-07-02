"""260701 커밋3 — fuzzy concept 총액 선별 TDD (네트워크 0, 구조값 단언).

단계6 표본 재적재가 드러낸 사전-존재 버그: `by_concept(term)` 기본 fuzzy 매칭이 한
(field, 기간)에 총액 외 형제 concept(CostOfRevenue, LiabilitiesAndStockholdersEquity=총자산,
sub-line)를 섞어 반환하는데, 현행 3M·instant 루프는 전부 append→upsert 마지막-쓰기로
아무거나(쓰레기·음수·엉뚱한 총액) 저장했다. 라이브 확정: GOOGL revenue 3M 에
Revenues(총액)·CostOfRevenue·RevenueNotFromContract 공존 → 음수 저장 → OPM>100%.

수정(커밋3): 필드별 정규 concept 화이트리스트(_FIELD_CANONICAL_CONCEPTS)로 총액만 선별.
**max-abs 는 부적합** — total_equity/total_liabilities 에서 LiabilitiesAndStockholdersEquity
(=총자산, 더 큼)를 오선택. 정규 concept 우선순위+최신 filing 로 정확 선별한다.

단언은 구조값만(렌더텍스트 금지, 컨벤션).
"""

from __future__ import annotations

from fixtures.edgar_aapl_facts import FakeFinancialFact, FakeQuarterlyFacts

_B = 1_000_000_000.0

# --- Revenue 3M: 총액(Revenues) + 형제(CostOfRevenue, RevenueNotFromContract) 공존 ---
# 라이브 GOOGL 2025-09-30 구조 재현. 캘린더 분기 = period_end 월 → 2025Q3.
REV_TOTAL = 102.3 * _B
_REV_3M = [
    FakeFinancialFact(REV_TOTAL, "acc-rev-tot", "USD", "2025-07-01", "2025-09-30",
                      "duration", "Q3 2025", filing_date="2025-10-30",
                      concept="us-gaap:Revenues"),
    FakeFinancialFact(41.4 * _B, "acc-rev-cost", "USD", "2025-07-01", "2025-09-30",
                      "duration", "Q3 2025", filing_date="2025-10-30",
                      concept="us-gaap:CostOfRevenue"),
    FakeFinancialFact(-0.207 * _B, "acc-rev-other", "USD", "2025-07-01", "2025-09-30",
                      "duration", "Q3 2025", filing_date="2025-10-30",
                      concept="us-gaap:RevenueNotFromContractWithCustomer"),
]

# --- total_equity instant: StockholdersEquity(총액 88B) + LiabilitiesAndStockholdersEquity(379B=총자산) ---
# max-abs 면 379B(총자산) 오선택 → 정규 concept 로 88B 선택해야 함. period_end→2025Q4.
EQ_TOTAL = 88.19 * _B
_EQ_INSTANT = [
    FakeFinancialFact(EQ_TOTAL, "acc-eq", "USD", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:StockholdersEquity"),
    FakeFinancialFact(379.3 * _B, "acc-lse", "USD", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:LiabilitiesAndStockholdersEquity"),
]

# --- total_liabilities instant: Liabilities(291B) + LiabilitiesAndStockholdersEquity(379B) + Current(162B) ---
LIAB_TOTAL = 291.1 * _B
_LIAB_INSTANT = [
    FakeFinancialFact(LIAB_TOTAL, "acc-liab", "USD", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:Liabilities"),
    FakeFinancialFact(379.3 * _B, "acc-lse2", "USD", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:LiabilitiesAndStockholdersEquity"),
    FakeFinancialFact(162.4 * _B, "acc-liabcur", "USD", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:LiabilitiesCurrent"),
]

# --- total_assets instant: Assets(379B 총액) + sub-line(OtherAssetsNoncurrent 93B) ---
# Assets 는 정규이자 최대 → 선택. sub-line 은 정규 아님 → 배제(현행은 sub-line 저장 버그).
ASSET_TOTAL = 379.3 * _B
_ASSET_INSTANT = [
    FakeFinancialFact(ASSET_TOTAL, "acc-asset", "USD", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:Assets"),
    FakeFinancialFact(93.1 * _B, "acc-asset-other", "USD", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:OtherAssetsNoncurrent"),
]

# --- shares: dei 표지(2026Q1, 앞선 분기) vs us-gaap 분기별(2025Q3·Q4) 폴백 우선 ---
# dei 는 재무 분기보다 앞선 shares-only 분기를 만들어 최신열을 오염 → us-gaap 폴백이 있으면
# dei 는 넣지 않는다(커밋4). 그래서 dei 분기(2026Q1)는 shares 결과에 없어야 함.
_DEI_SHARES = FakeFinancialFact(
    12.20 * _B, "acc-dei-sh", "shares", None, "2026-03-31", "instant", "Q1 2026",
    filing_date="2026-05-01", concept="dei:EntityCommonStockSharesOutstanding",
)
_USGAAP_SHARES = [
    FakeFinancialFact(12.30 * _B, "acc-sh-q3", "shares", None, "2025-09-30",
                      "instant", "Q3 2025", filing_date="2025-10-30",
                      concept="us-gaap:CommonStockSharesOutstanding"),
    FakeFinancialFact(12.25 * _B, "acc-sh-q4", "shares", None, "2025-12-31",
                      "instant", "Q4 2025", filing_date="2026-02-01",
                      concept="us-gaap:CommonStockSharesOutstanding"),
]

_STORE: dict = {
    ("Revenue", "quarterly"): _REV_3M,
    ("StockholdersEquity", "instant"): _EQ_INSTANT,
    ("Liabilities", "instant"): _LIAB_INSTANT,
    ("Assets", "instant"): _ASSET_INSTANT,
    ("CommonStockSharesOutstanding", "instant"): _USGAAP_SHARES,
}


def _patch(mocker, shares_fact=_DEI_SHARES):
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = FakeQuarterlyFacts(
        _STORE, shares_fact=shares_fact
    )
    return mock_company


def _val(rows, field, quarter):
    hits = [r for r in rows if r["field"] == field and r["quarter"] == quarter]
    return hits[-1]["value"] if hits else None


def test_revenue_3m_picks_total_not_sibling(mocker):
    """3M revenue: fuzzy 형제(CostOfRevenue·음수 other) 배제, 정규 총액(Revenues) 선택."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOGL")

    assert _val(rows, "revenue", "2025Q3") == REV_TOTAL, "정규 총액 Revenues 선택"
    # 형제 값(CostOfRevenue 41.4B, other −0.207B)은 저장되지 않아야 함.
    rev_vals = [r["value"] for r in rows if r["field"] == "revenue"]
    assert 41.4 * _B not in rev_vals, "CostOfRevenue 배제"
    assert all(v is None or v > 0 for v in rev_vals), "음수 other revenue 배제"


def test_total_equity_picks_canonical_not_maxabs(mocker):
    """total_equity: max-abs(LiabilitiesAndStockholdersEquity=총자산 379B)가 아니라 정규 88B."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOGL")

    assert _val(rows, "total_equity", "2025Q4") == EQ_TOTAL, "StockholdersEquity 선택(max-abs 아님)"
    eq_vals = [r["value"] for r in rows if r["field"] == "total_equity"]
    assert 379.3 * _B not in eq_vals, "LiabilitiesAndStockholdersEquity(총자산) 배제"


def test_total_liabilities_picks_canonical(mocker):
    """total_liabilities: Liabilities(291B) 선택, LiabilitiesAndStockholdersEquity(379B)·Current(162B) 배제."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOGL")

    assert _val(rows, "total_liabilities", "2025Q4") == LIAB_TOTAL
    liab_vals = [r["value"] for r in rows if r["field"] == "total_liabilities"]
    assert 379.3 * _B not in liab_vals and 162.4 * _B not in liab_vals


def test_total_assets_picks_total_not_subline(mocker):
    """total_assets: 정규 Assets(총액 379B) 선택, sub-line(OtherAssetsNoncurrent 93B) 배제."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOGL")

    assert _val(rows, "total_assets", "2025Q4") == ASSET_TOTAL
    asset_vals = [r["value"] for r in rows if r["field"] == "total_assets"]
    assert 93.1 * _B not in asset_vals, "sub-line 배제"


def test_shares_prefers_usgaap_over_dei(mocker):
    """us-gaap 분기별 폴백이 있으면 그것을 쓰고(분기 커버리지), dei 표지 단일분기는 배제."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)  # dei present(2026Q1, 앞선 분기) + us-gaap 폴백(2025Q3·Q4)
    rows = fetch_edgar_quarterly_raw("GOOGL")

    share_quarters = {r["quarter"] for r in rows if r["field"] == "shares_outstanding"}
    assert {"2025Q3", "2025Q4"} <= share_quarters, "us-gaap 분기별 shares 채택"
    # dei 표지 분기(2026Q1)는 shares-only 오염 분기 → us-gaap 있으면 배제.
    assert "2026Q1" not in share_quarters, "dei 표지 단일분기 배제(최신열 오염 방지)"


def test_shares_dei_last_resort_when_no_usgaap(mocker):
    """us-gaap 폴백 전무 시에만 dei 단일 fact 를 최후수단으로 사용."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    # us-gaap 폴백 concept 제거한 store → dei 만 남음.
    store = {k: v for k, v in _STORE.items() if k[0] != "CommonStockSharesOutstanding"}
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = FakeQuarterlyFacts(
        store, shares_fact=_DEI_SHARES
    )
    rows = fetch_edgar_quarterly_raw("GOOGL")
    share_quarters = {r["quarter"] for r in rows if r["field"] == "shares_outstanding"}
    assert "2026Q1" in share_quarters, "us-gaap 부재 → dei 최후수단 사용"


def test_concept_absent_lenient_passthrough(mocker):
    """concept 부재(목/구fixture) fact 는 관대 통과 — 하위호환(엄격 필터가 목을 깨지 않음)."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    # concept=None 인 revenue 3M 단일 fact 만 → 여전히 추출돼야 함.
    store = {
        ("Revenue", "quarterly"): [
            FakeFinancialFact(50 * _B, "acc-noc", "USD", "2025-07-01", "2025-09-30",
                              "duration", "Q3 2025", filing_date="2025-10-30"),
        ],
    }
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = FakeQuarterlyFacts(store)

    rows = fetch_edgar_quarterly_raw("GOOGL")
    assert _val(rows, "revenue", "2025Q3") == 50 * _B, "concept 부재 → 관대 통과"
