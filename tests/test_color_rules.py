"""COLOR-01~07 + TECH-04/05 RED stubs.

Import target (Wave 3 구현 계약):
    from stocksig.compute.color_rules import (
        decide_sigma_bucket,
        decide_stoch_bucket,
        decide_rsi_bucket,
        SigmaBucket,
        TechBucket,
    )
"""

import pytest


@pytest.mark.xfail(reason="Wave 3: TECH bucket 경계값 (Stoch≤20/≥80, RSI≤30/≥70) 대기 (TECH-04/05)", strict=False)
def test_tech_buckets():
    # GIVEN: Stoch values around 20 and 80, RSI values around 30 and 70
    # WHEN: decide_stoch_bucket / decide_rsi_bucket
    # THEN: classification matches TechBucket boundaries
    from stocksig.compute.color_rules import (  # noqa: F401
        decide_stoch_bucket,
        decide_rsi_bucket,
        TechBucket,
    )
    raise NotImplementedError("Wave 3에서 구현")


@pytest.mark.xfail(reason="Wave 3: 7 SigmaBucket cases + NaN + std=0 대기 (COLOR-01~07, D-02)", strict=False)
def test_sigma_buckets():
    # GIVEN: 7 (close, median, std) cases covering DEFAULT/SOFT_GREEN/HARD_GREEN/SOFT_RED/HARD_RED
    #        + NaN inputs + std=0 (degenerate) — D-02
    # WHEN: decide_sigma_bucket
    # THEN: classification matches SigmaBucket enum
    from stocksig.compute.color_rules import (  # noqa: F401
        decide_sigma_bucket,
        SigmaBucket,
    )
    raise NotImplementedError("Wave 3에서 구현")
