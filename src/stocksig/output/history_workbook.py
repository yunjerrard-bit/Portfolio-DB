"""트렌드 전용 워크북 팩토리 + Format 캐시 (Plan 09-02, Pitfall 5 / T-09-03).

시트1·종목시트용 `writer.py::make_workbook`(45키 SigmaBucket/TechBucket 캐시)와
**완전 비결합**한 별도 팩토리다. 트렌드 히스토리는 다른 Format 셋(초록/빨강/무색
+ header)만 필요하므로 시트1 Format 캐시를 오염시키지 않도록 신설한다(Core Value 보호).

- `make_workbook`(시트1 팩토리)·`write_portfolio_sheet`는 import·호출 금지.
- 색 hex 상수(GREEN_100/GREEN_900/RED_100/RED_900)만 `color_rules`에서 import —
  함수(decide_*_bucket)·로직은 미참조(상수만, T-09-03 mitigate).

Format 셋(D-05/07):
  - green/red: 상대색 베이킹용 셀(bg+font+소수 2자리). 시트1 σ-bucket과 비결합.
  - plain   : 무색(D-07 표본 게이트 미충족·중위 셀).
  - header  : bold + center.
  - green_text/red_text/plain_text: YoY 글리프(" ▲"/" ▼")를 셀 텍스트에 결합하므로
    값을 문자열로 write 한다 — num_format(숫자 포맷) 미적용(RESEARCH 방법 A).
    WARNING-2(표시 정합): 비율 지표(GPM/OPM 등 is_ratio_0_1)는 Task 2에서 값 텍스트를
    `f"{v*100:.1f}%"`로 포맷해 시트1과 동일한 퍼센트 표기로 보이게 굽는다 → 텍스트
    셀이라 별도 percent num_format 불필요(표시 분기만, 신규 산식 아님).

워크북 옵션(writer.py L86-88 패턴 차용 — 직접 호출 금지):
  - constant_memory=False: 시트 작성 후 close까지 데이터 유지(합리적 워크북 크기).
    `[원천]` 시트가 수만 행으로 비대해지면 True 옵션화 검토 가능(기본 False).
  - nan_inf_to_errors=True: NaN/Inf 셀 도달 시 TypeError 대신 Excel 오류 셀 폴백.
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import xlsxwriter

from stocksig.compute.color_rules import (
    GREEN_100,
    GREEN_900,
    RED_100,
    RED_900,
)

# 상대색 셀 num_format (숫자 셀 — 텍스트 셀은 미적용).
_NUM_FORMAT = "#,##0.00"


def make_history_workbook(
    path: Union[str, Path], *, constant_memory: bool = False
) -> tuple[xlsxwriter.Workbook, dict]:
    """트렌드 히스토리 .xlsx Workbook + 트렌드 전용 Format 캐시 dict 반환.

    부모 디렉터리 자동 생성. 시트1 팩토리(`make_workbook`)와 비결합 — 색 상수만 공유.

    Args:
        path: 출력 .xlsx 경로.
        constant_memory: `[원천]` 시트가 수만 행이면 True 검토(기본 False).

    Returns:
        (wb, formats): wb는 xlsxwriter.Workbook, formats는
          green/red/plain/header + green_text/red_text/plain_text 키 dict.
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    wb = xlsxwriter.Workbook(
        str(p),
        {"constant_memory": constant_memory, "nan_inf_to_errors": True},
    )

    formats: dict = {}
    # 숫자 셀(상대색 베이킹) — 시트1 σ-bucket과 비결합.
    formats["green"] = wb.add_format(
        {
            "bg_color": GREEN_100,
            "font_color": GREEN_900,
            "num_format": _NUM_FORMAT,
            "bold": True,
        }
    )
    formats["red"] = wb.add_format(
        {
            "bg_color": RED_100,
            "font_color": RED_900,
            "num_format": _NUM_FORMAT,
            "bold": True,
        }
    )
    formats["plain"] = wb.add_format({"num_format": _NUM_FORMAT})  # 무색(D-07)

    # 텍스트 셀(YoY 글리프 결합 — 값 문자열 write, num_format 미적용 RESEARCH 방법 A).
    formats["green_text"] = wb.add_format(
        {"bg_color": GREEN_100, "font_color": GREEN_900, "bold": True}
    )
    formats["red_text"] = wb.add_format(
        {"bg_color": RED_100, "font_color": RED_900, "bold": True}
    )
    formats["plain_text"] = wb.add_format({})  # 무색 텍스트

    formats["header"] = wb.add_format({"bold": True, "align": "center"})

    return wb, formats
