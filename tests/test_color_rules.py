"""COLOR-01~07 + TECH-04/05 GREEN tests.

Wave 2 구현: stocksig.compute.color_rules
- decide_sigma_bucket: D-02 (NaN/std=0 → DEFAULT), 경계 케이스
- decide_stoch_bucket / decide_rsi_bucket: D-04 임계 (20/80, 30/70)
- 7 hex 색 상수 (D-04 Material Design single source of truth)
"""

import math

from stocksig.compute.color_rules import (
    DEFAULT_BLACK,
    GREEN_100,
    GREEN_800,
    GREEN_900,
    RED_100,
    RED_800,
    RED_900,
    SigmaBucket,
    TechBucket,
    decide_rsi_bucket,
    decide_sigma_bucket,
    decide_stoch_bucket,
    decide_trend_bucket,
)


def test_trend_bucket():
    # gap-fix 01-11: 양수→SOFT_GREEN, 음수→SOFT_RED, 0/NaN/None→DEFAULT
    assert decide_trend_bucket(0.0123) == TechBucket.SOFT_GREEN
    assert decide_trend_bucket(1e-9) == TechBucket.SOFT_GREEN
    assert decide_trend_bucket(-0.0001) == TechBucket.SOFT_RED
    assert decide_trend_bucket(-1.0) == TechBucket.SOFT_RED
    assert decide_trend_bucket(0) == TechBucket.DEFAULT
    assert decide_trend_bucket(0.0) == TechBucket.DEFAULT
    assert decide_trend_bucket(float("nan")) == TechBucket.DEFAULT
    assert decide_trend_bucket(None) == TechBucket.DEFAULT


def test_tech_buckets():
    # Stoch 경계 (≤20 SOFT_GREEN, ≥80 SOFT_RED, NaN DEFAULT)
    assert decide_stoch_bucket(float("nan")) == TechBucket.DEFAULT
    assert decide_stoch_bucket(20) == TechBucket.SOFT_GREEN
    assert decide_stoch_bucket(19.99) == TechBucket.SOFT_GREEN
    assert decide_stoch_bucket(50) == TechBucket.DEFAULT
    assert decide_stoch_bucket(80) == TechBucket.SOFT_RED
    assert decide_stoch_bucket(80.01) == TechBucket.SOFT_RED

    # RSI 경계 (≤30 SOFT_GREEN, ≥70 SOFT_RED, NaN DEFAULT)
    assert decide_rsi_bucket(float("nan")) == TechBucket.DEFAULT
    assert decide_rsi_bucket(30) == TechBucket.SOFT_GREEN
    assert decide_rsi_bucket(50) == TechBucket.DEFAULT
    assert decide_rsi_bucket(70) == TechBucket.SOFT_RED


def test_sigma_buckets():
    # --- D-02 분기: NaN / None / std=0 → DEFAULT ---
    nan = float("nan")
    assert decide_sigma_bucket(nan, 100, 10) == SigmaBucket.DEFAULT
    assert decide_sigma_bucket(100, nan, 10) == SigmaBucket.DEFAULT
    assert decide_sigma_bucket(100, 100, nan) == SigmaBucket.DEFAULT
    assert decide_sigma_bucket(None, 100, 10) == SigmaBucket.DEFAULT
    assert decide_sigma_bucket(100, None, 10) == SigmaBucket.DEFAULT
    assert decide_sigma_bucket(100, 100, None) == SigmaBucket.DEFAULT
    assert decide_sigma_bucket(100, 100, 0) == SigmaBucket.DEFAULT  # D-02

    # --- COLOR-06: |dev| ≤ 1σ → DEFAULT ---
    assert decide_sigma_bucket(100, 100, 10) == SigmaBucket.DEFAULT  # dev=0
    assert decide_sigma_bucket(110, 100, 10) == SigmaBucket.DEFAULT  # dev=+1σ exact
    assert decide_sigma_bucket(90, 100, 10) == SigmaBucket.DEFAULT  # dev=-1σ exact

    # --- COLOR-03: 1σ < dev ≤ 2σ → SOFT_RED ---
    assert decide_sigma_bucket(110.01, 100, 10) == SigmaBucket.SOFT_RED
    assert decide_sigma_bucket(119.99, 100, 10) == SigmaBucket.SOFT_RED
    assert decide_sigma_bucket(120.0, 100, 10) == SigmaBucket.SOFT_RED  # exact 2σ

    # --- COLOR-05: dev > 2σ → HARD_RED ---
    assert decide_sigma_bucket(120.01, 100, 10) == SigmaBucket.HARD_RED
    assert decide_sigma_bucket(200, 100, 10) == SigmaBucket.HARD_RED

    # --- COLOR-02: -2σ ≤ dev < -1σ → SOFT_GREEN ---
    assert decide_sigma_bucket(89.99, 100, 10) == SigmaBucket.SOFT_GREEN
    assert decide_sigma_bucket(80.0, 100, 10) == SigmaBucket.SOFT_GREEN  # exact -2σ

    # --- COLOR-04: dev < -2σ → HARD_GREEN ---
    assert decide_sigma_bucket(79.99, 100, 10) == SigmaBucket.HARD_GREEN
    assert decide_sigma_bucket(50, 100, 10) == SigmaBucket.HARD_GREEN

    # --- D-04 색 hex single source of truth (COLOR-01/07) ---
    assert GREEN_800 == "#2E7D32"
    assert GREEN_900 == "#1B5E20"
    assert GREEN_100 == "#C8E6C9"
    assert RED_800 == "#C62828"
    assert RED_900 == "#B71C1C"
    assert RED_100 == "#FFCDD2"
    assert DEFAULT_BLACK == "#000000"

    # Sanity: nan helper works as expected
    assert math.isnan(nan)


def test_decide_impulse():
    """gap-fix 01-14: ImpulseBucket — 두 부호 일치 → GREEN/RED, 불일치 → BLUE, NaN → DEFAULT."""
    from stocksig.compute.color_rules import BLUE_100, BLUE_800, ImpulseBucket, decide_impulse

    assert BLUE_100 == "#BBDEFB"
    assert BLUE_800 == "#1565C0"

    assert decide_impulse(0.01, 0.5) == ImpulseBucket.GREEN
    assert decide_impulse(-0.01, -0.5) == ImpulseBucket.RED
    assert decide_impulse(0.01, -0.5) == ImpulseBucket.BLUE
    assert decide_impulse(-0.01, 0.5) == ImpulseBucket.BLUE
    assert decide_impulse(float("nan"), 0.5) == ImpulseBucket.DEFAULT
    assert decide_impulse(0.01, float("nan")) == ImpulseBucket.DEFAULT
    assert decide_impulse(None, 0.5) == ImpulseBucket.DEFAULT

    # value 텍스트 검증
    assert ImpulseBucket.GREEN.value == "녹색"
    assert ImpulseBucket.RED.value == "적색"
    assert ImpulseBucket.BLUE.value == "청색"
    assert ImpulseBucket.DEFAULT.value == ""
