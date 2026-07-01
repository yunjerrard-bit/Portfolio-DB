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

# 유량(quarterly): 손익 5종 + 영업현금흐름. (concept, 논리 field).
# 260629-hec(edgartools 5.35.0): by_period_type("quarterly")로 조회한다. quarterly 는
# 내부적으로 by_period_length(3)에 위임되므로(LOCKED FACT 3) 별도 length 필터는 제거.
# 조회된 fact 자체의 period_type 은 여전히 'duration' 이라 저장 라벨은 "duration" 유지.
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

# 260701(Q4 도출): 손익 유량 concept 중 회계 Q4 3M fact 부재로 캘린더 갭이 생기는 것들.
# EDGAR 는 회계 Q4 를 3M 단독으로 제공하지 않고 10-K 의 연간(12M)만 제공 → 캘린더상 매년
# 한 분기 영구 결손(_ttm_sum D-05 불관용으로 TTM 연쇄 None). 추출단계에서
# `Q4(3M) = annual(12M) − 9M(YTD)` 로 도출해 갭 분기를 메운다(엔진 0줄, locked (a)).
# EPS 는 분기 EPS 를 단순 뺄셈으로 도출하면 주식수 변동 시 왜곡 → 제외(EPS_ttm 은 registry
# 에서 net_income TTM ÷ 최근 shares 로 계산, A4). OCF 는 3M 단독 fact 자체가 희소(YTD 누계)
# 라 Q4 도출만으로 완전 복구되진 않으나(별건) 도출 Q4 값은 정확하므로 포함해 부분 개선.
_EDGAR_Q4_DERIVE_CONCEPTS: tuple[tuple[str, str], ...] = (
    ("Revenue", "revenue"),
    ("GrossProfit", "gross_profit"),
    ("OperatingIncomeLoss", "op_income"),
    ("NetIncomeLoss", "net_income"),
    ("NetCashProvidedByUsedInOperatingActivities", "operating_cash_flow"),
)

# 도출 Q4 provenance 라벨 — as-reported("duration")·저량("instant")과 구분(D-05 정신,
# "as-reported 만" 원칙과 명시적 분리). metrics_engine._normalize_quarters 는 (quarter,field)
# 만 키로 쓰므로 이 라벨은 엔진 소비에 무영향(store·엔진 0줄 수정으로 그대로 통과).
_DERIVED_PERIOD_TYPE = "derived"

# 260701(커밋2): shares_outstanding us-gaap 폴백 concept.
# facts.shares_outstanding_fact(dei:EntityCommonStockSharesOutstanding)는 종목당 1행 또는
# 0행(concept 부재)만 적재 → per-share 분모 결손. dei 부재 시 us-gaap 분기별 instant
# concept 을 폴백으로 추출해 분기별 shares 확보(PER_SHARE/가격의존 분모 복구, 백로그 근본원인3).
# 순서 = 선호도(먼저 값이 있는 concept 채택). WeightedAverage* 는 EPS 계산에 쓰이는 가중평균
# 발행주식수로, 시점 발행주식수(CommonStockSharesOutstanding)가 없을 때의 차선책.
_EDGAR_SHARES_FALLBACK_CONCEPTS: tuple[str, ...] = (
    "CommonStockSharesOutstanding",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
    "WeightedAverageNumberOfSharesOutstandingBasic",
)


def _quarter_key_from_period_end(period_end) -> str | None:
    """fact.period_end(종료일) 월 기준 캘린더 분기 "YYYYQn" 산출. 파싱 실패 시 None.

    260629-hec(D-08 진실원천): period 종료일의 캘린더 월 → (month-1)//3+1 분기.
    period_end 는 str("2026-03-28")·date 객체 양쪽 모두 안전 파싱(앞 7자 "YYYY-MM" 슬라이스).
    """
    if period_end is None:
        return None
    text = str(period_end).strip()
    # "YYYY-MM..." 앞 7자만 사용(ISO date/datetime 공통). 길이/형식 미달 시 None.
    if len(text) < 7 or text[4] != "-":
        return None
    try:
        year = int(text[0:4])
        month = int(text[5:7])
    except ValueError:
        return None
    if not (1 <= month <= 12):
        return None
    quarter = (month - 1) // 3 + 1
    return f"{year}Q{quarter}"


def _calendar_quarter_key(fact) -> str | None:
    """FinancialFact → 캘린더 분기 "YYYYQn" (D-08, period_end 종료일 월 기준).

    260629-hec(edgartools 5.35.0): 키 소스를 period_end 우선으로 교체 —
    `(month-1)//3+1` 로 캘린더 분기 산출(fiscal≠calendar 기업도 일관 정렬).
    period_end 부재/파싱 실패 시 기존 get_display_period_key() 차선책으로 폴백.
    최종 게이트: 정확히 YYYYQn 일 때만 통과(예 "FY 2026"·비분기 입력 → None) —
    metrics_engine 분기축 int() 파싱 오염 차단. 실패 시 None (호출부에서 skip).
    """
    # 1순위: period_end 종료일 월 기반 캘린더 분기.
    pe_key = _quarter_key_from_period_end(getattr(fact, "period_end", None))
    if pe_key is not None:
        return pe_key  # 이미 "YYYYQn" 형식 보장(_quarter_key_from_period_end)

    # 차선책: get_display_period_key() ("Q2 2026") → "2026Q2" 정규화.
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
        # 260629-hec(LOCKED FACT 6): 중복 (quarter, field) 정렬 전용. store 12-tuple
        # 변환(_rows_to_tuples)은 고정 키만 읽으므로 DB 컬럼으로 새지 않는다.
        "filing_date": _iso_or_none(getattr(fact, "filing_date", None)),
    }


def _query_facts(facts, concept: str, period_type: str | None = None):
    """facts.query() 빌더 실행 → list[FinancialFact]. 실패/빈 결과 시 빈 리스트.

    260629-hec(edgartools 5.35.0):
      - period_type 가 주어지면 by_period_type(period_type) 적용(유량="quarterly").
        "quarterly" 는 내부적으로 by_period_length(3)에 위임(LOCKED FACT 3)이라 별도
        length 필터 호출은 제거(중복).
      - period_type 가 None 이면 by_period_type 를 건너뛰고 by_concept→execute 만 수행
        (저량 BS — 호출부에서 파이썬 instant 필터 적용, LOCKED FACT 5).
      - 예외는 더 이상 조용히 삼키지 않고 concept·예외타입을 WARNING 로깅(향후 API
        어휘 변경 가시화, T-hec-02). 결손은 여전히 빈 리스트(추출 전체는 죽지 않음).
    """
    try:
        q = facts.query().by_concept(concept)
        if period_type is not None:
            q = q.by_period_type(period_type)
        result = q.execute()
    except Exception as exc:  # noqa: BLE001 — 외부 query 빌더, 결손은 빈 리스트로 흡수
        # T-04-03: concept·예외타입명만(예외 원문/PII 보간 금지).
        logger.warning("EDGAR query 실패 concept=%s (%s)", concept, type(exc).__name__)
        return []
    return list(result) if result else []


# --- 260701: Q4 도출 (Q4=annual−9M, 추출단계, locked (a)) --------------------


def _query_facts_by_length(facts, concept: str, months: int) -> list:
    """facts.query().by_concept(concept).by_period_length(months) 실행 → list.

    annual(12)·9M(9) YTD fact 취득 전용. 실패/빈 결과 시 빈 리스트 + WARNING(조용한
    삼킴 미부활, _query_facts 와 동일 정책). 260701.
    """
    try:
        q = facts.query().by_concept(concept).by_period_length(months)
        result = q.execute()
    except Exception as exc:  # noqa: BLE001 — 외부 query 빌더, 결손은 빈 리스트
        logger.warning(
            "EDGAR length query 실패 concept=%s months=%d (%s)",
            concept, months, type(exc).__name__,
        )
        return []
    return list(result) if result else []


def _is_total_fact(fact) -> bool:
    """비차원 총액 fact 여부 — 세그먼트(차원) fact 배제(라이브 스파이크: GOOGL 다중 세그먼트).

    실 FinancialFact 는 `is_dimensioned`(bool) / `dimensions`(None=총액) 를 제공한다.
    둘 중 하나라도 차원임을 시사하면 제외. 속성 부재 시 총액으로 간주(보수적 통과).
    """
    if getattr(fact, "is_dimensioned", False):
        return False
    dims = getattr(fact, "dimensions", None)
    return not dims


def _pick_total_by_start(flist: list) -> dict:
    """비차원 총액 fact 를 period_start 별로 정리 → {period_start: fact}.

    같은 회계연도 누계(annual/9M)는 period_start 가 동일하다(라이브 스파이크 확정 —
    9M 매칭 = period_start 동일). numeric_value 결손 fact 는 제외. 동일 start 중복 시
    절대값이 큰(총액) fact 유지(세그먼트 잔재 방어).
    """
    out: dict = {}
    for f in flist:
        if not _is_total_fact(f):
            continue
        if getattr(f, "numeric_value", None) is None:
            continue
        start = _iso_or_none(getattr(f, "period_start", None))
        if start is None:
            continue
        prev = out.get(start)
        if prev is None or abs(f.numeric_value) > abs(prev.numeric_value):
            out[start] = f
    return out


def _derive_q4_rows(facts, ticker: str, reported_quarters_by_field: dict) -> list[dict]:
    """손익 유량 concept 별 `Q4(3M) = annual(12M) − 9M(YTD)` 도출 행 생성 (260701).

    각 concept:
      1) annual(by_period_length(12))·9M(by_period_length(9)) 비차원 총액을 period_start
         별로 정리.
      2) 같은 회계연도(period_start 동일)의 (annual, 9M) 쌍마다 Q4 = annual − 9M 도출.
      3) 분기키 = annual.period_end 월 기준 캘린더 분기(=회계 Q4 = 갭 캘린더 분기).
      4) 이미 as-reported 3M 행이 있는 (field, quarter)는 skip(충돌 방지 — 정상 분기를
         도출로 덮지 않음). 갭 분기에만 채운다.
      5) provenance = _DERIVED_PERIOD_TYPE("derived") — as-reported 와 명시 구분.
    annual/9M 어느 쪽이든 부재·결손이면 해당 쌍 skip(조용한 except 미부활 — 빈값 자연 처리).

    reported_quarters_by_field: {field: set(quarter)} — 이미 추출된 as-reported 3M 분기.
    """
    derived: list[dict] = []
    for concept, field in _EDGAR_Q4_DERIVE_CONCEPTS:
        annual_by_start = _pick_total_by_start(_query_facts_by_length(facts, concept, 12))
        nine_by_start = _pick_total_by_start(_query_facts_by_length(facts, concept, 9))
        if not annual_by_start or not nine_by_start:
            continue  # annual/9M 부재 → 도출 불가(별건 결손, 자연 처리)

        already = reported_quarters_by_field.get(field, set())
        for start, annual_fact in annual_by_start.items():
            nine_fact = nine_by_start.get(start)
            if nine_fact is None:
                continue  # 같은 회계연도 9M 부재 → skip
            q4_value = annual_fact.numeric_value - nine_fact.numeric_value
            quarter = _quarter_key_from_period_end(
                getattr(annual_fact, "period_end", None)
            )
            if quarter is None:
                continue  # 분기키 산출 실패 → skip
            if quarter in already:
                continue  # as-reported 3M 존재 → 도출로 덮지 않음(정상 분기 보존)

            derived.append({
                "ticker": ticker,
                "source": "EDGAR",
                "quarter": quarter,
                "field": field,
                "value": q4_value,
                "unit": getattr(annual_fact, "unit", None),
                # accession: 도출은 두 fact 합성 — annual accession 을 대표로 보존.
                "accession": getattr(annual_fact, "accession", None),
                # period_start/end: 도출 Q4 의 3M 구간 = 9M 종료 다음날~연간 종료일.
                "period_start": _iso_or_none(getattr(nine_fact, "period_end", None)),
                "period_end": _iso_or_none(getattr(annual_fact, "period_end", None)),
                "period_type": _DERIVED_PERIOD_TYPE,  # as-reported 와 구분(provenance)
                "reprt_code": None,
                "filing_date": _iso_or_none(getattr(annual_fact, "filing_date", None)),
            })
    return derived


@throttled_edgar
def fetch_edgar_quarterly_raw(ticker: str) -> list[dict]:
    """EDGAR EntityFacts 에서 분기별 raw 행 리스트 추출 (Plan 07-02, FUND-07).

    D-01 (공짜 backfill): `Company(ticker).get_facts()` 1회만 호출 — EntityFacts 에
    과거 분기가 전부 딸려오므로 별도 호출 없이 전부 추출(추가 set_identity 없음).
    D-04 (신규 추출 경로): 손익 4종 + EPS + 영업현금흐름(duration) + BS 3종(instant).
    D-08: quarter 키는 period 종료일 기준 캘린더 분기 "YYYYQn".
    D-05: 결손 value=None (0/-999999 금지).

    260701(Q4 도출, locked (a)): as-reported 3M 추출 후, 손익 유량 concept 에 대해
    `Q4(3M) = annual(12M) − 9M(YTD)` 를 추가 도출해 회계 Q4(=캘린더 갭 분기) 를 메운다.
    도출 행은 period_type=_DERIVED_PERIOD_TYPE("derived") 로 as-reported 와 구분한다.
    갭 분기에만 채우며(as-reported 3M 존재 시 skip) 08-01 의 "FY−9M 보정 미구현" deferral 을
    해소한다. 엔진(metrics_engine)은 0줄 수정 — _normalize_quarters 가 (quarter,field)만
    키로 소비하므로 4연속 분기 완성 → TTM 자연 복구.

    Returns:
        list[dict] — 각 행: ticker/source="EDGAR"/quarter/field/value/unit/accession/
        period_start/period_end/period_type/reprt_code=None. (도출 Q4 는 period_type="derived".)
    """
    facts = Company(ticker).get_facts()  # D-01: get_facts 1회 (과거 분기 전부 포함)
    rows: list[dict] = []

    # 유량(quarterly 조회 → fact.period_type 은 'duration'). 260629-hec: by_period_type("quarterly").
    # 260701: as-reported 3M 분기를 field 별로 기록(Q4 도출 시 정상 분기 덮어쓰기 방지).
    reported_quarters_by_field: dict[str, set[str]] = {}
    for concept, field in _EDGAR_DURATION_CONCEPTS:
        for fact in _query_facts(facts, concept, "quarterly"):
            row = _fact_to_row(ticker, field, fact, "duration")
            if row is not None:
                rows.append(row)
                reported_quarters_by_field.setdefault(field, set()).add(row["quarter"])

    # 저량(instant, BS). 260629-hec(LOCKED FACT 5): by_concept 만으로 조회 후 파이썬에서
    # period_type=='instant' 필터(instant 어휘는 5.35.0 by_period_type 에서 ValidationError).
    # [A5] concept 결과 비거나 instant 0건 시 헬퍼 fallback.
    for concept, field in _EDGAR_INSTANT_CONCEPTS:
        concept_facts = _query_facts(facts, concept, period_type=None)
        instant_facts = [
            f for f in concept_facts
            if getattr(f, "period_type", None) == "instant"
        ]
        if not instant_facts:
            instant_facts = _instant_fallback(facts, field)
        for fact in instant_facts:
            row = _fact_to_row(ticker, field, fact, "instant")
            if row is not None:
                rows.append(row)

    # 발행주식수: facts.shares_outstanding_fact(dei 단일행) 있으면 행 추가.
    # 260701(커밋2): dei 부재 시 us-gaap 분기별 폴백으로 분기 shares 확보(per-share 분모 복구).
    shares_fact = getattr(facts, "shares_outstanding_fact", None)
    if shares_fact is not None:
        row = _fact_to_row(ticker, "shares_outstanding", shares_fact, "instant")
        if row is not None:
            rows.append(row)
    else:
        rows.extend(_shares_fallback_rows(facts, ticker))

    # 260701: Q4 도출 — 손익 유량 concept 의 회계 Q4(=캘린더 갭 분기)를 annual−9M 으로
    # 메운다. as-reported 3M 이 이미 있는 분기는 skip(reported_quarters_by_field 참조).
    rows.extend(_derive_q4_rows(facts, ticker, reported_quarters_by_field))

    # 260629-hec(LOCKED FACT 6): 같은 (quarter, field)에 다중 fact(정정공시)가 올 때
    # filing_date(실 FinancialFact.filing_date, 없으면 period_end) 오름차순 안정 정렬 —
    # 최신/정정값이 마지막에 와 store upsert 마지막-쓰기 승과 정합한다. 키 부재 행은
    # 빈 문자열로 최하위(None-safe). sorted 는 안정 정렬이라 동일 키 상대순서는 보존.
    rows.sort(key=_row_sort_key)

    logger.info("%s | EDGAR 분기 raw 추출 완료 (%d행)", ticker, len(rows))
    return rows


def _row_sort_key(row: dict) -> tuple:
    """중복 (quarter, field) 정렬 키 — filing_date(없으면 period_end) 오름차순.

    260629-hec(LOCKED FACT 6): 1차 (quarter, field) 로 묶고, 2차 보고일 오름차순 →
    같은 분기·필드의 정정값이 filing_date 늦은(=최신) 순서로 마지막에 온다. 보고일이
    None 인 행은 빈 문자열로 최하위(None-safe). ISO 문자열 비교 = 시간순.
    """
    report = row.get("filing_date") or row.get("period_end") or ""
    return (row.get("quarter") or "", row.get("field") or "", str(report))


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


def _shares_fallback_rows(facts, ticker: str) -> list[dict]:
    """dei shares_outstanding_fact 부재 시 us-gaap 분기별 shares 폴백 행 생성 (260701 커밋2).

    _EDGAR_SHARES_FALLBACK_CONCEPTS 를 선호도 순으로 시도, 첫 번째로 instant fact 를
    산출하는 concept 을 채택해 분기별 shares_outstanding 행을 만든다. per-share 분모
    (EPS_ttm/BPS/SPS/OCF_ps)·가격의존 분모 복구용. concept 전부 결손이면 빈 리스트
    (조용한 except 미부활 — _query_facts 가 WARNING 로깅, 결손은 빈값 자연 처리).

    저량(instant)이므로 quarter 별 시점값 — 같은 (quarter, shares_outstanding) 중복은
    상위 정렬(_row_sort_key)이 최신 filing_date 를 마지막에 두어 store upsert 정합.
    """
    for concept in _EDGAR_SHARES_FALLBACK_CONCEPTS:
        concept_facts = _query_facts(facts, concept, period_type=None)
        instant_facts = [
            f for f in concept_facts
            if getattr(f, "period_type", None) == "instant"
        ]
        if not instant_facts:
            continue
        out: list[dict] = []
        for fact in instant_facts:
            row = _fact_to_row(ticker, "shares_outstanding", fact, "instant")
            if row is not None:
                out.append(row)
        if out:
            return out  # 첫 산출 concept 채택(선호도 순)
    return []
