"""INPUT-01/02/03 RED stubs.

Import target (Wave 1 구현 계약):
    from stocksig.io.input import read_tickers
"""

import pytest


@pytest.mark.xfail(reason="Wave 1: read_tickers 구현 대기 (INPUT-01)", strict=False)
def test_read_single_ticker(tmp_tickers_file):
    # GIVEN: tickers.txt with a single line "AAPL"
    # WHEN: read_tickers(path) is called
    # THEN: returns ["AAPL"]
    from stocksig.io.input import read_tickers  # noqa: F401
    raise NotImplementedError("Wave 1에서 구현")


@pytest.mark.xfail(reason="Wave 1: read_tickers KR suffix 처리 대기 (INPUT-02)", strict=False)
def test_read_kr_suffix(tmp_tickers_file):
    # GIVEN: tickers.txt with "005930.KS" / "035720.KQ"
    # WHEN: read_tickers(path)
    # THEN: KR suffixes preserved verbatim
    from stocksig.io.input import read_tickers  # noqa: F401
    raise NotImplementedError("Wave 1에서 구현")


@pytest.mark.xfail(reason="Wave 1: empty file fail-fast 대기 (INPUT-03)", strict=False)
def test_empty_file_exits_nonzero(tmp_tickers_file, capsys):
    # GIVEN: empty tickers.txt
    # WHEN: read_tickers(path)
    # THEN: SystemExit with non-zero code + 한국어 메시지 in stderr
    from stocksig.io.input import read_tickers  # noqa: F401
    raise NotImplementedError("Wave 1에서 구현")
