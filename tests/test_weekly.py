"""gap-fix 01-14: compute_weekly (W-FRI resample + forward fill)."""

import pandas as pd

from stocksig.compute.weekly import compute_weekly


def _make_daily(n_weeks: int = 3) -> pd.DataFrame:
    """`n_weeks` 주 × 5영업일 mock 데이터. 주별로 값이 다름."""
    # 월~금 5영업일 × n_weeks
    dates = pd.date_range(start="2026-01-05", periods=5 * n_weeks, freq="B")  # 시작 월요일
    n = len(dates)
    close = [100.0 + i for i in range(n)]
    high = [c + 1 for c in close]
    low = [c - 1 for c in close]
    volume = [1000.0 + i * 10 for i in range(n)]
    df = pd.DataFrame(
        {"Close": close, "High": high, "Low": low, "Volume": volume}, index=dates
    )
    df.index.name = "Date"
    return df


def test_compute_weekly_columns():
    df = _make_daily(2)
    w = compute_weekly(df)
    assert list(w.columns) == ["Close_week", "High_week", "Low_week", "Volume_week"]
    assert len(w) == len(df)


def test_compute_weekly_ffill_broadcast():
    """W-FRI 주봉 값이 Friday부터 다음 Friday까지 ffill로 broadcast 된다 (look-ahead 없음)."""
    df = _make_daily(3)
    w = compute_weekly(df)
    # 첫 주의 Mon~Thu는 prior Friday 값이 없으므로 NaN
    assert w["Close_week"].iloc[:4].isna().all()
    # 첫 주 Friday = df.Close.iloc[4]
    fri1_close = df["Close"].iloc[4]
    assert w["Close_week"].iloc[4] == fri1_close
    # 그 다음 주 Mon~Thu (idx 5..8) ffill로 fri1_close 유지
    for i in range(5, 9):
        assert w["Close_week"].iloc[i] == fri1_close
    # 그 주 Friday (idx 9) = df.Close.iloc[9]
    assert w["Close_week"].iloc[9] == df["Close"].iloc[9]


def test_compute_weekly_volume_sum():
    """주봉 Volume_week = 그 주 5영업일 합."""
    df = _make_daily(2)
    w = compute_weekly(df)
    expected_sum_w1 = df["Volume"].iloc[:5].sum()
    # 그 주 Friday 위치 (iloc=4)에 합산값 출현
    assert w["Volume_week"].iloc[4] == expected_sum_w1


def test_compute_weekly_high_max_low_min():
    df = _make_daily(1)
    w = compute_weekly(df)
    # 그 주 금요일 (idx 4)에 최대/최소
    assert w["High_week"].iloc[4] == df["High"].max()
    assert w["Low_week"].iloc[4] == df["Low"].min()
