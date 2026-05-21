"""INPUT-05 RED stub.

Import target (Wave 1 구현 계약):
    from stocksig.config import load_env
"""

import pytest


@pytest.mark.xfail(reason="Wave 1: load_env fail-fast 대기 (INPUT-05)", strict=False)
def test_missing_env_fails(tmp_env_file, capsys):
    # GIVEN: tmp .env with empty contents (no EDGAR_USER_AGENT_EMAIL)
    # WHEN: load_env(path)
    # THEN: SystemExit + 한국어 메시지 stderr
    from stocksig.config import load_env  # noqa: F401
    raise NotImplementedError("Wave 1에서 구현")
