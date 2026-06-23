"""펀더멘털 공유 계약 — 데이터 모델·결손 게이트·순수 산식 헬퍼 (D-04).

Plan 10-03(FUND-11): 시트1 PER/PEG/GPM/OPM 이 store/registry 단일 원천
(`metrics_engine.compute_matrix` + `fundamentals_view.matrix_to_fundamentals`)
으로 이관되며, 구 fetch 오케스트레이터(`fetch_fundamentals`/`_fill_us`/`_fill_kr`
+ EDGAR/DART 직접 fetch + 7일 `.cache/fundamentals` 캐시)는 호출자가 사라져
제거됐다(D-03/D-05).

본 모듈은 이제 **공유 계약만** 보유한다 (registry·시트1·trend·color 가 의존):
  - 데이터 모델 `MetricCell{value, source, note}` / `FundamentalsResult{per,peg,gpm,opm}`
    (sheet_portfolio writer 입력 계약)
  - 결손 게이트 `_is_missing` (WR-01 — trend_color/sheet_metric_matrix/sheet_raw/
    sheet_snapshot 공유)
  - 순수 산식 헬퍼 `_compute_per` / `_compute_peg` / `_compute_margin`
    (metrics_engine 가 `_compute_peg` 를 import 재사용)
  - placeholder 헬퍼 `_empty_cell` (fundamentals_view 어댑터가 빈 DB 결손 셀에 재사용)

PEG 산식(RESEARCH Pattern 3 확정식 + 엣지케이스 4종):
    growth_pct = (eps_ttm / eps_prior - 1) * 100
    peg        = per / growth_pct        (growth_pct > 0 일 때만)
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class MetricCell:
    """단일 지표 셀 — 값 + 출처 라벨 + 메타/사유 note.

    - value: 산출값 (None = 결손; 0/-999999 금지, D-05).
    - source: "EDGAR" | "yf" | None (실제 사용 소스).
    - note: "EDGAR · 2026Q2" 같은 메타 또는 "조회 실패: <사유>" 한국어 사유.
    """

    value: float | None
    source: str | None
    note: str | None


@dataclass
class FundamentalsResult:
    """시트1 우측 4셀(PER/PEG/GPM/OPM)에 대응하는 펀더멘털 결과."""

    per: MetricCell
    peg: MetricCell
    gpm: MetricCell
    opm: MetricCell


def _empty_cell(note: str | None = None) -> MetricCell:
    return MetricCell(value=None, source=None, note=note)


# --- 순수 산식 헬퍼 ------------------------------------------------------

def _is_missing(x: float | None) -> bool:
    """결손 게이트 — None 또는 NaN 을 동일하게 "결손"으로 판정 (WR-01).

    NaN 은 모든 비교(<=0 등)가 False 라 `is None` 가드를 통과해 값 있는 셀·
    provenance 로 새므로(D-05 위반), 산식·폴백 진입 전 단일 게이트로 차단한다.
    """
    return x is None or (isinstance(x, float) and math.isnan(x))


def _compute_per(last_close: float | None, eps_ttm: float | None) -> MetricCell:
    """PER = last_close / eps_ttm. eps_ttm None/NaN → 미존재, ≤0 → EPS ≤ 0."""
    if _is_missing(eps_ttm):
        return _empty_cell("조회 실패: EPS TTM 미존재")
    if eps_ttm <= 0:
        return _empty_cell("조회 실패: EPS ≤ 0")
    if _is_missing(last_close):
        return _empty_cell("조회 실패: 종가 미존재")
    return MetricCell(value=last_close / eps_ttm, source=None, note=None)


def _compute_peg(
    per: float | None,
    eps_ttm: float | None,
    eps_prior: float | None,
) -> MetricCell:
    """PEG = PER / ((eps_ttm/eps_prior − 1)×100). 엣지케이스 4종 빈값+한국어 사유."""
    if _is_missing(per):
        return _empty_cell("조회 실패: PER 없음")
    if _is_missing(eps_prior):
        return _empty_cell("조회 실패: 전년 EPS 미존재")
    if eps_prior == 0:
        return _empty_cell("조회 실패: 전년 EPS 0")
    if _is_missing(eps_ttm):
        return _empty_cell("조회 실패: EPS TTM 미존재")
    growth_pct = (eps_ttm / eps_prior - 1) * 100
    if growth_pct <= 0:
        return _empty_cell("조회 실패: EPS 성장률 ≤ 0")
    return MetricCell(value=per / growth_pct, source=None, note=None)


def _compute_margin(numer: float | None, denom: float | None) -> MetricCell:
    """마진 = numer / denom (0~1 비율). 분모 0/None 또는 분자 None → 빈값+사유."""
    if _is_missing(numer):
        return _empty_cell("조회 실패: 분자 미존재")
    if _is_missing(denom) or denom == 0:
        return _empty_cell("조회 실패: 매출(분모) 미존재")
    return MetricCell(value=numer / denom, source=None, note=None)
