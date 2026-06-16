"""yfinance .info 기업명 조회 — market._SESSION 재사용(신규 세션 금지).

06-01 (COMPANY-01~04): 시트1 B열에 표시할 영문 기업명을 yfinance `.info`
metadata 에서만 조회한다 (DART 미사용, 한국 종목도 영문명). OHLCV/펀더멘털과
동일 경로·세션·throttle 정책을 따른다:
  - market._SESSION 재사용 (신규 TLS 세션 생성 금지 — Anti-Pattern).
  - `@throttled_yahoo` (2 RPS limiter) + `@retry`(YFRateLimitError 5회).
  - 30일 캐시(cache.get/put_company_name) — 재실행 시 HIT → 무호출 (COMPANY-04).

폴백 체인(Q1/Q3 확정): longName → shortName → 티커.
  longName 1순위(영문 정식명). shortName 은 KR 쓰레기값(.KS 등) 가능하므로
  longName 결손 시 차선책. 둘 다 결손 → 티커 폴백 (행 무손상, COMPANY-03).

예외 처리(Pitfall 4 / T-06-02): fetch 경로의 모든 예외(YFRateLimitError 포함)는
흡수하고 티커 폴백을 반환한다 — 기업명 결손 ≠ 티커 실패. 예외 로그는
`type(e).__name__` 만 노출(runner.py:100 패턴) — URL/키/UA 원문 미노출.
폴백값은 캐시에 put 하지 않는다 (다음 실행 재시도 허용).
"""

from __future__ import annotations

import logging

import yfinance as yf
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)
from yfinance.exceptions import YFRateLimitError

from stocksig.io import cache
from stocksig.io.market import _SESSION  # 재사용 — 신규 세션 생성 금지
from stocksig.io.throttle import throttled_yahoo  # 기존 2 RPS 재사용

logger = logging.getLogger(__name__)


def _pick_name(info: dict, ticker: str) -> str:
    """폴백 체인: longName → shortName → 티커 (longName 우선)."""
    return info.get("longName") or info.get("shortName") or ticker


@throttled_yahoo
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=30) + wait_random(0, 1),
    stop=stop_after_attempt(5),
    retry=retry_if_exception_type(YFRateLimitError),
    reraise=True,
)
def _fetch_info_with_retry(ticker: str) -> dict:
    """`yf.Ticker(ticker, session=_SESSION).info` 1회 왕복 (throttle + retry).

    market.fetch_ohlcv 와 동일한 데코레이터 스택(throttled_yahoo outer → retry inner):
    YFRateLimitError 시 최대 5회 재시도(wait_exponential 2~30s + jitter), 각 attempt 마다
    토큰 획득. 5회 후에도 rate-limited 면 reraise=True 로 예외 전파 → 호출부가 흡수.
    """
    return yf.Ticker(ticker, session=_SESSION).info or {}


def fetch_company_name(ticker: str) -> str:
    """티커의 영문 기업명을 캐시 우선으로 조회 (COMPANY-01~04).

    Flow:
        1. `cache.get_company_name(ticker)` HIT → 즉시 반환 (yfinance 왕복 0).
        2. MISS → `_fetch_info_with_retry` → `_pick_name` → `put_company_name` 후 반환.
        3. fetch 경로 예외(YFRateLimitError 포함) → 흡수 + 티커 폴백 (캐시 put 안 함).

    Returns:
        영문 기업명(longName→shortName) 또는 결손/예외 시 티커 폴백 (항상 non-empty).
    """
    cached = cache.get_company_name(ticker)
    if cached is not None:
        return cached

    try:
        info = _fetch_info_with_retry(ticker)
        name = _pick_name(info, ticker)
    except Exception as e:  # noqa: BLE001 — 결손 ≠ 실패 (Pitfall 4)
        # T-06-02: 예외 원문 보간 금지 (URL/키/UA 누설 차단) — 타입명만.
        logger.warning("%s | 기업명 조회 예외 흡수: %s", ticker, type(e).__name__)
        return ticker  # 폴백값은 캐시에 put 하지 않는다 (다음 실행 재시도 허용).

    cache.put_company_name(ticker, name)
    return name
