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
    fund_target = tmp_path / "fundamentals"
    monkeypatch.setattr(cache_mod, "_FUND_DIR", fund_target)
    monkeypatch.setattr(cache_mod, "_fund_cache", None)
    yield
    # close caches to release file handles on Windows
    for attr in ("_cache", "_fund_cache"):
        c = getattr(cache_mod, attr)
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
            monkeypatch.setattr(cache_mod, attr, None)


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


# --- 펀더멘털 7일 TTL 캐시 (FUND-04) ---


def test_make_fund_key_format():
    assert cache_mod.make_fund_key("EDGAR", "AAPL", "2026Q3") == "EDGAR|AAPL|2026Q3"


def test_fund_cache_dir_separate_from_ohlcv():
    cache_mod._get_fund_cache()
    assert cache_mod._FUND_DIR.exists()
    assert cache_mod._FUND_DIR.is_dir()
    # OHLCV 디렉터리와 분리
    assert cache_mod._FUND_DIR != cache_mod._DEFAULT_DIR


def test_fund_cache_put_get_roundtrip():
    payload = {"PER": 28.5, "PEG": 1.2}
    cache_mod.put_fund("EDGAR", "AAPL", "2026Q3", payload)
    got = cache_mod.get_fund("EDGAR", "AAPL", "2026Q3")
    assert got == payload


def test_fund_cache_different_quarter_miss():
    cache_mod.put_fund("EDGAR", "AAPL", "2026Q3", {"PER": 28.5})
    assert cache_mod.get_fund("EDGAR", "AAPL", "2026Q2") is None


def test_fund_cache_ttl_constant():
    assert cache_mod._FUND_TTL_SECONDS == 7 * 24 * 60 * 60


def test_fund_cache_hit_within_7d():
    with freeze_time("2026-05-26 00:01:00") as frozen:
        cache_mod.put_fund("DART", "005930", "2026Q1", {"OPM": 0.15})
        frozen.tick(delta=pd.Timedelta(days=6, hours=23).to_pytimedelta())
        assert cache_mod.get_fund("DART", "005930", "2026Q1") is not None


def test_fund_cache_miss_after_7d():
    with freeze_time("2026-05-26 00:01:00") as frozen:
        cache_mod.put_fund("DART", "005930", "2026Q1", {"OPM": 0.15})
        frozen.tick(delta=pd.Timedelta(days=7, hours=1).to_pytimedelta())
        assert cache_mod.get_fund("DART", "005930", "2026Q1") is None
