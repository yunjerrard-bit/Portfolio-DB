"""io.cache 단위 테스트."""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd
import pytest
from freezegun import freeze_time

from stocksig.io import cache as cache_mod


@pytest.fixture(autouse=True)
def _isolated_cache_dir(tmp_path, monkeypatch):
    """각 테스트 격리: 디렉토리/싱글톤 리셋."""
    target = tmp_path / "ohlcv"
    monkeypatch.setattr(cache_mod, "_DEFAULT_DIR", target)
    monkeypatch.setattr(cache_mod, "_cache", None)
    yield
    # close cache to release file handles on Windows
    if cache_mod._cache is not None:
        try:
            cache_mod._cache.close()
        except Exception:
            pass
        monkeypatch.setattr(cache_mod, "_cache", None)


def _df():
    return pd.DataFrame({"Close": [100.0, 101.5, 99.2]}, index=pd.date_range("2026-05-20", periods=3))


def test_cache_dir_created():
    cache_mod._get_cache()
    assert cache_mod._DEFAULT_DIR.exists()
    assert cache_mod._DEFAULT_DIR.is_dir()


def test_put_then_get_roundtrip():
    df = _df()
    cache_mod.put_ohlcv("AAPL", df)
    got = cache_mod.get_ohlcv("AAPL")
    assert got is not None
    pd.testing.assert_frame_equal(got, df)


def test_miss_returns_none():
    assert cache_mod.get_ohlcv("DOES_NOT_EXIST") is None


def test_hit_within_ttl():
    with freeze_time("2026-05-26 00:01:00") as frozen:
        cache_mod.put_ohlcv("AAPL", _df())
        # stay within same calendar day so make_key() resolves to same key
        frozen.tick(delta=pd.Timedelta(hours=23, minutes=58).to_pytimedelta())
        assert cache_mod.get_ohlcv("AAPL") is not None


def test_miss_after_24h():
    with freeze_time("2026-05-26 09:00:00") as frozen:
        cache_mod.put_ohlcv("AAPL", _df())
        # cross to next day -> make_key() yields different key -> miss
        frozen.tick(delta=pd.Timedelta(hours=24, minutes=1).to_pytimedelta())
        assert cache_mod.get_ohlcv("AAPL") is None


def test_make_key_format():
    assert cache_mod.make_key("AAPL", date(2026, 5, 26)) == "AAPL|2026-05-26"


def test_cache_logs_hit_miss_korean(caplog):
    caplog.set_level(logging.INFO, logger=cache_mod.__name__)
    cache_mod.get_ohlcv("AAPL")  # miss
    cache_mod.put_ohlcv("AAPL", _df())
    cache_mod.get_ohlcv("AAPL")  # hit
    text = "\n".join(r.getMessage() for r in caplog.records)
    assert "cache MISS" in text
    assert "cache HIT" in text
    assert "AAPL" in text
    assert "캐시" in text  # Korean prefix present
