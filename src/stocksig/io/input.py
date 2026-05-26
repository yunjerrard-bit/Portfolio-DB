"""tickers.txt 리더 — 한 줄당 1 티커, 주석/빈 줄 skip, suffix 보존.

D-05 로깅 포맷: [LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지
input 모듈에서는 TICKER 자리에 `tickers.txt`를 사용한다.

Phase 2 Wave 2 (D-01) 확장:
- `TickerSpec(symbol, tier, industry)` dataclass.
- `read_tickers_extended(path)` — 탭/공백 모두 허용. 1컬럼 입력은 back-compat
  (`tier="", industry=""`). `#` 시작 줄과 빈 줄은 skip.
- `read_tickers(path)` — Phase 1 호환을 위해 `list[str]` (symbol만) 반환.
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TickerSpec:
    """단일 티커 입력 스펙.

    Attributes:
        symbol: yfinance 심볼 (예: "AAPL", "005930.KS").
        tier: 종목 등급 문자열. 1컬럼 입력일 때 "".
        industry: 산업/섹터 이름. 다중 단어 허용. 1·2컬럼 입력일 때 "".
    """

    symbol: str
    tier: str = ""
    industry: str = ""


def read_tickers_extended(path: str | Path) -> list[TickerSpec]:
    """tickers.txt 읽어 `list[TickerSpec]` 반환.

    파싱 규칙 (D-01):
    - 빈 줄 skip, `#` 시작 줄 주석 skip.
    - `line.split()` — 탭/공백 어느 쪽으로 구분되어도 OK.
    - `parts[0]` → symbol. `parts[1]` → tier (없으면 "").
      `" ".join(parts[2:])` → industry (다중 단어 산업명 복원, 없으면 "").
    - 1컬럼 입력은 back-compat: tier="", industry="".
    - 대소문자 변환 없음 (.KS/.KQ suffix 보존).

    Args:
        path: tickers.txt 경로.

    Returns:
        TickerSpec list. 순서는 파일 순서를 따른다.

    Raises:
        SystemExit: 파일이 없거나 유효 티커가 0개일 때 (한국어 stderr 메시지).
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("tickers.txt | tickers.txt 파일을 찾을 수 없습니다: %s", p)
        sys.exit(1)

    specs: list[TickerSpec] = []
    for line in raw.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("#"):
            continue
        parts = stripped.split()
        symbol = parts[0]
        tier = parts[1] if len(parts) >= 2 else ""
        industry = " ".join(parts[2:]) if len(parts) >= 3 else ""
        specs.append(TickerSpec(symbol=symbol, tier=tier, industry=industry))

    if not specs:
        logger.error("tickers.txt | tickers.txt 파일이 비어있습니다.")
        sys.exit(1)

    return specs


def read_tickers(path: str | Path) -> list[str]:
    """Back-compat wrapper — Phase 1 호환을 위해 `list[str]` (symbol만) 반환.

    Phase 1 caller (`main_run.py:99`)이 그대로 동작하도록 유지.
    Wave 4의 `main_run` 리팩터링이 이 wrapper를 제거할 예정.
    """
    return [s.symbol for s in read_tickers_extended(path)]
