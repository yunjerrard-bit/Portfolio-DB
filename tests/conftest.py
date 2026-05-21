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
