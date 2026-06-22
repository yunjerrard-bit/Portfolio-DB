"""quarter_price.quarter_end_prices 단언 (D-09 / SC4) — 네트워크 0.

OHLCV는 `fetch_ohlcv_cached`를 monkeypatch한 합성 DataFrame으로 주입한다
(yfinance/네트워크 호출 0). 검증:
  - 분기말 종가 dict 키가 정확히 "YYYYQn" 표기 (Pitfall 4 — _calendar_quarter_offset 출력과 일치)
  - 각 분기 값 = 그 분기 마지막 거래일 Close (resample("QE").last())
  - current_price == Close.dropna().iloc[-1]
"""

from __future__ import annotations

import pandas as pd
import pytest

from stocksig.io import quarter_price as qp
from stocksig.io.metrics_engine import _calendar_quarter_offset


def _synthetic_ohlcv() -> pd.DataFrame:
    """4분기(2024Q1~Q4) 합성 OHLCV. 각 분기 마지막 거래일 Close가 분기별로 다르다.

    분기 경계가 휴장일(주말 등)이라도 resample("QE").last()가 그 분기
    마지막 *거래일* 종가를 잡아야 함을 확인하기 위해 영업일(freq="B")로 생성.
    """
    dates = pd.date_range(start="2024-01-01", end="2024-12-31", freq="B")
    # 분기별 식별 가능한 Close: 분기 번호 * 10 + 일자 비례 증가 (마지막 거래일이 최댓값)
    close = []
    for d in dates:
        q = (d.month - 1) // 3 + 1
        close.append(q * 100.0 + d.dayofyear * 0.01)
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


def test_quarter_end_close_and_current(monkeypatch: pytest.MonkeyPatch):
    df = _synthetic_ohlcv()
    monkeypatch.setattr(qp, "fetch_ohlcv_cached", lambda t: df)

    qmap, current = qp.quarter_end_prices("AAPL")

    # 분기키 YYYYQn 표기 — 4개 분기 전부
    assert set(qmap) == {"2024Q1", "2024Q2", "2024Q3", "2024Q4"}

    # 키 표기가 _calendar_quarter_offset 출력과 정확히 일치 (Pitfall 4)
    assert _calendar_quarter_offset("2024Q2", -1) == "2024Q1"
    assert "2024Q1" in qmap

    # 각 분기 값 = 그 분기 마지막 거래일 Close
    close = df["Close"].dropna()
    qe = close.resample("QE").last()
    expected = dict(zip(qe.index.to_period("Q").astype(str), qe.to_numpy()))
    for k, v in expected.items():
        assert qmap[k] == pytest.approx(float(v))

    # 분기별 값이 서로 달라야(각 분기 마지막 거래일 종가) — Q4 > Q3 > Q2 > Q1
    assert qmap["2024Q4"] > qmap["2024Q3"] > qmap["2024Q2"] > qmap["2024Q1"]

    # current_price == 마지막 거래일 Close
    assert current == pytest.approx(float(close.iloc[-1]))


def test_quarter_end_empty_series(monkeypatch: pytest.MonkeyPatch):
    """빈 Close 시계열 → 빈 dict + current None 가드 (호출자가 note 처리)."""
    empty = pd.DataFrame(
        {"Open": [], "High": [], "Low": [], "Close": [], "Volume": []},
        index=pd.DatetimeIndex([]),
    )
    monkeypatch.setattr(qp, "fetch_ohlcv_cached", lambda t: empty)

    qmap, current = qp.quarter_end_prices("EMPTY")
    assert qmap == {}
    assert current is None
