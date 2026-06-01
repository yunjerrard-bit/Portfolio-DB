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


def macd_oscillator_week_to_date(
    daily_close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.Series:
    """주간 진행형(week-to-date) MACD Oscillator(Histogram).

    완성된 주는 그 주 금요일 종가, 진행 중인 주는 '오늘 일봉 종가'를 그 주 종가로
    사용해 매 거래일 주봉 MACD-OSC를 갱신한다. 금요일(주 마지막 거래일) 행에서는
    표준 주봉 MACD-OSC(`compute_macd_oscillator(weekly_close)`)와 정확히 일치한다.

    원리: 주봉 종가 시퀀스로 EMA(fast/slow) + signal EMA를 구한 뒤, 각 일자에서
    '직전 주까지의 EMA 상태'에 '오늘 종가' 한 스텝만 추가로 굴린다 (adjust=False 재귀).
    """
    wc = daily_close.resample("W-FRI").last()
    ema_fast = wc.ewm(span=fast, adjust=False).mean()
    ema_slow = wc.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()

    a_fast = 2 / (fast + 1)
    a_slow = 2 / (slow + 1)
    a_sig = 2 / (signal + 1)

    idx = daily_close.index
    prev_fast = ema_fast.shift(1).reindex(idx, method="bfill")
    prev_slow = ema_slow.shift(1).reindex(idx, method="bfill")
    prev_sig = signal_line.shift(1).reindex(idx, method="bfill")

    ef = prev_fast * (1 - a_fast) + daily_close * a_fast
    es = prev_slow * (1 - a_slow) + daily_close * a_slow
    ml = ef - es
    sig = prev_sig * (1 - a_sig) + ml * a_sig
    return (ml - sig).rename("MACD_OSC")


def stoch_slow_week_to_date(
    daily_high: pd.Series,
    daily_low: pd.Series,
    daily_close: pd.Series,
    k_period: int = 14,
    slowing: int = 3,
    d_period: int = 3,
) -> pd.DataFrame:
    """주간 진행형(week-to-date) Slow Stochastic %K/%D.

    완성된 주는 주봉 OHLC(고가 max / 저가 min / 금요일 종가), 진행 중인 주는
    '이번 주 월~오늘'까지 누적된 고가 max / 저가 min / 오늘 종가를 그 주 바로 사용한다.
    금요일 행에서는 표준 주봉 Slow Stochastic(`stoch_slow(weekly_ohlc)`)과 일치한다.

    반환 DataFrame: Stoch_%K, Stoch_%D (index = daily_close.index).
    """
    wh = daily_high.resample("W-FRI").max()
    wl = daily_low.resample("W-FRI").min()
    wc = daily_close.resample("W-FRI").last()

    # 완성 주 기준 직전 (k_period-1)주 HH/LL (이번 주를 제외한 직전 주들).
    hh_prev = wh.rolling(k_period - 1).max().shift(1)
    ll_prev = wl.rolling(k_period - 1).min().shift(1)

    # 완성 주의 fast_k / slow_k — provisional slow_k/%D 계산용 직전 합계 산출.
    ll_full = wl.rolling(k_period).min()
    hh_full = wh.rolling(k_period).max()
    denom_full = (hh_full - ll_full).replace(0, np.nan)
    fast_k_w = 100 * (wc - ll_full) / denom_full
    slow_k_w = fast_k_w.rolling(slowing).mean()

    fastk_prev_sum = fast_k_w.rolling(slowing - 1).sum().shift(1)
    slowk_prev_sum = slow_k_w.rolling(d_period - 1).sum().shift(1)

    idx = daily_close.index
    hh_p = hh_prev.reindex(idx, method="bfill")
    ll_p = ll_prev.reindex(idx, method="bfill")
    fks = fastk_prev_sum.reindex(idx, method="bfill")
    sks = slowk_prev_sum.reindex(idx, method="bfill")

    # 진행형 주봉 바 (week-to-date): 이번 주 월~오늘 누적 고가/저가 + 오늘 종가.
    h_wtd = daily_high.groupby(pd.Grouper(freq="W-FRI")).cummax()
    l_wtd = daily_low.groupby(pd.Grouper(freq="W-FRI")).cummin()

    # np.maximum/minimum 은 NaN 전파 → 워밍업 구간(직전 주 부족) NaN 유지.
    hh = np.maximum(hh_p.to_numpy(dtype=float), h_wtd.to_numpy(dtype=float))
    ll = np.minimum(ll_p.to_numpy(dtype=float), l_wtd.to_numpy(dtype=float))
    denom = pd.Series(hh - ll, index=idx).replace(0, np.nan)
    fast_k = 100 * (daily_close - pd.Series(ll, index=idx)) / denom
    slow_k = (fks + fast_k) / slowing
    slow_d = (sks + slow_k) / d_period
    return pd.DataFrame({"Stoch_%K": slow_k, "Stoch_%D": slow_d}, index=idx)


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


def ema_week_to_date(daily_close: pd.Series, span: int) -> pd.Series:
    """주간 진행형(week-to-date) EMA.

    완성된 주는 그 주 금요일 종가에 대한 표준 주봉 EMA, 진행 중인 주는 '직전
    완성 주의 EMA 상태' 에 '오늘 일봉 종가' 로 한 스텝만 추가 진행한 값.
    금요일 행에서는 `weekly_close.ewm(span=span, adjust=False).mean()`과 정확히
    일치한다.

    오늘 종가의 직접 가중치 = α = 2/(span+1).
    (span=11 → 16.67%, span=22 → 8.70%)
    주중 다른 일자의 종가는 들어가지 않는다 — 매 일자는 '직전 완성 주 + 그날 종가'
    한 스텝만 본다 (진짜 주봉 EMA가 한 주에 한 점만 보는 것과 동치).

    Args:
        daily_close: 일봉 종가 Series (DatetimeIndex).
        span: EMA span (예: 11, 22).

    Returns:
        daily_close와 동일 인덱스의 진행형 주봉 EMA Series.
    """
    wc = daily_close.resample("W-FRI").last()
    ema_w = wc.ewm(span=span, adjust=False).mean()
    alpha = 2 / (span + 1)
    prev = ema_w.shift(1).reindex(daily_close.index, method="bfill")
    return prev * (1 - alpha) + daily_close * alpha


def rsi_week_to_date(daily_close: pd.Series, period: int = 14) -> pd.Series:
    """주간 진행형(week-to-date) Wilder RSI.

    완성된 주는 그 주 금요일 종가를, 진행 중인 주는 '그날 일봉 종가'를 그 주의
    종가로 사용해 매 거래일 주봉 RSI를 갱신한다. 금요일(주 마지막 거래일) 행에서는
    표준 주봉 RSI(`rsi_wilder(Close_week)`)와 정확히 일치한다.

    원리: 주봉 종가 시퀀스로 Wilder 평균(avg_gain/avg_loss)을 구한 뒤, 각 일자에서
    '직전 주까지의 평균'에 '오늘 종가 − 직전 주 종가'로 만든 한 스텝만 추가로 굴린다.

    Args:
        daily_close: 일봉 종가 Series (DatetimeIndex).
        period: Wilder 기간 (기본 14).

    Returns:
        daily_close와 동일 인덱스의 주간 진행형 RSI Series (name='RSI').
    """
    weekly_close = daily_close.resample("W-FRI").last()
    delta = weekly_close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False, min_periods=period).mean()

    # 직전 주까지의 Wilder 평균 + 직전 주 종가를, 그 주 모든 일자에 broadcast (bfill).
    prev_gain = avg_gain.shift(1).reindex(daily_close.index, method="bfill")
    prev_loss = avg_loss.shift(1).reindex(daily_close.index, method="bfill")
    prev_close = weekly_close.shift(1).reindex(daily_close.index, method="bfill")

    step = daily_close - prev_close
    g = step.clip(lower=0)
    l = (-step).clip(lower=0)
    ag = prev_gain * (1 - 1 / period) + g * (1 / period)
    al = prev_loss * (1 - 1 / period) + l * (1 / period)
    rs = ag / al.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(~((al == 0) & ag.notna() & (ag > 0)), 100.0)
    return rsi.rename("RSI")
