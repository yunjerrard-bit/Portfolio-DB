"""주봉 집계 (W-FRI) + daily index forward fill (gap-fix 01-14).

W-FRI 주봉:
  Close_week  = 같은 주 마지막 영업일 종가
  High_week   = 같은 주 최고가
  Low_week    = 같은 주 최저가
  Volume_week = 같은 주 거래량 합

reindex(daily_index, method='ffill')로 5영업일 broadcast.
"""

from __future__ import annotations

import pandas as pd


def compute_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """W-FRI 주봉 집계 후 daily_df.index로 forward fill (broadcast).

    Returns:
        DataFrame with columns [Close_week, High_week, Low_week, Volume_week]
        indexed by daily_df.index.
    """
    weekly = pd.DataFrame(
        {
            "Close_week": daily_df["Close"].resample("W-FRI").last(),
            "High_week": daily_df["High"].resample("W-FRI").max(),
            "Low_week": daily_df["Low"].resample("W-FRI").min(),
            "Volume_week": daily_df["Volume"].resample("W-FRI").sum(),
        }
    )
    return weekly.reindex(daily_df.index, method="ffill")
