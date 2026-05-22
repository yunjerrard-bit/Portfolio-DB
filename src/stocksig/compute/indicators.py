"""기술 지표 — Stochastic Slow + Wilder RSI (TECH-01/02).

Pattern 5 + 6 (RESEARCH.md). pandas-ta 미사용 (CLAUDE.md "What NOT to Use").
A4 ASSUMED: Wilder smoothing == ewm(alpha=1/N, adjust=False) (수학적 동등).
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def stoch_slow(
    df: pd.DataFrame,
    k_period: int = 14,
    slowing: int = 3,
    d_period: int = 3,
) -> pd.DataFrame:
    """Slow Stochastic (k_period, slowing, d_period) = (14, 3, 3) 기본.

    반환 DataFrame:
      Stoch_%K: slow %K (fast_k의 slowing-기간 단순이동평균)
      Stoch_%D: slow %K의 d_period 단순이동평균
    index = df.index. 초기 (k_period + slowing - 1)행 ~ Stoch_%K NaN.
    """
    low_min = df["Low"].rolling(window=k_period, min_periods=k_period).min()
    high_max = df["High"].rolling(window=k_period, min_periods=k_period).max()
    denom = (high_max - low_min).replace(0, np.nan)
    fast_k = 100 * (df["Close"] - low_min) / denom
    slow_k = fast_k.rolling(window=slowing, min_periods=slowing).mean()
    slow_d = slow_k.rolling(window=d_period, min_periods=d_period).mean()
    return pd.DataFrame(
        {"Stoch_%K": slow_k, "Stoch_%D": slow_d}, index=df.index
    )


def compute_macd_oscillator(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.Series:
    """MACD Oscillator (Histogram) = MACD_line - Signal_line.

    gap-fix 01-14:
      MACD_line = EMA(close, fast) - EMA(close, slow)
      Signal    = EMA(MACD_line, signal)
      OSC       = MACD_line - Signal

    adjust=False (TradingView 호환). 초기 (slow-1) 행 ~ 작은 값 (NaN 없음 — ewm은
    첫 행도 채움). 의미 있는 값은 ~slow+signal 행 이후.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return (macd_line - signal_line).rename("MACD_OSC")


def rsi_wilder(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Wilder RSI(period). ewm(alpha=1/period, adjust=False) 동등.

    반환 Series name='RSI'. 초기 period-1행 NaN (min_periods=period).
    """
    close = df["Close"]
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    # avg_loss == 0 (and avg_gain valid) → RSI = 100 (mathematical limit)
    rsi = rsi.where(
        ~((avg_loss == 0) & avg_gain.notna() & (avg_gain > 0)),
        100.0,
    )
    return rsi.rename("RSI")
