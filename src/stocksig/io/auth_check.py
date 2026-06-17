"""인증 사전검증 — EDGAR/DART ping (raise 금지, 키/UA 미노출).

200티커 실행 *전에* 인증 상태를 한 번에 검증해 per-call 인증실패 재시도·throttle
대기를 사전 차단한다 (D-02~04, EXEC-04 인증 부분). 두 ping 함수 모두:

  - raise하지 않는다 (D-02 fail-fast 아님) — `except Exception` 으로 흡수하고
    `(ok, 사유)` tuple 을 반환한다. 실행 흐름은 호출부에서 계속된다.
  - 캐시 쓰기 경로(`fetch_*_cached`)를 절대 사용하지 않는다 (Pitfall 1 — 캐시 오염
    방지). 캐시 미경유 가벼운 식별 호출만 수행한다.
  - 예외 사유 note 에 EDGAR UA/이메일·OPENDART_API_KEY 원문을 절대 보간하지 않는다
    (T-04-03 Information Disclosure). 고정 한국어 사유만 반환한다.

EDGAR ping 은 **httpx 직접 GET 단일 경로** 로 확정한다 (Pitfall 2 혼합 금지 —
edgartools 부수효과 경로는 사용하지 않음). `edgar_client._resolve_identity()` 로
User-Agent 헤더를 구성하고 SEC 소형 엔드포인트에 1회 GET 한 뒤 `raise_for_status()`
로 4xx(특히 403 UA 거부)만 검출한다. `@throttled_edgar` 경유.

DART ping 은 캐시 미경유 가벼운 호출로 status 코드를 본다. status "013"(데이터
미존재)/"020"(쿼터 초과)은 *키가 유효* 하다는 뜻이므로 OK 로 판정한다 (Pitfall 4
false-negative 방지). 그 외 status·예외는 키 무효로 보고 실패 처리. `@throttled_dart`
경유.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
)

from stocksig.io import dart_client, edgar_client
from stocksig.io.throttle import throttled_dart, throttled_edgar

logger = logging.getLogger(__name__)

# SEC 소형 식별 엔드포인트 — 캐시 미경유 1회 GET 으로 UA/403 만 검출.
_EDGAR_PING_URL = "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0000320193&type=10-K&dateb=&owner=include&count=1"

# 고정 한국어 사유 — 예외 원문(e) 미포함 (T-04-03 보안). DART status "013"/"020"
# 은 키 유효이므로 OK 셋에 둔다 (Pitfall 4).
_EDGAR_403_NOTE = "EDGAR 403 (UA 확인)"
_EDGAR_FAIL_NOTE = "EDGAR 인증 실패"
_DART_FAIL_NOTE = "DART 인증 실패"
_DART_VALID_KEY_STATUS = frozenset({"000", "013", "020"})


@dataclass
class AuthStatus:
    """인증 ping 결과 — None = ping 미실행(해당 시장 티커 없음, D-04).

    edgar_ok/dart_ok: True=OK, False=실패, None=미실행.
    edgar_note/dart_note: 실패 시 키/UA 미포함 고정 한국어 사유, 그 외 None.
    """

    edgar_ok: bool | None = None
    dart_ok: bool | None = None
    edgar_note: str | None = None
    dart_note: str | None = None


@throttled_edgar
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _edgar_probe() -> None:
    """SEC 소형 엔드포인트 1회 GET (캐시 미경유) — 4xx/5xx 시 raise.

    UA 는 edgar_client._resolve_identity() 재사용(.env 이메일 우선). 호출부
    ping_edgar 가 예외를 흡수하므로 여기서는 raise_for_status 로 검출만 한다.
    WR-02: transient(5xx/네트워크) 일시 장애를 흡수하기 위해 tenacity 로 최대 3회
    재시도(reraise=True — 소진 시 원 예외 그대로 전파, RetryError 미래핑).
    """
    headers = {"User-Agent": edgar_client._resolve_identity()}
    resp = httpx.get(_EDGAR_PING_URL, headers=headers, timeout=10)
    resp.raise_for_status()


def ping_edgar() -> tuple[bool, str | None]:
    """EDGAR 인증 사전검증 — raise 금지, (ok, 키/UA 미포함 사유).

    WR-02/WR-03 신 계약:
      - 성공 → (True, None).
      - HTTP 403(UA 거부) → (False, "EDGAR 403 (UA 확인)") — 구조적
        e.response.status_code == 403 판별(문자열 매칭 폐지).
      - HTTP 401 → (False, "EDGAR 인증 실패") — 인증 실패는 401/403 한정.
      - 그 외 HTTP status(5xx 등) → (True, None) — 서버측 일시 장애는 인증
        문제 아님, 1차 소스 차단 금지(self-DoS 방지, T-k34-02).
      - 그 외 transient 예외(연결 오류 등) → (True, None) — per-call 흡수
        경로에 맡긴다.
    예외 원문 e 는 note 에 절대 보간하지 않는다(UA/이메일 누설 방지, T-04-03).
    """
    try:
        _edgar_probe()
    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        if status in (401, 403):
            note = _EDGAR_403_NOTE if status == 403 else _EDGAR_FAIL_NOTE
            logger.warning("auth | ⚠ %s — 미국 펀더멘털 결손 처리됩니다", note)
            return False, note
        # 5xx 등 서버측 일시 장애 — 인증 문제 아님, 1차 소스 차단 금지.
        logger.warning(
            "auth | EDGAR ping 일시 장애(HTTP %s) — 인증 문제 아님, 계속 진행", status
        )
        return True, None
    except Exception:  # noqa: BLE001 — D-02 흡수 (fail-fast 아님)
        # transient(네트워크/연결 오류) — 인증 문제 아님, per-call 경로에 맡김.
        logger.warning("auth | EDGAR ping 일시 장애 — 인증 문제 아님, 계속 진행")
        return True, None
    logger.info("auth | EDGAR 인증 OK")
    return True, None


@throttled_dart
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    reraise=True,
)
def _dart_probe() -> str:
    """DART 가벼운 호출(캐시 미경유) → status 코드 문자열 반환.

    opendartreader 의 list(공시목록) 1건을 호출해 응답 형태/status 로 키 유효성을
    판정한다. 정상 응답(DataFrame/list)은 "000", dict 오류 응답은 그 status 를
    그대로 반환. 키 자체가 URL 에 들어가므로 호출부 ping_dart 가 예외/사유를
    sanitize 한다.
    """
    api_key = dart_client._resolve_api_key()
    dart = dart_client.OpenDartReader(api_key)
    # 가벼운 공시목록 조회 (재무제표 fetch 보다 가벼움, 캐시 미경유).
    resp = dart.list("005930")
    if isinstance(resp, dict):
        return str(resp.get("status", ""))
    return "000"


def ping_dart() -> tuple[bool, str | None]:
    """DART 인증 사전검증 — raise 금지, (ok, 키 미포함 사유).

    WR-02 신 계약:
      - status "000"/"013"/"020" 은 키 유효 → (True, None) (Pitfall 4
        false-negative 방지 — 데이터 미존재/쿼터 초과는 키 무효가 아님).
      - 그 외 status(무효 키 "010" 등) → (False, "DART 인증 실패").
      - HTTP 401/403 → (False, "DART 인증 실패") — 인증 실패는 401/403 한정.
      - 그 외 HTTP status(5xx 등)·transient 예외 → (True, None) — 일시 장애는
        인증 문제 아님, 1차 소스 차단 금지(self-DoS 방지, T-k34-02).
    opendartreader 가 키를 URL 에 넣으므로 예외 원문 e 는 note 에 보간하지
    않는다 (IN-02: except 절 미사용 e 바인딩 제거, T-04-03 누설 방지).
    """
    try:
        status = _dart_probe()
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            logger.warning(
                "auth | ⚠ %s — 한국 펀더멘털 결손 처리됩니다", _DART_FAIL_NOTE
            )
            return False, _DART_FAIL_NOTE
        # 5xx 등 서버측 일시 장애 — 인증 문제 아님, 1차 소스 차단 금지.
        logger.warning("auth | DART ping 일시 장애 — 인증 문제 아님, 계속 진행")
        return True, None
    except Exception:  # noqa: BLE001 — D-02 흡수 (fail-fast 아님)
        # transient(네트워크/연결 오류) — 인증 문제 아님, 계속 진행.
        logger.warning("auth | DART ping 일시 장애 — 인증 문제 아님, 계속 진행")
        return True, None
    if status in _DART_VALID_KEY_STATUS:
        logger.info("auth | DART 인증 OK")
        return True, None
    logger.warning("auth | ⚠ %s — 한국 펀더멘털 결손 처리됩니다", _DART_FAIL_NOTE)
    return False, _DART_FAIL_NOTE
