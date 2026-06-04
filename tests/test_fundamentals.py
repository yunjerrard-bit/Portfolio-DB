"""Phase 3 Wave 3 (03-03 Task 1): fundamentals.py 데이터모델 + PEG 산식 + US 라우팅.

순수 산식 헬퍼(PER/PEG/마진)와 `fetch_fundamentals` US 라우팅을 mock 주입으로 검증.
edgar/yf 호출은 `edgar_fn`/`yf_fn` 콜러블 주입(test_runner.py L23-41 analog)으로
네트워크 없이 격리. PEG 엣지케이스 4종(성장률≤0/0분모/전년없음/PER없음) +
per-metric 폴백(EDGAR→yf) provenance + 예외 흡수를 단언.
"""

from __future__ import annotations

from stocksig.io.fundamentals import (
    FundamentalsResult,
    MetricCell,
    _compute_margin,
    _compute_peg,
    _compute_per,
    fetch_fundamentals,
)


# --- 순수 산식 헬퍼 ------------------------------------------------------

def test_compute_per_normal():
    cell = _compute_per(last_close=100.0, eps_ttm=8.0)
    assert cell.value == 12.5
    assert cell.note is None


def test_compute_per_eps_none():
    cell = _compute_per(last_close=100.0, eps_ttm=None)
    assert cell.value is None
    assert "EPS" in (cell.note or "")


def test_compute_per_eps_non_positive():
    cell = _compute_per(last_close=100.0, eps_ttm=0.0)
    assert cell.value is None
    assert "EPS" in (cell.note or "")
    cell2 = _compute_per(last_close=100.0, eps_ttm=-2.0)
    assert cell2.value is None


def test_compute_peg_normal():
    # PER=12.5, eps_ttm=10, eps_prior=8 → growth=(10/8-1)*100=25 → PEG=0.5
    cell = _compute_peg(per=12.5, eps_ttm=10.0, eps_prior=8.0)
    assert cell.value == 0.5
    assert cell.note is None


def test_compute_peg_growth_non_positive():
    # eps_ttm < eps_prior → growth ≤ 0 → 빈값 + 사유
    cell = _compute_peg(per=12.5, eps_ttm=8.0, eps_prior=10.0)
    assert cell.value is None
    assert "성장률" in (cell.note or "")


def test_compute_peg_zero_prior():
    cell = _compute_peg(per=12.5, eps_ttm=10.0, eps_prior=0.0)
    assert cell.value is None
    assert "전년 EPS 0" in (cell.note or "")


def test_compute_peg_prior_none():
    cell = _compute_peg(per=12.5, eps_ttm=10.0, eps_prior=None)
    assert cell.value is None
    assert "전년 EPS 미존재" in (cell.note or "")


def test_compute_peg_per_none():
    cell = _compute_peg(per=None, eps_ttm=10.0, eps_prior=8.0)
    assert cell.value is None
    assert "PER 없음" in (cell.note or "")


def test_compute_margin_normal():
    cell = _compute_margin(numer=40.0, denom=100.0)
    assert cell.value == 0.4
    assert cell.note is None


def test_compute_margin_denom_zero():
    cell = _compute_margin(numer=40.0, denom=0.0)
    assert cell.value is None
    cell2 = _compute_margin(numer=40.0, denom=None)
    assert cell2.value is None


def test_compute_margin_numer_none():
    cell = _compute_margin(numer=None, denom=100.0)
    assert cell.value is None


# --- fetch_fundamentals US 라우팅 (mock 주입) ---------------------------

def _edgar_full():
    """EDGAR 전지표 채움 raw dict + quarter_label."""
    return {
        "eps_ttm": 8.07,
        "eps_prior": 6.40,
        "revenue": 451_442_000_000.0,
        "gross_profit": 195_201_000_000.0,
        "op_income": 133_050_000_000.0,
        "quarter_label": "2026Q2",
    }


def test_fetch_fundamentals_all_edgar():
    # ① EDGAR 전지표 채움 → source 전부 EDGAR
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: _edgar_full(),
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    assert res.per.value is not None
    assert res.per.source == "EDGAR"
    assert res.gpm.source == "EDGAR"
    assert res.opm.source == "EDGAR"
    assert res.peg.source == "EDGAR"
    # quarter 메타가 note에 들어감
    assert "2026Q2" in (res.per.note or "")


def test_fallback_chain():
    # ② EDGAR GPM 결손 → yf 보완 (GPM source=yf, 나머지 EDGAR) — FUND-05
    edgar_missing_gpm = {
        "eps_ttm": 8.07,
        "eps_prior": 6.40,
        "revenue": 451_442_000_000.0,
        "gross_profit": None,  # GOOGL 결손 케이스
        "op_income": 133_050_000_000.0,
        "quarter_label": "2026Q2",
    }
    yf_info = {"PER": 30.0, "PEG": 2.0, "GPM": 0.478, "OPM": 0.32}
    res = fetch_fundamentals(
        "GOOGL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar_missing_gpm,
        yf_fn=lambda t: yf_info,
    )
    # GPM만 yf로 채워짐
    assert res.gpm.value == 0.478
    assert res.gpm.source == "yf"
    # 나머지는 EDGAR 유지 (덮어쓰기 금지)
    assert res.per.source == "EDGAR"
    assert res.opm.source == "EDGAR"


def test_fetch_fundamentals_peg_growth_non_positive():
    # ③ PEG 성장률 ≤ 0 → 빈값 + 사유
    edgar = dict(_edgar_full(), eps_ttm=6.0, eps_prior=8.0)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.peg.value is None
    assert "성장률" in (res.peg.note or "")


def test_fetch_fundamentals_peg_zero_prior():
    # ④ PEG 0분모
    edgar = dict(_edgar_full(), eps_prior=0.0)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.peg.value is None
    assert "전년 EPS 0" in (res.peg.note or "")


def test_fetch_fundamentals_peg_prior_none():
    # ⑤ PEG 전년 EPS None
    edgar = dict(_edgar_full(), eps_prior=None)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.peg.value is None
    assert "전년 EPS 미존재" in (res.peg.note or "")


def test_fetch_fundamentals_per_eps_non_positive():
    # ⑥ PER eps≤0 → 빈값
    edgar = dict(_edgar_full(), eps_ttm=0.0)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.per.value is None


def test_fetch_fundamentals_absorbs_exception():
    # stub 예외 주입 시 raise 없이 빈 FundamentalsResult 반환 (흡수)
    def _boom(t):
        raise RuntimeError("edgar 폭발")

    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=_boom,
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    assert res.per.value is None
    assert res.peg.value is None
    assert res.gpm.value is None
    assert res.opm.value is None
