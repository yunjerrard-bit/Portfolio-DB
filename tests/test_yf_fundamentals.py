"""Phase 3 Wave 3 (03-03 Task 2): yf_fundamentals.py — .info 폴백(_SESSION 재사용).

`.info` mock 으로 PER/PEG/GPM/OPM 키 추출·None-safe 단언. pegRatio→trailingPegRatio
키 변동 가드(A4). 소스 단언: _SESSION 재사용(신규 세션 생성 없음).
"""

from __future__ import annotations

from pathlib import Path

from fixtures.yf_info_sample import AAPL_INFO, SAMSUNG_INFO


def test_source_reuses_session():
    # 소스 단언: from stocksig.io.market import _SESSION (신규 세션 생성 없음)
    src = Path("src/stocksig/io/yf_fundamentals.py").read_text(encoding="utf-8")
    assert "from stocksig.io.market import _SESSION" in src
    assert "@throttled_yahoo" in src
    # 신규 curl_cffi 세션 생성 금지
    assert "curl_requests.Session" not in src
    assert "Session(impersonate" not in src


def test_fetch_yf_info_extracts_keys(mocker):
    from stocksig.io.yf_fundamentals import fetch_yf_info

    mock_ticker = mocker.patch("stocksig.io.yf_fundamentals.yf.Ticker")
    mock_ticker.return_value.info = AAPL_INFO

    out = fetch_yf_info("AAPL")
    assert out["PER"] == AAPL_INFO["trailingPE"]
    assert out["PEG"] == AAPL_INFO["pegRatio"]
    assert out["GPM"] == AAPL_INFO["grossMargins"]
    assert out["OPM"] == AAPL_INFO["operatingMargins"]


def test_fetch_yf_info_uses_session(mocker):
    from stocksig.io import market
    from stocksig.io.yf_fundamentals import fetch_yf_info

    mock_ticker = mocker.patch("stocksig.io.yf_fundamentals.yf.Ticker")
    mock_ticker.return_value.info = AAPL_INFO

    fetch_yf_info("AAPL")
    call = mock_ticker.call_args
    assert call.kwargs.get("session") is market._SESSION


def test_fetch_yf_info_peg_fallback_key(mocker):
    # pegRatio 부재 → trailingPegRatio 폴백 (A4 키 변동 가드)
    from stocksig.io.yf_fundamentals import fetch_yf_info

    info = dict(AAPL_INFO)
    info["pegRatio"] = None
    mock_ticker = mocker.patch("stocksig.io.yf_fundamentals.yf.Ticker")
    mock_ticker.return_value.info = info

    out = fetch_yf_info("AAPL")
    assert out["PEG"] == AAPL_INFO["trailingPegRatio"]


def test_fetch_yf_info_none_safe(mocker):
    # KR(005930.KS): trailingPE None → PER None-safe (KeyError/예외 없음)
    from stocksig.io.yf_fundamentals import fetch_yf_info

    mock_ticker = mocker.patch("stocksig.io.yf_fundamentals.yf.Ticker")
    mock_ticker.return_value.info = SAMSUNG_INFO

    out = fetch_yf_info("005930.KS")
    assert out["PER"] is None  # trailingPE 결손
    assert out["GPM"] == SAMSUNG_INFO["grossMargins"]


def test_fetch_yf_info_empty_info(mocker):
    # 빈 .info → 전 키 None (None-safe .get)
    from stocksig.io.yf_fundamentals import fetch_yf_info

    mock_ticker = mocker.patch("stocksig.io.yf_fundamentals.yf.Ticker")
    mock_ticker.return_value.info = {}

    out = fetch_yf_info("XYZ")
    assert out["PER"] is None
    assert out["PEG"] is None
    assert out["GPM"] is None
    assert out["OPM"] is None
