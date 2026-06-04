"""DART finstate_all → 논리 지표명 매핑 상수 (실데이터 확정).

03-02 스파이크에서 OpenDartReader 0.3.x로 005930(삼성전자, 2025 사업보고서,
reprt_code="11011", fs_div="CFS") 1회 실호출하여 확정.  [VERIFIED 2026-06-04]

매핑 전략(실데이터 기반):
- **1차 키 = `account_id`** (예: `ifrs-full_Revenue`). DART가 IFRS/DART 표준
  account_id를 부여하며 `account_nm`(한글 라벨)보다 업종·종목 간 안정적이다.
  삼성전자 응답에서 account_nm은 회사 재량 라벨이지만 account_id는 표준 태그였다.
- **2차 키 = `account_nm`** (한글 문자열). account_id가 비표준(`-표준계정 미분류`
  등)일 때 한글 라벨로 폴백 매칭. 업종별 표기차를 흡수하기 위해 후보 tuple.

dart_client(Wave 3)는 두 dict를 차례로 조회: 먼저 account_id 정확매칭,
실패 시 account_nm 후보 매칭. `writer.py` `_NUM_FORMAT_MAP` 모듈 상수 스타일.

확정된 005930 2025 IS 값(KRW, thstrm_amount):
  매출액=333,605,938,000,000 / 매출원가=202,235,513,000,000
  매출총이익=131,370,425,000,000 / 영업이익=43,601,051,000,000
  당기순이익(ProfitLoss)=45,206,805,000,000 / 기본주당이익=6,605

주의: `thstrm_amount`는 문자열이다. 본 응답에서는 쉼표 없는 순수 digit 문자열
("333605938000000")이었으나, OpenDART 일부 응답/항목은 쉼표 포함 가능
("333,605,938,000,000") — dart_client는 항상 `s.replace(",", "")` 후 int 파싱.
EPS(기본주당이익)는 원 단위 정수 문자열("6605").
"""

from __future__ import annotations

# 1차 매핑: DART account_id(표준 태그) → 논리 지표명.
# 005930 실응답에서 확인된 정확 account_id. ifrs-full_* / dart_* 두 네임스페이스 공존.
DART_ACCOUNT_ID_MAP: dict[str, tuple[str, ...]] = {
    "revenue": (
        "ifrs-full_Revenue",  # 005930 매출액 [VERIFIED]
        "ifrs-full_RevenueFromSaleOfGoods",
        "dart_OperatingRevenue",  # 영업수익(금융·서비스업)
    ),
    "gross_profit": (
        "ifrs-full_GrossProfit",  # 005930 매출총이익 [VERIFIED]
    ),
    "op_income": (
        "dart_OperatingIncomeLoss",  # 005930 영업이익 [VERIFIED]
        "ifrs-full_ProfitLossFromOperatingActivities",
    ),
    "net_income": (
        "ifrs-full_ProfitLoss",  # 005930 당기순이익 [VERIFIED]
        "ifrs-full_ProfitLossAttributableToOwnersOfParent",
    ),
    "eps": (
        "ifrs-full_BasicEarningsLossPerShare",  # 005930 기본주당이익 [VERIFIED]
    ),
}

# 2차 매핑: account_nm(한글 라벨) → 논리 지표명. account_id 미매칭 시 폴백.
# 005930 실데이터 + 업종별 표기 후보(RESEARCH Pattern 4 시드 병합).
DART_ACCOUNT_MAP: dict[str, tuple[str, ...]] = {
    "revenue": ("매출액", "수익(매출액)", "영업수익", "매출"),  # 005930=매출액 [VERIFIED]
    "gross_profit": ("매출총이익",),  # 005930=매출총이익 [VERIFIED]
    "op_income": ("영업이익", "영업이익(손실)"),  # 005930=영업이익 [VERIFIED]
    "net_income": (
        "당기순이익",  # 005930=당기순이익 [VERIFIED]
        "당기순이익(손실)",
        "지배기업 소유주지분",
    ),
    "eps": ("기본주당이익", "기본주당순이익"),  # 005930=기본주당이익 [VERIFIED]
}

# 매출총이익 미표기(금융업 등) 시 GPM 결손 → yf 폴백 신호용 키 목록.
# net_income/eps 가 손익계산서(IS)에 없으면 포괄손익계산서(CIS)에도 ProfitLoss 존재.
SJ_DIV_INCOME_STATEMENT: tuple[str, ...] = ("IS", "CIS")
