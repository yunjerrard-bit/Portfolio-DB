"""End-to-end smoke + 3-row color verification RED stubs.

Import target (Wave 4 구현 계약):
    from stocksig.main import run  # or `from main import run`
"""

import pytest


@pytest.mark.xfail(reason="Wave 4: end-to-end xlsx 생성 대기 (SHEET-01~08, TECH-03/06, OUT-01~03)", strict=False)
def test_single_ticker_workbook(mocker, mock_ohlcv_df, tmp_path):
    # GIVEN: mocked yfinance returning mock_ohlcv_df, tickers.txt with AAPL
    # WHEN: main.run() executes
    # THEN: output/portfolio_*.xlsx exists; sheet name=AAPL, A1=AAPL,
    #       row 5 has Korean headers, row 6+ has data (openpyxl verifies)
    from stocksig.main import run  # noqa: F401
    raise NotImplementedError("Wave 4에서 구현")


@pytest.mark.xfail(reason="Wave 4: 3개 행 색 검증 대기 (Success Criteria #2/#3)", strict=False)
def test_color_at_three_rows(mocker, mock_ohlcv_df, tmp_path):
    # GIVEN: workbook produced by main.run() with mock OHLCV
    # WHEN: openpyxl loads workbook and inspects 가장 최근/중간/오래된 3 rows
    # THEN: expected SigmaBucket → cell.font.color.rgb matches D-04 hex
    from stocksig.main import run  # noqa: F401
    raise NotImplementedError("Wave 4에서 구현")
