"""Phase 3 Wave 4 (03-04 Task 1): naver_scraper.py — finance.naver.com PER 스크래핑 (UTF-8).

`mocker.patch("stocksig.io.naver_scraper.httpx")` 로 네트워크 차단, naver_005930.html
fixture(UTF-8) mock 으로 `#_per` 추출·None 가드·D-07 호출 상한(NAVER_FALLBACK_CAP) 단언.

SPIKE-FINDINGS A5 확정(반드시 따름):
  - 인코딩 = **UTF-8** (euc-kr 아님 — RESEARCH 가정 반증).
  - 셀렉터 #_per=28.94 (005930 실값), select_one None 가드, float(text.replace(",","")).
  - GPM/OPM 미노출 → PER 만 반환.
D-07: run당 NAVER_FALLBACK_CAP(기본 20) 호출 상한, 초과분 스크래핑 미수행 → None.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_HTML_PATH = Path(__file__).parent / "fixtures" / "naver_005930.html"


def _naver_html() -> str:
    return _HTML_PATH.read_text(encoding="utf-8")


class _FakeResp:
    """httpx.Response 흉내 — UTF-8 content + text."""

    def __init__(self, html: str, status_code: int = 200):
        self._html = html
        self.status_code = status_code
        self.content = html.encode("utf-8")
        self.text = html


def test_source_uses_utf8_not_euckr():
    # A5 소스 단언: utf-8 사용, euc-kr 미사용(반증), select_one, None 가드, CAP/reset 존재.
    src = Path("src/stocksig/io/naver_scraper.py").read_text(encoding="utf-8")
    assert "utf-8" in src.lower()
    # A5 — euc-kr/cp949 로 실제 디코드하지 않음(docstring 설명 언급은 허용, 디코드 호출만 금지)
    _lower = src.lower()
    assert '.decode("euc-kr")' not in _lower
    assert ".decode('euc-kr')" not in _lower
    assert 'encoding="euc-kr"' not in _lower
    assert "encoding='euc-kr'" not in _lower
    assert '.decode("cp949")' not in _lower
    assert ".decode('cp949')" not in _lower
    assert 'encoding="cp949"' not in _lower
    assert "encoding='cp949'" not in _lower
    assert "select_one" in src
    assert "NAVER_FALLBACK_CAP" in src
    assert "reset_naver_count" in src


def test_fetch_naver_per_parses_value(mocker):
    # #_per=28.94 추출.
    from stocksig.io import naver_scraper

    naver_scraper.reset_naver_count()
    mock_get = mocker.patch("stocksig.io.naver_scraper.httpx.get", return_value=_FakeResp(_naver_html()))

    per = naver_scraper.fetch_naver_per("005930.KS")
    assert per == pytest.approx(28.94)
    assert mock_get.call_count == 1
    # stock_code 직접 수용(.KS 제거) — URL 에 005930 포함
    url = mock_get.call_args[0][0] if mock_get.call_args[0] else mock_get.call_args.kwargs.get("url", "")
    assert "005930" in url


def test_fetch_naver_per_selector_missing(mocker):
    # select_one("#_per") None → None 가드 (raise 금지).
    from stocksig.io import naver_scraper

    naver_scraper.reset_naver_count()
    mocker.patch(
        "stocksig.io.naver_scraper.httpx.get",
        return_value=_FakeResp("<html><body>no per here</body></html>"),
    )
    assert naver_scraper.fetch_naver_per("005930.KS") is None


def test_fetch_naver_per_http_error(mocker):
    # 429/403·예외 → None 안전 처리 (시세 흐름 전파 금지).
    from stocksig.io import naver_scraper

    naver_scraper.reset_naver_count()
    mocker.patch("stocksig.io.naver_scraper.httpx.get", side_effect=RuntimeError("403 blocked"))
    assert naver_scraper.fetch_naver_per("005930.KS") is None


def test_naver_fallback_cap(mocker):
    # D-07 상한: reset 후 CAP+5회 호출 시 실제 httpx.get 은 CAP회만.
    from stocksig.io import naver_scraper

    naver_scraper.reset_naver_count()
    cap = naver_scraper.NAVER_FALLBACK_CAP
    mock_get = mocker.patch(
        "stocksig.io.naver_scraper.httpx.get", return_value=_FakeResp(_naver_html())
    )

    results = [naver_scraper.fetch_naver_per("005930.KS") for _ in range(cap + 5)]

    # 실제 스크래핑은 CAP회만
    assert mock_get.call_count == cap
    # 상한 도달 후 호출은 None(스크래핑 미수행)
    assert results[cap] is None
    assert results[-1] is None


def test_reset_naver_count_restores(mocker):
    # reset 후 카운터 0 → 다시 스크래핑 가능.
    from stocksig.io import naver_scraper

    naver_scraper.reset_naver_count()
    mock_get = mocker.patch(
        "stocksig.io.naver_scraper.httpx.get", return_value=_FakeResp(_naver_html())
    )
    cap = naver_scraper.NAVER_FALLBACK_CAP
    for _ in range(cap):
        naver_scraper.fetch_naver_per("005930.KS")
    assert naver_scraper.fetch_naver_per("005930.KS") is None  # 상한 도달

    naver_scraper.reset_naver_count()
    assert naver_scraper.fetch_naver_per("005930.KS") == pytest.approx(28.94)
