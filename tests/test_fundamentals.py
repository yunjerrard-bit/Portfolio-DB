"""Phase 3 Wave 3 (03-03 Task 1): fundamentals.py 공유 계약 — 순수 산식 헬퍼.

순수 산식 헬퍼(PER/PEG/마진)와 WR-01 NaN 결손 게이트를 검증한다.

Plan 10-03(FUND-11): 구 fetch 오케스트레이터(`fetch_fundamentals`/`_fill_us`/
`_fill_kr` + EDGAR/DART 직접 fetch + 7일 캐시)가 시트1 store/registry 단일 원천
이관으로 제거되며, 해당 라우팅·폴백·skip·예외흡수 테스트도 함께 제거됐다. 본
파일은 이제 **보존 계약(D-04)** — `_compute_per`/`_compute_peg`/`_compute_margin`
산식과 `_is_missing` NaN 게이트만 단언한다(metrics_engine 가 `_compute_peg` 를
import 재사용 + 어댑터가 동일 셀 계약을 소비).
"""

from __future__ import annotations

from stocksig.io.fundamentals import (
    _compute_margin,
    _compute_peg,
    _compute_per,
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


# --- WR-01: NaN 결손 가드 (NaN 을 None 과 동일하게 결손 처리) ------------------
# runner.process_ticker 가 주입하는 last_close = df.iloc[-1].get("Close") 가 장중
# 부분 행 등으로 NaN 일 수 있다. NaN 은 비교(<=0 등)가 모두 False 라 기존 `is None`
# 가드를 통과해 값 있는 셀·provenance 로 새므로(D-05 위반), _is_missing 단일 게이트로
# 차단해야 한다. 외부 의존 없이 float("nan") 직접 사용.

def test_compute_per_last_close_nan():
    cell = _compute_per(last_close=float("nan"), eps_ttm=8.0)
    assert cell.value is None
    assert "종가" in (cell.note or "")


def test_compute_per_eps_nan():
    # NaN EPS 가 ≤0 비교(False)로 새지 않고 결손으로 차단.
    cell = _compute_per(last_close=100.0, eps_ttm=float("nan"))
    assert cell.value is None


def test_compute_peg_per_nan():
    # NaN PER 이 _compute_peg 로 전파돼 값 있는 셀이 되지 않는다.
    cell = _compute_peg(per=float("nan"), eps_ttm=10.0, eps_prior=8.0)
    assert cell.value is None


def test_compute_peg_eps_nan():
    cell = _compute_peg(per=12.5, eps_ttm=float("nan"), eps_prior=8.0)
    assert cell.value is None


def test_compute_margin_nan():
    cell = _compute_margin(numer=float("nan"), denom=100.0)
    assert cell.value is None
    cell2 = _compute_margin(numer=40.0, denom=float("nan"))
    assert cell2.value is None
