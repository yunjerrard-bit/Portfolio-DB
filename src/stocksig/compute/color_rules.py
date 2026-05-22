"""색 결정 규칙 (COLOR-01~07 + TECH-04/05, D-02/D-04).

D-04: Material Design hex single source of truth (Phase 4 튜닝 단일 지점).
D-02: decide_sigma_bucket이 NaN / std==0 명시 분기 → SigmaBucket.DEFAULT
      (Pitfall A 직접 대응).

Pure functions. 외부 의존성 없음.
"""

from __future__ import annotations

import math
from enum import Enum

# --- D-04 색 상수 (Material Design hex) -----------------------------------
GREEN_800 = "#2E7D32"
GREEN_900 = "#1B5E20"
GREEN_100 = "#C8E6C9"
RED_800 = "#C62828"
RED_900 = "#B71C1C"
RED_100 = "#FFCDD2"
DEFAULT_BLACK = "#000000"

# gap-fix 01-14: 임펄스 청색 + 헤더 bg용 BLUE 팔레트
BLUE_100 = "#BBDEFB"
BLUE_800 = "#1565C0"
BLUE_900 = "#0D47A1"


class SigmaBucket(Enum):
    """중앙값 ± σ 색 분류 (Core Value 신호)."""

    DEFAULT = "default"
    SOFT_GREEN = "soft_green"
    HARD_GREEN = "hard_green"
    SOFT_RED = "soft_red"
    HARD_RED = "hard_red"


class ImpulseBucket(str, Enum):
    """임펄스 시스템 (gap-fix 01-14). 텍스트 값을 그대로 셀에 표기."""

    DEFAULT = ""
    GREEN = "녹색"
    RED = "적색"
    BLUE = "청색"


class TechBucket(Enum):
    """기술 지표 (Stoch / RSI) 3단 색 분류."""

    DEFAULT = "default"
    SOFT_GREEN = "soft_green"
    SOFT_RED = "soft_red"


def _is_nanish(x) -> bool:
    """None 또는 float NaN 판정."""
    if x is None:
        return True
    if isinstance(x, float) and math.isnan(x):
        return True
    return False


def decide_sigma_bucket(value, median, std) -> SigmaBucket:
    """value vs (median ± σ) 분류.

    D-02: value/median/std 중 None/NaN/0(std)이면 DEFAULT.
    경계 (deviation 정확히 ±1σ 또는 ±2σ): DEFAULT 또는 SOFT (strict 비교, COLOR-06).
    - dev < -2σ → HARD_GREEN (COLOR-04)
    - -2σ ≤ dev < -1σ → SOFT_GREEN (COLOR-02)
    - -1σ ≤ dev ≤ 1σ → DEFAULT (COLOR-06)
    - 1σ < dev ≤ 2σ → SOFT_RED (COLOR-03)
    - dev > 2σ → HARD_RED (COLOR-05)
    """
    if _is_nanish(value) or _is_nanish(median) or _is_nanish(std):
        return SigmaBucket.DEFAULT
    if std == 0:
        return SigmaBucket.DEFAULT

    deviation = value - median
    if deviation < -2 * std:
        return SigmaBucket.HARD_GREEN
    if deviation < -std:
        return SigmaBucket.SOFT_GREEN
    if deviation > 2 * std:
        return SigmaBucket.HARD_RED
    if deviation > std:
        return SigmaBucket.SOFT_RED
    return SigmaBucket.DEFAULT


def decide_stoch_bucket(value) -> TechBucket:
    """Stoch Slow %K/%D 분류 (D-04 임계 20/80)."""
    if _is_nanish(value):
        return TechBucket.DEFAULT
    if value <= 20:
        return TechBucket.SOFT_GREEN
    if value >= 80:
        return TechBucket.SOFT_RED
    return TechBucket.DEFAULT


def decide_trend_bucket(value) -> TechBucket:
    """EMA 전일 대비 등락률(pct_change) 색 결정 (gap-fix 01-11).

    value > 0 → SOFT_GREEN (상승)
    value < 0 → SOFT_RED   (하락)
    value == 0 또는 NaN/None → DEFAULT
    """
    if _is_nanish(value):
        return TechBucket.DEFAULT
    if value > 0:
        return TechBucket.SOFT_GREEN
    if value < 0:
        return TechBucket.SOFT_RED
    return TechBucket.DEFAULT


def decide_impulse(ema11_trend, macd_osc_diff) -> ImpulseBucket:
    """임펄스 시스템 (gap-fix 01-14).

    ema_trend, macd_osc_diff 동시 양수 → 녹색 (GREEN)
    동시 음수 → 적색 (RED)
    부호 혼합 → 청색 (BLUE)
    NaN / None → DEFAULT
    """
    if _is_nanish(ema11_trend) or _is_nanish(macd_osc_diff):
        return ImpulseBucket.DEFAULT
    up_ema = ema11_trend > 0
    up_osc = macd_osc_diff > 0
    if up_ema and up_osc:
        return ImpulseBucket.GREEN
    if (not up_ema) and (not up_osc):
        return ImpulseBucket.RED
    return ImpulseBucket.BLUE


def decide_rsi_bucket(value) -> TechBucket:
    """RSI 분류 (D-04 임계 30/70)."""
    if _is_nanish(value):
        return TechBucket.DEFAULT
    if value <= 30:
        return TechBucket.SOFT_GREEN
    if value >= 70:
        return TechBucket.SOFT_RED
    return TechBucket.DEFAULT
