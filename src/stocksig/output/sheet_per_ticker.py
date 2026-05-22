"""티커별 시트 작성 (D-03 컬럼 레이아웃 + 정적 색 베이킹 + num_format 01-06/01-07/01-14).

gap-fix 01-14: 95 컬럼 (이전 70).
  - 일봉 OHLC: rolling(200) median/std
  - 주봉 OHLC: expanding median/std (forward-filled to daily)
  - Close 등락률(일/주) + Volume(일/주) + Volume 등락률(일/주)
  - EMA_Close × 4 (값/med/std/trend)
  - DIFF × 12 (med/std)
  - Stoch (일/주) %K %D + RSI (일/주)
  - MACD-OSC (일/주)
  - Impulse (일/주)
"""

from __future__ import annotations

import re

import pandas as pd

from stocksig.compute.color_rules import (
    ImpulseBucket,
    SigmaBucket,
    TechBucket,
    decide_rsi_bucket,
    decide_sigma_bucket,
    decide_stoch_bucket,
    decide_trend_bucket,
)

_EMA_VALUE_RE = re.compile(r"^EMA_Close_\d+$")

_PRICES = ["Close", "High", "Low"]
_EMA_PERIODS = [11, 22, 96, 192]

_PRICE_KR = {"Close": "종가", "High": "고가", "Low": "저가", "Volume": "거래량"}


def build_column_layout(df: pd.DataFrame | None = None) -> list[str]:
    """gap-fix 01-14: 95 컬럼 이름 list.

    구조:
      Date (1)
      + 일봉 OHLC(3 × 3 = 9) + 주봉 OHLC(3 × 3 = 9)
      + 일봉 Close_pct_change(+med/std=3) + 주봉 Close_pct_change(+med/std=3)
      + Volume(일/주 = 2)
      + 일봉 Volume_pct_change(+med/std=3) + 주봉 Volume_pct_change(+med/std=3)
      + EMA_Close × 4 (val,med,std,trend) = 16
      + DIFF × 12 (val,med,std) = 36
      + Stoch %K/%D 일/주 = 4
      + RSI 일/주 = 2
      + MACD_OSC 일/주 = 2
      + Impulse 일/주 = 2
      = 1+9+9+3+3+2+3+3+16+36+4+2+2+2 = 95
    """
    layout: list[str] = ["Date"]
    # 일봉 OHLC (rolling 200) — 9
    for col in ["Close", "High", "Low"]:
        layout += [col, f"{col}_median", f"{col}_std"]
    # 주봉 OHLC (expanding) — 9
    for col in ["Close_week", "High_week", "Low_week"]:
        layout += [col, f"{col}_median", f"{col}_std"]
    # 종가 등락률 일/주 — 6
    layout += [
        "Close_pct_change",
        "Close_pct_change_median",
        "Close_pct_change_std",
        "Close_pct_change_week",
        "Close_pct_change_week_median",
        "Close_pct_change_week_std",
    ]
    # Volume 일/주 — 2
    layout += ["Volume", "Volume_week"]
    # Volume 등락률 일/주 — 6
    layout += [
        "Volume_pct_change",
        "Volume_pct_change_median",
        "Volume_pct_change_std",
        "Volume_pct_change_week",
        "Volume_pct_change_week_median",
        "Volume_pct_change_week_std",
    ]
    # EMA_Close × 4 — 16
    for n in _EMA_PERIODS:
        base = f"EMA_Close_{n}"
        layout += [base, f"{base}_median", f"{base}_std", f"{base}_trend"]
    # DIFF (period 외부, price 내부) — 36
    for n in _EMA_PERIODS:
        for price in _PRICES:
            base = f"DIFF_{price}_{n}"
            layout += [base, f"{base}_median", f"{base}_std"]
    # Stoch 일/주 — 4
    layout += ["Stoch_%K", "Stoch_%D", "Stoch_%K_week", "Stoch_%D_week"]
    # RSI 일/주 — 2
    layout += ["RSI", "RSI_week"]
    # MACD-OSC 일/주 — 2
    layout += ["MACD_OSC", "MACD_OSC_week"]
    # Impulse 일/주 — 2
    layout += ["Impulse_daily", "Impulse_weekly"]
    return layout


def korean_header(col: str) -> str:
    """원본 컬럼명 → 한국어 헤더 (gap-fix 01-14: (일)/(주) 접두사)."""
    if col == "Date":
        return "날짜"

    # 임펄스
    if col == "Impulse_daily":
        return "(일)임펄스"
    if col == "Impulse_weekly":
        return "(주)임펄스"

    # MACD-OSC
    if col == "MACD_OSC":
        return "(일)MACD-OSC"
    if col == "MACD_OSC_week":
        return "(주)MACD-OSC"

    # RSI
    if col == "RSI":
        return "(일)RSI"
    if col == "RSI_week":
        return "(주)RSI"

    # Stoch
    if col == "Stoch_%K":
        return "(일)Stoch %K"
    if col == "Stoch_%D":
        return "(일)Stoch %D"
    if col == "Stoch_%K_week":
        return "(주)Stoch %K"
    if col == "Stoch_%D_week":
        return "(주)Stoch %D"

    # pct_change (일/주)
    if col == "Close_pct_change":
        return "(일)종가 등락률"
    if col == "Close_pct_change_week":
        return "(주)종가 등락률"
    if col == "Volume_pct_change":
        return "(일)거래량 등락률"
    if col == "Volume_pct_change_week":
        return "(주)거래량 등락률"

    # Volume
    if col == "Volume":
        return "(일)거래량"
    if col == "Volume_week":
        return "(주)거래량"

    # _median/_std suffix 처리 (재귀 — base 명 lookup)
    if col.endswith("_median"):
        base = col[: -len("_median")]
        return f"{korean_header(base)} 일별 중앙값"
    if col.endswith("_std"):
        base = col[: -len("_std")]
        return f"{korean_header(base)} 일별 표준편차"

    # 일봉 OHLC (200일 접미사 — gap-fix 01-14)
    if col == "Close":
        return "(일)종가 (200일)"
    if col == "High":
        return "(일)고가 (200일)"
    if col == "Low":
        return "(일)저가 (200일)"

    # 주봉 OHLC (week base, prefix 주)
    if col == "Close_week":
        return "(주)종가"
    if col == "High_week":
        return "(주)고가"
    if col == "Low_week":
        return "(주)저가"

    # EMA_Close_{n}_trend (일봉 only)
    if col.startswith("EMA_Close_") and col.endswith("_trend"):
        n = col[len("EMA_Close_") : -len("_trend")]
        return f"ema{n} 추세"

    # EMA_Close_{n} (일봉 only)
    if col.startswith("EMA_Close_"):
        n = col[len("EMA_Close_") :]
        return f"종가 EMA{n}"

    # DIFF_{price}_{n}
    if col.startswith("DIFF_"):
        body = col[len("DIFF_") :]
        price, n = body.rsplit("_", 1)
        return f"{_PRICE_KR.get(price, price)}-EMA{n} 차이"

    return col


KOREAN_HEADERS: dict[str, str] = {col: korean_header(col) for col in build_column_layout()}


def column_num_format(col_name: str) -> str:
    """컬럼명 → num_format type."""
    # 임펄스는 텍스트 — write 루프에서 별도 처리. 임시 'price' (사용되지 않음)
    if col_name in ("Impulse_daily", "Impulse_weekly"):
        return "price"
    # Volume 계열 (값) — Volume, Volume_week
    if col_name in ("Volume", "Volume_week"):
        return "volume"
    # 절대 가격이 아닌 pct_change/percent_ratio 계열
    if col_name.startswith("Close_pct_change") or col_name.startswith("Volume_pct_change"):
        return "percent_ratio"
    # Stoch / RSI → literal % (0~100 스케일)
    if col_name.startswith("Stoch_%") or col_name.startswith("RSI"):
        return "percent_literal"
    # MACD-OSC → price (가격 단위)
    if col_name.startswith("MACD_OSC"):
        return "price"
    # DIFF → 비율
    if col_name.startswith("DIFF_"):
        return "percent_ratio"
    # EMA trend → 비율
    if col_name.endswith("_trend"):
        return "percent_ratio"
    return "price"


def _header_fmt_for(col_name: str, formats: dict):
    """DIFF 그룹별 헤더 bg Format 반환 (gap-fix 01-14)."""
    if col_name.startswith("DIFF_"):
        # DIFF_{price}_{n}  또는 DIFF_{price}_{n}_(median|std)
        # 마지막 숫자 그룹 추출
        m = re.search(r"_(\d+)(?:_(?:median|std))?$", col_name)
        if m:
            n = m.group(1)
            key = f"header_bg_ema{n}"
            if key in formats:
                return formats[key]
    return formats["header"]


def _impulse_fmt(value, formats):
    """impulse 텍스트 값 → Format 선택."""
    if value == ImpulseBucket.GREEN.value:
        return formats["impulse_green"]
    if value == ImpulseBucket.RED.value:
        return formats["impulse_red"]
    if value == ImpulseBucket.BLUE.value:
        return formats["impulse_blue"]
    return formats["impulse_default"]


def write_sheet_for_ticker(
    wb,
    formats: dict,
    ticker: str,
    enriched_df: pd.DataFrame,
    scalars: dict[str, dict[str, float]],
) -> None:
    """티커 시트 1개 — gap-fix 01-14: 95 col + A1 bold 20pt + 헤더 bg + 임펄스."""
    ws = wb.add_worksheet(ticker)
    # gap-fix 01-14: A1 = 티커, bold + 20pt
    ws.write(0, 0, ticker, formats["a1_title"])

    layout = build_column_layout(enriched_df)

    # 3·4행: median / std 스칼라 (DEFAULT bucket + 컬럼별 num_format)
    for col_idx, col_name in enumerate(layout):
        if col_name == "Date" or col_name.endswith(("_median", "_std")):
            continue
        # 임펄스 컬럼은 스칼라 없음
        if col_name in ("Impulse_daily", "Impulse_weekly"):
            continue
        if col_name in scalars:
            stats = scalars[col_name]
            fmt_type = column_num_format(col_name)
            # Stoch/RSI 는 TechBucket.DEFAULT, 그 외 SigmaBucket.DEFAULT
            if (
                col_name.startswith("Stoch_%")
                or col_name.startswith("RSI")
            ):
                default_fmt = formats[(TechBucket.DEFAULT, fmt_type)]
            else:
                default_fmt = formats[(SigmaBucket.DEFAULT, fmt_type)]
            if "median" in stats and stats["median"] is not None:
                try:
                    ws.write(2, col_idx, stats["median"], default_fmt)
                except Exception:
                    pass
            if "std" in stats and stats["std"] is not None:
                try:
                    ws.write(3, col_idx, stats["std"], default_fmt)
                except Exception:
                    pass

    # 5행: 한국어 헤더 (DIFF 그룹별 bg Format)
    for col_idx, col_name in enumerate(layout):
        header_fmt = _header_fmt_for(col_name, formats)
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

            # 임펄스 셀: 텍스트 + 색 Format
            if col_name in ("Impulse_daily", "Impulse_weekly"):
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    ws.write_blank(excel_row, col_idx, None)
                    continue
                fmt = _impulse_fmt(value, formats)
                ws.write_string(excel_row, col_idx, str(value), fmt)
                continue

            if pd.isna(value):
                ws.write_blank(excel_row, col_idx, None)
                continue

            fmt_type = column_num_format(col_name)

            # 색 결정 → bucket
            if col_name in ("Stoch_%K", "Stoch_%D", "Stoch_%K_week", "Stoch_%D_week"):
                bucket = decide_stoch_bucket(value)
            elif col_name in ("RSI", "RSI_week"):
                bucket = decide_rsi_bucket(value)
            elif col_name.endswith("_trend"):
                bucket = decide_trend_bucket(value)
            elif col_name in ("Close_pct_change", "Close_pct_change_week"):
                # gap-fix 01-14: σ 신호로 변경
                med = row.get(f"{col_name}_median")
                std = row.get(f"{col_name}_std")
                bucket = decide_sigma_bucket(value, med, std)
            elif col_name == "Volume":
                vpc = row.get("Volume_pct_change")
                bucket = decide_trend_bucket(vpc) if not pd.isna(vpc) else TechBucket.DEFAULT
            elif col_name == "Volume_week":
                vpc = row.get("Volume_pct_change_week")
                bucket = decide_trend_bucket(vpc) if not pd.isna(vpc) else TechBucket.DEFAULT
            elif col_name in ("Volume_pct_change", "Volume_pct_change_week"):
                med = row.get(f"{col_name}_median")
                std = row.get(f"{col_name}_std")
                bucket = decide_sigma_bucket(value, med, std)
            elif col_name == "MACD_OSC":
                d = row.get("MACD_OSC_diff")
                bucket = decide_trend_bucket(d) if not pd.isna(d) else TechBucket.DEFAULT
            elif col_name == "MACD_OSC_week":
                d = row.get("MACD_OSC_week_diff")
                bucket = decide_trend_bucket(d) if not pd.isna(d) else TechBucket.DEFAULT
            elif col_name.endswith(("_median", "_std")):
                bucket = SigmaBucket.DEFAULT
            else:
                # Close/High/Low (일봉, rolling 200), Close_week/High_week/Low_week, EMA_Close_N
                med = row.get(f"{col_name}_median")
                std = row.get(f"{col_name}_std")
                bucket = decide_sigma_bucket(value, med, std)

            fmt = formats[(bucket, fmt_type)]
            ws.write(excel_row, col_idx, value, fmt)

    ws.set_column(0, len(layout) - 1, 12)

    # 숨김: *_median, *_std, EMA_Close_{N} 값
    for col_idx, col_name in enumerate(layout):
        if col_name.endswith(("_median", "_std")) or _EMA_VALUE_RE.match(col_name):
            ws.set_column(col_idx, col_idx, None, None, {"hidden": True})

    ws.freeze_panes(5, 0)
