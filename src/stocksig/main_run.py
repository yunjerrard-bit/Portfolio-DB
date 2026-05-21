"""Walking Skeleton 오케스트레이션 (EXEC-01/02).

Wave 1~3의 모든 공개 시그니처를 한 흐름으로 연결하는 `run()`.

흐름:
    load_env → read_tickers → 티커별 [fetch_ohlcv → add_ema_columns →
    add_expanding_stats → cumulative_scalars → stoch_slow + rsi_wilder →
    write_sheet_for_ticker] → wb.close() → 출력 경로 반환

D-05 로깅 포맷: [LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지
main_run 모듈에서는 단계 시작 시 TICKER 자리에 `main`을, 티커별 로그에는
실제 ticker 심볼을 사용한다.
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from stocksig.compute.ema import add_ema_columns
from stocksig.compute.indicators import rsi_wilder, stoch_slow
from stocksig.compute.stats import add_expanding_stats, cumulative_scalars
from stocksig.config import load_env
from stocksig.io.input import read_tickers
from stocksig.io.market import fetch_ohlcv
from stocksig.output.sheet_per_ticker import write_sheet_for_ticker
from stocksig.output.writer import make_workbook

logger = logging.getLogger(__name__)

# --- D-03 데이터 컬럼 (40개) — expanding stats 대상 ---------------------------
# 4 OHLCV(Open 제외): Close, High, Low, Volume
# 12 EMA + 12 DIFF + 12 dailychg = 36
# 총 40
_OHLCV_DATA: list[str] = ["Close", "High", "Low", "Volume"]
_PRICES: list[str] = ["Close", "High", "Low"]
_EMA_PERIODS: list[int] = [11, 22, 96, 192]


def _build_data_cols() -> list[str]:
    cols: list[str] = list(_OHLCV_DATA)
    for price in _PRICES:
        for n in _EMA_PERIODS:
            cols.append(f"EMA_{price}_{n}")
    for price in _PRICES:
        for n in _EMA_PERIODS:
            cols.append(f"DIFF_{price}_{n}")
    for price in _PRICES:
        for n in _EMA_PERIODS:
            cols.append(f"EMA_{price}_{n}_dailychg")
    return cols


DATA_COLS: list[str] = _build_data_cols()
assert len(DATA_COLS) == 40, f"DATA_COLS는 40 컬럼이어야 한다 (현재: {len(DATA_COLS)})"


def run(
    tickers_path: str | Path = "tickers.txt",
    env_path: str | Path | None = None,
    output_dir: str | Path = "output",
) -> Path:
    """Walking Skeleton 전체 흐름 실행.

    Args:
        tickers_path: tickers.txt 경로.
        env_path: .env 경로. None이면 cwd의 .env.
        output_dir: 출력 디렉터리. 자동 생성.

    Returns:
        생성된 .xlsx 파일의 절대 경로.

    Raises:
        SystemExit: 입력/환경 검증 실패 (read_tickers / load_env에서).
        ValueError: yfinance 빈 응답.
        YFRateLimitError: 5회 재시도 후에도 rate-limited.
    """
    # 1. .env fail-fast (INPUT-05)
    load_env(env_path)

    # 2. 티커 목록 (INPUT-01/02/03)
    tickers = read_tickers(tickers_path)
    logger.info("main | 티커 %d개 로드 완료: %s", len(tickers), ", ".join(tickers))

    # 3. 출력 경로 (OUT-01/02): 같은 날 재실행 시 overwrite
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    output_path = out_dir / f"portfolio_{date.today():%Y%m%d}.xlsx"

    # 4. Workbook + Format 캐시 (Pattern 8)
    wb, formats = make_workbook(output_path)

    try:
        for ticker in tickers:
            logger.info("%s | OHLCV 수신 시작", ticker)
            df = fetch_ohlcv(ticker)  # MKTD-01~03 (내부에서 수신완료 로그)

            # 5. EMA + DIFF + dailychg (36 컬럼) (COMP-01/02/03)
            df = add_ema_columns(df)
            logger.info("%s | EMA/DIFF/일변동 계산 완료", ticker)

            # 6. expanding median/std (COMP-04)
            df = add_expanding_stats(df, DATA_COLS)

            # 7. 누적 스칼라 (3행/4행용) (COMP-05)
            scalars = cumulative_scalars(df, DATA_COLS)

            # 8. 기술 지표 (TECH-01/02)
            stoch = stoch_slow(df)
            df["Stoch_%K"] = stoch["Stoch_%K"]
            df["Stoch_%D"] = stoch["Stoch_%D"]
            df["RSI"] = rsi_wilder(df)
            logger.info("%s | Stoch/RSI 계산 완료", ticker)

            # 9. 시트 작성 (SHEET-01~08, 정적 색 베이킹)
            write_sheet_for_ticker(wb, formats, ticker, df, scalars)
            logger.info("%s | 시트 작성 완료", ticker)
    finally:
        # T-01-EXC mitigation: 단일 티커 실패여도 부분 워크북 디스크 저장
        wb.close()

    logger.info("main | 워크북 저장: %s", output_path)
    return output_path
