"""raw-data 의미 진실 확정 spike (Phase 8 산식 선행 — FUND-09).

네트워크 호출 0 — 기존 저장 fixture(`dart_005930_finstate.py`/`edgar_aapl_facts.py`)의
*재현 가능한 실응답*만 읽어, 산식의 옳고 그름을 좌우하는 2개 raw-data 진실을 단언·박제한다.
(RESEARCH Pitfall 1·2, Open Q1·Q2, Assumptions A1·A2, State of the Art)

============================================================================
확정 1: DART 손익 thstrm_amount = 분기 단독값 (누적은 thstrm_add_amount)
============================================================================
OpenDART 개발가이드 DS003(단일회사 전체 재무제표) [CITED]:
  - 분/반기 손익(IS/CIS)의 `thstrm_amount` = 해당 분기 **3개월 단독값**.
  - 손익의 *누적값*은 별도 컬럼 `thstrm_add_amount`에 담긴다.
  - 005930 실응답 fixture에서 `thstrm_add_amount`는 빈 문자열("")로,
    누적 표현이 thstrm_amount와 분리돼 있음을 교차 확인한다.

→ 08-03 엔진 산식 방침 (DART TTM):
  DART도 EDGAR처럼 **단순 4분기 thstrm_amount 합 = TTM**.
  YTD(누적) 분해(thisQ누적 − 직전Q누적) 작업은 **불필요** —
  08-03 엔진은 YTD 분해 로직을 미구현한다. (STATE 가정 "DART YTD 분해" 철회)

============================================================================
확정 2: EDGAR raw에 캘린더 Q4 손익 단독값·FY duration 부재
============================================================================
미국 10-K는 연간(FY, 12개월 duration)만 XBRL 보고 — Q4 3개월 duration fact가
존재하지 않는다. 현 추출기는 `by_period_length(3)`만 저장 → Q4 단독값도 FY값도
raw에 없다 (Pitfall 1, Assumption A2). AAPL fixture의 분기 store에는
캘린더 Q4(연 마지막 분기) revenue 행이 부재함을 단언한다.

→ 08-03 엔진 산식 방침 (EDGAR Q4):
  Q4 유량 지표 = **빈값+사유**(D-05 일관, 0/-999999 대체 금지).
  Q4 = FY − 9M 보정은 FY duration raw 부재로 수행 불가 →
  08-03 엔진은 Q4 보정 로직을 미구현하며, Q4 행은 자연 결손으로 둔다.
  FY duration 저장 추가는 본 범위 밖(Phase 7 추출 수정 = scope 경계).
"""

from __future__ import annotations

from fixtures.dart_005930_finstate import (
    COLUMNS,
    IS_CIS_ROWS,
    _META,
)
from fixtures.edgar_aapl_facts import AAPL_QUARTERLY_STORE


def _dart_field(account_id: str) -> dict:
    """IS_CIS_ROWS에서 account_id 행을 찾아 컬럼명→값 dict로 반환."""
    idx = COLUMNS.index("account_id")
    for row in IS_CIS_ROWS:
        if row[idx] == account_id:
            return dict(zip(COLUMNS, row))
    raise AssertionError(f"account_id={account_id} 행이 fixture에 없음")


def test_dart_quarter_semantics():
    """확정 1: DART thstrm_amount = 분기 단독값 (누적은 thstrm_add_amount).

    DS003 공식 가이드 + 005930 실응답 fixture를 교차 단언:
      - thstrm_amount는 쉼표 없는 digit 문자열 → int 파싱 가능(분기/연 손익 값).
      - 누적 컬럼 thstrm_add_amount는 별도 컬럼으로 존재하며, 본 응답에선 빈값("")
        — 즉 분기 단독값(thstrm_amount)과 누적(thstrm_add_amount)이 분리돼 있다.
    이 분리가 "thstrm_amount=분기 단독값" 진실의 fixture 근거다.
    """
    revenue = _dart_field("ifrs-full_Revenue")
    # thstrm_amount는 분기/기간 손익의 단독값(누적 아님) — 쉼표 제거 후 int 파싱.
    amt = int(revenue["thstrm_amount"].replace(",", ""))
    assert amt == 333_605_938_000_000, "005930 매출 thstrm_amount 실값 [VERIFIED]"

    # 누적값은 thstrm_amount가 아닌 thstrm_add_amount에 담긴다(DS003).
    # fixture(단일 보고서)에서는 add_amount가 빈 문자열 → 두 의미가 분리돼 있음을 확정.
    assert "thstrm_add_amount" in COLUMNS, "DART 응답은 누적 전용 컬럼을 별도로 가진다"
    assert _META["thstrm_add_amount"] == "", (
        "thstrm_amount(분기 단독값)와 thstrm_add_amount(누적)는 분리된 컬럼 — "
        "thstrm_amount는 누적이 아닌 분기/기간 단독값(DS003)"
    )

    # 손익 IS 행 다수가 동일 의미(분기 단독값)로 일관 — 매출/영업이익/순이익 교차.
    op_income = _dart_field("dart_OperatingIncomeLoss")
    net_income = _dart_field("ifrs-full_ProfitLoss")
    assert int(op_income["thstrm_amount"]) == 43_601_051_000_000
    assert int(net_income["thstrm_amount"]) == 45_206_805_000_000


def test_edgar_q4_gap_absent():
    """확정 2: EDGAR raw에 캘린더 Q4 손익 단독값·FY duration 부재.

    by_period_length(3) 추출 결과(분기 store)에는 캘린더 Q4(연 마지막 분기)
    revenue duration 행이 없고, FY(12개월) duration 행도 저장되지 않음 →
    Q4 단독값으로 Q4 유량 지표를 채울 raw가 영구 부재함을 단언한다.
    """
    revenue_duration = AAPL_QUARTERLY_STORE[("Revenue", "duration")]
    # 저장된 분기 키 = get_display_period_key() ("Q{n} {year}").
    period_keys = {fact.get_display_period_key() for fact in revenue_duration}

    # 캘린더 Q4(연 마지막 분기) 단독 duration 행 부재.
    q4_keys = {k for k in period_keys if k.startswith("Q4 ")}
    assert q4_keys == set(), (
        f"EDGAR raw에 캘린더 Q4 손익 단독값이 없어야 함 (Pitfall 1) — 발견: {q4_keys}"
    )

    # FY(12개월) duration도 분기 store에 미저장 — period_type='duration' 행은
    # 전부 3개월 분기값이며 FY 키("FY"/"12M" 등)가 없다.
    fy_keys = {k for k in period_keys if "FY" in k or "12M" in k}
    assert fy_keys == set(), (
        f"EDGAR raw에 FY duration이 미저장이어야 함 (Q4=FY−9M 보정 불가) — 발견: {fy_keys}"
    )

    # 저장된 키는 분기값만(Q1·Q2 등) — Q4 보정 raw 갭 확정.
    assert period_keys, "분기 revenue duration 행 자체는 존재(Q1/Q2)"
    assert all(k[:2] in {"Q1", "Q2", "Q3"} for k in period_keys), (
        f"저장 raw는 Q1~Q3 분기값만 — Q4는 자연 결손 → 08-03 빈값+사유 방침 (D-05). 키: {period_keys}"
    )
