"""trend_color 상대색 bucket(D-05/06/07) + YoY 글리프(D-08) 단언 — 네트워크 0.

순수 함수만 검증(import만으로 실행, 외부 호출 0). 합성 peer 리스트·MetricCell
직접 구성. 결손 게이트는 fundamentals._is_missing 재사용(신규 정의 0).
"""

from __future__ import annotations

import math

import pytest

from stocksig.compute import trend_color as tc
from stocksig.io.fundamentals import MetricCell


def _cell(value):
    return MetricCell(value=value, source=None, note=None)


# === relative_bucket — 방향(D-06) ============================================


def test_lower_is_better_lowest_is_green():
    # PER: 낮을수록 초록. value=5가 peer [5,20,30,40] 중 최저 → 초록
    assert tc.relative_bucket("PER", 5.0, [5.0, 20.0, 30.0, 40.0], "tech") == "초록"


def test_lower_is_better_highest_is_red():
    # PER: 최고값 → 빨강
    assert tc.relative_bucket("PER", 40.0, [5.0, 20.0, 30.0, 40.0], "tech") == "빨강"


def test_higher_is_better_reversed():
    # ROE: 높을수록 초록 (방향 반전). 최고값 → 초록
    assert tc.relative_bucket("ROE", 40.0, [5.0, 20.0, 30.0, 40.0], "tech") == "초록"
    # 최저값 → 빨강
    assert tc.relative_bucket("ROE", 5.0, [5.0, 20.0, 30.0, 40.0], "tech") == "빨강"


# === relative_bucket — 표본 게이트(D-07) =====================================


def test_sample_below_three_is_plain():
    # 유효 peer 2종 (<3) → 무색
    assert tc.relative_bucket("PER", 5.0, [5.0, 20.0], "tech") == "무색"


def test_empty_industry_is_plain():
    # 산업="" → 무색 (peer가 충분해도)
    assert tc.relative_bucket("PER", 5.0, [5.0, 20.0, 30.0, 40.0], "") == "무색"


def test_missing_peers_excluded_then_gate():
    # None/NaN peer는 유효 표본에서 제외 → 유효 2종 → 무색
    assert (
        tc.relative_bucket("PER", 5.0, [5.0, 20.0, None, float("nan")], "tech")
        == "무색"
    )


def test_value_missing_is_plain():
    # value 자체가 결손(None/NaN) → 무색
    assert tc.relative_bucket("PER", None, [5.0, 20.0, 30.0, 40.0], "tech") == "무색"
    assert (
        tc.relative_bucket("PER", float("nan"), [5.0, 20.0, 30.0, 40.0], "tech")
        == "무색"
    )


def test_tie_is_plain():
    # 동값(전부 동일) → 동률 무색 (RESEARCH A4)
    assert tc.relative_bucket("PER", 10.0, [10.0, 10.0, 10.0], "tech") == "무색"


# === yoy_glyph (D-08) ========================================================


def test_yoy_glyph():
    assert tc.yoy_glyph(_cell(20.0), _cell(10.0)) == " ▲"  # 증가
    assert tc.yoy_glyph(_cell(10.0), _cell(20.0)) == " ▼"  # 감소
    assert tc.yoy_glyph(_cell(10.0), _cell(10.0)) == ""  # 동값


def test_yoy_glyph_prior_missing():
    # 전년동기 결손(None cell / None value / NaN value) → 화살표 생략 (D-08)
    assert tc.yoy_glyph(_cell(20.0), None) == ""
    assert tc.yoy_glyph(None, _cell(10.0)) == ""
    assert tc.yoy_glyph(_cell(20.0), _cell(None)) == ""
    assert tc.yoy_glyph(_cell(20.0), _cell(float("nan"))) == ""
    assert tc.yoy_glyph(_cell(None), _cell(10.0)) == ""
