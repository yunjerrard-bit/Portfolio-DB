---
phase: 03-edgar-dart-yfinance-naver
plan: 01
subsystem: io (cross-cutting infra)
tags: [throttle, cache, dependencies, fundamentals, rate-limit]
requires: []
provides:
  - "throttled_edgar (8 RPS) / throttled_dart (2 RPS) 데코레이터"
  - "get_fund/put_fund/make_fund_key — 7d TTL 펀더멘털 캐시 (.cache/fundamentals)"
  - "edgartools / opendartreader / beautifulsoup4 / lxml 의존성"
affects:
  - "후속 4개 펀더멘털 클라이언트(edgar/dart/naver/yf) — 공통 rate-limit·캐시 토대"
tech-stack:
  added:
    - "edgartools>=5,<6 (import 이름 edgar) — SEC EDGAR US 펀더멘털"
    - "opendartreader>=0.3 (import 이름 opendartreader) — DART KR 펀더멘털"
    - "beautifulsoup4>=4.12 — 네이버 HTML 폴백 파싱"
    - "lxml>=5 — bs4 파서 백엔드"
  patterns:
    - "throttled_yahoo 블록을 EDGAR/DART용으로 2회 복제 (Rate·키만 변경)"
    - "OHLCV 24h 캐시 패턴을 7d TTL 펀더멘털 캐시로 복제 (별도 인스턴스/디렉터리)"
key-files:
  created: []
  modified:
    - pyproject.toml
    - uv.lock
    - src/stocksig/io/throttle.py
    - src/stocksig/io/cache.py
    - tests/test_throttle.py
    - tests/test_cache.py
decisions:
  - "OpenDartReader 패키지의 import 이름은 opendartreader(소문자) — plan의 `import OpenDartReader` verify 명령을 정정"
  - "edgartools 핀 >=5,<6 (RESEARCH가 CONTEXT의 stale 4.x를 5.x로 정정한 권고 채택)"
  - "httpx는 edgartools transitive 의존이므로 별도 추가 안 함"
metrics:
  duration: ~7m
  completed: 2026-06-04
  tasks: 2
  files: 6
---

# Phase 3 Plan 01: 펀더멘털 인프라 확장(throttle·cache·deps) Summary

EDGAR(8 RPS)/DART(2 RPS) 토큰버킷 데코레이터와 7일 TTL 펀더멘털 디스크 캐시(`.cache/fundamentals`, 키 `(source,ticker,quarter)`)를 기존 Yahoo throttle·OHLCV 캐시 패턴을 복제해 추가하고, 후속 펀더멘털 클라이언트용 의존성 4종(edgartools 5.x / opendartreader / beautifulsoup4 / lxml)을 설치했다. FUND-06(throttle)·FUND-04(7d 캐시) 충족.

## What Was Built

### Task 1 — 의존성 4종 설치 + pyproject 핀 갱신 (commit d6eaf50)
- `uv add "edgartools>=5,<6" "OpenDartReader>=0.3" "beautifulsoup4>=4.12" "lxml>=5"` 실행.
- 설치 결과: edgartools 5.35.0, opendartreader 0.3.2, beautifulsoup4 4.14.3, lxml 6.1.1. httpx 0.28.1은 edgartools transitive로 자동 해결(별도 추가 없음).
- import 검증: `import edgar, opendartreader, bs4, lxml` 4건 모두 ImportError 없이 통과.

### Task 2 (TDD) — EDGAR/DART throttle + 7d 펀더멘털 캐시 (RED 479f130 → GREEN 4965696)
- **throttle.py**: `_EDGAR_RATE = Rate(8, Duration.SECOND)` + `_edgar_limiter` + `throttled_edgar`(try_acquire 키 `"edgar"`), `_DART_RATE = Rate(2, Duration.SECOND)` + `_dart_limiter` + `throttled_dart`(키 `"dart"`). `@wraps(fn)` 유지(Phase 1 `_no_retry_wait` fixture 호환). 기존 `throttled_yahoo` 무손상.
- **cache.py**: `_FUND_DIR = Path(".cache/fundamentals")`, `_FUND_TTL_SECONDS = 7*24*60*60`, `_fund_cache` 싱글톤 + `_get_fund_cache()` lazy-init, `make_fund_key(source,ticker,quarter)`, `get_fund`/`put_fund`(한국어+영문 HIT/MISS 로그). 기존 OHLCV 캐시(`get_ohlcv`/`put_ohlcv`/`make_key`) 무손상.
- **tests**: test_throttle.py에 EDGAR/DART try_acquire·반환값·시그니처 4건; test_cache.py에 fixture를 `_fund_cache` 격리로 확장 후 make_fund_key 포맷·디렉터리 분리·roundtrip·다른 quarter MISS·TTL 상수·7d HIT·7d 만료 등 펀더멘털 7건 추가. `test_fund_cache*` 명명으로 FUND-04 VALIDATION 명령과 일치.

## Verification

- `uv run pytest tests/test_throttle.py tests/test_cache.py` — 21 passed
- `uv run pytest tests/test_cache.py -k test_fund_cache` — 6 passed (FUND-04)
- `uv run python -c "import edgar, opendartreader, bs4, lxml"` — 종료코드 0
- `uv run pytest` 전체 회귀 — 134 passed (0건 회귀)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] OpenDartReader import 이름 정정 (verify 명령 오류)**
- **Found during:** Task 1 검증
- **Issue:** plan/CONTEXT의 verify 명령 `uv run python -c "import ... OpenDartReader ..."`가 ModuleNotFoundError. 패키지명은 `OpenDartReader`/`opendartreader`이나 실제 import 모듈명은 `opendartreader`(소문자)이며 `OpenDartReader`는 그 안의 클래스명.
- **Fix:** 검증 명령을 `import opendartreader`로 수정해 4종 전부 통과 확인. 이는 plan의 read_first가 경고한 "RESEARCH Pitfall 1 — import 이름 혼동 방지"에 해당하는 케이스.
- **Files modified:** 없음(검증 명령만 정정). pyproject 핀은 `opendartreader>=0.3`로 표기됨(uv가 정규화).
- **Commit:** d6eaf50

## Self-Check: PASSED

- src/stocksig/io/throttle.py — FOUND (`def throttled_edgar`, `def throttled_dart`, `Rate(8`, `Rate(2`)
- src/stocksig/io/cache.py — FOUND (`def make_fund_key`, `_FUND_TTL_SECONDS = 7 * 24 * 60 * 60`, 기존 `def get_ohlcv` 무손상)
- pyproject.toml — FOUND (edgartools>=5,<6 / opendartreader>=0.3 / beautifulsoup4>=4.12 / lxml>=5 4항목)
- commits d6eaf50, 479f130, 4965696 — FOUND in git log
