"""yfinance OHLCV fetcher with curl_cffi Chrome impersonation + tenacity retries.

D-05 로깅 포맷: [LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지
market 모듈에서는 TICKER 자리에 ticker 심볼을 사용한다.

Pattern source: RESEARCH.md Pattern 2 (curl_cffi session reused at module level,
tenacity retry policy 5 attempts on YFRateLimitError).

Phase 2 Wave 2 (MKTD-04/05):
- `fetch_ohlcv`는 `@throttled_yahoo`로 감싸진다 (decorator stack:
  throttled_yahoo → retry → fetch_ohlcv). 즉 retry attempt마다 토큰 획득.
- `fetch_ohlcv_cached(ticker)` — cache.get_ohlcv 우선, miss시 fetch + put.
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

from stocksig.io import cache
from stocksig.io.throttle import throttled_yahoo

logger = logging.getLogger(__name__)

# 모듈 레벨 단일 인스턴스 (후속 wave에서 별도 session 생성 금지)
_SESSION = curl_requests.Session(impersonate="chrome")

# Phase 1 D-06 결정: today - 4000 calendar days ~ today
_WINDOW_DAYS = 4000


@throttled_yahoo
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
    - throttle: 모든 호출 (재시도 포함)이 2 RPS 토큰 버킷을 통과 (Wave 2)

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

    # 후행 미정산봉 트리밍: Yahoo가 최신 일봉의 Close를 NaN(Volume만)으로 내려주면
    # iloc[-1]이 빈 행을 가리켜 시트1 최신값이 빈칸이 된다. 캐시 저장 이전 단계에서
    # Close=NaN 행을 제거한다. High/Low/Open은 건드리지 않는다(EWM carry-forward 보존).
    original_rows = len(df)
    df = df.dropna(subset=["Close"])
    removed = original_rows - len(df)
    if removed > 0:
        logger.info("%s | 미정산/NaN 최신봉 %d개 제외", ticker, removed)

    if df.empty:
        raise ValueError(f"{ticker} | Close 유효 행이 없습니다 (전 봉 NaN)")

    logger.info("%s | OHLCV %d 거래일 수신 완료", ticker, len(df))
    return df


def fetch_ohlcv_cached(ticker: str) -> pd.DataFrame:
    """캐시 우선 OHLCV 페치 (MKTD-04/05).

    Flow:
        1. `cache.get_ohlcv(ticker)` — 캐시 HIT → 즉시 반환 (yfinance 호출 없음).
        2. MISS → `fetch_ohlcv(ticker)` 호출 (throttle + retry 적용).
        3. 받은 DataFrame을 `cache.put_ohlcv(ticker, df)`로 저장 (24h TTL).
    """
    df = cache.get_ohlcv(ticker)
    if df is not None:
        return df
    df = fetch_ohlcv(ticker)
    cache.put_ohlcv(ticker, df)
    return df
