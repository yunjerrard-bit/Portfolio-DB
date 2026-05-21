"""EMA 계산 (COMP-01/02/03).

Pattern 3 (RESEARCH.md): pandas `.ewm(span=N, adjust=False).mean()`.
TradingView/표준 금융 EMA 공식과 정확히 일치: EMA_t = α·P_t + (1-α)·EMA_{t-1},
α = 2/(span+1).
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
    """입력 df copy + 36 신규 컬럼 (12 EMA + 12 DIFF + 12 dailychg).

    컬럼 명명:
      EMA_{price}_{N}, DIFF_{price}_{N}, EMA_{price}_{N}_dailychg
      price ∈ {Close, High, Low}, N ∈ EMA_PERIODS.
    """
    out = df.copy()
    for price_col in PRICE_COLS:
        for n in EMA_PERIODS:
            ema = compute_ema(out[price_col], n)
            ema_col = f"EMA_{price_col}_{n}"
            diff_col = f"DIFF_{price_col}_{n}"
            chg_col = f"EMA_{price_col}_{n}_dailychg"
            out[ema_col] = ema
            out[diff_col] = out[price_col] - ema
            out[chg_col] = ema.diff()
    return out
