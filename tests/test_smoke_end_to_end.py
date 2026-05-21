"""End-to-end smoke + 3-row color verification.

Wave 4 (PLAN 01-05): `stocksig.main.run` (== `stocksig.main_run.run`) 호출 →
실제 XlsxWriter로 .xlsx 생성 → openpyxl로 다시 열어 시트 구조 + 3행 색 검증.

테스트는 mock yfinance fixture(`mock_ohlcv_df`, conftest.py)를 사용하므로
네트워크 호출 없이 결정론적으로 통과한다.
"""

from __future__ import annotations

import openpyxl
import pandas as pd

from stocksig.compute.color_rules import (
    GREEN_100,
    GREEN_800,
    GREEN_900,
    RED_100,
    RED_800,
    RED_900,
    SigmaBucket,
    decide_sigma_bucket,
)
from stocksig.main import run

# D-04 hex → openpyxl ARGB (alpha=FF) 매핑
_SIGMA_FONT_HEX = {
    SigmaBucket.DEFAULT: None,
    SigmaBucket.SOFT_GREEN: GREEN_800.lstrip("#").upper(),
    SigmaBucket.SOFT_RED: RED_800.lstrip("#").upper(),
    SigmaBucket.HARD_GREEN: GREEN_900.lstrip("#").upper(),
    SigmaBucket.HARD_RED: RED_900.lstrip("#").upper(),
}
_SIGMA_FILL_HEX = {
    SigmaBucket.DEFAULT: None,
    SigmaBucket.SOFT_GREEN: None,
    SigmaBucket.SOFT_RED: None,
    SigmaBucket.HARD_GREEN: GREEN_100.lstrip("#").upper(),
    SigmaBucket.HARD_RED: RED_100.lstrip("#").upper(),
}


def _normalize_rgb(rgb_value) -> str | None:
    """openpyxl ARGB ('FFRRGGBB') 또는 RGB ('RRGGBB') 또는 None → 'RRGGBB' uppercase 또는 None."""
    if rgb_value is None:
        return None
    if not isinstance(rgb_value, str):
        return None
    v = rgb_value.upper()
    if len(v) == 8:
        return v[2:]
    if len(v) == 6:
        return v
    return None


def _setup_mock_yfinance(mocker, df: pd.DataFrame) -> None:
    """`yf.Ticker(...).history(...)`가 df를 반환하도록 patch."""
    ticker_class = mocker.patch("stocksig.io.market.yf.Ticker")
    instance = ticker_class.return_value
    instance.history.return_value = df


def test_single_ticker_workbook(mocker, mock_ohlcv_df, tmp_path, tmp_tickers_file, tmp_env_file):
    """smoke: AAPL 단일 티커로 워크북 생성 + 시트 구조 검증."""
    _setup_mock_yfinance(mocker, mock_ohlcv_df)
    tickers = tmp_tickers_file("AAPL\n")
    env = tmp_env_file("EDGAR_USER_AGENT_EMAIL=test@example.com\nOPENDART_API_KEY=test-key\n")

    output_path = run(tickers, env, tmp_path / "output")

    assert output_path.exists(), f"워크북이 생성되어야 한다: {output_path}"
    assert output_path.suffix == ".xlsx"

    wb = openpyxl.load_workbook(output_path)
    assert "AAPL" in wb.sheetnames
    ws = wb["AAPL"]

    # SHEET-02: A1 == ticker
    assert ws["A1"].value == "AAPL"

    # 컬럼 폭: 124 (Date + (4 OHLCV × 3) + (12 EMA × 3) + (12 DIFF × 3) + (12 dailychg × 3) + 3 tech)
    assert ws.max_column == 124, f"시트 폭은 124여야 한다 (현재: {ws.max_column})"

    # SHEET-03: row 3 — Close 위치(col B, index 2) — 스칼라 median 존재
    assert ws.cell(row=3, column=2).value is not None
    assert isinstance(ws.cell(row=3, column=2).value, (int, float))

    # SHEET-04: row 4 — Close 위치 — 스칼라 std 존재
    assert ws.cell(row=4, column=2).value is not None
    assert isinstance(ws.cell(row=4, column=2).value, (int, float))

    # SHEET-05: row 5 한국어 헤더
    assert ws.cell(row=5, column=1).value == "날짜"
    assert ws.cell(row=5, column=2).value == "종가"
    assert ws.cell(row=5, column=3).value == "종가 일별 중앙값"
    assert ws.cell(row=5, column=4).value == "종가 일별 표준편차"

    # SHEET-06: row 6+ 데이터 — 가장 최신 날짜 (descending)
    first_date = ws.cell(row=6, column=1).value
    second_date = ws.cell(row=7, column=1).value
    assert first_date is not None
    assert second_date is not None
    # 첫 행이 두 번째 행보다 더 최신 (내림차순)
    assert first_date > second_date


def test_color_at_three_rows(mocker, mock_ohlcv_df, tmp_path, tmp_tickers_file, tmp_env_file):
    """Success Criteria #2/#3: 3개 행(최신/중간/오래된)의 Close 셀 색이 D-04와 일치.

    expected SigmaBucket은 mock_ohlcv_df로부터 직접 expanding median/std를
    재계산하여 `decide_sigma_bucket`으로 산출 → openpyxl로 읽은 실제 셀 색과 비교.
    """
    _setup_mock_yfinance(mocker, mock_ohlcv_df)
    tickers = tmp_tickers_file("AAPL\n")
    env = tmp_env_file("EDGAR_USER_AGENT_EMAIL=test@example.com\nOPENDART_API_KEY=test-key\n")

    output_path = run(tickers, env, tmp_path / "output")
    wb = openpyxl.load_workbook(output_path)
    ws = wb["AAPL"]

    # mock df로부터 expanding median/std 직접 계산 (Close 컬럼 기준)
    sorted_asc = mock_ohlcv_df.sort_index(ascending=True)
    close = sorted_asc["Close"]
    expanding_median = close.expanding().median()
    expanding_std = close.expanding().std()

    n = len(sorted_asc)
    # 3개 인덱스: 가장 오래된(0), 중간, 가장 최신(n-1)
    indices = [0, n // 2, n - 1]

    # 시트는 내림차순 → row 6이 가장 최신 (asc index n-1)
    # row 6+i 가 sorted_asc index n-1-i
    for asc_idx in indices:
        descending_row_offset = (n - 1) - asc_idx  # 0이면 row 6, 1이면 row 7, ...
        excel_row = 6 + descending_row_offset
        value = close.iloc[asc_idx]
        med = expanding_median.iloc[asc_idx]
        std = expanding_std.iloc[asc_idx]
        expected_bucket = decide_sigma_bucket(value, med, std)

        # Close 컬럼은 layout의 index 1 → openpyxl column 2
        cell = ws.cell(row=excel_row, column=2)

        # 값 정합성 (반올림 허용)
        assert cell.value is not None, f"row {excel_row} Close 셀이 비어있다"
        assert abs(float(cell.value) - float(value)) < 1e-6

        # 폰트 색 검증
        expected_font_hex = _SIGMA_FONT_HEX[expected_bucket]
        font_color = cell.font.color
        actual_font_hex = (
            _normalize_rgb(font_color.rgb) if font_color is not None else None
        )
        # 기본(검정/None)은 XlsxWriter가 색을 지정하지 않으므로 None 또는 '000000' 둘 다 허용
        if expected_font_hex is None:
            assert actual_font_hex in (None, "000000"), (
                f"row {excel_row} (bucket={expected_bucket}) 폰트 색이 기본이어야 한다 "
                f"(actual={actual_font_hex})"
            )
        else:
            assert actual_font_hex == expected_font_hex, (
                f"row {excel_row} (bucket={expected_bucket}) 폰트 색 불일치: "
                f"expected={expected_font_hex}, actual={actual_font_hex}"
            )

        # 배경 색 검증 (HARD 케이스만 fill 존재)
        expected_fill_hex = _SIGMA_FILL_HEX[expected_bucket]
        fill = cell.fill
        actual_fill_hex = None
        if fill is not None and fill.fgColor is not None:
            # openpyxl PatternFill: fgColor.type='rgb'일 때만 hex
            if getattr(fill.fgColor, "type", None) == "rgb":
                actual_fill_hex = _normalize_rgb(fill.fgColor.rgb)
        if expected_fill_hex is None:
            assert actual_fill_hex in (None, "000000"), (
                f"row {excel_row} (bucket={expected_bucket}) 배경 색이 없어야 한다 "
                f"(actual={actual_fill_hex})"
            )
        else:
            assert actual_fill_hex == expected_fill_hex, (
                f"row {excel_row} (bucket={expected_bucket}) 배경 색 불일치: "
                f"expected={expected_fill_hex}, actual={actual_fill_hex}"
            )
