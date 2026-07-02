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
    period_start/period_end, period_type, accession, unit, filing_date,
    get_display_period_key().

    260629-hec: edgartools 5.35.0 마이그레이션 — 유량은 by_period_type("quarterly")로
    조회되고(저장 라벨은 실제 fact.period_type="duration" 유지), 저량(BS)은 by_concept
    만으로 조회 후 파이썬에서 period_type=="instant" 필터를 거친다. filing_date 는
    실 FinancialFact 의 보고일 속성(models.py L49, date)으로 중복 정렬 키.
    분기키는 period_end 종료일 월 기준 캘린더 분기로 산출된다(get_display_period_key 차선책).
    """

    numeric_value: float | None
    accession: str
    unit: str | None = None
    period_start: str | None = None
    period_end: str | None = None
    period_type: str = "duration"
    _display_key: str = "Q2 2026"  # "Q{n} {year}" — get_display_period_key() 반환형(D-08)
    filing_date: str | None = None  # 실 FinancialFact.filing_date(date) — 중복 정렬 키
    is_dimensioned: bool = False  # 260701: True=세그먼트(차원) fact → Q4 도출 배제
    dimensions: object | None = None  # 260701: 비차원 총액은 None
    period_length_months: int | None = None  # 260701: by_period_length 필터용(12/9/3)
    concept: str | None = None  # 260701 커밋3: 정규 concept 선별용('us-gaap:Revenues' 등). None=관대통과

    def get_display_period_key(self) -> str:
        return self._display_key


class FakeQuery:
    """facts.query() 체인 mock — by_concept/by_period_type/by_period_length/execute.

    260629-hec: by_period_type 미설정(period_type=None) 시 by_concept 만으로 조회 —
    해당 concept 의 모든 fact(instant/duration 혼재 가능)를 반환한다(저량 BS 경로).
    by_period_type 설정 시는 (concept, period_type) 키 매칭(유량 quarterly 경로).

    260701(Q4 도출): by_period_length(n)이 지정되면 해당 concept 의 *모든* store 항목에서
    `period_length_months == n` fact 만 반환(annual=12/9M=9 추출 경로). by_period_type 와
    by_period_length 는 상호 배타적으로 쓰인다(추출기가 한쪽만 호출). 길이 필터가 지정되면
    period_type 매칭보다 우선한다(annual/9M 은 store 에 (concept,"annual")/(concept,"ytd9")
    등 임의 키로 담기므로 concept 전역 스캔 + 길이 필터로 취득).
    """

    def __init__(self, store: dict):
        self._store = store
        self._concept: str | None = None
        self._period_type: str | None = None
        self._period_length: int | None = None

    def by_concept(self, concept: str) -> FakeQuery:
        self._concept = concept
        return self

    def by_period_type(self, period_type: str) -> FakeQuery:
        self._period_type = period_type
        return self

    def by_period_length(self, n: int) -> FakeQuery:
        self._period_length = n  # 260701: 길이 필터 기록(annual=12/9M=9)
        return self

    def _all_facts_for_concept(self) -> list:
        out: list = []
        for (concept, _ptype), facts in self._store.items():
            if concept == self._concept:
                out.extend(facts)
        return out

    def execute(self) -> list:
        # 260701: 길이 필터 우선(annual/9M 추출) — concept 전역에서 length 일치 fact.
        if self._period_length is not None:
            return [
                f for f in self._all_facts_for_concept()
                if getattr(f, "period_length_months", None) == self._period_length
            ]
        if self._period_type is not None:
            # 유량 경로: (concept, period_type) 정확 매칭.
            return list(self._store.get((self._concept, self._period_type), []))
        # 저량(BS) 경로: by_concept 만 — 해당 concept 의 모든 period_type fact 반환
        # (추출기 파이썬 instant 필터가 instant 만 통과시킴).
        return self._all_facts_for_concept()


class FakeQuarterlyFacts:
    """EntityFacts mock — query 빌더 + shares_outstanding_fact 표면 제공.

    quarterly_store: {(concept, period_type): [FakeFinancialFact, ...]}.
    """

    def __init__(self, quarterly_store: dict, shares_fact=None):
        self._store = quarterly_store
        self.shares_outstanding_fact = shares_fact

    def query(self) -> FakeQuery:
        return FakeQuery(self._store)


# AAPL 2개 분기(2026Q1·2026Q2) 손익(quarterly)·BS(by_concept→instant 필터)·CF(quarterly) mock 행.
# 260629-hec: 유량 키 = (concept, "quarterly") — by_period_type("quarterly")로 조회.
#   분기키는 period_end 종료일 월 기준 캘린더 분기(2026-03-28→2026Q1, 2026-06-30→2026Q2).
# BS concept 에는 instant + duration 혼재 fact 를 넣어 파이썬 instant 필터가 instant 만
#   통과시킴을 입증(StockholdersEquity 에 duration 오염 fact 1개 추가).
AAPL_QUARTERLY_STORE: dict = {
    ("Revenue", "quarterly"): [
        # period_end 2026-06-30 → 캘린더 Q2. filing_date 가 더 늦은 정정값이 마지막에 오도록.
        FakeFinancialFact(94_000_000_000.0, "0000320193-26-000040", "USD",
                          "2026-04-01", "2026-06-30", "duration", "Q2 2026",
                          filing_date="2026-07-30"),
        # 같은 (2026Q2, revenue) 정정 fact — filing_date 더 늦음 → 정렬 후 마지막.
        FakeFinancialFact(95_359_000_000.0, "0000320193-26-000050", "USD",
                          "2026-04-01", "2026-06-30", "duration", "Q2 2026",
                          filing_date="2026-08-15"),
        # period_end 2026-03-28 → 캘린더 Q1.
        FakeFinancialFact(124_300_000_000.0, "0000320193-26-000010", "USD",
                          "2026-01-01", "2026-03-28", "duration", "Q1 2026",
                          filing_date="2026-04-30"),
    ],
    ("NetIncomeLoss", "quarterly"): [
        FakeFinancialFact(23_636_000_000.0, "0000320193-26-000050", "USD",
                          "2026-04-01", "2026-06-30", "duration", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
    ("EarningsPerShareDiluted", "quarterly"): [
        FakeFinancialFact(1.57, "0000320193-26-000050", "USD/shares",
                          "2026-04-01", "2026-06-30", "duration", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
    ("GrossProfit", "quarterly"): [
        # 결손 케이스: numeric_value=None → value=None 단언용 (D-05).
        FakeFinancialFact(None, "0000320193-26-000050", "USD",
                          "2026-04-01", "2026-06-30", "duration", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
    ("NetCashProvidedByUsedInOperatingActivities", "quarterly"): [
        FakeFinancialFact(29_935_000_000.0, "0000320193-26-000050", "USD",
                          "2026-04-01", "2026-06-30", "duration", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
    # BS(저량) — by_concept 만으로 조회되며 파이썬 instant 필터를 거친다.
    # StockholdersEquity 에 duration 오염 fact 1개를 추가 → instant 만 통과 단언용.
    ("StockholdersEquity", "instant"): [
        FakeFinancialFact(66_708_000_000.0, "0000320193-26-000050", "USD",
                          None, "2026-06-30", "instant", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
    ("StockholdersEquity", "duration"): [
        # 혼재 오염 fact: instant 필터가 걸러내야 함(total_equity duration 행 미생성).
        FakeFinancialFact(999_999_999.0, "0000320193-26-000050", "USD",
                          "2026-04-01", "2026-06-30", "duration", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
    ("Liabilities", "instant"): [
        FakeFinancialFact(277_327_000_000.0, "0000320193-26-000050", "USD",
                          None, "2026-06-30", "instant", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
    ("Assets", "instant"): [
        FakeFinancialFact(344_085_000_000.0, "0000320193-26-000050", "USD",
                          None, "2026-06-30", "instant", "Q2 2026",
                          filing_date="2026-08-15"),
    ],
}

AAPL_SHARES_FACT = FakeFinancialFact(
    14_840_000_000.0, "0000320193-26-000050", "shares",
    None, "2026-06-30", "instant", "Q2 2026",
    filing_date="2026-08-15",
)
