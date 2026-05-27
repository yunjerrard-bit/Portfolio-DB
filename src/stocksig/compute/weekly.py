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


def week_close_mask(index: pd.DatetimeIndex) -> pd.Series:
    """각 행이 그 주(W-FRI)의 '마지막 거래일'인지 여부 bool Series.

    금요일이 휴장이면 그 주의 실제 마지막 거래일(예: 목요일)이 True가 된다.
    주봉 신호 색·통계를 '완성된 주' 기준으로만 적용할 때 사용한다.

    Args:
        index: 일봉 DatetimeIndex.

    Returns:
        index와 동일한 인덱스의 bool Series (주 마지막 거래일 = True).
    """
    s = pd.Series(index, index=index)
    week_ends = s.resample("W-FRI").last().dropna().to_numpy()
    return pd.Series(index.isin(week_ends), index=index)


def week_to_date_close_return(daily_close: pd.Series) -> pd.Series:
    """주간 진행형(week-to-date) 종가 등락률.

    각 거래일 값 = (그날 종가 / 직전 완성 주(W-FRI)의 마지막 종가) − 1.
    즉 월=월 수익률, 화=월~화 수익률, …, 금=그 주 전체 수익률(주봉 캔들 등락률과 동일).

    첫 주는 직전 주가 없어 NaN.

    Args:
        daily_close: 일봉 종가 Series (DatetimeIndex).

    Returns:
        daily_close와 동일 인덱스의 week-to-date 등락률 Series (비율).
    """
    weekly_last = daily_close.resample("W-FRI").last()
    # 각 주 라벨(주 마지막 금요일)에 '직전 주' 종가를 매핑한 뒤,
    # bfill로 그 주의 모든 일자(월~금)에 '직전 주 종가'를 기준값으로 broadcast.
    prev_week_close = weekly_last.shift(1)
    base = prev_week_close.reindex(daily_close.index, method="bfill")
    return daily_close / base - 1
