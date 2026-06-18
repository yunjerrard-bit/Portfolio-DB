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
    # --- D-03 슈퍼셋 신규 BS/CF 필드 (Plan 07-02, additive) ---
    # [Open Q2 — 005930 BS/CF 실응답 1회 확정 후 VERIFIED]
    "total_equity": (
        "ifrs-full_Equity",  # 자본총계(지배+비지배)
        "ifrs-full_EquityAttributableToOwnersOfParent",  # 지배기업 소유주지분 자본
    ),
    "total_liabilities": (
        "ifrs-full_Liabilities",  # 부채총계
    ),
    "total_assets": (
        "ifrs-full_Assets",  # 자산총계(총자산)
    ),
    "operating_cash_flow": (
        "ifrs-full_CashFlowsFromUsedInOperatingActivities",  # 영업활동현금흐름
    ),
    # 발행주식수: finstate_all 에 통상 부재(Open Q2 RESOLVED).
    # 매핑 키만 placeholder 로 둔다 — finstate_all 부재 시 Phase 8 또는 yf 보완으로
    # 위임하며, 본 plan 에서는 별도 API 호출을 추가하지 않는다(D-03 슈퍼셋 결손=None).
    "shares_outstanding": (
        "ifrs-full_NumberOfSharesOutstanding",  # placeholder — finstate_all 통상 부재
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
    # --- D-03 슈퍼셋 신규 BS/CF 한글 라벨 폴백 (Plan 07-02, additive) ---
    # [Open Q2 — 005930 BS/CF 실응답 1회 확정 후 VERIFIED]
    "total_equity": ("자본총계", "자본총계(지배+비지배)", "자본총계 (지배+비지배)"),
    "total_liabilities": ("부채총계",),
    "total_assets": ("자산총계",),
    "operating_cash_flow": ("영업활동현금흐름", "영업활동으로 인한 현금흐름"),
    # 발행주식수: finstate_all 부재 시 Phase 8 또는 yf 보완으로 위임(본 plan API 호출 없음).
    "shares_outstanding": ("발행주식수", "유통주식수"),
}

# 매출총이익 미표기(금융업 등) 시 GPM 결손 → yf 폴백 신호용 키 목록.
# net_income/eps 가 손익계산서(IS)에 없으면 포괄손익계산서(CIS)에도 ProfitLoss 존재.
SJ_DIV_INCOME_STATEMENT: tuple[str, ...] = ("IS", "CIS")

# D-04 신규 추출 경로 sj_div 필터 (Plan 07-02).
# 재무상태표(BS) = 저량(instant): 자본총계·부채총계·총자산.
# 현금흐름표(CF) = 유량(duration): 영업활동현금흐름.
SJ_DIV_BALANCE_SHEET: tuple[str, ...] = ("BS",)
SJ_DIV_CASHFLOW: tuple[str, ...] = ("CF",)
