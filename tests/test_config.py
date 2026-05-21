"""INPUT-05 GREEN tests for load_env."""

import pytest

from stocksig.config import load_env


def _clear_env(monkeypatch):
    monkeypatch.delenv("EDGAR_USER_AGENT_EMAIL", raising=False)
    monkeypatch.delenv("OPENDART_API_KEY", raising=False)


def test_missing_env_fails(tmp_env_file, monkeypatch, caplog):
    # INPUT-05: empty .env -> SystemExit + 한국어 stderr (EDGAR key 우선 검증)
    _clear_env(monkeypatch)
    path = tmp_env_file("")
    with caplog.at_level("ERROR"):
        with pytest.raises(SystemExit) as exc_info:
            load_env(path)
    assert exc_info.value.code != 0
    assert "EDGAR_USER_AGENT_EMAIL" in caplog.text
    assert "비어있습니다" in caplog.text


def test_blank_opendart_key_fails(tmp_env_file, monkeypatch, caplog):
    # INPUT-05: EDGAR ok but OPENDART_API_KEY blank -> SystemExit + 한국어 stderr
    _clear_env(monkeypatch)
    path = tmp_env_file('EDGAR_USER_AGENT_EMAIL=test@example.com\nOPENDART_API_KEY=\n')
    with caplog.at_level("ERROR"):
        with pytest.raises(SystemExit) as exc_info:
            load_env(path)
    assert exc_info.value.code != 0
    assert "OPENDART_API_KEY" in caplog.text


def test_valid_env_returns_dict(tmp_env_file, monkeypatch):
    # behavior block: both keys populated -> dict returned, no exit
    _clear_env(monkeypatch)
    path = tmp_env_file(
        "EDGAR_USER_AGENT_EMAIL=test@example.com\nOPENDART_API_KEY=abc123\n"
    )
    result = load_env(path)
    assert result == {
        "EDGAR_USER_AGENT_EMAIL": "test@example.com",
        "OPENDART_API_KEY": "abc123",
    }
