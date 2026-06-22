"""분기말 종가 + 현재가 조달 (D-09 / SC4).

보유 10년치 OHLCV(`fetch_ohlcv_cached`, 캐시 우선 — HIT 시 외부 호출 0)를
분기 경계로 리샘플해 `{YYYYQn: 분기말 종가}` dict 와 최신 현재가를 분리한다.

- 과거 분기 = 그 분기 마지막 거래일 종가(`resample("QE").last()`, 휴장일 자동 처리).
- 현재가 = 가장 최근 거래일 종가(`Close.dropna().iloc[-1]`) — 시트1과 동일 진입점.
- 분기키 표기는 `to_period("Q").astype(str)`로 엔진 `_calendar_quarter_offset`
  출력("YYYYQn")과 정확히 일치(Pitfall 4).

신규 분기 경계 산술 없음 — pandas resample 에 위임(Don't Hand-Roll).
"""

from __future__ import annotations

import pandas as pd

from stocksig.io.market import fetch_ohlcv_cached


def quarter_end_prices(ticker: str) -> tuple[dict[str, float], float | None]:
    """`{YYYYQn: 분기말 종가}` + 현재가 반환 (네트워크 0 가능 — 캐시 HIT 시).

    빈 시계열(전 봉 NaN/무데이터)이면 `({}, None)` — note 부여는 호출자 책임.
    """
    df = fetch_ohlcv_cached(ticker)
    close = df["Close"].dropna()
    if close.empty:
        return {}, None

    # 분기말 마지막 거래일 종가 (구 "Q" 금지 — pandas 2.2+ "QE").
    qe = close.resample("QE").last()
    keys = qe.index.to_period("Q").astype(str)
    qmap = {k: float(v) for k, v in zip(keys, qe.to_numpy())}

    current_price = float(close.iloc[-1])
    return qmap, current_price
