"""티커별 시트 작성 (D-03 컬럼 레이아웃 + 정적 색 베이킹).

build_column_layout(df): 124 컬럼 이름 list (D-03 순서).
korean_header(col): 원본 컬럼명 → 한국어 헤더.
KOREAN_HEADERS: 정적 dict alias (korean_header lookup 가능).
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


def write_sheet_for_ticker(
    wb,
    formats: dict,
    ticker: str,
    enriched_df: pd.DataFrame,
    scalars: dict[str, dict[str, float]],
) -> None:
    """티커 시트 1개를 D-03 레이아웃 + 정적 색 베이킹으로 작성.

    Layout:
      row 0 (A1): ticker (SHEET-02)
      row 2: 데이터 컬럼 위치에 scalars[col]['median'] (SHEET-03)
      row 3: scalars[col]['std'] (SHEET-04)
      row 4: 한국어 헤더 (header Format) (SHEET-05)
      row 5+: enriched_df.sort_index(ascending=False) 한 행씩 (SHEET-06)

    각 데이터 셀에 SigmaBucket / Stoch·RSI 셀에 TechBucket Format 적용.
    DEFAULT bucket은 fmt 미지정 (기본 검정).
    """
    ws = wb.add_worksheet(ticker)
    ws.write(0, 0, ticker)

    layout = build_column_layout(enriched_df)
    header_fmt = formats["header"]

    # 3·4행: median / std 스칼라
    for col_idx, col_name in enumerate(layout):
        if col_name == "Date" or col_name.endswith(("_median", "_std")):
            continue
        if col_name in scalars:
            stats = scalars[col_name]
            if "median" in stats and stats["median"] is not None:
                ws.write(2, col_idx, stats["median"])
            if "std" in stats and stats["std"] is not None:
                ws.write(3, col_idx, stats["std"])

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

            # 색 결정
            if col_name in ("Stoch_%K", "Stoch_%D"):
                bucket = decide_stoch_bucket(value)
                fmt = formats[bucket] if bucket != TechBucket.DEFAULT else None
            elif col_name == "RSI":
                bucket = decide_rsi_bucket(value)
                fmt = formats[bucket] if bucket != TechBucket.DEFAULT else None
            elif col_name.endswith(("_median", "_std")):
                fmt = None
            else:
                med = row.get(f"{col_name}_median")
                std = row.get(f"{col_name}_std")
                bucket = decide_sigma_bucket(value, med, std)
                fmt = formats[bucket] if bucket != SigmaBucket.DEFAULT else None

            if fmt is None:
                ws.write(excel_row, col_idx, value)
            else:
                ws.write(excel_row, col_idx, value, fmt)

    ws.set_column(0, len(layout) - 1, 12)
