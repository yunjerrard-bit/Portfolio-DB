"""Phase 06 Plan 01: 기업명 fetch + 30일 캐시 테스트 (네트워크 없음).

`stocksig.io.company.fetch_company_name` 의 폴백 체인(longName→shortName→티커),
캐시 HIT 무호출(COMPANY-04), MISS 후 put, rate-limit 예외 흡수(Pitfall 4)를 검증.

mock 전략: `stocksig.io.company.yf.Ticker` 를 patch 해 `instance.info` 가 고정
dict 를 반환하게 한다 (test_smoke_end_to_end._setup_mock_yfinance 패턴 차용,
대상 모듈만 company 로 변경). 캐시는 conftest autouse 격리(ohlcv/fund)에 더해
company 네임스페이스(`_NAME_DIR`/`_name_cache`)도 각 테스트에서 tmp 격리한다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from yfinance.exceptions import YFRateLimitError

import stocksig.io.cache as cache_mod
import stocksig.io.company as company_mod


# ---------------- fixtures -------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_name_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """company 네임스페이스 캐시를 tmp_path로 격리 (운영 `.cache/company` 오염 방지)."""
    monkeypatch.setattr(cache_mod, "_NAME_DIR", tmp_path / ".cache" / "company")
    monkeypatch.setattr(cache_mod, "_name_cache", None)
    yield
    c = getattr(cache_mod, "_name_cache", None)
    if c is not None:
        try:
            c.close()
        except Exception:
            pass
        monkeypatch.setattr(cache_mod, "_name_cache", None)


def _setup_mock_info(mocker, info: dict):
    """`stocksig.io.company.yf.Ticker(...).info` 가 info dict 를 반환하도록 patch.

    반환된 mock 클래스를 돌려줘 호출 횟수(call_count) 검증에 쓴다.
    """
    ticker_class = mocker.patch("stocksig.io.company.yf.Ticker")
    instance = ticker_class.return_value
    instance.info = info
    return ticker_class


# ---------------- 폴백 체인 ------------------------------------------------


def test_longname_used_when_present(mocker):
    """longName 존재 → longName 반환 (영문 기업명)."""
    _setup_mock_info(mocker, {"longName": "Apple Inc.", "shortName": "Apple"})
    assert company_mod.fetch_company_name("AAPL") == "Apple Inc."


def test_shortname_used_when_longname_missing(mocker):
    """longName None, shortName 정상 → shortName 반환."""
    _setup_mock_info(mocker, {"longName": None, "shortName": "Microsoft"})
    assert company_mod.fetch_company_name("MSFT") == "Microsoft"


def test_ticker_fallback_when_both_missing(mocker):
    """longName/shortName 모두 None/빈값 → 티커 폴백 (COMPANY-03)."""
    _setup_mock_info(mocker, {"longName": None, "shortName": ""})
    assert company_mod.fetch_company_name("X") == "X"


def test_longname_preferred_over_garbage_shortname(mocker):
    """shortName 이 KR 쓰레기값이어도 longName 있으면 longName 우선 (1순위 검증)."""
    _setup_mock_info(
        mocker, {"longName": "Samsung Electronics Co., Ltd.", "shortName": "005930.KS"}
    )
    assert (
        company_mod.fetch_company_name("005930.KS")
        == "Samsung Electronics Co., Ltd."
    )


def test_junk_longname_falls_back_to_ticker(mocker):
    """longName 자체가 콤마-결합 식별자 쓰레기값(티커+Morningstar ID)이면 거부 → 티커 폴백.

    yfinance 가 일부 KR 종목에 longName="263750.KS,0P0001BL7Y,135285" 같은
    쓰레기 문자열을 반환한다 (체크포인트 발견). truthy 라서 폴백을 통과해
    시트1 B열에 사람이 읽을 수 없는 값이 표시되는 문제. shortName 도 결손이면
    티커로 폴백해야 한다 (COMPANY-01 영문 기업명 보장).
    """
    _setup_mock_info(
        mocker, {"longName": "263750.KS,0P0001BL7Y,135285", "shortName": None}
    )
    assert company_mod.fetch_company_name("263750.KS") == "263750.KS"


def test_junk_longname_falls_back_to_clean_shortname(mocker):
    """longName 쓰레기값 + shortName 정상 → shortName 채택 (가드가 long 만 거부)."""
    _setup_mock_info(
        mocker,
        {"longName": "382900.KS,0P0001P9A2,42965", "shortName": "WCP Co., Ltd."},
    )
    assert company_mod.fetch_company_name("382900.KS") == "WCP Co., Ltd."


# ---------------- 캐시 HIT/MISS (COMPANY-04) -------------------------------


def test_cache_hit_no_yfinance_call(mocker):
    """캐시 HIT: put_company_name 선저장 후 fetch → yf.Ticker 호출 0회 (재실행 무호출)."""
    cache_mod.put_company_name("AAPL", "Apple Inc.")
    ticker_class = _setup_mock_info(mocker, {"longName": "SHOULD NOT BE READ"})
    name = company_mod.fetch_company_name("AAPL")
    assert name == "Apple Inc."
    assert ticker_class.call_count == 0


def test_cache_miss_calls_info_then_puts(mocker):
    """캐시 MISS: 첫 호출 시 .info 1회 호출 + put 발생 (이후 HIT)."""
    ticker_class = _setup_mock_info(mocker, {"longName": "Apple Inc."})
    name = company_mod.fetch_company_name("AAPL")
    assert name == "Apple Inc."
    assert ticker_class.call_count == 1
    # put 검증: 캐시에서 직접 읽혀야 한다.
    assert cache_mod.get_company_name("AAPL") == "Apple Inc."


# ---------------- rate-limit 예외 흡수 (Pitfall 4) --------------------------


def test_rate_limit_absorbed_returns_ticker_fallback(mocker):
    """.info 가 YFRateLimitError 를 5회 raise → 예외 흡수 + 티커 폴백 (결손 ≠ 실패)."""
    ticker_class = mocker.patch("stocksig.io.company.yf.Ticker")
    instance = ticker_class.return_value
    # .info property 접근 시마다 raise
    type(instance).info = property(
        lambda self: (_ for _ in ()).throw(YFRateLimitError("rate limited"))
    )
    name = company_mod.fetch_company_name("RATE")
    assert name == "RATE"
    # 폴백값은 캐시에 put 하지 않는다 (다음 실행 재시도 허용).
    assert cache_mod.get_company_name("RATE") is None
