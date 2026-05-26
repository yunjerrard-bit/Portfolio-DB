"""EXEC-03/05 + INPUT-04 + MKTD-04/06 GREEN tests for runner.run_all.

Pipeline은 callable로 주입 — 실제 yfinance/cache 의존성 없음.
"""

from __future__ import annotations

import pandas as pd
import pytest

from stocksig.io.input import TickerSpec
from stocksig.runner import (
    TickerFailure,
    TickerResult,
    run_all,
)


def _make_df(rows: int) -> pd.DataFrame:
    return pd.DataFrame({"Close": [100.0] * rows})


def _classify(sym: str) -> str:
    return "KR" if sym.endswith((".KS", ".KQ")) else "US"


def test_all_success():
    specs = [TickerSpec("AAPL"), TickerSpec("MSFT"), TickerSpec("005930.KS")]

    def pipeline(sym: str) -> pd.DataFrame:
        return _make_df(2500)

    results, failures = run_all(specs, _classify, pipeline)
    assert len(results) == 3
    assert len(failures) == 0
    by_sym = {r.spec.symbol: r for r in results}
    assert by_sym["AAPL"].market == "US"
    assert by_sym["005930.KS"].market == "KR"
    for r in results:
        assert isinstance(r, TickerResult)
        assert len(r.enriched_df) == 2500


def test_invalid_ticker_isolated():
    specs = [TickerSpec("AAPL"), TickerSpec("BADSYM")]

    def pipeline(sym: str) -> pd.DataFrame:
        if sym == "BADSYM":
            raise ValueError("잘못된 티커 형식")
        return _make_df(2500)

    results, failures = run_all(specs, _classify, pipeline)
    assert len(results) == 1
    assert len(failures) == 1
    assert results[0].spec.symbol == "AAPL"
    assert failures[0].spec.symbol == "BADSYM"
    assert "잘못된 티커" in failures[0].reason


def test_network_error_isolated():
    specs = [TickerSpec("AAPL"), TickerSpec("MSFT"), TickerSpec("BAD")]

    def pipeline(sym: str) -> pd.DataFrame:
        if sym == "BAD":
            raise ConnectionError("net")
        return _make_df(2500)

    results, failures = run_all(specs, _classify, pipeline)
    assert len(results) == 2
    assert len(failures) == 1
    assert failures[0].spec.symbol == "BAD"
    assert failures[0].reason == "net"
    assert {r.spec.symbol for r in results} == {"AAPL", "MSFT"}


def test_partial_data_marked_failure():
    # D-06: 1000 rows (40% of 2500, below 50% threshold) → failure
    specs = [TickerSpec("AAPL"), TickerSpec("PARTIAL")]

    def pipeline(sym: str) -> pd.DataFrame:
        if sym == "PARTIAL":
            return _make_df(1000)
        return _make_df(2500)

    results, failures = run_all(specs, _classify, pipeline)
    assert len(results) == 1
    assert len(failures) == 1
    assert failures[0].spec.symbol == "PARTIAL"
    assert failures[0].reason.startswith("부분 데이터:")
    assert "1000 거래일" in failures[0].reason
    assert "40%" in failures[0].reason


def test_korean_progress_log(caplog):
    specs = [TickerSpec("AAPL"), TickerSpec("BAD")]

    def pipeline(sym: str) -> pd.DataFrame:
        if sym == "BAD":
            raise ValueError("불량")
        return _make_df(2500)

    with caplog.at_level("INFO"):
        run_all(specs, _classify, pipeline)
    text = caplog.text
    assert "OK AAPL" in text
    assert "FAIL BAD" in text
    # [k/N] 패턴 — 둘 다 N=2
    assert "/2]" in text


def test_failure_summary_log(caplog):
    specs = [TickerSpec("A"), TickerSpec("B"), TickerSpec("C")]

    def pipeline(sym: str) -> pd.DataFrame:
        if sym == "B":
            raise ValueError("fail-B")
        return _make_df(2500)

    with caplog.at_level("INFO"):
        run_all(specs, _classify, pipeline)
    text = caplog.text
    assert "총 3 티커 중 성공 2 / 실패 1" in text
    assert "실패 티커: B" in text


def test_max_workers_4(monkeypatch):
    captured = {}

    real_pool = __import__("concurrent.futures").futures.ThreadPoolExecutor

    class SpyPool(real_pool):
        def __init__(self, *a, **kw):
            captured["max_workers"] = kw.get("max_workers", a[0] if a else None)
            super().__init__(*a, **kw)

    monkeypatch.setattr("stocksig.runner.ThreadPoolExecutor", SpyPool)

    def pipeline(sym):
        return _make_df(2500)

    run_all([TickerSpec("AAPL")], _classify, pipeline)
    assert captured["max_workers"] == 4
