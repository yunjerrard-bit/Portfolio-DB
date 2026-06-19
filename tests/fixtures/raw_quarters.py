"""분기 raw_facts 행 builder fixture (Phase 8 엔진 테스트 입력).

`tests/test_fundamentals_store.py::_row`(L22-44) 스타일의 디폴트 인자 12-tuple
팩토리. 컬럼 순서 = SCHEMA UPSERT 순서:
  ticker, source, quarter, field, value, unit, accession,
  period_start, period_end, period_type, reprt_code, fetched_at

표현 가능 케이스(전부 오버라이드):
  - EDGAR 3개월 손익(duration): period_type="duration", reprt_code=None (기본)
  - DART 분기(reprt_code 지정): source="DART", reprt_code="11013" 등
  - BS instant: period_type="instant"
  - 결손 분기: value=None (D-05 — 0/-999999 금지)
"""

from __future__ import annotations


def raw_row(
    ticker: str = "AAPL",
    source: str = "EDGAR",
    quarter: str = "2026Q1",
    field: str = "revenue",
    value: float | None = 1000.0,
    unit: str = "USD",
    accession: str = "acc-0001",
    period_type: str = "duration",
    reprt_code: str | None = None,
) -> tuple:
    """raw_facts 12-tuple 행 (컬럼 순서 = SCHEMA UPSERT). value=None → 결손(D-05)."""
    return (
        ticker,
        source,
        quarter,
        field,
        value,
        unit,
        accession,
        "2026-01-01",
        "2026-03-31",
        period_type,
        reprt_code,
        "2026-06-19T00:00:00",
    )
