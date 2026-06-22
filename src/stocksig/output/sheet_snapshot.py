"""[최신 스냅샷] 시트 writer (Plan 09-02, D-13 / Open Q2).

종목 1행 × 전 지표(9종) 최신값. **매트릭스 최신 열 셀을 재계산 없이 재사용**한다
(신규 산식·재계산 금지 — price_ratio/compute_peg_cell 호출은 Plan 03 오케스트레이션에서만).
결손/PEG 미산출 셀은 "-" + 사유 코멘트(`_is_missing` 게이트, D-11).

식별 5열은 매트릭스 시트와 동일 트렌드 전용 리터럴(sheet_portfolio import 금지).
값 텍스트는 매트릭스와 동일 규칙(비율 지표 퍼센트·아니면 소수 2자리, WARNING-2).
"""

from __future__ import annotations

from stocksig.io.fundamentals import _is_missing
from stocksig.io.metrics_registry import REGISTRY

# 식별 5열 — 트렌드 전용(매트릭스와 동일 리터럴).
_IDENT_COLUMNS: list[str] = ["티커", "기업명", "시장", "티어", "산업"]
_N_IDENT = len(_IDENT_COLUMNS)

# 스냅샷 9지표 — 표시 순서(D-01 9종).
_SNAPSHOT_METRICS: list[str] = ["PER", "PEG", "GPM", "OPM", "PBR", "PCR", "PSR", "ROE", "ROA"]

# 비율 지표 표기(WARNING-2 — 매트릭스와 동일 규칙).
_IS_RATIO: dict[str, bool] = {m.name: m.is_ratio_0_1 for m in REGISTRY}


def _format_value_text(metric: str, value: float) -> str:
    if _IS_RATIO.get(metric, False):
        return f"{value * 100:.1f}%"
    return f"{value:.2f}"


def write_snapshot_sheet(ws, snapshot_rows: list[dict], formats: dict) -> None:
    """[최신 스냅샷] 시트 작성 (종목 1행 × 9지표 최신값 재사용).

    Args:
        ws: 대상 worksheet.
        snapshot_rows: 종목 행 리스트. 각 dict 키:
            "ticker"/"company"/"market"/"tier"/"industry"(식별),
            "metrics"({metric: MetricCell}) — 매트릭스 최신 열 셀 재사용(D-13).
        formats: 트렌드 Format 캐시.
    """
    # 헤더: 식별 5열 + 9지표.
    for col, name in enumerate(_IDENT_COLUMNS):
        ws.write(0, col, name, formats["header"])
    for j, metric in enumerate(_SNAPSHOT_METRICS):
        ws.write(0, _N_IDENT + j, metric, formats["header"])

    for i, srow in enumerate(snapshot_rows):
        row = 1 + i
        ws.write_string(row, 0, str(srow.get("ticker") or ""))
        ws.write_string(row, 1, str(srow.get("company") or ""))
        ws.write_string(row, 2, str(srow.get("market") or ""))
        ws.write_string(row, 3, str(srow.get("tier") or ""))
        ws.write_string(row, 4, str(srow.get("industry") or ""))

        metrics = srow.get("metrics") or {}
        for j, metric in enumerate(_SNAPSHOT_METRICS):
            col = _N_IDENT + j
            cell = metrics.get(metric)
            if cell is None or _is_missing(getattr(cell, "value", None)):
                ws.write_string(row, col, "-", formats["plain"])
                note = getattr(cell, "note", None) if cell is not None else None
                ws.write_comment(row, col, str(note or "결손"))
                continue
            text_val = _format_value_text(metric, cell.value)
            ws.write_string(row, col, text_val, formats["plain_text"])
            comment = cell.note or cell.source
            if comment:
                ws.write_comment(row, col, str(comment))

    # A열만 freeze(D-04 일관).
    ws.freeze_panes(0, 1)
