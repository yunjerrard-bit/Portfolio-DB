"""Phase 2 Wave 4: 2-pass 멀티 티커 오케스트레이션 (EXEC-03/05, PORT-01/02/08).

PASS 1 (fan-out): `read_tickers_extended` → `_make_pipeline()` → `run_all`
  - 각 워커가 `fetch_ohlcv_cached` + `_compute_enriched` 합성을 실행.
  - per-ticker 예외는 `runner` 가 `TickerFailure`로 격리.

PASS 2 (write): xlsxwriter Workbook 한 번 열어
  1. `write_portfolio_sheet` (시트1) FIRST — `sheetnames[0] == "시트1"` 보장 (PORT-01).
  2. 입력 순서대로 성공 티커 각각에 `write_sheet_for_ticker` (Phase 1 unchanged).

Korean console logging: 티커 로드, run_all 진행, 워크북 저장, 실패 요약.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Callable

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
)
from stocksig.compute.weekly import compute_weekly
from stocksig.config import load_env
from stocksig.io.input import read_tickers_extended
from stocksig.io.market import fetch_ohlcv_cached
from stocksig.io.market_kind import classify_market
from stocksig.output.sheet_per_ticker import write_sheet_for_ticker
from stocksig.output.sheet_portfolio import write_portfolio_sheet
from stocksig.output.writer import make_workbook
from stocksig.runner import run_all

logger = logging.getLogger(__name__)


_DAILY_OHLC: list[str] = ["Close", "High", "Low"]
_PRICES: list[str] = ["Close", "High", "Low"]
_EMA_PERIODS: list[int] = [11, 22, 96, 192]


def _build_data_cols() -> list[str]:
    """SCALARS 용 컬럼 list (3·4행 + sigma 계산 대상)."""
    cols: list[str] = list(_DAILY_OHLC)
    cols += ["Close_week", "High_week", "Low_week"]
    cols += [
        "Close_pct_change",
        "Close_pct_change_week",
        "Volume_pct_change",
        "Volume_pct_change_week",
    ]
    for n in _EMA_PERIODS:
        cols.append(f"EMA_Close_{n}")
    for price in _PRICES:
        for n in _EMA_PERIODS:
            cols.append(f"DIFF_{price}_{n}")
    return cols


DATA_COLS: list[str] = _build_data_cols()

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


def _compute_enriched(
    raw: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, dict[str, float]]]:
    """Phase 1 per-ticker compute chain — `raw` OHLCV → (enriched_df, scalars).

    Steps (Phase 1 main_run.py:113-182):
      1. add_pct_change_columns (Close/Volume daily)
      2. compute_weekly (W-FRI ffill broadcast) → concat
      3. 주봉 pct_change 컬럼 (broadcast된 컬럼에서)
      4. add_ema_columns (일봉 only)
      5. compute_macd_oscillator (일/주) + .diff() 사본
      6. stoch_slow / rsi_wilder (일/주)
      7. add_rolling_stats(_DAILY_OHLC, 200)
      8. add_expanding_stats(_EXPANDING_COLS)
      9. add_impulse_columns
     10. scalars (3·4행) — DATA_COLS 전체.
    """
    df = add_pct_change_columns(raw)

    weekly = compute_weekly(raw)
    df = pd.concat([df, weekly], axis=1)

    df["Close_pct_change_week"] = df["Close_week"].pct_change()
    df["Volume_pct_change_week"] = df["Volume_week"].pct_change()

    df = add_ema_columns(df)

    df["MACD_OSC"] = compute_macd_oscillator(df["Close"])
    df["MACD_OSC_week"] = compute_macd_oscillator(df["Close_week"])
    df["MACD_OSC_diff"] = df["MACD_OSC"].diff()
    df["MACD_OSC_week_diff"] = df["MACD_OSC_week"].diff()

    stoch = stoch_slow(df)
    df["Stoch_%K"] = stoch["Stoch_%K"]
    df["Stoch_%D"] = stoch["Stoch_%D"]
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
    df["RSI_week"] = rsi_wilder(
        pd.DataFrame({"Close": df["Close_week"]}, index=df.index)
    )

    df = add_rolling_stats(df, _DAILY_OHLC, window=200)
    df = add_expanding_stats(df, _EXPANDING_COLS)
    df = add_impulse_columns(df)

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

    return df, scalars


def _make_pipeline() -> Callable[[str], pd.DataFrame]:
    """`symbol → enriched DataFrame` 합성 — runner.run_all 용 fan-out 클로저.

    scalars dict는 `df.attrs["scalars"]`로 stash해 PASS 2가 재계산 없이 쓴다.
    pandas 2.x `attrs`는 indexing/concat을 통과해 보존된다 (T-02-12 mitigation).
    """

    def pipeline(symbol: str) -> pd.DataFrame:
        raw = fetch_ohlcv_cached(symbol)
        enriched, scalars = _compute_enriched(raw)
        enriched.attrs["scalars"] = scalars
        return enriched

    return pipeline


def run(
    tickers_path: str | Path = "tickers.txt",
    env_path: str | Path | None = None,
    output_dir: str | Path = "output",
    summary_only: bool = False,
) -> Path:
    """2-pass 멀티 티커 오케스트레이션 — PORT-01 시트1 first.

    PASS 1: parallel fetch+compute via `runner.run_all`.
    PASS 2: write 시트1 then per-ticker sheets in input order.

    summary_only=True 이면 시트1만 작성하고 종목별 시트는 생략 (빠른 통합 보기용).
    """
    load_env(env_path)

    specs = read_tickers_extended(tickers_path)
    logger.info("main | 티커 %d개 로드 완료", len(specs))

    # PASS 1 — fan-out
    pipeline = _make_pipeline()
    results, failures = run_all(specs, classify_market, pipeline)

    # PASS 2 — write
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"portfolio_{date.today():%Y%m%d}.xlsx"

    wb, formats = make_workbook(output_path)
    input_order = [s.symbol for s in specs]

    try:
        # ★ 시트1 FIRST (PORT-01 / RESEARCH L-05)
        write_portfolio_sheet(wb, formats, results, failures, input_order)

        if summary_only:
            logger.info("main | summary_only 모드 — 종목별 시트 생략")
        else:
            # 입력 순서로 각 티커 시트
            by_symbol = {r.spec.symbol: r for r in results}
            for sym in input_order:
                res = by_symbol.get(sym)
                if res is None:
                    continue
                scalars = res.enriched_df.attrs.get("scalars", {})
                write_sheet_for_ticker(
                    wb, formats, res.spec.symbol, res.enriched_df, scalars
                )
                logger.info("%s | 시트 작성 완료", res.spec.symbol)
    finally:
        wb.close()

    logger.info("main | 워크북 저장: %s", output_path)
    if failures:
        failed_syms = ", ".join(f.spec.symbol for f in failures)
        logger.warning(
            "실패 %d개 — 시트1에 표시됨: %s", len(failures), failed_syms
        )
    return output_path
