"""INPUT-01/02/03 GREEN tests for read_tickers."""

from pathlib import Path

import pytest

from stocksig.io.input import read_tickers


def test_read_single_ticker(tmp_tickers_file):
    # INPUT-01: single ticker line returns single-element list
    path = tmp_tickers_file("AAPL\n")
    assert read_tickers(path) == ["AAPL"]


def test_read_kr_suffix(tmp_tickers_file):
    # INPUT-02: KR suffixes preserved verbatim, ordering preserved, no case change
    content = "005930.KS\n035720.KQ\nAAPL\n"
    path = tmp_tickers_file(content)
    assert read_tickers(path) == ["005930.KS", "035720.KQ", "AAPL"]


def test_skips_blank_and_comments(tmp_tickers_file):
    # behavior block: blank lines + '#' comments skipped, whitespace stripped
    content = "# 주석\n\nAAPL\n  TSLA  \n"
    path = tmp_tickers_file(content)
    assert read_tickers(path) == ["AAPL", "TSLA"]


def test_empty_file_exits_nonzero(tmp_tickers_file, caplog):
    # INPUT-03: empty file -> SystemExit + 한국어 stderr
    path = tmp_tickers_file("")
    with caplog.at_level("ERROR"):
        with pytest.raises(SystemExit) as exc_info:
            read_tickers(path)
    assert exc_info.value.code != 0
    assert "tickers.txt 파일이 비어있습니다" in caplog.text


def test_missing_file_exits_nonzero(caplog):
    # behavior block: nonexistent file -> SystemExit + 한국어 stderr
    nonexistent = Path("/nonexistent_tickers_xyz.txt")
    with caplog.at_level("ERROR"):
        with pytest.raises(SystemExit) as exc_info:
            read_tickers(nonexistent)
    assert exc_info.value.code != 0
    assert "tickers.txt 파일을 찾을 수 없습니다" in caplog.text
