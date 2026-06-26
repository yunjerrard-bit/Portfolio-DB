---
phase: 04-quality-robustness
reviewed: 2026-06-12T06:17:50Z
depth: standard
files_reviewed: 12
files_reviewed_list:
  - src/stocksig/io/cache.py
  - src/stocksig/io/auth_check.py
  - src/stocksig/io/fundamentals.py
  - src/stocksig/main_run.py
  - tests/conftest.py
  - tests/test_cache.py
  - tests/test_cache_isolation.py
  - tests/test_smoke_n_tickers.py
  - tests/test_auth_check.py
  - tests/test_fundamentals.py
  - tests/test_freeze_panes.py
  - tests/test_color_tone.py
findings:
  critical: 1
  warning: 6
  info: 6
  total: 13
status: issues_found
---

# Phase 4: Code Review Report

**Reviewed:** 2026-06-12T06:17:50Z
**Depth:** standard
**Files Reviewed:** 12
**Status:** issues_found

## Summary

Phase 4 (quality-robustness) 변경분 검토: thread-safe 캐시 hit/miss 카운터, 한국어 실행 요약 블록, EDGAR/DART 인증 사전검증(ping + skip 클로저), frozen panes / WCAG 휘도 회귀 테스트, 테스트 디스크 캐시 autouse 격리.

핵심 구조는 견고하다 — 카운터는 lock으로 보호되고, `auth_check.py`의 ping 함수들은 예외 원문을 note에 보간하지 않는 sanitization 계약(T-04-03)을 충실히 지킨다. 그러나 **같은 보안 계약이 per-ticker 펀더멘털 경로에서는 깨진다**: `fetch_fundamentals`의 예외 흡수 블록이 예외 원문을 로그와 Excel note에 그대로 보간하는데, DART 클라이언트 예외 메시지에는 `crtfc_key=<API 키>`가 포함된 요청 URL이 들어갈 수 있다 (CR-01). 인증 ping이 OK여도 실행 중 일시적 네트워크/HTTP 오류 한 번이면 키가 콘솔 로그와 워크북에 남는다. 이는 이번 phase가 인증 사유 sanitize에 들인 노력을 우회하는 구멍이다.

그 외 ping의 단발성/무재시도 설계가 일시 장애를 "인증 실패"로 오판해 전체 run의 1차 소스를 끄는 문제(WR-02), NaN 가드 부재로 NaN PER/PEG가 정상값처럼 시트에 기록될 수 있는 문제(WR-01), 그리고 "네트워크 없음"을 표방하는 테스트들이 실제로는 SEC/EDGAR/DART/Naver에 실 네트워크 호출을 수행하는 테스트 신뢰성 결함(WR-05, WR-06)을 확인했다.

## Critical Issues

### CR-01: DART API 키가 예외 원문 보간을 통해 로그·Excel note로 누설될 수 있음

**File:** `src/stocksig/io/fundamentals.py:343-344, 370-371` (동일 패턴: `src/stocksig/runner.py:99-100`)
**Issue:** `fetch_fundamentals`의 예외 흡수 블록이 예외 원문 `e`를 (1) `logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", ticker, e)` 로 콘솔/로그파일에 출력하고, (2) `_empty_result(f"조회 실패: {e}")` 로 **워크북에 기록되는 MetricCell.note**에 보간한다.

KR 경로의 기본 클라이언트(`dart_client.fetch_dart_raw`)는 OpenDartReader를 경유하며, OpenDartReader는 `crtfc_key=<OPENDART_API_KEY>`를 쿼리스트링에 넣는다. `requests`의 `ConnectionError`/`HTTPError`/타임아웃 예외 메시지는 **전체 요청 URL(쿼리스트링 포함)** 을 담는다 (예: `HTTPSConnectionPool(host='opendart.fss.or.kr', ...): Max retries exceeded with url: /api/fnlttSinglAcntAll.json?crtfc_key=0123abcd...`). 따라서:

- 인증 ping이 OK(키 유효)여도, 실행 중 DART 일시 장애·타임아웃 1회로 **API 키가 로그와 .xlsx 파일에 영구 기록**된다.
- 이는 이번 phase의 보안 계약(T-04-03/T-04-04 — "예외 원문 e를 note에 보간 금지")을 `auth_check.py`에서만 지키고 정작 per-ticker 본 경로에서 위반하는 것이다. `test_summary_auth_line_no_secret_leak`는 "인증:" 줄만 검사하므로 이 누설 경로를 잡지 못한다.
- 이 코드는 Phase 3에서 도입됐지만, Phase 4가 바로 이 위협(T-04-03)을 닫는 phase이므로 여기서 함께 닫혀야 한다.

**Fix:**
```python
# fundamentals.py — US/KR 공통 (line 342-344, 369-371)
except Exception as e:  # D-disc-10: 펀더멘털 결손 ≠ 티커 실패
    # 예외 원문에 요청 URL(crtfc_key 등)이 포함될 수 있음 — 타입명만 로그,
    # note 는 고정 한국어 사유 (T-04-03: 키/UA 미노출).
    logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", ticker, type(e).__name__)
    return _empty_result("조회 실패: 데이터 소스 오류")
```
`runner.py:99-100`의 동일 패턴(`logger.warning(..., e)`)도 같은 방식으로 sanitize 필요. 더 방어적으로 가려면 공용 `_sanitize_exc(e)` 헬퍼에서 `re.sub(r"crtfc_key=[^&\s]+", "crtfc_key=***", str(e))` 처리 후 사용.

## Warnings

### WR-01: last_close / yf 폴백값에 NaN 가드 부재 — NaN PER·PEG가 정상값으로 시트에 기록됨

**File:** `src/stocksig/io/fundamentals.py:71-79, 96-99, 159-166, 253-261` (유입점: `src/stocksig/runner.py:96`)
**Issue:** `runner.process_ticker`는 `last_close = df.iloc[-1].get("Close")` 를 주입하는데, yfinance 마지막 행의 Close가 `NaN`인 경우가 실재한다(장중 부분 행 등). `_compute_per`는 `last_close is None`만 검사하므로 `NaN is not None` → `PER = NaN/eps = NaN`이 **값 있는 셀**로 통과하고, `cell.value is not None` 검사도 통과해 `source="EDGAR"` provenance까지 붙는다. 이 NaN은 `_compute_peg`로 전파되고(NaN 비교는 모두 False → 가드 통과) 결국 시트1에 NaN PER/PEG가 기록된다. yf 폴백의 `float(v)` (line 163, 257)도 `v=float('nan')`을 그대로 수용한다. D-05("결손은 None, 0/-999999 금지") 위반이며 Core Value인 통합 시트 정확성에 직결된다.
**Fix:**
```python
import math

def _is_missing(x: float | None) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))

# _compute_per / _compute_peg / _compute_margin 의 None 검사들을 _is_missing 으로 교체,
# yf 폴백도: if v is not None and not _is_missing(float(v)):
```

### WR-02: 인증 ping이 단발·무재시도 — 일시 장애/5xx를 "인증 실패"로 오판해 전체 run의 1차 소스를 차단

**File:** `src/stocksig/io/auth_check.py:61-70, 80-88, 117-122`
**Issue:** `_edgar_probe`는 GET 1회뿐이며 재시도가 없다. (1) `raise_for_status()`는 5xx에도 raise하므로 SEC 서버 일시 장애가 "EDGAR 인증 실패"로 분류되고, (2) DNS 일시 오류·타임아웃 같은 transient 예외도 동일하게 인증 실패로 처리된다. 그 결과 `main_run.run`의 skip 클로저가 **200티커 전체의 EDGAR/DART 1차 호출을 통째로 끈다** — 키가 멀쩡한데도 모든 셀 note가 "EDGAR 인증 실패"가 된다. DART 쪽은 status "013"/"020" false-negative를 정성껏 막았으면서(Pitfall 4), 같은 클래스의 false-negative(transient 예외)는 막지 않아 비대칭적이다. 스택에 이미 tenacity가 있다.
**Fix:** (a) probe에 tenacity 재시도(예: `stop_after_attempt(3) + wait_exponential`)를 적용하고, (b) 인증 실패 판정을 401/403으로 한정 — 그 외 예외/5xx는 `(True, None)` 또는 별도 "인증 미확정(스킵 안 함)" 상태로 처리해 1차 소스를 살린다:
```python
except httpx.HTTPStatusError as e:
    if e.response.status_code in (401, 403):
        return False, _EDGAR_403_NOTE
    return True, None  # 서버측 오류 — 인증 문제 아님, 스킵하지 않음
except Exception:
    return True, None  # transient — per-call 흡수 경로에 맡김
```

### WR-03: 403 판별이 `"403" in str(e)` 문자열 매칭 — 예외 타입/상태코드 기반이어야 함

**File:** `src/stocksig/io/auth_check.py:84`
**Issue:** `note = _EDGAR_403_NOTE if "403" in str(e) else _EDGAR_FAIL_NOTE` 는 예외 메시지 어디든 "403"이 있으면(URL 경로, 바이트 수, 다른 상태코드 설명 등) UA 거부로 오진한다. 반대로 메시지 포맷이 바뀌면 실제 403을 놓친다. httpx는 구조화된 예외를 제공하므로 문자열 검사가 불필요하다.
**Fix:**
```python
except httpx.HTTPStatusError as e:
    note = _EDGAR_403_NOTE if e.response.status_code == 403 else _EDGAR_FAIL_NOTE
    ...
except Exception:
    note = _EDGAR_FAIL_NOTE
    ...
```

### WR-04: 캐시 싱글톤 lazy 초기화에 race — fan-out 첫 호출에서 중복 Cache 인스턴스/핸들 누수 가능

**File:** `src/stocksig/io/cache.py:55-60, 102-107`
**Issue:** `_get_cache()`/`_get_fund_cache()`의 `if _cache is None: _cache = Cache(...)` 는 lock 없이 실행된다. `run_all`은 4-worker `ThreadPoolExecutor`로 fan-out하므로 첫 `get_ohlcv` 호출들이 동시에 들어와 두 스레드가 모두 `None`을 보고 각각 `Cache`를 생성할 수 있다. diskcache는 SQLite 기반이라 데이터 정합성은 유지되지만, 패배한 인스턴스는 close되지 않은 채 누수된다 — 이 프로젝트는 Windows에서 diskcache 파일 핸들 미해제로 인한 문제를 이미 겪었다(conftest 주석). 카운터(`_stats`)는 lock으로 보호하면서 정작 싱글톤 생성은 보호하지 않아 비일관적이다.
**Fix:**
```python
_cache_lock = threading.Lock()

def _get_cache() -> Cache:
    global _cache
    if _cache is None:
        with _cache_lock:
            if _cache is None:  # double-checked
                _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
                _cache = Cache(str(_DEFAULT_DIR))
    return _cache
```
(`_get_fund_cache`도 동일.)

### WR-05: test_freeze_panes — "네트워크 없음" 표방하나 매 테스트가 SEC에 실 HTTP GET + 실 펀더멘털 fetch 수행

**File:** `tests/test_freeze_panes.py:65-86` (fixture `mock_pipeline_env`)
**Issue:** 이 fixture는 smoke 테스트 패턴을 차용했다고 명시하지만(L15-16 "네트워크 없음, 결정론적") **ping stub을 빠뜨렸다**. 세 테스트 모두 US 티커(AAPL/MSFT)로 `run()`을 돌리므로 `ping_edgar()`가 실제 `httpx.get`을 sec.gov에 날린다(timeout 10초, `@throttled_edgar` 대기 포함). 추가로 펀더멘털 기본 클라이언트도 stub되지 않아 `Company(ticker).get_facts()`(EDGAR)·yfinance info의 실 네트워크 fetch가 시도된다. 오프라인에서는 예외 흡수로 통과하지만 타임아웃만큼 느려지고, 온라인에서는 테스트가 외부 서비스에 의존하며 test UA(`test@example.com`)로 SEC에 요청을 보낸다 — 04-03이 의도적으로 smoke fixture에 ping stub을 넣은 것과 정확히 반대 회귀.
**Fix:** smoke 패턴 그대로 fixture에 추가:
```python
import stocksig.main_run as main_mod
monkeypatch.setattr(main_mod, "ping_edgar", lambda: (True, None))
monkeypatch.setattr(main_mod, "ping_dart", lambda: (True, None))
monkeypatch.setattr(main_mod, "fetch_fundamentals",
                    lambda t, m, lc, **kw: None)  # frozen panes 검증에 펀더멘털 불필요
```

### WR-06: test_smoke_n_tickers — 펀더멘털 fetcher 미stub으로 run() 경유 테스트 전부가 실 EDGAR/DART/Naver/yf 호출 시도

**File:** `tests/test_smoke_n_tickers.py:65-90` (fixture `mock_pipeline_env`), 영향: 동 파일의 모든 `run()` 호출 테스트
**Issue:** fixture가 `fetch_ohlcv`와 ping은 stub하지만 펀더멘털 경로는 그대로 둔다. `run()`은 항상 `fundamentals_fn=_fundamentals_with_auth`를 전달하고 ping stub이 OK를 반환하므로 skip되지 않아, 티커마다 기본 클라이언트가 호출된다: US는 `fetch_edgar_cached` → `Company(t).get_facts()` 실 네트워크, KR은 `OpenDartReader("test-key")` 생성(corp_code zip 다운로드 시도) + Naver 스크래핑 + yf info. `test_10_tickers_completes`는 10티커 × 다중 외부 API를 건드린다. 모든 예외가 흡수되어 테스트는 "통과"하지만, 모듈 docstring의 "네트워크 없음, 결정론적" 계약이 거짓이며 실행 시간·flakiness가 네트워크 상태에 좌우되고, 무효 키(`test-key`)로 실제 DART에 요청을 보낸다.
**Fix:** fixture에서 펀더멘털을 무력화:
```python
monkeypatch.setattr(
    main_mod, "fetch_fundamentals",
    lambda ticker, market, last_close, **kw: None,
)
```
skip 전파를 검증하는 `test_ping_failure_propagates_skip_edgar`는 자체 spy로 덮어쓰므로 영향 없음 — 단, 해당 spy는 real `fetch_fundamentals`로 위임하므로(L397) 그 테스트만은 `yf_fn` 주입 또는 추가 stub 필요.

## Info

### IN-01: US 경로 진행 로그가 전 지표 결손/skip 시에도 "fund OK (EDGAR)"로 출력

**File:** `src/stocksig/io/fundamentals.py:168, 172-177`
**Issue:** `_log_progress`는 KR의 `_log_kr_progress`와 달리 "fund MISS" 분기가 없어 4지표 전부 None이어도 `fund OK <ticker> (EDGAR)`를 찍는다. 또한 `skip_edgar=True`로 EDGAR를 건너뛰고 yf로 채운 경우에도 `(EDGAR→yf)`로 출력되어 provenance 로그가 사실과 다르다.
**Fix:** KR과 동일하게 all-None이면 `fund MISS`, skip 시 `(yf)` 등 실제 경로를 반영.

### IN-02: ping_dart의 `except Exception as e` — `e` 미사용

**File:** `src/stocksig/io/auth_check.py:119`
**Issue:** 바인딩된 `e`가 본문에서 전혀 쓰이지 않는다(보간 금지가 의도이므로 바인딩 자체가 불필요). ruff `F841` 대상.
**Fix:** `except Exception:` 으로 변경 (ping_edgar는 WR-03 수정 시 함께 정리).

### IN-03: 격리 검증 테스트가 운영 `.cache/ohlcv` 디렉터리/DB를 직접 생성

**File:** `tests/test_cache_isolation.py:32`
**Issue:** `Cache(str(Path(".cache/ohlcv")))` 는 디렉터리가 없으면 **생성**하고 빈 `cache.db`를 만든다 — "운영 캐시 비오염"을 검증하는 테스트가 역설적으로 운영 경로에 파일을 만든다(레포 작업트리 오염). cwd가 프로젝트 루트가 아니면 엉뚱한 위치에 생성될 수도 있다.
**Fix:** `if not Path(".cache/ohlcv").exists(): return`(없으면 오염 불가 — 통과) 가드 후에만 열거나, sqlite 파일을 읽기 전용으로 검사.

### IN-04: 실패 티커 목록이 한 run에서 3번 출력됨

**File:** `src/stocksig/main_run.py:310-314, 337-340` + `src/stocksig/runner.py:159-161`
**Issue:** 실패 시 (1) runner의 `실패 티커: ...` warning, (2) main_run의 `실패 %d개 — 시트1에 표시됨: ...`, (3) 요약 블록의 `실패 티커: ...` info — 같은 목록이 세 번 출력되어 콘솔 노이즈. 또한 `test_summary_block_omits_failure_line_when_no_failures`는 전체 로그에서 `"실패 티커:"` 부재를 단언하므로 runner 로그 포맷과 암묵 결합되어 있다(runner가 무실패 시에도 해당 prefix를 쓰게 되면 오탐).
**Fix:** 요약 블록을 단일 진원지로 삼고 runner/중간 경고 중 하나를 정리하거나 prefix를 구분.

### IN-05: `_compute_peg` — 전년 EPS 음수(턴어라운드) 케이스의 사유 라벨 부정확

**File:** `src/stocksig/io/fundamentals.py:91-98`
**Issue:** `eps_prior < 0, eps_ttm > 0` (적자→흑자 전환)이면 `(eps_ttm/eps_prior - 1)*100` 이 음수가 되어 "조회 실패: EPS 성장률 ≤ 0" 사유가 붙는데, 실제로는 이익이 개선된 경우다. 값을 계산하지 않는 보수적 처리 자체는 안전하나(음수 prior에서 성장률 공식은 무의미), 사유 문구가 사용자에게 오해를 준다.
**Fix:** `if eps_prior < 0: return _empty_cell("조회 실패: 전년 EPS 음수(턴어라운드)")` 분기 추가.

### IN-06: `_dart_probe`가 "가벼운 호출"이 아님 — OpenDartReader 생성자가 corp_code 전체 zip을 다운로드

**File:** `src/stocksig/io/auth_check.py:100-103`
**Issue:** docstring은 "가벼운 공시목록 조회"라 하지만 `OpenDartReader(api_key)` 생성자는 초기화 시 전체 corp_code zip(수 MB)을 받는다. 매 run 시작마다 ping에서 이 비용이 발생하며, zip 다운로드 실패(네트워크)도 "인증 실패"로 분류된다(WR-02와 결합). 키 무효 시 생성자 단계에서 예외가 나면 status 분기(L104-106)는 도달하지 못할 수 있다.
**Fix:** dart_client 쪽에서 OpenDartReader 인스턴스를 모듈 싱글톤으로 재사용하거나, ping을 `httpx.get("https://opendart.fss.or.kr/api/list.json?crtfc_key=...&...")` 직접 호출로 바꿔 status JSON만 검사(키는 URL에만 두고 예외 sanitize는 현행 유지).

---

_Reviewed: 2026-06-12T06:17:50Z_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
