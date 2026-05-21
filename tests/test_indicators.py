"""TECH-01/02 RED stubs.

Import target (Wave 2 구현 계약):
    from stocksig.compute.indicators import stoch_slow, rsi_wilder
"""

import pytest


@pytest.mark.xfail(reason="Wave 2: Stochastic Slow sanity 대기 (TECH-01)", strict=False)
def test_stoch_slow_known_input():
    # GIVEN: synthetic OHLC where close==high → %K≈100, close==low → %K≈0,
    #        constant prices → %K=50
    # WHEN: stoch_slow(df)
    # THEN: assertions hold within tolerance
    from stocksig.compute.indicators import stoch_slow  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")


@pytest.mark.xfail(reason="Wave 2: Wilder RSI(14) golden 대기 (TECH-02)", strict=False)
def test_rsi_wilder_known_input(rsi_golden):
    # GIVEN: rsi_golden fixture (closes, period=14, expected_rsi_at_index_14)
    # WHEN: rsi_wilder(closes, period=14)
    # THEN: result[14] matches expected within tolerance (backfilled Wave 2)
    from stocksig.compute.indicators import rsi_wilder  # noqa: F401
    raise NotImplementedError("Wave 2에서 구현")
