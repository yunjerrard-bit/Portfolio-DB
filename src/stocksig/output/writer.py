"""XlsxWriter Workbook 팩토리 + Format 캐시 (Pattern 8, D-04 + gap-fix 01-06).

make_workbook(path) → (Workbook, formats_dict)
formats_dict 키:
  - (bucket, fmt_type) tuple — bucket ∈ 5 SigmaBucket + 3 TechBucket = 8,
                                 fmt_type ∈ {"price", "volume", "percent"}
  - "header"
총 8 × 3 + 1 = 25 키. 워크북당 add_format 호출 정확히 25회.

num_format 매핑:
  - "price"   → '#,##0.00'   (쉼표 + 소수점 2자리)
  - "volume"  → '#,##0'      (쉼표 + 정수)
  - "percent" → '0.00"%"'    (소수점 2자리 + 리터럴 % 접미사, 값 0~100 유지)
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import xlsxwriter

from stocksig.compute.color_rules import (
    GREEN_100,
    GREEN_800,
    GREEN_900,
    RED_100,
    RED_800,
    RED_900,
    SigmaBucket,
    TechBucket,
)

# num_format 문자열 (gap-fix 01-06)
NUM_FORMAT_PRICE = "#,##0.00"
NUM_FORMAT_VOLUME = "#,##0"
NUM_FORMAT_PERCENT = '0.00"%"'

_NUM_FORMAT_MAP = {
    "price": NUM_FORMAT_PRICE,
    "volume": NUM_FORMAT_VOLUME,
    "percent": NUM_FORMAT_PERCENT,
}

# 색 속성 (bucket → dict, num_format 제외)
_COLOR_PROPS: dict = {
    SigmaBucket.DEFAULT: {},
    SigmaBucket.SOFT_GREEN: {"font_color": GREEN_800},
    SigmaBucket.SOFT_RED: {"font_color": RED_800},
    SigmaBucket.HARD_GREEN: {"font_color": GREEN_900, "bg_color": GREEN_100},
    SigmaBucket.HARD_RED: {"font_color": RED_900, "bg_color": RED_100},
    TechBucket.DEFAULT: {},
    TechBucket.SOFT_GREEN: {"font_color": GREEN_800},
    TechBucket.SOFT_RED: {"font_color": RED_800},
}


def make_workbook(path: Union[str, Path]) -> tuple[xlsxwriter.Workbook, dict]:
    """출력 .xlsx Workbook + Format 캐시 dict 반환.

    부모 디렉터리 자동 생성. constant_memory=False (시트 작성 후 close까지
    데이터 유지 — 우리 use case는 합리적인 워크북 크기).

    Returns:
        (wb, formats): wb는 xlsxwriter.Workbook, formats는 25키 dict.
          - formats[(bucket, fmt_type)]: 색 + num_format 결합 Format
          - formats["header"]: bold + center 헤더
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(p), {"constant_memory": False})

    formats: dict = {}
    for bucket, color_props in _COLOR_PROPS.items():
        for fmt_type, num_format in _NUM_FORMAT_MAP.items():
            props = dict(color_props)
            props["num_format"] = num_format
            formats[(bucket, fmt_type)] = wb.add_format(props)

    formats["header"] = wb.add_format({"bold": True, "align": "center"})
    return wb, formats
