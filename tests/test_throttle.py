"""io.throttle 단위 테스트."""
from __future__ import annotations

import time

from stocksig.io.throttle import throttled_yahoo


def test_decorator_preserves_return():
    @throttled_yahoo
    def fn(x, y):
        return x + y

    assert fn(2, 3) == 5


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
