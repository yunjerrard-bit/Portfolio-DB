"""005930(삼성전자) DART finstate_all 반환 mock fixture (실데이터 기반).

OpenDartReader 0.3.x `dart.finstate_all("005930", 2025, reprt_code="11011",
fs_div="CFS")` 실호출 응답(229행)에서 손익계산서(IS)·포괄손익(CIS) 핵심 행만
축약.  [VERIFIED 2026-06-04]

확정 사실(A3/A6):
- 6자리 stock_code "005930" 직접 수용, corp_code(00126380) 내부 해석.  [A6 VERIFIED]
- 반환 컬럼 18종(아래 COLUMNS). `account_id`(표준 태그)가 `account_nm`(한글)보다
  안정적 매핑 키.  `fs_div` 컬럼은 응답에 채워지지 않음(None) — fs_div 는 요청 파라미터.
- `thstrm_amount` 는 쉼표 없는 digit 문자열("333605938000000").  단 일부 응답/항목은
  쉼표 포함 가능 → dart_client 는 항상 `.replace(",", "")` 후 int 파싱.
- EPS(기본주당이익) 단위 = 원, 정수 문자열("6605").
- status 필드는 finstate_all 의 DataFrame 반환에는 없음(빈 결과시 None/빈 df).
  쿼터초과("020")·데이터없음("013")은 라이브러리 내부에서 빈 결과로 표면화.

DataFrame 재구성:
  import pandas as pd
  from tests.fixtures.dart_005930_finstate import COLUMNS, IS_CIS_ROWS
  df = pd.DataFrame(IS_CIS_ROWS, columns=COLUMNS)
"""

from __future__ import annotations

# finstate_all 반환 DataFrame 컬럼 순서 (실응답)
COLUMNS: list[str] = [
    "rcept_no", "reprt_code", "bsns_year", "corp_code", "sj_div", "sj_nm",
    "account_id", "account_nm", "account_detail", "thstrm_nm", "thstrm_amount",
    "frmtrm_nm", "frmtrm_amount", "bfefrmtrm_nm", "bfefrmtrm_amount", "ord",
    "currency", "thstrm_add_amount",
]

# 공통 메타 (실응답)
_META = {
    "rcept_no": "20260310000000",
    "reprt_code": "11011",  # 사업보고서(연간)
    "bsns_year": "2025",
    "corp_code": "00126380",  # 005930 내부 해석된 corp_code [VERIFIED]
    "account_detail": "-",
    "thstrm_nm": "제57기",
    "frmtrm_nm": "제56기",
    "bfefrmtrm_nm": "제55기",
    "bfefrmtrm_amount": "",
    "ord": "0",
    "currency": "KRW",
    "thstrm_add_amount": "",
}


def _row(sj_div, sj_nm, account_id, account_nm, thstrm, frmtrm):
    r = dict(_META)
    r.update(
        sj_div=sj_div, sj_nm=sj_nm, account_id=account_id, account_nm=account_nm,
        thstrm_amount=thstrm, frmtrm_amount=frmtrm,
    )
    return [r[c] for c in COLUMNS]


# 손익계산서(IS) + 포괄손익(CIS) 핵심 행 — 005930 2025 사업보고서 연결 [VERIFIED]
IS_CIS_ROWS: list[list[str]] = [
    # account_nm="영업이익" / account_id=dart_OperatingIncomeLoss (주의: 라벨-id 매핑 확인)
    _row("IS", "손익계산서", "dart_OperatingIncomeLoss", "영업이익",
         "43601051000000", "32725961000000"),
    _row("IS", "손익계산서", "ifrs-full_Revenue", "매출액",
         "333605938000000", "300870903000000"),
    _row("IS", "손익계산서", "ifrs-full_CostOfSales", "매출원가",
         "202235513000000", "186562268000000"),
    _row("IS", "손익계산서", "ifrs-full_GrossProfit", "매출총이익",
         "131370425000000", "114308635000000"),
    _row("IS", "손익계산서", "ifrs-full_ProfitLoss", "당기순이익",
         "45206805000000", "34451351000000"),
    _row("IS", "손익계산서", "ifrs-full_ProfitLossAttributableToOwnersOfParent",
         "지배기업 소유주지분", "44260956000000", "33621363000000"),
    _row("IS", "손익계산서", "ifrs-full_BasicEarningsLossPerShare", "기본주당이익",
         "6605", "4950"),
    _row("IS", "손익계산서", "ifrs-full_DilutedEarningsLossPerShare", "희석주당이익",
         "6603", "4950"),
    # 포괄손익계산서에도 당기순이익(ProfitLoss) 존재 — IS 결손 시 CIS 폴백
    _row("CIS", "포괄손익계산서", "ifrs-full_ProfitLoss", "당기순이익",
         "45206805000000", "34451351000000"),
]

# 논리 지표 → 기대 정수값 (Wave 3 단위테스트 assert 용, thstrm 파싱 후)
EXPECTED_VALUES: dict[str, int] = {
    "revenue": 333_605_938_000_000,
    "gross_profit": 131_370_425_000_000,
    "op_income": 43_601_051_000_000,
    "net_income": 45_206_805_000_000,
    "eps": 6_605,  # 원
}

# 빈 결과(쿼터초과/데이터없음) 시나리오: finstate_all 이 빈 df 또는 None 반환
EMPTY_RESULT = None
