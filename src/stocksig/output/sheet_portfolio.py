"""Phase 2 Wave 3 (02-03): 통합 포트폴리오 시트 ("시트1") writer.

D-02 (단일 색 결정 경로 = compute.color_rules), D-03 (실패 티커 행),
D-08 (15 컬럼 레이아웃), PORT-02/03/04/06/07/08, TECH-07.

스탠드얼론 — `(wb, formats, results, failures, input_order)` 만 받아 시트 하나를
쓴다. Phase 1 sheet_per_ticker.py 는 건드리지 않는다.

VALIDATION 매핑 결정: 시트 이름은 한글 literal `"시트1"`로 고정한다
(CONTEXT.md "시트1" 표기와 일치).
"""

from __future__ import annotations

import logging
import re
from datetime import datetime

import pandas as pd
import xlsxwriter

from stocksig.compute.color_rules import (
    SigmaBucket,
    TechBucket,
    decide_rsi_bucket,
    decide_sigma_bucket,
    decide_stoch_bucket,
)
from stocksig.runner import TickerFailure, TickerResult

logger = logging.getLogger(__name__)

# 22 컬럼 — 기존 21열 + 기업명(index 1, 06-01 COMPANY-01) 삽입.
# 기업명을 티커(0)와 시장(2) 사이에 넣어 컬럼이 한 칸씩 우측 시프트된다.
# 하드코딩 정수 인덱스 대신 `_COL` 명명 인덱스를 단일 진실 출처로 사용해
# 시프트 회귀를 구조적으로 차단한다 (RESEARCH Pattern 3 / Pitfall 1).
PORTFOLIO_COLUMNS: list[str] = [
    "티커",
    "기업명",  # index 1 (06-01) — A 티커와 C 시장 사이 영문 기업명
    "시장",
    "티어",
    "산업",
    "최신 종가",
    "전일 등락률",
    "DIFF Close vs EMA11",
    "DIFF Close vs EMA22",
    "DIFF Close vs EMA96",
    "DIFF Close vs EMA192",
    "거래량",
    "(일)Stoch %K",
    "(일)RSI",
    "(주)Stoch %K",
    "(주)RSI",
    "(일)임펄스",
    "(주)임펄스",
    "PER",  # col 18 (시트 S)
    "PEG",  # col 19 (시트 T)
    "GPM",  # col 20 (시트 U)
    "OPM",  # col 21 (시트 V)
]

# 헤더명 → 0-base 컬럼 인덱스 단일 진실 출처. 정수 하드코딩 전면 대체.
_COL: dict[str, int] = {name: i for i, name in enumerate(PORTFOLIO_COLUMNS)}

# 펀더멘털 4셀 컬럼 인덱스 — _COL 에서 도출 (17→18 등 자동 시프트).
# PER/PEG = "price"(#,##0.00), GPM/OPM = "percent_ratio"(0.00%).
_FUND_COL_PER = _COL["PER"]
_FUND_COL_PEG = _COL["PEG"]
_FUND_COL_GPM = _COL["GPM"]
_FUND_COL_OPM = _COL["OPM"]

_SHEET_NAME = "시트1"
_EMA_PERIODS = (11, 22, 96, 192)
_FORBIDDEN_SHEET_CHARS = re.compile(r"[\[\]:\*\?/\\]")


# ---------------- helpers --------------------------------------------------


def _sanitize_sheet_name(name: str) -> str:
    """Excel 금지 문자 제거 + 31자 truncate. RESEARCH Pattern 5."""
    cleaned = _FORBIDDEN_SHEET_CHARS.sub("_", name)
    return cleaned[:31]


def _internal_link(ticker: str) -> str:
    """티커 → internal hyperlink target (single-quote 항상 wrap — KR `.KS`/`.KQ` 호환)."""
    return f"internal:'{_sanitize_sheet_name(ticker)}'!A1"


def _nan(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def _impulse_fmt(value, formats):
    if value == "녹색":
        return formats["impulse_green"]
    if value == "적색":
        return formats["impulse_red"]
    if value == "청색":
        return formats["impulse_blue"]
    return formats["impulse_default"]


def _write_fund_cell(ws, row: int, col: int, cell, num_fmt: str, formats: dict) -> None:
    """펀더멘털 단일 셀 — 값 write_number + 출처 write_comment (D-02/D-05).

    cell.value 존재 → write_number(기존 Format[(DEFAULT, num_fmt)] 재사용) +
                       note(또는 source) write_comment.
    cell.value 결손 → write_blank + 사유 note(또는 "조회 실패") write_comment.
    0/-999999 등 특수값을 절대 쓰지 않는다 (D-05 — 평균/정렬 오염 방지).
    write_comment 는 값/num_format 과 독립이라 포맷을 손상시키지 않는다.
    """
    fmt = formats[(SigmaBucket.DEFAULT, num_fmt)]
    value = cell.value
    if value is not None and not _nan(value):
        ws.write_number(row, col, float(value), fmt)
        comment = cell.note or cell.source
        if comment:
            ws.write_comment(row, col, str(comment))
    else:
        # D-05: 빈 셀 + 한국어 사유 주석 (값 미기재).
        ws.write_blank(row, col, None, fmt)
        ws.write_comment(row, col, str(cell.note or "조회 실패"))


# ---------------- row writers ---------------------------------------------


def _write_success_row(ws, row: int, res: TickerResult, formats: dict) -> None:
    """시트1 성공 티커 행."""
    last = res.enriched_df.iloc[-1]
    spec = res.spec

    # 티커 (hyperlink)
    ws.write_url(
        row,
        _COL["티커"],
        _internal_link(spec.symbol),
        cell_format=formats[(SigmaBucket.DEFAULT, "price")],
        string=spec.symbol,
    )
    # 기업명 (06-01 COMPANY-01/03) — 영문 기업명, 결손/None 시 티커 폴백.
    ws.write_string(
        row,
        _COL["기업명"],
        res.company_name or spec.symbol,
        formats[(SigmaBucket.DEFAULT, "price")],
    )
    # 시장
    ws.write_string(row, _COL["시장"], res.market)
    # 티어
    ws.write_string(row, _COL["티어"], spec.tier or "")
    # 산업
    ws.write_string(row, _COL["산업"], spec.industry or "")

    # 최신 종가
    close = last.get("Close")
    if not _nan(close):
        ws.write_number(
            row, _COL["최신 종가"], float(close), formats[(SigmaBucket.DEFAULT, "price")]
        )

    # 전일 등락률 (Close_pct_change σ-bucket)
    cpc = last.get("Close_pct_change")
    if not _nan(cpc):
        bucket = decide_sigma_bucket(
            cpc, last.get("Close_pct_change_median"), last.get("Close_pct_change_std")
        )
        ws.write_number(
            row, _COL["전일 등락률"], float(cpc), formats[(bucket, "percent_ratio")]
        )

    # DIFF EMA{11,22,96,192} (D-02 = decide_sigma_bucket(DIFF, med, std)) — 연속 4열.
    diff_base = _COL["DIFF Close vs EMA11"]
    for i, n in enumerate(_EMA_PERIODS):
        diff_val = last.get(f"DIFF_Close_{n}")
        diff_med = last.get(f"DIFF_Close_{n}_median")
        diff_std = last.get(f"DIFF_Close_{n}_std")
        if _nan(diff_val):
            continue
        bucket = decide_sigma_bucket(diff_val, diff_med, diff_std)
        ws.write_number(
            row, diff_base + i, float(diff_val), formats[(bucket, "percent_ratio")]
        )

    # 거래량 (Volume) — 색은 Volume_pct_change σ-bucket (PORT-06)
    volume = last.get("Volume")
    if not _nan(volume):
        vpc = last.get("Volume_pct_change")
        vpc_med = last.get("Volume_pct_change_median")
        vpc_std = last.get("Volume_pct_change_std")
        if _nan(vpc):
            bucket = SigmaBucket.DEFAULT
        else:
            bucket = decide_sigma_bucket(vpc, vpc_med, vpc_std)
        ws.write_number(row, _COL["거래량"], float(volume), formats[(bucket, "volume")])

    # (일)Stoch %K
    stoch = last.get("Stoch_%K")
    if not _nan(stoch):
        bucket_t = decide_stoch_bucket(stoch)
        ws.write_number(
            row, _COL["(일)Stoch %K"], float(stoch), formats[(bucket_t, "percent_literal")]
        )

    # (일)RSI
    rsi = last.get("RSI")
    if not _nan(rsi):
        bucket_t = decide_rsi_bucket(rsi)
        ws.write_number(
            row, _COL["(일)RSI"], float(rsi), formats[(bucket_t, "percent_literal")]
        )

    # (주)Stoch %K
    stoch_w = last.get("Stoch_%K_week")
    if not _nan(stoch_w):
        bucket_t = decide_stoch_bucket(stoch_w)
        ws.write_number(
            row, _COL["(주)Stoch %K"], float(stoch_w), formats[(bucket_t, "percent_literal")]
        )

    # (주)RSI
    rsi_w = last.get("RSI_week")
    if not _nan(rsi_w):
        bucket_t = decide_rsi_bucket(rsi_w)
        ws.write_number(
            row, _COL["(주)RSI"], float(rsi_w), formats[(bucket_t, "percent_literal")]
        )

    # (일)임펄스
    imp_d = last.get("Impulse_daily")
    if not _nan(imp_d) and imp_d:
        ws.write_string(row, _COL["(일)임펄스"], str(imp_d), _impulse_fmt(imp_d, formats))

    # (주)임펄스
    imp_w = last.get("Impulse_weekly")
    if not _nan(imp_w) and imp_w:
        ws.write_string(row, _COL["(주)임펄스"], str(imp_w), _impulse_fmt(imp_w, formats))

    # cols 17~20: 펀더멘털 PER/PEG/GPM/OPM (03-05, D-01/D-02/D-05).
    fund = res.fundamentals
    if fund is not None:
        _write_fund_cell(ws, row, _FUND_COL_PER, fund.per, "price", formats)
        _write_fund_cell(ws, row, _FUND_COL_PEG, fund.peg, "price", formats)
        _write_fund_cell(ws, row, _FUND_COL_GPM, fund.gpm, "percent_ratio", formats)
        _write_fund_cell(ws, row, _FUND_COL_OPM, fund.opm, "percent_ratio", formats)
    else:
        # 하위호환: 펀더멘털 미수집 → 4셀 빈칸 + 사유 주석 (raise 금지).
        for col, num_fmt in (
            (_FUND_COL_PER, "price"),
            (_FUND_COL_PEG, "price"),
            (_FUND_COL_GPM, "percent_ratio"),
            (_FUND_COL_OPM, "percent_ratio"),
        ):
            ws.write_blank(row, col, None, formats[(SigmaBucket.DEFAULT, num_fmt)])
            ws.write_comment(row, col, "펀더멘털 미수집")


def _write_failure_row(ws, row: int, fail: TickerFailure, formats: dict) -> None:
    """D-03 / HIGH-1 단일 규칙: 실패 티커 행 — 현행 동작을 한 칸 우측 시프트.

    좌표(0-base):
        _COL["티커"]      = 티커 (marker)
        _COL["기업명"]    = 빈칸 (write 안 함 — 실패행은 기업명 미기록)
        _COL["시장"]      = "?" (marker — 현행 index1 "?"가 한 칸 시프트)
        _COL["(주)임펄스"] = "실패: {reason}" (marker — 현행 index16 reason 시프트)
    """
    marker = formats["failed_row_marker"]
    ws.write_string(row, _COL["티커"], fail.spec.symbol, marker)
    # _COL["기업명"] 칸은 빈칸 유지 — 아무 것도 write 하지 않는다.
    ws.write_string(row, _COL["시장"], "?", marker)
    # 중간 칸은 비워둠.
    ws.write_string(row, _COL["(주)임펄스"], f"실패: {fail.reason}", marker)


# ---------------- main entry -----------------------------------------------


def write_portfolio_sheet(
    wb: xlsxwriter.Workbook,
    formats: dict,
    results: list[TickerResult],
    failures: list[TickerFailure],
    input_order: list[str],
    now: datetime | None = None,
) -> None:
    """시트1 (포트폴리오 통합) 작성.

    Args:
        wb: 활성 xlsxwriter Workbook.
        formats: `make_workbook` 의 44키 Format 캐시.
        results: `runner.run_all` 의 성공 리스트.
        failures: `runner.run_all` 의 실패 리스트.
        input_order: `tickers.txt` 원본 순서의 symbol 리스트. 행은 이 순서를 따른다
            (PORT-02 — as_completed 순이 아님).
        now: A1 실행 시각 (테스트 주입용). None → `datetime.now()`.
    """
    ws = wb.add_worksheet(_SHEET_NAME)
    ws.set_column(0, len(PORTFOLIO_COLUMNS) - 1, 14)

    # Row 1 (A1) — 실행 시각 (PORT-08)
    now = now or datetime.now()
    ws.write(0, 0, f"실행 시각: {now:%Y-%m-%d %H:%M:%S}", formats["timestamp"])

    # Row 5 (index 4) — 한국어 헤더 (bold + center)
    for col_idx, name in enumerate(PORTFOLIO_COLUMNS):
        ws.write(4, col_idx, name, formats["header"])

    # 성공 행 — input_order 보존 (PORT-02)
    by_sym = {r.spec.symbol: r for r in results}
    cursor = 5
    for sym in input_order:
        res = by_sym.get(sym)
        if res is None:
            continue
        _write_success_row(ws, cursor, res, formats)
        cursor += 1

    # 실패 행 — input_order 보존, 성공행 다음에 추가 (D-03)
    fail_by_sym = {f.spec.symbol: f for f in failures}
    for sym in input_order:
        fail = fail_by_sym.get(sym)
        if fail is None:
            continue
        _write_failure_row(ws, cursor, fail, formats)
        cursor += 1

    ws.freeze_panes(5, 1)
