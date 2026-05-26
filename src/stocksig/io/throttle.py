"""Yahoo Finance 호출 throttle (토큰 버킷, 2 req/s).

`pyrate_limiter`의 `Limiter`를 모듈 싱글톤으로 보유하고 `@throttled_yahoo`
데코레이터로 함수 호출 빈도를 초당 2회 이하로 제한. 호출자는 토큰을
획득할 때까지 차단(block)된다. D-04 결정에 따른 보수적 레이트.

Phase 3에서 EDGAR(10 RPS)/DART(별도 한도)용 limiter가 추가될 예정.
"""
from __future__ import annotations

from functools import wraps

from pyrate_limiter import Duration, Limiter, Rate

_YAHOO_RATE = Rate(2, Duration.SECOND)
_yahoo_limiter = Limiter(_YAHOO_RATE)


def throttled_yahoo(fn):
    """함수가 Yahoo Finance를 호출하기 전에 토큰을 획득(필요시 대기)."""

    @wraps(fn)
    def wrapper(*args, **kwargs):
        _yahoo_limiter.try_acquire("yahoo")
        return fn(*args, **kwargs)

    return wrapper
