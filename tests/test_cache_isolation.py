"""테스트 디스크 캐시 격리 회귀 테스트.

배경: `.cache/ohlcv`는 상대 경로 + 모듈 전역 싱글톤이라, 캐시 격리 없이
run()을 돌리는 테스트가 합성 OHLCV를 운영 캐시에 저장하는 사고가 있었다
(키 `AAPL|<오늘>`, 같은 날 main.py 실행 시 cache HIT → AAPL 시트가
2026-05-20 합성 데이터로 채워짐). conftest의 autouse `_isolated_disk_cache`
픽스처가 이를 차단하는지 검증한다.
"""
from pathlib import Path

from diskcache import Cache

import stocksig.io.cache as cache_mod


def test_default_dirs_redirected_away_from_project_cache():
    """autouse 격리 픽스처가 운영 상대경로 기본값을 덮어썼는지 확인.

    Plan 10-03(FUND-11): 구 `.cache/fundamentals` 캐시 제거 → OHLCV·기업명 격리만 단언.
    """
    assert cache_mod._DEFAULT_DIR != Path(".cache/ohlcv")
    assert cache_mod._NAME_DIR != Path(".cache/company")


def test_put_ohlcv_does_not_touch_project_cache(mock_ohlcv_df):
    """put_ohlcv가 격리 디렉토리에만 쓰고 운영 `.cache/ohlcv`는 오염시키지 않는다."""
    canary = "ISOLATION-CANARY"
    cache_mod.put_ohlcv(canary, mock_ohlcv_df)

    # 격리 디렉토리에는 존재
    assert cache_mod.get_ohlcv(canary) is not None
    assert cache_mod._DEFAULT_DIR.exists()

    # 운영 캐시에는 캔러리 키가 없어야 함
    real = Cache(str(Path(".cache/ohlcv")))
    try:
        assert real.get(cache_mod.make_key(canary)) is None
    finally:
        real.close()
