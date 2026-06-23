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

# 저량(stock, BS instant) field — PER_SHARE 분자가 이들이면 TTM이 아니라 최근 시점값
# 사용(BPS=total_equity/shares). 그 외 분자(net_income/revenue/operating_cash_flow)는
# 유량 → TTM. dart_client._QUARTERLY_BS_FIELDS analog.
_STOCK_FIELDS: frozenset[str] = frozenset(
    {"total_equity", "total_assets", "total_liabilities", "shares_outstanding"}
)

# 매트릭스에 가격을 주입해 채울 가격 의존 4종 → 주당 분모 metric (D-07 price_denominator).
# REGISTRY 단일 도출 — 시트1·트렌드 공유 코어(inject_prices_for_quarter)와 history_render
# 가 함께 참조한다(사본·드리프트 0). history_render 가 이 상수를 import 재사용한다.
_PRICE_DEPENDENT: dict[str, str] = {
    m.name: m.price_denominator
    for m in REGISTRY
    if m.price_denominator is not None
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

    # DERIVED(PEG) — 2차 파생. compute_cell 단독 산출 불가(가격 의존).
    # 호출자가 compute_peg_cell(PER, EPS_ttm 현재, EPS_ttm 4분기전)로 산출(D-07).
    if mdef.mtype is MetricType.DERIVED:
        return _empty_cell("파생 지표: compute_peg_cell로 2차 계산(PEG)")

    # 분자: 유량 분자 = TTM, 저량 분자(BPS=total_equity 등 BS instant) = 최근 시점값.
    # FLOW_TTM/HYBRID 분자는 항상 유량(TTM). PER_SHARE는 분자가 stock field면 최근,
    # 아니면 TTM(EPS_ttm=net_income TTM·SPS=revenue TTM·OCF_ps=OCF TTM).
    numer_is_stock = mdef.mtype is MetricType.STOCK or (
        mdef.mtype is MetricType.PER_SHARE and mdef.numerator in _STOCK_FIELDS
    )
    if numer_is_stock:
        numer = _recent(raw_by_qf, mdef.numerator, quarter)
        numer_sources = [_source_for_recent(raw_by_qf, mdef.numerator, quarter)]
    else:
        numer = _ttm_sum(raw_by_qf, mdef.numerator, quarter)
        numer_sources = _sources_for_ttm(raw_by_qf, mdef.numerator, quarter)

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


def compute_peg_cell(
    per_value: float | None,
    eps_ttm: float | None,
    eps_prior: float | None,
) -> MetricCell:
    """PEG 2단계 공개 API — PER value·EPS 성장률에서 PEG 산출 (진실 #8·#9, FUND-09).

    PER의 `price_ratio(denom_cell, price)` 2단계 계약과 **대칭**인 공개 진입점.
    PEG는 PER(가격 의존)에 다시 의존하므로 registry/compute_matrix가 값을 직접 산출할
    수 없다(D-07 가격 비결합). 따라서 호출자(Phase 9/10)가 가격 주입 후 본 함수를 호출한다.

    산식·엣지케이스 4종(PER 없음/전년 EPS 미존재/전년 EPS 0/성장률 ≤ 0)은
    `fundamentals._compute_peg`에 위임(신규 산식 작성 금지, Don't Hand-Roll). 산출 후
    sanity bounds("PEG": 0~10, `_apply_sanity` 재사용) 적용 — 범위 밖은 빈값+사유.

    provenance: per_value만 받으므로 source=None(fundamentals._compute_peg와 동일).
    호출자가 PER 셀 source를 보존하려면 결과 셀의 source를 별도 주입하면 된다.

    인자:
      per_value: price_ratio(matrix["EPS_ttm"][q], price).value (가격 주입 후 PER)
      eps_ttm:   matrix["EPS_ttm"][q].value (현재 분기 per-share EPS, 최근 TTM)
      eps_prior: matrix["EPS_ttm"][q-4].value (_calendar_quarter_offset(q,-4))
    """
    cell = _compute_peg(per_value, eps_ttm, eps_prior)
    if _is_missing(cell.value):
        return cell
    ok, reason = _apply_sanity("PEG", cell.value)
    if not ok:
        return MetricCell(value=None, source=cell.source, note=reason)
    return cell


def inject_prices_for_quarter(
    matrix: dict,
    q: str,
    price: float | None,
    eps_map: dict,
) -> None:
    """단일 분기 q에 가격 의존 4종 + PEG in-place 주입 (시트1·트렌드 공유 코어, D-06).

    `history_render._inject_prices`(다분기 루프)와 시트1(최신 분기 1열, Plan 02/03)이
    **동일 코드·동일 입력**을 호출해 두 산출물 값 드리프트를 구조적으로 차단한다(D-06).

    동작:
      (a) 가격 의존 4종(PER/PBR/PCR/PSR) = `price_ratio(matrix[denom][q], price)` 주입.
      (b) PEG 3단 계약 = `compute_peg_cell(PER.value, eps_now, eps_prior(4분기 전))`.

    신규 산식 0 — `price_ratio`/`compute_peg_cell`/`_calendar_quarter_offset` 재사용.
    price 결손 시 4종·PEG 모두 빈 셀+사유로 자연 처리(price_ratio/compute_peg_cell 게이트).

    인자:
      matrix:  compute_matrix 반환 `{metric: {quarter: MetricCell}}` (in-place 변형).
      q:       대상 분기 "YYYYQn".
      price:   주입 가격(시트1=last_close, 트렌드=분기말 종가 / 최신=현재가).
      eps_map: `matrix["EPS_ttm"]` ({quarter: MetricCell}).
    """
    # (a) 가격 의존 4종 — 분모 per-share 셀에 가격 주입.
    for metric, denom in _PRICE_DEPENDENT.items():
        denom_cell = matrix.get(denom, {}).get(q)
        matrix.setdefault(metric, {})[q] = price_ratio(denom_cell, price)

    # (b) 분기별 PEG (3단 계약, D-10) — PER 가격 주입 후 EPS 성장률.
    per = matrix.get("PER", {}).get(q)
    per_value = per.value if per is not None else None
    eps_now = eps_map.get(q)
    eps_now_v = eps_now.value if eps_now is not None else None
    eps_prior = eps_map.get(_calendar_quarter_offset(q, -4))
    eps_prior_v = eps_prior.value if eps_prior is not None else None
    matrix.setdefault("PEG", {})[q] = compute_peg_cell(per_value, eps_now_v, eps_prior_v)


def compute_matrix(
    ticker: str,
    fetch_fn: Callable[[str], list[tuple]] = fetch_raw_quarters,
) -> dict[str, dict[str, MetricCell]]:
    """저장 raw만으로 9종 분기 매트릭스 전체 산출 (외부 재호출 0, D-06).

    반환 = `{metric_name: {quarter: MetricCell}}`. 최신값 = 마지막 분기 열.
    fetch_fn 주입 가능(테스트 격리·DB 비결합). 가격 의존 4종(PER/PBR/PCR/PSR)은
    per-share 분모 셀만 산출 → 호출자가 price_ratio로 가격 주입(D-07).

    **Phase 9/10 PEG 소비 계약 (가격 의존 2차 파생 — compute_peg_cell 공개 API):**
    PEG는 compute_matrix가 직접 산출하지 않는다(PER 가격 의존). 호출자가 3단으로 산출:
      ① PER 확보:   per = price_ratio(matrix["EPS_ttm"][q], price)   # 가격 주입(D-07)
      ② EPS 추출:   eps_now   = matrix["EPS_ttm"][q].value          # 현재 TTM per-share EPS
                    q_prior   = _calendar_quarter_offset(q, -4)     # 4분기 전
                    eps_prior = matrix["EPS_ttm"][q_prior].value
      ③ PEG 산출:   peg = compute_peg_cell(per.value, eps_now, eps_prior)  # MetricCell
    예시:
      >>> matrix = compute_matrix("AAPL")
      >>> per = price_ratio(matrix["EPS_ttm"]["2026Q1"], price=48.0)
      >>> qp = _calendar_quarter_offset("2026Q1", -4)  # "2025Q1"
      >>> peg = compute_peg_cell(
      ...     per.value,
      ...     matrix["EPS_ttm"]["2026Q1"].value,
      ...     matrix["EPS_ttm"][qp].value,
      ... )
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
    "compute_peg_cell",
    "inject_prices_for_quarter",
    "price_ratio",
    "_PRICE_DEPENDENT",
    "_normalize_quarters",
    "_recent",
    "_ttm_sum",
    "_prior_4_quarters",
    "_calendar_quarter_offset",
    "_merge_provenance",
]
