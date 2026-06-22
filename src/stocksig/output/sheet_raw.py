"""[원천] raw long 시트 writer (Plan 09-02, D-12 provenance 중심).

`fetch_raw_quarters(ticker)` 가 돌려주는 **7-tuple**
`(quarter, source, field, value, period_type, reprt_code, unit)` 을 long 행으로 펼친다
(period_end/accession 미포함 — store SELECT 컬럼 제외, RESEARCH Runtime State).
provenance(source 열)가 중심인 검증 시트이며, 값 결손은 "-" 로 일관(D-11).

종목 순서는 호출자(Plan 03)가 정한 `sorted_tickers` 순서를 그대로 따른다.
"""

from __future__ import annotations

from stocksig.io.fundamentals import _is_missing

# 한국어 헤더 — 7-tuple 컬럼 대응.
_RAW_HEADERS: list[str] = [
    "티커",
    "소스",
    "분기",
    "필드",
    "값",
    "기간유형",
    "보고서코드",
    "단위",
]


def write_raw_sheet(ws, raw_by_ticker: dict, formats: dict, sorted_tickers=None) -> None:
    """[원천] long 시트 작성.

    Args:
        ws: 대상 worksheet.
        raw_by_ticker: {ticker: list[7-tuple]} — `fetch_raw_quarters` 결과 모음.
        formats: 트렌드 Format 캐시(header 사용).
        sorted_tickers: 종목 정렬 순서(호출자 주입). None 이면 raw_by_ticker 키 순서.
    """
    for col, name in enumerate(_RAW_HEADERS):
        ws.write(0, col, name, formats["header"])

    tickers = sorted_tickers if sorted_tickers is not None else list(raw_by_ticker)

    row = 1
    for ticker in tickers:
        for r in raw_by_ticker.get(ticker, []):
            quarter, source, field, value, period_type, reprt_code, unit = r
            ws.write_string(row, 0, str(ticker))
            ws.write_string(row, 1, str(source) if source is not None else "-")
            ws.write_string(row, 2, str(quarter) if quarter is not None else "-")
            ws.write_string(row, 3, str(field) if field is not None else "-")
            # 값 결손 → "-" 일관(D-11).
            if _is_missing(value):
                ws.write_string(row, 4, "-")
            else:
                ws.write_number(row, 4, float(value))
            ws.write_string(row, 5, str(period_type) if period_type is not None else "-")
            ws.write_string(row, 6, str(reprt_code) if reprt_code is not None else "-")
            ws.write_string(row, 7, str(unit) if unit is not None else "-")
            row += 1
