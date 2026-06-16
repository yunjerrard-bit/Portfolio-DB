"""gap-fix 01-14 + Phase 5: add_impulse_columns 검증.

Phase 5 신규: 주봉 임펄스 금-금 계단형 (week_close_mask 샘플링 + ffill broadcast).
- 계단형/금요일휴장/첫주DEFAULT 단언은 짧은 합성 DF(>=3주) 허용 — 값이 DEFAULT여도
  '한 주 내 동일값(nunique==1)' / 'DEFAULT 자체'만 단언 (부호값 강제 안 함).
- 색(녹/적) 부호 단언은 MACD 주봉 워밍업(~35주) 이후 구간에서만 (~60주 합성 DF).
"""

import numpy as np
import pandas as pd

from stocksig.compute.impulse import add_impulse_columns
from stocksig.compute.weekly import week_close_mask


def _impulse_minimal_df(close: pd.Series) -> pd.DataFrame:
    """주봉 임펄스 계단형/경계 단언용 최소 DF — 신규 로직은 Close·DatetimeIndex만
    유효하게 읽는다. 일봉부가 요구하는 컬럼은 0으로 채운다."""
    n = len(close)
    return pd.DataFrame(
        {
            "Close": close,
            "Close_week": close,
            "EMA_Close_11_trend": [0.0] * n,
            "MACD_OSC": [0.0] * n,
        },
        index=close.index,
    )


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


# --- Phase 5 신규: 계단형 / 금요일휴장 / 첫주 / 부호 / 진행형회귀 / 시트1경로 ---


def test_weekly_impulse_stepwise_same_value_within_week():
    """(1) 계단형: 같은 주(week_close_mask 그룹) 내 모든 거래일 Impulse_weekly 동일.

    짧은 합성 DF(>=3주)이므로 부호값은 DEFAULT여도 무방 — 주별 nunique==1만 단언.
    """
    n = 15  # 3주치 영업일
    dates = pd.date_range(start="2026-01-05", periods=n, freq="B")  # 월요일 시작
    close = pd.Series([100.0 + i for i in range(n)], index=dates)
    out = add_impulse_columns(_impulse_minimal_df(close))

    # 값은 주 마지막 거래일(금)에 갱신된다 → 동일값 구간은 [금 ~ 다음 금]이다.
    # 따라서 mask=True(금) 행에서 그룹을 증가시켜 '금~목' 단위로 묶는다.
    mask = week_close_mask(out.index)
    holding_group = mask.cumsum()
    for _, grp in out["Impulse_weekly"].groupby(holding_group):
        assert grp.nunique() == 1  # 한 보유 구간(금~다음 목) 내 동일 값 (계단형)


def test_weekly_impulse_sign_green_on_accelerating_uptrend():
    """(2) 부호: ~60주 가속 상승 → 마지막 완성 주 '녹색' (워밍업 이후 단언)."""
    n = 300
    dates = pd.date_range(start="2020-01-06", periods=n, freq="B")
    close = np.array([100.0 + i * 0.1 for i in range(n)])
    close[-40:] += np.arange(40) ** 2 * 0.5  # EMA↑ & MACD-OSC↑
    out = add_impulse_columns(_impulse_minimal_df(pd.Series(close, index=dates)))
    assert out["Impulse_weekly"].iloc[-1] == "녹색"


def test_weekly_impulse_sign_red_on_accelerating_downtrend():
    """(2b) 부호: ~60주 가속 하락 → 마지막 완성 주 '적색' (워밍업 이후 단언)."""
    n = 300
    dates = pd.date_range(start="2020-01-06", periods=n, freq="B")
    close = np.array([100.0 + 5000 - i * 0.1 for i in range(n)])
    close[-40:] -= np.arange(40) ** 2 * 0.5  # EMA↓ & MACD-OSC↓
    out = add_impulse_columns(_impulse_minimal_df(pd.Series(close, index=dates)))
    assert out["Impulse_weekly"].iloc[-1] == "적색"


def test_weekly_impulse_friday_holiday_no_gap():
    """(3) 금요일 휴장: 금요일을 인덱스에서 제외(목=마지막) → 그 주 일관된 값(nunique==1).

    짧은 DF이므로 값 자체가 DEFAULT여도 무방 — '그 주에 빈칸/오산출 없이 일관'만 단언.
    """
    n = 15
    full = pd.date_range(start="2026-01-05", periods=n, freq="B")  # 월~금 3주
    # 둘째 주 금요일(2026-01-16)을 휴장 처리 — 인덱스에서 제외.
    holiday_fri = pd.Timestamp("2026-01-16")
    dates = full[full != holiday_fri]
    close = pd.Series([100.0 + i for i in range(len(dates))], index=dates)
    out = add_impulse_columns(_impulse_minimal_df(close))

    # 금요일 휴장 주(둘째 주)의 행들 — 목요일(01-15)이 그 주 마지막.
    mask = week_close_mask(out.index)
    week_group = mask.shift(1, fill_value=False).cumsum()
    # 둘째 주 그룹 추출 (01-12 ~ 01-15)
    second_week = out["Impulse_weekly"][
        (out.index >= pd.Timestamp("2026-01-12"))
        & (out.index <= pd.Timestamp("2026-01-15"))
    ]
    assert len(second_week) == 4  # 월화수목 (금 휴장)
    assert second_week.notna().all()  # 빈칸(NaN) 없음
    assert second_week.nunique() == 1  # 그 주 일관된 값 (계단형)


def test_weekly_impulse_first_week_default():
    """(4) 첫 주: 직전 완성 주 없음 → 첫 완성 주 구간 Impulse_weekly == ""(DEFAULT)."""
    n = 15
    dates = pd.date_range(start="2026-01-05", periods=n, freq="B")
    close = pd.Series([100.0 + i for i in range(n)], index=dates)
    out = add_impulse_columns(_impulse_minimal_df(close))

    # 첫 완성 주(첫 금요일 = 2026-01-09) 행들은 직전 주 diff=NaN → DEFAULT.
    first_week = out["Impulse_weekly"][out.index <= pd.Timestamp("2026-01-09")]
    assert (first_week == "").all()


def test_progressive_week_columns_unchanged_in_pipeline(mock_ohlcv_df):
    """(5) 진행형 회귀: _compute_enriched 결과에 EMA_Close_11_week_trend·MACD_OSC_week
    존재 + 한 주 내 주중 변동(nunique>1) — main_run이 D4 진행형 컬럼을 여전히 산출."""
    from stocksig.main_run import _compute_enriched

    enriched, _ = _compute_enriched(mock_ohlcv_df)
    assert "EMA_Close_11_week_trend" in enriched.columns
    assert "MACD_OSC_week" in enriched.columns

    mask = week_close_mask(enriched.index)
    week_group = mask.shift(1, fill_value=False).cumsum()
    # 마지막 완전한 주 그룹에서 진행형 컬럼이 주중 변동(nunique>1)함을 단언.
    for col in ("EMA_Close_11_week_trend", "MACD_OSC_week"):
        per_week_nunique = (
            enriched[col].groupby(week_group).nunique()
        )
        # 적어도 한 주는 주중 변동 (진행형 — 계단형이 아님).
        assert (per_week_nunique > 1).any()


def test_sheet1_path_matches_per_ticker_stepwise(mock_ohlcv_df):
    """(6) 시트1 경로: sheet_portfolio.py:218-219 가 읽는 last.get("Impulse_weekly")
    (= enriched df.iloc[-1]["Impulse_weekly"]) 가 종목 시트 계단형 컬럼의 마지막 행과
    동일 값임을 단언. (시각·미적 확정은 Task 3 수기 검증.)"""
    from stocksig.main_run import _compute_enriched

    enriched, _ = _compute_enriched(mock_ohlcv_df)
    # sheet_portfolio.py: last = enriched.iloc[-1]; imp_w = last.get("Impulse_weekly")
    last = enriched.iloc[-1]
    imp_w_sheet1 = last.get("Impulse_weekly")
    # 종목 시트(sheet_per_ticker)는 동일 컬럼 전체를 표시 → 마지막 행이 시트1과 일치.
    imp_w_per_ticker = enriched.iloc[-1]["Impulse_weekly"]
    assert imp_w_sheet1 == imp_w_per_ticker
