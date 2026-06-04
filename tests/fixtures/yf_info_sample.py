"""yfinance Ticker.info 폴백 mock fixture (실데이터 기반, 03-02 스파이크 확정).

`yf.Ticker(t, session=market._SESSION).info` 의 펀더멘털 키를 AAPL(US) +
005930.KS(KR) 실호출로 확정.  [VERIFIED 2026-06-04]

확정 사실(A4):
- US(AAPL): trailingPE/pegRatio/trailingPegRatio/grossMargins/operatingMargins
  전부 존재.
- KR(005930.KS): **trailingPE 결손(None)** — KR .info 부분지원.
  단 forwardPE/pegRatio/grossMargins/operatingMargins 는 존재 →
  KR GPM/OPM/PEG 의 최후 폴백으로 유효(PER 은 DART→Naver 우선).
- PEG 키: `pegRatio` 와 `trailingPegRatio` 둘 다 존재 →
  yf_fundamentals 는 `info.get("pegRatio") or info.get("trailingPegRatio")`.
- grossMargins/operatingMargins 는 0~1 비율(0.479 = 47.9%) → 시트 0.00% 포맷.

Wave 3 `test_yf_fundamentals.py` 가 이 dict 를 .info mock 으로 주입.
"""

from __future__ import annotations

# AAPL (US) — 전 키 존재 [VERIFIED]
AAPL_INFO: dict[str, float | str | None] = {
    "trailingPE": 37.607273,
    "forwardPE": 32.29211,
    "pegRatio": 2.53,
    "trailingPegRatio": 2.5336,
    "grossMargins": 0.47862,
    "operatingMargins": 0.32275,
    "profitMargins": 0.27152002,
    "currency": "USD",
}

# 005930.KS (KR) — trailingPE 결손, 나머지 부분지원 [VERIFIED]
SAMSUNG_INFO: dict[str, float | str | None] = {
    "trailingPE": None,  # KR .info 결손 [VERIFIED]
    "forwardPE": 6.4164815,
    "pegRatio": 0.2,
    "trailingPegRatio": 0.1996,
    "grossMargins": 0.47678003,
    "operatingMargins": 0.42751,
    "profitMargins": 0.21459,
    "currency": "KRW",
}

# yf_fundamentals 가 조회하는 키 우선순위 (A4 확정)
YF_KEY_MAP: dict[str, tuple[str, ...]] = {
    "per": ("trailingPE",),  # forwardPE 는 의미 다름 → PER 폴백엔 trailingPE 만
    "peg": ("pegRatio", "trailingPegRatio"),  # 둘 다 존재, 앞 우선
    "gpm": ("grossMargins",),
    "opm": ("operatingMargins",),
}
