"""환경설정 로더 — .env에서 필수 키를 검증하여 fail-fast.

D-05 로깅 포맷: [LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지
config 모듈에서는 TICKER 자리에 `config`를 사용한다.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

REQUIRED_KEYS: tuple[str, ...] = ("EDGAR_USER_AGENT_EMAIL", "OPENDART_API_KEY")


def _is_blank(value: str | None) -> bool:
    return value is None or value.strip() == ""


def load_env(env_path: str | Path | None = None) -> dict[str, str]:
    """python-dotenv로 .env 로드.

    필수 키(EDGAR_USER_AGENT_EMAIL, OPENDART_API_KEY)가 비어있으면
    한국어 메시지를 stderr로 출력 후 sys.exit(1).

    Args:
        env_path: .env 파일 경로. None이면 cwd의 .env를 찾는다.

    Returns:
        검증된 환경변수 dict.
    """
    if env_path is None:
        load_dotenv()
    else:
        load_dotenv(dotenv_path=str(env_path), override=True)

    resolved: dict[str, str] = {}
    for key in REQUIRED_KEYS:
        value = os.environ.get(key)
        if _is_blank(value):
            logger.error("config | .env의 %s 값이 비어있습니다.", key)
            sys.exit(1)
        assert value is not None  # type narrow
        resolved[key] = value.strip()
    return resolved
