"""임펄스 시스템 (gap-fix 01-14).

일봉 임펄스: EMA_Close_11_trend 부호 + MACD_OSC.diff() 부호
주봉 임펄스: EMA_Close_11_week_trend(진행형) 부호 + MACD_OSC_week.diff()(진행형) 부호

두 입력 모두 week-to-date 진행형으로 통일됨 (사용자 개념과 일치):
- EMA: ema_week_to_date(Close, 11).pct_change() — main_run 에서 미리 계산
- MACD: macd_oscillator_week_to_date(Close).diff()

→ 녹색/적색/청색/DEFAULT 텍스트 컬럼.
"""

from __future__ import annotations

import pandas as pd

from stocksig.compute.color_rules import decide_impulse


def add_impulse_columns(df: pd.DataFrame) -> pd.DataFrame:
    """(일)Impulse_daily, (주)Impulse_weekly 컬럼 추가.

    의존 컬럼:
      - EMA_Close_11_trend           (일봉 EMA11 pct_change, add_ema_columns 산출)
      - MACD_OSC                     (일봉)
      - EMA_Close_11_week_trend      (주봉 EMA11 진행형 pct_change, main_run 에서 산출)
      - MACD_OSC_week                (주봉 진행형)
    """
    out = df.copy()

    # 일봉 임펄스
    osc_diff = out["MACD_OSC"].diff()
    ema_trend_daily = out["EMA_Close_11_trend"]
    out["Impulse_daily"] = [
        decide_impulse(t, d).value for t, d in zip(ema_trend_daily, osc_diff)
    ]

    # 주봉 임펄스 — 두 입력 모두 week-to-date 진행형 (사용자 개념 일치)
    ema11_week_trend = out["EMA_Close_11_week_trend"]
    osc_week_diff = out["MACD_OSC_week"].diff()
    out["Impulse_weekly"] = [
        decide_impulse(t, d).value for t, d in zip(ema11_week_trend, osc_week_diff)
    ]

    return out
