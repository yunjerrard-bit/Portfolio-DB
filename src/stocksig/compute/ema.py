"""EMA 계산 (COMP-01/02/03).

Pattern 3 (RESEARCH.md): pandas `.ewm(span=N, adjust=False).mean()`.
TradingView/표준 금융 EMA 공식과 정확히 일치: EMA_t = α·P_t + (1-α)·EMA_{t-1},
α = 2/(span+1).

gap-fix 01-07: 사용자 결정으로 모든 DIFF는 종가 EMA 기준으로 통일.
  - EMA: Close × 4 periods = 4개 (High/Low EMA 제거)
  - DIFF: (price - EMA_Close_N) / EMA_Close_N (비율) × 3 prices × 4 periods = 12개
  - dailychg: EMA_Close_N.diff() × 4 periods = 4개 (가격 단위)
"""

from __future__ import annotations

import pandas as pd

EMA_PERIODS: list[int] = [11, 22, 96, 192]
PRICE_COLS: list[str] = ["Close", "High", "Low"]


def compute_ema(series: pd.Series, span: int) -> pd.Series:
    """단일 EMA 헬퍼 (단위 테스트용 export).

    pandas `.ewm(span=span, adjust=False).mean()` 그대로.
    adjust=True 금지 (Pitfall: TradingView 공식과 불일치).
    """
    return series.ewm(span=span, adjust=False).mean()


def add_ema_columns(df: pd.DataFrame) -> pd.DataFrame:
    """입력 df copy + 20 신규 컬럼 (4 EMA + 12 DIFF + 4 dailychg).

    컬럼 명명 (gap-fix 01-07):
      EMA_Close_{N}             — 종가 EMA, 가격 단위 (4)
      DIFF_{price}_{N}          — (price - EMA_Close_N) / EMA_Close_N, 비율 (12)
      EMA_Close_{N}_dailychg    — EMA_Close_N.diff(), 가격 단위 (4)

      price ∈ {Close, High, Low}, N ∈ EMA_PERIODS.
    """
    out = df.copy()
    # EMA_Close_N + dailychg (4 + 4)
    for n in EMA_PERIODS:
        ema = compute_ema(out["Close"], n)
        ema_col = f"EMA_Close_{n}"
        chg_col = f"EMA_Close_{n}_dailychg"
        out[ema_col] = ema
        out[chg_col] = ema.diff()
    # DIFF_{price}_N — 모두 EMA_Close_N 기준, 비율로 저장 (12)
    for price_col in PRICE_COLS:
        for n in EMA_PERIODS:
            ema_close = out[f"EMA_Close_{n}"]
            diff_col = f"DIFF_{price_col}_{n}"
            out[diff_col] = (out[price_col] - ema_close) / ema_close
    return out
