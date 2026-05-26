"""Phase 2 Wave 2: 멀티 티커 fan-out 오케스트레이터.

`ThreadPoolExecutor(max_workers=4)`로 N개 티커를 병렬 처리하고,
per-ticker 예외를 `TickerFailure`로 격리해 한 종목의 실패가 전체 실행을
중단시키지 않게 한다 (INPUT-04, MKTD-04, EXEC-03).

D-06 결정: 부분 데이터 (rows < 50% of 예상 2500 거래일)는 경고가 아니라
실패로 간주한다 — `_validate_row_count`가 한국어 reason 문자열을 만들고
`process_ticker`가 `ValueError(reason)`을 raise해 except에서 잡힌다.

Korean progress log (D-05 포맷): `[k/N] OK <sym>` / `[k/N] FAIL <sym> | <reason>`.
"""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from stocksig.io.input import TickerSpec

logger = logging.getLogger(__name__)

_MAX_WORKERS = 4
_EXPECTED_TRADING_DAYS = 2500
# 임계 완화 (2026-05-26): 50% → 20 거래일 절대값.
# 사용자 결정: 최근 IPO/스핀오프 종목도 가진 데이터만큼 분석. 부족한 지표는 NaN으로 자동 표시.
_MIN_TRADING_DAYS = 20


@dataclass
class TickerResult:
    """성공한 티커의 결과."""

    spec: TickerSpec
    enriched_df: pd.DataFrame
    market: str  # "US" | "KR"


@dataclass
class TickerFailure:
    """실패한 티커의 한국어 reason 문자열."""

    spec: TickerSpec
    reason: str


def _validate_row_count(ticker: str, df: pd.DataFrame) -> str | None:
    """행 수가 최소 임계(20 거래일) 미만이면 한국어 reason 반환, 아니면 None.

    완화된 임계 (2026-05-26): IPO 직후 종목도 가진 데이터만큼 분석한다.
    EMA192/rolling(200) 같은 장기 지표는 부족 시 자동 NaN으로 표시된다.
    """
    n = len(df)
    if n < _MIN_TRADING_DAYS:
        return f"데이터 부족: {n} 거래일 (최소 {_MIN_TRADING_DAYS} 필요)"
    return None


def process_ticker(
    spec: TickerSpec,
    classify_market: Callable[[str], str],
    pipeline: Callable[[str], pd.DataFrame],
) -> TickerResult:
    """단일 티커 처리 (스레드 worker 진입점).

    pipeline 예외는 그대로 propagate시켜 `run_all`의 except에서 잡힌다.
    부분 데이터 검출 시 `ValueError(한국어 reason)`을 raise해 일관된
    failure path를 유지한다.
    """
    market = classify_market(spec.symbol)
    df = pipeline(spec.symbol)
    reason = _validate_row_count(spec.symbol, df)
    if reason is not None:
        raise ValueError(reason)
    return TickerResult(spec=spec, enriched_df=df, market=market)


def run_all(
    specs: list[TickerSpec],
    classify_market: Callable[[str], str],
    pipeline: Callable[[str], pd.DataFrame],
) -> tuple[list[TickerResult], list[TickerFailure]]:
    """N 티커 fan-out 실행 + per-ticker 예외 격리.

    Args:
        specs: TickerSpec list.
        classify_market: `symbol → "US"|"KR"` 분류 함수.
        pipeline: `symbol → enriched DataFrame` — fetch+compute 합본.
                  예외를 raise하면 해당 티커만 TickerFailure로 격리된다.

    Returns:
        `(results, failures)` — 모든 티커가 둘 중 하나에 들어간다.
    """
    total = len(specs)
    results: list[TickerResult] = []
    failures: list[TickerFailure] = []

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as executor:
        future_to_spec = {
            executor.submit(process_ticker, spec, classify_market, pipeline): spec
            for spec in specs
        }
        completed = 0
        for future in as_completed(future_to_spec):
            spec = future_to_spec[future]
            completed += 1
            try:
                result = future.result()
                results.append(result)
                logger.info("[%d/%d] OK %s", completed, total, spec.symbol)
            except Exception as e:
                # D-06: ValueError("부분 데이터: ...") 메시지 그대로 보존.
                reason = str(e) if str(e) else type(e).__name__
                failures.append(TickerFailure(spec=spec, reason=reason))
                logger.warning(
                    "[%d/%d] FAIL %s | %s", completed, total, spec.symbol, reason
                )

    logger.info(
        "총 %d 티커 중 성공 %d / 실패 %d", total, len(results), len(failures)
    )
    if failures:
        failed_syms = ", ".join(f.spec.symbol for f in failures)
        logger.warning("실패 티커: %s", failed_syms)

    return results, failures
