"""D-01 / INPUT-04 GREEN tests for read_tickers_extended + TickerSpec."""

from pathlib import Path

import pytest

from stocksig.io.input import TickerSpec, read_tickers, read_tickers_extended


def test_single_column_backcompat(tmp_tickers_file):
    path = tmp_tickers_file("AAPL\nMSFT\n")
    specs = read_tickers_extended(path)
    assert specs == [
        TickerSpec("AAPL", "", ""),
        TickerSpec("MSFT", "", ""),
    ]


def test_tab_separated(tmp_tickers_file):
    path = tmp_tickers_file("AAPL\t1\tTechnology\n")
    assert read_tickers_extended(path) == [TickerSpec("AAPL", "1", "Technology")]


def test_whitespace_separated(tmp_tickers_file):
    path = tmp_tickers_file("AAPL 1 Technology\n")
    assert read_tickers_extended(path) == [TickerSpec("AAPL", "1", "Technology")]


def test_mixed_tab_and_whitespace(tmp_tickers_file):
    # 탭+공백 혼합 — `line.split()`이 모든 whitespace를 분리한다.
    path = tmp_tickers_file("AAPL\t1 Technology\n")
    spec = read_tickers_extended(path)[0]
    assert spec.symbol == "AAPL"
    assert spec.tier == "1"
    assert spec.industry == "Technology"


def test_multiword_industry_preserved(tmp_tickers_file):
    # `" ".join(parts[2:])`로 다중 단어 산업명 복원.
    path = tmp_tickers_file("XOM\t3\tOil and Gas\n")
    spec = read_tickers_extended(path)[0]
    assert spec.industry == "Oil and Gas"


def test_comment_lines_skipped(tmp_tickers_file):
    path = tmp_tickers_file("# header\nAAPL\n# tail\n")
    specs = read_tickers_extended(path)
    assert len(specs) == 1
    assert specs[0].symbol == "AAPL"


def test_blank_lines_skipped(tmp_tickers_file):
    path = tmp_tickers_file("\n\nAAPL\n\n")
    specs = read_tickers_extended(path)
    assert len(specs) == 1
    assert specs[0].symbol == "AAPL"


def test_korean_industry(tmp_tickers_file):
    path = tmp_tickers_file("005930.KS\t2\t반도체\n")
    spec = read_tickers_extended(path)[0]
    assert spec.symbol == "005930.KS"
    assert spec.tier == "2"
    assert spec.industry == "반도체"


def test_empty_file_exits(tmp_tickers_file, caplog):
    path = tmp_tickers_file("")
    with caplog.at_level("ERROR"):
        with pytest.raises(SystemExit) as exc_info:
            read_tickers_extended(path)
    assert exc_info.value.code != 0
    assert "tickers.txt 파일이 비어있습니다" in caplog.text


def test_missing_file_exits(caplog):
    nonexistent = Path("/nonexistent_tickers_xyz_extended.txt")
    with caplog.at_level("ERROR"):
        with pytest.raises(SystemExit) as exc_info:
            read_tickers_extended(nonexistent)
    assert exc_info.value.code != 0
    assert "tickers.txt 파일을 찾을 수 없습니다" in caplog.text


def test_read_tickers_backcompat(tmp_tickers_file):
    # Phase 1 caller가 그대로 동작 — list[str] of symbols.
    path = tmp_tickers_file("AAPL\t1\tTechnology\n005930.KS\t2\t반도체\n")
    assert read_tickers(path) == ["AAPL", "005930.KS"]
