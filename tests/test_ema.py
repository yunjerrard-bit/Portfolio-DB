"""COMP-01/02/03 GREEN tests.

Wave 2 구현: stocksig.compute.ema
- add_ema_columns: 36 신규 컬럼 (12 EMA + 12 DIFF + 12 dailychg)
- compute_ema: 단일 EMA 헬퍼 (span override 테스트용)
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
    # GIVEN: OHLCV df with computed EMAs
    # WHEN: add_ema_columns adds price-EMA diff columns
    # THEN: diff column present per EMA span; DIFF == price - EMA
    out = add_ema_columns(mock_ohlcv_df)
    for price_col in ["Close", "High", "Low"]:
        for n in EMA_PERIODS:
            ema_col = f"EMA_{price_col}_{n}"
            diff_col = f"DIFF_{price_col}_{n}"
            assert ema_col in out.columns, f"missing {ema_col}"
            assert diff_col in out.columns, f"missing {diff_col}"
            # DIFF == price - EMA
            expected_diff = out[price_col] - out[ema_col]
            pd.testing.assert_series_equal(
                out[diff_col], expected_diff, check_names=False
            )


def test_daily_change(mock_ohlcv_df):
    # GIVEN: OHLCV df with EMA columns
    # WHEN: EMA.diff() applied
    # THEN: daily-change column == EMA.diff()
    out = add_ema_columns(mock_ohlcv_df)
    for price_col in ["Close", "High", "Low"]:
        for n in EMA_PERIODS:
            ema_col = f"EMA_{price_col}_{n}"
            chg_col = f"EMA_{price_col}_{n}_dailychg"
            assert chg_col in out.columns, f"missing {chg_col}"
            pd.testing.assert_series_equal(
                out[chg_col], out[ema_col].diff(), check_names=False
            )
