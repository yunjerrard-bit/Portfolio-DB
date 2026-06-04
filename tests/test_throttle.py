"""io.throttle 단위 테스트."""
from __future__ import annotations

import time

from stocksig.io.throttle import throttled_dart, throttled_edgar, throttled_yahoo


def test_decorator_preserves_return():
    @throttled_yahoo
    def fn(x, y):
        return x + y

    assert fn(2, 3) == 5


def test_edgar_decorator_preserves_return_and_acquires(mocker):
    spy = mocker.patch("stocksig.io.throttle._edgar_limiter.try_acquire")

    @throttled_edgar
    def fn(x, y):
        return x * y

    assert fn(4, 5) == 20
    spy.assert_called_once_with("edgar")


def test_edgar_decorator_preserves_signature():
    @throttled_edgar
    def fetch_facts():
        return "ok"

    assert fetch_facts.__name__ == "fetch_facts"


def test_dart_decorator_preserves_return_and_acquires(mocker):
    spy = mocker.patch("stocksig.io.throttle._dart_limiter.try_acquire")

    @throttled_dart
    def fn(x, y):
        return x - y

    assert fn(9, 4) == 5
    spy.assert_called_once_with("dart")


def test_dart_decorator_preserves_signature():
    @throttled_dart
    def fetch_finstate():
        return "ok"

    assert fetch_finstate.__name__ == "fetch_finstate"


def test_decorator_preserves_signature():
    @throttled_yahoo
    def fetch_ohlcv():
        return "ok"

    assert fetch_ohlcv.__name__ == "fetch_ohlcv"


def test_yahoo_2rps():
    @throttled_yahoo
    def noop():
        return None

    start = time.monotonic()
    for _ in range(10):
        noop()
    elapsed = time.monotonic() - start
    # 10 calls @ 2 RPS ≈ 4.5s; allow slow-CI floor of 4.0s per plan
    assert elapsed >= 4.0, f"throttle too fast: {elapsed:.2f}s"
