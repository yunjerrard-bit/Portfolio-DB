"""260701 Q4 도출 TDD — 추출단계 `Q4(3M) = annual − 9M` + TTM 복구 (네트워크 0).

근본원인(확정): EDGAR 회계 Q4 3M fact 부재 → by_period_type("quarterly") 갭 →
metrics_engine._ttm_sum 4분기 결손 불관용(D-05) → TTM 및 전 파생 지표 연쇄 None.

수정(추출단계, locked (a)): edgar_client.fetch_edgar_quarterly_raw 가 annual(12M)·9M YTD
fact 를 추가 추출해 `Q4 = annual − 9M` 을 도출, 갭 캘린더 분기키에 저장한다. metrics_engine
은 0줄 수정(_normalize_quarters 가 (quarter,field)만 키로 소비 → 무변경으로 4연속 분기 인식).

단언은 **구조값**만(렌더텍스트 금지, 코드베이스 컨벤션):
  - 도출 Q4 행이 갭 분기(2025Q4)에 존재하고 value == annual − 9M.
  - 도출 행은 as-reported 와 구분되는 provenance 라벨(period_type != "duration").
  - 도출 분기키가 기존 3M 분기(Q1~Q3)와 충돌하지 않음.
  - 세그먼트(차원) fact 는 도출에 쓰이지 않음(비차원 총액만).
  - 도출 Q4 를 store 에 넣고 compute_matrix 로 계산 시 최신분기 TTM 이 복구됨.
"""

from __future__ import annotations

from fixtures.edgar_q4_derive import (
    NI_ANNUAL,
    NI_Q4_EXPECTED,
    REV_Q4_EXPECTED,
    make_facts,
)


def _patch(mocker):
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    mock_company.return_value.get_facts.return_value = make_facts()
    return mock_company


def test_derived_q4_row_fills_gap_quarter(mocker):
    """도출 Q4(3M) 행이 갭 분기 2025Q4 에 존재하고 value == annual − 9M."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOG")

    ni_q4 = [r for r in rows if r["field"] == "net_income" and r["quarter"] == "2025Q4"]
    assert ni_q4, "도출 net_income 2025Q4(갭) 행 존재"
    assert ni_q4[-1]["value"] == NI_Q4_EXPECTED, "Q4 = annual − 9M 정합"

    rev_q4 = [r for r in rows if r["field"] == "revenue" and r["quarter"] == "2025Q4"]
    assert rev_q4, "도출 revenue 2025Q4(갭) 행 존재"
    assert rev_q4[-1]["value"] == REV_Q4_EXPECTED


def test_derived_row_has_distinct_provenance(mocker):
    """도출 Q4 행은 as-reported(period_type='duration')와 구분되는 라벨을 가진다."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOG")

    ni_q4 = [r for r in rows if r["field"] == "net_income" and r["quarter"] == "2025Q4"]
    assert ni_q4
    # as-reported 3M 은 "duration". 도출 Q4 는 그와 달라야 함(예 "derived").
    assert ni_q4[-1]["period_type"] != "duration", "도출 행 provenance 구분"
    # as-reported 3M(Q1~Q3)은 여전히 "duration" 유지(회귀 없음).
    ni_q1 = [r for r in rows if r["field"] == "net_income" and r["quarter"] == "2025Q1"]
    assert ni_q1 and ni_q1[-1]["period_type"] == "duration"


def test_derived_q4_no_collision_with_reported_quarters(mocker):
    """도출 분기키(2025Q4)가 기존 as-reported 3M 분기(2025Q1~Q3)와 충돌하지 않음."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOG")

    ni = {r["quarter"] for r in rows if r["field"] == "net_income"}
    assert {"2025Q1", "2025Q2", "2025Q3", "2025Q4"} <= ni, "4연속 분기 완성"
    # 2025Q4 는 도출 1건만(3M as-reported 부재였으므로 중복 아님).
    ni_q4_reported = [
        r for r in rows
        if r["field"] == "net_income" and r["quarter"] == "2025Q4"
        and r["period_type"] == "duration"
    ]
    assert not ni_q4_reported, "갭 분기에 as-reported 3M 행 없음(도출만)"


def test_segment_fact_not_used_for_derivation(mocker):
    """세그먼트(차원) annual fact 는 도출에 쓰이지 않음 — 비차원 총액만."""
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOG")

    ni_q4 = [r for r in rows if r["field"] == "net_income" and r["quarter"] == "2025Q4"]
    assert ni_q4
    # 세그먼트 annual(5B)을 썼다면 Q4 = 5B − 9M(음수) 이 됐을 것 → 비차원 총액(127B) 사용 확인.
    assert ni_q4[-1]["value"] == NI_Q4_EXPECTED
    assert ni_q4[-1]["value"] > 0


def test_ttm_recovers_after_q4_derivation(mocker):
    """도출 Q4 로 4연속 분기 완성 → metrics_engine TTM 복구(엔진 0줄, 구조값 단언)."""
    from stocksig.io import metrics_engine as me
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    _patch(mocker)
    rows = fetch_edgar_quarterly_raw("GOOG")

    # 추출 raw dict → fetch_raw_quarters 7-tuple 형태로 변환(엔진 입력 계약).
    fetch_rows = [
        (r["quarter"], r["source"], r["field"], r["value"],
         r["period_type"], r["reprt_code"], r["unit"])
        for r in rows
    ]
    raw_by_qf = me._normalize_quarters(fetch_rows)

    # 2025Q4 TTM 윈도 = [2025Q4, 2025Q3, 2025Q2, 2025Q1] — 갭이 도출로 메워져 4개 모두 존재.
    ni_ttm = me._ttm_sum(raw_by_qf, "net_income", "2025Q4")
    assert ni_ttm is not None, "도출 Q4 로 net_income TTM 복구(더 이상 None 아님)"
    # TTM = 연간(FY2025) 과 정합(4분기 합 == annual).
    assert ni_ttm == NI_ANNUAL

    rev_ttm = me._ttm_sum(raw_by_qf, "revenue", "2025Q4")
    assert rev_ttm is not None


def test_derivation_skips_when_annual_or_nine_missing(mocker):
    """annual 또는 9M fact 부재 시 도출 안 함(조용한 except 미부활·빈값 자연 처리)."""
    from fixtures.edgar_q4_derive import Q4_DERIVE_STORE
    from stocksig.io.edgar_client import fetch_edgar_quarterly_raw

    # 9M 을 제거한 store 복제 — revenue 는 9M 없음 → revenue Q4 도출 불가.
    store = dict(Q4_DERIVE_STORE)
    store[("Revenue", "ytd9")] = []
    mock_company = mocker.patch("stocksig.io.edgar_client.Company")
    from fixtures.edgar_aapl_facts import FakeQuarterlyFacts
    mock_company.return_value.get_facts.return_value = FakeQuarterlyFacts(store)

    rows = fetch_edgar_quarterly_raw("GOOG")
    rev_q4 = [r for r in rows if r["field"] == "revenue" and r["quarter"] == "2025Q4"]
    assert not rev_q4, "9M 부재 → revenue Q4 도출 skip(예외 없음)"
    # net_income 은 annual·9M 온전 → 여전히 도출됨.
    ni_q4 = [r for r in rows if r["field"] == "net_income" and r["quarter"] == "2025Q4"]
    assert ni_q4, "net_income 은 정상 도출(부분 결손 격리)"
