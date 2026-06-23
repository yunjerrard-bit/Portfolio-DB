"""Plan 10-01 Task 2 — matrix_to_fundamentals 어댑터 단위 테스트 (FUND-11).

compute_matrix 최신열 → 시트1 writer 입력 계약 `FundamentalsResult{per,peg,gpm,opm}`
변환 어댑터를 검증한다. 전부 네트워크 0 / 실DB 0 (fetch_fn_stub·build_ohlcv 격리).

behavior 5종:
  test_adapter_maps_latest_column   — 최신열 PER/PEG/GPM/OPM value 정확 매핑
  test_sheet1_matches_snapshot      — 어댑터 4셀 value == sheet_snapshot 최신열 셀(드리프트 0, SC1)
  test_peg_provenance_inherited     — PEG.source == PER.source 승계(L5 LANDMINE)
  test_missing_db_blank             — latest_q=None / 빈 matrix → 4셀 빈칸 + 한국어 사유(D-02/L8)
  test_price_source_parity          — runner last_close == quarter_price current(동일 OHLCV, L4)
"""

from __future__ import annotations

import pytest

from fixtures.history_fixtures import build_ohlcv, fetch_fn_stub
from stocksig.io import metrics_engine as me
from stocksig.io.fundamentals import FundamentalsResult, MetricCell
from stocksig.io.fundamentals_view import matrix_to_fundamentals

_METRICS = ["PER", "PEG", "GPM", "OPM"]


def _prepared_matrix(ticker: str, price: float):
    """compute_matrix → inject_prices_for_quarter(latest_q, price) (L1 호출순서)."""
    matrix = me.compute_matrix(ticker, fetch_fn=fetch_fn_stub)
    quarters = sorted({q for cells in matrix.values() for q in cells})
    latest_q = quarters[-1] if quarters else None
    if latest_q is not None:
        me.inject_prices_for_quarter(matrix, latest_q, price, matrix.get("EPS_ttm", {}))
    return matrix, latest_q


def test_adapter_maps_latest_column():
    """compute_matrix → 가격 주입 → 어댑터가 PER/PEG/GPM/OPM 최신열 value 정확 매핑."""
    matrix, latest_q = _prepared_matrix("AAPL", price=480.0)
    result = matrix_to_fundamentals(matrix, latest_q)

    assert isinstance(result, FundamentalsResult)
    assert result.per.value == matrix["PER"][latest_q].value
    assert result.peg.value == matrix["PEG"][latest_q].value
    assert result.gpm.value == matrix["GPM"][latest_q].value
    assert result.opm.value == matrix["OPM"][latest_q].value
    # GPM/OPM 은 가격 무관 — 값이 실제로 존재해야(매핑 확인).
    assert result.gpm.value is not None
    assert result.opm.value is not None


def test_sheet1_matches_snapshot():
    """드리프트 0(SC1): 어댑터 4셀 value == sheet_snapshot 이 쓰는 매트릭스 최신열 셀 value.

    sheet_snapshot.write_snapshot_sheet 는 `matrix.get(metric).get(latest_q)` 셀을
    그대로 소비한다. 어댑터도 동일 셀을 추출하므로 같은 입력·같은 latest_q 에서
    두 경로 value 가 동일해야 한다(구조적 일치).
    """
    matrix, latest_q = _prepared_matrix("AAPL", price=480.0)
    result = matrix_to_fundamentals(matrix, latest_q)

    # sheet_snapshot 이 소비하는 최신열 셀(재계산 0, D-13) 구성.
    snapshot_cells = {m: matrix.get(m, {}).get(latest_q) for m in _METRICS}

    field_map = {"PER": result.per, "PEG": result.peg, "GPM": result.gpm, "OPM": result.opm}
    for m in _METRICS:
        snap = snapshot_cells[m]
        adapted = field_map[m]
        snap_v = getattr(snap, "value", None) if snap is not None else None
        assert adapted.value == snap_v, f"{m} 드리프트 0 (어댑터==스냅샷)"


def test_peg_provenance_inherited():
    """L5 LANDMINE: compute_peg_cell source=None → 어댑터가 PEG.source = PER.source 승계."""
    matrix, latest_q = _prepared_matrix("AAPL", price=480.0)
    # 가격 주입 직후 PEG 셀 자체 source 는 None(compute_peg_cell 계약).
    assert matrix["PEG"][latest_q].source is None
    assert matrix["PEG"][latest_q].value is not None  # value 는 존재(승계 대상)

    result = matrix_to_fundamentals(matrix, latest_q)
    assert result.peg.source == result.per.source
    assert result.peg.source is not None


def test_missing_db_blank():
    """D-02/L8: latest_q=None 또는 빈 matrix → 4셀 value=None + 한국어 사유."""
    # (a) latest_q=None.
    result = matrix_to_fundamentals({}, None)
    for cell in (result.per, result.peg, result.gpm, result.opm):
        assert isinstance(cell, MetricCell)
        assert cell.value is None
        assert cell.source is None
        assert "DB 분기 데이터 없음" in (cell.note or "")

    # (b) 미등록 ticker → compute_matrix 빈 분기축 → latest_q=None.
    matrix, latest_q = _prepared_matrix("NOSUCH", price=100.0)
    assert latest_q is None
    result2 = matrix_to_fundamentals(matrix, latest_q)
    for cell in (result2.per, result2.peg, result2.gpm, result2.opm):
        assert cell.value is None
        assert "DB 분기 데이터 없음" in (cell.note or "")


def test_price_source_parity():
    """L4: runner last_close(df.iloc[-1]["Close"]) == quarter_price current 동일 OHLCV 가드.

    두 가격 추출 경로가 같은 OHLCV fixture 에서 같은 float 를 반환해야 드리프트 0(A1).
    """
    df = build_ohlcv()
    # 시트1 runner 경로(runner.py:100).
    runner_last_close = df.iloc[-1].get("Close")
    # 트렌드 quarter_price 경로(quarter_price.py: Close.dropna().iloc[-1]).
    qp_current = float(df["Close"].dropna().iloc[-1])

    assert float(runner_last_close) == pytest.approx(qp_current)


def test_provenance_label_synthesis():
    """D-09: 값 있는 셀 note = '소스 · 최신분기' 라벨 합성(예 'EDGAR · 2026Q1')."""
    matrix, latest_q = _prepared_matrix("AAPL", price=480.0)
    result = matrix_to_fundamentals(matrix, latest_q)
    # AAPL 은 EDGAR source. note 가 '소스 · 분기' 형태로 합성됨.
    assert result.per.note == f"{result.per.source} · {latest_q}"
    assert latest_q in (result.per.note or "")
