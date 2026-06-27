"""SEC EDGAR 펀더멘털 클라이언트 — EntityFacts typed accessor + set_identity + throttle.

market.py 구조 복제: import-time singleton(set_identity 1회) + `@throttled_edgar`
페치. SPIKE-FINDINGS A1/A2/A7 확정 경로 사용.

Plan 10-03(FUND-11): 구 cache-first 페치 `fetch_edgar_cached`(7d `.cache/fundamentals`)는
시트1 단일 원천 이관으로 호출자가 사라져 제거됐다. store 경로 per-quarter 추출기
`fetch_edgar_quarterly_raw`(Phase 7)와 raw 추출기 `fetch_edgar_raw`는 유지된다.

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
import re

from edgar import Company, set_identity  # 주의: 패키지명 edgartools ≠ import 이름 edgar

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


# --- Plan 07-02: per-quarter raw 추출 (additive, 시트1 TTM 경로 불변 D-06) ---

# 유량(duration, by_period_length(3)): 손익 5종 + 영업현금흐름.
# (concept, 논리 field). EPS는 per-share 라 period_length 무관하지만 duration 으로 취득.
_EDGAR_DURATION_CONCEPTS: tuple[tuple[str, str], ...] = (
    ("Revenue", "revenue"),
    ("GrossProfit", "gross_profit"),
    ("OperatingIncomeLoss", "op_income"),
    ("NetIncomeLoss", "net_income"),
    ("EarningsPerShareDiluted", "eps"),
    ("NetCashProvidedByUsedInOperatingActivities", "operating_cash_flow"),
)

# 저량(instant): BS 항목 (D-04 신규 경로).
_EDGAR_INSTANT_CONCEPTS: tuple[tuple[str, str], ...] = (
    ("StockholdersEquity", "total_equity"),
    ("Liabilities", "total_liabilities"),
    ("Assets", "total_assets"),
)


def _calendar_quarter_key(fact) -> str | None:
    """FinancialFact.get_display_period_key() ("Q2 2026") → "2026Q2" (D-08 캘린더 분기).

    period 종료일 기준 캘린더 분기로 정규화된 키 사용 — fiscal≠calendar 기업도 일관 정렬.
    실패 시 None (호출부에서 skip).
    """
    key_fn = getattr(fact, "get_display_period_key", None)
    if not callable(key_fn):
        return None
    try:
        disp = key_fn()
    except Exception:  # noqa: BLE001 — 외부 객체, 키 산출 실패는 skip
        return None
    if not disp:
        return None
    disp = str(disp).strip()
    # "Q2 2026" → "2026Q2" / 이미 "2026Q2" 형식이면 그대로.
    parts = disp.split()
    if len(parts) == 2 and parts[0].startswith("Q") and parts[1].isdigit():
        disp = f"{parts[1]}{parts[0]}"
    elif len(parts) == 2 and parts[1].startswith("Q") and parts[0].isdigit():
        disp = f"{parts[0]}{parts[1]}"
    # 최종 게이트: 정확히 YYYYQn(연도 4자리 + Q + 1~4) 일 때만 통과. 그 외(예 "FY 2026")는
    # 분기 키가 아니므로 None — metrics_engine 분기축 int() 파싱 오염 차단(docstring '실패 시 None').
    return disp if re.fullmatch(r"\d{4}Q[1-4]", disp) else None


def _iso_or_none(value) -> str | None:
    """date/datetime/str → ISO 문자열, None-safe."""
    if value is None:
        return None
    iso_fn = getattr(value, "isoformat", None)
    if callable(iso_fn):
        return iso_fn()
    return str(value)


def _fact_to_row(ticker: str, field: str, fact, period_type: str) -> dict | None:
    """FinancialFact → raw 행 dict (D-08 quarter·accession·결손 None-safe).

    quarter 산출 실패 시 None 반환(호출부 skip).
    """
    quarter = _calendar_quarter_key(fact)
    if quarter is None:
        return None
    return {
        "ticker": ticker,
        "source": "EDGAR",
        "quarter": quarter,
        "field": field,
        "value": getattr(fact, "numeric_value", None),  # None-safe (D-05)
        "unit": getattr(fact, "unit", None),
        "accession": getattr(fact, "accession", None),
        "period_start": _iso_or_none(getattr(fact, "period_start", None)),
        "period_end": _iso_or_none(getattr(fact, "period_end", None)),
        "period_type": period_type,
        "reprt_code": None,
    }


def _query_facts(facts, concept: str, period_type: str, period_length: int | None):
    """facts.query() 빌더 실행 → list[FinancialFact]. 실패/빈 결과 시 빈 리스트."""
    try:
        q = facts.query().by_concept(concept).by_period_type(period_type)
        if period_length is not None:
            q = q.by_period_length(period_length)
        result = q.execute()
    except Exception:  # noqa: BLE001 — 외부 query 빌더, 결손은 빈 리스트로 흡수
        return []
    return list(result) if result else []


@throttled_edgar
def fetch_edgar_quarterly_raw(ticker: str) -> list[dict]:
    """EDGAR EntityFacts 에서 분기별 raw 행 리스트 추출 (Plan 07-02, FUND-07).

    D-01 (공짜 backfill): `Company(ticker).get_facts()` 1회만 호출 — EntityFacts 에
    과거 분기가 전부 딸려오므로 별도 호출 없이 전부 추출(추가 set_identity 없음).
    D-04 (신규 추출 경로): 손익 4종 + EPS + 영업현금흐름(duration) + BS 3종(instant).
    D-08: quarter 키는 period 종료일 기준 캘린더 분기 "YYYYQn".
    D-05: 결손 value=None (0/-999999 금지). as-reported 만 — Q4 보정·분기 분해 금지(Phase 8).

    Returns:
        list[dict] — 각 행: ticker/source="EDGAR"/quarter/field/value/unit/accession/
        period_start/period_end/period_type/reprt_code=None.
    """
    facts = Company(ticker).get_facts()  # D-01: get_facts 1회 (과거 분기 전부 포함)
    rows: list[dict] = []

    # 유량(duration, 분기 = period_length 3개월).
    for concept, field in _EDGAR_DURATION_CONCEPTS:
        for fact in _query_facts(facts, concept, "duration", 3):
            row = _fact_to_row(ticker, field, fact, "duration")
            if row is not None:
                rows.append(row)

    # 저량(instant, BS). [A5] concept 빈 결과 시 헬퍼 fallback.
    for concept, field in _EDGAR_INSTANT_CONCEPTS:
        instant_facts = _query_facts(facts, concept, "instant", None)
        if not instant_facts:
            instant_facts = _instant_fallback(facts, field)
        for fact in instant_facts:
            row = _fact_to_row(ticker, field, fact, "instant")
            if row is not None:
                rows.append(row)

    # 발행주식수: facts.shares_outstanding_fact 있으면 행 추가, 없으면 skip.
    shares_fact = getattr(facts, "shares_outstanding_fact", None)
    if shares_fact is not None:
        row = _fact_to_row(ticker, "shares_outstanding", shares_fact, "instant")
        if row is not None:
            rows.append(row)

    logger.info("%s | EDGAR 분기 raw 추출 완료 (%d행)", ticker, len(rows))
    return rows


def _instant_fallback(facts, field: str) -> list:
    """[A5] concept 빈 결과 시 EntityFacts 헬퍼 fallback (total_assets/shareholders_equity).

    헬퍼는 단일 스칼라만 반환할 수 있어 FinancialFact 리스트가 아니면 빈 리스트.
    """
    helper_name = {
        "total_assets": "get_total_assets",
        "total_equity": "get_shareholders_equity",
    }.get(field)
    if not helper_name:
        return []
    helper = getattr(facts, helper_name, None)
    if not callable(helper):
        return []
    try:
        result = helper()
    except Exception:  # noqa: BLE001
        return []
    # FinancialFact (numeric_value 보유) 만 행으로 사용. 스칼라는 quarter 산출 불가 → skip.
    if result is not None and hasattr(result, "numeric_value"):
        return [result]
    return []
