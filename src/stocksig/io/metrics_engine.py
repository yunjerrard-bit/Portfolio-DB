"""분기 매트릭스 계산 엔진 — 저장 raw만으로 9종 지표를 외부 재호출 없이 산출 (FUND-09).

Phase 9(트렌드 엑셀 매트릭스)·Phase 10(시트1 최신열)이 공통으로 읽는 **단일 원천**
백엔드 계약. 두 출력의 값이 드리프트 없이 일치해야 한다(설계노트).

구성:
  1) 분기 산술 헬퍼 — `_calendar_quarter_offset`/`_prior_4_quarters` ("YYYYQn" ±N,
     Q1→전년 Q4 경계, Pitfall 5). dart_client._calendar_quarter_key analog.
  2) 유형 계산 코어 — `_recent`(저량=분기 시점값) / `_ttm_sum`(유량=직전 4분기 합,
     1개라도 결손 시 None 반환 — 부분합산·0 대체 절대 금지, SC4/D-05).
  3) `_normalize_quarters` — fetch_raw_quarters 행 → `{(quarter, field): (value, source)}`
     dict. DART 손익은 08-01 확정대로 thstrm_amount=분기 단독값 → 추가 분해 없이 그대로
     소비(단순 4분기 합 = TTM). EDGAR Q4는 raw 부재대로 자연 결손(FY−9M 보정 미구현).
  4) `compute_cell`/`compute_matrix`/`price_ratio` — registry 순회 + per-share 분모 +
     sanity bounds + per-metric provenance.

설계 결정(08-01/08-02 SUMMARY 권위 입력):
- **D-03** 하이브리드(ROE/ROA) = 분자 TTM ÷ 분모 *최근값*(기초·기말 평균 아님).
- **D-04** registry(저장 raw 4분기 합)가 새 단일 원천(canonical). 레거시 시트1 표시값과의
  미세 차이는 '더 일관된 값'으로 수용·문서화.
- **D-05** 결손 = None (0/-999999 금지). _is_missing 단일 게이트(WR-01).
- **D-07** 가격 의존 4종(PER/PBR/PCR/PSR)은 per-share 분모만 산출. 비율은 호출자가
  price_ratio로 가격 주입 → registry와 가격 비결합.
- **D-08** per-metric provenance: 사용 raw field source 라벨, 혼합 시 정렬 "+"결합.
- **D-09** 폴백 fetch(DART→Naver→yf)는 registry 책임 아님(Phase 10 오케스트레이션).
  registry는 저장된 어느 source raw든 균일 소비, 1차 결손 시 빈값+사유.

재사용(신규 정의 금지, Phase 10 계약 동일 — Don't Hand-Roll):
  fundamentals._is_missing / MetricCell / _empty_cell / _compute_peg
"""

from __future__ import annotations

from typing import Callable

from stocksig.io.fundamentals import (
    MetricCell,
    _compute_peg,
    _empty_cell,
    _is_missing,
)
from stocksig.io.fundamentals_store import fetch_raw_quarters
from stocksig.io.metrics_registry import REGISTRY, MetricDef, MetricType

# --- sanity bounds (RESEARCH 권고표, ASSUMED — 느슨하게 시작). 밖=빈값+사유 ---
# 비율/배수 metric별 (하한, 상한). 범위 밖 = 단위 오류·이상치 → 빈값+"sanity 범위 밖"(D-05).
_SANITY_BOUNDS: dict[str, tuple[float, float]] = {
    "GPM": (-0.5, 1.5),
    "OPM": (-2.0, 1.5),
    "ROE": (-2.0, 2.0),
    "ROA": (-1.0, 1.0),
    "PER": (0.0, 1000.0),
    "PEG": (0.0, 10.0),
    "PBR": (0.0, 100.0),
    "PSR": (0.0, 100.0),
    "PCR": (0.0, 100.0),
}


# --- 캘린더 분기 산술 (Pitfall 5 경계 정확) ---------------------------------

def _calendar_quarter_offset(q: str, n: int) -> str:
    """"YYYYQn" + n 분기 (n<0=과거). Q1−1=전년 Q4 경계 정확.

    예: ("2026Q1", -1) -> "2025Q4", ("2026Q4", 1) -> "2027Q1".
    """
    year = int(q[:4])
    quarter = int(q[5:])
    # 0-기준 절대 분기 인덱스로 환산 후 산술 (음수 안전).
    idx = year * 4 + (quarter - 1) + n
    new_year, new_q0 = divmod(idx, 4)
    return f"{new_year}Q{new_q0 + 1}"


def _prior_4_quarters(q: str) -> list[str]:
    """해당 분기 포함 직전 4분기 키 (TTM 윈도). [q, q-1, q-2, q-3] 내림차순."""
    return [_calendar_quarter_offset(q, -i) for i in range(4)]


# --- 분기 정규화 ------------------------------------------------------------

def _normalize_quarters(rows: list[tuple]) -> dict[tuple[str, str], tuple[float | None, str | None]]:
    """fetch_raw_quarters 행 → `{(quarter, field): (value, source)}` dict.

    행 = (quarter, source, field, value, period_type, reprt_code, unit).
    DART 손익 thstrm_amount=분기 단독값(08-01 확정) → 추가 분해 없이 그대로 저장
    (단순 4분기 합 = TTM). EDGAR Q4는 raw 부재대로 자연 결손 — 본 함수는 raw를 변형하지
    않고 키만 만든다(누적 분해·FY−9M 보정 모두 미구현, 08-01 방침).
    동일 (quarter, field)에 복수 source 행이 있으면 마지막 행이 우선(조회 순서 의존).
    """
    out: dict[tuple[str, str], tuple[float | None, str | None]] = {}
    for row in rows:
        quarter, source, field, value, _period_type, _reprt_code, _unit = row
        out[(quarter, field)] = (value, source)
    return out


# --- 유형 계산 코어 ---------------------------------------------------------

def _recent(
    raw_by_qf: dict[tuple[str, str], tuple[float | None, str | None]],
    field: str,
    quarter: str,
) -> float | None:
    """저량(STOCK) / 하이브리드 분모 — 해당 분기 시점값 (D-03, 기초·기말 평균 아님)."""
    value, _source = raw_by_qf.get((quarter, field), (None, None))
    return None if _is_missing(value) else value


def _ttm_sum(
    raw_by_qf: dict[tuple[str, str], tuple[float | None, str | None]],
    field: str,
    quarter: str,
) -> float | None:
    """유량(FLOW_TTM) / 하이브리드·주당 분자 — 직전 4분기 합.

    4분기 중 1개라도 결손(부재·None·NaN)이면 None 반환. 부분합산·0 대체 절대 금지
    (SC4/D-05). pandas rolling().sum() min_periods 부분합산은 안티패턴이라 미사용.
    """
    total = 0.0
    for q in _prior_4_quarters(quarter):
        value, _source = raw_by_qf.get((q, field), (None, None))
        if _is_missing(value):
            return None
        total += value
    return total


def _sources_for_ttm(
    raw_by_qf: dict[tuple[str, str], tuple[float | None, str | None]],
    field: str,
    quarter: str,
) -> list[str]:
    """TTM 윈도 4분기에서 사용된 source 라벨 (provenance 병합용)."""
    labels: list[str] = []
    for q in _prior_4_quarters(quarter):
        _value, source = raw_by_qf.get((q, field), (None, None))
        if source:
            labels.append(source)
    return labels


def _source_for_recent(
    raw_by_qf: dict[tuple[str, str], tuple[float | None, str | None]],
    field: str,
    quarter: str,
) -> str | None:
    """저량 시점값의 source 라벨."""
    _value, source = raw_by_qf.get((quarter, field), (None, None))
    return source


def _merge_provenance(used_sources: list[str | None]) -> str | None:
    """per-metric provenance — 동일 source면 그 라벨, 혼합이면 정렬 "+"결합 (D-08).

    fundamentals L289 `"+".join` 패턴. None/빈값은 제외.
    """
    distinct = sorted({s for s in used_sources if s})
    if not distinct:
        return None
    return "+".join(distinct)


def _apply_sanity(name: str, value: float) -> tuple[bool, str | None]:
    """sanity bounds 검사. (통과여부, 사유). 범위 밖 → (False, 한국어 사유)."""
    bounds = _SANITY_BOUNDS.get(name)
    if bounds is None:
        return True, None
    low, high = bounds
    if value < low or value > high:
        return False, f"sanity 범위 밖({low}~{high}): {value:.4g}"
    return True, None


# --- 셀 산출 ----------------------------------------------------------------

def compute_cell(
    mdef: MetricDef,
    quarter: str,
    raw_by_qf: dict[tuple[str, str], tuple[float | None, str | None]],
) -> MetricCell:
    """단일 (metric, quarter) 셀 산출 — mtype별 산식 분기.

    - STOCK: _recent 분자(/_recent 분모).
    - FLOW_TTM: _ttm_sum 분자 ÷ _ttm_sum 분모 (마진 GPM/OPM — 분모도 유량 매출 TTM).
    - HYBRID: _ttm_sum 분자 ÷ _recent 분모 (ROE/ROA, D-03).
    - PER_SHARE 분모 metric(EPS_ttm/BPS/SPS/OCF_ps): 분자(유량은 TTM·저량은 최근)
      ÷ 최근 shares. shares 결손 → 빈값+"발행주식수 미존재"(Pitfall 4).
    - PER_SHARE 가격 의존(PER/PBR/PCR/PSR): numerator/denominator=None → 본 함수는
      비율을 계산하지 않고 빈 셀 반환. 호출자가 price_ratio로 가격 주입(D-07).
    - DERIVED(PEG): registry는 유형만 선언. 본 함수 단독으로는 산출 불가(2차 파생).
    결손=None(0 금지, D-05). sanity 범위 밖=빈값+사유.
    """
    name = mdef.name

    # 가격 의존 4종 — 비율 미계산(D-07). per-share 분모는 price_denominator가 별도 metric.
    if mdef.price_denominator is not None:
        return _empty_cell("가격 의존 지표: price_ratio로 가격 주입 필요")

    # DERIVED(PEG) — 2차 파생. compute_cell 단독 산출 불가(엔진 후처리).
    if mdef.mtype is MetricType.DERIVED:
        return _empty_cell("파생 지표: 2차 계산(PEG)")

    # 분자: 유량/주당 분자 = TTM, 저량(분모로 쓰이는 BS instant) = 최근.
    if mdef.mtype in (MetricType.FLOW_TTM, MetricType.HYBRID, MetricType.PER_SHARE):
        numer = _ttm_sum(raw_by_qf, mdef.numerator, quarter)
        numer_sources = _sources_for_ttm(raw_by_qf, mdef.numerator, quarter)
    else:  # STOCK
        numer = _recent(raw_by_qf, mdef.numerator, quarter)
        numer_sources = [_source_for_recent(raw_by_qf, mdef.numerator, quarter)]

    if _is_missing(numer):
        return _empty_cell(f"{name}: 분자({mdef.numerator}) 미존재 또는 TTM 결손")

    # 분모: FLOW_TTM(마진) = 유량 매출 TTM, HYBRID/PER_SHARE = 최근 시점값.
    if mdef.mtype is MetricType.FLOW_TTM:
        denom = _ttm_sum(raw_by_qf, mdef.denominator, quarter)
        denom_sources = _sources_for_ttm(raw_by_qf, mdef.denominator, quarter)
    else:  # HYBRID / PER_SHARE
        denom = _recent(raw_by_qf, mdef.denominator, quarter)
        denom_sources = [_source_for_recent(raw_by_qf, mdef.denominator, quarter)]

    if _is_missing(denom) or denom == 0:
        if mdef.denominator == "shares_outstanding":
            return _empty_cell(f"{name}: 발행주식수 미존재")
        return _empty_cell(f"{name}: 분모({mdef.denominator}) 미존재 또는 0")

    value = numer / denom
    source = _merge_provenance([*numer_sources, *denom_sources])

    ok, reason = _apply_sanity(name, value)
    if not ok:
        return MetricCell(value=None, source=source, note=reason)

    return MetricCell(value=value, source=source, note=None)


def price_ratio(denom_cell: MetricCell, price: float | None) -> MetricCell:
    """가격 의존 비율 = price ÷ per-share 분모 (D-07 가격 주입).

    PER=price/EPS_ttm, PBR=price/BPS, PCR=price/OCF_ps, PSR=price/SPS.
    분모 결손/≤0 또는 price 결손 → 빈값+사유. provenance는 분모 셀 source 보존.
    OCF<0(PCR) 등은 분모≤0 게이트로 자연 차단(빈값+사유).
    """
    if denom_cell is None or _is_missing(denom_cell.value):
        return _empty_cell("가격비율: 분모(주당 지표) 미존재")
    if denom_cell.value <= 0:
        return MetricCell(value=None, source=denom_cell.source, note="가격비율: 분모 ≤ 0")
    if _is_missing(price):
        return MetricCell(value=None, source=denom_cell.source, note="가격비율: 가격 미존재")
    return MetricCell(value=price / denom_cell.value, source=denom_cell.source, note=None)


def compute_matrix(
    ticker: str,
    fetch_fn: Callable[[str], list[tuple]] = fetch_raw_quarters,
) -> dict[str, dict[str, MetricCell]]:
    """저장 raw만으로 9종 분기 매트릭스 전체 산출 (외부 재호출 0, D-06).

    반환 = `{metric_name: {quarter: MetricCell}}`. 최신값 = 마지막 분기 열.
    fetch_fn 주입 가능(테스트 격리·DB 비결합). 가격 의존 4종(PER/PBR/PCR/PSR)은
    per-share 분모 셀만 산출 → 호출자가 price_ratio로 가격 주입(D-07). PEG(DERIVED)는
    PER + EPS 성장률 2차 계산(가격 의존이라 분모만 산출 후 후처리).
    """
    rows = fetch_fn(ticker)
    raw_by_qf = _normalize_quarters(rows)

    # 매트릭스 분기 축 = raw에 등장한 모든 분기 (오름차순).
    quarters = sorted({q for (q, _f) in raw_by_qf})

    matrix: dict[str, dict[str, MetricCell]] = {}
    for mdef in REGISTRY:
        cells: dict[str, MetricCell] = {}
        for q in quarters:
            cells[q] = compute_cell(mdef, q, raw_by_qf)
        matrix[mdef.name] = cells
    return matrix


__all__ = [
    "compute_matrix",
    "compute_cell",
    "price_ratio",
    "_normalize_quarters",
    "_recent",
    "_ttm_sum",
    "_prior_4_quarters",
    "_calendar_quarter_offset",
    "_merge_provenance",
    "_compute_peg",
]
