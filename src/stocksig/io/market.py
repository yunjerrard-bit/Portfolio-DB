"""yfinance OHLCV fetcher with curl_cffi Chrome impersonation + tenacity retries.

D-05 로깅 포맷: [LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지
market 모듈에서는 TICKER 자리에 ticker 심볼을 사용한다.

Pattern source: RESEARCH.md Pattern 2 (curl_cffi session reused at module level,
tenacity retry policy 5 attempts on YFRateLimitError).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import pandas as pd
import yfinance as yf
from curl_cffi import requests as curl_requests
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)
from yfinance.exceptions import YFRateLimitError

logger = logging.getLogger(__name__)

# 모듈 레벨 단일 인스턴스 (후속 wave에서 별도 session 생성 금지)
_SESSION = curl_requests.Session(impersonate="chrome")

# Phase 1 D-06 결정: today - 4000 calendar days ~ today
_WINDOW_DAYS = 4000


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30) + wait_random(0, 1),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(YFRateLimitError),
    reraise=True,
)
def fetch_ohlcv(ticker: str) -> pd.DataFrame:
    """단일 티커의 OHLCV DataFrame을 yfinance로 받아온다.

    - 시간 윈도우: today - 4000 calendar days ~ today
    - auto_adjust=True (D-06)
    - curl_cffi Chrome impersonation session 재사용 (_SESSION)
    - tenacity: YFRateLimitError 시 최대 5회 재시도 (wait_exponential 2~30s + jitter)

    Args:
        ticker: yfinance 심볼 (예: "AAPL", "005930.KS").

    Returns:
        OHLCV DataFrame (columns=[Open, High, Low, Close, Volume]).

    Raises:
        ValueError: 빈 DataFrame 반환 시 (Phase 1 fail-fast — Pitfall B).
        YFRateLimitError: 5회 재시도 후에도 rate-limited (reraise=True).
    """
    today = date.today()
    start = (today - timedelta(days=_WINDOW_DAYS)).isoformat()
    end = today.isoformat()

    df = yf.Ticker(ticker, session=_SESSION).history(
        start=start,
        end=end,
        auto_adjust=True,
    )

    if df is None or df.empty:
        raise ValueError(
            f"{ticker} | yfinance가 빈 OHLCV를 반환했습니다 (티커 확인 필요)."
        )

    logger.info("%s | OHLCV %d 거래일 수신 완료", ticker, len(df))
    return df
