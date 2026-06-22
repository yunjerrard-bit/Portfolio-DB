"""다종목·다산업 네트워크 0 fixture (Phase 9 렌더 테스트 공용).

두 산출물:
  1) `fetch_fn_stub()` — `compute_matrix(ticker, fetch_fn=stub)` 가 받는 형태(7-tuple:
     quarter, source, field, value, period_type, reprt_code, unit)를 ticker 별로
     돌려주는 결정적 stub. US 1종(AAPL/tech, EDGAR)·KR 1종(005930.KS/semis, DART) 최소.
  2) `build_ohlcv(...)` — `fetch_ohlcv_cached` monkeypatch 용 합성 OHLCV DataFrame
     (DatetimeIndex 다분기 Close 시계열).

전부 결정적(하드코딩·seed 고정), 외부 호출 0. 실제 키·비밀 미포함(T-09-02).
"""

from __future__ import annotations

import pandas as pd

# 7-tuple raw 행 = (quarter, source, field, value, period_type, reprt_code, unit)
# compute_matrix→_normalize_quarters 는 (quarter, field)만 키로 쓰고 value/source 보존.

# 5분기(2025Q1~2026Q1) — TTM(직전 4분기) 윈도가 2026Q1에서 완성되도록 5개 제공.
_QUARTERS = ["2025Q1", "2025Q2", "2025Q3", "2025Q4", "2026Q1"]


def _series_rows(
    source: str,
    *,
    revenue: float,
    gross_profit: float,
    operating_income: float,
    net_income: float,
    total_equity: float,
    total_assets: float,
    shares: float,
    unit: str = "USD",
) -> list[tuple]:
    """5분기 동안 일정 비율로 증가하는 결정적 raw 시계열(다분기·다지표)."""
    rows: list[tuple] = []
    for i, q in enumerate(_QUARTERS):
        scale = 1.0 + 0.1 * i  # 분기마다 10% 증가 (YoY 비교 가능)
        pt_dur = "duration"
        pt_inst = "instant"
        rows += [
            (q, source, "revenue", revenue * scale, pt_dur, None, unit),
            (q, source, "gross_profit", gross_profit * scale, pt_dur, None, unit),
            (q, source, "operating_income", operating_income * scale, pt_dur, None, unit),
            (q, source, "net_income", net_income * scale, pt_dur, None, unit),
            (q, source, "total_equity", total_equity * scale, pt_inst, None, unit),
            (q, source, "total_assets", total_assets * scale, pt_inst, None, unit),
            (q, source, "shares_outstanding", shares, pt_inst, None, unit),
        ]
    return rows


# 결정적 종목별 raw 표 (다종목·다산업).
_TICKER_ROWS: dict[str, list[tuple]] = {
    "AAPL": _series_rows(
        "EDGAR",
        revenue=1000.0,
        gross_profit=400.0,
        operating_income=300.0,
        net_income=250.0,
        total_equity=2000.0,
        total_assets=5000.0,
        shares=100.0,
        unit="USD",
    ),
    "005930.KS": _series_rows(
        "DART",
        revenue=8000.0,
        gross_profit=3000.0,
        operating_income=2000.0,
        net_income=1500.0,
        total_equity=20000.0,
        total_assets=40000.0,
        shares=600.0,
        unit="KRW",
    ),
}

# 종목 → 산업 매핑(다산업) — relative_bucket 모집단 구성용.
TICKER_INDUSTRY: dict[str, str] = {
    "AAPL": "tech",
    "005930.KS": "semiconductors",
}


def fetch_fn_stub(ticker: str) -> list[tuple]:
    """compute_matrix(ticker, fetch_fn=fetch_fn_stub) 주입용 결정적 stub.

    등록되지 않은 ticker → 빈 리스트(결손 매트릭스). 외부 호출 0.
    """
    return list(_TICKER_ROWS.get(ticker, []))


def build_ohlcv(
    start: str = "2024-01-01",
    end: str = "2024-12-31",
    base: float = 100.0,
) -> pd.DataFrame:
    """`fetch_ohlcv_cached` monkeypatch 용 합성 OHLCV (영업일 DatetimeIndex).

    각 분기 마지막 거래일 Close 가 분기별로 단조 증가하도록 구성 →
    quarter_end_prices 의 resample("QE").last() 결과가 분기별로 구분된다.
    """
    dates = pd.date_range(start=start, end=end, freq="B")
    close = []
    for d in dates:
        q = (d.month - 1) // 3 + 1
        close.append(base + q * 100.0 + d.dayofyear * 0.01)
    return pd.DataFrame(
        {
            "Open": close,
            "High": [c * 1.01 for c in close],
            "Low": [c * 0.99 for c in close],
            "Close": close,
            "Volume": [1_000_000] * len(close),
        },
        index=dates,
    )
