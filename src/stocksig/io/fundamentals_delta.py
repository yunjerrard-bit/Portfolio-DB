"""접수번호 델타 오케스트레이션 (FUND-08, D-02 forward 누적).

책임: 가벼운 메타 probe 로 최신 접수번호(EDGAR accession / DART rcept_no)만 얻고,
store(Plan 01)의 `delta_state`(last_accession)와 비교해 — 같으면 full-fetch 를
생략(평소 외부 전체호출 ≈0, SC3), 다르면 추출기(Plan 02)로 재추출·누적·
`last_accession` 갱신(forward 누적, SC4)한다.

설계 불변 (locked):
  - D-02 (backfill 이후 forward 누적): 첫 backfill 이후 매 실행 forward 누적 모델.
    접수번호 델타 없음(저장값 == probe) → 신규 저장 0(full-fetch 생략).
    델타 있음 → 재추출·upsert·last_accession 갱신으로만 누적.
  - Pitfall 1: OpenDartReader 는 `dart_client._get_dart()` 모듈 싱글톤을 공유
    재사용한다 (종목마다 새 인스턴스 생성 금지 — corp_codes 이중 다운로드 차단).
  - Pitfall 2 / T-07-07: probe 실패(예외/None) 시 "갱신 생략, 기존 DB 유지"
    (보수적 재추출 금지 — DART 쿼터 폭주·연쇄 차단).
  - T-07-08 (T-04-03): probe/fetch 예외 로그에 API 키(crtfc_key)·예외 원문을
    보간하지 않는다 (타입명만 로그).

throttle: probe 2종은 외부 메타 호출이므로 `@throttled_edgar`/`@throttled_dart`.
"""

from __future__ import annotations

import logging

from edgar import Company

from stocksig.io import dart_client, edgar_client
from stocksig.io import fundamentals_store as store
from stocksig.io.dart_client import _get_dart
from stocksig.io.throttle import throttled_dart, throttled_edgar

logger = logging.getLogger(__name__)

__all__ = [
    "probe_edgar_accession",
    "probe_dart_rcept",
    "sync_ticker_history",
]


@throttled_edgar
def probe_edgar_accession(ticker: str) -> str | None:
    """EDGAR 최신 10-Q 접수번호만 가벼운 메타 호출로 반환 (RESEARCH Pattern 2 [A4]).

    `Company(ticker).latest("10-Q").accession_number` — 전체 facts 추출보다 훨씬
    가벼운 메타 조회. 최신 10-Q 가 없으면 None.
    """
    latest = Company(ticker).latest("10-Q")
    if latest is None:
        return None
    return latest.accession_number


@throttled_dart
def probe_dart_rcept(ticker: str) -> str | None:
    """DART 최신 공시 접수번호(rcept_no)만 list API 로 반환 (RESEARCH Pattern 2).

    `_get_dart().list(stock_code, kind="A").iloc[0]["rcept_no"]` (rcept_dt 내림차순).
    싱글톤 `dart_client._get_dart()` 재사용(Pitfall 1). 빈 결과 → None.
    """
    stock_code = ticker.split(".")[0]  # "005930.KS" → "005930"
    df = _get_dart().list(stock_code, kind="A")
    if df is None or df.empty or "rcept_no" not in df.columns:
        return None
    return str(df.iloc[0]["rcept_no"])


def _probe(ticker: str, source: str) -> str | None:
    """source 별 probe 디스패치 — 예외는 호출자에 전파(상위에서 안전 폴백)."""
    if source == "EDGAR":
        return probe_edgar_accession(ticker)
    return probe_dart_rcept(ticker)


def _full_fetch(ticker: str, source: str, years: int) -> list[dict]:
    """source 별 추출기(Plan 02) 호출 — 분기 raw dict 행 리스트 반환."""
    if source == "EDGAR":
        return edgar_client.fetch_edgar_quarterly_raw(ticker)
    return dart_client.fetch_dart_quarterly_raw(ticker, years)


def _rows_to_tuples(rows: list[dict]) -> list[tuple]:
    """추출기 11-key dict 행 → store 12-tuple (+fetched_at) 변환 (Plan 02→01 계약).

    컬럼 순서 = upsert_quarters 12-tuple (ticker, source, quarter, field, value,
    unit, accession, period_start, period_end, period_type, reprt_code, fetched_at).
    fetched_at 만 store 측 시각으로 부여한다(나머지는 dict 그대로).
    """
    fetched_at = store._now_iso()
    return [
        (
            r.get("ticker"),
            r.get("source"),
            r.get("quarter"),
            r.get("field"),
            r.get("value"),
            r.get("unit"),
            r.get("accession"),
            r.get("period_start"),
            r.get("period_end"),
            r.get("period_type"),
            r.get("reprt_code"),
            fetched_at,
        )
        for r in rows
    ]


def sync_ticker_history(ticker: str, source: str, years: int = 3) -> None:
    """접수번호 델타 동기화 (D-02 forward 누적).

    1) probe(메타 호출)로 최신 접수번호 취득. 실패(예외/None) 시 "갱신 생략,
       기존 DB 유지"(Pitfall 2 — 보수적 재추출 금지). 타입명만 로그(T-04-03).
    2) `get_last_accession` 과 비교: 같으면(델타 없음) `mark_delta_hit` 후 return
       — full-fetch·신규 저장 0(평소 ≈0, SC3).
    3) 다르거나 state 부재(델타 있음): `mark_delta_miss` → 추출기 full-fetch →
       dict→12-tuple 변환 → `upsert_quarters` → `mark_full_fetch` →
       `set_last_accession`(forward 누적, SC4).

    fetch 실패도 안전 흡수 — 부분 추출/예외 시 last_accession 갱신·저장을
    하지 않아 다음 실행에서 재시도된다(기존 DB 유지).
    """
    # 1) probe — 예외/None 안전 폴백 (Pitfall 2).
    try:
        latest = _probe(ticker, source)
    except Exception as exc:  # noqa: BLE001 — 메타 호출 전면 흡수
        logger.info(
            "%s | %s probe 실패(%s) → 갱신 생략, 기존 DB 유지",
            ticker, source, type(exc).__name__,  # 예외 원문/키 보간 금지(T-04-03)
        )
        return
    if latest is None:
        logger.info("%s | %s probe 빈 응답 → 갱신 생략, 기존 DB 유지", ticker, source)
        return

    # 2) delta_state 비교 (D-02: 같으면 SKIP).
    last = store.get_last_accession(ticker, source)
    if last is not None and last == latest:
        store.mark_delta_hit()
        logger.info("%s | %s 접수번호 동일(%s) → SKIP(full-fetch 0)", ticker, source, latest)
        return

    # 3) 델타 있음 → 재추출·누적·갱신 (forward 누적).
    store.mark_delta_miss()
    try:
        rows = _full_fetch(ticker, source, years)
    except Exception as exc:  # noqa: BLE001 — fetch 실패 안전 흡수
        logger.info(
            "%s | %s full-fetch 실패(%s) → 누적·갱신 생략, 기존 DB 유지",
            ticker, source, type(exc).__name__,
        )
        return

    if rows:
        store.upsert_quarters(_rows_to_tuples(rows))
    store.mark_full_fetch()
    store.set_last_accession(ticker, source, latest)
    logger.info(
        "%s | %s 델타 감지(%s→%s) → %d행 누적·last_accession 갱신",
        ticker, source, last, latest, len(rows),
    )
