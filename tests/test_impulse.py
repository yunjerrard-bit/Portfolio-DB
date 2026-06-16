"""gap-fix 01-14: add_impulse_columns 검증."""

import numpy as np
import pandas as pd

from stocksig.compute.impulse import add_impulse_columns


def test_add_impulse_columns_basic():
    """직접 구성된 입력으로 4가지 결과 검증."""
    n = 5
    dates = pd.date_range(start="2026-01-05", periods=n, freq="B")
    df = pd.DataFrame(
        {
            "Close": [100.0, 101.0, 102.0, 103.0, 104.0],
            "Close_week": [100.0, 101.0, 102.0, 103.0, 104.0],
            # trend 양수
            "EMA_Close_11_trend": [np.nan, 0.01, 0.01, -0.01, -0.01],
            # 주봉 EMA11 진행형 trend (현재 임펄스가 이 컬럼을 직접 읽음)
            "EMA_Close_11_week_trend": [np.nan, 0.0, 0.0, 0.0, 0.0],
            # MACD_OSC: 차분이 +,+,-,-,+ 패턴
            "MACD_OSC": [0.0, 1.0, 2.0, 1.5, 1.0],
            "MACD_OSC_week": [0.0, 1.0, 2.0, 1.5, 1.0],
        },
        index=dates,
    )
    out = add_impulse_columns(df)
    assert "Impulse_daily" in out.columns
    assert "Impulse_weekly" in out.columns

    # index 0: trend=NaN → DEFAULT
    assert out["Impulse_daily"].iloc[0] == ""
    # index 1: trend>0, diff(1.0)>0 → GREEN ("녹색")
    assert out["Impulse_daily"].iloc[1] == "녹색"
    # index 2: trend>0, diff(1.0)>0 → GREEN
    assert out["Impulse_daily"].iloc[2] == "녹색"
    # index 3: trend<0, diff(-0.5)<0 → RED ("적색")
    assert out["Impulse_daily"].iloc[3] == "적색"
    # index 4: trend<0, diff(-0.5)<0 → RED
    assert out["Impulse_daily"].iloc[4] == "적색"


def test_add_impulse_columns_blue_mixed():
    """trend 양수 + osc 음수 (또는 반대) → BLUE (일봉 검증)."""
    n = 3
    # 신규 주봉 로직은 DatetimeIndex(week_close_mask)를 요구하므로 명시 dates 부여.
    dates = pd.date_range(start="2026-01-05", periods=n, freq="B")
    df = pd.DataFrame(
        {
            "Close": [100.0, 101.0, 102.0],
            "Close_week": [100.0, 101.0, 102.0],
            "EMA_Close_11_trend": [0.01, 0.01, 0.01],
            # 신규 로직은 이 컬럼을 더 이상 읽지 않음 (남아 있어도 무해).
            "EMA_Close_11_week_trend": [0.0, 0.0, 0.0],
            "MACD_OSC": [10.0, 5.0, 1.0],  # 단조 하락 → diff < 0
            "MACD_OSC_week": [10.0, 5.0, 1.0],
        },
        index=dates,
    )
    out = add_impulse_columns(df)
    # index 1, 2: trend>0, osc_diff<0 → BLUE ("청색")
    assert out["Impulse_daily"].iloc[1] == "청색"
    assert out["Impulse_daily"].iloc[2] == "청색"


def _weekly_warmup_df(close: np.ndarray) -> pd.DataFrame:
    """주봉 임펄스 부호 단언용 헬퍼 — 신규 로직이 무시하는 진행형 입력 컬럼은
    임의값으로 채운다 (Close·DatetimeIndex 만 신규 주봉 로직에 유효)."""
    n = len(close)
    dates = pd.date_range(start="2020-01-06", periods=n, freq="B")
    cw = pd.Series(close, index=dates)
    return pd.DataFrame(
        {
            "Close": cw,
            "Close_week": cw,
            "EMA_Close_11_trend": [0.0] * n,
            "EMA_Close_11_week_trend": [0.0] * n,  # 신규 로직은 무시
            "MACD_OSC": [0.0] * n,
            "MACD_OSC_week": [0.0] * n,  # 신규 로직은 무시
        },
        index=dates,
    )


def test_add_impulse_columns_weekly_computed():
    """주봉 임펄스: 가속 상승 Close → 워밍업 이후 마지막 완성 주 '녹색'.

    신규 로직은 ema_week_to_date/macd_oscillator_week_to_date를 week_close_mask
    행에서 직접 샘플링한다. MACD 주봉 워밍업(~35주)이 충분하도록 ~60주(300영업일)
    Close를 쓰며, 마지막 구간을 가속 상승시켜 주봉 EMA11↑ & 주봉 MACD-OSC↑를
    모두 만들어 마지막 완성 주가 GREEN("녹색")이 되게 한다.
    """
    n = 300  # ~60주 (충분한 MACD 주봉 워밍업)
    close = np.array([100.0 + i * 0.1 for i in range(n)])
    close[-40:] += np.arange(40) ** 2 * 0.5  # 마지막 구간 가속 상승 (EMA↑ & OSC↑)
    out = add_impulse_columns(_weekly_warmup_df(close))
    assert out["Impulse_weekly"].iloc[-1] == "녹색"
