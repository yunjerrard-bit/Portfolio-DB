"""지표별 매트릭스 시트 writer (Plan 09-02, D-01/02/04/05/07/08/11/12).

행 = 종목, 열 = 식별 5열(티커·기업명·시장·티어·산업) + 분기 열(최신 왼쪽 D-01).
각 분기 셀에 (분기열×산업) 모집단 상대색(D-05/06/07)을 정적 Format 으로 베이킹하고
전년동기 YoY 글리프(D-08)를 셀 텍스트에 결합한다. 결손/sanity-밖 셀은 "-" + 사유
코멘트(D-11 — 0/빈칸 sentinel 금지). A열만 freeze(D-04, 헤더행 미고정).

**시트1 비결합(Core Value):** sheet_portfolio `_COL`/`PORTFOLIO_COLUMNS`를 import 하지
않고 동일 식별열 헤더 리터럴을 트렌드 전용으로 재정의한다(22열 vs 5열+분기열 구조 다름).
색은 history_workbook 의 트렌드 전용 Format 셋만 사용 — 시트1 σ-bucket 미참조.

**peer/prior 책임(WARNING-3):** 모집단(분기열×산업)·4분기 전 셀 계산은 호출자
(Plan 03 run_history)가 담당하고 `peer_lookup(metric, quarter, industry) -> list`·
`prior_lookup(metric, ticker, quarter) -> MetricCell|None`로 주입한다. 본 writer 는
모집단을 자체 구성하지 않는다(책임 단일화 — wave3 통합 시 시그니처 재작업 방지,
Pitfall 3 모집단=(분기열,산업) 2차원 보장은 호출자 측).
"""

from __future__ import annotations

from stocksig.compute.trend_color import relative_bucket, yoy_glyph
from stocksig.io.fundamentals import _is_missing
from stocksig.io.metrics_registry import REGISTRY

# 식별 5열 — 트렌드 전용 정의(sheet_portfolio _COL import 금지, 동일 헤더 리터럴).
_IDENT_COLUMNS: list[str] = ["티커", "기업명", "시장", "티어", "산업"]
_IDENT_COL: dict[str, int] = {name: i for i, name in enumerate(_IDENT_COLUMNS)}
_N_IDENT = len(_IDENT_COLUMNS)

# WARNING-2 표시 정합: 비율 지표(GPM/OPM 등 is_ratio_0_1=True)는 시트1과 동일하게
# 퍼센트(27.0%)로 보이도록 값 텍스트를 포맷한다(저장은 0~1 비율, 신규 산식 아님).
_IS_RATIO: dict[str, bool] = {m.name: m.is_ratio_0_1 for m in REGISTRY}

# 식별 열 개별 최소 폭(시장/티어는 짧은 라벨).
_COL_WIDTHS: dict[str, int] = {
    "티커": 12,
    "기업명": 18,
    "시장": 6,
    "티어": 6,
    "산업": 16,
}


def _format_value_text(metric: str, value: float) -> str:
    """값 텍스트(WARNING-2): 비율 지표는 퍼센트, 아니면 소수 2자리."""
    if _IS_RATIO.get(metric, False):
        return f"{value * 100:.1f}%"
    return f"{value:.2f}"


def _bucket_formats(bucket: str, formats: dict) -> tuple:
    """bucket → (숫자셀 Format, 텍스트셀 Format) 선택."""
    if bucket == "초록":
        return formats["green"], formats["green_text"]
    if bucket == "빨강":
        return formats["red"], formats["red_text"]
    return formats["plain"], formats["plain_text"]


def write_metric_sheet(
    wb,
    ws,
    metric: str,
    ticker_rows: list[dict],
    display_quarters: list[str],
    formats: dict,
    peer_lookup,
    prior_lookup,
) -> None:
    """지표 매트릭스 시트 작성.

    Args:
        wb: 활성 트렌드 Workbook(미사용 — 시그니처 호환·향후 확장).
        ws: 대상 worksheet.
        metric: 지표 이름(REGISTRY name — PER/PEG/GPM/...).
        ticker_rows: 종목 행 리스트. 각 dict 키:
            "ticker"(str), "company"(str|None), "market"(str|None),
            "tier"(str|None), "industry"(str|None),
            "cells"({quarter: MetricCell}) — 그 지표의 분기별 셀(.get 가드).
        display_quarters: 표시 분기 라벨(이미 최신 왼쪽 = reversed, 호출자 산출 D-01).
        formats: `make_history_workbook` 트렌드 Format 캐시.
        peer_lookup: (metric, quarter, industry) -> list[float] 유효 peer 값(호출자 주입).
        prior_lookup: (metric, ticker, quarter) -> MetricCell|None 4분기 전 셀(호출자 주입).
    """
    # (1) 헤더 행: 식별 5열 + 분기 열(최신 왼쪽).
    for col_idx, name in enumerate(_IDENT_COLUMNS):
        ws.write(0, col_idx, name, formats["header"])
    for j, q in enumerate(display_quarters):
        ws.write(0, _N_IDENT + j, q, formats["header"])

    # 식별 열 개별 폭.
    for name, width in _COL_WIDTHS.items():
        ws.set_column(_IDENT_COL[name], _IDENT_COL[name], width)

    # (2) 종목 행.
    for i, trow in enumerate(ticker_rows):
        row = 1 + i  # 헤더가 0행.
        ticker = trow["ticker"]
        industry = trow.get("industry") or ""
        ws.write_string(row, _IDENT_COL["티커"], ticker)
        ws.write_string(row, _IDENT_COL["기업명"], trow.get("company") or "")
        ws.write_string(row, _IDENT_COL["시장"], trow.get("market") or "")
        ws.write_string(row, _IDENT_COL["티어"], trow.get("tier") or "")
        ws.write_string(row, _IDENT_COL["산업"], industry)

        cells = trow.get("cells") or {}

        # (3) 분기 셀.
        for j, q in enumerate(display_quarters):
            col = _N_IDENT + j
            cell = cells.get(q)  # 분기 미보유 → None(Pitfall 2 .get 가드).

            if cell is None or _is_missing(getattr(cell, "value", None)):
                # 결손/sanity-밖(엔진이 None 으로 박음) → "-" + 사유 코멘트(D-11).
                ws.write_string(row, col, "-", formats["plain"])
                note = getattr(cell, "note", None) if cell is not None else None
                ws.write_comment(row, col, str(note or "결손"))
                continue

            value = cell.value
            # (분기열×산업) 모집단 상대색(D-05/06/07) — 호출자 주입 peer.
            peer_values = peer_lookup(metric, q, industry)
            bucket = relative_bucket(metric, value, peer_values, industry)
            _, fmt_text = _bucket_formats(bucket, formats)

            # YoY 글리프(D-08) — 4분기 전 셀은 호출자 주입.
            prior = prior_lookup(metric, ticker, q)
            glyph = yoy_glyph(cell, prior)

            text_val = _format_value_text(metric, value)
            ws.write_string(row, col, f"{text_val}{glyph}", fmt_text)

            # provenance 코멘트(D-12 보조 — [원천] 시트가 중심).
            comment = cell.note or cell.source
            if comment:
                ws.write_comment(row, col, str(comment))

    # (4) A열만 freeze(D-04 — col 1 부터 스크롤, 헤더행 미고정).
    ws.freeze_panes(0, 1)
