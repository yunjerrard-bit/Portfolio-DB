"""Expanding stats + 누적 스칼라 (COMP-04/05/06).

Pattern 4 (RESEARCH.md): pandas `.expanding().median()` / `.std()`, ddof=1 default.
Look-ahead-free: expanding window은 [0..i] 만 사용.
"""

from __future__ import annotations

import pandas as pd


def add_expanding_stats(df: pd.DataFrame, data_cols: list[str]) -> pd.DataFrame:
    """각 col별 {col}_median, {col}_std 신규 컬럼 추가 (expanding window).

    ddof=1 (표본 표준편차) — pandas default.
    """
    out = df.copy()
    for col in data_cols:
        out[f"{col}_median"] = out[col].expanding().median()
        out[f"{col}_std"] = out[col].expanding().std()
    return out


def cumulative_scalars(
    df: pd.DataFrame, data_cols: list[str]
) -> dict[str, dict[str, float]]:
    """{col: {'median': float, 'std': float}} — 전체 누적 (행 3·4용).

    ddof=1 (pandas default).
    """
    return {
        col: {
            "median": float(df[col].median()),
            "std": float(df[col].std()),
        }
        for col in data_cols
    }
