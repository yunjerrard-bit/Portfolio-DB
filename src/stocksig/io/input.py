"""tickers.txt 리더 — 한 줄당 1 티커, 주석/빈 줄 skip, suffix 보존.

D-05 로깅 포맷: [LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지
input 모듈에서는 TICKER 자리에 `tickers.txt`를 사용한다.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)


def read_tickers(path: str | Path) -> list[str]:
    """tickers.txt 읽기.

    한 줄당 1 티커, 빈 줄 skip, '#' 시작 줄 주석 skip, strip 후 보존.
    대소문자 변환 없음 (US/KR suffix-agnostic — '.KS', '.KQ' 보존).

    Args:
        path: tickers.txt 경로.

    Returns:
        티커 list[str]. 순서는 파일 순서를 따른다.

    Raises:
        SystemExit: 파일이 없거나 유효 티커가 0개일 때 (한국어 stderr 메시지).
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("tickers.txt | tickers.txt 파일을 찾을 수 없습니다: %s", p)
        sys.exit(1)

    tickers: list[str] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        tickers.append(stripped)

    if not tickers:
        logger.error("tickers.txt | tickers.txt 파일이 비어있습니다.")
        sys.exit(1)

    return tickers
