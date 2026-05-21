"""End-to-end smoke + 3-row color verification.

Wave 4 (PLAN 01-05): `stocksig.main.run` (== `stocksig.main_run.run`) 호출 →
실제 XlsxWriter로 .xlsx 생성 → openpyxl로 다시 열어 시트 구조 + 3행 색 검증.

테스트는 mock yfinance fixture(`mock_ohlcv_df`, conftest.py)를 사용하므로
네트워크 호출 없이 결정론적으로 통과한다.
"""

from __future__ import annotations

import openpyxl
import pandas as pd
from openpyxl.utils import get_column_letter

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
from stocksig.output.sheet_per_ticker import build_column_layout

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

    # 컬럼 폭: 76 (gap-fix 01-07: Date + 12 OHLCV + 12 EMA_Close + 36 DIFF + 12 dailychg + 3 tech)
    assert ws.max_column == 76, f"시트 폭은 76여야 한다 (현재: {ws.max_column})"

    # gap-fix 01-07: 신규 한국어 헤더 검증
    layout = build_column_layout()
    diff_high_11_col = layout.index("DIFF_High_11") + 1
    assert ws.cell(row=5, column=diff_high_11_col).value == "고가-EMA11 차이"
    ema_close_11_col = layout.index("EMA_Close_11") + 1
    assert ws.cell(row=5, column=ema_close_11_col).value == "종가 EMA11"

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


def test_num_format_baked(mocker, mock_ohlcv_df, tmp_path, tmp_tickers_file, tmp_env_file):
    """gap-fix 01-06: 각 컬럼 타입의 데이터 셀에 num_format이 베이크되어 있어야 한다.

    - 종가 (Close)    → '#,##0.00'
    - 거래량 (Volume) → '#,##0'
    - RSI             → '0.00"%"'
    """
    _setup_mock_yfinance(mocker, mock_ohlcv_df)
    tickers = tmp_tickers_file("AAPL\n")
    env = tmp_env_file("EDGAR_USER_AGENT_EMAIL=test@example.com\nOPENDART_API_KEY=test-key\n")

    output_path = run(tickers, env, tmp_path / "output")
    wb = openpyxl.load_workbook(output_path)
    ws = wb["AAPL"]

    layout = build_column_layout()
    close_col = layout.index("Close") + 1
    volume_col = layout.index("Volume") + 1
    rsi_col = layout.index("RSI") + 1  # gap-fix 01-07: 새 위치 (76번째)
    diff_close_11_col = layout.index("DIFF_Close_11") + 1  # gap-fix 01-07: percent_ratio

    # 데이터 첫 행 = row 6 (내림차순 최신)
    close_cell = ws.cell(row=6, column=close_col)
    volume_cell = ws.cell(row=6, column=volume_col)
    rsi_cell = ws.cell(row=6, column=rsi_col)
    diff_cell = ws.cell(row=6, column=diff_close_11_col)

    assert close_cell.value is not None, "Close 셀이 비어 있다"
    assert volume_cell.value is not None, "Volume 셀이 비어 있다"
    assert rsi_cell.value is not None, "RSI 셀이 비어 있다"
    assert diff_cell.value is not None, "DIFF_Close_11 셀이 비어 있다"

    assert close_cell.number_format == "#,##0.00", (
        f"Close num_format 불일치: expected='#,##0.00', actual={close_cell.number_format!r}"
    )
    assert volume_cell.number_format == "#,##0", (
        f"Volume num_format 불일치: expected='#,##0', actual={volume_cell.number_format!r}"
    )
    assert rsi_cell.number_format == '0.00"%"', (
        f"RSI num_format 불일치: expected='0.00\"%\"', actual={rsi_cell.number_format!r}"
    )
    # gap-fix 01-07: DIFF는 비율 → '0.00%' (Excel가 자동 ×100)
    assert diff_cell.number_format == "0.00%", (
        f"DIFF_Close_11 num_format 불일치: expected='0.00%', actual={diff_cell.number_format!r}"
    )
    # DIFF 값은 비율 스케일 — 절댓값 < 1
    assert abs(float(diff_cell.value)) < 1.0, (
        f"DIFF_Close_11 값이 비율 스케일이 아니다: {diff_cell.value}"
    )


def test_median_std_columns_hidden(mocker, mock_ohlcv_df, tmp_path, tmp_tickers_file, tmp_env_file):
    """gap-fix 01-08: 모든 *_median, *_std 컬럼은 hidden=True, 그 외 가시.

    검증:
      - Close_median, DIFF_Close_11_std 위치 → hidden == True
      - Close, RSI, Stoch_%K 등 primary 컬럼 → hidden == False
      - 데이터·서식은 그대로 유지 (값 존재 확인)
    """
    _setup_mock_yfinance(mocker, mock_ohlcv_df)
    tickers = tmp_tickers_file("AAPL\n")
    env = tmp_env_file("EDGAR_USER_AGENT_EMAIL=test@example.com\nOPENDART_API_KEY=test-key\n")

    output_path = run(tickers, env, tmp_path / "output")
    wb = openpyxl.load_workbook(output_path)
    ws = wb["AAPL"]

    layout = build_column_layout()

    # XlsxWriter는 연속된 set_column 호출을 min/max 범위로 합쳐 저장하므로,
    # openpyxl의 ws.column_dimensions[letter]는 defaultdict 동작으로 빈 항목을 만들 수 있다.
    # 실제 컬럼 속성은 저장된 모든 ColumnDimension 의 (min, max) 범위를 순회해 찾는다.
    def is_hidden(col_excel_idx: int) -> bool:
        for cd in ws.column_dimensions.values():
            if cd.min is None or cd.max is None:
                continue
            if cd.min <= col_excel_idx <= cd.max:
                return bool(cd.hidden)
        return False

    # 숨김 대상 검증 (sample)
    hidden_targets = ["Close_median", "Close_std", "DIFF_Close_11_std", "Volume_median",
                       "EMA_Close_192_median", "EMA_Close_11_dailychg_std"]
    for col_name in hidden_targets:
        col_idx = layout.index(col_name)
        letter = get_column_letter(col_idx + 1)
        assert is_hidden(col_idx + 1) is True, (
            f"{col_name} (column {letter}) 는 hidden=True 여야 한다"
        )

    # 비숨김 대상 검증
    visible_targets = ["Close", "High", "Low", "Volume", "EMA_Close_11",
                        "DIFF_Close_11", "RSI", "Stoch_%K", "Stoch_%D"]
    for col_name in visible_targets:
        col_idx = layout.index(col_name)
        letter = get_column_letter(col_idx + 1)
        assert is_hidden(col_idx + 1) is False, (
            f"{col_name} (column {letter}) 는 hidden=False 여야 한다"
        )

    # 데이터 유지 확인: 숨겨진 컬럼에도 값이 살아있어야 함
    close_median_idx = layout.index("Close_median")
    close_median_cell = ws.cell(row=6, column=close_median_idx + 1)
    assert close_median_cell.value is not None, "Close_median 셀 데이터는 보존되어야 한다"

    # 전체 layout 모든 *_median / *_std 가 빠짐없이 hidden인지 확인
    for col_idx, col_name in enumerate(layout):
        letter = get_column_letter(col_idx + 1)
        expected_hidden = col_name.endswith(("_median", "_std"))
        actual_hidden = is_hidden(col_idx + 1)
        assert actual_hidden == expected_hidden, (
            f"{col_name} (column {letter}) hidden 불일치: "
            f"expected={expected_hidden}, actual={actual_hidden}"
        )


def test_diff_columns_ordered_by_period():
    """gap-fix 01-09: DIFF 컬럼이 EMA period 기준으로 그룹화되어야 한다.

    이전(01-07): price 외부, period 내부 → Close_11, Close_22, ..., High_11, ...
    이후(01-09): period 외부, price 내부 → Close_11, High_11, Low_11, Close_22, ...
    """
    layout = build_column_layout()
    diff_cols = [
        c for c in layout
        if c.startswith("DIFF_") and not c.endswith(("_median", "_std"))
    ]
    expected = [
        "DIFF_Close_11", "DIFF_High_11", "DIFF_Low_11",
        "DIFF_Close_22", "DIFF_High_22", "DIFF_Low_22",
        "DIFF_Close_96", "DIFF_High_96", "DIFF_Low_96",
        "DIFF_Close_192", "DIFF_High_192", "DIFF_Low_192",
    ]
    assert diff_cols == expected, f"DIFF 컬럼 순서 불일치: {diff_cols}"

    # median/std siblings 가 각 base 바로 뒤에 interleave 되어 있는지 확인
    for base in expected:
        i = layout.index(base)
        assert layout[i + 1] == f"{base}_median", (
            f"{base} 다음 컬럼이 {base}_median 이어야 함, 실제: {layout[i + 1]}"
        )
        assert layout[i + 2] == f"{base}_std", (
            f"{base} +2 컬럼이 {base}_std 이어야 함, 실제: {layout[i + 2]}"
        )

    # 총 컬럼 수 76 유지
    assert len(layout) == 76, f"총 컬럼 수 76 이어야 함, 실제: {len(layout)}"
