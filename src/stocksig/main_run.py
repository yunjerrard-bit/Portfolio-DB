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
    ema_week_to_date,
    macd_oscillator_week_to_date,
    rsi_week_to_date,
    rsi_wilder,
    stoch_slow,
    stoch_slow_week_to_date,
)
from stocksig.compute.stats import (
    add_expanding_stats,
    add_pct_change_columns,
    add_rolling_stats,
)
from stocksig.compute.weekly import (
    compute_weekly,
    week_close_mask,
    week_to_date_close_return,
)
from stocksig.config import load_env
from stocksig.io import cache, naver_scraper
from stocksig.io.auth_check import AuthStatus, ping_dart, ping_edgar
from stocksig.io.fundamentals import fetch_fundamentals
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

# 주봉 등락률(Close/Volume)은 '금요일값만'으로 통계를 내야 하므로 expanding 대상에서
# 제외하고, _compute_enriched에서 별도로 금요일 기준 통계를 계산한다.
_WEEKLY_FRIDAY_STAT_COLS: list[str] = [
    "Close_pct_change_week",
    "Volume_pct_change_week",
]

_EXPANDING_COLS: list[str] = [
    "Close_week",
    "High_week",
    "Low_week",
    "Close_pct_change",
    "Volume_pct_change",
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

    # 주봉 종가 등락률 (W열) — week-to-date 누적 수익률 (월=월, …, 금=주간 전체).
    df["Close_pct_change_week"] = week_to_date_close_return(df["Close"])
    # 주봉 거래량 등락률 (AE열) — 현행 유지: 주간 총거래량 pct_change (월~목 0, 금=주간 변화).
    df["Volume_pct_change_week"] = df["Volume_week"].pct_change()

    df = add_ema_columns(df)

    df["MACD_OSC"] = compute_macd_oscillator(df["Close"])
    # 주봉 MACD-OSC (CO열) — week-to-date: 금요일=진짜 주봉 MACD, 주중=오늘 종가 반영.
    df["MACD_OSC_week"] = macd_oscillator_week_to_date(df["Close"])
    df["MACD_OSC_diff"] = df["MACD_OSC"].diff()
    df["MACD_OSC_week_diff"] = df["MACD_OSC_week"].diff()

    stoch = stoch_slow(df)
    df["Stoch_%K"] = stoch["Stoch_%K"]
    df["Stoch_%D"] = stoch["Stoch_%D"]
    # 주봉 Stoch %K/%D (CJ/CK열) — week-to-date: 금요일=진짜 주봉, 주중=이번 주 누적 고저/오늘 종가.
    stoch_w = stoch_slow_week_to_date(df["High"], df["Low"], df["Close"])
    df["Stoch_%K_week"] = stoch_w["Stoch_%K"]
    df["Stoch_%D_week"] = stoch_w["Stoch_%D"]
    df["RSI"] = rsi_wilder(df)
    # 주봉 RSI (CM열) — 진행 중인 주의 종가를 '오늘 일봉 종가'로 갱신 (week-to-date).
    df["RSI_week"] = rsi_week_to_date(df["Close"])

    # 주봉 EMA 진행형 추세 (AK·AL열) — 일봉 AK/AO 추세 컬럼의 주봉 대응.
    # 금요일=진짜 주봉 EMA의 pct_change, 주중=오늘 종가가 α=2/(N+1)만큼 반영.
    # 주봉 임펄스의 EMA 입력으로도 사용된다 (impulse.py 가 이 컬럼을 읽음).
    df["EMA_Close_11_week_trend"] = ema_week_to_date(df["Close"], span=11).pct_change()
    df["EMA_Close_22_week_trend"] = ema_week_to_date(df["Close"], span=22).pct_change()

    df = add_rolling_stats(df, _DAILY_OHLC, window=200)
    df = add_expanding_stats(df, _EXPANDING_COLS)

    # 주봉 등락률 통계는 '완성된 주(금요일)' 값만으로 계산 — 월~목 값(0 또는 진행형)이
    # 중앙값/표준편차를 오염시키지 않도록 한다. 일봉 인덱스로 ffill broadcast.
    week_mask = week_close_mask(df.index)
    for col in _WEEKLY_FRIDAY_STAT_COLS:
        fri = df.loc[week_mask, col]
        df[f"{col}_median"] = (
            fri.expanding().median().reindex(df.index, method="ffill")
        )
        df[f"{col}_std"] = (
            fri.expanding().std().reindex(df.index, method="ffill")
        )

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
        elif col in _WEEKLY_FRIDAY_STAT_COLS:
            # 행 3·4 스칼라도 금요일값만 기준 (위 통계와 동일 정책).
            fri = df.loc[week_mask, col].dropna()
            if fri.size:
                scalars[col] = {
                    "median": float(fri.median()),
                    "std": float(fri.std()),
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


def _auth_label(ok: bool | None, note: str | None) -> str:
    """인증 상태 라벨 — 요약 인증 줄 출력용.

    None(ping 미실행) → "해당없음", True → "OK", False → "실패(<note>)".
    note 는 auth_check 에서 이미 키/UA 미포함 고정 사유이므로 그대로 출력해도
    안전하다 (T-04-04 — API 키·UA 원문 미노출).
    """
    if ok is None:
        return "해당없음"
    if ok:
        return "OK"
    return f"실패({note})" if note else "실패"


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

    # D-07: run 시작마다 네이버 폴백 카운터 초기화 (다회 실행/장수 프로세스 안전).
    naver_scraper.reset_naver_count()
    # EXEC-04: run 시작마다 캐시 hit/miss 카운터 초기화 (다회 실행 누적 방지).
    cache.reset_cache_stats()

    specs = read_tickers_extended(tickers_path)
    logger.info("main | 티커 %d개 로드 완료", len(specs))

    # EXEC-04: 실행 시작 시 조건부 인증 사전검증 (D-04 — 해당 시장 티커 있을 때만 1회씩).
    # ping 은 raise하지 않고 (ok, 키/UA 미포함 사유) 만 반환한다(D-02 fail-fast 아님).
    markets = {classify_market(s.symbol) for s in specs}
    auth = AuthStatus()
    if "US" in markets:
        auth.edgar_ok, auth.edgar_note = ping_edgar()
    if "KR" in markets:
        auth.dart_ok, auth.dart_note = ping_dart()

    # PASS 1b: 인증 실패 소스의 1차 펀더멘털 호출만 스킵하는 클로저 주입.
    # yf/Naver 폴백은 독립 소스이므로 유지된다(A4 확정).
    def _fundamentals_with_auth(ticker, market, last_close):
        return fetch_fundamentals(
            ticker,
            market,
            last_close,
            skip_edgar=(market == "US" and auth.edgar_ok is False),
            skip_dart=(market == "KR" and auth.dart_ok is False),
        )

    # PASS 1 — fan-out (+ PASS 1b: 인증 배선된 펀더멘털 클로저 주입)
    pipeline = _make_pipeline()
    results, failures = run_all(
        specs, classify_market, pipeline, fundamentals_fn=_fundamentals_with_auth
    )

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

    # EXEC-04 / 로드맵 SC3 — 한국어 최종 실행 요약 블록 (콘솔/로그파일).
    # 카운트(정수)·티커 심볼만 출력 (T-04-01: API 키·예외 원문 미포함).
    stats = cache.get_cache_stats()
    logger.info("════════ 실행 요약 ════════")
    logger.info(
        "티커: 총 %d / 성공 %d / 실패 %d", len(specs), len(results), len(failures)
    )
    # 인증 상태 줄 (EXEC-04) — note 는 auth_check 에서 이미 키/UA 미포함 고정 사유
    # 이므로 _auth_label 이 그대로 출력해도 안전(T-04-04 보안).
    logger.info(
        "인증: EDGAR %s | DART %s",
        _auth_label(auth.edgar_ok, auth.edgar_note),
        _auth_label(auth.dart_ok, auth.dart_note),
    )
    logger.info(
        "캐시: OHLCV HIT %d/MISS %d · 펀더멘털 HIT %d/MISS %d",
        stats["ohlcv_hit"],
        stats["ohlcv_miss"],
        stats["fund_hit"],
        stats["fund_miss"],
    )
    if failures:
        logger.info(
            "실패 티커: %s", ", ".join(f.spec.symbol for f in failures)
        )
    return output_path
