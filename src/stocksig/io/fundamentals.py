"""펀더멘털 오케스트레이터 — PER/PEG/GPM/OPM 산출 + 소스 라우팅 + provenance.

미국 종목(D-03)은 EDGAR 1차 → 결손된 *개별 지표만* yfinance.info 로 보완하고,
각 `MetricCell` 에 실제 사용 소스("EDGAR"|"yf")와 메타/사유 note 를 기록한다.
한국 종목(D-04)은 03-04 에서 같은 `fetch_fundamentals` 함수에 확장 예정 —
본 plan 은 US 경로만 완성하고 KR 은 빈 결과 placeholder 로 둔다.

데이터 모델은 runner.py L34-49 `TickerResult`/`TickerFailure` dataclass 스타일,
라우팅은 `classify_market`(market_kind), 폴백 격리는 try/except 흡수
(D-disc-10: 펀더멘털 결손 ≠ 티커 실패).

PEG 산식(RESEARCH Pattern 3 확정식 + 엣지케이스 4종):
    growth_pct = (eps_ttm / eps_prior - 1) * 100
    peg        = per / growth_pct        (growth_pct > 0 일 때만)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from stocksig.io.market_kind import classify_market

logger = logging.getLogger(__name__)


@dataclass
class MetricCell:
    """단일 지표 셀 — 값 + 출처 라벨 + 메타/사유 note.

    - value: 산출값 (None = 결손; 0/-999999 금지, D-05).
    - source: "EDGAR" | "yf" | None (실제 사용 소스).
    - note: "EDGAR · 2026Q2" 같은 메타 또는 "조회 실패: <사유>" 한국어 사유.
    """

    value: float | None
    source: str | None
    note: str | None


@dataclass
class FundamentalsResult:
    """시트1 우측 4셀(PER/PEG/GPM/OPM)에 대응하는 펀더멘털 결과."""

    per: MetricCell
    peg: MetricCell
    gpm: MetricCell
    opm: MetricCell


def _empty_cell(note: str | None = None) -> MetricCell:
    return MetricCell(value=None, source=None, note=note)


def _empty_result(note: str | None = None) -> FundamentalsResult:
    """전 지표 결손 placeholder (예외 흡수·KR 미구현 등)."""
    return FundamentalsResult(
        per=_empty_cell(note),
        peg=_empty_cell(note),
        gpm=_empty_cell(note),
        opm=_empty_cell(note),
    )


# --- 순수 산식 헬퍼 ------------------------------------------------------

def _compute_per(last_close: float | None, eps_ttm: float | None) -> MetricCell:
    """PER = last_close / eps_ttm. eps_ttm None → 미존재, ≤0 → EPS ≤ 0."""
    if eps_ttm is None:
        return _empty_cell("조회 실패: EPS TTM 미존재")
    if eps_ttm <= 0:
        return _empty_cell("조회 실패: EPS ≤ 0")
    if last_close is None:
        return _empty_cell("조회 실패: 종가 미존재")
    return MetricCell(value=last_close / eps_ttm, source=None, note=None)


def _compute_peg(
    per: float | None,
    eps_ttm: float | None,
    eps_prior: float | None,
) -> MetricCell:
    """PEG = PER / ((eps_ttm/eps_prior − 1)×100). 엣지케이스 4종 빈값+한국어 사유."""
    if per is None:
        return _empty_cell("조회 실패: PER 없음")
    if eps_prior is None:
        return _empty_cell("조회 실패: 전년 EPS 미존재")
    if eps_prior == 0:
        return _empty_cell("조회 실패: 전년 EPS 0")
    if eps_ttm is None:
        return _empty_cell("조회 실패: EPS TTM 미존재")
    growth_pct = (eps_ttm / eps_prior - 1) * 100
    if growth_pct <= 0:
        return _empty_cell("조회 실패: EPS 성장률 ≤ 0")
    return MetricCell(value=per / growth_pct, source=None, note=None)


def _compute_margin(numer: float | None, denom: float | None) -> MetricCell:
    """마진 = numer / denom (0~1 비율). 분모 0/None 또는 분자 None → 빈값+사유."""
    if numer is None:
        return _empty_cell("조회 실패: 분자 미존재")
    if denom is None or denom == 0:
        return _empty_cell("조회 실패: 매출(분모) 미존재")
    return MetricCell(value=numer / denom, source=None, note=None)


# --- US 라우팅 ----------------------------------------------------------

def _fill_us(
    ticker: str,
    last_close: float,
    edgar_fn: Callable[[str], dict],
    yf_fn: Callable[[str], dict],
) -> FundamentalsResult:
    """EDGAR 1차 → 결손 지표만 yf 보완 (per-metric provenance, D-03)."""
    raw = edgar_fn(ticker)
    quarter = raw.get("quarter_label") or "?"
    edgar_meta = f"EDGAR · {quarter}"

    # 1차: EDGAR 산식
    per = _compute_per(last_close, raw.get("eps_ttm"))
    peg = _compute_peg(per.value, raw.get("eps_ttm"), raw.get("eps_prior"))
    gpm = _compute_margin(raw.get("gross_profit"), raw.get("revenue"))
    opm = _compute_margin(raw.get("op_income"), raw.get("revenue"))

    # EDGAR 로 채운 지표에 source/note 부여
    for cell in (per, peg, gpm, opm):
        if cell.value is not None:
            cell.source = "EDGAR"
            cell.note = edgar_meta

    # 2차: EDGAR 결손 *개별 지표만* yf 보완 (1차 채운 지표는 덮어쓰지 않음)
    missing = [c for c in (per, peg, gpm, opm) if c.value is None]
    used_yf = False
    if missing:
        yf_info: dict = {}
        try:
            yf_info = yf_fn(ticker) or {}
        except Exception as e:  # yf 폴백 실패는 흡수 (1차 결손 사유 유지)
            logger.warning("%s | yf 폴백 fetch 예외 흡수: %s", ticker, e)
            yf_info = {}
        for cell, key in ((per, "PER"), (peg, "PEG"), (gpm, "GPM"), (opm, "OPM")):
            if cell.value is None:
                v = yf_info.get(key)
                if v is not None:
                    cell.value = float(v)
                    cell.source = "yf"
                    cell.note = "yf"
                    used_yf = True

    _log_progress(ticker, used_yf)
    return FundamentalsResult(per=per, peg=peg, gpm=gpm, opm=opm)


def _log_progress(ticker: str, used_yf: bool) -> None:
    """한국어 진행 로그 (runner L114 형식 차용)."""
    if used_yf:
        logger.info("fund OK %s (EDGAR→yf)", ticker)
    else:
        logger.info("fund OK %s (EDGAR)", ticker)


# --- 진입점 -------------------------------------------------------------

def fetch_fundamentals(
    ticker: str,
    market: str,
    last_close: float,
    edgar_fn: Callable[[str], dict] | None = None,
    yf_fn: Callable[[str], dict] | None = None,
) -> FundamentalsResult:
    """티커 펀더멘털 fetch + 산식 + provenance. raise 금지 (전 경로 흡수).

    Args:
        ticker: yfinance 심볼 (예: "AAPL", "005930.KS").
        market: "US" | "KR" — 미지정 시 classify_market 로 재분류.
        last_close: PER 분자(주가) — 호출부가 enriched_df Close 최신값 주입.
        edgar_fn: EDGAR raw dict fetcher (테스트 주입용; 기본 edgar_client).
        yf_fn: yf info fetcher (테스트 주입용; 기본 yf_fundamentals).

    Returns:
        FundamentalsResult — 결손 지표는 MetricCell.value=None + 사유 note.
    """
    resolved_market = market or classify_market(ticker)

    if resolved_market != "US":
        # KR 경로는 03-04 에서 같은 함수에 확장 (SCOPE 축소 아님, placeholder).
        return _empty_result("KR 미구현 (03-04 예정)")

    # 기본 클라이언트 lazy import (테스트는 콜러블 주입으로 우회).
    if edgar_fn is None:
        from stocksig.io import edgar_client

        def _default_edgar(t: str) -> dict:
            # quarter_label 결정 후 cache-first fetch.
            raw = edgar_client.fetch_edgar_raw(t)
            return raw

        edgar_fn = _default_edgar
    if yf_fn is None:
        from stocksig.io import yf_fundamentals

        yf_fn = yf_fundamentals.fetch_yf_info

    try:
        return _fill_us(ticker, last_close, edgar_fn, yf_fn)
    except Exception as e:  # D-disc-10: 펀더멘털 결손 ≠ 티커 실패
        logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", ticker, e)
        return _empty_result(f"조회 실패: {e}")
