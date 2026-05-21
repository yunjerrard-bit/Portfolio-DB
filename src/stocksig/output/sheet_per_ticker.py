"""티커별 시트 작성 (D-03 컬럼 레이아웃 + 정적 색 베이킹 + num_format 01-06).

build_column_layout(df): 124 컬럼 이름 list (D-03 순서).
korean_header(col): 원본 컬럼명 → 한국어 헤더.
KOREAN_HEADERS: 정적 dict alias (korean_header lookup 가능).
column_num_format(col): col_name → "price" | "volume" | "percent" (gap-fix 01-06).
write_sheet_for_ticker(wb, formats, ticker, df, scalars): 시트 1개 작성.
"""

from __future__ import annotations

import pandas as pd

from stocksig.compute.color_rules import (
    SigmaBucket,
    TechBucket,
    decide_rsi_bucket,
    decide_sigma_bucket,
    decide_stoch_bucket,
)

# --- D-03 컬럼 레이아웃 상수 ----------------------------------------------
_OHLCV = ["Close", "High", "Low", "Volume"]
_PRICES = ["Close", "High", "Low"]
_EMA_PERIODS = [11, 22, 96, 192]

_PRICE_KR = {"Close": "종가", "High": "고가", "Low": "저가", "Volume": "거래량"}

_VOLUME_COLS = {"Volume", "Volume_median", "Volume_std"}
_PERCENT_COLS = {"Stoch_%K", "Stoch_%D", "RSI"}


def build_column_layout(df: pd.DataFrame | None = None) -> list[str]:
    """D-03 124 컬럼 이름 list 반환.

    구조: Date + (4 OHLCV × 3) + (12 EMA × 3) + (12 DIFF × 3)
        + (12 dailychg × 3) + (Stoch_%K, Stoch_%D, RSI)
    = 1 + 12 + 36 + 36 + 36 + 3 = 124
    """
    layout: list[str] = ["Date"]
    # 원천 OHLCV (group 1)
    for col in _OHLCV:
        layout += [col, f"{col}_median", f"{col}_std"]
    # 1차 EMA (group 2)
    for price in _PRICES:
        for n in _EMA_PERIODS:
            base = f"EMA_{price}_{n}"
            layout += [base, f"{base}_median", f"{base}_std"]
    # 2차 차이 DIFF (group 3)
    for price in _PRICES:
        for n in _EMA_PERIODS:
            base = f"DIFF_{price}_{n}"
            layout += [base, f"{base}_median", f"{base}_std"]
    # 2차 EMA 일변동 (group 4)
    for price in _PRICES:
        for n in _EMA_PERIODS:
            base = f"EMA_{price}_{n}_dailychg"
            layout += [base, f"{base}_median", f"{base}_std"]
    # 기술 지표 (group 5)
    layout += ["Stoch_%K", "Stoch_%D", "RSI"]
    return layout


def korean_header(col: str) -> str:
    """원본 컬럼명 → 한국어 헤더 (D-05, SHEET-05)."""
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

    # EMA_{price}_{n}_dailychg
    if col.startswith("EMA_") and col.endswith("_dailychg"):
        body = col[len("EMA_") : -len("_dailychg")]
        # body = "{price}_{n}"
        price, n = body.rsplit("_", 1)
        return f"{_PRICE_KR.get(price, price)} EMA{n} 일변동"

    # EMA_{price}_{n}
    if col.startswith("EMA_"):
        body = col[len("EMA_") :]
        price, n = body.rsplit("_", 1)
        return f"{_PRICE_KR.get(price, price)} EMA{n}"

    # DIFF_{price}_{n}
    if col.startswith("DIFF_"):
        body = col[len("DIFF_") :]
        price, n = body.rsplit("_", 1)
        return f"{_PRICE_KR.get(price, price)}-EMA{n} 차이"

    return col


# 정적 dict alias: layout 컬럼 → 한국어 (lookup 호환)
KOREAN_HEADERS: dict[str, str] = {col: korean_header(col) for col in build_column_layout()}


def column_num_format(col_name: str) -> str:
    """컬럼명 → num_format type ("price" | "volume" | "percent").

    분류 규칙 (gap-fix 01-06):
      - Volume 계열 (Volume, Volume_median, Volume_std) → "volume" (#,##0)
      - Stoch_%K, Stoch_%D, RSI → "percent" (0.00"%")
      - 그 외 (Close/High/Low + EMA/DIFF/dailychg + 모든 _median/_std) → "price" (#,##0.00)
    """
    if col_name in _VOLUME_COLS:
        return "volume"
    if col_name in _PERCENT_COLS:
        return "percent"
    return "price"


def write_sheet_for_ticker(
    wb,
    formats: dict,
    ticker: str,
    enriched_df: pd.DataFrame,
    scalars: dict[str, dict[str, float]],
) -> None:
    """티커 시트 1개를 D-03 레이아웃 + 정적 색 베이킹 + num_format으로 작성.

    Layout:
      row 0 (A1): ticker (SHEET-02)
      row 2: 데이터 컬럼 위치에 scalars[col]['median'] (SHEET-03)
      row 3: scalars[col]['std'] (SHEET-04)
      row 4: 한국어 헤더 (header Format) (SHEET-05)
      row 5+: enriched_df.sort_index(ascending=False) 한 행씩 (SHEET-06)

    각 데이터 셀에 (bucket, fmt_type) Format 적용:
      - bucket: 색 (SigmaBucket / TechBucket / DEFAULT)
      - fmt_type: column_num_format(col_name) → price/volume/percent
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
            # 3/4행은 통계 스칼라 → 색 없음(DEFAULT) + num_format
            # OHLCV 컬럼은 SigmaBucket.DEFAULT, 기술지표는 TechBucket.DEFAULT 사용
            if col_name in _PERCENT_COLS:
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
            elif col_name.endswith(("_median", "_std")):
                # row 단위 _median/_std 값 — 색 없음, num_format만
                bucket = SigmaBucket.DEFAULT
            else:
                med = row.get(f"{col_name}_median")
                std = row.get(f"{col_name}_std")
                bucket = decide_sigma_bucket(value, med, std)

            fmt = formats[(bucket, fmt_type)]
            ws.write(excel_row, col_idx, value, fmt)

    ws.set_column(0, len(layout) - 1, 12)
