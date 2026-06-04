"""SEC EDGAR 펀더멘털 클라이언트 — EntityFacts typed accessor + set_identity + throttle + 7d cache.

market.py 구조 복제: import-time singleton(set_identity 1회) + `@throttled_edgar`
페치 + cache-first 페치 2함수. SPIKE-FINDINGS A1/A2/A7 확정 경로 사용.

확정 취득 경로(edgartools 5.35.0, A1 — `facts.to_pandas()` 부재):
    facts = Company(ticker).get_facts()                  # EntityFacts
    facts.get_ttm("EarningsPerShareDiluted").value       # EPS_TTM
    facts.get_ttm_revenue().value                        # Revenue
        (get_ttm("Revenues")는 stale FY 선택 → 사용 금지)
    facts.get_gross_profit()    -> float | None          # GOOGL None (GPM 폴백 트리거)
    facts.get_operating_income()

quarter_label(A7): EPS TTM 의 가장 최근 (year, "Qn") → "2026Q2".

set_identity(FUND-02): import-time 1회 "<이름> <이메일>" (per-call 금지, RESEARCH Anti-Pattern).
이메일은 config.load_env 의 EDGAR_USER_AGENT_EMAIL 사용(하드코딩 회피, T-03-07).
"""

from __future__ import annotations

import logging
import os

from edgar import Company, set_identity  # 주의: 패키지명 edgartools ≠ import 이름 edgar

from stocksig.io import cache
from stocksig.io.throttle import throttled_edgar

logger = logging.getLogger(__name__)

# SEC 정책상 UA 이름. 이메일은 .env(EDGAR_USER_AGENT_EMAIL)에서, 없으면 PROJECT.md 기본값.
_UA_NAME = "Yunjae Kim"
_DEFAULT_EMAIL = "yunjerrard@gmail.com"


def _resolve_identity() -> str:
    """`"<이름> <이메일>"` UA 문자열 — .env 이메일 우선(하드코딩 회피)."""
    email = os.environ.get("EDGAR_USER_AGENT_EMAIL") or _DEFAULT_EMAIL
    return f"{_UA_NAME} {email}"


# import-time 1회 set_identity (RESEARCH Anti-Pattern: per-call 금지).
_SET_IDENTITY_ARG = _resolve_identity()
set_identity(_SET_IDENTITY_ARG)


def _quarter_label(periods: list[tuple[int, str]] | None) -> str:
    """TTMMetric.periods 의 가장 최근 (year, "Qn") → "2026Q2" (A7)."""
    if not periods:
        return "UNKNOWN"
    year, q = periods[-1]
    return f"{year}{q}"


def _ttm_value(metric) -> float | None:
    """TTMMetric.value None-safe 추출."""
    if metric is None:
        return None
    return getattr(metric, "value", None)


@throttled_edgar
def fetch_edgar_raw(ticker: str) -> dict:
    """EDGAR EntityFacts 에서 EPS/Revenue/GrossProfit/OpIncome raw dict + quarter_label 산출.

    FUND-01. retry 는 edgartools 내부 처리에 위임(market.py 와 달리 생략).
    None-safe 가드 — 결손 지표는 None 으로 둔다(0/-999999 금지, D-05).

    Returns:
        {eps_ttm, eps_prior, revenue, gross_profit, op_income, quarter_label}.
        (eps_prior: 5.35.0 EntityFacts 에 전년 EPS TTM 의 확정 accessor 부재 → None.
         PEG 는 호출부에서 "전년 EPS 미존재" 사유로 안전 처리.)
    """
    facts = Company(ticker).get_facts()

    eps_metric = facts.get_ttm("EarningsPerShareDiluted")
    eps_ttm = _ttm_value(eps_metric)
    quarter_label = _quarter_label(getattr(eps_metric, "periods", None))

    revenue = _ttm_value(facts.get_ttm_revenue())
    gross_profit = facts.get_gross_profit()  # float | None (A2 결손 케이스)
    op_income = facts.get_operating_income()

    logger.info("%s | EDGAR facts 수신 완료", ticker)
    return {
        "eps_ttm": eps_ttm,
        "eps_prior": None,  # A2: 5.35.0 전년 EPS TTM accessor 미확정 → PEG yf 폴백 의존
        "revenue": revenue,
        "gross_profit": gross_profit,
        "op_income": op_income,
        "quarter_label": quarter_label,
    }


def fetch_edgar_cached(ticker: str, quarter_label: str) -> dict:
    """cache-first 페치 (market.py L89-102 패턴). 7d TTL, 키 "EDGAR|ticker|quarter"."""
    cached = cache.get_fund("EDGAR", ticker, quarter_label)
    if cached is not None:
        return cached
    raw = fetch_edgar_raw(ticker)
    cache.put_fund("EDGAR", ticker, quarter_label, raw)
    return raw
