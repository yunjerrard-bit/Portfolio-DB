"""MKTD-01/02/03 GREEN tests (no network — mock yf.Ticker).

Phase 2 Wave 2 (MKTD-04/05): adds fetch_ohlcv_cached cache+throttle tests.
"""

from __future__ import annotations

import time
from datetime import date, timedelta

import pandas as pd
import pytest
from diskcache import Cache
from tenacity import wait_none
from yfinance.exceptions import YFRateLimitError

from stocksig.io import cache as cache_mod
from stocksig.io import market
from stocksig.io.market import fetch_ohlcv, fetch_ohlcv_cached


@pytest.fixture(autouse=True)
def _no_retry_wait():
    """tenacity wait을 0으로 override — 5회 retry 테스트가 ~60s 걸리지 않도록."""
    original = fetch_ohlcv.retry.wait
    fetch_ohlcv.retry.wait = wait_none()
    yield
    fetch_ohlcv.retry.wait = original


def test_fetch_ohlcv_date_window(mocker, mock_ohlcv_df):
    # MKTD-01: history called with start=today-4000d, end=today, auto_adjust=True
    mock_ticker_cls = mocker.patch("stocksig.io.market.yf.Ticker")
    mock_ticker_cls.return_value.history.return_value = mock_ohlcv_df

    df = fetch_ohlcv("AAPL")

    assert isinstance(df, pd.DataFrame)
    assert not df.empty
    # Ticker(ticker="AAPL", session=_SESSION) — positional or kw both accepted
    call_args = mock_ticker_cls.call_args
    assert "AAPL" in call_args.args or call_args.kwargs.get("ticker") == "AAPL"
    assert call_args.kwargs.get("session") is market._SESSION

    history_kwargs = mock_ticker_cls.return_value.history.call_args.kwargs
    today = date.today()
    expected_start = (today - timedelta(days=4000)).isoformat()
    expected_end = today.isoformat()
    assert history_kwargs["start"] == expected_start
    assert history_kwargs["end"] == expected_end
    assert history_kwargs["auto_adjust"] is True


def test_uses_curl_cffi_session():
    # MKTD-02: _SESSION is a curl_cffi.requests.Session, impersonate="chrome"
    from curl_cffi.requests import Session as CurlSession

    assert isinstance(market._SESSION, CurlSession)
    # curl_cffi exposes impersonate on Session instances
    assert getattr(market._SESSION, "impersonate", None) == "chrome"


def test_retries_on_rate_limit(mocker, mock_ohlcv_df):
    # MKTD-03 success path: 2 rate-limit errors then success — DataFrame returned
    mock_ticker_cls = mocker.patch("stocksig.io.market.yf.Ticker")
    mock_ticker_cls.return_value.history.side_effect = [
        YFRateLimitError(),
        YFRateLimitError(),
        mock_ohlcv_df,
    ]

    df = fetch_ohlcv("AAPL")

    assert isinstance(df, pd.DataFrame)
    assert mock_ticker_cls.return_value.history.call_count == 3


def test_retries_exhausted_reraises(mocker):
    # MKTD-03 failure path: 5 rate-limit errors -> YFRateLimitError reraised
    mock_ticker_cls = mocker.patch("stocksig.io.market.yf.Ticker")
    mock_ticker_cls.return_value.history.side_effect = [YFRateLimitError()] * 5

    with pytest.raises(YFRateLimitError):
        fetch_ohlcv("AAPL")
    assert mock_ticker_cls.return_value.history.call_count == 5


def test_empty_dataframe_raises_value_error(mocker):
    # Pitfall B: empty DataFrame -> ValueError fail-fast
    mock_ticker_cls = mocker.patch("stocksig.io.market.yf.Ticker")
    mock_ticker_cls.return_value.history.return_value = pd.DataFrame()

    with pytest.raises(ValueError, match="AAPL"):
        fetch_ohlcv("AAPL")


@pytest.fixture
def _tmp_cache(tmp_path, monkeypatch):
    """Redirect cache._get_cache to a tmp_path-backed diskcache."""
    tmp_dir = tmp_path / "ohlcv_cache"
    tmp_dir.mkdir()
    new_cache = Cache(str(tmp_dir))
    monkeypatch.setattr(cache_mod, "_cache", new_cache)
    monkeypatch.setattr(cache_mod, "_get_cache", lambda: new_cache)
    yield new_cache
    new_cache.close()


def test_cache_miss_calls_fetch(mocker, mock_ohlcv_df, _tmp_cache):
    # MKTD-04: 1st call → fetch invoked once and result cached.
    stub = mocker.patch(
        "stocksig.io.market.fetch_ohlcv", return_value=mock_ohlcv_df
    )
    df = fetch_ohlcv_cached("AAPL")
    assert stub.call_count == 1
    assert isinstance(df, pd.DataFrame)
    # cache populated
    assert cache_mod.get_ohlcv("AAPL") is not None


def test_cache_hit_skips_fetch(mocker, mock_ohlcv_df, _tmp_cache):
    # MKTD-05: 2nd same-day call hits cache, fetch NOT invoked again.
    stub = mocker.patch(
        "stocksig.io.market.fetch_ohlcv", return_value=mock_ohlcv_df
    )
    df1 = fetch_ohlcv_cached("AAPL")
    df2 = fetch_ohlcv_cached("AAPL")
    assert stub.call_count == 1  # cache hit on 2nd call
    pd.testing.assert_frame_equal(df1, df2)


def test_throttle_applied_to_fetch(mocker, _tmp_cache):
    # D-04: 10 cache-MISS calls → token bucket enforces ≥4.5s wall-clock at 2 RPS.
    # Use distinct tickers so cache never hits; stub the underlying fetch_ohlcv
    # to a no-op returning a tiny DataFrame (so we measure throttle, not fetch).
    tiny = pd.DataFrame({"Close": [1.0]})

    # Replace ONLY the inner fetch_ohlcv (already decorated with throttle+retry).
    # We want the throttle decorator preserved — so patch by replacing the
    # function body via the underlying __wrapped__? Simpler: just call
    # `fetch_ohlcv_cached` which itself calls `fetch_ohlcv` (throttled).
    # Patch `yf.Ticker(...).history` to return tiny DF immediately.
    mock_ticker = mocker.patch("stocksig.io.market.yf.Ticker")
    mock_ticker.return_value.history.return_value = tiny

    t0 = time.monotonic()
    for i in range(10):
        fetch_ohlcv_cached(f"SYM{i}")
    elapsed = time.monotonic() - t0
    # 10 calls at 2 RPS = ~4.5s minimum (10/2 = 5s; first 2 burst free).
    assert elapsed >= 4.5, f"throttle not enforced: {elapsed:.2f}s for 10 calls"


def test_logs_trading_day_count(mocker, mock_ohlcv_df, caplog):
    # Pitfall F: success log includes trading day count
    mock_ticker_cls = mocker.patch("stocksig.io.market.yf.Ticker")
    mock_ticker_cls.return_value.history.return_value = mock_ohlcv_df

    with caplog.at_level("INFO"):
        fetch_ohlcv("AAPL")

    assert "AAPL" in caplog.text
    assert f"OHLCV {len(mock_ohlcv_df)} 거래일 수신 완료" in caplog.text
