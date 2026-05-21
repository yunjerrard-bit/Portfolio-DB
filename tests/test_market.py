"""MKTD-01/02/03 GREEN tests (no network — mock yf.Ticker)."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import pytest
from tenacity import wait_none
from yfinance.exceptions import YFRateLimitError

from stocksig.io import market
from stocksig.io.market import fetch_ohlcv


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


def test_logs_trading_day_count(mocker, mock_ohlcv_df, caplog):
    # Pitfall F: success log includes trading day count
    mock_ticker_cls = mocker.patch("stocksig.io.market.yf.Ticker")
    mock_ticker_cls.return_value.history.return_value = mock_ohlcv_df

    with caplog.at_level("INFO"):
        fetch_ohlcv("AAPL")

    assert "AAPL" in caplog.text
    assert f"OHLCV {len(mock_ohlcv_df)} 거래일 수신 완료" in caplog.text
