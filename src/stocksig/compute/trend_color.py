"""트렌드 상대색 bucket(D-05/06/07) + 전년동기 YoY 글리프(D-08) — 순수 함수.

CLAUDE.md "정적 색 베이킹" 정합: Python이 (분기 열 × 산업 그룹) 2차원 모집단
안에서 상대 순위를 판정해 "초록"|"무색"|"빨강" bucket 을 돌려준다(색 hex 베이킹은
Plan 02 history_workbook 이 color_rules 상수로 수행 — 본 모듈은 hex 미정의).

방향(D-06):
  - LOWER_IS_BETTER (PER/PEG/PBR/PCR/PSR) — 낮을수록 초록.
  - HIGHER_IS_BETTER (ROE/ROA/GPM/OPM)   — 높을수록 초록.

표본 게이트(D-07): 산업="" 또는 유효 peer < 3 → 무색.
결손 게이트: fundamentals._is_missing 재사용(신규 정의 금지).
"""

from __future__ import annotations

from stocksig.io.fundamentals import MetricCell, _is_missing

# 방향 상수 (D-06)
LOWER_IS_BETTER = {"PER", "PEG", "PBR", "PCR", "PSR"}   # 낮을수록 초록
HIGHER_IS_BETTER = {"ROE", "ROA", "GPM", "OPM"}         # 높을수록 초록

# D-07 표본 게이트 권장 최소 표본
_MIN_SAMPLE = 3


def relative_bucket(metric: str, value, peer_values: list, industry: str) -> str:
    """(분기 열 × 산업) 모집단 내 상대 순위 → "초록"|"무색"|"빨강".

    - industry=="" 또는 유효 peer(_is_missing 제외) < 3 → "무색" (D-07).
    - value 자체가 결손 → "무색".
    - 유효 peer 내 위치를 3분위(하/중/상)로 나눠 bucket 결정.
      LOWER_IS_BETTER 면 하위가 초록, HIGHER_IS_BETTER 면 상위가 초록.
    - 동률(strict 분리 불가) → "무색" (RESEARCH A4 중립).
    """
    if industry == "" or _is_missing(value):
        return "무색"

    valid = [v for v in peer_values if not _is_missing(v)]
    if len(valid) < _MIN_SAMPLE:
        return "무색"

    # 유효 peer 대비 value 위치: 엄격히 작은/큰 표본 수.
    below = sum(1 for v in valid if v < value)
    above = sum(1 for v in valid if v > value)
    total = len(valid)

    # 동률(strict 분리 0) → 중립.
    if below == 0 and above == 0:
        return "무색"

    # 하위 3분위(낮은 값) / 상위 3분위(높은 값) / 중간.
    lower_frac = below / total      # 0에 가까울수록 낮은 값
    upper_frac = above / total      # 0에 가까울수록 높은 값

    if lower_frac <= 1.0 / 3.0:
        rank = "low"
    elif upper_frac <= 1.0 / 3.0:
        rank = "high"
    else:
        rank = "mid"

    if rank == "mid":
        return "무색"

    if metric in LOWER_IS_BETTER:
        return "초록" if rank == "low" else "빨강"
    if metric in HIGHER_IS_BETTER:
        return "초록" if rank == "high" else "빨강"
    # 방향 미지정 지표 → 중립(무색).
    return "무색"


def yoy_glyph(cell_q: MetricCell | None, cell_q_prior: MetricCell | None) -> str:
    """전년동기(4분기 전) 대비 ↑/↓ 글리프 (D-08).

    둘 중 하나라도 None 또는 value 결손(_is_missing) → "" (전년 결손 생략).
    cell_q > prior → " ▲", < → " ▼", == → "".
    4분기 전 키 산술은 호출자(_calendar_quarter_offset(q,-4))가 처리.
    """
    if cell_q is None or cell_q_prior is None:
        return ""
    if _is_missing(cell_q.value) or _is_missing(cell_q_prior.value):
        return ""
    if cell_q.value > cell_q_prior.value:
        return " ▲"
    if cell_q.value < cell_q_prior.value:
        return " ▼"
    return ""
