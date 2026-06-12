"""Phase 4 Plan 02 (04-02) Task 2: WCAG 휘도 그레이스케일 구분 테스트 (COLOR-07 / SC4).

±1σ/±2σ 색 신호가 흑백(그레이스케일)에서도 방향(매수/과열) 구분 가능한지를
WCAG relative luminance 로 측정 가능하게 만든다.

WCAG relative luminance (sRGB):
  L = 0.2126·R + 0.7152·G + 0.0722·B
  단, R/G/B 는 sRGB 선형화: c/12.92 (c<=0.03928) 또는 ((c+0.055)/1.055)**2.4

색 단일 진원지 (D-02/D-04): 상수 조정 시 color_rules.py 만 변경.

--- 실측 휘도 (2026-06-12 measured) -------------------------------------------
  GREEN_100 #C8E6C9 L=0.7309   RED_100 #FFCDD2 L=0.6958   → HARD bg 차 0.0351
  GREEN_900 #1B5E20 L=0.0834   RED_900 #B71C1C L=0.1098   → HARD font 차 0.0264
  GREEN_800 #2E7D32 L=0.1548   RED_800 #C62828 L=0.1368   → SOFT font 차 0.0180

HARD 버킷(writer.py)은 font(GREEN_900/RED_900) + bg(GREEN_100/RED_100) + bold 조합.
그레이스케일에서 두 HARD bg 는 모두 매우 밝아 차가 작다(0.0351). 본 테스트는
이 휘도차를 측정·고정해, 후속 팔레트 튜닝이 그레이스케일 구분을 약화시키면
적색이 되도록 한다. 임계값은 실측값에서 합리적 마진(약 0.005)을 둔 0.03.
SOFT 글자색 휘도차(0.018)는 Pitfall 5 대로 본질적으로 약하므로 bold + 셀 위치에
의존 — 별도로 측정·문서화하고, 회귀 방지용으로만 하한(0.01)을 둔다.
"""

from __future__ import annotations

from stocksig.compute.color_rules import (
    GREEN_100,
    GREEN_800,
    GREEN_900,
    RED_100,
    RED_800,
    RED_900,
)

# 실측 HARD 배경 휘도차(0.0351)에서 합리적 마진을 둔 임계 — 억지로 낮추지 않음.
HARD_BG_LUMINANCE_THRESHOLD = 0.03
# 실측 SOFT 글자색 휘도차(0.0180). Pitfall 5: SOFT 는 본질적으로 약해 bold 의존.
# 회귀 방지용 하한만 둔다(현재 통과, 후속 튜닝이 더 약화시키면 적색).
SOFT_FONT_LUMINANCE_FLOOR = 0.01


def _rel_luminance(h: str) -> float:
    """WCAG relative luminance — hex(#RRGGBB) → 0.0~1.0.

    sRGB 선형화 후 0.2126·R + 0.7152·G + 0.0722·B.
    """
    h = h.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))

    def _lin(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = _lin(r), _lin(g), _lin(b)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


# --- WCAG 공식 정확성 -------------------------------------------------------


def test_rel_luminance_black_is_zero():
    assert _rel_luminance("#000000") == 0.0


def test_rel_luminance_white_is_one():
    assert abs(_rel_luminance("#FFFFFF") - 1.0) < 1e-9


def test_rel_luminance_pure_green_matches_coefficient():
    """순수 녹(#00FF00) 휘도 ≈ 0.7152 계수 (sRGB 선형화 후 1.0·0.7152)."""
    assert abs(_rel_luminance("#00FF00") - 0.7152) < 1e-6


# --- HARD 버킷(±2σ) 그레이스케일 구분 ---------------------------------------


def test_hard_buckets_distinguishable_grayscale():
    """HARD 배경색(GREEN_100 vs RED_100) 휘도차가 임계 초과 — ±2σ 흑백 구분."""
    diff = abs(_rel_luminance(GREEN_100) - _rel_luminance(RED_100))
    assert diff > HARD_BG_LUMINANCE_THRESHOLD, (
        f"HARD 배경 휘도차 {diff:.4f} ≤ 임계 {HARD_BG_LUMINANCE_THRESHOLD} — "
        "±2σ 그레이스케일 구분 약함. color_rules.py HARD bg 상수 튜닝 필요(D-02)."
    )


def test_hard_font_colors_have_luminance_separation():
    """HARD 글자색(GREEN_900 vs RED_900) 휘도차 측정 — bg 와 함께 방향 신호."""
    diff = abs(_rel_luminance(GREEN_900) - _rel_luminance(RED_900))
    # HARD 는 bg+font+bold 조합으로 구분. font 휘도차도 회귀 방지용 하한 단언.
    assert diff > SOFT_FONT_LUMINANCE_FLOOR, (
        f"HARD 글자색 휘도차 {diff:.4f} ≤ 하한 {SOFT_FONT_LUMINANCE_FLOOR}"
    )


# --- SOFT 버킷(±1σ) 휘도차 측정 (Pitfall 5: bold 의존 문서화) ----------------


def test_soft_font_luminance_difference_measured():
    """SOFT 글자색(GREEN_800 vs RED_800) 휘도차 측정·고정.

    Pitfall 5: SOFT(±1σ)는 글자색만 사용 — 흑백 휘도차가 본질적으로 약하다
    (실측 0.0180). 방향 구분은 bold + 셀 위치(매수/과열 영역)에 의존한다.
    여기서는 회귀 방지 하한(0.01)만 단언하고, 약함을 명시적으로 문서화한다.
    그레이스케일 강구분이 필요하면 color_rules.py SOFT 상수 튜닝(D-02)으로 대응.
    """
    diff = abs(_rel_luminance(GREEN_800) - _rel_luminance(RED_800))
    assert diff > SOFT_FONT_LUMINANCE_FLOOR, (
        f"SOFT 글자색 휘도차 {diff:.4f} ≤ 하한 {SOFT_FONT_LUMINANCE_FLOOR} — "
        "후속 튜닝이 SOFT 구분을 더 약화시킴. color_rules.py SOFT 상수 점검(D-02)."
    )
