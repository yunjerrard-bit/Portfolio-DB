"""Phase 4 Wave 2 (04-03 Task 1·2·3): auth_check.py 인증 사전검증.

`ping_edgar()`/`ping_dart()` 는 raise하지 않는 순수 검증 함수 — (ok, 키/UA 미포함 사유)
tuple 을 반환한다. 외부 호출(httpx GET·opendartreader)은 mocker.patch 로 차단해
성공/403/일반예외/키유효status/보안(EDGAR UA·DART 키 양쪽 미노출)/조건부 골격을 단언.

보안 계약(T-04-03/04): ping 예외 사유 note 에 EDGAR UA/이메일·OPENDART_API_KEY 원문이
절대 포함되지 않는다 — 예외 원문 e 를 note 에 보간 금지, 고정 한국어 사유만 사용.

Task 2 (skip 인자): fetch_fundamentals(skip_edgar/skip_dart) — 1차만 스킵, yf 폴백 유지.
"""

from __future__ import annotations

from pathlib import Path

import httpx

from stocksig.io.auth_check import AuthStatus, ping_dart, ping_edgar


# 보안 테스트에 주입할 민감값 — note 에 이 문자열이 새어나오면 안 됨.
_SECRET_EMAIL = "yunjerrard@gmail.com"
_SECRET_DART_KEY = "0123456789abcdef0123456789abcdef01234567"


# --- 소스 단언 (raise 금지 계약) ----------------------------------------

def test_source_has_except_exception_and_no_cache():
    # raise 금지 계약 = except Exception 흡수, 캐시 쓰기 경로 미사용(Pitfall 1).
    src = Path("src/stocksig/io/auth_check.py").read_text(encoding="utf-8")
    assert "except Exception" in src
    assert "fetch_edgar_cached" not in src
    assert "fetch_dart_cached" not in src
    # EDGAR ping 은 httpx 직접 GET 단일 경로 (edgartools 부수효과 분기 부재).
    assert "httpx" in src


def test_source_notes_have_no_exception_interpolation():
    # 고정 한국어 사유 — note 에 예외 원문 {e} 보간 없음 (보안 T-04-03).
    src = Path("src/stocksig/io/auth_check.py").read_text(encoding="utf-8")
    lines = src.splitlines()
    for needle in ("DART 인증 실패", "EDGAR 인증 실패", "EDGAR 403"):
        hits = [ln for ln in lines if needle in ln]
        assert hits, f"고정 사유 '{needle}' 가 소스에 없음"
        for ln in hits:
            assert "{e}" not in ln, f"'{needle}' 줄에 예외 보간 {{e}} 포함: {ln}"


# --- AuthStatus ----------------------------------------------------------

def test_auth_status_defaults_all_none():
    # 기본 인스턴스의 4필드가 모두 None (None = ping 미실행).
    auth = AuthStatus()
    assert auth.edgar_ok is None
    assert auth.dart_ok is None
    assert auth.edgar_note is None
    assert auth.dart_note is None


# --- ping_edgar ----------------------------------------------------------

def test_ping_edgar_success(mocker):
    # 성공 경로 → (True, None), raise 없음.
    resp = mocker.Mock()
    resp.raise_for_status.return_value = None
    mocker.patch("stocksig.io.auth_check.httpx.get", return_value=resp)

    ok, note = ping_edgar()
    assert ok is True
    assert note is None


def _edgar_status_error(status: int) -> httpx.HTTPStatusError:
    req = httpx.Request("GET", "https://www.sec.gov/")
    resp = httpx.Response(status, request=req)
    return httpx.HTTPStatusError(str(status), request=req, response=resp)


def test_ping_edgar_403(mocker):
    # 내부 호출이 403(UA 거부) → (False, "EDGAR 403 (UA 확인)"), raise 없음.
    mocker.patch(
        "stocksig.io.auth_check.httpx.get",
        side_effect=_edgar_status_error(403),
    )

    ok, note = ping_edgar()
    assert ok is False
    assert "403" in (note or "")


def test_ping_edgar_401_is_auth_fail(mocker):
    # WR-02: 401 도 인증 실패로 한정 → (False, "EDGAR 인증 실패").
    mocker.patch(
        "stocksig.io.auth_check.httpx.get",
        side_effect=_edgar_status_error(401),
    )

    ok, note = ping_edgar()
    assert ok is False
    assert "EDGAR 인증 실패" in (note or "")


def test_ping_edgar_5xx_not_auth_fail(mocker):
    # WR-02: 5xx(서버측 일시 장애)는 인증 문제 아님 → (True, None), 1차 소스 미차단.
    mocker.patch(
        "stocksig.io.auth_check.httpx.get",
        side_effect=_edgar_status_error(503),
    )

    ok, note = ping_edgar()
    assert ok is True
    assert note is None


def test_ping_edgar_transient_exception_not_auth_fail(mocker):
    # WR-02: transient 일반 예외(연결 오류 등)는 인증 문제 아님 → (True, None).
    req = httpx.Request("GET", "https://www.sec.gov/")
    mocker.patch(
        "stocksig.io.auth_check.httpx.get",
        side_effect=httpx.ConnectError("연결 실패", request=req),
    )

    ok, note = ping_edgar()
    assert ok is True
    assert note is None


def test_ping_edgar_runtime_error_not_auth_fail(mocker):
    # WR-02: 일반 RuntimeError 도 transient 로 간주 → (True, None).
    mocker.patch(
        "stocksig.io.auth_check.httpx.get",
        side_effect=RuntimeError("연결 실패"),
    )

    ok, note = ping_edgar()
    assert ok is True
    assert note is None


def test_ping_edgar_note_never_leaks_ua_email(mocker):
    # 보안(T-04-03): 403 예외 메시지에 UA/이메일을 주입해도 note 에 그 값이 포함되지 않음.
    req = httpx.Request("GET", "https://www.sec.gov/")
    resp = httpx.Response(403, request=req)
    mocker.patch(
        "stocksig.io.auth_check.httpx.get",
        side_effect=httpx.HTTPStatusError(
            f"403 Forbidden for User-Agent: {_SECRET_EMAIL}",
            request=req,
            response=resp,
        ),
    )

    ok, note = ping_edgar()
    assert ok is False
    assert _SECRET_EMAIL not in (note or "")


# --- ping_dart -----------------------------------------------------------

def test_ping_dart_success(mocker):
    # 정상 응답(키 유효, status 미사용 정상 DataFrame/list) → (True, None).
    mocker.patch("stocksig.io.auth_check._dart_probe", return_value="000")

    ok, note = ping_dart()
    assert ok is True
    assert note is None


def test_ping_dart_status_013_is_valid_key(mocker):
    # Pitfall 4: status "013"(데이터 미존재)은 키 유효 → (True, None).
    mocker.patch("stocksig.io.auth_check._dart_probe", return_value="013")

    ok, note = ping_dart()
    assert ok is True
    assert note is None


def test_ping_dart_status_020_is_valid_key(mocker):
    # Pitfall 4: status "020"(쿼터 초과)도 키 유효 → (True, None).
    mocker.patch("stocksig.io.auth_check._dart_probe", return_value="020")

    ok, note = ping_dart()
    assert ok is True
    assert note is None


def test_ping_dart_invalid_key(mocker):
    # 키 무효 status → (False, "DART 인증 실패"류 키 미포함 사유), raise 없음.
    mocker.patch("stocksig.io.auth_check._dart_probe", return_value="010")

    ok, note = ping_dart()
    assert ok is False
    assert note
    assert "DART 인증 실패" in note


def test_ping_dart_transient_exception_not_auth_fail(mocker):
    # WR-02: transient 예외(네트워크 장애)는 인증 문제 아님 → (True, None), 1차 소스 미차단.
    mocker.patch(
        "stocksig.io.auth_check._dart_probe",
        side_effect=RuntimeError("연결 실패"),
    )

    ok, note = ping_dart()
    assert ok is True
    assert note is None


def test_ping_dart_note_never_leaks_api_key(mocker):
    # 보안(T-04-03): 무효 키 status 사유 note 에 OPENDART_API_KEY 가 포함되지 않음.
    mocker.patch("stocksig.io.auth_check._dart_probe", return_value="010")

    ok, note = ping_dart()
    assert ok is False
    assert _SECRET_DART_KEY not in (note or "")
