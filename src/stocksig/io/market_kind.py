"""티커 접미사 기반 시장 분류 (US/KR).

Yahoo Finance 티커 표기를 기준으로 한국 주식(`.KS`, `.KQ`, `.KOSPI`,
`.KOSDAQ`)을 `"KR"`, 나머지를 `"US"`로 분류. 일본(`.T`), 홍콩(`.HK`),
런던(`.L`) 등의 비미·비한 시장은 본 분류기에서 `"US"`로 떨어진다
(L-14 제약). 후속 단계에서 EDGAR/DART 라우팅 분기에 사용.
"""
from __future__ import annotations

from typing import Literal

KR_SUFFIXES: tuple[str, ...] = (".KS", ".KQ", ".KOSDAQ", ".KOSPI")


def classify_market(symbol: str) -> Literal["US", "KR"]:
    """대문자 변환 후 KR 접미사 매칭. 미매칭은 'US'."""
    s = symbol.upper()
    for suf in KR_SUFFIXES:
        if s.endswith(suf):
            return "KR"
    return "US"
