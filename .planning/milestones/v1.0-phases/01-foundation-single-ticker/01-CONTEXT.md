# Phase 1: 기반 + 단일 티커 수직 슬라이스 - Context

**Gathered:** 2026-05-20
**Status:** Ready for planning

<domain>
## Phase Boundary

단일 미국 티커 한 개에 대해 OHLCV 수신 → EMA/expanding-window 통계(중앙값·표준편차) → 정적 색 베이킹 → 단일 시트 `.xlsx` 출력까지의 vertical end-to-end 슬라이스. Core Value(중앙값±σ 색 신호)가 실제로 셀에 베이킹되어 살아있음을 증명한다.

**Phase 1 범위 안:**
- 입력: 단일 미국 티커가 적힌 `tickers.txt`, `.env` (EDGAR/DART 키 로드만, 실제 호출은 Phase 3)
- 시세: yfinance + curl_cffi(Chrome impersonation) + tenacity 재시도
- 계산: EMA11/22/96/192 (종/고/저 각각), 12개 차이 시리즈, EMA 일변동, expanding window 중앙값·표준편차, Stochastic Slow(14/3/3) — native, RSI(14, Wilder) — native
- 출력: `output/portfolio_YYYYMMDD.xlsx` 단일 시트 (시트명 = 티커), 정적 색 베이킹

**Phase 1 범위 밖 (다른 phase로):**
- 시트1 통합 포트폴리오 요약, 100 티커 팬아웃, sqlite 캐시, 토큰버킷 throttle → Phase 2
- EDGAR/DART 실제 호출, PER/PEG/GPM/OPM 컬럼 → Phase 3
- 데이터 품질 시트, frozen panes, 한국어 진행 로그 본격화, 색상 톤 시각 검증 → Phase 4

</domain>

<decisions>
## Implementation Decisions

### A. 프로젝트 구조
- **D-01:** 도메인 레이어 분리 — `src/stocksig/{io,compute,output}/` 3 레이어 구조 채택.
  ```
  example/
  ├── main.py                  # 엔트리포인트만 (argparse, orchestration)
  ├── pyproject.toml
  ├── .env.example
  ├── tickers.txt
  ├── src/
  │   └── stocksig/
  │       ├── __init__.py
  │       ├── config.py        # .env, 상수
  │       ├── io/
  │       │   ├── input.py     # tickers.txt 읽기·검증
  │       │   └── market.py    # yfinance + curl_cffi + tenacity
  │       ├── compute/
  │       │   ├── ema.py       # pandas.ewm 4개 EMA + 차이/일변동
  │       │   ├── stats.py     # expanding window median/std
  │       │   ├── indicators.py # Stoch Slow + RSI (native)
  │       │   └── color_rules.py # σ-신호 + Stoch/RSI 색 결정 로직
  │       └── output/
  │           ├── writer.py    # XlsxWriter 워크북 라이프사이클
  │           └── sheet_per_ticker.py # 시트 1개 작성
  └── tests/
  ```
- **Why:** Phase 2(시트1 요약·캐시), Phase 3(EDGAR/DART), Phase 4(품질 시트)가 모두 같은 3 레이어에 자연스럽게 매핑됨. Phase 2 진입 시 `io/cache.py`, `io/fundamentals.py`, `output/summary_sheet.py`, `output/quality_sheet.py` 등 **모듈 추가만** 하면 됨 — 리팩토링 비용 회피.

### D. expanding window 초기 행 색 처리
- **D-02:** 누적 표본 부족으로 expanding `median`/`std`가 NaN이거나 불안정한 초기 행에서는 **색 베이킹을 적용하지 않고 기본 글자색·배경색으로 표시**한다.
- **Why:** 별도 minimum-sample threshold나 명시적 마커를 두면 시각적 노이즈 증가. 기본색이면 사용자가 "아직 신호 없음"으로 자연스럽게 해석 가능.
- **How to apply:** `color_rules.py`에서 입력 `median`/`std`가 NaN이거나 `0`인 경우 `None`(또는 default Format)을 반환. writer는 그 행에 대해 색 인자를 적용하지 않음.

### Claude's Discretion (사용자가 기본값 위임)

#### B. 시트 열 배치/그룹 순서
- **D-03:** 좌→우 순서 (5행 = 한국어 헤더, 6행부터 데이터):
  1. **날짜**
  2. **원천 OHLCV 그룹**: `종가` → `종가_일별중앙값` → `종가_일별표준편차` → `고가` → ... → `거래량` → `거래량_일별중앙값` → `거래량_일별표준편차` (각 데이터 열 우측에 즉시 med/std 배치 — SHEET-08 충족)
  3. **1차 EMA 그룹**: 종가 EMA11/22/96/192 → 고가 EMA11/22/96/192 → 저가 EMA11/22/96/192 (각 옆에 med/std)
  4. **2차 차이 그룹**: (종가-EMA11, 종가-EMA22, …, 저가-EMA192) 총 12 시리즈 (각 옆에 med/std)
  5. **2차 EMA 일변동 그룹**: EMA11/22/96/192의 일별 차분 × 종/고/저 = 12 시리즈 (각 옆에 med/std)
  6. **기술적 지표 그룹**: `Stoch %K` → `Stoch %D` → `RSI` (별도 med/std 없음 — 임계값 기반 색)
- **Why:** SHEET-07의 "원천→1차→2차" 그룹화 + SHEET-08의 "각 데이터 열 옆에 med/std 인접" 둘 다 만족. 색을 한 눈에 비교하기 좋음.
- **Note:** 시트가 매우 넓어진다 (수십 열). Phase 4의 frozen panes(1~5행)가 도입되면 가독성 보완됨. Planner는 컬럼 인덱스 매핑 표를 별도 산출할 것.

#### C. 파스텔 색 톤 (구체 hex)
- **D-04:** Material Design 팔레트 기반 4색 정책 (그레이스케일 인쇄에서도 명도 차 확보):

  | 신호 | 글자색 (font) | 배경색 (fill) |
  |---|---|---|
  | 1σ < 값 ≤ 2σ 미만 (-) 매수 시그널 | `#2E7D32` (Green 800) | 기본 (없음) |
  | 1σ < 값 ≤ 2σ 미만 (+) 과열 시그널 | `#C62828` (Red 800) | 기본 (없음) |
  | 값 < 중앙값 − 2σ (강한 매수) | `#1B5E20` (Green 900) | `#C8E6C9` (Green 100, 파스텔 민트) |
  | 값 > 중앙값 + 2σ (강한 과열) | `#B71C1C` (Red 900) | `#FFCDD2` (Red 100, 파스텔 핑크) |
  | Stoch ≤20 / RSI ≤30 | `#2E7D32` | 기본 |
  | Stoch ≥80 / RSI ≥70 | `#C62828` | 기본 |
  | 기본 | `#000000` | 기본 |

- **Why:** Material 800/900 = 흰 배경에서 가독성 좋고 흑백 인쇄 시 충분히 어두움. 100 계열 배경 = 충분히 옅어 "강렬하지 않은 파스텔" 요건(COLOR-07) 충족.
- **Note:** Phase 4에서 시각 검증(그레이스케일 스크린샷 테스트)에 따라 톤이 조정될 수 있음 — 색상 상수는 `compute/color_rules.py`의 모듈 상수로 노출해 한 곳에서 튜닝 가능하게 한다.

#### E. 로깅 도구
- **D-05:** Phase 1은 **stdlib `logging`** 사용. 한국어 메시지 포맷:
  ```
  [INFO] 2026-05-20 14:23:01 | AAPL | OHLCV 수신 시작 (start=2015-05-21, end=2026-05-20)
  [INFO] 2026-05-20 14:23:03 | AAPL | OHLCV 2498 거래일 수신 완료
  [ERROR] 2026-05-20 14:23:05 | tickers.txt 파일이 비어있습니다.
  ```
- **Why:** Phase 1 단일 티커에는 progress bar가 불필요. stdlib는 zero-dep, Phase 2에서 100 티커 진행률 시각화가 필요해지면 `rich.progress`를 `output/` 또는 별도 `cli/` 모듈에서 도입(StreamHandler와 공존 가능). `loguru`는 stdlib와 의도 중복이라 미채택.
- **How to apply:** `main.py`에서 `logging.basicConfig(level=INFO, format=..., encoding='utf-8')` 설정. Windows 콘솔 한국어 출력은 `PYTHONIOENCODING=utf-8` 보장 필요 시 `main.py`에서 `sys.stdout.reconfigure(encoding='utf-8')` 추가.

#### F. OHLCV 수신 기간 인자
- **D-06:** `yfinance.Ticker(ticker).history(start=today - timedelta(days=4000), end=today, auto_adjust=True)` 사용. `period="max"` 미사용.
- **Why:** MKTD-01이 "today() − 4000 calendar days" 명시. `period="max"`는 결정적이지 않고(상장일에 따라 가변), 캐시 키 일관성도 깨짐. `auto_adjust=True`는 분할/배당 조정가 사용(σ 계산에서 점프 회피).
- **How to apply:** `io/market.py`의 `fetch_ohlcv(ticker: str) -> pd.DataFrame` 시그니처 고정. tenacity 데코레이터로 `wait_exponential(multiplier=1, min=2, max=30) + wait_random(0,1) + stop_after_attempt(5) + retry_if_exception_type(YFRateLimitError)`.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 프로젝트 정의 & 요구사항
- `.planning/PROJECT.md` — Core Value, 사용자 정의, 제약(스택·언어·성능)
- `.planning/REQUIREMENTS.md` §INPUT, §MKTD, §COMP, §SHEET, §TECH, §COLOR, §OUT, §EXEC — Phase 1 범위 39개 요구사항 (구체 조항은 ROADMAP.md Phase 1 매핑 참조)
- `.planning/ROADMAP.md` §"Phase 1" — 목표·Success Criteria 6개

### 기술 스택 & 의사결정
- `CLAUDE.md` "Technology Stack" 섹션 — Python 3.13 + uv, yfinance + curl_cffi(≥0.15,<0.16), pandas.ewm, XlsxWriter, tenacity 등 라이브러리 핀 + Critical Decisions
- `.planning/research/STACK.md` (존재 시) — 동일 내용 상세
- `.planning/research/ARCHITECTURE.md` — 아키텍처 초안
- `.planning/research/PITFALLS.md` — 알려진 함정(yfinance ≥0.2.60 session API 변경, curl_cffi CVE 등)
- `.planning/research/FEATURES.md` — 기능 카탈로그
- `.planning/research/SUMMARY.md` — 리서치 종합

### 검증 기준
- `.planning/ROADMAP.md` Phase 1 Success Criteria #1~6 — verifier가 phase 종료 시 검증할 6개 사실

### 외부 문서 (필요 시 참조)
- yfinance changelog: https://github.com/ranaroussi/yfinance/blob/main/CHANGELOG.rst — session API 변경 컨텍스트
- XlsxWriter conditional/format 문서: https://xlsxwriter.readthedocs.io/working_with_conditional_formats.html, https://xlsxwriter.readthedocs.io/format.html — 정적 색 베이킹은 `Format` 객체 + `worksheet.write(row, col, value, fmt)` 패턴 사용 (조건부서식 API 미사용)
- pandas EMA: `df.ewm(span=N, adjust=False).mean()`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- 없음 — Phase 1이 첫 코드 phase. `src/stocksig/` 전체가 신규.

### Established Patterns
- `pyproject.toml` 기반 uv 관리 (`uv add`, `uv run`).
- `.env` + `python-dotenv` 패턴은 Phase 1에서 로드만 하고 EDGAR/DART 실제 호출은 Phase 3.

### Integration Points
- `main.py` 단일 엔트리포인트. `src/stocksig/`에서 export되는 함수 4개 정도를 orchestrate:
  1. `io.input.read_tickers(path) -> list[str]`
  2. `io.market.fetch_ohlcv(ticker) -> pd.DataFrame`
  3. `compute.*` (ema/stats/indicators) → 컬럼 확장된 DataFrame
  4. `output.writer.write_workbook(dataframes_by_ticker, out_path)`
- 출력 디렉토리 `output/` 부재 시 자동 생성.

</code_context>

<specifics>
## Specific Ideas

- 색상은 Material Design 800/900 (글자) + 100 (배경) 팔레트. 한 곳(`color_rules.py`의 모듈 상수)에서 튜닝 가능하게.
- 사용자가 "간단한 답변"을 선호함 — 초기 표본 부족 행은 그냥 기본색.
- 단일 미국 티커 동작 확인용 1차 검증 티커: `AAPL` (Success Criteria #1 기준).

</specifics>

<deferred>
## Deferred Ideas

- **시트1 통합 포트폴리오 요약** — Phase 2 (`output/summary_sheet.py`)
- **sqlite OHLCV 캐시 (24h TTL)** — Phase 2 (`io/cache.py`)
- **토큰버킷 throttle + max_workers=4 팬아웃** — Phase 2
- **부분 데이터 (<50%) 검증/품질 보고** — Phase 4 데이터 품질 시트
- **EDGAR/DART 실제 호출** — Phase 3 (`io/fundamentals.py`)
- **frozen panes (1~5행)** — Phase 4
- **rich progress bar / 한국어 진행률 본격화** — Phase 2~4
- **파스텔 색 톤 그레이스케일 시각 검증** — Phase 4

</deferred>

---

*Phase: 1-기반 + 단일 티커 수직 슬라이스*
*Context gathered: 2026-05-20*
