"""finance.naver.com PER 스크래핑 — KR 2차 폴백 전용 (PER만, UTF-8).

DART 결손 시 PER 만 보완하는 KR 2차 폴백. GPM/OPM 은 Naver 가 미노출하므로
(RESEARCH Open Q4) PER 단일 지표만 반환한다.

SPIKE-FINDINGS A5 [VERIFIED 2026-06-04] (반드시 따름):
  - 인코딩 = **UTF-8** (RESEARCH 의 euc-kr 가정 반증 — 현재 페이지 charset=utf-8.
    euc-kr/cp949 디코드 시 UnicodeDecodeError). httpx 기본 charset 또는 content.decode("utf-8").
  - 셀렉터 `#_per`=28.94 (005930 실값). select_one None 가드 → float(text.replace(",","")).

D-07 — 네이버는 *소수 폴백 전용* (T-03-12, DoS/ToS 가드):
  - 모듈 레벨 `NAVER_FALLBACK_CAP`(env override, 기본 20) + `_naver_calls` 카운터.
  - fetch_naver_per 는 카운터 ≥ CAP 이면 스크래핑 없이 None 반환(상한 도달).
  - runner 는 run 시작 시 `reset_naver_count()` 호출.
  - 429/403·빈 응답(소프트 블록)은 None 안전 처리(시세·실행 흐름 전파 금지).
  - @throttled_yahoo(2 RPS 보수적) 재사용 — 신규 limiter 불필요.
"""

from __future__ import annotations

import logging
import os

import httpx
from bs4 import BeautifulSoup

from stocksig.io.throttle import throttled_yahoo  # 보수적 2 RPS 재사용

logger = logging.getLogger(__name__)

# D-07 — run당 네이버 폴백 호출 상한 (env override 가능).
NAVER_FALLBACK_CAP: int = int(os.getenv("NAVER_FALLBACK_CAP", "20"))

# 모듈 레벨 호출 카운터 — run 시작 시 reset_naver_count() 로 초기화.
_naver_calls: int = 0

_NAVER_URL = "https://finance.naver.com/item/main.naver?code={code}"
_UA = {"User-Agent": "Mozilla/5.0"}


def reset_naver_count() -> None:
    """run 시작 시 네이버 폴백 카운터 초기화 (D-07)."""
    global _naver_calls
    _naver_calls = 0


@throttled_yahoo
def fetch_naver_per(ticker: str) -> float | None:
    """finance.naver.com 에서 PER(`#_per`)만 스크래핑 (UTF-8, A5).

    D-07 상한: `_naver_calls >= NAVER_FALLBACK_CAP` 이면 스크래핑 없이 None 반환.
    GPM/OPM 미노출(Open Q4) → PER 만 반환.
    429/403·예외·셀렉터 부재·float 파싱 실패는 모두 None 안전 처리(흐름 전파 금지).

    Args:
        ticker: yfinance 심볼 (예: "005930.KS"). ".KS" 제거 후 6자리 stock_code.

    Returns:
        PER float, 또는 결손/상한초과/오류 시 None.
    """
    global _naver_calls

    # D-07 상한 — 초과분은 스크래핑 미수행(yf 직행 신호).
    if _naver_calls >= NAVER_FALLBACK_CAP:
        logger.info("%s | Naver 폴백 상한(%d) 도달 — 스크래핑 건너뜀", ticker, NAVER_FALLBACK_CAP)
        return None

    _naver_calls += 1
    code = ticker.split(".")[0]
    url = _NAVER_URL.format(code=code)

    try:
        r = httpx.get(url, headers=_UA, timeout=10)
        # 429/403 등 비정상 응답 → None 안전 처리.
        if getattr(r, "status_code", 200) >= 400:
            logger.info("%s | Naver 응답 status=%s → None", ticker, r.status_code)
            return None
        # UTF-8 디코드 (A5 — euc-kr 아님). httpx 기본 charset 신뢰 + content 폴백.
        html = r.text or r.content.decode("utf-8")
        soup = BeautifulSoup(html, "lxml")
        el = soup.select_one("#_per")
        if el is None:  # 셀렉터 부재 가드 (페이지 구조 변경/빈 응답)
            return None
        text = el.get_text(strip=True).replace(",", "")
        return float(text)
    except (httpx.HTTPError, ValueError, AttributeError, UnicodeDecodeError, RuntimeError) as e:
        # 소프트 블록·파싱 실패 모두 None (T-03-09/12 — 펀더멘털 결손 ≠ 티커 실패).
        logger.info("%s | Naver 스크래핑 실패 흡수: %s", ticker, e)
        return None
