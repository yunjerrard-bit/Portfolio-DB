"""MKTD-01/02/03 RED stubs (no network — mock yf.Ticker).

Import target (Wave 1 구현 계약):
    from stocksig.io.market import fetch_ohlcv
"""

import pytest


@pytest.mark.xfail(reason="Wave 1: fetch_ohlcv date window 대기 (MKTD-01)", strict=False)
def test_fetch_ohlcv_date_window(mocker, mock_ohlcv_df):
    # GIVEN: today() - 4000 calendar days as start, today() as end
    # WHEN: fetch_ohlcv("AAPL") is called
    # THEN: yfinance Ticker.history called with start ~ today-4000d
    mocker.patch("yfinance.Ticker")
    from stocksig.io.market import fetch_ohlcv  # noqa: F401
    raise NotImplementedError("Wave 1에서 구현")


@pytest.mark.xfail(reason="Wave 1: curl_cffi session 사용 검증 대기 (MKTD-02)", strict=False)
def test_uses_curl_cffi_session(mocker):
    # GIVEN: stocksig.io.market._SESSION 모듈 attribute
    # THEN: 인스턴스가 curl_cffi.requests.Session + impersonate="chrome"
    from stocksig.io.market import fetch_ohlcv  # noqa: F401
    raise NotImplementedError("Wave 1에서 구현")


@pytest.mark.xfail(reason="Wave 1: tenacity 재시도 대기 (MKTD-03)", strict=False)
def test_retries_on_rate_limit(mocker, mock_ohlcv_df):
    # GIVEN: yf.Ticker.history side_effect=YFRateLimitError() 4회 + 5번째 성공
    # WHEN: fetch_ohlcv("AAPL")
    # THEN: tenacity 5회 재시도 후 결과 반환
    mocker.patch("yfinance.Ticker")
    from stocksig.io.market import fetch_ohlcv  # noqa: F401
    raise NotImplementedError("Wave 1에서 구현")
