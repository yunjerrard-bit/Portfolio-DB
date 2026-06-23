"""OpenDART 한국 펀더멘털 클라이언트 — finstate_all + account 매핑 + throttle.

market.py / edgar_client.py 구조 복제: `@throttled_dart`(2 RPS) 페치.
SPIKE-FINDINGS A3/A6 확정 경로 사용.

Plan 10-03(FUND-11): 구 cache-first 페치 `fetch_dart_cached`(7d `.cache/fundamentals`)는
시트1 단일 원천 이관으로 호출자가 사라져 제거됐다. store 경로 per-quarter 추출기
`fetch_dart_quarterly_raw`(Phase 7)와 raw 추출기 `fetch_dart_raw`는 유지된다.

확정 취득 경로(OpenDartReader 0.3.x, A6 — 6자리 stock_code 직접 수용):
    dart = OpenDartReader(api_key)                          # corp_code 내부 해석
    df = dart.finstate_all("005930", year, reprt_code="11011", fs_div="CFS")
    # status: "000"=정상 "013"=데이터없음 "020"=쿼터초과 (Pitfall 3)

계정 매핑(A3 [VERIFIED] — account_id 1차 / account_nm 2차):
    1차: DART_ACCOUNT_ID_MAP (표준 태그, 예 ifrs-full_Revenue) 로 account_id 정확매칭
    2차: DART_ACCOUNT_MAP (한글 account_nm 후보 tuple) 폴백
    손익행만(sj_div ∈ SJ_DIV_INCOME_STATEMENT = IS/CIS).
    thstrm_amount(쉼표 문자열) → int(s.replace(",","")) try/except (T-03-10, ASVS V5).

stock_code 파싱: market_kind KR_SUFFIXES 발상 — `.split(".")[0]` 로 ".KS" 제거.
API 키: config.load_env 의 OPENDART_API_KEY (하드코딩 회피, T-03-03).
"""

from __future__ import annotations

import datetime
import logging
import os
import threading

import pandas as pd
from opendartreader import OpenDartReader  # 주의: import 소문자 opendartreader, 클래스 OpenDartReader (A6)

from stocksig.io.dart_account_map import (
    DART_ACCOUNT_ID_MAP,
    DART_ACCOUNT_MAP,
    SJ_DIV_BALANCE_SHEET,
    SJ_DIV_CASHFLOW,
    SJ_DIV_INCOME_STATEMENT,
)
from stocksig.io.throttle import throttled_dart

logger = logging.getLogger(__name__)

# OpenDartReader 모듈 레벨 싱글톤 (Pitfall 1: corp_codes 이중 다운로드 차단).
# cache.py double-checked locking 패턴 복제 — 07-03 fundamentals_delta 가 공유.
_dart_singleton: OpenDartReader | None = None
_dart_lock = threading.Lock()


def _get_dart() -> OpenDartReader:
    """OpenDartReader 싱글톤 — double-checked locking (Pitfall 1 corp_codes 1회 다운로드)."""
    global _dart_singleton
    if _dart_singleton is None:  # fast-path
        with _dart_lock:
            if _dart_singleton is None:  # double-checked
                _dart_singleton = OpenDartReader(_resolve_api_key())
    return _dart_singleton

# 논리 지표 키 순서 (raw dict 구성 + None 초기화).
_METRIC_KEYS: tuple[str, ...] = ("revenue", "gross_profit", "op_income", "net_income", "eps")

# DART status 코드 → 한국어 사유 (Pitfall 3 — 4분기 가드).
_STATUS_NOTES: dict[str, str] = {
    "013": "DART 데이터 미존재",
    "020": "DART 쿼터 초과",
}
_STATUS_OTHER_NOTE = "DART corp_code 매핑 실패"


def _resolve_api_key() -> str:
    """OPENDART_API_KEY 해석 — .env 우선(하드코딩 회피, T-03-03)."""
    key = os.environ.get("OPENDART_API_KEY")
    if not key:
        from stocksig.config import load_env

        key = load_env()["OPENDART_API_KEY"]
    return key


def _parse_amount(raw: object) -> int | None:
    """thstrm_amount(쉼표 문자열) → int. 파싱 실패 시 None (T-03-10, ASVS V5)."""
    if raw is None:
        return None
    try:
        s = str(raw).replace(",", "").strip()
        if s == "" or s == "-":
            return None
        return int(s)
    except (ValueError, TypeError):
        return None


def _income_rows(df: pd.DataFrame) -> pd.DataFrame:
    """손익행만(sj_div ∈ IS/CIS) 필터 — 재무상태표(BS) 동명행 오염 차단."""
    if "sj_div" not in df.columns:
        return df
    return df[df["sj_div"].isin(SJ_DIV_INCOME_STATEMENT)]


def _match_amount(
    rows: pd.DataFrame,
    id_candidates: tuple[str, ...] | None,
    nm_candidates: tuple[str, ...] | None,
    column: str = "thstrm_amount",
) -> int | None:
    """account_id 1차 → account_nm 2차 매핑으로 금액 행 추출 후 int 파싱."""
    # 1차: account_id 정확매칭 (표준 태그 — 업종 간 안정적).
    if id_candidates and "account_id" in rows.columns:
        for acc_id in id_candidates:
            hit = rows[rows["account_id"] == acc_id]
            if not hit.empty:
                val = _parse_amount(hit.iloc[0][column])
                if val is not None:
                    return val
    # 2차: account_nm 후보 매칭 (한글 라벨 폴백).
    if nm_candidates and "account_nm" in rows.columns:
        for acc_nm in nm_candidates:
            hit = rows[rows["account_nm"] == acc_nm]
            if not hit.empty:
                val = _parse_amount(hit.iloc[0][column])
                if val is not None:
                    return val
    return None


def _empty_raw(note: str) -> dict:
    """전 지표 결손 raw dict + 한국어 사유 (status 가드/빈응답)."""
    raw: dict = {k: None for k in _METRIC_KEYS}
    raw["eps_prior"] = None
    raw["note"] = note
    return raw


@throttled_dart
def fetch_dart_raw(ticker: str, year: int) -> dict:
    """DART finstate_all 에서 KR 재무 raw dict 산출 (FUND-03).

    stock_code 직접 수용(".KS" 제거, A6), status 가드(Pitfall 3),
    account_id 1차 / account_nm 2차 매핑(A3), thstrm_amount int 파싱(T-03-10).
    None-safe — 결손 지표는 None(0/-999999 금지, D-05).

    Returns:
        {revenue, gross_profit, op_income, net_income, eps, eps_prior, note}.
        eps_prior: frmtrm_amount(전년 기본주당이익) — PEG 입력.
        note: 결손/오류 시 한국어 사유, 정상 시 None.
    """
    stock_code = ticker.split(".")[0]  # "005930.KS" → "005930" (RESEARCH Pattern 4)
    api_key = _resolve_api_key()
    dart = OpenDartReader(api_key)

    resp = dart.finstate_all(stock_code, year, reprt_code="11011", fs_div="CFS")

    # status 가드 (dict 형태 오류 응답) — DataFrame 이 아니면 status 검사.
    if isinstance(resp, dict):
        status = resp.get("status")
        note = _STATUS_NOTES.get(status, _STATUS_OTHER_NOTE)
        logger.info("%s | DART status=%s → %s", ticker, status, note)
        return _empty_raw(note)

    # 빈 결과(데이터없음/쿼터초과가 빈 df 로 표면화).
    if resp is None or not isinstance(resp, pd.DataFrame) or resp.empty:
        logger.info("%s | DART 빈 응답 → 데이터 미존재", ticker)
        return _empty_raw("DART 데이터 미존재")

    rows = _income_rows(resp)
    raw: dict = {}
    for key in _METRIC_KEYS:
        raw[key] = _match_amount(
            rows, DART_ACCOUNT_ID_MAP.get(key), DART_ACCOUNT_MAP.get(key)
        )
    # 전년 기본주당이익(frmtrm_amount) — PEG eps_prior.
    raw["eps_prior"] = _match_amount(
        rows,
        DART_ACCOUNT_ID_MAP.get("eps"),
        DART_ACCOUNT_MAP.get("eps"),
        column="frmtrm_amount",
    )
    raw["note"] = None

    logger.info("%s | DART finstate 수신 완료 (year=%s)", ticker, year)
    return raw


# --- Plan 07-02: 분기 백필 raw 추출 (additive, 시트1 TTM 경로 불변 D-06) ---

# reprt_code → 캘린더 분기 번호 (D-08). 11013=1Q, 11012=반기→Q2, 11014=3Q, 11011=연간→Q4.
QUARTER_CODES: list[str] = ["11013", "11012", "11014", "11011"]
_REPRT_TO_QUARTER: dict[str, int] = {"11013": 1, "11012": 2, "11014": 3, "11011": 4}

# 분기 백필 추출 대상 (논리 field, sj_div 필터, period_type).
_QUARTERLY_INCOME_FIELDS: tuple[str, ...] = ("revenue", "gross_profit", "op_income", "net_income", "eps")
_QUARTERLY_BS_FIELDS: tuple[str, ...] = ("total_equity", "total_liabilities", "total_assets")
_QUARTERLY_CF_FIELDS: tuple[str, ...] = ("operating_cash_flow",)


def _calendar_quarter_key(bsns_year: object, reprt_code: str) -> str | None:
    """bsns_year + reprt_code → "YYYYQn" 캘린더 분기 키 (D-08). 실패 시 None."""
    qn = _REPRT_TO_QUARTER.get(reprt_code)
    if qn is None:
        return None
    try:
        year = int(str(bsns_year).strip())
    except (ValueError, TypeError):
        return None
    return f"{year}Q{qn}"


def _div_rows(df: pd.DataFrame, sj_divs: tuple[str, ...]) -> pd.DataFrame:
    """주어진 sj_div 집합 행만 필터 (BS/CF 동명행 오염 차단, D-04)."""
    if "sj_div" not in df.columns:
        return df.iloc[0:0]
    return df[df["sj_div"].isin(sj_divs)]


def _extract_quarter_rows(
    ticker: str,
    df: pd.DataFrame,
    quarter: str,
    reprt_code: str,
    rcept: str | None,
) -> list[dict]:
    """단일 finstate_all 응답 → 분기 raw 행 리스트 (IS/CIS 손익 + BS + CF).

    D-04: 손익=SJ_DIV_INCOME_STATEMENT, BS=SJ_DIV_BALANCE_SHEET, CF=SJ_DIV_CASHFLOW.
    D-05: 결손 value=None. as-reported(YTD 누적 그대로) — 분기 분해는 Phase 8(Pitfall 4).
    """
    rows: list[dict] = []

    def _emit(fields: tuple[str, ...], src_rows: pd.DataFrame, period_type: str):
        for field in fields:
            value = _match_amount(
                src_rows, DART_ACCOUNT_ID_MAP.get(field), DART_ACCOUNT_MAP.get(field)
            )
            rows.append({
                "ticker": ticker,
                "source": "DART",
                "quarter": quarter,
                "field": field,
                "value": value,  # None-safe (D-05)
                "unit": "KRW",
                "accession": rcept,  # rcept_no (델타 키, 매 행 동일)
                "period_start": None,
                "period_end": None,
                "period_type": period_type,
                "reprt_code": reprt_code,
            })

    _emit(_QUARTERLY_INCOME_FIELDS, _income_rows(df), "duration")
    _emit(_QUARTERLY_BS_FIELDS, _div_rows(df, SJ_DIV_BALANCE_SHEET), "instant")
    _emit(_QUARTERLY_CF_FIELDS, _div_rows(df, SJ_DIV_CASHFLOW), "duration")
    return rows


@throttled_dart
def fetch_dart_quarterly_raw(ticker: str, years: int = 3) -> list[dict]:
    """DART finstate_all 최근 N년 분기 백필 raw 행 리스트 (Plan 07-02, FUND-07).

    D-01 (소스별 차등): EDGAR 와 달리 DART 는 비용·쿼터를 고려해 최근 `years`년
    (기본 3년 ~12분기)만 finstate_all 루프로 backfill 한다.
    D-04: 손익 5종(IS/CIS) + BS 3종 + 영업현금흐름 추출.
    D-08: quarter 키 = bsns_year + reprt_code → "YYYYQn" 캘린더 분기.
    D-05: 결손 value=None. YTD 누적은 as-reported 그대로(분기 분해는 Phase 8, Pitfall 4).
    Pitfall 1: OpenDartReader 싱글톤 재사용(corp_codes 1회 다운로드).

    Returns:
        list[dict] — 각 행: ticker/source="DART"/quarter/field/value/unit="KRW"/
        accession=rcept_no/period_start=None/period_end=None/period_type/reprt_code.
    """
    stock_code = ticker.split(".")[0]  # "005930.KS" → "005930" (A6)
    dart = _get_dart()  # 싱글톤 (Pitfall 1)
    this_year = datetime.date.today().year

    rows: list[dict] = []
    for year in range(this_year - years, this_year + 1):
        for code in QUARTER_CODES:
            resp = dart.finstate_all(stock_code, year, reprt_code=code, fs_div="CFS")

            # status 가드 (dict 형태 오류 응답) — skip.
            if isinstance(resp, dict):
                status = resp.get("status")
                logger.info("%s | DART %sQ%s status=%s → skip", ticker, year, code, status)
                continue
            # 빈 결과 가드 (데이터없음/쿼터초과/미존재 분기) — skip.
            if resp is None or not isinstance(resp, pd.DataFrame) or resp.empty:
                continue

            quarter = _calendar_quarter_key(year, code)
            if quarter is None:
                continue
            rcept = None
            if "rcept_no" in resp.columns and not resp.empty:
                rcept = str(resp.iloc[0]["rcept_no"])  # 매 행 동일(델타 키)

            rows.extend(_extract_quarter_rows(ticker, resp, quarter, code, rcept))

    logger.info("%s | DART 분기 백필 추출 완료 (%d행, 최근 %d년)", ticker, len(rows), years)
    return rows
