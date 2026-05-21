"""COMP-04/05/06 GREEN tests.

Wave 2 구현: stocksig.compute.stats
- add_expanding_stats: {col}_median, {col}_std (expanding, ddof=1)
- cumulative_scalars: 전체 누적 median/std dict
"""

import math

import pandas as pd

from stocksig.compute.stats import (
    add_expanding_stats,
    add_pct_change_columns,
    cumulative_scalars,
)


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


def test_expanding_volume_pct_change(mock_ohlcv_df):
    # gap-fix 01-13: Volume_median/_std는 더 이상 사용하지 않음 — Volume_pct_change 기반으로 교체.
    df = add_pct_change_columns(mock_ohlcv_df)
    out = add_expanding_stats(df, ["Volume_pct_change"])
    assert "Volume_pct_change_median" in out.columns
    assert "Volume_pct_change_std" in out.columns
    pd.testing.assert_series_equal(
        out["Volume_pct_change_median"],
        df["Volume_pct_change"].expanding().median(),
        check_names=False,
    )
    pd.testing.assert_series_equal(
        out["Volume_pct_change_std"],
        df["Volume_pct_change"].expanding().std(),
        check_names=False,
    )


def test_pct_change_columns():
    """gap-fix 01-13: add_pct_change_columns adds Close_pct_change + Volume_pct_change."""
    df = pd.DataFrame(
        {
            "Close": [100.0, 110.0, 99.0, 99.0],
            "Volume": [1000.0, 2000.0, 1000.0, 500.0],
        }
    )
    out = add_pct_change_columns(df)
    assert "Close_pct_change" in out.columns
    assert "Volume_pct_change" in out.columns
    # 첫 행 NaN, 이후 (curr-prev)/prev
    assert math.isnan(out["Close_pct_change"].iloc[0])
    assert math.isclose(out["Close_pct_change"].iloc[1], 0.10, abs_tol=1e-9)
    assert math.isclose(out["Close_pct_change"].iloc[2], -0.10, abs_tol=1e-9)
    assert math.isclose(out["Close_pct_change"].iloc[3], 0.0, abs_tol=1e-9)
    assert math.isnan(out["Volume_pct_change"].iloc[0])
    assert math.isclose(out["Volume_pct_change"].iloc[1], 1.0, abs_tol=1e-9)
    assert math.isclose(out["Volume_pct_change"].iloc[2], -0.5, abs_tol=1e-9)
    assert math.isclose(out["Volume_pct_change"].iloc[3], -0.5, abs_tol=1e-9)
