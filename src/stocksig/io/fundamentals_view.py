"""시트1 펀더멘털 어댑터 — compute_matrix 최신열 → FundamentalsResult (Plan 10-01, FUND-11).

`metrics_engine.compute_matrix` 가 계산한 분기 매트릭스의 **최신 분기 1열**을 시트1 writer
입력 계약 `FundamentalsResult{per,peg,gpm,opm}` 로 변환하는 **얇은 어댑터**(D-08). 신규
산식·신규 dataclass 0 — `fundamentals.FundamentalsResult/MetricCell/_empty_cell/_is_missing`
import 재사용(D-04). MetricCell 은 타입 변환·복사 없이 그대로 FundamentalsResult 에 넣어
`sheet_portfolio.py` 4셀 writer 가 0줄 수정으로 동작한다(Core Value 보호).

**호출 순서 강제 (L1 LANDMINE):**
    이 어댑터는 가격을 주입하지 않는다. 호출자가 반드시 아래 순서로 호출해야
    PER/PEG 가 채워진다 — 어기면 빈 셀("가격 의존 지표…")로 나와 회귀가 된다.

        matrix = compute_matrix(ticker)
        inject_prices_for_quarter(matrix, latest_q, last_close, matrix["EPS_ttm"])  # D-06/D-07
        result = matrix_to_fundamentals(matrix, latest_q)

provenance 라벨(D-09): 값 있는 셀의 note 를 "소스 · 최신분기"(예 "EDGAR · 2026Q2",
"DART+yf · 2026Q2")로 재구성한다. source 없는(결손) 셀은 기존 한국어 사유 note 보존(D-10).

**PEG source 승계 (L5 LANDMINE):** `compute_peg_cell` 은 source=None 을 반환한다
(per_value 만 받음). PEG value 가 있으면 PER 셀 source 를 승계한 뒤 라벨을 합성한다 —
그래야 PEG 주석이 구 경로("EDGAR · Q") 대비 회귀하지 않는다.
"""

from __future__ import annotations

from stocksig.io.fundamentals import (
    FundamentalsResult,
    MetricCell,
    _empty_cell,
    _is_missing,
)

# DB 빈 종목(분기 데이터 없음) 사유 — 구 경로 "조회 실패" 와 동일 UX(D-02/D-10).
_MISSING_DB_NOTE = "조회 실패: DB 분기 데이터 없음"


def _provenance_note(cell: MetricCell, latest_q: str) -> str | None:
    """값 있는 셀 → "소스 · 최신분기" 라벨, source 없으면 기존 사유 note 보존(D-09/D-10)."""
    if cell.source:
        return f"{cell.source} · {latest_q}"
    return cell.note


def matrix_to_fundamentals(matrix: dict, latest_q: str | None) -> FundamentalsResult:
    """compute_matrix 최신열 → FundamentalsResult{per,peg,gpm,opm} 무변환 매핑 (D-08).

    Args:
        matrix: compute_matrix 반환 `{metric: {quarter: MetricCell}}`.
                **반드시 inject_prices_for_quarter(latest_q, last_close) 적용 후** 전달
                (L1 — 아니면 PER/PEG 빈 셀).
        latest_q: 시트1이 읽을 최신 분기 "YYYYQn". None(DB 빈 종목) → 4셀 빈칸+사유(D-02).

    Returns:
        FundamentalsResult — PER/PEG/GPM/OPM 셀. 값 있는 셀 note 는 provenance 라벨,
        결손 셀 note 는 한국어 사유. PEG.source 는 PER.source 승계(L5).
    """
    def cell_or_empty(metric: str) -> MetricCell:
        c = matrix.get(metric, {}).get(latest_q) if latest_q else None
        return c if c is not None else _empty_cell(_MISSING_DB_NOTE)

    per = cell_or_empty("PER")
    peg = cell_or_empty("PEG")
    gpm = cell_or_empty("GPM")
    opm = cell_or_empty("OPM")

    # L5: PEG 셀 source 는 compute_peg_cell 계약상 None — value 가 있으면 PER source 승계.
    if not _is_missing(peg.value) and peg.source is None:
        peg.source = per.source

    # D-09: 값 있는 셀 note 를 "소스 · 최신분기" 라벨로 합성(결손 셀은 사유 보존).
    if latest_q is not None:
        for cell in (per, peg, gpm, opm):
            if not _is_missing(cell.value):
                cell.note = _provenance_note(cell, latest_q)

    return FundamentalsResult(per=per, peg=peg, gpm=gpm, opm=opm)


__all__ = ["matrix_to_fundamentals"]
