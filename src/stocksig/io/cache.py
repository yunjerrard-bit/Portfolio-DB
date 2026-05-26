"""OHLCV 디스크 캐시 (24h TTL).

`diskcache.Cache` 기반의 단순 키-값 저장소. 키는 `make_key(ticker, today)`
포맷 `"{TICKER}|{YYYY-MM-DD}"` 이며 값은 임의의 pickle 가능 객체(주로
pandas DataFrame). 만료는 24시간으로 고정. Phase 2 Wave 2의 `io.market`
모듈이 Yahoo Finance 호출 전후로 사용.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Optional

from diskcache import Cache

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(".cache/ohlcv")
_TTL_SECONDS = 24 * 60 * 60

_cache: Optional[Cache] = None


def _get_cache() -> Cache:
    global _cache
    if _cache is None:
        _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
        _cache = Cache(str(_DEFAULT_DIR))
    return _cache


def make_key(ticker: str, today: date | None = None) -> str:
    """캐시 키 생성: `"{TICKER}|{YYYY-MM-DD}"`."""
    d = today or date.today()
    return f"{ticker}|{d.isoformat()}"


def get_ohlcv(ticker: str):
    """캐시 조회. 히트시 객체 반환, 미스시 None.

    HIT/MISS 로그는 한국어 + 영문 substring(`cache HIT`/`cache MISS`)을
    동시에 포함하여 MKTD-05 검증 통과.
    """
    key = make_key(ticker)
    value = _get_cache().get(key)
    if value is not None:
        logger.info("%s | 캐시 HIT (cache HIT, key=%s)", ticker, key)
    else:
        logger.info("%s | 캐시 MISS (cache MISS, key=%s)", ticker, key)
    return value


def put_ohlcv(ticker: str, df) -> None:
    """캐시 저장. 만료 24시간."""
    key = make_key(ticker)
    _get_cache().set(key, df, expire=_TTL_SECONDS)
