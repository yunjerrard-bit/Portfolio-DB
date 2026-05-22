"""TECH-01/02 GREEN tests.

Wave 2 구현: stocksig.compute.indicators
- stoch_slow: Slow Stochastic (14, 3, 3) sanity
- rsi_wilder: Wilder RSI(14) golden (Wilder 1978 worked example)
"""

import math

import pandas as pd

from stocksig.compute.indicators import compute_macd_oscillator, rsi_wilder, stoch_slow


def _ohlc(close: list[float], high: list[float], low: list[float]) -> pd.DataFrame:
    return pd.DataFrame({"Close": close, "High": high, "Low": low})


def test_stoch_slow_known_input():
    # Case A: constant close=high=low=100 → denom=0 → all NaN
    n = 30
    df_const = _ohlc([100.0] * n, [100.0] * n, [100.0] * n)
    s_const = stoch_slow(df_const)
    assert s_const["Stoch_%K"].isna().all(), "all-equal series → %K all NaN"

    # Case B: close=100, high=110, low=90 (constant) → 14일 후 %K = 50.0 정확
    df_mid = _ohlc([100.0] * n, [110.0] * n, [90.0] * n)
    s_mid = stoch_slow(df_mid)
    # 처음 13행 (rolling(14) 결과) NaN
    assert s_mid["Stoch_%K"].iloc[:13].isna().all()
    # slow_k = mean of last 3 fast_k = 50.0
    assert math.isclose(s_mid["Stoch_%K"].iloc[-1], 50.0, abs_tol=1e-9)
    # slow_d = mean of last 3 slow_k = 50.0 (constant)
    assert math.isclose(s_mid["Stoch_%D"].iloc[-1], 50.0, abs_tol=1e-9)

    # Case C: close near high → %K ≈ 100
    high = [110.0] * n
    low = [90.0] * n
    close_hi = [109.5] * n
    df_hi = _ohlc(close_hi, high, low)
    s_hi = stoch_slow(df_hi)
    assert abs(s_hi["Stoch_%K"].iloc[-1] - 100.0) < 5.0

    # Case D: close near low → %K ≈ 0
    close_lo = [90.5] * n
    df_lo = _ohlc(close_lo, high, low)
    s_lo = stoch_slow(df_lo)
    assert abs(s_lo["Stoch_%K"].iloc[-1] - 0.0) < 5.0

    # Initial-row NaN sanity: 처음 13행 Stoch_%K NaN, 처음 ~15행 Stoch_%D NaN
    assert s_mid["Stoch_%K"].iloc[:13].isna().all()
    assert s_mid["Stoch_%D"].iloc[:15].isna().all()


def test_rsi_wilder_known_input(rsi_golden):
    # GIVEN: rsi_golden fixture (Wilder 1978 worked example, period=14)
    closes = rsi_golden["closes"]
    period = rsi_golden["period"]
    expected = rsi_golden["expected_rsi_at_index_14"]
    tol = rsi_golden["tolerance"]
    assert expected is not None, "fixture must be backfilled in Wave 2"

    df = pd.DataFrame({"Close": closes})
    rsi = rsi_wilder(df, period=period)

    # 처음 period-1행 NaN (min_periods=period)
    assert rsi.iloc[:period - 1].isna().all()
    # 14번째 행부터 valid
    assert not math.isnan(rsi.iloc[period])
    # golden match
    assert abs(rsi.iloc[period] - expected) < tol, (
        f"RSI[{period}]={rsi.iloc[period]} expected={expected} (tol={tol})"
    )
    # name='RSI'
    assert rsi.name == "RSI"

    # Monotonic-up sanity: RSI → 100
    df_up = pd.DataFrame({"Close": [100.0 + i for i in range(30)]})
    rsi_up = rsi_wilder(df_up, period=14)
    assert abs(rsi_up.iloc[-1] - 100.0) < 5.0

    # Monotonic-down sanity: RSI → 0
    df_dn = pd.DataFrame({"Close": [100.0 - i for i in range(30)]})
    rsi_dn = rsi_wilder(df_dn, period=14)
    assert abs(rsi_dn.iloc[-1] - 0.0) < 5.0


def test_macd_oscillator():
    """gap-fix 01-14: MACD-OSC(12, 26, 9) sanity — finite + length 일치."""
    n = 100
    close = pd.Series([100.0 + i * 0.5 for i in range(n)])
    osc = compute_macd_oscillator(close)
    assert len(osc) == n
    # 충분히 뒤쪽 (>= slow+signal) 값은 finite
    assert math.isfinite(osc.iloc[-1])
    assert osc.name == "MACD_OSC"

    # 단조 상승 입력 → 양수 영역으로 수렴
    assert osc.iloc[-1] > 0

    # 단조 하락 → 음수
    close_dn = pd.Series([100.0 - i * 0.5 for i in range(n)])
    osc_dn = compute_macd_oscillator(close_dn)
    assert osc_dn.iloc[-1] < 0

    # 상수 → 0
    close_const = pd.Series([100.0] * n)
    osc_const = compute_macd_oscillator(close_const)
    assert abs(osc_const.iloc[-1]) < 1e-9
