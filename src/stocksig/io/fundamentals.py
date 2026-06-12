"""펀더멘털 오케스트레이터 — PER/PEG/GPM/OPM 산출 + 소스 라우팅 + provenance.

미국 종목(D-03)은 EDGAR 1차 → 결손된 *개별 지표만* yfinance.info 로 보완하고,
각 `MetricCell` 에 실제 사용 소스("EDGAR"|"yf")와 메타/사유 note 를 기록한다.
한국 종목(D-04)은 DART 1차 → metric별 차등 폴백:
    PER     → DART → Naver(`fetch_naver_per`, D-07 상한 내) → yf
    GPM/OPM → DART → yf            (Naver 미노출 — Open Q4, Naver 건너뜀)
    PEG     → DART(eps/eps_prior) → yf
각 `MetricCell.source` 에 실제 사용 소스("DART"|"Naver"|"yf") 를 기록한다.

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
    skip_edgar: bool = False,
) -> FundamentalsResult:
    """EDGAR 1차 → 결손 지표만 yf 보완 (per-metric provenance, D-03).

    skip_edgar=True (인증 실패) 면 EDGAR 1차 호출을 건너뛰고 모든 1차 지표를
    결손(note="EDGAR 인증 실패")으로 둔 뒤, yf 폴백은 그대로 실행한다 — yf 는
    EDGAR 와 독립 소스이므로 살린다 (A4 확정).
    """
    if skip_edgar:
        # EDGAR 1차 스킵 — raw 호출 없이 전 지표 결손(인증 실패 사유). yf 폴백은 유지.
        per = _empty_cell("EDGAR 인증 실패")
        peg = _empty_cell("EDGAR 인증 실패")
        gpm = _empty_cell("EDGAR 인증 실패")
        opm = _empty_cell("EDGAR 인증 실패")
    else:
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


# --- KR 라우팅 ----------------------------------------------------------

def _fill_kr(
    ticker: str,
    last_close: float,
    dart_fn: Callable[[str], dict],
    naver_fn: Callable[[str], float | None],
    yf_fn: Callable[[str], dict],
    skip_dart: bool = False,
) -> FundamentalsResult:
    """DART 1차 → metric별 차등 폴백 (PER: DART→Naver→yf; GPM/OPM: DART→yf), D-04.

    KR 산식(RESEARCH Pattern 4):
        PER = last_close(KRW) / eps(기본주당이익)
        PEG = _compute_peg(per, eps, eps_prior=전년 기본주당이익)
        GPM = 매출총이익 / 매출액
        OPM = 영업이익 / 매출액
    per-metric: 1차(DART)에서 채운 지표는 폴백으로 덮어쓰지 않음.
    Naver 는 PER 단일 지표 폴백 전용(D-07 상한은 naver_fn 내부에서 통제).

    skip_dart=True (인증 실패) 면 DART 1차 호출을 건너뛰고 전 지표를 결손
    (note="DART 인증 실패")으로 둔 뒤, Naver(PER)→yf 폴백 체인은 그대로 작동한다
    (독립 소스 유지, A4 확정).
    """
    if skip_dart:
        # DART 1차 스킵 — raw 호출 없이 전 지표 결손(인증 실패 사유). Naver/yf 폴백 유지.
        per = _empty_cell("DART 인증 실패")
        peg = _empty_cell("DART 인증 실패")
        gpm = _empty_cell("DART 인증 실패")
        opm = _empty_cell("DART 인증 실패")
    else:
        raw = dart_fn(ticker) or {}
        dart_note = raw.get("note")

        # 1차: DART 산식 (eps=기본주당이익 KRW, eps_prior=전년 기본주당이익).
        eps = raw.get("eps")
        eps_prior = raw.get("eps_prior")
        per = _compute_per(last_close, eps)
        peg = _compute_peg(per.value, eps, eps_prior)
        gpm = _compute_margin(raw.get("gross_profit"), raw.get("revenue"))
        opm = _compute_margin(raw.get("op_income"), raw.get("revenue"))

        # DART 로 채운 지표에 source/note 부여.
        for cell in (per, peg, gpm, opm):
            if cell.value is not None:
                cell.source = "DART"
                cell.note = dart_note or "DART"

    used = []  # 폴백 사용 경로 로그 누적.

    # 2차-A: PER 결손 → Naver(PER 단일 지표 폴백, D-07 상한 내).
    if per.value is None:
        naver_per = None
        try:
            naver_per = naver_fn(ticker)
        except Exception as e:  # Naver 폴백 예외 흡수 (결손 사유 유지)
            logger.info("%s | Naver 폴백 예외 흡수: %s", ticker, e)
            naver_per = None
        if naver_per is not None:
            per.value = float(naver_per)
            per.source = "Naver"
            per.note = "Naver"
            used.append("Naver")

    # 2차-B: 잔여 결손 지표만 yf 보완 (GPM/OPM 은 Naver 건너뜀 — yf 직행).
    missing = [c for c in (per, peg, gpm, opm) if c.value is None]
    if missing:
        yf_info: dict = {}
        try:
            yf_info = yf_fn(ticker) or {}
        except Exception as e:  # yf 폴백 실패 흡수 (1차/Naver 결손 사유 유지)
            logger.info("%s | yf 폴백 fetch 예외 흡수: %s", ticker, e)
            yf_info = {}
        for cell, key in ((per, "PER"), (peg, "PEG"), (gpm, "GPM"), (opm, "OPM")):
            if cell.value is None:
                v = yf_info.get(key)
                if v is not None:
                    cell.value = float(v)
                    cell.source = "yf"
                    cell.note = "yf"
                    if "yf" not in used:
                        used.append("yf")

    _log_kr_progress(ticker, per, peg, gpm, opm, used)
    return FundamentalsResult(per=per, peg=peg, gpm=gpm, opm=opm)


def _log_kr_progress(
    ticker: str,
    per: MetricCell,
    peg: MetricCell,
    gpm: MetricCell,
    opm: MetricCell,
    used: list[str],
) -> None:
    """한국어 진행 로그 — 폴백 경로 표기 (DART / DART→Naver / DART→yf / fund MISS)."""
    if all(c.value is None for c in (per, peg, gpm, opm)):
        logger.info("fund MISS %s", ticker)
    elif used:
        logger.info("fund OK %s (DART→%s)", ticker, "+".join(used))
    else:
        logger.info("fund OK %s (DART)", ticker)


# --- 진입점 -------------------------------------------------------------

def fetch_fundamentals(
    ticker: str,
    market: str,
    last_close: float,
    edgar_fn: Callable[[str], dict] | None = None,
    yf_fn: Callable[[str], dict] | None = None,
    dart_fn: Callable[[str], dict] | None = None,
    naver_fn: Callable[[str], float | None] | None = None,
    skip_edgar: bool = False,
    skip_dart: bool = False,
) -> FundamentalsResult:
    """티커 펀더멘털 fetch + 산식 + provenance. raise 금지 (전 경로 흡수).

    Args:
        ticker: yfinance 심볼 (예: "AAPL", "005930.KS").
        market: "US" | "KR" — 미지정 시 classify_market 로 재분류.
        last_close: PER 분자(주가) — 호출부가 enriched_df Close 최신값 주입.
        edgar_fn: EDGAR raw dict fetcher (US, 테스트 주입용; 기본 edgar_client).
        yf_fn: yf info fetcher (US/KR 최후 폴백, 테스트 주입용; 기본 yf_fundamentals).
        dart_fn: DART raw dict fetcher (KR 1차, 테스트 주입용; 기본 dart_client).
        naver_fn: Naver PER fetcher (KR 2차, 테스트 주입용; 기본 naver_scraper).
        skip_edgar: 인증 실패 시 EDGAR 1차 호출을 건너뛴다 (yf 폴백은 유지, A4).
        skip_dart: 인증 실패 시 DART 1차 호출을 건너뛴다 (Naver/yf 폴백은 유지, A4).

    Returns:
        FundamentalsResult — 결손 지표는 MetricCell.value=None + 사유 note.
    """
    resolved_market = market or classify_market(ticker)

    # 기본 클라이언트 lazy import (테스트는 콜러블 주입으로 우회).
    if yf_fn is None:
        from stocksig.io import yf_fundamentals

        yf_fn = yf_fundamentals.fetch_yf_info

    if resolved_market == "US":
        # skip_edgar=True 면 EDGAR raw 호출 자체를 건너뛰므로 기본 클라이언트 lazy
        # import 도 생략한다(_fill_us 가 edgar_fn 을 호출하지 않음).
        if edgar_fn is None and not skip_edgar:
            from stocksig.io import edgar_client

            def _default_edgar(t: str) -> dict:
                # FUND-04/SC4: 기본 경로도 7d 캐시(fetch_edgar_cached)를 타야 함.
                # quarter_label 추정 = 현재 분기 "YYYYQn" — 주 단위 안정이라 같은 주
                # 재실행 시 캐시 HIT. 실제 period_of_report 와 정확 일치 불필요(키는
                # 주 단위 안정성만 필요). 정밀 분기/접수번호 델타는 후속 '펀더멘털
                # 히스토리' phase 에서 교체(DART _default_dart 와 동일 패턴).
                import datetime as _dt

                _today = _dt.date.today()
                _q = (_today.month - 1) // 3 + 1
                return edgar_client.fetch_edgar_cached(t, f"{_today.year}Q{_q}")

            edgar_fn = _default_edgar
        try:
            return _fill_us(ticker, last_close, edgar_fn, yf_fn, skip_edgar=skip_edgar)
        except Exception as e:  # D-disc-10: 펀더멘털 결손 ≠ 티커 실패
            logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", ticker, e)
            return _empty_result(f"조회 실패: {e}")

    # KR 경로 (D-04: DART → Naver(PER) / yf(GPM/OPM·잔여) metric별 차등).
    # skip_dart=True 면 DART raw 호출 자체를 건너뛰므로 기본 클라이언트 lazy import 생략.
    if dart_fn is None and not skip_dart:
        from stocksig.io import dart_client

        def _default_dart(t: str) -> dict:
            # quarter_label = "{bsns_year}-{reprt_code}" (사업보고서 11011, A7).
            # 직전 회계연도 사업보고서를 1차 조회 (러너 연동은 후속 plan).
            import datetime as _dt

            year = _dt.date.today().year - 1
            return dart_client.fetch_dart_cached(t, f"{year}-11011")

        dart_fn = _default_dart
    if naver_fn is None:
        from stocksig.io import naver_scraper

        naver_fn = naver_scraper.fetch_naver_per

    try:
        return _fill_kr(
            ticker, last_close, dart_fn, naver_fn, yf_fn, skip_dart=skip_dart
        )
    except Exception as e:  # D-disc-10: 펀더멘털 결손 ≠ 티커 실패
        logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", ticker, e)
        return _empty_result(f"조회 실패: {e}")
