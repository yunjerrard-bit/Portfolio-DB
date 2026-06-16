"""임펄스 시스템 (gap-fix 01-14, Phase 5 주봉 주간화).

일봉 임펄스: EMA_Close_11_trend 부호 + MACD_OSC.diff() 부호 (매일 변동, 불변).

주봉 임펄스 (Phase 5): 금요일-대-금요일 주간 계단형 신호.
- 주 마지막 거래일(week_close_mask=True; 금, 휴장 시 그 주 실제 마지막 거래일)에서
  ema_week_to_date(Close, 11)·macd_oscillator_week_to_date(Close)를 샘플링한다.
  이 두 시리즈는 금요일(주 마지막 거래일) 행에서 진짜 주봉값과 일치하므로,
  마스크 샘플 = '완성 주' 값이다.
- 각 완성 주 값의 직전 완성 주 대비 변화 부호를 decide_impulse 에 넣어 한 주의 색을
  결정하고, reindex(daily_index, method="ffill")로 주중 행에 직전 완성 주 값을
  broadcast 한다 → 한 주 내 동일 값(계단형, D2).
- 첫 완성 주는 직전 주가 없어 diff=NaN → decide_impulse 가 DEFAULT("") 반환.

→ 녹색/적색/청색/DEFAULT 텍스트 컬럼.
"""

from __future__ import annotations

import pandas as pd

from stocksig.compute.color_rules import decide_impulse
from stocksig.compute.indicators import (
    ema_week_to_date,
    macd_oscillator_week_to_date,
)
from stocksig.compute.weekly import week_close_mask


def _weekly_impulse_series(df: pd.DataFrame) -> pd.Series:
    """금-금 부호 조합 기반 주봉 임펄스를 daily index로 broadcast 한 Series.

    1. week_close_mask(df.index)로 주 마지막 거래일(완성 주 경계)을 식별한다.
    2. ema_week_to_date(Close, 11)·macd_oscillator_week_to_date(Close)를 그 마스크
       행에서 샘플링 → 완성 주 시퀀스 (금요일 행 = 진짜 주봉값과 일치).
    3. 각 완성 주의 직전 완성 주 대비 차분(.diff()) 부호로 decide_impulse 판정.
       첫 완성 주는 diff=NaN → DEFAULT("").
    4. 완성 주별 임펄스 값을 reindex(df.index, method="ffill")로 주중 broadcast.
    """
    mask = week_close_mask(df.index)
    ema11_week = ema_week_to_date(df["Close"], 11)
    osc_week = macd_oscillator_week_to_date(df["Close"])

    # 완성 주(주 마지막 거래일)만 샘플링 → 완성 주 시퀀스.
    ema_weekly = ema11_week[mask]
    osc_weekly = osc_week[mask]

    # 직전 완성 주 대비 변화 (첫 완성 주는 NaN → DEFAULT).
    ema_week_diff = ema_weekly.diff()
    osc_week_diff = osc_weekly.diff()

    weekly_impulse = pd.Series(
        [
            decide_impulse(t, d).value
            for t, d in zip(ema_week_diff, osc_week_diff)
        ],
        index=ema_weekly.index,
    )

    # 완성 주 값을 주중 행에 forward fill (직전 완성 주 값 고정, D2 계단형).
    return weekly_impulse.reindex(df.index, method="ffill")


def add_impulse_columns(df: pd.DataFrame) -> pd.DataFrame:
    """(일)Impulse_daily, (주)Impulse_weekly 컬럼 추가.

    의존 컬럼:
      - EMA_Close_11_trend           (일봉 EMA11 pct_change, add_ema_columns 산출)
      - MACD_OSC                     (일봉)
      - Close                        (주봉 임펄스 샘플링 입력, DatetimeIndex 필수)

    주봉 임펄스는 더 이상 main_run 의 진행형 표시 컬럼
    (EMA_Close_11_week_trend·MACD_OSC_week)을 읽지 않는다 — 그것들은 진행형이라
    계단형을 깨뜨린다. 대신 Close 에서 ema_week_to_date/macd_oscillator_week_to_date
    를 직접 주 마지막 거래일에 샘플링한다.
    """
    out = df.copy()

    # 일봉 임펄스 (불변 — 매일 변동)
    osc_diff = out["MACD_OSC"].diff()
    ema_trend_daily = out["EMA_Close_11_trend"]
    out["Impulse_daily"] = [
        decide_impulse(t, d).value for t, d in zip(ema_trend_daily, osc_diff)
    ]

    # 주봉 임펄스 — 금-금 계단형 (Phase 5)
    out["Impulse_weekly"] = _weekly_impulse_series(out)

    return out
