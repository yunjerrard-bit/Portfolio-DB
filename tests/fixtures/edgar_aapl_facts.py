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


# --- Plan 07-02: per-quarter raw 추출 mock 표면 (additive) ---


@dataclass
class FakeFinancialFact:
    """edgartools FinancialFact 의 mock — facts.query()...execute() 가 반환하는 행.

    실 FinancialFact 공개 attr 중 추출기가 쓰는 것만: numeric_value(None-safe),
    period_start/period_end, period_type, accession, unit, get_display_period_key().
    """

    numeric_value: float | None
    accession: str
    unit: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    period_type: str = "duration"
    _display_key: str = "Q2 2026"  # "Q{n} {year}" — get_display_period_key() 반환형(D-08)

    def get_display_period_key(self) -> str:
        return self._display_key


class FakeQuery:
    """facts.query() 체인 mock — by_concept/by_period_type/by_period_length/execute."""

    def __init__(self, store: dict):
        self._store = store
        self._concept: str | None = None
        self._period_type: str | None = None

    def by_concept(self, concept: str) -> FakeQuery:
        self._concept = concept
        return self

    def by_period_type(self, period_type: str) -> FakeQuery:
        self._period_type = period_type
        return self

    def by_period_length(self, n: int) -> FakeQuery:
        return self  # 분기=3, mock 은 길이 필터 무시(이미 분기 행만 보유)

    def execute(self) -> list:
        return list(self._store.get((self._concept, self._period_type), []))


class FakeQuarterlyFacts:
    """EntityFacts mock — query 빌더 + shares_outstanding_fact 표면 제공.

    quarterly_store: {(concept, period_type): [FakeFinancialFact, ...]}.
    """

    def __init__(self, quarterly_store: dict, shares_fact=None):
        self._store = quarterly_store
        self.shares_outstanding_fact = shares_fact

    def query(self) -> FakeQuery:
        return FakeQuery(self._store)


# AAPL 2개 분기(2026Q1·2026Q2) 손익(duration)·BS(instant)·CF(duration) mock 행.
AAPL_QUARTERLY_STORE: dict = {
    ("Revenue", "duration"): [
        FakeFinancialFact(95_359_000_000.0, "0000320193-26-000050", "USD",
                          "2026-01-01", "2026-03-28", "duration", "Q2 2026"),
        FakeFinancialFact(124_300_000_000.0, "0000320193-26-000010", "USD",
                          "2025-09-28", "2025-12-31", "duration", "Q1 2026"),
    ],
    ("NetIncomeLoss", "duration"): [
        FakeFinancialFact(23_636_000_000.0, "0000320193-26-000050", "USD",
                          "2026-01-01", "2026-03-28", "duration", "Q2 2026"),
    ],
    ("EarningsPerShareDiluted", "duration"): [
        FakeFinancialFact(1.57, "0000320193-26-000050", "USD/shares",
                          "2026-01-01", "2026-03-28", "duration", "Q2 2026"),
    ],
    ("GrossProfit", "duration"): [
        # 결손 케이스: numeric_value=None → value=None 단언용 (D-05).
        FakeFinancialFact(None, "0000320193-26-000050", "USD",
                          "2026-01-01", "2026-03-28", "duration", "Q2 2026"),
    ],
    ("NetCashProvidedByUsedInOperatingActivities", "duration"): [
        FakeFinancialFact(29_935_000_000.0, "0000320193-26-000050", "USD",
                          "2026-01-01", "2026-03-28", "duration", "Q2 2026"),
    ],
    ("StockholdersEquity", "instant"): [
        FakeFinancialFact(66_708_000_000.0, "0000320193-26-000050", "USD",
                          None, "2026-03-28", "instant", "Q2 2026"),
    ],
    ("Liabilities", "instant"): [
        FakeFinancialFact(277_327_000_000.0, "0000320193-26-000050", "USD",
                          None, "2026-03-28", "instant", "Q2 2026"),
    ],
    ("Assets", "instant"): [
        FakeFinancialFact(344_085_000_000.0, "0000320193-26-000050", "USD",
                          None, "2026-03-28", "instant", "Q2 2026"),
    ],
}

AAPL_SHARES_FACT = FakeFinancialFact(
    14_840_000_000.0, "0000320193-26-000050", "shares",
    None, "2026-03-28", "instant", "Q2 2026",
)
