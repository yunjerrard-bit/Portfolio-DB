"""Phase 3 Wave 3 (03-03 Task 1): fundamentals.py 데이터모델 + PEG 산식 + US 라우팅.

순수 산식 헬퍼(PER/PEG/마진)와 `fetch_fundamentals` US 라우팅을 mock 주입으로 검증.
edgar/yf 호출은 `edgar_fn`/`yf_fn` 콜러블 주입(test_runner.py L23-41 analog)으로
네트워크 없이 격리. PEG 엣지케이스 4종(성장률≤0/0분모/전년없음/PER없음) +
per-metric 폴백(EDGAR→yf) provenance + 예외 흡수를 단언.
"""

from __future__ import annotations

from stocksig.io.fundamentals import (
    FundamentalsResult,
    MetricCell,
    _compute_margin,
    _compute_peg,
    _compute_per,
    fetch_fundamentals,
)


# --- 순수 산식 헬퍼 ------------------------------------------------------

def test_compute_per_normal():
    cell = _compute_per(last_close=100.0, eps_ttm=8.0)
    assert cell.value == 12.5
    assert cell.note is None


def test_compute_per_eps_none():
    cell = _compute_per(last_close=100.0, eps_ttm=None)
    assert cell.value is None
    assert "EPS" in (cell.note or "")


def test_compute_per_eps_non_positive():
    cell = _compute_per(last_close=100.0, eps_ttm=0.0)
    assert cell.value is None
    assert "EPS" in (cell.note or "")
    cell2 = _compute_per(last_close=100.0, eps_ttm=-2.0)
    assert cell2.value is None


def test_compute_peg_normal():
    # PER=12.5, eps_ttm=10, eps_prior=8 → growth=(10/8-1)*100=25 → PEG=0.5
    cell = _compute_peg(per=12.5, eps_ttm=10.0, eps_prior=8.0)
    assert cell.value == 0.5
    assert cell.note is None


def test_compute_peg_growth_non_positive():
    # eps_ttm < eps_prior → growth ≤ 0 → 빈값 + 사유
    cell = _compute_peg(per=12.5, eps_ttm=8.0, eps_prior=10.0)
    assert cell.value is None
    assert "성장률" in (cell.note or "")


def test_compute_peg_zero_prior():
    cell = _compute_peg(per=12.5, eps_ttm=10.0, eps_prior=0.0)
    assert cell.value is None
    assert "전년 EPS 0" in (cell.note or "")


def test_compute_peg_prior_none():
    cell = _compute_peg(per=12.5, eps_ttm=10.0, eps_prior=None)
    assert cell.value is None
    assert "전년 EPS 미존재" in (cell.note or "")


def test_compute_peg_per_none():
    cell = _compute_peg(per=None, eps_ttm=10.0, eps_prior=8.0)
    assert cell.value is None
    assert "PER 없음" in (cell.note or "")


def test_compute_margin_normal():
    cell = _compute_margin(numer=40.0, denom=100.0)
    assert cell.value == 0.4
    assert cell.note is None


def test_compute_margin_denom_zero():
    cell = _compute_margin(numer=40.0, denom=0.0)
    assert cell.value is None
    cell2 = _compute_margin(numer=40.0, denom=None)
    assert cell2.value is None


def test_compute_margin_numer_none():
    cell = _compute_margin(numer=None, denom=100.0)
    assert cell.value is None


# --- fetch_fundamentals US 라우팅 (mock 주입) ---------------------------

def _edgar_full():
    """EDGAR 전지표 채움 raw dict + quarter_label."""
    return {
        "eps_ttm": 8.07,
        "eps_prior": 6.40,
        "revenue": 451_442_000_000.0,
        "gross_profit": 195_201_000_000.0,
        "op_income": 133_050_000_000.0,
        "quarter_label": "2026Q2",
    }


def test_default_us_path_uses_edgar_cache(mocker):
    # FUND-04/SC4 회귀 가드: edgar_fn 미주입 시 기본 클로저가 fetch_edgar_cached(7d 캐시)를
    # 타야 한다(fetch_edgar_raw 직접 호출로 캐시 우회 금지). 같은 주 재실행 HIT 의 전제.
    cached = mocker.patch(
        "stocksig.io.edgar_client.fetch_edgar_cached", return_value=_edgar_full()
    )
    raw = mocker.patch("stocksig.io.edgar_client.fetch_edgar_raw", return_value=_edgar_full())
    res = fetch_fundamentals("AAPL", "US", last_close=200.0, yf_fn=lambda t: {})
    assert isinstance(res, FundamentalsResult)
    assert cached.call_count == 1  # 캐시 경로 사용
    assert raw.call_count == 0     # 기본 클로저가 raw 를 직접 부르지 않음
    # 캐시 키는 "YYYYQn" 형태(주 단위 안정)
    _, kwargs = cached.call_args[0], cached.call_args
    assert cached.call_args[0][0] == "AAPL"
    assert cached.call_args[0][1].endswith(("Q1", "Q2", "Q3", "Q4"))


def test_fetch_fundamentals_all_edgar():
    # ① EDGAR 전지표 채움 → source 전부 EDGAR
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: _edgar_full(),
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    assert res.per.value is not None
    assert res.per.source == "EDGAR"
    assert res.gpm.source == "EDGAR"
    assert res.opm.source == "EDGAR"
    assert res.peg.source == "EDGAR"
    # quarter 메타가 note에 들어감
    assert "2026Q2" in (res.per.note or "")


def test_fallback_chain():
    # ② EDGAR GPM 결손 → yf 보완 (GPM source=yf, 나머지 EDGAR) — FUND-05
    edgar_missing_gpm = {
        "eps_ttm": 8.07,
        "eps_prior": 6.40,
        "revenue": 451_442_000_000.0,
        "gross_profit": None,  # GOOGL 결손 케이스
        "op_income": 133_050_000_000.0,
        "quarter_label": "2026Q2",
    }
    yf_info = {"PER": 30.0, "PEG": 2.0, "GPM": 0.478, "OPM": 0.32}
    res = fetch_fundamentals(
        "GOOGL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar_missing_gpm,
        yf_fn=lambda t: yf_info,
    )
    # GPM만 yf로 채워짐
    assert res.gpm.value == 0.478
    assert res.gpm.source == "yf"
    # 나머지는 EDGAR 유지 (덮어쓰기 금지)
    assert res.per.source == "EDGAR"
    assert res.opm.source == "EDGAR"


def test_fetch_fundamentals_peg_growth_non_positive():
    # ③ PEG 성장률 ≤ 0 → 빈값 + 사유
    edgar = dict(_edgar_full(), eps_ttm=6.0, eps_prior=8.0)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.peg.value is None
    assert "성장률" in (res.peg.note or "")


def test_fetch_fundamentals_peg_zero_prior():
    # ④ PEG 0분모
    edgar = dict(_edgar_full(), eps_prior=0.0)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.peg.value is None
    assert "전년 EPS 0" in (res.peg.note or "")


def test_fetch_fundamentals_peg_prior_none():
    # ⑤ PEG 전년 EPS None
    edgar = dict(_edgar_full(), eps_prior=None)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.peg.value is None
    assert "전년 EPS 미존재" in (res.peg.note or "")


def test_fetch_fundamentals_per_eps_non_positive():
    # ⑥ PER eps≤0 → 빈값
    edgar = dict(_edgar_full(), eps_ttm=0.0)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar,
        yf_fn=lambda t: {},
    )
    assert res.per.value is None


def test_fetch_fundamentals_absorbs_exception():
    # stub 예외 주입 시 raise 없이 빈 FundamentalsResult 반환 (흡수)
    def _boom(t):
        raise RuntimeError("edgar 폭발")

    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=_boom,
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    assert res.per.value is None
    assert res.peg.value is None
    assert res.gpm.value is None
    assert res.opm.value is None


# --- fetch_fundamentals KR 라우팅 (metric별 차등 폴백, mock 주입) ----------

def _dart_full():
    """DART 전지표 채움 raw dict (005930 스파이크값 스케일).

    eps=기본주당이익(KRW/주), eps_prior=전년 기본주당이익(PEG 입력).
    """
    return {
        "revenue": 300_870_000_000_000.0,
        "gross_profit": 110_000_000_000_000.0,
        "op_income": 43_601_000_000_000.0,
        "net_income": 45_206_000_000_000.0,
        "eps": 6_605.0,
        "eps_prior": 4_950.0,
        "note": None,
    }


def test_fetch_fundamentals_kr_all_dart():
    # ① DART 전지표 채움 → source 전부 DART (Naver/yf 미호출)
    naver_calls = {"n": 0}
    yf_calls = {"n": 0}

    def _naver(t):
        naver_calls["n"] += 1
        return None

    def _yf(t):
        yf_calls["n"] += 1
        return {}

    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=lambda t: _dart_full(),
        naver_fn=_naver,
        yf_fn=_yf,
    )
    assert isinstance(res, FundamentalsResult)
    # PER = 80000 / 6605
    assert res.per.value is not None
    assert res.per.source == "DART"
    assert res.peg.source == "DART"
    assert res.gpm.source == "DART"
    assert res.opm.source == "DART"
    # GPM = 110조 / 300.87조
    assert abs(res.gpm.value - (110_000_000_000_000.0 / 300_870_000_000_000.0)) < 1e-9
    # 전지표 DART 충족 → 폴백 미호출
    assert naver_calls["n"] == 0
    assert yf_calls["n"] == 0


def test_fetch_fundamentals_kr_per_naver_fallback():
    # ② DART PER 결손(eps None) → Naver 보완 (PER source=Naver)
    dart_no_eps = dict(_dart_full(), eps=None, eps_prior=None)
    naver_calls = {"n": 0}

    def _naver(t):
        naver_calls["n"] += 1
        return 12.3  # Naver PER

    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=lambda t: dart_no_eps,
        naver_fn=_naver,
        yf_fn=lambda t: {},
    )
    assert res.per.value == 12.3
    assert res.per.source == "Naver"
    assert naver_calls["n"] == 1
    # GPM/OPM 은 DART 유지
    assert res.gpm.source == "DART"
    assert res.opm.source == "DART"


def test_fetch_fundamentals_kr_per_yf_fallback():
    # ③ DART PER 결손 + Naver None → yf (PER source=yf)
    dart_no_eps = dict(_dart_full(), eps=None, eps_prior=None)

    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=lambda t: dart_no_eps,
        naver_fn=lambda t: None,  # Naver 결손/상한초과
        yf_fn=lambda t: {"PER": 15.5},
    )
    assert res.per.value == 15.5
    assert res.per.source == "yf"


def test_fetch_fundamentals_kr_gpm_skips_naver():
    # ④ DART GPM 결손 → Naver 미호출(GPM 미노출)·yf 직행
    dart_no_gpm = dict(_dart_full(), gross_profit=None)
    naver_calls = {"n": 0}

    def _naver(t):
        naver_calls["n"] += 1
        return 12.3

    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=lambda t: dart_no_gpm,
        naver_fn=_naver,
        yf_fn=lambda t: {"GPM": 0.42},
    )
    assert res.gpm.value == 0.42
    assert res.gpm.source == "yf"
    # GPM 폴백은 Naver 를 절대 거치지 않음 (PER 은 DART 로 채워져 Naver 불필요)
    assert naver_calls["n"] == 0
    # PER 은 DART 유지
    assert res.per.source == "DART"


def test_fetch_fundamentals_kr_all_missing():
    # ⑤ 전 소스 결손 → 빈값 + 한국어 사유, raise 없음
    dart_empty = {
        "revenue": None, "gross_profit": None, "op_income": None,
        "net_income": None, "eps": None, "eps_prior": None,
        "note": "DART 데이터 미존재",
    }
    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=lambda t: dart_empty,
        naver_fn=lambda t: None,
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    assert res.per.value is None
    assert res.peg.value is None
    assert res.gpm.value is None
    assert res.opm.value is None
    # 한국어 사유 존재
    assert res.per.note is not None


def test_fetch_fundamentals_kr_absorbs_exception():
    # KR dart_fn 예외 → raise 없이 빈 결과
    def _boom(t):
        raise RuntimeError("dart 폭발")

    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=_boom,
        naver_fn=lambda t: None,
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    assert res.per.value is None


# --- skip_edgar / skip_dart (04-03 Task 2: 1차만 스킵, yf 폴백 유지) ---------

def test_skip_edgar_skips_primary_but_keeps_yf(monkeypatch):
    # skip_edgar=True → EDGAR 1차 edgar_fn 미호출, yf 폴백은 여전히 채움(독립 소스, A4).
    edgar_calls = {"n": 0}
    yf_calls = {"n": 0}

    def _edgar(t):
        edgar_calls["n"] += 1
        return _edgar_full()

    def _yf(t):
        yf_calls["n"] += 1
        return {"PER": 30.0, "PEG": 2.0, "GPM": 0.478, "OPM": 0.32}

    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=_edgar, yf_fn=_yf,
        skip_edgar=True,
    )
    # EDGAR 1차 호출 안 됨
    assert edgar_calls["n"] == 0
    # yf 폴백은 호출되어 지표를 채움 (독립 소스 유지)
    assert yf_calls["n"] == 1
    assert res.per.value == 30.0
    assert res.per.source == "yf"
    assert res.gpm.value == 0.478


def test_skip_edgar_missing_metric_note_when_no_yf():
    # skip_edgar=True 이고 yf 도 비면 결손 + EDGAR 인증 실패류 사유, EDGAR source 없음.
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: _edgar_full(),
        yf_fn=lambda t: {},
        skip_edgar=True,
    )
    assert res.per.value is None
    assert res.per.source != "EDGAR"
    assert "EDGAR 인증 실패" in (res.per.note or "")


def test_skip_dart_skips_primary_but_keeps_naver_yf_chain():
    # skip_dart=True → DART 1차 미호출, Naver→yf 폴백 체인은 작동.
    dart_calls = {"n": 0}

    def _dart(t):
        dart_calls["n"] += 1
        return _dart_full()

    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=_dart,
        naver_fn=lambda t: 12.3,  # Naver PER 폴백
        yf_fn=lambda t: {"GPM": 0.42},
        skip_dart=True,
    )
    assert dart_calls["n"] == 0
    # Naver PER 폴백 작동
    assert res.per.value == 12.3
    assert res.per.source == "Naver"
    # yf GPM 폴백 작동
    assert res.gpm.value == 0.42
    assert res.gpm.source == "yf"


def test_skip_defaults_false_no_regression():
    # skip 미전달(기본 False) → 기존 동작과 동일(EDGAR 1차 채움).
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: _edgar_full(),
        yf_fn=lambda t: {},
    )
    assert res.per.source == "EDGAR"
    assert res.gpm.source == "EDGAR"


# --- T-04-03 회귀: 예외 원문(자격증명 URL) 로그/note 누설 차단 (CR-01) ------

def test_fetch_fundamentals_exception_no_secret_leak(caplog):
    """DART 예외 메시지에 crtfc_key 가 담겨도 로그·note 에 원문이 보간되지 않는다.

    opendartreader 경유 requests 예외는 `crtfc_key=<API 키>` 가 포함된 전체
    요청 URL 을 메시지에 담을 수 있다. 외곽 except 는 타입명만 로깅하고
    note 는 고정 사유만 사용해야 한다 (T-04-03 / 04-REVIEW CR-01).
    """
    import dataclasses
    import logging

    secret = "crtfc_key=SUPER-SECRET-KEY-12345"

    def _boom(t):
        raise RuntimeError(
            f"HTTPSConnectionPool: /api/fnlttSinglAcnt.json?{secret} failed"
        )

    caplog.set_level(logging.WARNING, logger="stocksig.io.fundamentals")
    res = fetch_fundamentals(
        "005930.KS", "KR", last_close=80_000.0,
        dart_fn=_boom,
        naver_fn=lambda t: None,
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    # 로그: 예외 원문 금지, 타입명만 허용
    assert secret not in caplog.text
    assert "RuntimeError" in caplog.text
    # 워크북 note: 고정 사유만, 원문 금지
    for f in dataclasses.fields(res):
        cell = getattr(res, f.name)
        assert secret not in (cell.note or "")
        assert (cell.note or "") == "조회 실패: 데이터 소스 오류"


def test_fetch_fundamentals_us_exception_no_secret_leak(caplog):
    """US(EDGAR) 외곽 except 도 동일하게 원문 보간이 없어야 한다."""
    import dataclasses
    import logging

    marker = "User-Agent: someone@example.com"

    def _boom(t):
        raise RuntimeError(f"403 Forbidden ({marker})")

    caplog.set_level(logging.WARNING, logger="stocksig.io.fundamentals")
    res = fetch_fundamentals(
        "AAPL", "US", last_close=100.0,
        edgar_fn=_boom,
        yf_fn=lambda t: {},
    )
    assert isinstance(res, FundamentalsResult)
    assert marker not in caplog.text
    assert "RuntimeError" in caplog.text
    for f in dataclasses.fields(res):
        cell = getattr(res, f.name)
        assert marker not in (cell.note or "")


# --- WR-01: NaN 결손 가드 (NaN 을 None 과 동일하게 결손 처리) ------------------
# runner.process_ticker 가 주입하는 last_close = df.iloc[-1].get("Close") 가 장중
# 부분 행 등으로 NaN 일 수 있다. NaN 은 비교(<=0 등)가 모두 False 라 기존 `is None`
# 가드를 통과해 값 있는 셀·provenance 로 새므로(D-05 위반), _is_missing 단일 게이트로
# 차단해야 한다. 외부 의존 없이 float("nan") 직접 사용.

def test_compute_per_last_close_nan():
    cell = _compute_per(last_close=float("nan"), eps_ttm=8.0)
    assert cell.value is None
    assert "종가" in (cell.note or "")


def test_compute_per_eps_nan():
    # NaN EPS 가 ≤0 비교(False)로 새지 않고 결손으로 차단.
    cell = _compute_per(last_close=100.0, eps_ttm=float("nan"))
    assert cell.value is None


def test_compute_peg_per_nan():
    # NaN PER 이 _compute_peg 로 전파돼 값 있는 셀이 되지 않는다.
    cell = _compute_peg(per=float("nan"), eps_ttm=10.0, eps_prior=8.0)
    assert cell.value is None


def test_compute_peg_eps_nan():
    cell = _compute_peg(per=12.5, eps_ttm=float("nan"), eps_prior=8.0)
    assert cell.value is None


def test_compute_margin_nan():
    cell = _compute_margin(numer=float("nan"), denom=100.0)
    assert cell.value is None
    cell2 = _compute_margin(numer=40.0, denom=float("nan"))
    assert cell2.value is None


def test_fetch_fundamentals_us_nan_last_close():
    # NaN last_close → PER 결손(value None) AND provenance 미부여(source None).
    res = fetch_fundamentals(
        "AAPL", "US", last_close=float("nan"),
        edgar_fn=lambda t: _edgar_full(),  # eps_ttm 양수 반환
        yf_fn=lambda t: {},
    )
    assert res.per.value is None
    assert res.per.source is None


def test_fill_us_yf_nan_rejected():
    # EDGAR PER 결손(eps None) + yf 가 NaN PER 반환 → 결손 유지, "yf" 미부여.
    edgar_no_eps = dict(_edgar_full(), eps_ttm=None)
    res = fetch_fundamentals(
        "AAPL", "US", last_close=200.0,
        edgar_fn=lambda t: edgar_no_eps,
        yf_fn=lambda t: {"PER": float("nan")},
    )
    assert res.per.value is None
    assert res.per.source is None
