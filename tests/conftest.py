"""Shared pytest fixtures for stocksig test suite.

Wave 0 (PLAN 01-01) provides:
  - mock_ohlcv_df: deterministic mock yfinance OHLCV DataFrame (2700 rows)
  - tmp_tickers_file: factory fixture writing arbitrary content to a tmp tickers.txt
  - tmp_env_file: factory fixture writing arbitrary content to a tmp .env
  - rsi_golden: loads tests/fixtures/rsi_golden.json
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import numpy as np
import pandas as pd
import pytest

import stocksig.io.cache as _cache_mod
import stocksig.io.fundamentals_store as _store_mod


@pytest.fixture(autouse=True)
def _isolated_fundamentals_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """모든 테스트에서 SQLite 펀더멘털 store를 tmp_path로 격리 (운영 `data/fundamentals.db` 오염 방지).

    `_DB_PATH`는 상대 경로(`data/fundamentals.db`)라 프로젝트 루트에서 pytest 실행 시
    운영 DB가 그대로 쓰인다. autouse로 전 테스트를 강제 격리해 store 모듈이 운영 분기
    히스토리를 오염시키는 사고를 차단한다(`_isolated_disk_cache` L23-47 패턴 모방, sqlite 치환).
    """
    monkeypatch.setattr(_store_mod, "_DB_PATH", tmp_path / "data" / "fundamentals.db")
    monkeypatch.setattr(_store_mod, "_conn", None)
    yield
    # Windows: sqlite 연결 핸들을 닫아야 tmp_path 정리가 PermissionError 없이 끝난다.
    conn = getattr(_store_mod, "_conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
    monkeypatch.setattr(_store_mod, "_conn", None)


@pytest.fixture(autouse=True)
def _isolated_disk_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """모든 테스트에서 디스크 캐시를 tmp_path로 격리 (운영 `.cache/` 오염 방지).

    `.cache/ohlcv`는 상대 경로라 프로젝트 루트에서 pytest 실행 시 운영 캐시가
    그대로 쓰인다. yf.Ticker 등 캐시 계층 *아래*를 mock한 테스트가 run()을
    돌리면 합성 OHLCV가 `put_ohlcv()`로 운영 캐시에 저장되어, 같은 날 실제
    main.py 실행이 가짜 데이터를 cache HIT으로 읽는 사고가 발생했다
    (AAPL 시트 2026-05-20 고정 + 합성 가격). autouse로 전 테스트에 강제 격리.
    개별 테스트의 자체 격리 픽스처는 이 위에 덮어써도 무방하다.
    """
    # Plan 10-03(FUND-11): 구 펀더멘털 7일 캐시(_FUND_DIR/_fund_cache) 제거 →
    # OHLCV·기업명 캐시만 격리. OHLCV/company 디렉터리·싱글톤은 무손상 유지.
    monkeypatch.setattr(_cache_mod, "_DEFAULT_DIR", tmp_path / ".cache" / "ohlcv")
    monkeypatch.setattr(_cache_mod, "_cache", None)
    monkeypatch.setattr(_cache_mod, "_NAME_DIR", tmp_path / ".cache" / "company")
    monkeypatch.setattr(_cache_mod, "_name_cache", None)
    yield
    # Windows: diskcache 파일 핸들을 닫아야 tmp_path 정리가 실패하지 않는다.
    for attr in ("_cache", "_name_cache"):
        c = getattr(_cache_mod, attr, None)
        if c is not None:
            try:
                c.close()
            except Exception:
                pass
        monkeypatch.setattr(_cache_mod, attr, None)


@pytest.fixture
def mock_ohlcv_df() -> pd.DataFrame:
    """Deterministic mock yfinance OHLCV DataFrame.

    ~2700 rows (≈10 years of trading days), DatetimeIndex,
    columns=[Open, High, Low, Close, Volume]. Close drifts around 100,
    high=close*1.02, low=close*0.98, volume=random ints.
    """
    rng = np.random.default_rng(seed=42)
    n_rows = 2700
    dates = pd.date_range(end=pd.Timestamp("2026-05-20"), periods=n_rows, freq="B")
    drift = rng.normal(loc=0.0, scale=1.0, size=n_rows).cumsum() * 0.1
    close = 100.0 + drift
    high = close * 1.02
    low = close * 0.98
    open_ = close + rng.normal(loc=0.0, scale=0.5, size=n_rows)
    volume = rng.integers(low=1_000_000, high=10_000_000, size=n_rows)
    df = pd.DataFrame(
        {
            "Open": open_,
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": volume,
        },
        index=dates,
    )
    df.index.name = "Date"
    return df


@pytest.fixture
def tmp_tickers_file(tmp_path: Path) -> Callable[[str], Path]:
    """Factory: writes content into a tmp tickers.txt and returns its path."""

    def _make(content: str) -> Path:
        p = tmp_path / "tickers.txt"
        p.write_text(content, encoding="utf-8")
        return p

    return _make


@pytest.fixture
def tmp_env_file(tmp_path: Path) -> Callable[[str], Path]:
    """Factory: writes content into a tmp .env and returns its path."""

    def _make(content: str) -> Path:
        p = tmp_path / ".env"
        p.write_text(content, encoding="utf-8")
        return p

    return _make


@pytest.fixture
def rsi_golden() -> dict:
    """Load Wilder RSI(14) golden fixture."""
    fixture_path = Path(__file__).parent / "fixtures" / "rsi_golden.json"
    with fixture_path.open(encoding="utf-8") as fh:
        return json.load(fh)
