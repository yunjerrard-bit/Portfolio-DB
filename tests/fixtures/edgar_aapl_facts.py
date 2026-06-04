"""AAPL EDGAR EntityFacts mock fixture (실데이터 기반, 03-02 스파이크 확정).

edgartools 5.35.0 `Company("AAPL").get_facts()` → `EntityFacts` 의 실제 표면을
Wave 3 `test_edgar_client.py` 가 mock 할 수 있도록 축약 재현.  [VERIFIED 2026-06-04]

확정된 5.x 취득 경로(A1):
  facts = Company(tk).get_facts()            # -> EntityFacts (NOT to_pandas)
  facts.get_revenue() -> float (최신 연간)
  facts.get_gross_profit() -> float | None   # GOOGL은 None (A2 결손 케이스)
  facts.get_operating_income() -> float
  facts.get_net_income() -> float
  facts.get_ttm_revenue() -> TTMMetric(concept, value, periods, as_of_date, ...)
  facts.get_ttm_net_income() -> TTMMetric
  facts.get_ttm("EarningsPerShareDiluted") -> TTMMetric(value=8.07, ...)  # EPS_TTM
  facts.available_periods() -> PeriodSummary  # 2026-Q2 / 2025-FY 표

폐기된 RESEARCH 가정(A1):  `facts.to_pandas("us-gaap:Revenues")` 는
5.35.0에 **존재하지 않음**(EntityFacts.to_pandas AttributeError).
또한 `get_ttm("Revenues")` 는 stale 기간(FY2018) 선택 → revenue는 반드시
`get_ttm_revenue()`(concept=RevenueFromContractWithCustomerExcludingAssessedTax)
사용.

값 출처: AAPL FY2025(2025-09-27) 연간 + TTM as_of 2026-Q2.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class FakeTTMMetric:
    """edgar EntityFacts.get_ttm_* 가 반환하는 TTMMetric 의 mock.

    실 TTMMetric 공개 attr: value, concept, as_of_date, periods,
    has_calculated_q4, has_gaps, label, period_facts, unit, warning.
    """

    concept: str
    value: float
    periods: list[tuple[int, str]] = field(default_factory=list)
    as_of_date: str | None = None
    has_gaps: bool = False
    warning: str | None = None


# 최신 연간(FY2025) 단일 float — get_revenue/get_gross_profit/... 반환형
AAPL_ANNUAL: dict[str, float | None] = {
    "revenue": 416_161_000_000.0,  # get_revenue() [VERIFIED]
    "gross_profit": 195_201_000_000.0,  # get_gross_profit() [VERIFIED]
    "operating_income": 133_050_000_000.0,  # get_operating_income() [VERIFIED]
    "net_income": 112_010_000_000.0,  # get_net_income() [VERIFIED]
}

# TTM 메트릭 — PER/PEG 산출 입력
AAPL_TTM_EPS_DILUTED = FakeTTMMetric(
    concept="us-gaap:EarningsPerShareDiluted",
    value=8.07,  # get_ttm("EarningsPerShareDiluted").value [VERIFIED]
    periods=[(2026, "Q2"), (2025, "Q3"), (2026, "Q1"), (2026, "Q2")],
    as_of_date="2026-03-28",
    has_gaps=False,
)

AAPL_TTM_REVENUE = FakeTTMMetric(
    concept="us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    value=451_442_000_000.0,  # get_ttm_revenue().value [VERIFIED]
    periods=[(2025, "Q3"), (2025, "Q4"), (2026, "Q1"), (2026, "Q2")],
    as_of_date="2026-03-28",
)

AAPL_TTM_NET_INCOME = FakeTTMMetric(
    concept="us-gaap:NetIncomeLoss",
    value=122_575_000_000.0,  # get_ttm_net_income().value [VERIFIED]
    periods=[(2025, "Q3"), (2025, "Q4"), (2026, "Q1"), (2026, "Q2")],
    as_of_date="2026-03-28",
)

# A7: quarter_label 산출 입력.  available_periods() 최상단 또는
# TTMMetric.periods[-1] / as_of_date 에서 "2026Q2" 도출.
AAPL_AVAILABLE_PERIODS: list[str] = [
    "2026-Q2", "2026-Q1", "2025-FY", "2025-Q3", "2025-Q2", "2025-Q1", "2024-FY",
]
AAPL_LATEST_10Q_PERIOD_OF_REPORT = "2026-03-28"  # Company.get_filings("10-Q").latest()


def quarter_label_from_periods(periods: list[tuple[int, str]]) -> str:
    """TTMMetric.periods 의 가장 최근 (year, "Qn") → "2026Q2" 라벨 (A7 확정 방식)."""
    if not periods:
        return "UNKNOWN"
    year, q = periods[-1]
    return f"{year}{q}"  # (2026, "Q2") -> "2026Q2"


# GOOGL GrossProfit 결손 케이스(A2) — GPM yf 폴백 트리거 검증용
GOOGL_GROSS_PROFIT_MISSING: float | None = None  # get_gross_profit() -> None [VERIFIED]
