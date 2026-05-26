"""io.market_kind 단위 테스트."""
from __future__ import annotations

from stocksig.io.market_kind import KR_SUFFIXES, classify_market


def test_us_default():
    assert classify_market("AAPL") == "US"


def test_kr_ks():
    assert classify_market("005930.KS") == "KR"


def test_kr_kq():
    assert classify_market("035720.KQ") == "KR"


def test_kr_aliases():
    assert classify_market("FOO.KOSPI") == "KR"
    assert classify_market("BAR.KOSDAQ") == "KR"


def test_case_insensitive():
    assert classify_market("aapl") == "US"
    assert classify_market("005930.ks") == "KR"


def test_no_match_unknown_suffix():
    # Japanese .T not in KR list → falls through to US default (L-14)
    assert classify_market("7203.T") == "US"


def test_kr_suffixes_constant():
    assert ".KS" in KR_SUFFIXES
    assert ".KQ" in KR_SUFFIXES
