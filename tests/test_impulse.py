"""gap-fix 01-14: add_impulse_columns 검증."""

import numpy as np
import pandas as pd

from stocksig.compute.impulse import add_impulse_columns


def test_add_impulse_columns_basic():
    """직접 구성된 입력으로 4가지 결과 검증."""
    n = 5
    dates = pd.date_range(start="2026-01-05", periods=n, freq="B")
    df = pd.DataFrame(
        {
            "Close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "Close_week": [100.0, 101.0, 102.0, 103.0, 104.0],
            # trend 양수
            "EMA_Close_11_trend": [np.nan, 0.01, 0.01, -0.01, -0.01],
            # MACD_OSC: 차분이 +,+,-,-,+ 패턴
            "MACD_OSC": [0.0, 1.0, 2.0, 1.5, 1.0],
            "MACD_OSC_week": [0.0, 1.0, 2.0, 1.5, 1.0],
        },
        index=dates,
    )
    out = add_impulse_columns(df)
    assert "Impulse_daily" in out.columns
    assert "Impulse_weekly" in out.columns

    # index 0: trend=NaN → DEFAULT
    assert out["Impulse_daily"].iloc[0] == ""
    # index 1: trend>0, diff(1.0)>0 → GREEN ("녹색")
    assert out["Impulse_daily"].iloc[1] == "녹색"
    # index 2: trend>0, diff(1.0)>0 → GREEN
    assert out["Impulse_daily"].iloc[2] == "녹색"
    # index 3: trend<0, diff(-0.5)<0 → RED ("적색")
    assert out["Impulse_daily"].iloc[3] == "적색"
    # index 4: trend<0, diff(-0.5)<0 → RED
    assert out["Impulse_daily"].iloc[4] == "적색"


def test_add_impulse_columns_blue_mixed():
    """trend 양수 + osc 음수 (또는 반대) → BLUE."""
    n = 3
    df = pd.DataFrame(
        {
            "Close": [100.0, 101.0, 102.0],
            "Close_week": [100.0, 101.0, 102.0],
            "EMA_Close_11_trend": [0.01, 0.01, 0.01],
            "MACD_OSC": [10.0, 5.0, 1.0],  # 단조 하락 → diff < 0
            "MACD_OSC_week": [10.0, 5.0, 1.0],
        }
    )
    out = add_impulse_columns(df)
    # index 1, 2: trend>0, osc_diff<0 → BLUE ("청색")
    assert out["Impulse_daily"].iloc[1] == "청색"
    assert out["Impulse_daily"].iloc[2] == "청색"


def test_add_impulse_columns_weekly_computed():
    """주봉 임펄스: Close_week ewm + MACD_OSC_week.diff() 부호."""
    n = 30
    dates = pd.date_range(start="2026-01-05", periods=n, freq="B")
    cw = pd.Series([100.0 + i for i in range(n)], index=dates)
    df = pd.DataFrame(
        {
            "Close": cw,
            "Close_week": cw,
            "EMA_Close_11_trend": [0.0] * n,
            "MACD_OSC": [0.0] * n,
            "MACD_OSC_week": [i * 0.1 for i in range(n)],
        },
        index=dates,
    )
    out = add_impulse_columns(df)
    # 마지막 행: ema11_week_trend > 0 (단조 상승), osc_week_diff > 0 → GREEN
    assert out["Impulse_weekly"].iloc[-1] == "녹색"
