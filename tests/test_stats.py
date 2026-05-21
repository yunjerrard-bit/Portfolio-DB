"""COMP-04/05/06 GREEN tests.

Wave 2 구현: stocksig.compute.stats
- add_expanding_stats: {col}_median, {col}_std (expanding, ddof=1)
- cumulative_scalars: 전체 누적 median/std dict
"""

import math

import pandas as pd

from stocksig.compute.stats import add_expanding_stats, cumulative_scalars


def test_expanding_median_std():
    # GIVEN: Close = [10, 20, 30, 40, 50]
    df = pd.DataFrame({"Close": [10.0, 20.0, 30.0, 40.0, 50.0]})
    out = add_expanding_stats(df, ["Close"])

    assert "Close_median" in out.columns
    assert "Close_std" in out.columns

    expected_median = [10.0, 15.0, 20.0, 25.0, 30.0]
    for got, exp in zip(out["Close_median"].tolist(), expected_median, strict=True):
        assert math.isclose(got, exp, abs_tol=1e-9)

    stds = out["Close_std"].tolist()
    assert math.isnan(stds[0])  # 표본 1, ddof=1 → NaN
    assert math.isclose(stds[1], math.sqrt(50.0), abs_tol=1e-6)
    # std([10,20,30,40,50], ddof=1) ≈ 15.811
    assert math.isclose(stds[4], 15.811388300841896, abs_tol=1e-6)


def test_cumulative_scalars():
    # GIVEN: Close = [10, 20, 30, 40, 50]
    df = pd.DataFrame({"Close": [10.0, 20.0, 30.0, 40.0, 50.0]})
    scalars = cumulative_scalars(df, ["Close"])
    assert math.isclose(scalars["Close"]["median"], 30.0, abs_tol=1e-9)
    assert math.isclose(scalars["Close"]["std"], 15.811388300841896, abs_tol=1e-6)


def test_expanding_volume(mock_ohlcv_df):
    # GIVEN: df with Volume column
    # WHEN: add_expanding_stats(df, ["Volume"])
    # THEN: Volume_median, Volume_std columns appended; values match pandas expanding equivalents
    out = add_expanding_stats(mock_ohlcv_df, ["Volume"])
    assert "Volume_median" in out.columns
    assert "Volume_std" in out.columns
    # Equivalence check
    pd.testing.assert_series_equal(
        out["Volume_median"],
        mock_ohlcv_df["Volume"].expanding().median(),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        out["Volume_std"],
        mock_ohlcv_df["Volume"].expanding().std(),
        check_names=False,
    )
