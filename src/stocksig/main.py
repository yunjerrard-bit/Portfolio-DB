"""Compatibility re-export — `stocksig.main.run` → `stocksig.main_run.run`.

PLAN 01-05의 정식 오케스트레이션 모듈은 `stocksig.main_run`이지만,
smoke test (`tests/test_smoke_end_to_end.py`)가 Wave 0 단계에서 이미
`from stocksig.main import run`을 import 한다 (Wave 0 PLAN의 RED stub
계약). 두 경로 모두에서 동일 `run`을 import 할 수 있도록 본 모듈은
얇은 re-export shim 역할만 한다.

신규 코드는 `from stocksig.main_run import run`을 직접 사용한다.
"""

from __future__ import annotations

from stocksig.main_run import run

__all__ = ["run"]
