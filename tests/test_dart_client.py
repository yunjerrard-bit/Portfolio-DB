"""Phase 3 Wave 4 (03-04 Task 1): dart_client.py — DART finstate_all + account 매핑 + throttle + cache.

`mocker.patch("stocksig.io.dart_client.OpenDartReader")` 로 외부 호출 차단(test_edgar_client.py
analog), dart_005930_finstate fixture(DataFrame 재구성)로 fetch_dart_raw 산출 dict 단언.
account_id 1차 / account_nm 2차 매핑(A3), thstrm_amount 쉼표 int 파싱(T-03-10),
status 가드(000/013/020), stock_code 직접 수용(.KS 제거, A6), cache HIT 재호출 0 단언.

SPIKE-FINDINGS A3/A6 확정 경로:
  dart = OpenDartReader(api_key)
  df = dart.finstate_all("005930", year, reprt_code="11011", fs_div="CFS")  # 6자리 직접 수용
  status "000"=정상 "013"=데이터없음 "020"=쿼터초과
  thstrm_amount 쉼표 문자열 → int(s.replace(",",""))
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest
from diskcache import Cache

from fixtures.dart_005930_finstate import COLUMNS, EXPECTED_VALUES, IS_CIS_ROWS


def _fixture_df() -> pd.DataFrame:
    """005930 IS/CIS mock DataFrame (status 컬럼 없는 정상 응답)."""
    return pd.DataFrame(IS_CIS_ROWS, columns=COLUMNS)


def test_source_uses_dart_imports():
    # 소스 단언: throttled_dart, DART_ACCOUNT_ID_MAP/DART_ACCOUNT_MAP, finstate_all 존재.
    src = Path("src/stocksig/io/dart_client.py").read_text(encoding="utf-8")
    assert "throttled_dart" in src
    assert "DART_ACCOUNT_ID_MAP" in src
    assert "DART_ACCOUNT_MAP" in src
    assert "finstate_all" in src


def test_fetch_dart_raw_accepts_stock_code(mocker):
    # A6: finstate_all 이 6자리 stock_code 직접 수용(".KS" 제거).
    from stocksig.io import dart_client

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_inst = mock_cls.return_value
    mock_inst.finstate_all.return_value = _fixture_df()
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    dart_client.fetch_dart_raw("005930.KS", 2025)

    # 첫 위치 인자가 ".KS" 제거된 6자리 stock_code
    args, kwargs = mock_inst.finstate_all.call_args
    assert args[0] == "005930"
    # reprt_code/fs_div 확정값
    assert kwargs.get("reprt_code") == "11011"
    assert kwargs.get("fs_div") == "CFS"


def test_fetch_dart_raw_account_mapping(mocker):
    # A3: account_id 1차 매핑으로 raw dict 산출 (revenue/gross_profit/op_income/net_income/eps).
    from stocksig.io import dart_client

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = _fixture_df()
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    raw = dart_client.fetch_dart_raw("005930", 2025)

    assert raw["revenue"] == EXPECTED_VALUES["revenue"]
    assert raw["gross_profit"] == EXPECTED_VALUES["gross_profit"]
    assert raw["op_income"] == EXPECTED_VALUES["op_income"]
    assert raw["net_income"] == EXPECTED_VALUES["net_income"]
    assert raw["eps"] == EXPECTED_VALUES["eps"]
    # 전년 EPS(frmtrm) 도 제공 → PEG eps_prior
    assert raw["eps_prior"] == 4_950


def test_fetch_dart_raw_thstrm_comma_parse(mocker):
    # T-03-10: thstrm_amount 쉼표 문자열 int 파싱 ("1,234,567" → 1234567).
    from stocksig.io import dart_client

    df = _fixture_df()
    # 매출액 행 thstrm_amount 를 쉼표 포함으로 변조
    df.loc[df["account_id"] == "ifrs-full_Revenue", "thstrm_amount"] = "333,605,938,000,000"
    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = df
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    raw = dart_client.fetch_dart_raw("005930", 2025)
    assert raw["revenue"] == 333_605_938_000_000


def test_fetch_dart_raw_only_income_statement_rows(mocker):
    # sj_div ∈ (IS, CIS) 손익행만 매핑 — BS(재무상태표) 동명행은 무시.
    from stocksig.io import dart_client

    df = _fixture_df()
    # 재무상태표(BS) 에 "매출액" 동명·다른 account_id 행을 끼워넣어 오염 시도
    bs_row = df.iloc[0].copy()
    bs_row["sj_div"] = "BS"
    bs_row["account_id"] = "ifrs-full_Revenue"
    bs_row["account_nm"] = "매출액"
    bs_row["thstrm_amount"] = "999"
    df = pd.concat([pd.DataFrame([bs_row]), df], ignore_index=True)

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = df
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    raw = dart_client.fetch_dart_raw("005930", 2025)
    # BS 행("999")이 아니라 IS 행(333조)이 매핑되어야 한다
    assert raw["revenue"] == EXPECTED_VALUES["revenue"]


def test_fetch_dart_raw_status_013_empty(mocker):
    # status "013"(데이터없음) → 빈 결과 → 한국어 사유 "DART 데이터 미존재".
    from stocksig.io import dart_client

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = {"status": "013", "message": "조회된 데이타가 없습니다."}
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    raw = dart_client.fetch_dart_raw("000000", 2025)
    assert raw.get("note")
    assert "데이터 미존재" in raw["note"]
    assert raw.get("revenue") is None


def test_fetch_dart_raw_status_020_quota(mocker):
    # status "020"(쿼터초과) → "DART 쿼터 초과".
    from stocksig.io import dart_client

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = {"status": "020", "message": "요청 제한을 초과하였습니다."}
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    raw = dart_client.fetch_dart_raw("005930", 2025)
    assert "쿼터 초과" in (raw.get("note") or "")


def test_fetch_dart_raw_status_other(mocker):
    # 그 외 status → "DART corp_code 매핑 실패".
    from stocksig.io import dart_client

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = {"status": "100", "message": "필드의 부적절한 값입니다."}
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    raw = dart_client.fetch_dart_raw("005930", 2025)
    assert "corp_code 매핑 실패" in (raw.get("note") or "")


def test_fetch_dart_raw_empty_df(mocker):
    # 빈 DataFrame(None) → 데이터 미존재 사유.
    from stocksig.io import dart_client

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = None
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    raw = dart_client.fetch_dart_raw("005930", 2025)
    assert raw.get("revenue") is None
    assert raw.get("note")


@pytest.fixture
def _isolated_fund_cache(tmp_path, monkeypatch):
    """get_fund/put_fund 가 tmp 디렉터리를 쓰도록 격리."""
    from stocksig.io import cache as cache_mod

    fund_cache = Cache(str(tmp_path / "fund"))
    monkeypatch.setattr(cache_mod, "_get_fund_cache", lambda: fund_cache)
    yield fund_cache
    fund_cache.close()


def test_fetch_dart_cached_hit(mocker, _isolated_fund_cache):
    # cache HIT: 같은 (DART,ticker,quarter) 2회 호출 시 finstate_all 1회만.
    from stocksig.io import dart_client

    mock_cls = mocker.patch("stocksig.io.dart_client.OpenDartReader")
    mock_cls.return_value.finstate_all.return_value = _fixture_df()
    mocker.patch("stocksig.io.dart_client._resolve_api_key", return_value="DUMMY")

    first = dart_client.fetch_dart_cached("005930", "2025-11011")
    second = dart_client.fetch_dart_cached("005930", "2025-11011")

    assert first == second
    assert mock_cls.return_value.finstate_all.call_count == 1  # 2회차 캐시 HIT
