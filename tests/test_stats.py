"""COMP-04/05/06 RED stubs.

Import target (Wave 2 구현 계약):
    from stocksig.compute.stats import add_expanding_stats, cumulative_scalars
"""

import pytest


@pytest.mark.xfail(reason="Wave 2: expanding median/std 대기 (COMP-04)", strict=False)
def test_expanding_median_std(mock_ohlcv_df):
    # GIVEN: df with Close column
    # WHEN: add_expanding_stats(df)
    # THEN: expanding().median() / .std() columns appended
    from stocksig.compute.stats import add_expanding_stats  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")


@pytest.mark.xfail(reason="Wave 2: cumulative scalars (row 3/4) 대기 (COMP-05)", strict=False)
def test_cumulative_scalars(mock_ohlcv_df):
    # GIVEN: df with Close column
    # WHEN: cumulative_scalars(df) -> (median, std) for row 3/4
    # THEN: scalar values match pandas expanding equivalents
    from stocksig.compute.stats import cumulative_scalars  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")


@pytest.mark.xfail(reason="Wave 2: expanding volume 처리 대기 (COMP-06)", strict=False)
def test_expanding_volume(mock_ohlcv_df):
    # GIVEN: df with Volume column
    # WHEN: add_expanding_stats(df, columns=["Volume"])
    # THEN: volume expanding median/std columns appended
    from stocksig.compute.stats import add_expanding_stats  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")
