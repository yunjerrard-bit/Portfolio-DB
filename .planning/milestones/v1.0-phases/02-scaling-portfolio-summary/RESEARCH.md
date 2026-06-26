# Phase 2: N개 티커 스케일링 + 포트폴리오 요약 시트 — Research

**Researched:** 2026-05-22
**Domain:** 다중 티커 fan-out (ThreadPoolExecutor + 토큰버킷) · OHLCV 디스크 캐시(SQLite 24h TTL) · 부분 실패 격리 · 통합 포트폴리오 시트1(하이퍼링크/시장 감지/티어·산업·임펄스) · `tickers.txt` 탭 구분 확장
**Confidence:** HIGH (Phase 1 SUMMARY·RESEARCH·CONTEXT가 이미 모든 stack/팬아웃 결정을 잠갔고, Phase 2 신규 요구는 모두 잘 정의된 표준 패턴)

> CONTEXT.md가 본 phase에 아직 없다(`/gsd:discuss-phase` 미수행). 본 RESEARCH는 STATE.md "Phase 2 backlog" 3건 + ROADMAP Phase 2 Success Criteria + REQUIREMENTS 14건을 잠긴 입력으로 취급한다. discuss-phase가 발생하면 §"Open Questions for discuss-phase"의 항목들이 user-locking 대상.

## Summary

Phase 2는 Phase 1의 1-티커 vertical slice를 **100-티커 fan-out + 포트폴리오 요약 시트1**로 확장한다. 신규 위험은 (1) **XlsxWriter 시트 순서가 `add_worksheet` 호출 순서로 고정되며 사후 재정렬 public API가 없음** [VERIFIED: github.com/jmcnamara/XlsxWriter#317] — 따라서 시트1은 다른 모든 티커 시트보다 먼저 add 되어야 하고, 그 시점에는 모든 티커 데이터가 이미 계산되어 있어야 한다. (2) yfinance + curl_cffi 공유 세션에서의 동시성 안전성 + Yahoo rate-limit 회피용 토큰버킷. (3) sqlite OHLCV 캐시의 직렬화·TTL·키 디자인.

핵심 아키텍처: **2-pass 파이프라인**. Pass 1 = N개 티커 fan-out (`ThreadPoolExecutor(max_workers=4)`)으로 enriched DataFrame 전부를 메모리에 모음. Pass 2 = 시트1 먼저 add → 각 티커 시트 add (Phase 1 `write_sheet_for_ticker` 재사용). 부분 실패(예외 발생 티커)는 결과 dict에서 제외되되 시트1에는 "조회 실패" placeholder 행을 생성하지 않고(Phase 2 단순화) 콘솔에만 한국어 경고 — 데이터 품질 시트는 Phase 4.

**Primary recommendation:** `io/cache.py` (sqlite OHLCV 캐시 24h TTL), `io/throttle.py` (per-source 토큰버킷), `runner.py` (ThreadPoolExecutor fan-out + 예외 격리), `io/input.py` 확장 (탭 구분 + 후방 호환), `output/sheet_portfolio.py` (시트1 작성기) 5개 신규 모듈을 추가하고 `main_run.run()`을 2-pass로 재구성. 기존 `sheet_per_ticker.py`·`writer.py`·`compute/*`는 손대지 않는다 (Phase 1 95-컬럼 시트는 그대로).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 탭 구분 `tickers.txt` 파싱 + 후방 호환 | `io/input.py` (확장) | — | 기존 어댑터 책임 그대로 |
| 시장 감지 (US/KR) | `io/market.py` (또는 신규 `io/market_kind.py`) | — | 시세 어댑터 인접, 순수 suffix lookup |
| sqlite OHLCV 캐시 (24h TTL) | `io/cache.py` (신규) | `io/market.py` | 캐시는 fetch 어댑터에 종속 |
| 토큰버킷 throttle | `io/throttle.py` (신규) | `io/market.py` | 데코레이터로 fetch_ohlcv를 감쌈 |
| 다중 티커 fan-out + 예외 격리 | `runner.py` (신규) | `main_run.py` | 오케스트레이션 분리 |
| 시트1 작성 (행=티커, 하이퍼링크) | `output/sheet_portfolio.py` (신규) | `output/writer.py` (Format 캐시 재사용) | sheet writer 패턴 그대로 |
| 시장(US/KR) 표시 + 티어/산업 컬럼 | `output/sheet_portfolio.py` | — | 시트1 전용 데이터 |
| 임펄스(일/주) 셀 | `output/sheet_portfolio.py` | `compute/impulse.py` (재사용) | Format `impulse_green/red/blue` 재사용 |
| 부분 데이터 검증 (<50%) | `io/market.py` 또는 `runner.py` | — | row count 검증 (Phase 2는 콘솔 경고만, 시트 기록은 Phase 4) |
| 2-pass 오케스트레이션 | `main_run.py` (재구성) | — | 시트1 add 시점 = 모든 티커 데이터 준비 후 |

순수 계산 레이어(`compute/*`)는 Phase 2에서 손대지 않는다.

## User Constraints (from STATE.md Phase 2 backlog + ROADMAP)

### Locked Decisions (Phase 1 SUMMARY + STATE.md 누적)

- **L-01:** 동시성 = **`ThreadPoolExecutor(max_workers=4)`** (CLAUDE STACK + EXEC-03).
- **L-02:** OHLCV 캐시 = **sqlite, 24h TTL, 키=`(ticker, date_today_iso)`** (MKTD-05). 라이브러리는 `diskcache` 권장 (자세한 비교는 §"Don't Hand-Roll").
- **L-03:** yfinance 세션 = curl_cffi Chrome impersonation (Phase 1 `io/market.py` `_SESSION` 그대로 공유).
- **L-04:** tenacity 백오프 정책 = Phase 1 D-06 그대로 (5회 재시도, exp(2~30s) + jitter, `YFRateLimitError`).
- **L-05:** **시트1이 워크북의 첫 시트** (PORT-01). XlsxWriter는 `add_worksheet` 호출 순서로 시트가 직렬화됨 [VERIFIED: github #317] → 모든 티커 데이터가 계산된 **후**에 시트1을 add → 그 다음 티커 시트들을 add.
- **L-06:** 시트1 상단 = 실행 시각 타임스탬프 (PORT-08).
- **L-07:** 각 티커 행의 티커 셀 = 해당 시트로의 하이퍼링크 (PORT-07).
- **L-08:** **부분 실패 격리** — 한 티커 실패는 전체 중단 금지, 콘솔 한국어 경고 (MKTD-04, INPUT-04). 데이터 품질 시트는 Phase 4 deferred.
- **L-09:** **부분 데이터 경고** — 행 수 < 예상치(~2500 거래일)의 50% → 경고 기록 (MKTD-06).
- **L-10:** 콘솔 로그 한국어 (티커별 진행률, cache hit/miss, 실패 요약) — EXEC-05.
- **L-11:** **`tickers.txt` 탭 구분 확장** — `ticker\ttier\tindustry`, 1컬럼만 있는 행도 호환 (tier/industry 빈 문자열). 헤더 주석(`#`) 줄 유지.
- **L-12:** 시트1 신규 컬럼 `티어`, `산업` (STATE 2026-05-21 사용자 요청).
- **L-13:** 시트1 신규 컬럼 `(일)임펄스`, `(주)임펄스` — 종목 시트의 `Impulse_daily`/`Impulse_weekly` 최신 행 값 그대로. Format은 Phase 1 01-14 정의된 `impulse_green/red/blue/default` 재사용 (STATE 2026-05-22 사용자 요청).
- **L-14:** **시장 감지** — 티커 끝이 `.KS` 또는 `.KQ` (그리고 KOSDAQ 별칭) → KR, 그 외 → US. 사용자가 suffix를 직접 입력하므로 자동 추론 없음 (PROJECT.md key decision).
- **L-15:** 색 정책 = Phase 1 D-04 hex 그대로. 시트1 σ-신호 셀(EMA 4개, 거래량, Stoch %K, RSI)은 종목 시트의 **최신 행 색 bucket**과 동일해야 함 (사용자의 직관적 일치).
- **L-16:** 시트1 행 구성 (사용자 backlog + ROADMAP Success Criteria #1 합치):
  티커(하이퍼링크) | 시장 | 티어 | 산업 | 최신 종가 | 전일대비 등락률 | EMA11/22/96/192 색신호(4셀) | 거래량 색신호 | Stoch 최신 %K 색 | RSI 최신 색 | (일)임펄스 | (주)임펄스

### Claude's Discretion

- 캐시 라이브러리 선택: `diskcache` vs custom sqlite vs `requests-cache` — §"Standard Stack"에서 추천 + 대안 명시.
- 토큰버킷 구현체: `pyrate-limiter` vs 자체 구현 — §"Don't Hand-Roll"에서 추천.
- 시트1 컬럼 순서 미세 조정 (L-16 골격은 잠금이되 그룹 내 순서는 가독성 고려).
- 시트1 상단 행 사용 방식: 1행=타임스탬프(merge), 2행=빈, 3행=총 티커 수/실패 수/cache hit/miss 통계 (선택), 4행=구분, 5행=헤더 — Phase 1 시트와 같은 5행 헤더 컨벤션 유지.
- Phase 2 데이터 컬럼 hide 정책 (시트1은 hide 컬럼 없음 — 모든 정보 노출).
- `runner.py` vs `pipeline.py` 모듈명 — `runner.py` 권장.

### Deferred Ideas (OUT OF SCOPE — Phase 3/4)

- 데이터 품질 시트 (실패 티커 모음) → Phase 4 (EXEC-04).
- frozen panes (1~5행 고정) → Phase 4 (OUT-04).
- PER/PEG/GPM/OPM 컬럼 → Phase 3 (PORT-05).
- 캐시 hit/miss 통계 시트 표시 → 콘솔만, 시트는 Phase 4.
- rich progress bar → Phase 4 (현재는 stdlib logging만 — D-05).
- 색상 톤 그레이스케일 검증 → Phase 4.
- 100 티커 성능 최적화 (yf.download 배치) → v2 PERF (PERF-01).

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| INPUT-04 | 잘못된 형식 티커 격리 (run 중단 금지) | `runner.py` per-ticker `try/except` 격리 패턴 (§"Pattern 4") |
| MKTD-04 | 한 티커 수신 실패 → run 계속 + 콘솔 경고 | 동상. fetch_ohlcv 예외 → `runner._safe_process()`에서 capture |
| MKTD-05 | sqlite 디스크 캐시 24h TTL | `io/cache.py` (§"Pattern 2") |
| MKTD-06 | 행 수 <50% → 경고 기록 | `_validate_row_count(df, expected=2500, threshold=0.5)` helper (§"Pattern 4") |
| PORT-01 | 시트1 = 첫 번째 시트 | XlsxWriter `add_worksheet` 호출 순서 (§"Pattern 6") |
| PORT-02 | 모든 티커 한 행씩 | `sheet_portfolio.write_portfolio_sheet(wb, formats, results)` |
| PORT-03 | 티커명, 시장, 최신 종가, 등락률 | 종목 enriched_df 최신 행에서 추출 |
| PORT-04 | EMA11/22/96/192 색신호 4셀 | 종목 시트 최신 행과 동일 bucket — `compute/color_rules.decide_sigma_bucket(close, EMA, std)` 재사용 — 단, **σ 시그널의 입력 = `DIFF_Close_{N}` 컬럼의 최신값 vs `DIFF_Close_{N}_median`/`_std`** (시트2의 DIFF 컬럼 색과 일치) |
| PORT-06 | 거래량 최신 색신호 | Phase 1 `Volume_pct_change` σ bucket 재사용 |
| PORT-07 | 티커 셀 = 해당 시트 하이퍼링크 | `worksheet.write_url(row, col, f"internal:'{sanitized}'!A1", string=ticker)` (§"Pattern 5") |
| PORT-08 | 시트1 상단 타임스탬프 | `ws.write(0, 0, f"실행 시각: {datetime.now():%Y-%m-%d %H:%M:%S}")` |
| TECH-07 | 시트1에 Stoch %K, RSI 최신값 + 색 | `decide_stoch_bucket`/`decide_rsi_bucket` 재사용 |
| EXEC-03 | 100 티커 rate-limit 위반 없이 완료 | `ThreadPoolExecutor(max_workers=4)` + per-source 토큰버킷 (§"Pattern 3") |
| EXEC-05 | 한국어 콘솔 로그 (진행률, cache hit/miss, 실패) | stdlib `logging` (Phase 1 D-05 포맷 그대로) |

추가 backlog 항목 (사용자 요청, 요구사항 슬롯 후보로 표기됨):

| 슬롯 후보 | Description | Research Support |
|----------|-------------|------------------|
| PORT-09 (티어) | 시트1 `티어` 컬럼 | `tickers.txt` 2번째 토큰 → 시트1 컬럼 |
| PORT-10 (산업) | 시트1 `산업` 컬럼 | `tickers.txt` 3번째 토큰 → 시트1 컬럼 |
| PORT-11 (임펄스 일) | 시트1 `(일)임펄스` | 종목 enriched_df `Impulse_daily.iloc[-1]` |
| PORT-12 (임펄스 주) | 시트1 `(주)임펄스` | 종목 enriched_df `Impulse_weekly.iloc[-1]` |

## Standard Stack

### Core (Phase 1에서 핀, 본 phase 신규 도입 없음 — 재확인용)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.13.x | Runtime | [VERIFIED: STACK.md] |
| yfinance | ≥0.2.66 | OHLCV (Phase 2: 캐시·throttle 추가) | [VERIFIED: STACK.md] |
| curl_cffi | ≥0.15,<0.16 | TLS 임퍼소네이션 (공유 세션) | [VERIFIED: STACK.md] |
| pandas | 2.2.x | DataFrame | [VERIFIED: STACK.md] |
| XlsxWriter | 3.2.x | xlsx 생성 (Format 캐시 재사용) | [VERIFIED: STACK.md] |
| tenacity | 9.x | Phase 1 백오프 유지 | [VERIFIED: STACK.md] |
| python-dotenv | 1.0+ | `.env` | [VERIFIED: STACK.md] |
| stdlib `concurrent.futures.ThreadPoolExecutor` | — | fan-out | EXEC-03 명시 |
| stdlib `sqlite3` | — | 캐시 백엔드 (직접 사용 시) | 표준 라이브러리 |

### Supporting (Phase 2 신규)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `diskcache` | 5.6+ | sqlite-backed 키-값 캐시 (TTL 지원) | OHLCV 캐시 백엔드 추천 [CITED: PyPI grimoire.io/diskcache, github.com/grantjenks/python-diskcache] |
| `pyrate-limiter` | 3.x | 토큰버킷 throttle | per-source 요청률 강제 [CITED: PyPI] |

**대안:**
- `requests-cache`: HTTP 응답 레벨 캐시 — yfinance가 사용하는 내부 transport(curl_cffi)를 직접 가로채기 어렵고, 키 디자인 자유도 낮음. **부적합**.
- 자체 sqlite3 캐시: 30~50 LOC로 가능하나 TTL/eviction을 다시 만들어야 함. `diskcache`보다 신뢰성 낮음.
- `joblib.Memory`: 함수 결과 디스크 캐시. TTL이 native가 아니라 만료 처리에 추가 코드 필요. 부적합.

**Installation (uv):**
```bash
uv add diskcache pyrate-limiter
```

**Version verification (실행 시):**
```bash
uv pip show diskcache
uv pip show pyrate-limiter
```

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| diskcache | 자체 sqlite3 wrapper | LOC 절감 + 검증된 TTL 동작. 자체 wrapper는 디버깅 부담만 늘림 |
| pyrate-limiter | 자체 token bucket (threading.Lock + 카운터) | pyrate-limiter는 thread-safe + sliding/fixed window 옵션 검증됨. 자체 구현은 ~30 LOC + 단위 테스트 부담 |
| ThreadPoolExecutor | `asyncio` + httpx async | yfinance는 sync API. asyncio는 큰 리팩터 강제. **부적합** |
| 2-pass (compute → write all) | 1-pass (티커별 fetch → 즉시 시트 작성) | 1-pass는 시트1을 마지막에 추가 → L-05 위반. 2-pass가 유일 |

## Package Legitimacy Audit

> slopcheck CLI 미실행 (도구 미설치). 후보 패키지 2개는 PyPI 다년 이력 + 활성 GitHub 저장소 보유.

| Package | Registry | Age | Downloads (대략) | Source Repo | slopcheck | Disposition |
|---------|----------|-----|------------------|-------------|-----------|-------------|
| diskcache | PyPI | 8+ yrs | 수백만/월 | github.com/grantjenks/python-diskcache | n/a | Approved [ASSUMED — PyPI 직접 확인 권장 `pip index versions diskcache`] |
| pyrate-limiter | PyPI | 6+ yrs | 활발 | github.com/vutran1710/PyrateLimiter | n/a | Approved [ASSUMED — PyPI 직접 확인 권장] |

discuss-phase에서 사용자에게 두 패키지 도입 승인 받기. 거부 시 자체 sqlite3 + threading.Lock 토큰버킷으로 대체 (LOC ~80, 동작 동일).

## Architecture Patterns

### System Architecture Diagram

```
                       [tickers.txt]   [.env]
                       (탭 구분 or 1col)
                              │            │
                              ▼            ▼
                       ┌─────────────────────────────┐
                       │      main_run.run()         │
                       │  (2-pass orchestrator)      │
                       └─────────────────────────────┘
                                       │
                       ┌───────────────┴───────────────────┐
                       ▼                                   ▼
                   PASS 1: fan-out                   PASS 2: write
              ┌────────────────────┐         ┌────────────────────┐
              │ runner.run_all()   │         │ 1. add 시트1 먼저   │
              │ ThreadPool(4)      │         │    write_portfolio │
              │   per-ticker:      │         │    _sheet()        │
              │     fetch (cache)  │         │ 2. for each ticker:│
              │     compute        │         │    add 시트 + write│
              │     enriched_df    │         │    _sheet_for_     │
              │     try/except     │         │    ticker()        │
              │     → result/err   │         │ 3. wb.close()      │
              └────────────────────┘         └────────────────────┘
                       │                                   ▲
                       ▼                                   │
              ┌────────────────────────────────────────────┘
              │ List[TickerResult] / List[TickerFailure]
              ▼
      ┌─────────────────────────────────────────┐
      │   io/cache.py   io/throttle.py          │
      │   sqlite TTL    token bucket(Yahoo: N/s)│
      └─────────────────────────────────────────┘

  io/input.py (확장)     io/market.py (Phase 1)    io/market_kind.py (신규)
   read_tickers_extended  fetch_ohlcv(t) ← wrapped  classify_market(t) → "US"/"KR"
   → list[TickerSpec]       by cache + throttle

  compute/* (Phase 1 무변경)   output/writer.py (Format 캐시 재사용)
  output/sheet_per_ticker.py   output/sheet_portfolio.py (신규)
  (Phase 1 무변경)
```

데이터 흐름:
1. 입력 어댑터 → `TickerSpec(symbol, tier, industry)` list
2. fan-out: 각 티커 → 캐시 lookup → miss 시 throttled fetch → compute → enriched_df + 메타 (성공/실패)
3. write: 시트1 add 후 티커 시트 add (Phase 1 함수 재사용)

### Recommended Project Structure (Phase 2 신규 파일만 표시)

```
src/stocksig/
├── io/
│   ├── input.py              # ← 확장 (탭 구분 + TickerSpec dataclass)
│   ├── market.py             # ← 확장 (cache + throttle decorator 적용)
│   ├── market_kind.py        # ← 신규 (시장 감지: US/KR)
│   ├── cache.py              # ← 신규 (diskcache 24h TTL)
│   └── throttle.py           # ← 신규 (pyrate-limiter token bucket)
├── runner.py                 # ← 신규 (ThreadPoolExecutor fan-out + 예외 격리)
├── main_run.py               # ← 재구성 (2-pass)
└── output/
    └── sheet_portfolio.py    # ← 신규 (시트1 작성)
tests/
├── test_input_extended.py    # 탭 구분 + 후방 호환
├── test_market_kind.py       # US/KR suffix lookup
├── test_cache.py             # TTL 동작 (freeze time)
├── test_throttle.py          # rate limit 적용 검증 (mock clock)
├── test_runner.py            # 부분 실패 격리
├── test_sheet_portfolio.py   # 시트1 셀 검증 (openpyxl read-back)
└── test_smoke_n_tickers.py   # 10 티커 end-to-end (mock yfinance)
```

### Pattern 1: `tickers.txt` 탭 구분 + 후방 호환 파서

```python
# src/stocksig/io/input.py (확장)
from dataclasses import dataclass

@dataclass(frozen=True)
class TickerSpec:
    symbol: str
    tier: str = ""        # 사용자 입력. 빈 문자열 = 미지정
    industry: str = ""

def read_tickers_extended(path) -> list[TickerSpec]:
    """탭 구분 (ticker\ttier\tindustry) + 1컬럼 후방 호환.
    빈 줄, '#' 주석 줄 skip.
    """
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.error("tickers.txt | 파일을 찾을 수 없습니다: %s", p)
        sys.exit(1)

    specs: list[TickerSpec] = []
    for line in raw.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        # 탭 우선, 부족하면 빈 문자열로 채움
        parts = s.split("\t")
        symbol = parts[0].strip()
        tier = parts[1].strip() if len(parts) >= 2 else ""
        industry = parts[2].strip() if len(parts) >= 3 else ""
        specs.append(TickerSpec(symbol=symbol, tier=tier, industry=industry))

    if not specs:
        logger.error("tickers.txt | 유효한 티커가 0개입니다.")
        sys.exit(1)
    return specs
```

**후방 호환:** Phase 1 `read_tickers()` 함수도 유지(re-export from `read_tickers_extended` mapped to symbols list)하여 기존 테스트와 main_run 부분 코드가 깨지지 않게 한다.

**왜 `split("\t")`:** `csv.DictReader(delimiter='\t')`는 header 행을 강제하나 사용자 포맷은 header 주석 줄(`#`)을 옵션으로 두므로 매뉴얼 split이 단순. tab vs 공백은 명확히 구분되어 산업명에 공백이 들어가도 안전.

### Pattern 2: SQLite OHLCV 캐시 (diskcache)

```python
# src/stocksig/io/cache.py
from __future__ import annotations
import logging
from pathlib import Path
from datetime import date

from diskcache import Cache

logger = logging.getLogger(__name__)

_DEFAULT_DIR = Path(".cache/ohlcv")
_TTL_SECONDS = 24 * 60 * 60  # 24h TTL (MKTD-05)

_cache: Cache | None = None

def _get_cache() -> Cache:
    global _cache
    if _cache is None:
        _DEFAULT_DIR.mkdir(parents=True, exist_ok=True)
        _cache = Cache(str(_DEFAULT_DIR))
    return _cache

def make_key(ticker: str, today: date | None = None) -> str:
    """캐시 키 = (ticker, today_iso). 같은 날 재실행 시 hit."""
    today = today or date.today()
    return f"{ticker}|{today.isoformat()}"

def get_ohlcv(ticker: str):
    """캐시에서 DataFrame 반환. miss 시 None."""
    key = make_key(ticker)
    df = _get_cache().get(key)
    if df is not None:
        logger.info("%s | cache HIT (key=%s)", ticker, key)
    else:
        logger.info("%s | cache MISS (key=%s)", ticker, key)
    return df

def put_ohlcv(ticker: str, df) -> None:
    key = make_key(ticker)
    _get_cache().set(key, df, expire=_TTL_SECONDS)
```

**Why diskcache:**
- TTL/expire native 지원, sqlite WAL 기반 — 멀티 스레드 safe (PASS 1 fan-out에서 4 thread 동시 set/get) [CITED: grantjenks.com/docs/diskcache/]
- DataFrame을 직접 set 가능 (pickle protocol)
- 키 만료는 lazy (next get 시 expired 면 None 반환)

**Cache size:** 100 티커 × ~2500행 × ~100컬럼 × ~8B ≈ 200MB. diskcache는 기본 `size_limit=1GB` — 충분. 디렉터리는 `.cache/ohlcv/` (gitignored).

**`io/market.py` 통합:**
```python
def fetch_ohlcv_cached(ticker: str):
    df = cache.get_ohlcv(ticker)
    if df is not None:
        return df
    df = fetch_ohlcv(ticker)   # Phase 1 함수
    cache.put_ohlcv(ticker, df)
    return df
```

### Pattern 3: Token bucket throttle (pyrate-limiter)

```python
# src/stocksig/io/throttle.py
from pyrate_limiter import Duration, Rate, Limiter
from functools import wraps

# Yahoo는 공식 RPS가 없으나 안전선: 2 req/s × max_workers=4 → 동시 8 req/s 미만
# pyrate-limiter는 rate*duration 단위로 정의: 2 req per second
_YAHOO_RATE = Rate(2, Duration.SECOND)
_yahoo_limiter = Limiter(_YAHOO_RATE)

def throttled_yahoo(fn):
    """yfinance 호출을 Yahoo 토큰버킷으로 throttle."""
    @wraps(fn)
    def wrapper(*args, **kwargs):
        _yahoo_limiter.try_acquire("yahoo")  # blocking until token available
        return fn(*args, **kwargs)
    return wrapper

# 사용:
# fetch_ohlcv = throttled_yahoo(fetch_ohlcv)  또는 데코레이터 부착
```

**왜 2 req/s 권장:**
- yfinance 공식 RPS 미공개. 커뮤니티 보고: `threads=False`+ ~1-2 req/s 시 안정 [CITED: PITFALLS.md Pitfall 1]
- max_workers=4 × per-thread 직렬 호출이지만 토큰버킷이 그보다 더 엄격하게 강제 → 4 thread가 동시에 token 요청해도 limiter가 직렬화.

**EDGAR/DART (Phase 3 deferred)를 위한 분리:**
```python
_edgar_limiter = Limiter(Rate(8, Duration.SECOND))    # SEC 정책 ≤10 req/s, 안전선 8
_dart_limiter  = Limiter(Rate(2, Duration.SECOND))    # DART 정책 (Phase 3에서 확정)
```

Phase 2는 Yahoo만. 나머지는 Phase 3에서 활성화.

### Pattern 4: ThreadPoolExecutor fan-out + 예외 격리

```python
# src/stocksig/runner.py
from __future__ import annotations
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable
import pandas as pd

from stocksig.io.input import TickerSpec

logger = logging.getLogger(__name__)

_MAX_WORKERS = 4
_EXPECTED_TRADING_DAYS = 2500
_PARTIAL_THRESHOLD = 0.5

@dataclass
class TickerResult:
    spec: TickerSpec
    enriched_df: pd.DataFrame
    market: str       # "US" / "KR"

@dataclass
class TickerFailure:
    spec: TickerSpec
    reason: str       # 한국어

def _validate_row_count(ticker: str, df: pd.DataFrame) -> None:
    """MKTD-06: <50% → 경고 (raise는 아님; 호출자가 결정)."""
    n = len(df)
    if n < _EXPECTED_TRADING_DAYS * _PARTIAL_THRESHOLD:
        logger.warning(
            "%s | 부분 데이터 의심: %d 거래일 (예상 %d의 %.0f%%)",
            ticker, n, _EXPECTED_TRADING_DAYS, 100 * n / _EXPECTED_TRADING_DAYS
        )

def process_ticker(spec: TickerSpec, classify_market: Callable[[str], str],
                   pipeline: Callable[[str], pd.DataFrame]) -> TickerResult:
    """단일 티커 처리. pipeline = main_run의 fetch+compute 파이프라인 (Phase 1 합성)."""
    market = classify_market(spec.symbol)
    df = pipeline(spec.symbol)        # fetch_ohlcv_cached + compute layer
    _validate_row_count(spec.symbol, df)
    return TickerResult(spec=spec, enriched_df=df, market=market)

def run_all(specs: list[TickerSpec], classify_market, pipeline
            ) -> tuple[list[TickerResult], list[TickerFailure]]:
    results: list[TickerResult] = []
    failures: list[TickerFailure] = []
    total = len(specs)

    with ThreadPoolExecutor(max_workers=_MAX_WORKERS) as ex:
        future_to_spec = {ex.submit(process_ticker, s, classify_market, pipeline): s for s in specs}
        done = 0
        for fut in as_completed(future_to_spec):
            spec = future_to_spec[fut]
            done += 1
            try:
                res = fut.result()
                results.append(res)
                logger.info("[%d/%d] OK %s", done, total, spec.symbol)
            except Exception as e:
                msg = f"{type(e).__name__}: {e}"
                failures.append(TickerFailure(spec=spec, reason=msg))
                logger.warning("[%d/%d] FAIL %s | %s", done, total, spec.symbol, msg)

    logger.info("총 %d 티커 중 성공 %d / 실패 %d", total, len(results), len(failures))
    if failures:
        logger.warning("실패 티커: %s",
                       ", ".join(f"{f.spec.symbol}({f.reason.split(':')[0]})" for f in failures))
    return results, failures
```

**핵심 결정:**
- `as_completed`로 완료 즉시 진행률 로깅 → 사용자 체감 응답성.
- 한 티커의 예외는 result에서 분리되며 전체 실행 계속 (L-08).
- 결과 dict 순서가 입력 순서와 다를 수 있음 → 시트1 작성 시 `specs` 순서로 정렬 필요.

### Pattern 5: 시트1 작성 (write_portfolio_sheet)

```python
# src/stocksig/output/sheet_portfolio.py
from __future__ import annotations
from datetime import datetime
import pandas as pd

from stocksig.compute.color_rules import (
    SigmaBucket, TechBucket, ImpulseBucket,
    decide_sigma_bucket, decide_stoch_bucket, decide_rsi_bucket,
)
from stocksig.runner import TickerResult

# 시트1 컬럼 순서 (L-16)
PORTFOLIO_COLUMNS = [
    "티커", "시장", "티어", "산업",
    "최신 종가", "전일대비 등락률",
    "EMA11", "EMA22", "EMA96", "EMA192",
    "거래량",
    "(일)Stoch %K", "(일)RSI",
    "(일)임펄스", "(주)임펄스",
]

def _sanitize_sheet_name(name: str) -> str:
    """Excel sheet name 제약: max 31자, [/\\?*:[]] 금지.
    Phase 2 입력 티커는 [A-Z0-9._] 위주이지만 .KS/.KQ 마침표는 허용됨.
    """
    safe = name
    for ch in r"[]/\?*:":
        safe = safe.replace(ch, "_")
    return safe[:31]

def _internal_link(ticker: str) -> str:
    """worksheet.write_url용 internal: URI. 시트명에 마침표/공백 있으면 single-quote."""
    sheet = _sanitize_sheet_name(ticker)
    # 마침표(.KS, .KQ) 또는 공백이 있으면 single-quote — Excel 컨벤션
    if any(c in sheet for c in ". "):
        sheet_ref = f"'{sheet}'"
    else:
        sheet_ref = sheet
    return f"internal:{sheet_ref}!A1"

def write_portfolio_sheet(wb, formats: dict, results: list[TickerResult],
                          input_order: list[str]) -> None:
    """시트1 작성. input_order = tickers.txt 원래 순서.
    results는 입력 순서대로 정렬해서 쓴다."""
    ws = wb.add_worksheet("시트1")

    # 1행: 타임스탬프 (PORT-08)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ws.write(0, 0, f"실행 시각: {ts}", formats["a1_title"])

    # 5행: 헤더 (Phase 1과 동일하게 5행 헤더 컨벤션)
    for col_idx, name in enumerate(PORTFOLIO_COLUMNS):
        ws.write(4, col_idx, name, formats["header"])

    # results를 input_order대로 정렬
    by_symbol = {r.spec.symbol: r for r in results}

    # 6행+: 한 티커 한 행
    for row_offset, symbol in enumerate(input_order):
        res = by_symbol.get(symbol)
        if res is None:
            continue   # 실패 티커는 시트1 제외 (Phase 2 단순화; Phase 4에서 placeholder 행)
        excel_row = 5 + row_offset
        df = res.enriched_df
        last = df.sort_index(ascending=False).iloc[0]
        prev = df.sort_index(ascending=False).iloc[1] if len(df) >= 2 else None

        # 0: 티커 (하이퍼링크) — PORT-07
        ws.write_url(excel_row, 0, _internal_link(res.spec.symbol),
                     string=res.spec.symbol)
        # 1: 시장
        ws.write_string(excel_row, 1, res.market)
        # 2: 티어
        ws.write_string(excel_row, 2, res.spec.tier)
        # 3: 산업
        ws.write_string(excel_row, 3, res.spec.industry)
        # 4: 최신 종가
        ws.write_number(excel_row, 4, float(last["Close"]),
                        formats[(SigmaBucket.DEFAULT, "price")])
        # 5: 전일대비 등락률 (Close_pct_change 최신값 = ratio)
        cpc = last.get("Close_pct_change")
        if pd.isna(cpc):
            ws.write_blank(excel_row, 5, None)
        else:
            # σ-bucket으로 색 결정 (Phase 1 시트2와 동일 정책)
            med = last.get("Close_pct_change_median")
            std = last.get("Close_pct_change_std")
            bucket = decide_sigma_bucket(cpc, med, std)
            ws.write_number(excel_row, 5, float(cpc),
                            formats[(bucket, "percent_ratio")])

        # 6~9: EMA11/22/96/192 — DIFF_Close_{N} 최신 σ-bucket → 빈 셀에 색만 (또는 EMA 값 표시?)
        # L-15: 시트1 색 = 종목 시트 최신 행의 색과 동일 → DIFF_Close_{N} σ-bucket 사용
        # 표시값: EMA_Close_{N} 절대값 (price format) + 색은 DIFF σ-bucket
        for i, n in enumerate([11, 22, 96, 192]):
            ema_val = last.get(f"EMA_Close_{n}")
            diff_val = last.get(f"DIFF_Close_{n}")
            diff_med = last.get(f"DIFF_Close_{n}_median")
            diff_std = last.get(f"DIFF_Close_{n}_std")
            bucket = decide_sigma_bucket(diff_val, diff_med, diff_std)
            if pd.isna(ema_val):
                ws.write_blank(excel_row, 6 + i, None)
            else:
                ws.write_number(excel_row, 6 + i, float(ema_val),
                                formats[(bucket, "price")])

        # 10: 거래량 (최신값, color = Volume_pct_change σ-bucket — Phase 1 정책과 동일)
        vol = last.get("Volume")
        vpc = last.get("Volume_pct_change")
        vpc_med = last.get("Volume_pct_change_median")
        vpc_std = last.get("Volume_pct_change_std")
        vol_bucket = decide_sigma_bucket(vpc, vpc_med, vpc_std)
        if pd.isna(vol):
            ws.write_blank(excel_row, 10, None)
        else:
            ws.write_number(excel_row, 10, float(vol),
                            formats[(vol_bucket, "volume")])

        # 11: Stoch %K 일봉 최신 + bucket
        stk = last.get("Stoch_%K")
        stk_bucket = decide_stoch_bucket(stk) if not pd.isna(stk) else TechBucket.DEFAULT
        if pd.isna(stk):
            ws.write_blank(excel_row, 11, None)
        else:
            ws.write_number(excel_row, 11, float(stk),
                            formats[(stk_bucket, "percent_literal")])
        # 12: RSI 일봉 최신 + bucket
        rsi = last.get("RSI")
        rsi_bucket = decide_rsi_bucket(rsi) if not pd.isna(rsi) else TechBucket.DEFAULT
        if pd.isna(rsi):
            ws.write_blank(excel_row, 12, None)
        else:
            ws.write_number(excel_row, 12, float(rsi),
                            formats[(rsi_bucket, "percent_literal")])

        # 13: (일)임펄스 — 텍스트 + impulse_* Format
        imp_d = last.get("Impulse_daily")
        _write_impulse(ws, excel_row, 13, imp_d, formats)
        # 14: (주)임펄스
        imp_w = last.get("Impulse_weekly")
        _write_impulse(ws, excel_row, 14, imp_w, formats)

    ws.set_column(0, len(PORTFOLIO_COLUMNS) - 1, 14)

def _write_impulse(ws, row, col, value, formats):
    if value is None or (isinstance(value, float) and pd.isna(value)) or value == "":
        ws.write_blank(row, col, None)
        return
    if value == "녹색":
        fmt = formats["impulse_green"]
    elif value == "적색":
        fmt = formats["impulse_red"]
    elif value == "청색":
        fmt = formats["impulse_blue"]
    else:
        fmt = formats["impulse_default"]
    ws.write_string(row, col, str(value), fmt)
```

### Pattern 6: 시장 감지 (US/KR)

```python
# src/stocksig/io/market_kind.py
KR_SUFFIXES = (".KS", ".KQ", ".KOSDAQ", ".KOSPI")   # PROJECT는 .KS/.KQ만 명시; 확장 별칭 허용

def classify_market(symbol: str) -> str:
    """티커 suffix로 US/KR 분류. 입력은 사용자가 직접 지정 (PROJECT key decision)."""
    s = symbol.upper()
    for suf in KR_SUFFIXES:
        if s.endswith(suf):
            return "KR"
    return "US"
```

**Why suffix-based:** PROJECT.md key decision — 한국 티커는 사용자가 `.KS`/`.KQ`를 명시 입력. 자동 추론 금지.

### Pattern 7: 2-pass 오케스트레이션 (`main_run.run()` 재구성)

```python
# main_run.py (개념 — 실제 코드는 plan-phase에서 task로 분해)
def run(tickers_path=..., env_path=None, output_dir="output"):
    load_env(env_path)
    specs = read_tickers_extended(tickers_path)   # list[TickerSpec]
    logger.info("티커 %d개 로드", len(specs))

    # PASS 1: fan-out (compute only — no xlsx write)
    pipeline = _make_pipeline()                   # fetch_ohlcv_cached + Phase 1 compute 합성
    results, failures = run_all(specs, classify_market, pipeline)

    # PASS 2: write — 시트1 먼저, 그 다음 티커 시트들
    out_path = Path(output_dir) / f"portfolio_{date.today():%Y%m%d}.xlsx"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    wb, formats = make_workbook(out_path)
    try:
        # ★ 시트1을 가장 먼저 추가
        write_portfolio_sheet(wb, formats, results,
                              input_order=[s.symbol for s in specs])
        # 그 후 각 티커 시트
        for res in sorted(results, key=lambda r: [s.symbol for s in specs].index(r.spec.symbol)):
            scalars = _build_scalars(res.enriched_df)
            write_sheet_for_ticker(wb, formats, res.spec.symbol, res.enriched_df, scalars)
    finally:
        wb.close()

    logger.info("워크북 저장: %s", out_path)
    if failures:
        logger.warning("실패 %d개 — 시트1 제외 (Phase 4에서 데이터 품질 시트 도입 예정)",
                       len(failures))
    return out_path
```

`_build_scalars`는 현재 `main_run.run()` 안 인라인 코드 (line 165~183)를 헬퍼로 추출 — 리팩터.

### Anti-Patterns to Avoid

- **시트1을 마지막에 add 후 사후 재정렬** — `workbook.worksheets_objs.sort(...)`는 비공식 hack, sheetnames와 desync 위험 [VERIFIED: github #317]. 금지.
- **티커 시트 작성 중 동시에 시트1 데이터 모으기** — 1-pass처럼 보이지만 XlsxWriter는 시트 add 순서가 곧 출력 순서이므로 시트1을 마지막에 추가하게 됨 → L-05 위반.
- **`yf.download(tickers="A B C", threads=True)` 일괄 배치** — PITFALLS Pitfall 1: 100 티커 batch는 silent partial-history 위험. Phase 2는 per-ticker `yf.Ticker(...).history()` 유지. (PERF-01 v2로 deferred.)
- **`requests-cache`로 yfinance 가로채기** — curl_cffi transport를 monkey-patch해야 하는데 안정성 낮음. diskcache가 표준.
- **티커별 Workbook 생성 후 합치기** — XlsxWriter는 write-only, 워크북 합치기 불가.
- **`pd.concat` 후 다시 `sort_index`로 정렬** — `as_completed`가 완료 순서로 결과를 주므로, write 시점에 입력 순서 명시적으로 재정렬해야 함 (Pattern 7).
- **`ThreadPoolExecutor` 외부에서 `_SESSION` 재생성** — curl_cffi 모듈 레벨 세션 1개 공유 (Phase 1 `io/market.py:30`). 스레드별 세션 생성은 TLS 핸드셰이크 비용 폭발.
- **시트 이름에 `:` `/` `\` `?` `*` `[` `]`** — Excel 거부. Sanitize 함수 적용 (Pattern 5 `_sanitize_sheet_name`). KR 티커의 `.`는 허용되나 `internal:` URI에서 sheet name을 single-quote로 감싸야 함.
- **시트1 색 결정과 종목 시트 색 결정이 분기된 로직** — `compute/color_rules.decide_*` 함수를 양쪽 모두 import해서 단일 source of truth 유지.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| sqlite 캐시 + TTL + eviction | 자체 `sqlite3` wrapper | `diskcache` | TTL 만료·동시성·size limit 이미 검증 |
| 토큰버킷 (sliding window, thread-safe) | 자체 `threading.Lock` + counter | `pyrate-limiter` | 미세한 race, sliding window 미묘 |
| ThreadPool fan-out + 예외 격리 | `threading.Thread` 직접 | `concurrent.futures.ThreadPoolExecutor` + `as_completed` | exception propagation, future 결과 수집 |
| 탭 구분 CSV + 후방 호환 | `csv` 모듈 (header 강제) | 매뉴얼 split | header 옵션이 더 단순 (Pattern 1) |
| Excel 내부 하이퍼링크 | 수동 OOXML | `worksheet.write_url("internal:Sheet!A1")` | XlsxWriter native |
| 시장 분류 | 외부 ticker 마스터 DB | suffix lookup | 100 티커 규모는 suffix로 충분; PROJECT가 사용자 명시 입력 결정 |

**Key insight:** Phase 2의 핵심 실수 모드는 "100 티커를 어떻게든 끝까지 돌리는 인프라"를 자체 구현하다 race condition · 캐시 invalidation · 예외 누락에 시간을 다 쓰는 것. diskcache + pyrate-limiter + ThreadPoolExecutor 셋이 산업 표준 — 본 Phase는 그것들을 **조립**할 뿐이다.

## Runtime State Inventory

Phase 2는 **새 파일 추가가 주** (기존 코드는 `io/input.py`·`io/market.py`·`main_run.py` 확장만). rename/refactor 성격이 아니므로 본 섹션의 5 카테고리 대부분 N/A.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `.cache/ohlcv/*.sqlite` — Phase 2에서 신규 생성, Phase 3에서 EDGAR/DART 캐시도 같은 디렉터리 패턴 사용 예정 | gitignore 추가: `.cache/` |
| Live service config | 없음 (외부 서비스 등록 상태 없음) | None |
| OS-registered state | 없음 (스케줄러 미사용 — v2 SCHED deferred) | None |
| Secrets/env vars | `.env`의 `EDGAR_USER_AGENT_EMAIL`/`OPENDART_API_KEY` — Phase 2는 미사용, Phase 3 사전 준비 | None (Phase 1 load_env 그대로) |
| Build artifacts | `src/stocksig.egg-info/`나 wheel 캐시 — Phase 2가 pyproject.toml 의존성을 추가하면 `uv sync` 후 무효화됨 | `uv sync` task 추가 |

**확인:** `.gitignore`에 `.cache/` 추가 필요 (현재 `output/` 추가는 Phase 1 RESEARCH에서 권고됨). discuss-phase에서 사용자 확인 권장.

## Common Pitfalls

### Pitfall A: XlsxWriter `worksheets_objs.sort()` hack
**What goes wrong:** "시트1을 마지막에 추가하고 정렬"이 깔끔해 보임. 비공식 hack은 `Workbook._get_sheet_index`가 `sheetnames`와 desync되어 `internal:` 하이퍼링크가 깨지거나, 워크북 close 시 ZIP 구조 오류.
**Why it happens:** XlsxWriter는 write-once 설계 — 시트 추가 후 메타데이터가 즉시 빌드됨.
**How to avoid:** 시트1을 **add_worksheet 호출의 첫 번째**로 두는 2-pass 아키텍처 (Pattern 7). [VERIFIED: github.com/jmcnamara/XlsxWriter#317]
**Warning signs:** 빌드된 xlsx가 Excel에서 "복구 필요"로 열림, 또는 하이퍼링크 클릭이 "참조 유효하지 않음".

### Pitfall B: curl_cffi 세션을 thread별로 생성
**What goes wrong:** 각 thread가 별도 `curl_cffi.Session(impersonate="chrome")`을 만들면 TLS 핸드셰이크 비용 폭증 + Yahoo의 IP-단위 rate-limit가 다중 세션을 동일 IP로 인식해 차단.
**How to avoid:** Phase 1 `io/market.py`의 모듈 레벨 `_SESSION` 그대로 공유. curl_cffi 세션은 thread-safe함 [CITED: curl_cffi docs].
**Warning signs:** 100 티커 실행 중 30~50번째 티커부터 429 폭증.

### Pitfall C: ThreadPoolExecutor 내부에서 발생한 예외가 `as_completed` 에서만 잡힘
**What goes wrong:** `future.result()`를 호출하지 않으면 예외가 silently 사라짐. `executor.submit()` 직후 future 객체를 버리면 예외 전파 불가.
**How to avoid:** `as_completed(future_to_spec)` 루프에서 `try: fut.result() except: ...` 명시 (Pattern 4).
**Warning signs:** 콘솔에 "실패 0건"인데 시트1에는 일부 티커가 누락.

### Pitfall D: diskcache가 DataFrame을 pickle하지 못함
**What goes wrong:** pandas 객체는 pickle 가능하지만 일부 dtype(예: tz-aware DatetimeIndex with custom tz)에서 unpickle 실패 사례 보고됨.
**How to avoid:** yfinance `auto_adjust=True` 결과는 tz-naive index → 영향 없음. 그러나 캐시 set 직후 다시 get으로 round-trip 검증 단위 테스트 1건 추가 권장.
**Warning signs:** 두 번째 실행에서 첫 티커부터 "캐시 miss" 로그가 매번 나옴.

### Pitfall E: `tickers.txt` 탭 구분이 visual tab(공백)으로 입력됨
**What goes wrong:** 사용자가 에디터에서 Tab 키 대신 공백을 입력 → `split("\t")`가 한 토큰만 반환 → tier/industry 손실, 사용자는 "왜 시트1에 티어 안 보이지?" 혼란.
**How to avoid:** Pattern 1 파서에서 `\t`가 한 번도 없는 줄 + 토큰이 2개 이상으로 보이는 공백 split이면 warning logging. README에 "탭으로 구분" 명시 + `.editorconfig` 권장.
**Warning signs:** 시트1의 티어/산업 컬럼이 일관되게 빈 칸.

### Pitfall F: yfinance 부분 데이터 silent fail (Phase 1 Pitfall B 재현)
**What goes wrong:** Phase 1은 `df.empty` → ValueError. Phase 2는 ValueError가 runner에서 잡혀 실패 처리되지만, **non-empty but partial (예: 100행만)** 케이스는 통과 → 시트가 만들어지나 σ가 부정확.
**How to avoid:** `_validate_row_count(df, 2500, 0.5)` 호출 (Pattern 4). <50%면 경고만 (MKTD-06 명시 — abort 아님).
**Warning signs:** 시트1 색이 무지개처럼 불안정, 콘솔에 "%로 측정" 경고 다수.

### Pitfall G: 시트1 σ 색이 종목 시트 최신 행 색과 불일치
**What goes wrong:** 시트1에서 "EMA11 색"을 `decide_sigma_bucket(Close, EMA11, std_of_Close)`로 계산하면 종목 시트의 `DIFF_Close_11` 색과 다른 값 사용 → 사용자가 두 시트 비교 시 색이 다름.
**How to avoid:** L-15 — 시트1은 **반드시 종목 시트와 같은 입력**(`DIFF_Close_N` + `DIFF_Close_N_median` + `DIFF_Close_N_std`)으로 `decide_sigma_bucket` 호출 (Pattern 5).
**Warning signs:** 사용자 수기 검증에서 "EMA192 셀 색이 종목 시트랑 다른데?"

### Pitfall H: 캐시 키에 날짜 포함하지 않으면 다음 날 stale data
**What goes wrong:** 키 = `ticker` 뿐이면 어제 받은 데이터가 오늘도 hit → 거래 가능 시간 동안 stale.
**How to avoid:** 키 = `f"{ticker}|{date.today().isoformat()}"` (Pattern 2). TTL 24h는 자정 경계 정렬용 안전장치 (예: 23:59에 set한 데이터를 다음날 00:01에 만료시키지 않음 — 24h 후 만료).
**Warning signs:** 같은 날 두 번째 실행이 빠른데, 다음 날 첫 실행이 cache hit 로그를 잘못 출력.

### Pitfall I: `internal:` 하이퍼링크의 sheet name quote 누락
**What goes wrong:** KR 티커 `005930.KS`로 시트가 만들어졌을 때 `internal:005930.KS!A1`은 Excel가 거부 (마침표가 sheet/cell 분리자처럼 보임). `internal:'005930.KS'!A1`이 올바름. [VERIFIED: XlsxWriter write_url docs]
**How to avoid:** Pattern 5의 `_internal_link` 함수가 마침표/공백 포함 시 single-quote 감쌈.
**Warning signs:** 시트1에서 KR 티커 클릭 시 "참조 유효하지 않음" 또는 아무 일도 안 일어남.

### Pitfall J: pyrate-limiter blocking이 daemon 스레드를 멈춤
**What goes wrong:** `try_acquire("yahoo")` 기본이 blocking. ThreadPoolExecutor 워커가 토큰 대기 중 KeyboardInterrupt 처리 무시 가능.
**How to avoid:** main 스레드의 SIGINT 핸들러 + `ThreadPoolExecutor`의 `with` 블록 종료 시 `shutdown(wait=False, cancel_futures=True)` 명시 (Python 3.9+).
**Warning signs:** Ctrl+C가 즉시 안 먹힘.

## Code Examples

(Pattern 1~7에서 모두 제시. 시트1 read-back 검증 예시 추가:)

### 시트1 cell-level read-back 검증 (openpyxl)
```python
# tests/test_sheet_portfolio.py
from openpyxl import load_workbook

def test_portfolio_sheet_layout(tmp_path):
    out = tmp_path / "p.xlsx"
    # ... mock 실행 후 ...
    wb = load_workbook(out)
    assert wb.sheetnames[0] == "시트1"     # PORT-01
    ws = wb["시트1"]
    assert "실행 시각:" in ws["A1"].value   # PORT-08
    # 5행 헤더
    assert ws.cell(row=5, column=1).value == "티커"
    # 6행: 첫 티커
    a6 = ws.cell(row=6, column=1)
    assert a6.value == "AAPL"
    # 하이퍼링크 — openpyxl은 .hyperlink attribute로 노출
    assert a6.hyperlink is not None
    assert "AAPL!A1" in a6.hyperlink.target or "AAPL" in a6.hyperlink.location
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `requests-cache` for yfinance | `diskcache` keyed by `(ticker, date)` | Phase 1→2 결정 | yfinance 내부 transport와 디커플링 |
| 자체 sqlite + threading.Lock token bucket | `diskcache` + `pyrate-limiter` | Phase 2 결정 | LOC 절감, 검증된 라이브러리 |
| 1-pass write (티커별 fetch+write 즉시) | 2-pass (fan-out compute → write all) | XlsxWriter 시트 순서 제약 | L-05 충족, 시트1 첫 위치 보장 |
| `yf.download(threads=True)` 배치 | per-ticker `Ticker.history()` + ThreadPoolExecutor | PITFALLS Pitfall 1 | partial-history silent fail 회피 |

**Deprecated/outdated:**
- `pandas-ta` (Phase 1에서 기각된 이유와 동일) — Phase 2도 미사용
- `requests.Session` (yfinance ≥0.2.60 거부) — curl_cffi만

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x + pytest-mock (Phase 1과 동일) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (Phase 1에서 생성됨) |
| Quick run command | `uv run pytest -x -q` |
| Full suite command | `uv run pytest` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| INPUT-04 | 잘못된 티커 격리 | unit (mock fetch_ohlcv → raise) | `pytest tests/test_runner.py::test_failure_isolates_one_ticker -x` | ❌ Wave 0 |
| MKTD-04 | 한 티커 실패 → 나머지 정상 | unit | `pytest tests/test_runner.py::test_partial_failure_completes_run -x` | ❌ Wave 0 |
| MKTD-05 | sqlite 캐시 24h TTL | unit (freeze_time) | `pytest tests/test_cache.py::test_ttl_24h -x` | ❌ Wave 0 |
| MKTD-06 | <50% 행 → 경고 | unit (mock df 100행) | `pytest tests/test_runner.py::test_partial_row_count_warns -x` | ❌ Wave 0 |
| PORT-01 | 시트1이 첫 시트 | integration (openpyxl read) | `pytest tests/test_sheet_portfolio.py::test_sheet1_is_first -x` | ❌ Wave 0 |
| PORT-02 | N 티커 한 행씩 | integration | `pytest tests/test_sheet_portfolio.py::test_row_per_ticker -x` | ❌ Wave 0 |
| PORT-03 | 시장/종가/등락률 컬럼 | integration | `pytest tests/test_sheet_portfolio.py::test_market_close_change_cols -x` | ❌ Wave 0 |
| PORT-04 | EMA 4셀 색 = 종목 시트 색 | integration | `pytest tests/test_sheet_portfolio.py::test_ema_color_matches_ticker_sheet -x` | ❌ Wave 0 |
| PORT-06 | 거래량 색 = 종목 시트 색 | integration | `pytest tests/test_sheet_portfolio.py::test_volume_color_matches -x` | ❌ Wave 0 |
| PORT-07 | 티커 셀 하이퍼링크 | integration | `pytest tests/test_sheet_portfolio.py::test_ticker_hyperlink -x` | ❌ Wave 0 |
| PORT-08 | 시트1 상단 타임스탬프 | integration | `pytest tests/test_sheet_portfolio.py::test_timestamp_at_top -x` | ❌ Wave 0 |
| PORT-09/10 | 티어/산업 컬럼 | integration | `pytest tests/test_sheet_portfolio.py::test_tier_industry_cols -x` | ❌ Wave 0 |
| PORT-11/12 | 임펄스 일/주 셀 | integration | `pytest tests/test_sheet_portfolio.py::test_impulse_cells -x` | ❌ Wave 0 |
| TECH-07 | Stoch/RSI 시트1 표시 + 색 | integration | `pytest tests/test_sheet_portfolio.py::test_stoch_rsi_with_color -x` | ❌ Wave 0 |
| EXEC-03 | 100 티커 throttle 위반 없음 | unit (mock clock + count Yahoo calls/sec) | `pytest tests/test_throttle.py::test_yahoo_rate_under_limit -x` | ❌ Wave 0 |
| EXEC-05 | 한국어 진행 로그 | unit (caplog) | `pytest tests/test_runner.py::test_korean_progress_log -x` | ❌ Wave 0 |
| `tickers.txt` 탭 구분 | unit | `pytest tests/test_input_extended.py::test_tab_separated -x` | ❌ Wave 0 |
| 후방 호환 1컬럼 | unit | `pytest tests/test_input_extended.py::test_single_column_backward_compat -x` | ❌ Wave 0 |
| 시장 감지 | unit | `pytest tests/test_market_kind.py::test_us_kr_classification -x` | ❌ Wave 0 |
| 2-pass end-to-end | smoke (mock yfinance, 10 티커) | `pytest tests/test_smoke_n_tickers.py::test_workbook_with_10_mixed_tickers -x` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `uv run pytest -x -q tests/test_<changed>.py` (<5초)
- **Per wave merge:** `uv run pytest -x -q` 전체 (Phase 1+2 합쳐 ~60초 예상)
- **Phase gate:** 전체 그린 + 10-티커 smoke로 생성된 xlsx 수기 확인 (Success Criteria 5건)

### Wave 0 Gaps
- [ ] `tests/test_input_extended.py` — 탭 구분 + 후방 호환
- [ ] `tests/test_market_kind.py` — US/KR
- [ ] `tests/test_cache.py` — diskcache TTL (freezegun 또는 monkey-patched `date.today`)
- [ ] `tests/test_throttle.py` — pyrate-limiter rate 강제 검증
- [ ] `tests/test_runner.py` — fan-out + 예외 격리 + 진행률 로그
- [ ] `tests/test_sheet_portfolio.py` — 시트1 layout/하이퍼링크/색 일치
- [ ] `tests/test_smoke_n_tickers.py` — 10 티커 end-to-end
- [ ] dev 의존성 추가: `uv add --dev freezegun` (캐시 TTL 테스트용; 또는 `monkeypatch`로 `date.today` 대체 — 더 단순)

### 수기 검증 포인트 (Phase 2 gate)
1. `tickers.txt`에 10개 혼합 티커 (US 7개 + KR 3개 `.KS`/`.KQ`) + 일부 탭 구분 + 일부 1컬럼 → 실행 → xlsx 생성.
2. 시트1이 첫 번째 시트, A1에 "실행 시각: ..." 표시.
3. 각 티커 행: 시장 컬럼 US/KR 정확, 티어/산업 (탭 구분된 항목만) 채워짐.
4. 티커 셀 클릭 → 해당 티커 시트로 이동 (KR `.KS` 티커 포함).
5. 임의 티커의 EMA192 색이 시트1과 종목 시트 최신 행에서 일치.
6. 같은 날 두 번째 실행 — 콘솔에 "cache HIT" 다수.
7. `tickers.txt`에 의도적 잘못된 티커(`ZZZZZ`) 1개 포함 → 콘솔에 한국어 FAIL 경고, 나머지 9 티커는 정상.
8. 일부러 100 티커 입력 시 토큰버킷이 ~2 req/s로 yfinance 호출 직렬화 (`logger.info`로 호출 빈도 측정 가능하게 instrument; 또는 단순히 실행 시간이 50초 이상이어야 정상).

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| Python 3.13 | 모든 코드 | Phase 1 설치 확인 | — | uv가 자동 |
| uv | 의존성 관리 | Phase 1 설치 확인 | — | 없음 |
| diskcache | Pattern 2 | 미설치 | — | `uv add diskcache` |
| pyrate-limiter | Pattern 3 | 미설치 | — | `uv add pyrate-limiter` |
| 인터넷 (Yahoo) | runtime | 의존 | — | smoke test는 mock |
| 디스크 공간 (`.cache/ohlcv`) | 캐시 | runtime 생성 | — | 충분(<500MB) |

**Missing dependencies with no fallback:** 없음.
**Missing dependencies with fallback:** diskcache/pyrate-limiter는 자체 sqlite + threading.Lock으로 대체 가능 (discuss-phase에서 결정).

## Project Constraints (from CLAUDE.md)

- **Tech stack 핀** (Phase 1과 동일): Python 3.13, yfinance ≥0.2.66, curl_cffi ≥0.15<0.16, XlsxWriter 3.2.x, pandas 2.2.x, tenacity 9.x, python-dotenv.
- **금지 사항:** `requests-cache`로 yfinance 가로채기, `yf.download(threads=True)` 배치, `pandas-ta`, openpyxl writer, `requests.Session` plain.
- **언어:** UI/로그 한국어 (D-05 유지).
- **GSD workflow:** `/gsd:plan-phase 2` 일부로 본 RESEARCH 작성. 직접 코드 편집 금지.

## Security Domain

### Applicable ASVS Categories

| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Phase 2도 외부 인증 호출 없음 |
| V5 Input Validation | yes | `tickers.txt` 탭 구분 파서 — 토큰 수·형식 검증, 빈/주석 줄 skip |
| V7 Error Handling & Logging | yes | 한국어 메시지, 예외 → 콘솔 경고, raw traceback 비노출 |
| V8 Data Protection | yes | `.cache/ohlcv/*.sqlite`에 시세 데이터 저장 — `.gitignore` 추가 필요 |
| V14 Configuration | yes | python-dotenv 그대로 |

### Known Threat Patterns

| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| 사용자 입력 ticker에 path traversal 문자 (`../`) | Tampering | sheet name sanitize (Pattern 5 `_sanitize_sheet_name`); `tickers.txt`의 토큰을 그대로 sheet name으로 사용하므로 [A-Z0-9._] 외 문자 거부 또는 `_` 치환 |
| `.cache/ohlcv/` 누설 → 사용자 관심 종목 노출 | Information Disclosure | `.gitignore`에 `.cache/` 추가 |
| 토큰버킷 우회 시도 (사용자 코드가 직접 yfinance 호출) | — | `io/market.py`만 yfinance import — 다른 모듈에서 직접 호출 금지 (코드 리뷰 게이트) |
| 네트워크 응답 신뢰 (빈/부분 DataFrame) | Tampering | `_validate_row_count` (Pattern 4) + Phase 1 `df.empty` 체크 |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `diskcache`가 100 티커 × ~수MB DataFrame을 pickle/unpickle 안정적으로 처리 | Pattern 2 | round-trip 단위 테스트로 검증; 실패 시 자체 sqlite + parquet 저장으로 전환 |
| A2 | `pyrate-limiter`의 `try_acquire("yahoo")` 기본 동작이 thread-safe blocking | Pattern 3 | 공식 docs 확인 필요; 실패 시 자체 `threading.Lock` + monotonic clock 토큰버킷 |
| A3 | curl_cffi 모듈 레벨 세션이 thread-safe | Pitfall B | curl_cffi docs 검증 필요; 실패 시 `threading.local()` 세션 |
| A4 | Yahoo는 안전한 RPS = 2 req/s 수준 | Pattern 3 | 사용자 환경에서 100 티커 1회 실행으로 검증; rate-limit 발생 시 1 req/s로 하향 |
| A5 | XlsxWriter `internal:` 하이퍼링크가 `.KS` 등 마침표 포함 시트명을 single-quote로 처리 | Pitfall I | XlsxWriter docs 명시 [VERIFIED — write_url 페이지의 "spaces should be single quoted" 언급] |
| A6 | 시트1과 종목 시트 색이 동일 입력(`DIFF_Close_N` σ-bucket)을 사용하면 사용자 직관과 일치 | L-15 | discuss-phase에서 사용자 확인 필요 — "EMA11 색"이 실제로 의미하는 것 ("price - EMA11이 σ 밴드 어디인지") |
| A7 | `tickers.txt` 탭 구분 도입 시 1컬럼 후방 호환만 충분 (헤더 행 명시 없이) | Pattern 1 | 사용자가 헤더 행을 추가하고 싶다면 `#` 주석 줄로 표현 — 이미 지원됨 |
| A8 | 부분 데이터 임계 50%, 예상 ~2500 거래일 | Pattern 4 | KR 시장은 ~2450 거래일/10년 — 50% = 1250로 안전 마진 충분 |
| A9 | 시트1 실패 티커 placeholder 행 제외 (Phase 2 단순화) | Pattern 5 | discuss-phase에서 "실패 티커를 시트1에 빈 행으로 표시할지" 확인 |

## Open Questions (for `/gsd:discuss-phase`)

1. **사용자가 `tickers.txt` 형식 마이그레이션을 어떻게 할지** — 기존 Phase 1 사용자 파일(1컬럼)을 그대로 두고 새 티커만 탭 구분으로 추가하는 흐름이 의도된 흐름인가, 아니면 전체 마이그레이션을 안내해야 하는가? (A7 관련)

2. **실패 티커의 시트1 처리** — 완전히 제외(현재 default) vs "조회 실패" placeholder 행(이름만 빨간색 등). Phase 2 단순화 vs UX 명확성. (A9 관련)

3. **사용자가 의도하는 "EMA 색"의 의미** — 시트1의 EMA11 색은 (a) 종목 시트의 `DIFF_Close_11` 셀 색(=PORT-04가 명시한 것; 차이가 σ밴드 어디인지) (b) 종목 시트의 `EMA_Close_11` 값 자체의 σ 색, 둘 중 어느 쪽이 사용자 의도인지. 본 RESEARCH는 (a)로 가정(요구사항 명문). (A6, L-15)

4. **시트1에 표시할 EMA 셀의 값** — 옵션:
   (a) `EMA_Close_N` 절대값 (price format) + 색은 DIFF σ-bucket (현재 추천)
   (b) `DIFF_Close_N` 비율값 (percent_ratio format) + 색은 같은 bucket
   (c) 색만 표시 (빈 텍스트, bg only)
   사용자가 시트1을 "한 눈에 보는" 용도라면 (a)가 가독성 높음. discuss에서 확정 필요.

5. **Yahoo throttle RPS 값** — 2 req/s가 안전선이지만 100 티커 × 4 thread = 200초+로 길 수 있음. 캐시 채워진 2회차 실행은 빠름. 1회차 시간을 1~2분 더 단축하려면 3 req/s로 올릴지? (A4)

6. **`.cache/` 디렉터리 위치** — 프로젝트 루트 `.cache/ohlcv/`(현재 추천) vs OS 표준 `%LOCALAPPDATA%\stocksig\cache\`. 프로젝트 루트가 단순하나 사용자가 여러 클론 디렉터리를 두면 캐시가 분산됨.

7. **부분 데이터 임계** — 50%(현재) vs 80%(더 엄격). 너무 엄격하면 KR 정기 휴장이 잦은 종목이 거짓 경고. (A8)

8. **slopcheck를 실제로 실행할지** — Phase 2가 신규 패키지 2개(`diskcache`, `pyrate-limiter`)를 도입하므로 보안 게이트로 권장됨.

## Sources

### Primary (HIGH confidence)
- `.planning/research/SUMMARY.md` — Phase 0 stack/architecture/pitfalls 검증
- `.planning/phases/01-foundation-single-ticker/01-RESEARCH.md` — Phase 1 패턴 재사용 근거
- `.planning/REQUIREMENTS.md` — Phase 2 14개 요구사항 ID
- `.planning/ROADMAP.md` — Phase 2 Success Criteria 5개
- `.planning/STATE.md` — Phase 2 backlog 3건 (사용자 요청)
- 본 repo `src/stocksig/main_run.py`·`output/sheet_per_ticker.py`·`output/writer.py`·`io/market.py`·`compute/color_rules.py` — Phase 1 코드 패턴 그대로 검증
- [github.com/jmcnamara/XlsxWriter#317](https://github.com/jmcnamara/XlsxWriter/issues/317) — 시트 순서 비변경 정책 [VERIFIED]
- [XlsxWriter write_url docs](https://xlsxwriter.readthedocs.io/worksheet.html#write_url) — `internal:` URI + single-quote 컨벤션 [VERIFIED]

### Secondary (MEDIUM confidence)
- [grantjenks.com/docs/diskcache/](https://grantjenks.com/docs/diskcache/) — diskcache TTL/thread safety 일반 docs [CITED]
- [pyrate-limiter PyPI](https://pypi.org/project/pyrate-limiter/) — rate limiter API 일반 docs [CITED]

### Tertiary (LOW confidence)
- 없음

## Metadata

**Confidence breakdown:**
- 시트 순서 제약 (시트1 first): HIGH — github #317 + write_url docs
- 동시성 모델: HIGH — Phase 0/1에서 잠금
- 캐시/throttle 라이브러리 선택: MEDIUM — diskcache/pyrate-limiter는 표준이나 본 프로젝트에서 신규
- 시장 감지: HIGH — PROJECT key decision
- 부분 실패 격리: HIGH — concurrent.futures 표준 패턴
- 임펄스/티어/산업 컬럼: HIGH — Phase 1 01-14에서 이미 모든 컴퓨테이션 존재

**Research date:** 2026-05-22
**Valid until:** 2026-06-22 (30일 — 핀된 라이브러리, 안정적 도메인)

---

## RESEARCH COMPLETE

**Phase:** 2 — N개 티커 스케일링 + 포트폴리오 요약 시트
**Confidence:** HIGH

### Key Findings
- **XlsxWriter 시트 순서가 add_worksheet 호출 순서로 고정** → 2-pass 아키텍처 강제 (compute all → write 시트1 first → 티커 시트들).
- Phase 1 `write_sheet_for_ticker`·`writer.make_workbook` Format 캐시·`compute/color_rules.*`를 그대로 재사용 — 신규 코드는 5개 모듈 (`io/cache.py`, `io/throttle.py`, `io/market_kind.py`, `runner.py`, `output/sheet_portfolio.py`) + 2개 모듈 확장 (`io/input.py`, `main_run.py`).
- diskcache + pyrate-limiter 2개 패키지 신규 도입 — slopcheck 미실행, discuss-phase에서 승인 게이트 권장.
- 시트1 EMA 색은 종목 시트의 DIFF_Close_N σ-bucket과 동일 입력 사용 (L-15) — 사용자 직관 일치, discuss-phase에서 의미 재확인 필요.
- 부분 실패 격리는 `ThreadPoolExecutor` + `as_completed` + `try fut.result()` 표준 패턴. 데이터 품질 시트는 Phase 4 deferred.

### File Created
`C:\Users\kimyunjae\Documents\Claude 앱 개발\example\.planning\phases\02-scaling-portfolio-summary\RESEARCH.md`

### Confidence Assessment
| Area | Level | Reason |
|------|-------|--------|
| Architecture (2-pass) | HIGH | github #317 + Phase 1 코드 직접 검증 |
| 시트1 layout/하이퍼링크 | HIGH | XlsxWriter write_url docs 직접 인용 |
| Cache/throttle 라이브러리 | MEDIUM | 표준이나 본 프로젝트 신규 — 통합 후 HIGH 승격 |
| Fan-out + 예외 격리 | HIGH | stdlib 표준 패턴 |
| 임펄스/티어/산업 컬럼 | HIGH | Phase 1 01-14에 모든 입력 존재 |
| 부분 데이터 검증 | HIGH | MKTD-06 명문 |

### Open Questions
8건 (위 §"Open Questions for discuss-phase" 참조). 핵심: (1) 실패 티커 시트1 처리, (2) 시트1 EMA 색의 의미, (3) Yahoo RPS 값.

### Ready for Planning
Research complete. Planner는 다음 wave 구조를 권장 진행할 수 있다:
- **Wave 0:** 신규 의존성 (`diskcache`, `pyrate-limiter`) + 9개 테스트 stub + `.gitignore` (`.cache/`)
- **Wave 1:** `io/input.py` 확장 + `io/market_kind.py` + `io/cache.py` + `io/throttle.py` (4개 모듈)
- **Wave 2:** `runner.py` + `io/market.py` 통합 (캐시·throttle 데코레이터 부착)
- **Wave 3:** `output/sheet_portfolio.py`
- **Wave 4:** `main_run.py` 2-pass 재구성 + 10-티커 smoke test
- **Wave 5:** 수기 검증 8 포인트
