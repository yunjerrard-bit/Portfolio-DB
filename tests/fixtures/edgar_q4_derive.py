"""260701 Q4 도출 픽스처 — annual(12M)·9M YTD·3M 혼재 store (네트워크 0).

라이브 스파이크(단계1) 확정 구조를 오프라인으로 재현:
  - EDGAR 회계 Q4 3M fact 부재 → 캘린더상 매년 한 분기 영구 결손.
  - annual(by_period_length(12)) + 9M YTD(by_period_length(9)) 는 실존.
  - 추출단계 도출 `Q4(3M) = annual − 9M` 로 갭 분기를 메워 4연속 분기 완성 → TTM 복구.

케이스 설계(GOOGL 유형, 12월 결산 → 캘린더 Q4 갭):
  net_income / revenue 각각:
    3M(quarterly): 2025Q1·2025Q2·2025Q3 존재, **2025Q4 부재**(갭).
    annual(12M):   FY2025 (period_start 2025-01-01 ~ period_end 2025-12-31).
    9M YTD:        (period_start 2025-01-01 ~ period_end 2025-09-30).
  도출: Q4 = annual − 9M, 분기키 = annual.period_end 월 → 2025Q4(갭 정확 매칭).

혼재 세그먼트(차원) fact 1개를 annual 에 추가 → 비차원 총액만 도출에 쓰임 검증.
값은 정합(sum3 + Q4 == annual)하도록 구성 — 구조값 단언 전용(렌더텍스트 금지).
"""

from __future__ import annotations

from fixtures.edgar_aapl_facts import FakeFinancialFact, FakeQuarterlyFacts

# --- net_income: 3M 3개(2025Q1~Q3) + annual FY2025 + 9M YTD -----------------
# 3M 합 = 30 + 28 + 35 = 93.  annual = 132.  => 도출 Q4 = 132 − 97 = 35... 정합 확인:
#   9M = 30 + 28 + 35 = 93?  아니다 — 9M 은 YTD 누계값(단일 fact)로 별도 지정.
# 정합식: annual = sum(3M Q1..Q3) + Q4 = (9M) + Q4.  9M == sum(3M Q1..Q3) 이도록 구성.
_NI_Q1 = 30_000_000_000.0
_NI_Q2 = 28_000_000_000.0
_NI_Q3 = 35_000_000_000.0
_NI_9M = _NI_Q1 + _NI_Q2 + _NI_Q3            # 93B (YTD 누계)
_NI_Q4_EXPECTED = 34_000_000_000.0
_NI_ANNUAL = _NI_9M + _NI_Q4_EXPECTED        # 127B

_REV_Q1 = 90_000_000_000.0
_REV_Q2 = 96_000_000_000.0
_REV_Q3 = 102_000_000_000.0
_REV_9M = _REV_Q1 + _REV_Q2 + _REV_Q3        # 288B
_REV_Q4_EXPECTED = 113_000_000_000.0
_REV_ANNUAL = _REV_9M + _REV_Q4_EXPECTED     # 401B

# 노출 상수(테스트 단언에서 재사용 — 매직넘버 회피).
NI_Q4_EXPECTED = _NI_Q4_EXPECTED
REV_Q4_EXPECTED = _REV_Q4_EXPECTED
NI_ANNUAL = _NI_ANNUAL
REV_ANNUAL = _REV_ANNUAL


def _q3m(concept_field_value_map):
    """concept → 3M 3개(2025Q1·Q2·Q3, period_length_months=3) FakeFinancialFact 리스트."""
    q1, q2, q3 = concept_field_value_map
    return [
        FakeFinancialFact(q1, "acc-q1", "USD", "2025-01-01", "2025-03-31",
                          "duration", "Q1 2025", filing_date="2025-04-30",
                          period_length_months=3),
        FakeFinancialFact(q2, "acc-q2", "USD", "2025-04-01", "2025-06-30",
                          "duration", "Q2 2025", filing_date="2025-07-30",
                          period_length_months=3),
        FakeFinancialFact(q3, "acc-q3", "USD", "2025-07-01", "2025-09-30",
                          "duration", "Q3 2025", filing_date="2025-10-30",
                          period_length_months=3),
        # 2025Q4(3M) 부재 — 갭.
    ]


def _annual(value, accession="acc-fy"):
    return FakeFinancialFact(value, accession, "USD", "2025-01-01", "2025-12-31",
                             "duration", "FY 2025", filing_date="2026-02-01",
                             period_length_months=12)


def _nine(value, accession="acc-9m"):
    return FakeFinancialFact(value, accession, "USD", "2025-01-01", "2025-09-30",
                             "duration", "9M 2025", filing_date="2025-10-30",
                             period_length_months=9)


# 세그먼트(차원) 오염 fact — 비차원 총액만 도출에 쓰임 검증용(라이브 GOOGL 다중 세그먼트).
_NI_ANNUAL_SEGMENT = FakeFinancialFact(
    5_000_000_000.0, "acc-fy-seg", "USD", "2025-01-01", "2025-12-31",
    "duration", "FY 2025", filing_date="2026-02-01",
    is_dimensioned=True, dimensions={"segment": "Cloud"}, period_length_months=12,
)


# store: (concept, period_type-or-tag) → [FakeFinancialFact].
# 3M 은 기존 유량 경로(by_period_type("quarterly"))로, annual/9M 은 by_period_length 로 취득.
Q4_DERIVE_STORE: dict = {
    # --- net_income ---
    ("NetIncomeLoss", "quarterly"): _q3m((_NI_Q1, _NI_Q2, _NI_Q3)),
    ("NetIncomeLoss", "annual"): [_annual(_NI_ANNUAL), _NI_ANNUAL_SEGMENT],
    ("NetIncomeLoss", "ytd9"): [_nine(_NI_9M)],
    # --- revenue ---
    ("Revenue", "quarterly"): _q3m((_REV_Q1, _REV_Q2, _REV_Q3)),
    ("Revenue", "annual"): [_annual(_REV_ANNUAL, "acc-fy-rev")],
    ("Revenue", "ytd9"): [_nine(_REV_9M, "acc-9m-rev")],
}


def make_facts(shares_fact=None) -> FakeQuarterlyFacts:
    """Q4 도출 store 로 EntityFacts mock 생성 (FakeQuarterlyFacts 재사용)."""
    return FakeQuarterlyFacts(Q4_DERIVE_STORE, shares_fact=shares_fact)


# --- 260701 커밋2: shares_outstanding us-gaap 폴백 픽스처 -------------------
# 시나리오: facts.shares_outstanding_fact 는 None(dei concept 부재)이지만
# us-gaap:CommonStockSharesOutstanding 분기별 instant fact 는 존재 → 폴백으로 분기별
# shares 확보 → per-share 분모(EPS_ttm/BPS/SPS/OCF_ps) 복구.
_SHARES_Q3 = 12_300_000_000.0
_SHARES_Q4 = 12_250_000_000.0
SHARES_Q4_EXPECTED = _SHARES_Q4

# 폴백 concept 별 분기 instant fact. (concept, "instant") 키 — by_concept 스캔 경로.
_SHARES_FALLBACK_FACTS: dict = {
    ("CommonStockSharesOutstanding", "instant"): [
        FakeFinancialFact(_SHARES_Q3, "acc-sh-q3", "shares", None, "2025-09-30",
                          "instant", "Q3 2025", filing_date="2025-10-30"),
        FakeFinancialFact(_SHARES_Q4, "acc-sh-q4", "shares", None, "2025-12-31",
                          "instant", "Q4 2025", filing_date="2026-02-01"),
    ],
}


def make_facts_shares_fallback() -> FakeQuarterlyFacts:
    """shares_outstanding_fact=None + us-gaap 분기 shares 폴백 fact 보유 mock.

    Q4_DERIVE_STORE + 폴백 shares concept fact 병합. dei 단일행(shares_outstanding_fact)
    은 None 이라 추출기가 us-gaap 폴백을 타야 분기 shares 를 확보한다.
    """
    store = dict(Q4_DERIVE_STORE)
    store.update(_SHARES_FALLBACK_FACTS)
    return FakeQuarterlyFacts(store, shares_fact=None)
