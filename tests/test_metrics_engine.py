"""metrics_engine RED 스캐폴드 + fetch_raw_quarters store 헬퍼 GREEN (FUND-09).

본 파일은 두 부분:
  1) store 입력 경로(fetch_raw_quarters) — **GREEN** (08-01에서 구현·검증).
  2) 08-03 Wave 2 엔진 계산 테스트 — **RED 스캐폴드**. `stocksig.io.metrics_engine`
     모듈이 아직 없으므로 본문은 `pytest.skip`으로 collect만 통과시킨다.
     08-03이 모듈을 채우면서 각 함수 본문을 실제 단언으로 교체한다.

-k 마커 ↔ RESEARCH Test Map(L449-454):
  test_type_rules               (SC2) 저량=최근/유량=TTM4합/하이브리드=분자TTM÷분모최근
  test_reproduce                (SC3) 저장 raw만으로 PER/PEG/GPM/OPM 재현 + ROE/PBR 신규
  test_ttm_missing              (SC4) TTM 4분기 결손 → 빈값+사유(0 대체·부분합산 금지, D-05)
  test_provenance_or_pershare   (SC5) per-metric provenance 라벨 + per-share 분모/가격 분리
  test_edgar_q4                 (Pitfall 1) EDGAR Q4 = 빈값+사유(FY raw 부재로 보정 불가)
"""

from __future__ import annotations

import pytest

from fixtures.raw_quarters import raw_row
from stocksig.io import fundamentals_store as fs
from stocksig.io import metrics_engine as me


def _to_fetch_row(r: tuple) -> tuple:
    """raw_row 12-tuple → fetch_raw_quarters 7-tuple 형태로 변환 (테스트 헬퍼).

    raw_row: ticker, source, quarter, field, value, unit, accession,
             period_start, period_end, period_type, reprt_code, fetched_at
    fetch_raw_quarters: quarter, source, field, value, period_type, reprt_code, unit
    """
    (_ticker, source, quarter, field, value, unit, _accession,
     _ps, _pe, period_type, reprt_code, _fetched) = r
    return (quarter, source, field, value, period_type, reprt_code, unit)


def _by_qf(rows: list[tuple]) -> dict:
    """raw_row 행 리스트 → metrics_engine 정규화 dict (테스트 헬퍼)."""
    return me._normalize_quarters([_to_fetch_row(r) for r in rows])


# === store 입력 경로 — GREEN (08-01 구현) ===================================


def test_fetch_raw_quarters_returns_sorted():
    """upsert한 2026Q1·2025Q4 revenue 행 → quarter 오름차순 list 반환."""
    fs.upsert_quarters(
        [
            raw_row(quarter="2026Q1", value=2000.0, accession="acc-q1"),
            raw_row(quarter="2025Q4", value=1000.0, accession="acc-q4"),
        ]
    )
    rows = fs.fetch_raw_quarters("AAPL")

    quarters = [r[0] for r in rows]
    assert quarters == ["2025Q4", "2026Q1"], "quarter 오름차순 정렬"

    # 각 행에 (quarter, source, field, value, period_type, reprt_code, unit) 포함.
    first = rows[0]
    assert len(first) == 7
    quarter, source, field, value, period_type, reprt_code, unit = first
    assert quarter == "2025Q4"
    assert source == "EDGAR"
    assert field == "revenue"
    assert value == 1000.0
    assert period_type == "duration"
    assert reprt_code is None
    assert unit == "USD"


def test_fetch_raw_quarters_empty():
    """미존재 ticker → 빈 list."""
    assert fs.fetch_raw_quarters("NOSUCH") == []


# === 엔진 계산 — RED 스캐폴드 (08-03이 채움) ================================


# --- Task 1: 분기 산술 + TTM 합 + 유형 코어 --------------------------------


def test_prior_4_quarters_boundary():
    """Pitfall 5: "YYYYQn" −N 산술, Q1→직전=전년 Q4 경계."""
    assert me._prior_4_quarters("2026Q1") == ["2026Q1", "2025Q4", "2025Q3", "2025Q2"]
    assert me._prior_4_quarters("2026Q3") == ["2026Q3", "2026Q2", "2026Q1", "2025Q4"]
    # _calendar_quarter_offset 단위 — Q1에서 1 빼면 전년 Q4.
    assert me._calendar_quarter_offset("2026Q1", -1) == "2025Q4"
    assert me._calendar_quarter_offset("2026Q1", -4) == "2025Q1"
    assert me._calendar_quarter_offset("2026Q4", 1) == "2027Q1"


def test_type_rules():
    """SC2: 저량=최근값 / 유량=TTM 4분기 합 / 하이브리드=분자TTM÷분모최근."""
    rows = [
        raw_row(quarter="2025Q2", field="revenue", value=100.0),
        raw_row(quarter="2025Q3", field="revenue", value=110.0),
        raw_row(quarter="2025Q4", field="revenue", value=120.0),
        raw_row(quarter="2026Q1", field="revenue", value=130.0),
        raw_row(quarter="2026Q1", field="total_equity", value=5000.0, period_type="instant"),
        raw_row(quarter="2025Q4", field="total_equity", value=4000.0, period_type="instant"),
    ]
    raw = _by_qf(rows)

    # 저량(STOCK) = 해당 분기 시점값.
    assert me._recent(raw, "total_equity", "2026Q1") == 5000.0
    assert me._recent(raw, "total_equity", "2025Q4") == 4000.0

    # 유량(FLOW_TTM) = 직전 4분기 합.
    assert me._ttm_sum(raw, "revenue", "2026Q1") == 100.0 + 110.0 + 120.0 + 130.0


def test_ttm_missing():
    """SC4: TTM 4분기 중 결손 → None 반환 (0 대체·부분합산 금지, D-05)."""
    rows = [
        raw_row(quarter="2025Q2", field="revenue", value=100.0),
        raw_row(quarter="2025Q3", field="revenue", value=None),  # 결손
        raw_row(quarter="2025Q4", field="revenue", value=120.0),
        raw_row(quarter="2026Q1", field="revenue", value=130.0),
    ]
    raw = _by_qf(rows)
    # 4분기 중 1개 None → 전체 None (3개 합산 안 됨, 0 대체 안 됨).
    assert me._ttm_sum(raw, "revenue", "2026Q1") is None

    # 분기 자체가 raw에 부재(자연 결손)해도 None.
    rows2 = [
        raw_row(quarter="2025Q4", field="revenue", value=120.0),
        raw_row(quarter="2026Q1", field="revenue", value=130.0),
    ]
    assert me._ttm_sum(_by_qf(rows2), "revenue", "2026Q1") is None


def test_dart_quarter_semantics_applied():
    """08-01 확정: DART thstrm_amount=분기 단독값 → 단순 4분기 합 = TTM (YTD 분해 없음)."""
    rows = [
        raw_row(quarter="2025Q2", source="DART", field="net_income", value=10.0, reprt_code="11012"),
        raw_row(quarter="2025Q3", source="DART", field="net_income", value=20.0, reprt_code="11014"),
        raw_row(quarter="2025Q4", source="DART", field="net_income", value=30.0, reprt_code="11011"),
        raw_row(quarter="2026Q1", source="DART", field="net_income", value=40.0, reprt_code="11013"),
    ]
    raw = _by_qf(rows)
    # 단순 4분기 합 (누적 분해 없음 — 08-01 방침).
    assert me._ttm_sum(raw, "net_income", "2026Q1") == 100.0


def test_edgar_q4():
    """Pitfall 1: EDGAR Q4 손익 raw 부재 → 해당 TTM 자연 결손(빈값), FY−9M 보정 미수행."""
    # EDGAR 저장 키 Q1~Q3만 (캘린더 Q4 손익 duration 부재 — 08-01 확정).
    rows = [
        raw_row(quarter="2025Q1", field="revenue", value=100.0),
        raw_row(quarter="2025Q2", field="revenue", value=110.0),
        raw_row(quarter="2025Q3", field="revenue", value=120.0),
        # 2025Q4 부재.
        raw_row(quarter="2026Q1", field="revenue", value=130.0),
    ]
    raw = _by_qf(rows)
    # 2026Q1 TTM = [2026Q1, 2025Q4, 2025Q3, 2025Q2] → 2025Q4 부재 → None (보정 없음).
    assert me._ttm_sum(raw, "revenue", "2026Q1") is None


# --- Task 2: compute_matrix + per-share + sanity + provenance ---------------


def _four_q_revenue(field="revenue", base=100.0, source="EDGAR"):
    """2025Q2~2026Q1 동일 field 4분기 행 (TTM 산출용)."""
    return [
        raw_row(quarter=q, field=field, value=base, source=source)
        for q in ("2025Q2", "2025Q3", "2025Q4", "2026Q1")
    ]


def test_compute_matrix_shape():
    """D-06: compute_matrix → {metric: {quarter: MetricCell}} 분기 매트릭스 전체."""
    rows = [
        *_four_q_revenue("revenue", 1000.0),
        *_four_q_revenue("gross_profit", 400.0),
    ]
    matrix = me.compute_matrix("AAPL", fetch_fn=lambda t: [_to_fetch_row(r) for r in rows])

    # REGISTRY 9종 + 주당 분모 4종 = 13 metric 모두 키 존재.
    assert "GPM" in matrix and "ROE" in matrix and "PER" in matrix and "PEG" in matrix
    # 최신 분기 열 존재.
    assert "2026Q1" in matrix["GPM"]
    # GPM = gross_profit TTM / revenue TTM = 1600/4000 = 0.4.
    assert matrix["GPM"]["2026Q1"].value == pytest.approx(0.4)


def test_reproduce():
    """SC3: 저장 raw만으로 GPM/OPM 재현 + ROE 신규 — 외부 재호출 0."""
    rows = [
        *_four_q_revenue("revenue", 1000.0),
        *_four_q_revenue("gross_profit", 400.0),
        *_four_q_revenue("op_income", 250.0),
        *_four_q_revenue("net_income", 200.0),
        raw_row(quarter="2026Q1", field="total_equity", value=8000.0, period_type="instant"),
    ]
    called = {"n": 0}

    def _fetch(t):
        called["n"] += 1
        return [_to_fetch_row(r) for r in rows]

    matrix = me.compute_matrix("AAPL", fetch_fn=_fetch)
    assert called["n"] == 1, "fetch는 1회만 (외부 재호출 0, D-06)"

    assert matrix["GPM"]["2026Q1"].value == pytest.approx(0.4)
    assert matrix["OPM"]["2026Q1"].value == pytest.approx(0.25)
    # ROE = net_income TTM(800) / total_equity 최근(8000) = 0.1 (HYBRID, D-03).
    assert matrix["ROE"]["2026Q1"].value == pytest.approx(0.1)


def test_new_metrics():
    """SC3: ROE/ROA/PBR 신규 — 동일 원천 즉시 산출. PBR 분모=BPS=total_equity/shares."""
    rows = [
        *_four_q_revenue("net_income", 200.0),
        raw_row(quarter="2026Q1", field="total_equity", value=8000.0, period_type="instant"),
        raw_row(quarter="2026Q1", field="total_assets", value=16000.0, period_type="instant"),
        raw_row(quarter="2026Q1", field="shares_outstanding", value=100.0, period_type="instant"),
    ]
    matrix = me.compute_matrix("AAPL", fetch_fn=lambda t: [_to_fetch_row(r) for r in rows])

    assert matrix["ROE"]["2026Q1"].value == pytest.approx(800.0 / 8000.0)
    assert matrix["ROA"]["2026Q1"].value == pytest.approx(800.0 / 16000.0)
    # BPS = total_equity 최근(8000) / shares(100) = 80.
    assert matrix["BPS"]["2026Q1"].value == pytest.approx(80.0)
    # PBR 셀은 compute_cell 단독으로는 비계산(가격 의존, D-07).
    assert matrix["PBR"]["2026Q1"].value is None
    # 가격 주입 시 price_ratio로 PBR 산출 = price(160) / BPS(80) = 2.0.
    pbr = me.price_ratio(matrix["BPS"]["2026Q1"], 160.0)
    assert pbr.value == pytest.approx(2.0)


def test_provenance_or_pershare():
    """SC5/D-08: provenance 혼합 "+"결합 + per-share 분모/가격 분리(D-07)."""
    # net_income은 EDGAR, shares는 yf → EPS_ttm source = "EDGAR+yf".
    rows = [
        *_four_q_revenue("net_income", 200.0, source="EDGAR"),
        raw_row(quarter="2026Q1", field="shares_outstanding", value=100.0,
                period_type="instant", source="yf"),
    ]
    matrix = me.compute_matrix("AAPL", fetch_fn=lambda t: [_to_fetch_row(r) for r in rows])

    eps = matrix["EPS_ttm"]["2026Q1"]
    assert eps.value == pytest.approx(800.0 / 100.0)
    assert eps.source == "EDGAR+yf", "혼합 provenance 정렬 + 결합"

    # PER 셀 자체는 비율 미계산(D-07) — 호출자가 가격 주입.
    assert matrix["PER"]["2026Q1"].value is None
    per = me.price_ratio(matrix["EPS_ttm"]["2026Q1"], 80.0)
    assert per.value == pytest.approx(10.0)
    assert per.source == "EDGAR+yf"


def test_sanity_bounds():
    """D-05: sanity 범위 밖 → 빈값+사유(0 아님)."""
    # GPM = gross_profit TTM(8000) / revenue TTM(4000) = 2.0 > 1.5 상한 → 빈값.
    rows = [
        *_four_q_revenue("revenue", 1000.0),
        *_four_q_revenue("gross_profit", 2000.0),
    ]
    matrix = me.compute_matrix("AAPL", fetch_fn=lambda t: [_to_fetch_row(r) for r in rows])
    cell = matrix["GPM"]["2026Q1"]
    assert cell.value is None
    assert "sanity" in (cell.note or "")


def test_shares_missing_pershare():
    """Pitfall 4: shares_outstanding 결손 → per-share 분모 빈값+'발행주식수' 사유."""
    rows = [*_four_q_revenue("net_income", 200.0)]  # shares 행 없음.
    matrix = me.compute_matrix("AAPL", fetch_fn=lambda t: [_to_fetch_row(r) for r in rows])
    eps = matrix["EPS_ttm"]["2026Q1"]
    assert eps.value is None
    assert "발행주식수" in (eps.note or "")


def test_price_ratio_negative_denom():
    """PCR: 분모(OCF_ps) ≤ 0 → 빈값+사유 (가격 주입 게이트)."""
    neg = me.MetricCell(value=-5.0, source="EDGAR", note=None)
    out = me.price_ratio(neg, 100.0)
    assert out.value is None
    assert "분모" in (out.note or "")
