"""Walking Skeleton 오케스트레이션 (EXEC-01/02) — gap-fix 01-14 확장.

Pipeline 순서:
  1. fetch_ohlcv
  2. add_pct_change_columns (Close/Volume daily)
  3. compute_weekly → daily에 concat
  4. 주봉 pct_change 컬럼 추가
  5. add_ema_columns (일봉 only)
  6. compute_macd_oscillator (일/주) + .diff() 사본
  7. stoch_slow / rsi_wilder (일/주)
  8. add_rolling_stats(['Close','High','Low'], 200)
  9. add_expanding_stats(다수의 sigma cols)
 10. add_impulse_columns
 11. write_sheet_for_ticker
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from stocksig.compute.ema import add_ema_columns
from stocksig.compute.impulse import add_impulse_columns
from stocksig.compute.indicators import (
    compute_macd_oscillator,
    rsi_wilder,
    stoch_slow,
)
from stocksig.compute.stats import (
    add_expanding_stats,
    add_pct_change_columns,
    add_rolling_stats,
    cumulative_scalars,
)
from stocksig.compute.weekly import compute_weekly
from stocksig.config import load_env
from stocksig.io.input import read_tickers
from stocksig.io.market import fetch_ohlcv
from stocksig.output.sheet_per_ticker import write_sheet_for_ticker
from stocksig.output.writer import make_workbook

logger = logging.getLogger(__name__)


_DAILY_OHLC: list[str] = ["Close", "High", "Low"]
_PRICES: list[str] = ["Close", "High", "Low"]
_EMA_PERIODS: list[int] = [11, 22, 96, 192]


def _build_data_cols() -> list[str]:
    """SCALARS 용 컬럼 list (3·4행 + sigma 계산 대상)."""
    cols: list[str] = list(_DAILY_OHLC)
    # 주봉 OHLC
    cols += ["Close_week", "High_week", "Low_week"]
    # 등락률 일/주
    cols += [
        "Close_pct_change",
        "Close_pct_change_week",
        "Volume_pct_change",
        "Volume_pct_change_week",
    ]
    # EMA_Close × 4
    for n in _EMA_PERIODS:
        cols.append(f"EMA_Close_{n}")
    # DIFF × 12
    for price in _PRICES:
        for n in _EMA_PERIODS:
            cols.append(f"DIFF_{price}_{n}")
    return cols


DATA_COLS: list[str] = _build_data_cols()

# Expanding stats 적용 컬럼 (rolling 일봉 OHLC 제외) — gap-fix 01-14
_EXPANDING_COLS: list[str] = [
    "Close_week",
    "High_week",
    "Low_week",
    "Close_pct_change",
    "Close_pct_change_week",
    "Volume_pct_change",
    "Volume_pct_change_week",
] + [f"EMA_Close_{n}" for n in _EMA_PERIODS] + [
    f"DIFF_{price}_{n}" for price in _PRICES for n in _EMA_PERIODS
]


def run(
    tickers_path: str | Path = "tickers.txt",
    env_path: str | Path | None = None,
    output_dir: str | Path = "output",
) -> Path:
    """Walking Skeleton 전체 흐름 실행 (gap-fix 01-14)."""
    load_env(env_path)

    tickers = read_tickers(tickers_path)
    logger.info("main | 티커 %d개 로드 완료: %s", len(tickers), ", ".join(tickers))

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"portfolio_{date.today():%Y%m%d}.xlsx"

    wb, formats = make_workbook(output_path)

    try:
        for ticker in tickers:
            logger.info("%s | OHLCV 수신 시작", ticker)
            raw = fetch_ohlcv(ticker)

            # 1. 일봉 pct_change
            df = add_pct_change_columns(raw)

            # 2. 주봉 OHLC (ffill) — daily index에 broadcast
            weekly = compute_weekly(raw)
            df = pd.concat([df, weekly], axis=1)

            # 3. 주봉 pct_change (broadcast된 컬럼에서 — Friday-to-Friday 차이만 non-zero)
            df["Close_pct_change_week"] = df["Close_week"].pct_change()
            df["Volume_pct_change_week"] = df["Volume_week"].pct_change()

            # 4. EMA + DIFF + trend (일봉 only)
            df = add_ema_columns(df)
            logger.info("%s | EMA/DIFF/추세 계산 완료", ticker)

            # 5. MACD-OSC 일/주 + .diff()
            df["MACD_OSC"] = compute_macd_oscillator(df["Close"])
            df["MACD_OSC_week"] = compute_macd_oscillator(df["Close_week"])
            df["MACD_OSC_diff"] = df["MACD_OSC"].diff()
            df["MACD_OSC_week_diff"] = df["MACD_OSC_week"].diff()

            # 6. Stoch / RSI 일/주
            stoch = stoch_slow(df)
            df["Stoch_%K"] = stoch["Stoch_%K"]
            df["Stoch_%D"] = stoch["Stoch_%D"]
            # 주봉 Stoch (Close_week/High_week/Low_week 입력)
            weekly_input = pd.DataFrame(
                {
                    "Close": df["Close_week"],
                    "High": df["High_week"],
                    "Low": df["Low_week"],
                },
                index=df.index,
            )
            stoch_w = stoch_slow(weekly_input)
            df["Stoch_%K_week"] = stoch_w["Stoch_%K"]
            df["Stoch_%D_week"] = stoch_w["Stoch_%D"]
            df["RSI"] = rsi_wilder(df)
            df["RSI_week"] = rsi_wilder(pd.DataFrame({"Close": df["Close_week"]}, index=df.index))
            logger.info("%s | Stoch/RSI/MACD 계산 완료", ticker)

            # 7. rolling stats (일봉 OHLC 200일)
            df = add_rolling_stats(df, _DAILY_OHLC, window=200)

            # 8. expanding stats (그 외)
            df = add_expanding_stats(df, _EXPANDING_COLS)

            # 9. impulse
            df = add_impulse_columns(df)

            # 10. 스칼라 (3·4행) — DATA_COLS 전체
            # 일봉 OHLC는 rolling이라 .iloc[-1] (최신 200일 rolling med/std) 사용
            scalars: dict[str, dict[str, float]] = {}
            for col in DATA_COLS:
                if col in _DAILY_OHLC:
                    med_series = df[f"{col}_median"]
                    std_series = df[f"{col}_std"]
                    med = med_series.dropna().iloc[-1] if med_series.dropna().size else None
                    std = std_series.dropna().iloc[-1] if std_series.dropna().size else None
                    scalars[col] = {
                        "median": float(med) if med is not None else None,
                        "std": float(std) if std is not None else None,
                    }
                elif col in df.columns:
                    s = df[col].dropna()
                    if s.size:
                        scalars[col] = {
                            "median": float(s.median()),
                            "std": float(s.std()),
                        }

            # 11. 시트 작성
            write_sheet_for_ticker(wb, formats, ticker, df, scalars)
            logger.info("%s | 시트 작성 완료", ticker)
    finally:
        wb.close()

    logger.info("main | 워크북 저장: %s", output_path)
    return output_path
