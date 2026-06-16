"""io.cache 단위 테스트."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
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


# --- hit/miss 집계 카운터 (EXEC-04, lock 보호) ---


def test_reset_then_get_stats_all_zero():
    cache_mod.reset_cache_stats()
    assert cache_mod.get_cache_stats() == {
        "ohlcv_hit": 0,
        "ohlcv_miss": 0,
        "fund_hit": 0,
        "fund_miss": 0,
        # 06-01 (COMPANY-04): 기업명 캐시 통계 키 추가 — reset 후 0 초기화.
        "name_hit": 0,
        "name_miss": 0,
    }


def test_ohlcv_hit_miss_counted():
    cache_mod.reset_cache_stats()
    cache_mod.get_ohlcv("MISSING")  # miss
    cache_mod.put_ohlcv("AAPL", _df())
    cache_mod.get_ohlcv("AAPL")  # hit
    stats = cache_mod.get_cache_stats()
    assert stats["ohlcv_hit"] == 1
    assert stats["ohlcv_miss"] == 1


def test_fund_hit_miss_counted():
    cache_mod.reset_cache_stats()
    cache_mod.get_fund("EDGAR", "AAPL", "2026Q3")  # miss
    cache_mod.put_fund("EDGAR", "AAPL", "2026Q3", {"PER": 1.0})
    cache_mod.get_fund("EDGAR", "AAPL", "2026Q3")  # hit
    stats = cache_mod.get_cache_stats()
    assert stats["fund_hit"] == 1
    assert stats["fund_miss"] == 1


def test_get_stats_returns_copy():
    cache_mod.reset_cache_stats()
    cache_mod.get_ohlcv("MISSING")  # miss → ohlcv_miss == 1
    snapshot = cache_mod.get_cache_stats()
    snapshot["ohlcv_miss"] = 999  # 반환값 변형
    # 내부 _stats 는 오염되지 않아야 함
    assert cache_mod.get_cache_stats()["ohlcv_miss"] == 1


def test_concurrent_get_ohlcv_counts_exact():
    """race: 같은 키로 다수 호출해도 hit+miss 합계가 호출 횟수와 정확히 일치 (lock 증명)."""
    cache_mod.reset_cache_stats()
    cache_mod.put_ohlcv("AAPL", _df())  # 이후 호출은 모두 HIT
    n_calls = 200

    def _call(_i):
        return cache_mod.get_ohlcv("AAPL")

    with ThreadPoolExecutor(max_workers=4) as ex:
        list(ex.map(_call, range(n_calls)))

    stats = cache_mod.get_cache_stats()
    total = (
        stats["ohlcv_hit"]
        + stats["ohlcv_miss"]
        + stats["fund_hit"]
        + stats["fund_miss"]
    )
    assert total == n_calls, f"카운터 합계 {total} != 호출 {n_calls} (lost update)"
