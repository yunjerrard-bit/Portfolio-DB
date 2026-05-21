"""티커별 시트 작성 (D-03 컬럼 레이아웃 + 정적 색 베이킹 + num_format 01-06/01-07).

build_column_layout(df): 68 컬럼 이름 list (gap-fix 01-12 — dailychg 제거 후).
korean_header(col): 원본 컬럼명 → 한국어 헤더.
KOREAN_HEADERS: 정적 dict alias (korean_header lookup 가능).
column_num_format(col): col_name → "price" | "volume" | "percent_literal" | "percent_ratio".
write_sheet_for_ticker(wb, formats, ticker, df, scalars): 시트 1개 작성.
"""

from __future__ import annotations

import re

import pandas as pd

from stocksig.compute.color_rules import (
    SigmaBucket,
    TechBucket,
    decide_rsi_bucket,
    decide_sigma_bucket,
    decide_stoch_bucket,
    decide_trend_bucket,
)

# gap-fix 01-11: 정확히 `EMA_Close_{N}` (suffix 없는 값 컬럼)에만 매치
_EMA_VALUE_RE = re.compile(r"^EMA_Close_\d+$")

# --- 컬럼 레이아웃 상수 (gap-fix 01-07) ----------------------------------
_OHLCV = ["Close", "High", "Low", "Volume"]
_PRICES = ["Close", "High", "Low"]
_EMA_PERIODS = [11, 22, 96, 192]

_PRICE_KR = {"Close": "종가", "High": "고가", "Low": "저가", "Volume": "거래량"}

_VOLUME_COLS = {"Volume", "Volume_median", "Volume_std"}
_PERCENT_LITERAL_COLS = {"Stoch_%K", "Stoch_%D", "RSI"}


def build_column_layout(df: pd.DataFrame | None = None) -> list[str]:
    """68 컬럼 이름 list 반환 (gap-fix 01-07/01-11/01-12).

    구조: Date + (4 OHLCV × 3) + (4 EMA_Close × 4) + (12 DIFF × 3)
        + (Stoch_%K, Stoch_%D, RSI)
    = 1 + 12 + 16 + 36 + 3 = 68

    (gap-fix 01-12: dailychg 그룹 4 × 3 = 12 컬럼 제거 — trend가 대체.)
    """
    layout: list[str] = ["Date"]
    # 원천 OHLCV (group 1) — 4 × 3 = 12
    for col in _OHLCV:
        layout += [col, f"{col}_median", f"{col}_std"]
    # 1차 EMA — Close만 (group 2) — 4 × 4 = 16 (gap-fix 01-11: + trend)
    for n in _EMA_PERIODS:
        base = f"EMA_Close_{n}"
        layout += [base, f"{base}_median", f"{base}_std", f"{base}_trend"]
    # 2차 DIFF — Close/High/Low × N, 모두 EMA_Close_N 기준 (group 3) — 12 × 3 = 36
    # gap-fix 01-09: EMA period 외부, price 내부 → period로 그룹핑된 순서
    for n in _EMA_PERIODS:
        for price in _PRICES:
            base = f"DIFF_{price}_{n}"
            layout += [base, f"{base}_median", f"{base}_std"]
    # 기술 지표 (group 4)
    layout += ["Stoch_%K", "Stoch_%D", "RSI"]
    return layout


def korean_header(col: str) -> str:
    """원본 컬럼명 → 한국어 헤더 (D-05, SHEET-05, gap-fix 01-07)."""
    if col == "Date":
        return "날짜"
    if col == "Stoch_%K":
        return "Stoch %K"
    if col == "Stoch_%D":
        return "Stoch %D"
    if col == "RSI":
        return "RSI"

    # *_median / *_std suffix 처리
    if col.endswith("_median"):
        base = col[: -len("_median")]
        return f"{korean_header(base)} 일별 중앙값"
    if col.endswith("_std"):
        base = col[: -len("_std")]
        return f"{korean_header(base)} 일별 표준편차"

    # OHLCV 원천
    if col in _PRICE_KR:
        return _PRICE_KR[col]

    # EMA_Close_{n}_trend → "ema{n} 추세" (gap-fix 01-11)
    if col.startswith("EMA_Close_") and col.endswith("_trend"):
        n = col[len("EMA_Close_") : -len("_trend")]
        return f"ema{n} 추세"

    # (gap-fix 01-12: EMA_Close_{n}_dailychg 분기 제거 — 컬럼 자체가 없어짐)

    # EMA_Close_{n} → "종가 EMA{n}"
    if col.startswith("EMA_Close_"):
        n = col[len("EMA_Close_") :]
        return f"종가 EMA{n}"

    # DIFF_{price}_{n} → "{종가|고가|저가}-EMA{n} 차이"
    if col.startswith("DIFF_"):
        body = col[len("DIFF_") :]
        price, n = body.rsplit("_", 1)
        return f"{_PRICE_KR.get(price, price)}-EMA{n} 차이"

    return col


# 정적 dict alias: layout 컬럼 → 한국어 (lookup 호환)
KOREAN_HEADERS: dict[str, str] = {col: korean_header(col) for col in build_column_layout()}


def column_num_format(col_name: str) -> str:
    """컬럼명 → num_format type (gap-fix 01-07).

    분류 규칙:
      - Volume 계열 (Volume, Volume_median, Volume_std) → "volume" (#,##0)
      - Stoch_%K, Stoch_%D, RSI → "percent_literal" (0.00"%") — 값 0~100
      - DIFF_* 와 DIFF_*_median/_std → "percent_ratio" (0.00%) — 값 0~1 비율
      - 그 외 (Close/High/Low + EMA_Close_N + 모든 _median/_std) → "price" (#,##0.00)
    """
    if col_name in _VOLUME_COLS:
        return "volume"
    if col_name in _PERCENT_LITERAL_COLS:
        return "percent_literal"
    # DIFF 계열 — DIFF_, DIFF_*_median, DIFF_*_std 모두 비율
    if col_name.startswith("DIFF_"):
        return "percent_ratio"
    # gap-fix 01-11: EMA_Close_N_trend → 비율 (pct_change)
    if col_name.endswith("_trend"):
        return "percent_ratio"
    return "price"


def write_sheet_for_ticker(
    wb,
    formats: dict,
    ticker: str,
    enriched_df: pd.DataFrame,
    scalars: dict[str, dict[str, float]],
) -> None:
    """티커 시트 1개를 68 컬럼 레이아웃 + 정적 색 베이킹 + num_format으로 작성.

    Layout:
      row 0 (A1): ticker (SHEET-02)
      row 2: 데이터 컬럼 위치에 scalars[col]['median'] (SHEET-03)
      row 3: scalars[col]['std'] (SHEET-04)
      row 4: 한국어 헤더 (header Format) (SHEET-05)
      row 5+: enriched_df.sort_index(ascending=False) 한 행씩 (SHEET-06)

    각 데이터 셀에 (bucket, fmt_type) Format 적용:
      - bucket: 색 (SigmaBucket / TechBucket / DEFAULT)
      - fmt_type: column_num_format(col_name) → price/volume/percent_literal/percent_ratio
    """
    ws = wb.add_worksheet(ticker)
    ws.write(0, 0, ticker)

    layout = build_column_layout(enriched_df)
    header_fmt = formats["header"]

    # 3·4행: median / std 스칼라 (DEFAULT bucket + 컬럼별 num_format)
    for col_idx, col_name in enumerate(layout):
        if col_name == "Date" or col_name.endswith(("_median", "_std")):
            continue
        if col_name in scalars:
            stats = scalars[col_name]
            fmt_type = column_num_format(col_name)
            if col_name in _PERCENT_LITERAL_COLS:
                default_fmt = formats[(TechBucket.DEFAULT, fmt_type)]
            else:
                default_fmt = formats[(SigmaBucket.DEFAULT, fmt_type)]
            if "median" in stats and stats["median"] is not None:
                ws.write(2, col_idx, stats["median"], default_fmt)
            if "std" in stats and stats["std"] is not None:
                ws.write(3, col_idx, stats["std"], default_fmt)

    # 5행: 한국어 헤더 (header Format)
    for col_idx, col_name in enumerate(layout):
        ws.write(4, col_idx, korean_header(col_name), header_fmt)

    # 6행+: 날짜 내림차순 데이터
    sorted_df = enriched_df.sort_index(ascending=False)
    for row_offset, (idx, row) in enumerate(sorted_df.iterrows()):
        excel_row = 5 + row_offset
        for col_idx, col_name in enumerate(layout):
            if col_name == "Date":
                try:
                    ws.write_datetime(
                        excel_row,
                        col_idx,
                        idx.to_pydatetime() if hasattr(idx, "to_pydatetime") else idx,
                    )
                except Exception:
                    ws.write(excel_row, col_idx, str(idx))
                continue

            if col_name not in row.index:
                continue

            value = row[col_name]
            if pd.isna(value):
                ws.write_blank(excel_row, col_idx, None)
                continue

            fmt_type = column_num_format(col_name)

            # 색 결정 → bucket
            if col_name in ("Stoch_%K", "Stoch_%D"):
                bucket = decide_stoch_bucket(value)
            elif col_name == "RSI":
                bucket = decide_rsi_bucket(value)
            elif col_name.endswith("_trend"):
                # gap-fix 01-11: EMA pct_change → 양수 green / 음수 red
                bucket = decide_trend_bucket(value)
            elif col_name.endswith(("_median", "_std")):
                bucket = SigmaBucket.DEFAULT
            else:
                med = row.get(f"{col_name}_median")
                std = row.get(f"{col_name}_std")
                bucket = decide_sigma_bucket(value, med, std)

            fmt = formats[(bucket, fmt_type)]
            ws.write(excel_row, col_idx, value, fmt)

    ws.set_column(0, len(layout) - 1, 12)

    # gap-fix 01-08/01-11/01-12: *_median, *_std, 그리고 EMA_Close_{N} 값 컬럼도 숨김.
    # trend 등 다른 suffix 는 가시 유지. (dailychg 컬럼은 01-12에서 제거됨.)
    for col_idx, col_name in enumerate(layout):
        if col_name.endswith(("_median", "_std")) or _EMA_VALUE_RE.match(col_name):
            ws.set_column(col_idx, col_idx, None, None, {"hidden": True})

    # gap-fix 01-10: 1~5행(ticker, median, std, blank, 한국어 헤더) 고정 — 스크롤 시 항상 보임
    ws.freeze_panes(5, 0)
