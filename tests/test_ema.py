"""COMP-01/02/03 GREEN tests.

Wave 2 구현: stocksig.compute.ema
Updated for gap-fix 01-07 / 01-12 (Close-EMA-only contract, no dailychg):
  - EMA: 4 (Close × 4 periods)
  - DIFF: 12 (Close/High/Low × 4) — all referenced to EMA_Close_N, stored as ratio
  - trend: 4 (Close × 4) — pct_change ratio (gap-fix 01-11, replaces dailychg)
"""

import math

import pandas as pd

from stocksig.compute.ema import (
    EMA_PERIODS,
    add_ema_columns,
    compute_ema,
)


def test_ema_matches_tradingview_formula():
    # GIVEN: closes = [1,2,3,4,5], span=3
    # WHEN: pandas .ewm(span=3, adjust=False).mean()
    # THEN: [1.0, 1.5, 2.25, 3.125, 4.0625] within tol=1e-9
    closes = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = compute_ema(closes, span=3)
    expected = [1.0, 1.5, 2.25, 3.125, 4.0625]
    for got, exp in zip(result.tolist(), expected, strict=True):
        assert math.isclose(got, exp, abs_tol=1e-9), f"expected {exp}, got {got}"


def test_diff_columns(mock_ohlcv_df):
    # GIVEN: OHLCV df with computed EMAs (gap-fix 01-07: all DIFF reference EMA_Close_N)
    # WHEN: add_ema_columns adds price-vs-EMA_Close ratio diff columns
    # THEN: DIFF_{price}_N == (price - EMA_Close_N) / EMA_Close_N (ratio)
    out = add_ema_columns(mock_ohlcv_df)
    for n in EMA_PERIODS:
        ema_close_col = f"EMA_Close_{n}"
        assert ema_close_col in out.columns, f"missing {ema_close_col}"
        for price_col in ["Close", "High", "Low"]:
            diff_col = f"DIFF_{price_col}_{n}"
            assert diff_col in out.columns, f"missing {diff_col}"
            expected_diff = (out[price_col] - out[ema_close_col]) / out[ema_close_col]
            pd.testing.assert_series_equal(
                out[diff_col], expected_diff, check_names=False
            )


def test_no_dailychg_columns(mock_ohlcv_df):
    # gap-fix 01-12: dailychg 컬럼은 완전히 제거됨 — trend가 대체.
    # 어떤 (price, period) 조합에 대해서도 *_dailychg 컬럼이 존재하면 안 된다.
    out = add_ema_columns(mock_ohlcv_df)
    assert not any(c.endswith("_dailychg") for c in out.columns), (
        f"dailychg cols leaked: {[c for c in out.columns if c.endswith('_dailychg')]}"
    )
    for n in EMA_PERIODS:
        for price_col in ["Close", "High", "Low"]:
            assert f"EMA_{price_col}_{n}_dailychg" not in out.columns


def test_no_high_low_ema_columns(mock_ohlcv_df):
    # gap-fix 01-07: High/Low EMA 컬럼은 더 이상 생성하지 않는다
    out = add_ema_columns(mock_ohlcv_df)
    for n in EMA_PERIODS:
        assert f"EMA_High_{n}" not in out.columns
        assert f"EMA_Low_{n}" not in out.columns


def test_trend_columns_added(mock_ohlcv_df):
    # gap-fix 01-11: add_ema_columns must add 4 _trend columns = EMA_Close_N.pct_change()
    out = add_ema_columns(mock_ohlcv_df)
    for n in EMA_PERIODS:
        trend_col = f"EMA_Close_{n}_trend"
        assert trend_col in out.columns, f"missing {trend_col}"
        ema_col = f"EMA_Close_{n}"
        pd.testing.assert_series_equal(
            out[trend_col], out[ema_col].pct_change(), check_names=False
        )
    # at least one non-null/non-zero trend value exists
    assert out["EMA_Close_11_trend"].notna().sum() > 0


def test_diff_is_ratio(mock_ohlcv_df):
    # gap-fix 01-07: DIFF는 비율 스케일 — mock df (close~100, high=close*1.02)에서
    # DIFF_High_N이 EMA 수렴 후 작은 양수 (0~0.1 범위) 여야 한다
    out = add_ema_columns(mock_ohlcv_df)
    # 충분히 EMA가 수렴한 뒤 (마지막 행) 검사
    last = out.iloc[-1]
    for n in EMA_PERIODS:
        for price_col in ["Close", "High", "Low"]:
            diff_val = last[f"DIFF_{price_col}_{n}"]
            assert abs(diff_val) < 1.0, (
                f"DIFF_{price_col}_{n}={diff_val} 비율 스케일 벗어남 (|.|<1 기대)"
            )
