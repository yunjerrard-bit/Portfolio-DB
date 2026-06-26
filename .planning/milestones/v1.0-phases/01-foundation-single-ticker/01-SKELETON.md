# Walking Skeleton — 표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트

**Phase:** 1
**Generated:** 2026-05-20

## Capability Proven End-to-End

> 사용자가 `tickers.txt`에 단일 미국 티커(`AAPL`) 한 줄을 적고 `uv run python main.py`를 실행하면, Yahoo Finance에서 실제 OHLCV를 받아 EMA·expanding σ를 계산하고, 정적 색 베이킹이 적용된 단일 시트 `output/portfolio_YYYYMMDD.xlsx`를 새로 생성한다. Core Value(중앙값 ± 표준편차 색 신호)가 실제 셀에 살아있음이 증명된다.

## Architectural Decisions

| Decision | Choice | Rationale |
|---|---|---|
| Runtime | Python 3.13.x | STACK.md 핀, curl_cffi/yfinance 휠 풀 지원 (D-06 context) |
| Dep manager | uv 0.5+ + `pyproject.toml` (hatchling backend) | `uv run python main.py` 한 줄 실행 (EXEC-01/02) |
| Project layout | `src/stocksig/{io,compute,output}/` 3 레이어 + `main.py` 엔트리포인트 | **D-01**. Phase 2/3/4가 모듈 추가만으로 확장 가능 |
| Market data | yfinance ≥0.2.66 + `curl_cffi.requests.Session(impersonate="chrome")` | **D-06** + MKTD-02. yfinance ≥0.2.60 세션 API 변경 |
| Retry policy | tenacity `wait_exponential(min=2, max=30) + wait_random(0,1) + stop_after_attempt(5) + retry_if_exception_type(YFRateLimitError)` | **D-06** |
| EMA | `pandas.ewm(span=N, adjust=False).mean()` (TradingView-호환) | COMP-01. pandas-ta 미사용 (2026 archive 예정) |
| Stoch / RSI | native pandas rolling + Wilder via `ewm(alpha=1/14, adjust=False)` | TECH-01/02. pandas-ta 미사용 |
| Stats window | `pandas.expanding().median() / .std()` (look-ahead-free) | COMP-04~06 |
| Color baking | XlsxWriter `Format` 객체 7개 + Enum lookup (per-cell 정적) | COLOR-01~07, TECH-06. **D-04** Material Design 800/900 + 100 |
| Initial-row safety | `median`/`std`가 NaN 또는 `std==0` → `SigmaBucket.DEFAULT` (기본색) | **D-02** |
| Output path | `output/portfolio_{YYYYMMDD}.xlsx`, 매 실행 새 파일, 같은 날 overwrite | OUT-01~03 |
| Logging | stdlib `logging`, 한국어, 포맷 `[LEVEL] YYYY-MM-DD HH:MM:SS \| TICKER \| msg`, `sys.stdout.reconfigure(encoding='utf-8')` | **D-05** |
| Tests | pytest 8.x + pytest-mock + openpyxl(검증용 dev dep) | VALIDATION.md, Sampling < 30s |
| Color palette source-of-truth | `compute/color_rules.py` 모듈 상수 (GREEN_800/900/100 등) | **D-04**, Phase 4 튜닝 단일 지점 |

## Stack Touched in Phase 1

- [x] **Project scaffold** — `pyproject.toml` (hatchling, src-layout), `uv add` 7 런타임 + 3 dev deps, `tests/`, `.gitignore`, `.env.example`, `tickers.txt`
- [x] **Input adapter** — `io/input.py` (`tickers.txt` 파싱·검증, 빈 파일 한국어 fail-fast)
- [x] **External data** — `io/market.py` 실제 yfinance + curl_cffi + tenacity (단일 티커 한 번)
- [x] **Pure computation** — EMA(12), 차이(12), 일변동(12), expanding med/std, Stoch Slow(14,3,3), RSI(14 Wilder)
- [x] **Pure decision logic** — `compute/color_rules.py` σ-bucket + Stoch/RSI bucket (NaN/0 분기 명시)
- [x] **Output sink** — `output/writer.py` Format 캐시 7개, `output/sheet_per_ticker.py` 1 시트 작성
- [x] **Entrypoint** — `main.py` argparse + orchestration + 한국어 로깅 + `sys.stdout` UTF-8 보장
- [x] **Local execution** — `uv run python main.py` 한 줄로 실제 .xlsx 생성 (Excel에서 열리면 성공)

## Out of Scope (Deferred to Later Slices)

> Phase 1 minimalism을 지키기 위해 명시적으로 deferred. 이 목록은 후속 phase가 Phase 1 결정을 재논의하지 않도록 잠금.

- 시트1 통합 포트폴리오 요약 시트, `PORT-*` 전체 → **Phase 2** (`output/summary_sheet.py`)
- sqlite OHLCV 캐시 24h TTL, MKTD-05/06 → **Phase 2** (`io/cache.py`)
- 토큰버킷 throttle + `ThreadPoolExecutor(max_workers=4)` 팬아웃, EXEC-03 → **Phase 2**
- 잘못된 형식 티커 워크북 비중단 처리 (INPUT-04), 한 티커 실패 격리 (MKTD-04), 부분 데이터 (<50%) 경고 (MKTD-06), "데이터 품질" 시트 (EXEC-04) → **Phase 2/4**
- EDGAR (edgartools) + DART (OpenDartReader) 실제 호출, PER/PEG/GPM/OPM, FUND-* → **Phase 3** (`io/fundamentals.py`)
- frozen panes 1~5행 (OUT-04) → **Phase 4**
- rich progress bar / 한국어 진행률 본격화 (EXEC-05) → **Phase 2~4**
- 파스텔 색 톤 그레이스케일 시각 검증 → **Phase 4**
- 같은 날 재실행 시 시간 suffix 또는 캐시 hit 처리 → **Phase 2** (overwrite로 충분)
- v2: 스케줄러, 백테스팅, 다중 timeframe, PERF 최적화 → **v2 milestone**

## Subsequent Slice Plan

각 후속 phase는 본 skeleton의 아키텍처 결정(레이어 구조, 색 정책, 출력 포맷, 의존성 핀)을 **변경하지 않고** vertical slice를 추가한다.

- **Phase 2:** N개 티커(최대 100) 스케일링 + 시트1 통합 포트폴리오 요약 시트 + sqlite OHLCV 캐시 + 토큰버킷 throttle. 모듈 추가만: `io/cache.py`, `output/summary_sheet.py`.
- **Phase 3:** EDGAR(미)/DART(한) 기본적 분석 데이터(PER/PEG/GPM/OPM) + 시트1에 컬럼 4개 + 데이터 소스 출처 표시. 모듈 추가만: `io/fundamentals.py`.
- **Phase 4:** "데이터 품질" 시트, frozen panes(1~5행), 한국어 진행 로그 본격화, 색상 톤 그레이스케일 시각 검증. 모듈 추가만: `output/quality_sheet.py`.
