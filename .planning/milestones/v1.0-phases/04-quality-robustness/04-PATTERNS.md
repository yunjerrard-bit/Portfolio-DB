# Phase 4: 품질·견고성 마감 - Pattern Map

**Mapped:** 2026-06-11
**Files analyzed:** 9 (2 new source + 2 extended source + 5 new/extended test)
**Analogs found:** 9 / 9

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/stocksig/io/auth_check.py` (NEW) | io / service | request-response (외부 HTTP ping) | `src/stocksig/io/edgar_client.py` + `io/dart_client.py` (예외흡수: `io/fundamentals.py`) | role-match (외부 API 클라이언트) |
| `src/stocksig/io/cache.py` (확장) | io / store | CRUD + counter state | self (기존 함수) + `io/naver_scraper.py` (`reset_naver_count` 카운터 패턴) | exact (동일 파일 확장) |
| `src/stocksig/main_run.py` (확장) | orchestration | request-response | self (기존 `run()` 구조) | exact (동일 파일 확장) |
| `tests/test_auth_check.py` (NEW) | test | unit (mock) | `tests/test_edgar_client.py` + `tests/test_naver_scraper.py` | role-match |
| `tests/test_cache.py` (확장) | test | unit | self (기존 카운터 없는 cache 테스트) | exact |
| `tests/test_freeze_panes.py` (NEW) | test | integration (openpyxl 읽기) | `tests/test_smoke_n_tickers.py` (openpyxl `load_workbook` 패턴) | role-match |
| `tests/test_color_tone.py` (NEW) | test | unit (pure) | `tests/test_color_rules.py` (color_rules 상수 단언) | role-match |
| `tests/test_smoke_n_tickers.py` (확장) | test | integration (smoke + caplog) | self (기존 `caplog` 로그 assert) | exact |
| `compute/color_rules.py` (조건부) | compute / config | transform (상수만) | self (L15-27 상수 블록) — **조정 필요 시에만 수정** | exact |

> 신규 외부 의존성 0개 (RESEARCH §Standard Stack). 모든 작업은 기존 구조의 재배선.

---

## Pattern Assignments

### `src/stocksig/io/auth_check.py` (NEW — io/service, request-response)

**Analog:** `src/stocksig/io/edgar_client.py` (식별·throttle), `io/dart_client.py` (status 가드), `io/fundamentals.py` (예외 흡수 계약), `io/naver_scraper.py` (graceful-None HTTP).

**핵심 계약 (RESEARCH Pattern 1):** ping 함수는 **절대 raise하지 않는다.** `fundamentals.py:309-313`의 전 경로 try/except 흡수 계약을 그대로 차용하여 D-02(경고 후 계속)를 함수 시그니처로 강제. 반환은 `(bool, str | None)` 또는 `AuthStatus`.

**예외 흡수 패턴** — copy from `io/fundamentals.py:309-313` (US 경로) / `:333-337` (KR 경로):
```python
try:
    return _fill_us(ticker, last_close, edgar_fn, yf_fn)
except Exception as e:  # D-disc-10: 펀더멘털 결손 ≠ 티커 실패
    logger.warning("%s | 펀더멘털 fetch 예외 흡수: %s", ticker, e)
    return _empty_result(f"조회 실패: {e}")
```
ping은 같은 형태로 `except Exception` → `logger.warning(...)` → `return (False, note)`.

**throttle 데코레이터 재사용** — copy decorator usage from `io/edgar_client.py:63` / `io/dart_client.py:114`:
```python
from stocksig.io.throttle import throttled_edgar   # 8 RPS
from stocksig.io.throttle import throttled_dart     # 2 RPS

@throttled_edgar
def fetch_edgar_raw(ticker: str) -> dict: ...
```
ping 함수도 `@throttled_edgar` / `@throttled_dart`를 직접 붙이거나, 데코레이트된 기존 fetch를 호출(재량 3).

**EDGAR UA 식별 재사용** — copy from `io/edgar_client.py:37-45`:
```python
_UA_NAME = "Yunjae Kim"
_DEFAULT_EMAIL = "yunjerrard@gmail.com"

def _resolve_identity() -> str:
    """`"<이름> <이메일>"` UA 문자열 — .env 이메일 우선(하드코딩 회피)."""
    email = os.environ.get("EDGAR_USER_AGENT_EMAIL") or _DEFAULT_EMAIL
    return f"{_UA_NAME} {email}"

# import-time 1회 set_identity (per-call 금지)
set_identity(_resolve_identity())
```
**Pitfall 2:** `set_identity`는 `edgar_client` import 시점의 부수효과(`:44-45`). httpx 직접 ping 경로를 쓰면 `edgar_client._resolve_identity()`를 재사용해 UA 헤더를 직접 넣어야 일관성 유지. edgartools 경로와 httpx 경로를 **섞지 말 것.**

**DART status 가드** — copy logic from `io/dart_client.py:42-47, 134-143`:
```python
_STATUS_NOTES: dict[str, str] = {
    "013": "DART 데이터 미존재",   # 키 유효 — 인증 OK로 판정
    "020": "DART 쿼터 초과",       # 일시적 — 키 유효
}
# status 가드:
if isinstance(resp, dict):
    status = resp.get("status")
    note = _STATUS_NOTES.get(status, _STATUS_OTHER_NOTE)
```
**Pitfall 4:** ping은 키 유효성만 판정. `status="013"`(데이터없음)은 키가 유효하므로 **OK**로 취급. 키 무효 코드(예 미등록 키)만 실패. 특정 종목/연도 리포트 부재로 false-negative 내지 말 것.

**AuthStatus dataclass** — `dataclass` 스타일은 `runner.py:34-55`(`TickerResult`/`TickerFailure`), `fundamentals.py:31-53`(`MetricCell`/`FundamentalsResult`)와 동일. None = ping 미실행(해당 시장 티커 없음):
```python
from dataclasses import dataclass

@dataclass
class AuthStatus:
    edgar_ok: bool | None = None   # None = ping 미실행
    dart_ok: bool | None = None
    edgar_note: str | None = None  # 한국어 사유 (셀 주석 재사용 가능)
    dart_note: str | None = None
```

**보안 (RESEARCH §Security Domain):** ping 예외 사유 `f"...: {e}"`의 `e`가 `OPENDART_API_KEY`를 포함할 수 있음(opendartreader가 키를 URL에 넣음). 예외 문자열을 sanitize하거나 키 미포함 일반 메시지로 치환할 것. `dart_client._STATUS_NOTES` 류 고정 한국어 사유 매핑을 쓰면 키 누설 회피.

**캐시 미오염 (Pitfall 1):** ping은 `fetch_edgar_cached`/`fetch_dart_cached`(캐시 쓰기 경로)를 쓰지 말 것 — 입력에 없는 티커가 `.cache/fundamentals`에 박힘. 캐시 미경유 가벼운 호출 사용.

---

### `src/stocksig/io/cache.py` (확장 — io/store, CRUD + counter)

**Analog:** self (기존 `get_ohlcv`/`get_fund`) + `io/naver_scraper.py:34-44`(모듈 레벨 카운터 + reset 패턴).

**카운터 + reset 패턴** — copy from `io/naver_scraper.py:34-44`:
```python
# naver_scraper.py 패턴
_naver_calls: int = 0
def reset_naver_count() -> None:
    """run 시작 시 네이버 폴백 카운터 초기화 (D-07)."""
    global _naver_calls
    _naver_calls = 0
```
cache.py에 적용 (RESEARCH Pattern 4):
```python
import threading
_stats = {"ohlcv_hit": 0, "ohlcv_miss": 0, "fund_hit": 0, "fund_miss": 0}
_stats_lock = threading.Lock()   # Pitfall 3 — ThreadPoolExecutor(4) race 보호

def reset_cache_stats() -> None:
    with _stats_lock:
        for k in _stats:
            _stats[k] = 0

def get_cache_stats() -> dict[str, int]:
    with _stats_lock:
        return dict(_stats)
```

**카운터 증가 지점** — 기존 HIT/MISS 분기에 삽입. `cache.py:48-54` (`get_ohlcv`) 와 `:89-95` (`get_fund`):
```python
# get_ohlcv 현행 (cache.py:48-54):
def get_ohlcv(ticker: str):
    key = make_key(ticker)
    value = _get_cache().get(key)
    if value is not None:
        logger.info("%s | 캐시 HIT (cache HIT, key=%s)", ticker, key)   # ← here: _stats["ohlcv_hit"] += 1 (lock)
    else:
        logger.info("%s | 캐시 MISS (cache MISS, key=%s)", ticker, key)  # ← here: _stats["ohlcv_miss"] += 1 (lock)
    return value
```
**Anti-pattern (RESEARCH):** per-call HIT/MISS `logger.info`는 **유지**. `test_smoke_n_tickers.py`가 `"cache HIT"` 문자열을 INFO 레벨에서 grep하므로 제거/강등 시 회귀.

**Pitfall 3:** `_stats[k] += 1`은 4워커에서 read-modify-write race. `threading.Lock`으로 증가 보호.

---

### `src/stocksig/main_run.py` (확장 — orchestration, request-response)

**Analog:** self (기존 `run()` 구조 `:216-278`).

**조건부 ping 삽입 지점** — 티커 로드 직후(`main_run.py:234-235` 이후, PASS 1 호출 전). 기존 `naver_scraper.reset_naver_count()`(`:232`) 옆에 `cache.reset_cache_stats()` 추가:
```python
# 현행 main_run.py:229-241 (삽입 지점 명시)
load_env(env_path)
naver_scraper.reset_naver_count()          # :232
# ★ ADD: cache.reset_cache_stats()         (reset_naver_count 옆 — 다회 실행 안전)
specs = read_tickers_extended(tickers_path) # :234
logger.info("main | 티커 %d개 로드 완료", len(specs))  # :235

# ★ NEW: 조건부 ping (RESEARCH Pattern 2, D-04) — classify_market 재사용
markets = {classify_market(s.symbol) for s in specs}
auth = AuthStatus()
if "US" in markets:
    auth.edgar_ok, auth.edgar_note = ping_edgar()
if "KR" in markets:
    auth.dart_ok, auth.dart_note = ping_dart()
```
`classify_market`은 이미 import됨 (`main_run.py:49`). 시장 집합 판단은 `market_kind.classify_market` (`io/market_kind.py:15`).

**skip 플래그 전파 (RESEARCH Pattern 3, 재량 4)** — `run_all`이 `fundamentals_fn`을 받는 구조(`runner.py:113`)에 클로저 주입. 현행은 `fetch_fundamentals` 직접 전달(`main_run.py:239-241`):
```python
# 현행 main_run.py:239-241:
results, failures = run_all(
    specs, classify_market, pipeline, fundamentals_fn=fetch_fundamentals
)
# ★ 클로저로 skip 정보 바인딩 (Pattern 3):
def _fundamentals_with_auth(ticker, market, last_close):
    if market == "US" and auth.edgar_ok is False:
        return _empty_result("조회 실패: EDGAR 인증 실패")
    if market == "KR" and auth.dart_ok is False:
        return _empty_result("조회 실패: DART 인증 실패")
    return fetch_fundamentals(ticker, market, last_close)
```
**Open Q (A4, planner 확정):** EDGAR 인증 실패 시 yf 폴백을 살릴지(`fetch_fundamentals`에 `skip_edgar=True` 인자 추가) vs 전부 결손(`_empty_result`). `_empty_result`(`fundamentals.py:59-66`)는 보수적 — yf까지 스킵.

**최종 요약 블록 삽입 지점** — `run()` 종료부, 워크북 저장 로그 직후(`main_run.py:272-277`). 기존 패턴 **확장이지 대체 아님**:
```python
# 현행 main_run.py:272-277 (이 뒤에 요약 블록 추가):
logger.info("main | 워크북 저장: %s", output_path)
if failures:
    failed_syms = ", ".join(f.spec.symbol for f in failures)
    logger.warning("실패 %d개 — 시트1에 표시됨: %s", len(failures), failed_syms)
# ★ NEW: 요약 블록 (RESEARCH Pattern 5)
stats = cache.get_cache_stats()
logger.info("════════ 실행 요약 ════════")
logger.info("티커: 총 %d / 성공 %d / 실패 %d", len(specs), len(results), len(failures))
logger.info("인증: EDGAR %s | DART %s", _auth_label(auth.edgar_ok, auth.edgar_note),
            _auth_label(auth.dart_ok, auth.dart_note))
logger.info("캐시: OHLCV HIT %d/MISS %d · 펀더멘털 HIT %d/MISS %d",
            stats["ohlcv_hit"], stats["ohlcv_miss"], stats["fund_hit"], stats["fund_miss"])
```
`_auth_label(ok, note)`: `None`→"해당없음", `True`→"OK", `False`→f"실패({note})". **보안:** note에 API 키 원문 미포함 검증.

**한국어 로그 형식** — 기존 `runner.py:147,153,156-157`의 `[k/N] OK/FAIL`, `총 N 티커 중 성공 X / 실패 Y` 패턴 유지(`test_smoke_n_tickers.py`가 grep). 요약 블록은 추가.

---

### `tests/test_auth_check.py` (NEW — unit, mock)

**Analog:** `tests/test_edgar_client.py` (Company mock + 소스 단언), `tests/test_naver_scraper.py` (httpx graceful-None).

**소스 단언 패턴** — copy from `test_edgar_client.py:29-36`:
```python
def test_source_uses_throttle():
    src = Path("src/stocksig/io/auth_check.py").read_text(encoding="utf-8")
    assert "@throttled_edgar" in src or "throttled_edgar" in src
    # ping은 raise 금지 — except Exception 흡수 존재 단언
    assert "except Exception" in src
```

**mock 외부 호출** — `mocker.patch("stocksig.io.auth_check....")`로 ping 대상 차단(`test_edgar_client.py` `mocker.patch("stocksig.io.edgar_client.Company")` analog). 검증: ping 성공→`(True, None)`, ping 실패(예외)→`(False, note)` raise 없음, 조건부(US/KR 티커 없으면 ping 생략).

---

### `tests/test_freeze_panes.py` (NEW — integration, openpyxl 읽기 / OUT-04 회귀)

**Analog:** `tests/test_smoke_n_tickers.py` (openpyxl `load_workbook` + `run()` end-to-end + `env_file`/mock fixture).

**검증 대상 (이미 구현됨 — 회귀만):** `sheet_per_ticker.py:438` `ws.freeze_panes(5, 0)`, `sheet_portfolio.py:303` `ws.freeze_panes(5, 1)`.

**openpyxl 읽기 패턴** (RESEARCH Code Examples):
```python
import openpyxl
out = run(tickers, env_file, tmp_path / "output")
wb = openpyxl.load_workbook(out)
for name in wb.sheetnames:
    fp = wb[name].freeze_panes        # XlsxWriter (5,0)→"A6", (5,1)→"B6"
    assert fp is not None and fp.endswith("6")
assert wb["시트1"].freeze_panes == "B6"   # 행 1~5 + A열 고정
```
fixture(`env_file`, mock OHLCV)는 `test_smoke_n_tickers.py:54-60`에서 차용. **Windows 파일 핸들:** `test_cache.py:25-33`처럼 caches close 필요할 수 있음.

---

### `tests/test_color_tone.py` (NEW — unit, pure / COLOR-07·SC4)

**Analog:** `tests/test_color_rules.py` (color_rules 상수 import + 단언).

**WCAG 휘도 테스트** (RESEARCH §색 톤 휘도 검증) — `color_rules.py:16-21`의 상수 import:
```python
from stocksig.compute.color_rules import GREEN_100, RED_100, GREEN_800, RED_800

def _rel_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    def _lin(c): return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*_lin(r) + 0.7152*_lin(g) + 0.0722*_lin(b)

def test_hard_buckets_distinguishable_grayscale():
    diff = abs(_rel_luminance(GREEN_100) - _rel_luminance(RED_100))  # HARD 배경색
    assert diff > 0.05   # 임계값은 실측 후 확정
```
**Pitfall 5:** HARD(배경색 `GREEN_100`/`RED_100`)는 휘도차 명확. SOFT(글자색 `GREEN_800`/`RED_800`)는 흑백에서 본질적으로 약함 — 휘도차 측정 후 SC4 통과 판정. 분리 검증.

---

### `tests/test_smoke_n_tickers.py` (확장 — integration smoke + caplog)

**Analog:** self (기존 `caplog` 로그 assert).

**caplog 로그 단언** (RESEARCH Code Examples):
```python
def test_summary_block_emitted(mock_pipeline_env, tmp_path, env_file, caplog):
    caplog.set_level(logging.INFO)
    run(tickers, env_file, tmp_path / "output")
    msgs = [r.getMessage() for r in caplog.records]
    assert any("실행 요약" in m for m in msgs)
    assert any("캐시:" in m and "HIT" in m for m in msgs)
```
기존 cache HIT grep 테스트(`"cache HIT" in r.getMessage()`)는 유지 — per-call 로그 제거 금지.

---

## Shared Patterns

### 예외 흡수 (graceful degradation, D-02 / D-disc-10)
**Source:** `io/fundamentals.py:309-313, 333-337` (전 경로 try/except), `io/naver_scraper.py:86-89` (HTTP graceful-None)
**Apply to:** `auth_check.py` 모든 ping 함수 (raise 절대 금지)
```python
except Exception as e:  # noqa: BLE001
    logger.warning("%s | ... 예외 흡수: %s", x, e)
    return _empty_result(f"조회 실패: {e}")   # 또는 (False, note)
```

### throttle 데코레이터 (rate-limit 공유)
**Source:** `io/throttle.py:35-43` (`throttled_edgar` 8 RPS), `:50-58` (`throttled_dart` 2 RPS)
**Apply to:** `auth_check.ping_edgar`/`ping_dart` (메인 fetch와 레이트 버킷 공유)
```python
@throttled_edgar   # try_acquire("edgar") — 토큰 획득까지 block
def ping_edgar(): ...
```

### 모듈 레벨 카운터 + run당 reset
**Source:** `io/naver_scraper.py:34-44` (`_naver_calls` + `reset_naver_count`)
**Apply to:** `cache.py` `_stats` + `reset_cache_stats`. reset은 `main_run.run()` 시작부(`reset_naver_count` 옆, `main_run.py:232`)에서 호출.

### dataclass 결과 모델
**Source:** `runner.py:34-55` (`TickerResult`/`TickerFailure`), `fundamentals.py:31-53` (`MetricCell`/`FundamentalsResult`)
**Apply to:** `auth_check.AuthStatus`. `bool | None` 필드로 "미실행" 상태 표현.

### 색 단일 진원지 (D-02 from Phase 2)
**Source:** `compute/color_rules.py:16-27` (Material hex 상수)
**Apply to:** 톤 조정 필요 시 **이 상수만** 변경. writer/시트 코드 무변경.

### 한국어 로그 형식 (EXEC-05)
**Source:** `runner.py:147` (`[%d/%d] OK %s`), `:156-157` (`총 %d 티커 중 성공 %d / 실패 %d`), `cache.py:51,53` (HIT/MISS), `config.py` 헤더(D-05 포맷 `[LEVEL] YYYY-MM-DD HH:MM:SS | TICKER | 메시지`)
**Apply to:** 신규 ping 로그(`auth | ⚠ ...`), 요약 블록. 기존 grep 대상 문자열 변경 금지.

### .env 자격증명 읽기 (하드코딩 회피)
**Source:** `config.py:18,25-50` (`REQUIRED_KEYS`, `load_env`), `edgar_client.py:37-40` (`_resolve_identity`), `dart_client.py:50-57` (`_resolve_api_key`)
**Apply to:** ping이 자격증명을 읽을 때 기존 resolver 재사용. **보안:** 키 원문을 로그/요약/예외 사유에 출력 금지.

---

## No Analog Found

해당 없음 — 모든 신규/확장 파일이 코드베이스 내 강한 analog를 가진다. Phase 4는 신규 기능이 ping 1건뿐이며, 그조차 기존 edgar/dart 클라이언트 + fundamentals 예외흡수 + naver 카운터 패턴의 조합이다.

> 단, **ping 엔드포인트 정확 선정**(재량 3, RESEARCH Open Q1)은 코드 analog가 아닌 실측 결정 사항: edgartools 경로 vs httpx 직접 GET 중 더 가벼운 쪽을 구현자가 `.env`로 1회 실측 후 채택. 캐시 미경유 보장(Pitfall 1).

## Metadata

**Analog search scope:** `src/stocksig/io/` (auth_check, cache, throttle, edgar_client, dart_client, fundamentals, naver_scraper, market_kind, config), `src/stocksig/main_run.py`, `src/stocksig/runner.py`, `src/stocksig/compute/color_rules.py`, `src/stocksig/output/sheet_per_ticker.py:438`, `sheet_portfolio.py:303`, `tests/` (cache, edgar_client, smoke_n_tickers, color_rules)
**Files scanned:** 15 source + 4 test (targeted reads)
**Pattern extraction date:** 2026-06-11
