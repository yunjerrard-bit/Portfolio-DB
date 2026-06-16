"""OHLCV 디스크 캐시 (24h TTL).

`diskcache.Cache` 기반의 단순 키-값 저장소. 키는 `make_key(ticker, today)`
포맷 `"{TICKER}|{YYYY-MM-DD}"` 이며 값은 임의의 pickle 가능 객체(주로
pandas DataFrame). 만료는 24시간으로 고정. Phase 2 Wave 2의 `io.market`
모듈이 Yahoo Finance 호출 전후로 사용.

Phase 3에서 7일 TTL 펀더멘털 캐시(`.cache/fundamentals`, 키
`"{SOURCE}|{TICKER}|{QUARTER}"`)를 동일 패턴으로 추가(OHLCV와 분리).
"""
from __future__ import annotations

import logging
import threading
from datetime import date
from pathlib import Path
from typing import Optional

from diskcache import Cache

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(".cache/ohlcv")
_TTL_SECONDS = 24 * 60 * 60

_cache: Optional[Cache] = None

# --- hit/miss 집계 카운터 (EXEC-04) -------------------------------------
# 모듈 레벨 카운터 + lock. run 시작 시 reset_cache_stats() 로 초기화하고,
# 종료부 요약 블록에서 get_cache_stats() 로 스냅샷을 읽는다.
# read-modify-write `+=` 는 ThreadPoolExecutor fan-out(runner) 하에서
# lost-update 가능 → _stats_lock 으로 보호 (Pitfall 3).
_stats: dict[str, int] = {
    "ohlcv_hit": 0,
    "ohlcv_miss": 0,
    "fund_hit": 0,
    "fund_miss": 0,
    # 06-01 (COMPANY-04): 기업명 캐시 hit/miss. reset_cache_stats 가 자동 초기화 (for k in _stats).
    "name_hit": 0,
    "name_miss": 0,
}
_stats_lock = threading.Lock()


def reset_cache_stats() -> None:
    """run 시작 시 캐시 hit/miss 카운터 초기화 (EXEC-04)."""
    with _stats_lock:
        for k in _stats:
            _stats[k] = 0


def get_cache_stats() -> dict[str, int]:
    """현재 hit/miss 카운터의 *복사본* 반환 (반환값 변형이 내부 상태를 오염시키지 않음)."""
    with _stats_lock:
        return dict(_stats)


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
        with _stats_lock:
            _stats["ohlcv_hit"] += 1
    else:
        logger.info("%s | 캐시 MISS (cache MISS, key=%s)", ticker, key)
        with _stats_lock:
            _stats["ohlcv_miss"] += 1
    return value


def put_ohlcv(ticker: str, df) -> None:
    """캐시 저장. 만료 24시간."""
    key = make_key(ticker)
    _get_cache().set(key, df, expire=_TTL_SECONDS)


# --- 펀더멘털 캐시 (7일 TTL, OHLCV와 분리) -------------------------------

_FUND_DIR = Path(".cache/fundamentals")
_FUND_TTL_SECONDS = 7 * 24 * 60 * 60

_fund_cache: Optional[Cache] = None


def _get_fund_cache() -> Cache:
    global _fund_cache
    if _fund_cache is None:
        _FUND_DIR.mkdir(parents=True, exist_ok=True)
        _fund_cache = Cache(str(_FUND_DIR))
    return _fund_cache


def make_fund_key(source: str, ticker: str, quarter_label: str) -> str:
    """펀더멘털 캐시 키: `"{SOURCE}|{TICKER}|{QUARTER}"` (예: ``"EDGAR|AAPL|2026Q3"``)."""
    return f"{source}|{ticker}|{quarter_label}"


def get_fund(source: str, ticker: str, quarter_label: str):
    """펀더멘털 캐시 조회. 히트시 객체 반환, 미스시 None.

    HIT/MISS 로그는 한국어 + 영문 substring(`cache HIT`/`cache MISS`)을 동시 포함.
    """
    key = make_fund_key(source, ticker, quarter_label)
    value = _get_fund_cache().get(key)
    if value is not None:
        logger.info("%s | 펀더멘털 캐시 HIT (cache HIT, key=%s)", ticker, key)
        with _stats_lock:
            _stats["fund_hit"] += 1
    else:
        logger.info("%s | 펀더멘털 캐시 MISS (cache MISS, key=%s)", ticker, key)
        with _stats_lock:
            _stats["fund_miss"] += 1
    return value


def put_fund(source: str, ticker: str, quarter_label: str, value) -> None:
    """펀더멘털 캐시 저장. 만료 7일."""
    key = make_fund_key(source, ticker, quarter_label)
    _get_fund_cache().set(key, value, expire=_FUND_TTL_SECONDS)


# --- 기업명 캐시 (30일 TTL, OHLCV/펀더멘털과 분리) -----------------------
# 06-01 (COMPANY-04): 기업명은 안정적이므로 30일 TTL. 재실행 시 HIT → yfinance 무호출.

_NAME_DIR = Path(".cache/company")
_NAME_TTL_SECONDS = 30 * 24 * 60 * 60

_name_cache: Optional[Cache] = None


def _get_name_cache() -> Cache:
    global _name_cache
    if _name_cache is None:
        _NAME_DIR.mkdir(parents=True, exist_ok=True)
        _name_cache = Cache(str(_NAME_DIR))
    return _name_cache


def make_name_key(ticker: str) -> str:
    """기업명 캐시 키: `"{TICKER}"` (날짜 무관 — 기업명 불변성)."""
    return ticker


def get_company_name(ticker: str):
    """기업명 캐시 조회. 히트시 문자열 반환, 미스시 None.

    HIT/MISS 로그는 한국어 + 영문 substring(`cache HIT`/`cache MISS`)을 동시 포함.
    """
    key = make_name_key(ticker)
    value = _get_name_cache().get(key)
    if value is not None:
        logger.info("%s | 기업명 캐시 HIT (cache HIT, key=%s)", ticker, key)
        with _stats_lock:
            _stats["name_hit"] += 1
    else:
        logger.info("%s | 기업명 캐시 MISS (cache MISS, key=%s)", ticker, key)
        with _stats_lock:
            _stats["name_miss"] += 1
    return value


def put_company_name(ticker: str, name: str) -> None:
    """기업명 캐시 저장. 만료 30일."""
    key = make_name_key(ticker)
    _get_name_cache().set(key, name, expire=_NAME_TTL_SECONDS)
