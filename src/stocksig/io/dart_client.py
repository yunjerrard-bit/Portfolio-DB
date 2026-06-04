"""OpenDART 한국 펀더멘털 클라이언트 — finstate_all + account 매핑 + throttle + 7d cache.

market.py / edgar_client.py 구조 복제: `@throttled_dart`(2 RPS) 페치 + cache-first 페치
2함수. SPIKE-FINDINGS A3/A6 확정 경로 사용.

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

import logging
import os

import pandas as pd
from opendartreader import OpenDartReader  # 주의: import 소문자 opendartreader, 클래스 OpenDartReader (A6)

from stocksig.io import cache
from stocksig.io.dart_account_map import (
    DART_ACCOUNT_ID_MAP,
    DART_ACCOUNT_MAP,
    SJ_DIV_INCOME_STATEMENT,
)
from stocksig.io.throttle import throttled_dart

logger = logging.getLogger(__name__)

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


def fetch_dart_cached(ticker: str, quarter_label: str) -> dict:
    """cache-first 페치 (market.py L89-102 패턴). 7d TTL, 키 "DART|ticker|quarter".

    quarter_label 은 "{bsns_year}-{reprt_code}" (예 "2025-11011", A7).
    bsns_year 를 파싱해 finstate_all year 인자로 전달.
    """
    cached = cache.get_fund("DART", ticker, quarter_label)
    if cached is not None:
        return cached
    year = int(quarter_label.split("-")[0])
    raw = fetch_dart_raw(ticker, year)
    cache.put_fund("DART", ticker, quarter_label, raw)
    return raw
