"""COMP-01/02/03 RED stubs.

Import target (Wave 2 구현 계약):
    from stocksig.compute.ema import add_ema_columns
"""

import pytest


@pytest.mark.xfail(reason="Wave 2: EMA(span=3, adjust=False) 골든 일치 대기 (COMP-01)", strict=False)
def test_ema_matches_tradingview_formula():
    # GIVEN: closes = [1,2,3,4,5], span=3
    # WHEN: pandas .ewm(span=3, adjust=False).mean()
    # THEN: [1.0, 1.5, 2.25, 3.125, 4.0625] within tol=1e-9
    from stocksig.compute.ema import add_ema_columns  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")


@pytest.mark.xfail(reason="Wave 2: 가격-EMA diff 컬럼 대기 (COMP-02)", strict=False)
def test_diff_columns(mock_ohlcv_df):
    # GIVEN: OHLCV df with computed EMAs
    # WHEN: add_ema_columns adds price-EMA diff columns
    # THEN: diff column present per EMA span
    from stocksig.compute.ema import add_ema_columns  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")


@pytest.mark.xfail(reason="Wave 2: 일일 변화량 (EMA.diff()) 대기 (COMP-03)", strict=False)
def test_daily_change(mock_ohlcv_df):
    # GIVEN: OHLCV df with EMA columns
    # WHEN: EMA.diff() applied
    # THEN: daily-change column matches expected
    from stocksig.compute.ema import add_ema_columns  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")
