"""임펄스 시스템 (gap-fix 01-14).

일봉 임펄스: EMA_Close_11_trend 부호 + MACD_OSC.diff() 부호
주봉 임펄스: 주봉 EMA11(내부 계산)의 pct_change 부호 + MACD_OSC_week.diff() 부호

→ 녹색/적색/청색/DEFAULT 텍스트 컬럼.
"""

from __future__ import annotations

import pandas as pd

from stocksig.compute.color_rules import decide_impulse


def add_impulse_columns(df: pd.DataFrame) -> pd.DataFrame:
    """(일)Impulse_daily, (주)Impulse_weekly 컬럼 추가.

    의존 컬럼:
      - EMA_Close_11_trend  (일봉 EMA11 pct_change, add_ema_columns 산출)
      - MACD_OSC            (일봉)
      - Close_week          (주봉, broadcast 됨)
      - MACD_OSC_week       (주봉)
    """
    out = df.copy()

    # 일봉 임펄스
    osc_diff = out["MACD_OSC"].diff()
    ema_trend_daily = out["EMA_Close_11_trend"]
    out["Impulse_daily"] = [
        decide_impulse(t, d).value for t, d in zip(ema_trend_daily, osc_diff)
    ]

    # 주봉 EMA11 trend (내부 계산, broadcast된 Close_week 위에 ewm)
    ema11_week = out["Close_week"].ewm(span=11, adjust=False).mean()
    ema11_week_trend = ema11_week.pct_change()
    osc_week_diff = out["MACD_OSC_week"].diff()
    out["Impulse_weekly"] = [
        decide_impulse(t, d).value for t, d in zip(ema11_week_trend, osc_week_diff)
    ]

    return out
