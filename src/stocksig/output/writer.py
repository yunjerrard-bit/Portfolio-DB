"""XlsxWriter Workbook 팩토리 + Format 캐시 (Pattern 8, D-04 + gap-fix 01-06/01-07).

make_workbook(path) → (Workbook, formats_dict)
formats_dict 키:
  - (bucket, fmt_type) tuple — bucket ∈ 5 SigmaBucket + 3 TechBucket = 8,
                                 fmt_type ∈ {"price", "volume", "percent_literal", "percent_ratio"}
  - "header"
총 8 × 4 + 1 = 33 키 (Phase 1 01-06).
gap-fix 01-14: + a1_title + header_bg×4 + impulse×4 = 42 키.
Phase 2 02-03: + failed_row_marker + timestamp = 44 키.
워크북당 add_format 호출 정확히 44회.

num_format 매핑 (gap-fix 01-07: percent를 두 종류로 분리):
  - "price"           → '#,##0.00'   (쉼표 + 소수점 2자리)
  - "volume"          → '#,##0'      (쉼표 + 정수)
  - "percent_literal" → '0.00"%"'    (값 0~100 그대로 + 리터럴 % — Stoch/RSI 용)
  - "percent_ratio"   → '0.00%'      (Excel가 값 ×100 — DIFF 비율 용; 저장값 0.0123 → 1.23% 표시)
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import xlsxwriter

from stocksig.compute.color_rules import (
    BLUE_100,
    BLUE_800,
    BLUE_900,
    GREEN_100,
    GREEN_800,
    GREEN_900,
    ImpulseBucket,
    RED_100,
    RED_800,
    RED_900,
    SigmaBucket,
    TechBucket,
)

# num_format 문자열 (gap-fix 01-06/01-07)
NUM_FORMAT_PRICE = "#,##0.00"
NUM_FORMAT_VOLUME = "#,##0"
NUM_FORMAT_PERCENT_LITERAL = '0.00"%"'  # 값 0~100 그대로 표시, 리터럴 %
NUM_FORMAT_PERCENT_RATIO = "0.00%"  # Excel가 자동 ×100, DIFF 비율용

_NUM_FORMAT_MAP = {
    "price": NUM_FORMAT_PRICE,
    "volume": NUM_FORMAT_VOLUME,
    "percent_literal": NUM_FORMAT_PERCENT_LITERAL,
    "percent_ratio": NUM_FORMAT_PERCENT_RATIO,
}

# 색 속성 (bucket → dict, num_format 제외)
# gap-fix 01-10: 색이 칠해진 6종 bucket에 bold 추가 (DEFAULT 2종은 무색·무볼드 유지)
_COLOR_PROPS: dict = {
    SigmaBucket.DEFAULT: {},
    SigmaBucket.SOFT_GREEN: {"font_color": GREEN_800, "bold": True},
    SigmaBucket.SOFT_RED: {"font_color": RED_800, "bold": True},
    SigmaBucket.HARD_GREEN: {"font_color": GREEN_900, "bg_color": GREEN_100, "bold": True},
    SigmaBucket.HARD_RED: {"font_color": RED_900, "bg_color": RED_100, "bold": True},
    TechBucket.DEFAULT: {},
    TechBucket.SOFT_GREEN: {"font_color": GREEN_800, "bold": True},
    TechBucket.SOFT_RED: {"font_color": RED_800, "bold": True},
}


def make_workbook(path: Union[str, Path]) -> tuple[xlsxwriter.Workbook, dict]:
    """출력 .xlsx Workbook + Format 캐시 dict 반환.

    부모 디렉터리 자동 생성. constant_memory=False (시트 작성 후 close까지
    데이터 유지 — 우리 use case는 합리적인 워크북 크기).

    Returns:
        (wb, formats): wb는 xlsxwriter.Workbook, formats는 33키 dict.
          - formats[(bucket, fmt_type)]: 색 + num_format 결합 Format
          - formats["header"]: bold + center 헤더
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    # nan_inf_to_errors: 2026-05-26 hotfix — IPO 직후 종목의 0-나누기 등으로
    # 발생하는 NaN/Inf가 셀에 도달해도 TypeError 대신 Excel #NUM!/#DIV/0! 셀로 폴백.
    # 1차 방어는 sheet_per_ticker.py의 pd.isna() / math.isinf() 필터.
    wb = xlsxwriter.Workbook(
        str(p), {"constant_memory": False, "nan_inf_to_errors": True}
    )

    formats: dict = {}
    for bucket, color_props in _COLOR_PROPS.items():
        for fmt_type, num_format in _NUM_FORMAT_MAP.items():
            props = dict(color_props)
            props["num_format"] = num_format
            formats[(bucket, fmt_type)] = wb.add_format(props)

    formats["header"] = wb.add_format({"bold": True, "align": "center"})

    # gap-fix 01-14: A1 ticker 셀 (bold + 20pt)
    formats["a1_title"] = wb.add_format({"bold": True, "font_size": 20})

    # gap-fix 01-14: 헤더 bg 4 variants (DIFF 그룹 4 EMA period)
    _HEADER_BG = {
        "header_bg_ema11": "#BDD7EE",  # 바다색 (60%)
        "header_bg_ema22": "#F8CBAD",  # 주황 (60%)
        "header_bg_ema96": "#E2EFDA",  # 황록 (60%)
        "header_bg_ema192": "#E1BEE7",  # 자주 (60%)
    }
    for key, bg in _HEADER_BG.items():
        formats[key] = wb.add_format(
            {"bold": True, "align": "center", "bg_color": bg}
        )

    # gap-fix 01-14: 임펄스 3 variants + DEFAULT
    formats["impulse_green"] = wb.add_format(
        {"bold": True, "font_color": GREEN_800, "bg_color": GREEN_100, "align": "center"}
    )
    formats["impulse_red"] = wb.add_format(
        {"bold": True, "font_color": RED_800, "bg_color": RED_100, "align": "center"}
    )
    formats["impulse_blue"] = wb.add_format(
        {"bold": True, "font_color": BLUE_800, "bg_color": BLUE_100, "align": "center"}
    )
    formats["impulse_default"] = wb.add_format({"align": "center"})

    # Phase 2 02-03 (D-03): 시트1 실패 티커 행 마커 — italic + pastel red
    formats["failed_row_marker"] = wb.add_format(
        {
            "italic": True,
            "font_color": RED_800,  # #C62828
            "bg_color": "#FFEBEE",  # Material Design RED 50 (pastel pink)
            "align": "left",
        }
    )
    # Phase 2 02-03 (PORT-08): 시트1 A1 실행 시각
    formats["timestamp"] = wb.add_format({"italic": True, "font_size": 12})

    return wb, formats
