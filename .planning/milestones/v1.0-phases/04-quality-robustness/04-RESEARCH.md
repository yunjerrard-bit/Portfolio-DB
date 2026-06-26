# Phase 4: 품질·견고성 마감 - Research

**Researched:** 2026-06-11
**Domain:** 기존 코드베이스 마감/검증 — 시작 시 인증 사전검증(EDGAR/DART ping), 한국어 콘솔 로그(진행률·캐시 hit/miss·실패 요약), frozen panes 검증, 파스텔 색 톤 검증
**Confidence:** HIGH (코드베이스가 모두 grep·읽기로 검증됨, 신규 외부 의존성 0개)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

- **D-01 (데이터 품질 시트 미생성):** 데이터 품질 별도 시트를 만들지 **않는다**. EXEC-04의 "이슈 한곳 확인" 취지는 **콘솔 최종 실패 요약 블록**으로 충족한 것으로 재정의. 티커 실패는 시트1 실패행(D-03 from Phase 2), 펀더멘털 결손은 셀 주석(D-05 from Phase 3)으로 이미 워크북 안에서 확인 가능. `REQUIREMENTS.md`의 EXEC-04와 `ROADMAP.md` Phase 4 성공 기준 2번은 이 결정에 맞게 plan-phase에서 갱신 필요.
- **D-02 (인증 ping 실패 시 동작 = 경고 후 계속):** 인증 ping 실패(DART 키 만료, EDGAR 403 등) 시 한국어 경고를 출력하고 실행은 계속한다. 시세·시트 생성은 정상 진행, 해당 소스 펀더멘털만 결손 처리(셀 주석에 "인증 실패" 계열 사유). **fail-fast 아님.** 펀더멘털 결손 ≠ 티커 실패(D-disc-10) 원칙과 일관.
- **D-03 (ping 주기 = 매 실행 시작 시):** 캐시 없이 매 실행 시작 시 1회씩 ping. EDGAR 1회 + DART 1회는 200티커 실행 대비 무시할 비용.
- **D-04 (검증 범위 = EDGAR + DART 둘 다, 조건부):** EDGAR는 UA 이메일 유효성(403 여부), DART는 API 키 유효성 확인. **단 tickers.txt에 해당 시장 티커가 있을 때만 각각 ping** (US 티커 없으면 EDGAR ping 생략, KR 티커 없으면 DART ping 생략).

### Claude's Discretion

1. **콘솔 로그·캐시 통계 형식:** 캐시 hit/miss 집계 표시 형태(OHLCV/펀더멘털 분리 또는 합산), 최종 실패 요약 블록 포맷, 200티커 시 per-call HIT/MISS 로그 유지 여부. 기존 한국어 로그 패턴(`[k/N] OK <ticker>`, `총 N 중 성공 X / 실패 Y`)을 깨지 않는 선에서 확장. rich 진행바 도입 여부도 재량(필수 아님).
2. **색 톤 검증·조정:** 현행 Material 팔레트가 "강렬하지 않은 톤" 기준 충족하는지 시각 검증. 그레이스케일 ±1σ/±2σ 구분 검증 방법(수기 스크린샷 vs 자동 휘도 계산 테스트)도 재량. 조정 필요 시 단일 진원지 `compute/color_rules.py` 상수만 변경.
3. **ping 엔드포인트 선정:** EDGAR/DART 각각 가장 가벼운 검증 호출. 기존 토큰버킷(`@throttled_edgar` 8 RPS / `@throttled_dart` 2 RPS) 경유 여부 포함.
4. **인증 실패 시 펀더멘털 fetch 스킵 최적화:** ping 실패 소스에 대해 본 실행에서 per-ticker 펀더멘털 호출을 아예 건너뛸지, 아니면 개별 호출에 맡길지.

### Deferred Ideas (OUT OF SCOPE)

- **데이터 품질 별도 시트 (EXEC-04 원형):** D-01로 v1 미생성. `TickerFailure` + `MetricCell.note` 수집 구조가 이미 있어 추후 시트 추가는 작은 작업.
- **rich 진행바:** 도입 여부 Claude 재량 — 미도입해도 SC3 충족 가능.
- 새 지표·새 컬럼·새 데이터 소스 (다른 phase).
- 자동 스케줄링 (v2 SCHED).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| OUT-04 | 모든 시트의 1~5행을 fixed/frozen 처리 | 이미 구현됨 — `sheet_per_ticker.py:438` `freeze_panes(5, 0)`, `sheet_portfolio.py:303` `freeze_panes(5, 1)`. XlsxWriter `freeze_panes(row, col)` = "첫 비고정 셀" 규약이므로 (5,0)은 행 1~5 고정, (5,1)은 행 1~5 + A열 고정. 신규 코드 아님 — **자동 회귀 테스트(openpyxl 읽기) + 수기 검증**만 필요. `[CITED: xlsxwriter.readthedocs.io/worksheet.html]` |
| EXEC-05 (cited as EXEC-04 in roadmap, redefined by D-01) | 콘솔 로그 한국어 진행률·캐시 hit/miss·실패 요약 | 부분 구현됨 — `runner.py`가 `[k/N] OK/FAIL` + `총 N 중 성공 X / 실패 Y` 출력, `cache.py`가 per-call HIT/MISS 로깅. **누락분 = 캐시 hit/miss 집계 통계 + 최종 실패 요약 블록(인증 ping 결과 포함).** |

> 주의: 추가 컨텍스트가 명시한 phase 요구사항 IDs는 **OUT-04, EXEC-04**다. D-01에 따라 EXEC-04(데이터 품질 시트)는 콘솔 요약으로 재정의되며, 그 충족 수단은 사실상 EXEC-05(콘솔 로그)의 확장이다. plan-phase가 REQUIREMENTS.md·ROADMAP.md 텍스트를 D-01에 맞게 갱신해야 한다.
</phase_requirements>

## Summary

Phase 4는 **신규 기능이 거의 없는 마감/검증 phase**다. 신규 외부 의존성은 0개 — 기존 스택(XlsxWriter, edgartools 5.35, opendartreader 0.3.2, diskcache, pyrate-limiter, logging stdlib)만 재배선한다. 작업은 4갈래로 나뉜다:

1. **신규 기능 (유일):** 시작 시 인증 사전검증(EDGAR UA/403 ping + DART 키 유효성 ping). `main_run.py:run()`의 티커 로드 직후(`L234~235` 이후)에 조건부 ping을 삽입한다. `classify_market`으로 US/KR 티커 존재 여부를 판단해 해당 시장 티커가 있을 때만 ping(D-04). 실패 시 경고만 출력하고 계속(D-02), ping 실패 소스의 펀더멘털 fetch를 스킵하는 플래그를 `run_all`/`fetch_fundamentals`로 전달(Claude 재량 4).
2. **검증 (frozen panes):** 이미 구현됨. openpyxl 읽기 회귀 테스트 + 수기 검증.
3. **확장 (콘솔 로그):** `cache.py`에 hit/miss 집계 카운터를 추가하고, `main_run.py` 종료부에 최종 요약 블록(성공/실패/인증 상태/캐시 통계)을 출력.
4. **검증 (색 톤):** `color_rules.py`의 Material 팔레트가 "강렬하지 않은 톤" 기준을 충족하는지 + 그레이스케일에서 ±1σ/±2σ 구분 가능한지 검증. 자동 휘도(luminance) 테스트 권장(아래 Pattern 4).

**Primary recommendation:** `io/auth_check.py` 신규 모듈에 `ping_edgar()`/`ping_dart()` 순수 함수 + `AuthStatus` dataclass를 두고, `main_run.run()`이 티커 로드 직후 조건부로 호출한 뒤 그 결과를 (a) 콘솔 경고, (b) `fetch_fundamentals`로 전달하는 skip 플래그, (c) 종료부 요약 블록의 한 줄로 흘려보낸다. 색 톤은 그레이스케일 휘도 자동 테스트로 검증한다.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 인증 사전검증 (EDGAR/DART ping) | IO / 외부 API (`io/auth_check.py` 신규) | 오케스트레이션 (`main_run.run`) | ping은 외부 HTTP 호출이므로 io 계층. 호출 시점·조건부 판단·결과 전파는 main_run이 조율. throttle 데코레이터 재사용. |
| 조건부 ping 판단 (US/KR 티커 존재) | 오케스트레이션 (`main_run.run`) | 분류 (`market_kind.classify_market`) | 어떤 시장 ping을 돌릴지는 로드된 specs를 보고 결정 — main_run이 specs를 갖고 있음. |
| 캐시 hit/miss 집계 통계 | IO / 캐시 (`io/cache.py`) | 오케스트레이션 (출력) | 카운터는 hit/miss가 발생하는 cache 모듈에서 증가시키는 게 결합도 최소. 출력은 main_run. |
| 최종 실패 요약 블록 | 오케스트레이션 (`main_run.run` 종료부) | — | `(results, failures)` + 캐시 통계 + 인증 상태를 모두 가진 유일한 지점. |
| 진행률 로그 `[k/N]` | 오케스트레이션 (`runner.run_all`) | — | 이미 구현됨 — 변경 없음. |
| frozen panes | 출력 (`output/sheet_*.py`) | — | 이미 구현됨 — 검증만. |
| 색 톤 (팔레트 상수) | 컴퓨트 (`compute/color_rules.py`) | 출력 (`output/writer.py` Format 캐시) | 단일 진원지(D-02 from Phase 2). 조정 시 상수만 변경하면 writer는 자동 반영. |

## Standard Stack

### 신규 의존성: 없음

이 phase는 **신규 외부 패키지를 설치하지 않는다.** 전부 기존 `pyproject.toml` 의존성으로 충족된다 `[VERIFIED: pyproject.toml grep]`:

| Library | 설치된 버전 제약 | 이 phase에서의 용도 |
|---------|------------------|---------------------|
| edgartools (`edgar`) | `>=5,<6` (5.35.0 설치 확인됨, STATE.md 03-01) | EDGAR ping — `Company(t).get_facts()` 또는 더 가벼운 식별 호출 |
| opendartreader (`opendartreader`) | `>=0.3` (0.3.2 설치 확인됨) | DART ping — `OpenDartReader(key).list(...)` 또는 가벼운 `finstate_all` 1건 |
| diskcache | `>=5.6` | 기존 OHLCV/펀더멘털 캐시 — 집계 카운터는 캐시 자체가 아니라 `cache.py` 모듈 레벨 변수 |
| pyrate-limiter | `>=3` (4.1 설치) | ping 호출도 `@throttled_edgar`/`@throttled_dart` 경유 가능 (재량 3) |
| logging (stdlib) | — | 한국어 콘솔 로그 (basicConfig는 `main.py`에 이미 UTF-8로 설정됨) |
| openpyxl (dev) | dev group | frozen panes 회귀 테스트 (읽기), 색 톤 휘도 테스트 |
| pytest, pytest-mock, freezegun (dev) | dev group | 테스트 |

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| stdlib logging 집계 카운터 | rich progress bar | rich는 STACK.md 권장이나 D-deferred로 미도입 결정. 200티커 시 per-call 로그를 progress bar로 대체하면 콘솔이 깔끔해지나, 현행 `[k/N]` 패턴(테스트가 grep)을 깨므로 도입 시 테스트 영향. **권장: 미도입.** |
| edgartools `Company().get_facts()` ping | 직접 `httpx` GET `data.sec.gov` (UA 헤더 포함, 403 검출) | httpx ping이 더 가볍고 403을 명시적으로 잡기 쉬움. 단 신규 의존성 아님(edgartools transitive httpx 0.28.1 있음). edgartools 경로는 set_identity가 import-time에 이미 호출됨 — ping이 같은 UA를 쓰는지 확인 필요. **권장: 가벼운 EDGAR 식별 호출(아래 Pattern 1) 또는 httpx submissions 엔드포인트.** |
| opendartreader `list()` ping | 직접 `httpx` GET OpenDART `/api/list.json?crtfc_key=...` | 둘 다 가능. opendartreader 경유가 코드 일관성 높음. 키 무효 시 status 코드로 검출. **권장: opendartreader 또는 httpx list.json 1건.** |

**Installation:** 없음 — 신규 설치 0개.

## Package Legitimacy Audit

> 이 phase는 **신규 외부 패키지를 설치하지 않는다.** 모든 사용 라이브러리는 Phase 1~3에서 이미 설치·검증된 기존 의존성이다. 따라서 본 audit는 "신규 설치 없음" 확인에 그친다.

| Package | Registry | Disposition |
|---------|----------|-------------|
| (신규 설치 없음) | — | N/A — 기존 의존성 재사용만 |

**Packages removed due to slopcheck [SLOP] verdict:** none (신규 설치 없음)
**Packages flagged as suspicious [SUS]:** none

*slopcheck 미실행 사유: 신규 패키지 설치가 0개이므로 적용 대상이 없음. 기존 edgartools/opendartreader/diskcache/pyrate-limiter는 Phase 1~3에서 `pyproject.toml`에 고정·검증됨 `[VERIFIED: pyproject.toml]`.*

## Architecture Patterns

### System Architecture Diagram

```
main.py (--tickers --env --output-dir --summary-only)
   │  UTF-8 reconfigure + logging.basicConfig (한국어)
   ▼
main_run.run()
   │
   ├─ load_env(env_path)              # .env: EDGAR_USER_AGENT_EMAIL, OPENDART_API_KEY
   ├─ reset_naver_count()
   ├─ specs = read_tickers_extended() ──► logger "티커 N개 로드 완료"
   │
   ├─ ★ NEW: 인증 사전검증 (D-02~04) ◄─── auth_check.ping_edgar / ping_dart
   │     │   markets = {classify_market(s.symbol) for s in specs}
   │     │   if "US" in markets:  edgar_status = ping_edgar()   # 403/UA 검증
   │     │   if "KR" in markets:  dart_status  = ping_dart()    # 키 유효성 검증
   │     │   실패 → logger.warning("⚠ EDGAR 인증 실패 ...") (계속, fail-fast 아님)
   │     ▼
   │   AuthStatus(edgar_ok, dart_ok, edgar_note, dart_note)
   │     │  (재량 4) ping 실패 소스 → skip 플래그로 펀더멘털 fetch 차단
   │
   ├─ PASS 1: run_all(specs, classify_market, pipeline, fundamentals_fn)
   │     │   ThreadPoolExecutor(4) per-ticker
   │     │   pipeline: fetch_ohlcv_cached → cache HIT/MISS 로그
   │     │   fundamentals_fn: fetch_fundamentals (US=EDGAR→yf, KR=DART→Naver→yf)
   │     │     └─ skip 플래그 시 해당 소스 호출 생략, note="인증 실패" 셀 주석
   │     ▼
   │   (results, failures)  + cache 모듈 집계 카운터 누적
   │
   ├─ PASS 2: make_workbook → write_portfolio_sheet (시트1, freeze_panes(5,1))
   │     │                  → write_sheet_for_ticker × N (freeze_panes(5,0))
   │     ▼
   │   portfolio_YYYYMMDD.xlsx
   │
   └─ ★ NEW: 최종 요약 블록 (콘솔)
         "════ 실행 요약 ════"
         "티커: 총 N / 성공 X / 실패 Y"
         "인증: EDGAR OK | DART 실패(키 만료)"
         "캐시: OHLCV HIT a/MISS b · 펀더멘털 HIT c/MISS d"
         "실패 티커: <list> (시트1 참조)"
```

### Recommended Project Structure (신규 파일 1개)

```
src/stocksig/
├── io/
│   ├── auth_check.py     # ★ NEW — ping_edgar() / ping_dart() / AuthStatus
│   └── cache.py          # 확장 — 모듈 레벨 hit/miss 카운터 + 조회/리셋 함수
├── main_run.py           # 확장 — ping 호출(시작) + 요약 블록(종료) + skip 전파
└── (나머지 무변경)

tests/
├── test_auth_check.py    # ★ NEW — ping 성공/실패/예외 흡수 (mock httpx/client)
├── test_cache.py         # 확장 — 카운터 증가/리셋
├── test_freeze_panes.py  # ★ NEW — openpyxl 읽기로 freeze_panes 검증 (OUT-04 회귀)
├── test_color_tone.py    # ★ NEW — 그레이스케일 휘도 구분 자동 테스트 (재량 2)
└── test_smoke_n_tickers.py  # 확장 — 요약 블록 로그 assert
```

### Pattern 1: 인증 ping — 순수 함수 + dataclass (예외 흡수)

**What:** ping 함수는 `bool` 또는 `AuthStatus`를 반환하고 **절대 raise하지 않는다** (`fetch_fundamentals` 전 경로 흡수 패턴 차용, `fundamentals.py:311`). D-02(경고 후 계속)를 함수 계약으로 강제.
**When to use:** `main_run.run()` 티커 로드 직후, 조건부.
**Example:**
```python
# Source: 기존 edgar_client.py / dart_client.py / fundamentals.py 예외흡수 패턴 차용
# src/stocksig/io/auth_check.py (NEW)
from dataclasses import dataclass
import logging
logger = logging.getLogger(__name__)

@dataclass
class AuthStatus:
    edgar_ok: bool | None = None   # None = ping 미실행(해당 시장 티커 없음)
    dart_ok: bool | None = None
    edgar_note: str | None = None  # 한국어 사유 (셀 주석 재사용 가능)
    dart_note: str | None = None

def ping_edgar() -> tuple[bool, str | None]:
    """EDGAR UA/403 사전검증. raise 금지 — (ok, 한국어_사유)."""
    try:
        from stocksig.io import edgar_client  # set_identity는 import-time에 이미 호출됨
        # 가장 가벼운 식별 호출 1건 (예: 알려진 소형 티커 facts 또는 httpx submissions HEAD)
        edgar_client.fetch_edgar_raw("AAPL")   # @throttled_edgar 경유 (재량 3)
        logger.info("auth | EDGAR 인증 OK")
        return True, None
    except Exception as e:  # 403/네트워크/UA 오류 전부 흡수 (D-02)
        note = "EDGAR 403 (UA 확인)" if "403" in str(e) else f"EDGAR 인증 실패: {e}"
        logger.warning("auth | ⚠ %s — 미국 펀더멘털 결손 처리됩니다", note)
        return False, note

def ping_dart() -> tuple[bool, str | None]:
    """DART API 키 사전검증. raise 금지."""
    try:
        from stocksig.io import dart_client
        # 가벼운 list 1건 또는 알려진 종목 finstate 1건; status 코드로 키 유효성 판정
        dart_client.fetch_dart_raw("005930.KS", 2024)  # @throttled_dart 경유
        logger.info("auth | DART 인증 OK")
        return True, None
    except Exception as e:
        note = f"DART 인증 실패: {e}"
        logger.warning("auth | ⚠ %s — 한국 펀더멘털 결손 처리됩니다", note)
        return False, note
```
> 주의: ping 엔드포인트 선정(재량 3)은 planner/구현자가 확정. `fetch_edgar_raw("AAPL")`은 무겁고 EDGAR 캐시를 오염시킬 수 있으므로, 더 가벼운 `httpx.get("https://www.sec.gov/cgi-bin/browse-edgar", headers={"User-Agent": _resolve_identity()})` HEAD 류 호출로 403만 검출하는 편이 D-03(매 실행 무비용 ping) 취지에 맞다. DART도 `OpenDartReader(key).list("005930", ...)` 1건이 `finstate_all`보다 가볍다.

### Pattern 2: 조건부 ping (US/KR 티커 존재 시에만, D-04)

**What:** 로드된 specs에서 시장 집합을 만들어 해당 시장 티커가 있을 때만 ping.
**Example:**
```python
# main_run.run() 안, read_tickers_extended 직후
markets = {classify_market(s.symbol) for s in specs}
auth = AuthStatus()
if "US" in markets:
    auth.edgar_ok, auth.edgar_note = ping_edgar()
if "KR" in markets:
    auth.dart_ok, auth.dart_note = ping_dart()
```

### Pattern 3: ping 실패 소스의 펀더멘털 스킵 (Claude 재량 4)

**What:** ping이 실패한 소스는 본 실행에서 per-ticker 펀더멘털 호출을 건너뛰어 불필요한 throttle 대기·재시도를 절약하고, 셀 주석에 "인증 실패" 사유를 남긴다.
**When to use:** `auth.edgar_ok is False` 또는 `auth.dart_ok is False`.
**구현 경로:** `fetch_fundamentals`에 skip 플래그를 전달. `run_all`이 `fundamentals_fn`을 받는 구조(`runner.py:113`)이므로, `main_run`이 `functools.partial` 또는 클로저로 skip 정보를 바인딩한 `fundamentals_fn`을 넘긴다.
```python
# main_run.run() — fundamentals_fn 클로저로 skip 주입
from functools import partial

def _fundamentals_with_auth(ticker, market, last_close):
    if market == "US" and auth.edgar_ok is False:
        from stocksig.io.fundamentals import _empty_result
        return _empty_result("조회 실패: EDGAR 인증 실패")  # yf 폴백도 의도적으로 스킵 여부는 구현자 결정
    if market == "KR" and auth.dart_ok is False:
        from stocksig.io.fundamentals import _empty_result
        return _empty_result("조회 실패: DART 인증 실패")
    return fetch_fundamentals(ticker, market, last_close)

results, failures = run_all(specs, classify_market, pipeline,
                            fundamentals_fn=_fundamentals_with_auth)
```
> 주의: EDGAR 인증 실패 시 US 종목이 yf 폴백으로 PER 등을 채울 수 있는지는 결정 포인트다. D-02는 "해당 소스 펀더멘털만 결손 처리"라고 명시 — 1차 소스만 스킵하고 yf 폴백은 살릴지(부분 충족), 전부 결손 처리할지 planner가 확정. `_empty_result`는 yf까지 스킵하는 보수적 선택. yf 폴백을 살리려면 `fetch_fundamentals`에 `skip_edgar=True` 류 인자를 추가해 EDGAR 호출만 건너뛰게 한다.

### Pattern 4: 캐시 hit/miss 집계 카운터 (SC3)

**What:** `cache.py`에 모듈 레벨 카운터를 추가하고 `get_ohlcv`/`get_fund`에서 증가. `reset_naver_count()`(naver_scraper) 패턴 차용.
**Example:**
```python
# src/stocksig/io/cache.py 확장
_stats = {"ohlcv_hit": 0, "ohlcv_miss": 0, "fund_hit": 0, "fund_miss": 0}

def reset_cache_stats() -> None:
    for k in _stats:
        _stats[k] = 0

def get_cache_stats() -> dict[str, int]:
    return dict(_stats)

# get_ohlcv 안:
#   if value is not None: _stats["ohlcv_hit"] += 1; logger.info(... HIT ...)
#   else:                 _stats["ohlcv_miss"] += 1; logger.info(... MISS ...)
# get_fund 안 동일 (fund_hit/fund_miss)
```
> 주의: `run_all`이 `ThreadPoolExecutor(max_workers=4)`로 병렬 실행하므로 카운터 증가는 **GIL 하에서 단순 정수 `+=`이긴 하나 race 가능**. `threading.Lock` 또는 `collections.Counter` + lock으로 보호 권장(Pitfall 3 참조). `main_run.run()`은 `reset_cache_stats()`를 시작부에서 호출(다회 실행 안전, `reset_naver_count` 옆).

### Pattern 5: 최종 요약 블록 (콘솔, D-01 EXEC-04 대체 충족)

**What:** `run()` 종료부(현 `L272~277` 워크북 저장 로그 직후)에 한 블록으로 출력.
**Example:**
```python
# main_run.run() 종료부 — 기존 L272-277 확장
stats = cache.get_cache_stats()
logger.info("════════ 실행 요약 ════════")
logger.info("티커: 총 %d / 성공 %d / 실패 %d", len(specs), len(results), len(failures))
logger.info("인증: EDGAR %s | DART %s",
            _auth_label(auth.edgar_ok, auth.edgar_note),
            _auth_label(auth.dart_ok, auth.dart_note))
logger.info("캐시: OHLCV HIT %d/MISS %d · 펀더멘털 HIT %d/MISS %d",
            stats["ohlcv_hit"], stats["ohlcv_miss"],
            stats["fund_hit"], stats["fund_miss"])
if failures:
    logger.warning("실패 티커: %s (시트1 참조)",
                   ", ".join(f.spec.symbol for f in failures))
```
> `_auth_label(ok, note)`: `None`→"해당없음", `True`→"OK", `False`→f"실패({note})".

### Anti-Patterns to Avoid

- **ping에서 raise:** D-02 위반. ping 함수는 반드시 예외를 흡수하고 `(False, note)` 반환. `fundamentals.py`의 전 경로 try/except 흡수 계약과 일관.
- **사용자 입력 대기(프롬프트):** Specific Idea에 명시 — 무인/스케줄 호환을 위해 ping 실패 시에도 프롬프트 없이 자동 계속.
- **현행 `[k/N]` 로그 패턴 변경:** `test_smoke_n_tickers.py:214`가 `"총 10 티커 중 성공 10 / 실패 0"` 문자열을 grep. 변경하면 회귀. 요약 블록은 **추가**이지 대체가 아님.
- **색 상수를 writer/시트 코드에 하드코딩:** D-02(단일 진원지). 톤 조정은 `color_rules.py` 상수만.
- **per-call HIT/MISS 로그를 200티커에서 제거:** 캐시 검증 테스트(`test_smoke_n_tickers.py:190` `"cache HIT" in r.getMessage()`)가 의존. 제거 시 회귀. 콘솔 노이즈가 문제면 집계 블록만 INFO, per-call은 DEBUG로 내릴 수 있으나 테스트 캡처 레벨 영향 확인 필요.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| HTTP rate-limit on ping | 수동 sleep/카운터 | 기존 `@throttled_edgar`/`@throttled_dart` 데코레이터 | 이미 토큰버킷 구현됨, ping도 같은 버킷 경유하면 메인 fetch와 레이트 공유 |
| 예외 흡수 + 한국어 사유 | 새 try/except 패턴 | `fundamentals.py` `_empty_result(note)` + `MetricCell.note` 재사용 | "인증 실패" 사유가 기존 셀 주석 파이프라인을 그대로 탄다 |
| 캐시 통계 영속화 | sqlite 테이블/파일 | 모듈 레벨 dict + run당 reset (`reset_naver_count` 패턴) | run 1회 통계만 필요. 영속화 불필요 |
| frozen panes 검증 | 수동 xlsx 열기만 | openpyxl 읽기 회귀 테스트 (`ws.freeze_panes` 속성) | 자동 회귀로 후속 phase가 깨뜨리지 않게 보장 |
| 그레이스케일 색 구분 검증 | 눈대중 스크린샷만 | 휘도(luminance) 자동 계산 테스트 | 재현 가능·CI 가능. WCAG relative luminance 공식 사용 |
| UTF-8 콘솔 한국어 | chcp 65001 수동 | 이미 있는 `main.py:19-32` reconfigure + `encoding="utf-8"` | Windows 콘솔 한국어 깨짐 이미 해결됨 — 신규 로그도 자동 안전 |

**Key insight:** Phase 4의 거의 모든 "신규" 작업은 기존 구조의 **재배선(rewiring)**이다. ping은 throttle·예외흡수·셀주석 파이프라인을 재사용하고, 캐시 통계는 `reset_naver_count` 패턴을, 요약 블록은 이미 모인 `(results, failures)`를 재사용한다.

## Runtime State Inventory

> rename/refactor가 아니나, 캐시·카운터·인증이라는 런타임 상태를 다루므로 점검.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `.cache/ohlcv` (24h TTL), `.cache/fundamentals` (7d TTL) — diskcache. ping은 캐시 미사용(D-03 매 실행). | ping이 EDGAR/DART 캐시를 오염시키지 않도록 ping 호출이 `fetch_edgar_cached`/`fetch_dart_cached`(캐시 쓰기)가 아닌 캐시 미경유 경로(`fetch_edgar_raw`/직접 httpx)를 쓰게 할 것 |
| Live service config | 없음 — n8n/Datadog 등 외부 서비스 없음. EDGAR/DART는 stateless REST. | None — verified by 코드 grep (외부 서비스 등록 없음) |
| OS-registered state | 없음 — Task Scheduler 미사용(v1 수동 실행, SCHED는 v2). | None — verified by REQUIREMENTS.md (스케줄링 OUT) |
| Secrets/env vars | `.env`: `EDGAR_USER_AGENT_EMAIL`, `OPENDART_API_KEY` (`config.REQUIRED_KEYS`, `config.py:18`). ping이 이 자격증명을 읽음. 키 이름 변경 없음. | None — ping은 기존 키를 읽기만 함 |
| Build artifacts | 신규 모듈 `io/auth_check.py` 추가는 editable install(`hatchling`)에서 자동 인식. egg-info 재생성 불필요(uv 관리). | None |

**캐시 통계 카운터 = 신규 런타임 상태:** 모듈 레벨 dict. `run()` 시작부 `reset_cache_stats()` 호출 필수(다회 실행/장수 프로세스 안전 — `reset_naver_count()` 옆에 배치). 병렬(ThreadPoolExecutor 4) race 보호 필요(Pitfall 3).

## Common Pitfalls

### Pitfall 1: EDGAR ping이 캐시를 오염시키거나 무겁다
**What goes wrong:** `fetch_edgar_cached("AAPL", quarter)`를 ping으로 쓰면 7d 캐시에 AAPL을 박아넣고, AAPL이 입력에 없어도 EDGAR facts 전체를 받는 무거운 호출이 된다.
**Why it happens:** 가장 손쉬운 ping이 기존 fetch 함수 재사용이라서.
**How to avoid:** ping은 캐시 미경유 + 가벼운 식별 호출. EDGAR는 UA 헤더 포함 HEAD/GET로 403만 검출(`https://www.sec.gov/...` + `_resolve_identity()` UA). DART는 `list()` 1건. 둘 다 결과를 캐시에 쓰지 않음.
**Warning signs:** ping 후 `.cache/fundamentals`에 입력에 없는 티커 키 등장.

### Pitfall 2: EDGAR set_identity import-time 호출 — ping이 import만으로 UA를 등록
**What goes wrong:** `edgar_client.py:45`가 `import` 시점에 `set_identity(...)`를 실행. `auth_check`가 `from stocksig.io import edgar_client`를 import하면 그 부수효과로 UA가 설정됨. ping이 httpx 직접 경로를 쓰면 UA를 별도로 넣어야 일관.
**Why it happens:** set_identity가 모듈 import 부수효과(Anti-Pattern 회피용 1회 설정).
**How to avoid:** ping이 edgartools 경로면 import만으로 UA 설정 완료. httpx 직접 경로면 `edgar_client._resolve_identity()`를 재사용해 UA 헤더 구성. **둘을 섞지 말 것.**
**Warning signs:** EDGAR ping이 로컬은 통과하나 실제 환경에서 403 — UA 누락 의심.

### Pitfall 3: 캐시 카운터 race (ThreadPoolExecutor 4 워커)
**What goes wrong:** `_stats["ohlcv_hit"] += 1`이 4개 스레드에서 동시 실행 → 일부 증가 유실. CPython GIL이 단일 바이트코드는 보호하나 `read-modify-write`(`+=`)는 원자적이지 않음.
**Why it happens:** `run_all`이 `max_workers=4`(`runner.py:27`).
**How to avoid:** `threading.Lock`으로 카운터 증가 보호하거나 `cache.py`에서 dict 대신 `itertools.count`/lock-guarded 증가. 통계가 ±몇 개 어긋나도 치명적이진 않으나(표시용), 정확성을 원하면 lock.
**Warning signs:** `OHLCV HIT + MISS ≠ 총 티커 수` (2차 실행 시).

### Pitfall 4: DART ping이 알려진 종목을 하드코딩 → 그 종목이 상장폐지/리포트 미존재 시 false negative
**What goes wrong:** ping이 `005930.KS`(삼성전자) 1건으로 키를 검증하는데, 특정 연도 리포트가 없거나 status="013"이면 키가 멀쩡한데도 "인증 실패"로 판정.
**Why it happens:** ping 대상 종목/연도를 너무 특정하게 고름.
**How to avoid:** DART ping은 키 유효성만 봐야 함 — `status` 코드로 구분: status="000"(정상) 또는 "013"(데이터없음, 키는 유효) → OK; 키 무효 status(예: "010" 등록되지 않은 키, "020" 쿼터초과는 일시적)만 실패로. `dart_client._STATUS_NOTES`에 이미 "013"/"020" 매핑 존재 — 키 무효 코드는 별도 판정.
**Warning signs:** 유효한 키인데 매 실행 "DART 인증 실패" 경고.

### Pitfall 5: 색 톤 그레이스케일 구분 실패 (COLOR-07/SC4)
**What goes wrong:** SOFT_GREEN(`#2E7D32`)과 SOFT_RED(`#C62828`)가 그레이스케일로 변환되면 휘도가 비슷해 흑백에서 ±1σ 방향을 구분 못 함. HARD는 배경색까지 있어 구분되나 SOFT는 글자색만이라 위험.
**Why it happens:** 녹색/빨강은 색맹·흑백에서 가장 혼동되기 쉬운 페어.
**How to avoid:** 휘도 자동 테스트(Pattern 아래) + 필요 시 SOFT_GREEN/SOFT_RED 휘도 차를 벌리거나 bold(이미 적용됨)에 의존. SOFT는 글자색만이라 흑백에서 본질적으로 약함 — **SC4 "그레이스케일 ±1σ/±2σ 구분"은 HARD(배경색 있음)는 명확히 통과, SOFT(글자색만)는 휘도차 측정 후 판정.** 구분이 부족하면 색 톤 변경(`color_rules.py` 상수)이 단일 진원지 수정.
**Warning signs:** 흑백 인쇄 시 약한 녹/빨 글자가 같은 회색으로 보임.

### 색 톤 휘도 검증 (자동 테스트, 재량 2)

```python
# tests/test_color_tone.py (NEW)
# WCAG relative luminance — 그레이스케일 휘도 차로 ±1σ/±2σ 구분 가능성 검증
def _rel_luminance(hex_color: str) -> float:
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i+2], 16) / 255 for i in (0, 2, 4))
    def _lin(c): return c/12.92 if c <= 0.03928 else ((c+0.055)/1.055)**2.4
    return 0.2126*_lin(r) + 0.7152*_lin(g) + 0.0722*_lin(b)

def test_hard_buckets_distinguishable_grayscale():
    from stocksig.compute.color_rules import GREEN_100, RED_100
    # HARD 배경색 휘도차 — 충분히 벌어져야 흑백 구분 가능
    diff = abs(_rel_luminance(GREEN_100) - _rel_luminance(RED_100))
    assert diff > 0.05, f"HARD 배경 휘도차 부족: {diff:.3f}"
```
> 임계값(0.05 등)은 구현자가 실제 팔레트로 측정 후 확정. SOFT(글자색)와 HARD(배경색)를 분리 검증. 그레이스케일 스크린샷 수기 대조도 병행 권장(`output/portfolio_*.xlsx`를 Excel에서 흑백 미리보기).

## Code Examples

### frozen panes 회귀 테스트 (OUT-04, openpyxl 읽기)
```python
# tests/test_freeze_panes.py (NEW)
# Source: openpyxl Worksheet.freeze_panes 속성 = 첫 비고정 셀 좌표 (예: "A6", "B6")
import openpyxl
from stocksig.main_run import run

def test_all_sheets_freeze_rows_1_to_5(mock_pipeline_env, tmp_path, env_file):
    tickers = tmp_path / "tickers.txt"
    tickers.write_text("AAPL\nMSFT\n", encoding="utf-8")
    out = run(tickers, env_file, tmp_path / "output")
    wb = openpyxl.load_workbook(out)
    for name in wb.sheetnames:
        fp = wb[name].freeze_panes  # "A6" (종목시트) 또는 "B6" (시트1)
        assert fp is not None and fp.endswith("6"), \
            f"{name} freeze_panes={fp} — 행 1~5 고정 아님"
    # 시트1은 A열까지 고정 → "B6"
    assert wb["시트1"].freeze_panes == "B6"
```
> XlsxWriter `freeze_panes(5, 0)` → openpyxl 읽기 시 `"A6"`(행 6이 첫 비고정), `freeze_panes(5, 1)` → `"B6"`. `[CITED: xlsxwriter.readthedocs.io/worksheet.html — freeze_panes(row,col)는 첫 비고정 셀 규약]`

### 요약 블록 로그 assert (EXEC-05 확장)
```python
# tests/test_smoke_n_tickers.py 확장
def test_summary_block_emitted(mock_pipeline_env, tmp_path, env_file, caplog):
    import logging
    tickers = tmp_path / "tickers.txt"
    tickers.write_text("AAPL\nMSFT\n", encoding="utf-8")
    caplog.set_level(logging.INFO)
    run(tickers, env_file, tmp_path / "output")
    msgs = [r.getMessage() for r in caplog.records]
    assert any("실행 요약" in m for m in msgs)
    assert any("캐시:" in m and "HIT" in m for m in msgs)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| 데이터 품질 별도 시트 (EXEC-04 원형) | 콘솔 최종 요약 블록 + 기존 시트1 실패행 + 셀 주석 | D-01 (2026-06-11 discuss) | 신규 시트 작성 코드 불필요. REQUIREMENTS/ROADMAP 텍스트 갱신 필요 |
| 인증 검증 없음 (per-call 호출이 실패 시 흡수) | 시작 시 사전검증 ping + skip 최적화 | D-02~04 (2026-06-11) | 200티커 전 불필요한 인증실패 재시도 사전 차단 |

**Deprecated/outdated:** 없음 — 기존 스택 전부 현행 유지.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | EDGAR ping에 가벼운 httpx GET(UA 헤더)가 `fetch_edgar_raw` 재사용보다 적합 | Pattern 1 / Pitfall 1 | 무거운 ping이면 D-03(무비용) 취지 약화. 구현자가 엔드포인트 확정(재량 3) |
| A2 | DART 키 무효는 `status` 코드로 구분 가능, "013"은 키 유효 | Pitfall 4 | OpenDartReader가 키 무효 시 정확히 어떤 status/예외를 내는지 실측 필요 — 구현 시 1회 확인 |
| A3 | SOFT 버킷(글자색만)은 그레이스케일 구분이 본질적으로 약할 수 있음 | Pitfall 5 | 실제 휘도 측정 전엔 SC4 SOFT 통과 여부 불확실. 자동 테스트로 측정 후 판정 |
| A4 | EDGAR 인증 실패 시 yf 폴백을 살릴지/죽일지는 D-02 해석에 따라 결정 | Pattern 3 | "해당 소스만 결손"의 범위 해석. planner가 yf 폴백 유지 여부 확정 필요 |
| A5 | 캐시 카운터 `+=`는 4워커에서 race 가능 (lock 필요) | Pitfall 3 | lock 없으면 통계가 ±소수 어긋남(표시용이라 치명적이진 않음) |

## Open Questions (RESOLVED)

1. **ping 엔드포인트 정확한 선정 (재량 3)** — RESOLVED: 04-03-PLAN Task 1에서 httpx 직접 GET 단일 경로로 확정.
   - What we know: throttle 데코레이터 재사용 가능, EDGAR는 403/UA, DART는 키 유효성 검증.
   - What's unclear: edgartools 경로 vs httpx 직접 경로 중 무엇이 가장 가벼운지, DART 키 무효 시 정확한 status/예외 형태.
   - Recommendation: 구현 시 두 경로를 1회씩 실측(실제 .env로 `python -c` 호출) 후 가벼운 쪽 채택. 캐시 미경유 보장.

2. **EDGAR 인증 실패 시 yf 폴백 유지 여부 (재량 4 / A4)** — RESOLVED: 04-03-PLAN Task 2에서 A4 확정 (`skip_edgar=True`로 EDGAR 1차만 스킵, yf 폴백 유지).
   - What we know: D-02는 "해당 소스 펀더멘털만 결손 처리".
   - What's unclear: US 종목에서 EDGAR ping 실패 시 yf 폴백으로 PER 등을 채우는 게 D-02 위반인지(EDGAR≠yf, 다른 소스).
   - Recommendation: yf는 EDGAR와 독립 소스이므로 살리는 게 사용자 가치 높음. `skip_edgar` 인자로 EDGAR 1차만 건너뛰고 yf 폴백은 작동시키는 설계 권장. planner 확정.

3. **per-call HIT/MISS 로그 레벨 (200티커 콘솔 노이즈, 재량 1)** — RESOLVED: 04-01-PLAN Task 1에서 per-call 로그 유지 + 집계 블록 추가로 확정.
   - What we know: 테스트가 INFO 레벨에서 `"cache HIT"` 문자열을 캡처.
   - What's unclear: 200티커 시 per-call 로그가 너무 많을 수 있음.
   - Recommendation: per-call은 유지(테스트 의존), 집계 블록을 추가. 노이즈가 실사용 문제면 별도 quick task로 DEBUG 강등 검토(테스트 캡처 레벨 동반 조정).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| edgartools (`edgar`) | EDGAR ping | ✓ | 5.35.0 (pyproject `>=5,<6`) | — |
| opendartreader | DART ping | ✓ | 0.3.2 (pyproject `>=0.3`) | — |
| diskcache | 캐시 통계 | ✓ | `>=5.6` | — |
| pyrate-limiter | ping throttle | ✓ | 4.1 (`>=3`) | — |
| openpyxl (dev) | frozen panes/색 톤 테스트 | ✓ | dev group | — |
| `.env` (EDGAR_USER_AGENT_EMAIL, OPENDART_API_KEY) | ping 자격증명 | 사용자 보유 | — | ping 실패 시 D-02 경고 후 계속 |
| 네트워크 (SEC EDGAR, OpenDART) | 실제 ping | 런타임 | — | ping 실패 시 결손 처리 |

**Missing dependencies with no fallback:** 없음 — 전부 설치됨.
**Missing dependencies with fallback:** 실제 인증/네트워크는 ping 실패 시 D-02 경고 후 계속(설계된 폴백).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest >=8.0 (+ pytest-mock, freezegun, openpyxl) `[VERIFIED: pyproject.toml]` |
| Config file | `pyproject.toml [tool.pytest.ini_options]` — `testpaths=["tests"]`, `pythonpath=["src"]` |
| Quick run command | `uv run pytest tests/test_auth_check.py tests/test_cache.py -x` |
| Full suite command | `uv run pytest` (현재 200 passed, STATE.md) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| OUT-04 | 모든 시트 행 1~5 frozen | unit (openpyxl 읽기) | `uv run pytest tests/test_freeze_panes.py -x` | ❌ Wave 0 |
| EXEC-05 (ping) | EDGAR/DART ping 성공/실패/예외흡수 | unit (mock) | `uv run pytest tests/test_auth_check.py -x` | ❌ Wave 0 |
| EXEC-05 (조건부) | US/KR 티커 없으면 ping 생략 | unit (mock) | `uv run pytest tests/test_auth_check.py::test_conditional -x` | ❌ Wave 0 |
| EXEC-05 (캐시 통계) | hit/miss 카운터 증가·리셋 | unit | `uv run pytest tests/test_cache.py -k stats -x` | ⚠️ 확장 |
| EXEC-05 (요약 블록) | 종료부 요약 로그 출력 | integration (smoke) | `uv run pytest tests/test_smoke_n_tickers.py -k summary -x` | ⚠️ 확장 |
| COLOR-07/SC4 | 그레이스케일 휘도 구분 | unit (luminance) | `uv run pytest tests/test_color_tone.py -x` | ❌ Wave 0 |
| (수기) | 실 `python main.py` frozen panes 육안 + 흑백 스크린샷 | manual | — | manual-only |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_auth_check.py tests/test_cache.py tests/test_freeze_panes.py -x` (관련 모듈만)
- **Per wave merge:** `uv run pytest` (전체 200+ green)
- **Phase gate:** 전체 green + 수기 검증(실 실행 frozen panes 육안, 흑백 스크린샷 색 구분) 후 `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_auth_check.py` — ping 성공/실패/예외흡수/조건부 (EXEC-05 ping)
- [ ] `tests/test_freeze_panes.py` — openpyxl 읽기 회귀 (OUT-04)
- [ ] `tests/test_color_tone.py` — WCAG 휘도 구분 (COLOR-07/SC4)
- [ ] `tests/test_cache.py` 확장 — `reset_cache_stats`/`get_cache_stats` (lock race 포함)
- [ ] `tests/test_smoke_n_tickers.py` 확장 — 요약 블록 로그 + ping skip 경로
- [ ] 신규 `io/auth_check.py` 모듈 (소스)

## Security Domain

> `security_enforcement` 키가 config에 없음 → 활성 간주. 단 이 phase는 신규 외부 입력·신규 데이터 소스가 없어 표면적이 작다.

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | 외부 API 키(.env)는 Phase 1~3에서 이미 처리. ping은 기존 키 읽기만 |
| V3 Session Management | no | 세션 개념 없음 (배치 스크립트) |
| V4 Access Control | no | 단일 사용자 로컬 도구 |
| V5 Input Validation | yes (간접) | ping 응답 파싱은 기존 `dart_client._parse_amount` try/except 패턴 재사용. ping이 외부 응답을 신뢰하지 않고 status/예외로만 판정 |
| V6 Cryptography | no | 직접 암호화 없음. HTTPS는 httpx/edgartools/opendartreader가 처리 |

### Known Threat Patterns for 이 phase

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| .env 키가 로그/요약 블록에 노출 | Information Disclosure | 요약 블록·경고 로그에 **API 키 원문 절대 출력 금지** — "DART 인증 실패"만, 키 값 미포함. `_auth_label`이 note에 키를 넣지 않게 검증 |
| ping 예외 메시지에 키/UA 누설 | Information Disclosure | `f"DART 인증 실패: {e}"`의 `e`가 키를 포함할 수 있음(opendartreader 내부) — 예외 문자열을 sanitize하거나 일반 사유로 치환 |
| ping이 EDGAR/DART에 과도 요청 | DoS (타인 서비스) | D-03 매 실행 1회 + throttle 데코레이터 경유 — 무시할 부하 |

> **Security 주의:** Pattern 1의 `f"...: {e}"` 예외 문자열이 OPENDART_API_KEY를 포함할 위험이 실재한다(opendartreader가 키를 URL에 넣음). planner는 ping 예외 사유를 **키 미포함 일반 메시지**로 치환하는 task를 포함할 것.

## Sources

### Primary (HIGH confidence)
- 코드베이스 직접 읽기 (grep + Read): `main_run.py`, `runner.py`, `cache.py`, `throttle.py`, `config.py`, `color_rules.py`, `writer.py`, `fundamentals.py`, `edgar_client.py`, `dart_client.py`, `market.py`, `market_kind.py`, `sheet_per_ticker.py:438`, `sheet_portfolio.py:303`, `main.py`, `tests/conftest.py`, `tests/test_smoke_n_tickers.py`, `pyproject.toml` — `[VERIFIED: codebase grep/read 2026-06-11]`
- `.planning/phases/04-quality-robustness/04-CONTEXT.md` — D-01~04 + 재량 4건
- `.planning/REQUIREMENTS.md` §OUT-04 §EXEC-04 §EXEC-05 §COLOR-07
- `.planning/STATE.md` — Phase 1~3 완료 상태, 200 passed, 색 팔레트 히스토리

### Secondary (MEDIUM confidence)
- XlsxWriter docs — `freeze_panes(row, col)` "첫 비고정 셀" 규약 `[CITED: xlsxwriter.readthedocs.io/worksheet.html]` (페이지 본문에 freeze_panes 항목 직접 노출 안 됨 — 일반 spreadsheet 규약 + 코드 동작으로 교차검증)

### Tertiary (LOW confidence)
- WCAG relative luminance 공식 (Pattern 4 휘도 테스트) — 표준 공개 공식, 임계값은 구현자 실측 필요 `[ASSUMED]`

## Metadata

**Confidence breakdown:**
- 기존 코드 통합 지점: HIGH — 모든 파일·라인 직접 읽기 검증
- ping 엔드포인트 선정: MEDIUM — 패턴은 명확하나 정확 엔드포인트는 실측 필요(재량 3)
- 색 톤 그레이스케일 구분: MEDIUM — 자동 휘도 테스트 설계 명확, 임계값은 실측
- 신규 의존성: HIGH — 0개 (pyproject.toml 검증)

**Research date:** 2026-06-11
**Valid until:** 2026-07-11 (코드베이스 안정, 외부 라이브러리 변동 없음 — 30일)
