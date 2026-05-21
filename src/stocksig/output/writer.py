"""XlsxWriter Workbook 팩토리 + Format 캐시 (Pattern 8, D-04).

make_workbook(path) → (Workbook, formats_dict)
formats_dict 키: 5 SigmaBucket + 3 TechBucket + 'header' = 9개.
워크북당 add_format 호출은 9회로 제한 — 셀당 add_format 금지.
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


def make_workbook(path: Union[str, Path]) -> tuple[xlsxwriter.Workbook, dict]:
    """출력 .xlsx Workbook + Format 캐시 dict 반환.

    부모 디렉터리 자동 생성. constant_memory=False (시트 작성 후 close까지
    데이터 유지 — 우리 use case는 합리적인 워크북 크기).

    Returns:
        (wb, formats): wb는 xlsxwriter.Workbook, formats는 9키 dict.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(str(p), {"constant_memory": False})
    formats: dict = {
        SigmaBucket.DEFAULT: wb.add_format({}),
        SigmaBucket.SOFT_GREEN: wb.add_format({"font_color": GREEN_800}),
        SigmaBucket.SOFT_RED: wb.add_format({"font_color": RED_800}),
        SigmaBucket.HARD_GREEN: wb.add_format(
            {"font_color": GREEN_900, "bg_color": GREEN_100}
        ),
        SigmaBucket.HARD_RED: wb.add_format(
            {"font_color": RED_900, "bg_color": RED_100}
        ),
        TechBucket.DEFAULT: wb.add_format({}),
        TechBucket.SOFT_GREEN: wb.add_format({"font_color": GREEN_800}),
        TechBucket.SOFT_RED: wb.add_format({"font_color": RED_800}),
        "header": wb.add_format({"bold": True, "align": "center"}),
    }
    return wb, formats
