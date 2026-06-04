"""yfinance .info 펀더멘털 폴백 — market._SESSION 재사용(신규 세션 금지).

EDGAR/DART 결손 지표를 보완하는 최후 폴백. RESEARCH Anti-Pattern 준수:
새 curl_cffi/httpx 세션을 만들지 않고 `market._SESSION` 을 재사용하며,
기존 2 RPS yahoo limiter(`@throttled_yahoo`)를 그대로 통과한다.

키 매핑(A4 확정):
    PER = info.get("trailingPE")                              # forwardPE 는 의미 다름
    PEG = info.get("pegRatio") or info.get("trailingPegRatio")  # 키 변동 가드
    GPM = info.get("grossMargins")                            # 0~1 비율
    OPM = info.get("operatingMargins")
"""

from __future__ import annotations

import logging

import yfinance as yf

from stocksig.io.market import _SESSION  # 재사용 — 신규 세션 생성 금지
from stocksig.io.throttle import throttled_yahoo  # 기존 2 RPS 재사용

logger = logging.getLogger(__name__)


@throttled_yahoo
def fetch_yf_info(ticker: str) -> dict:
    """`yf.Ticker(ticker, session=_SESSION).info` 에서 PER/PEG/GPM/OPM None-safe 추출.

    KR(.KS) 부분지원: trailingPE 결손(None) 가능 → None-safe `.get()` 으로 흡수.
    """
    info = yf.Ticker(ticker, session=_SESSION).info or {}
    return {
        "PER": info.get("trailingPE"),
        "PEG": info.get("pegRatio") or info.get("trailingPegRatio"),
        "GPM": info.get("grossMargins"),
        "OPM": info.get("operatingMargins"),
    }
