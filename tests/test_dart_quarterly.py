"""Plan 07-02 Task 3: dart_client.fetch_dart_quarterly_raw — 분기 백필 raw 추출.

`mocker.patch("stocksig.io.dart_client.OpenDartReader")` 로 외부 호출 차단(네트워크 0).
dart_005930_finstate fixture(ALL_ROWS: IS/CIS+BS/CF)로 DataFrame 재구성, 추출기가:
  - 최근 years 년만 루프 backfill (D-01 DART 차등)
  - BS/CF 필드를 SJ_DIV 필터로 손익행 오염 없이 추출 (D-04)
  - quarter 키 = bsns_year+reprt_code → "YYYYQn" 캘린더 분기 (D-08)
  - accession == rcept_no, 결손 None (D-05)
  - YTD as-reported 그대로(분기 분해 없음, Pitfall 4)
를 단언한다.
"""

from __future__ import annotations

import pandas as pd
import pytest

from fixtures.dart_005930_finstate import ALL_ROWS, COLUMNS, EXPECTED_VALUES


def _fixture_df() -> pd.DataFrame:
    """005930 IS/CIS+BS/CF mock DataFrame (정상 응답)."""
    return pd.DataFrame(ALL_ROWS, columns=COLUMNS)


@pytest.fixture(autouse=True)
def _reset_singleton():
    """테스트 간 OpenDartReader 싱글톤 격리 (mock 누수 차단)."""
    from stocksig.io import dart_client

    dart_client._dart_singleton = None
    yield
    dart_client._dart_singleton = None


def _patch_dart(mocker, return_value=None):
    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = (
        return_value if return_value is not None else _fixture_df()
    )
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")
    return mock_cls


def test_source_contains_quarterly_symbols():
    from pathlib import Path

    src = Path("src/stocksig/io/dart_client.py").read_text(encoding="utf-8")
    assert "def fetch_dart_quarterly_raw(" in src
    # QUARTER_CODES = ["11013", "11012", "11014", "11011"] (type 주석 허용)
    assert "QUARTER_CODES" in src
    assert '["11013", "11012", "11014", "11011"]' in src


def test_returns_backfill_rows(mocker):
    from stocksig.io import dart_client

    _patch_dart(mocker)
    rows = dart_client.fetch_dart_quarterly_raw("005930.KS", years=3)

    assert isinstance(rows, list)
    assert len(rows) > 0
    for r in rows:
        assert r["ticker"] == "005930.KS"
        assert r["source"] == "DART"
        assert r["unit"] == "KRW"


def test_stock_code_stripped(mocker):
    # A6: ".KS" 제거된 6자리 stock_code 로 finstate_all 호출.
    from stocksig.io import dart_client

    mock_cls = _patch_dart(mocker)
    dart_client.fetch_dart_quarterly_raw("005930.KS", years=1)

    first_call = mock_cls.return_value.finstate_all.call_args_list[0]
    assert first_call.args[0] == "005930"
    assert first_call.kwargs.get("fs_div") == "CFS"


def test_recent_years_backfill_loop(mocker):
    # D-01: years=3 → (3+1)년 × 4분기 = 16 호출 (최근 3년 차등 backfill).
    from stocksig.io import dart_client

    mock_cls = _patch_dart(mocker)
    dart_client.fetch_dart_quarterly_raw("005930", years=3)

    assert mock_cls.return_value.finstate_all.call_count == 4 * (3 + 1)


def test_bs_cf_fields_extracted(mocker):
    # D-04: BS/CF 신규 필드가 SJ_DIV 필터로 추출됨.
    from stocksig.io import dart_client

    _patch_dart(mocker)
    rows = dart_client.fetch_dart_quarterly_raw("005930", years=1)
    by_field_value = {(r["field"], r["value"]) for r in rows}

    assert ("total_equity", EXPECTED_VALUES["total_equity"]) in by_field_value
    assert ("total_liabilities", EXPECTED_VALUES["total_liabilities"]) in by_field_value
    assert ("total_assets", EXPECTED_VALUES["total_assets"]) in by_field_value
    assert ("operating_cash_flow", EXPECTED_VALUES["operating_cash_flow"]) in by_field_value


def test_bs_period_type_instant_cf_duration(mocker):
    from stocksig.io import dart_client

    _patch_dart(mocker)
    rows = dart_client.fetch_dart_quarterly_raw("005930", years=1)
    pt = {r["field"]: r["period_type"] for r in rows}

    assert pt["total_assets"] == "instant"
    assert pt["operating_cash_flow"] == "duration"
    assert pt["revenue"] == "duration"


def test_calendar_quarter_key_yyyyqn(mocker):
    # D-08: reprt_code 11011(연간) → Qn=4. fixture bsns_year="2025" → quarter 끝자리 Q4 포함.
    from stocksig.io import dart_client

    _patch_dart(mocker)
    rows = dart_client.fetch_dart_quarterly_raw("005930", years=1)
    quarters = {r["quarter"] for r in rows}

    # 모든 quarter 가 "YYYYQn" 형식
    for q in quarters:
        assert len(q) == 6 and q[4] == "Q" and q[:4].isdigit()
    # fixture 가 매 호출 동일 df(연간 11011 라벨)를 돌려주므로 Qn 후보들이 매핑됨
    assert any(q.endswith("Q1") for q in quarters)
    assert any(q.endswith("Q4") for q in quarters)


def test_accession_is_rcept_no(mocker):
    # 각 행 accession == 응답 rcept_no.
    from stocksig.io import dart_client

    _patch_dart(mocker)
    rows = dart_client.fetch_dart_quarterly_raw("005930", years=1)

    for r in rows:
        assert r["accession"] == "20260310000000"  # fixture _META rcept_no


def test_missing_value_is_none(mocker):
    # D-05: 매핑 안 되는 필드는 None (0/-999999 아님). BS 행 없는 df → BS 필드 None.
    from stocksig.io import dart_client

    df = _fixture_df()
    df = df[df["sj_div"].isin(["IS", "CIS"])]  # BS/CF 제거
    _patch_dart(mocker, return_value=df)
    rows = dart_client.fetch_dart_quarterly_raw("005930", years=1)

    bs = [r for r in rows if r["field"] == "total_equity"]
    assert bs and all(r["value"] is None for r in bs)


def test_ytd_as_reported_no_subtraction(mocker):
    # Pitfall 4: YTD 값을 그대로 저장(분기 분해·뺄셈 없음).
    from stocksig.io import dart_client

    _patch_dart(mocker)
    rows = dart_client.fetch_dart_quarterly_raw("005930", years=1)
    rev = [r["value"] for r in rows if r["field"] == "revenue" and r["value"] is not None]

    # fixture 매출 원값 그대로 (분해 시 다른 값이 됨)
    assert EXPECTED_VALUES["revenue"] in rev


def test_singleton_reused_across_years(mocker):
    # Pitfall 1: OpenDartReader 가 루프 내내 1회만 생성(corp_codes 1회 다운로드).
    from stocksig.io import dart_client

    mock_cls = _patch_dart(mocker)
    dart_client.fetch_dart_quarterly_raw("005930", years=3)

    assert mock_cls.call_count == 1  # 싱글톤 — 16 호출 동안 생성 1회


def test_status_dict_skipped(mocker):
    # status dict(데이터없음/쿼터초과) 응답은 skip(에러 없음).
    from stocksig.io import dart_client

    _patch_dart(mocker, return_value={"status": "013", "message": "조회된 데이타가 없습니다."})
    rows = dart_client.fetch_dart_quarterly_raw("005930", years=1)

    assert rows == []
