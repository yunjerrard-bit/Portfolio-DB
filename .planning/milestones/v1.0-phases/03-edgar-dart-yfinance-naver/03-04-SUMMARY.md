---
phase: 03-edgar-dart-yfinance-naver
plan: 04
subsystem: api
tags: [dart, opendartreader, naver, scraping, yfinance, fundamentals, fallback-chain, provenance, throttle, cache]

# Dependency graph
requires:
  - phase: 03-02
    provides: DART_ACCOUNT_ID_MAP / DART_ACCOUNT_MAP / SJ_DIV_INCOME_STATEMENT, dart/naver fixtures
  - phase: 03-03
    provides: fetch_fundamentals US 분기 + MetricCell/FundamentalsResult dataclass + _compute_per/_compute_peg/_compute_margin 헬퍼 + yf_fundamentals.fetch_yf_info
  - phase: 03-01
    provides: throttled_dart/throttled_yahoo limiter, cache.get_fund/put_fund
provides:
  - "dart_client.py — OpenDartReader finstate_all(stock_code 직접) + account_id 1차/account_nm 2차 매핑 + status 가드 + throttle + 7d cache"
  - "naver_scraper.py — finance.naver.com PER 스크래핑(UTF-8) + D-07 폴백 상한(NAVER_FALLBACK_CAP=20)"
  - "fetch_fundamentals KR 분기 — metric별 차등 폴백(PER: DART→Naver→yf; GPM/OPM: DART→yf) + provenance 라벨(DART/Naver/yf)"
affects: [04-xlsx-sheet-builder, runner-integration, portfolio-sheet]

# Tech tracking
tech-stack:
  added: [OpenDartReader, httpx, beautifulsoup4/lxml]
  patterns:
    - "metric별 차등 폴백 체인 (per-metric provenance — 1차 채운 지표는 폴백으로 덮어쓰지 않음)"
    - "의존성 주입(dart_fn/naver_fn/yf_fn/edgar_fn) 으로 네트워크 없는 단위테스트"
    - "전 경로 try/except 흡수 — 펀더멘털 결손 ≠ 티커 실패 (D-disc-10)"
    - "외부 스크래핑 호출 상한(D-07) — 모듈 레벨 카운터 + run당 reset"

key-files:
  created:
    - src/stocksig/io/dart_client.py
    - src/stocksig/io/naver_scraper.py
    - tests/test_dart_client.py
    - tests/test_naver_scraper.py
  modified:
    - src/stocksig/io/fundamentals.py
    - tests/test_fundamentals.py

key-decisions:
  - "DART 계정 매핑은 account_id 1차(IFRS/DART 표준태그, 업종 안정) / account_nm 2차(한글 라벨 폴백) — A3 [VERIFIED]"
  - "Naver 인코딩 = UTF-8 (RESEARCH 의 euc-kr 가정 폐기 — A5 [VERIFIED] charset=utf-8)"
  - "Naver 는 PER 단일 지표 폴백 전용 — GPM/OPM 미노출(Open Q4)이라 GPM/OPM 은 DART→yf 직행"
  - "D-07: Naver 는 소수 폴백 전용 — run당 NAVER_FALLBACK_CAP(20) 상한, 초과 시 yf 직행"
  - "기본 dart_fn quarter_label 은 직전 회계연도 사업보고서(YYYY-11011) — 러너 연동은 후속 plan"

patterns-established:
  - "KR per-metric 차등 폴백: PER(DART→Naver→yf) vs GPM/OPM(DART→yf, Naver 건너뜀)"
  - "테스트는 dart_fn/naver_fn/yf_fn 콜러블 주입으로 격리 — call_count 단언으로 체인 검증"

requirements-completed: [FUND-03, FUND-05]

# Metrics
duration: ~12min (Task 2; Task 1 별도 세션)
completed: 2026-06-05
---

# Phase 03 Plan 04: KR 펀더멘털 확장 (DART + Naver + yf 폴백) Summary

**OpenDartReader finstate_all(account_id 1차 매핑) + Naver PER 스크래핑(UTF-8, D-07 상한) + fetch_fundamentals KR 분기로 metric별 차등 폴백 체인(PER: DART→Naver→yf, GPM/OPM: DART→yf)과 per-metric provenance 라벨을 구현.**

## Performance

- **Duration:** Task 2 약 12분 (Task 1 은 8915b94 별도 세션)
- **Completed:** 2026-06-05
- **Tasks:** 2 (Task 1 선완료, 본 세션 Task 2 실행)
- **Files modified (Task 2):** 2 — `src/stocksig/io/fundamentals.py`, `tests/test_fundamentals.py`

## Accomplishments

- **Task 1 (선완료, `8915b94`)** — `dart_client.py`(finstate_all stock_code 직접 수용·account_id 1차/account_nm 2차 매핑·status 000/013/020 한국어 가드·thstrm_amount int 파싱·throttle·7d cache) + `naver_scraper.py`(UTF-8 PER 스크래핑·`#_per` None 가드·D-07 NAVER_FALLBACK_CAP 상한·reset_naver_count).
- **Task 2 (본 세션, `e7642be`)** — `fetch_fundamentals` KR 분기(`_fill_kr`): DART 1차 산출 후 PER 은 DART→Naver→yf, GPM/OPM 은 DART→yf(Naver 건너뜀), PEG 은 DART(eps/eps_prior)→yf. per-metric provenance 라벨("DART"/"Naver"/"yf"), 1차 채운 지표 보존, 전 경로 try/except 흡수, 한국어 진행 로그(DART / DART→Naver+yf / fund MISS).
- KR 산식: PER = last_close(KRW)/기본주당이익, PEG = `_compute_peg(per, eps, eps_prior)`, GPM = 매출총이익/매출액, OPM = 영업이익/매출액 (03-03 헬퍼 재사용).

## Task Commits

1. **Task 1: dart_client.py + naver_scraper.py** - `8915b94` (feat) — 선행 세션
2. **Task 2: fundamentals.py KR 분기 + KR 테스트** - `e7642be` (feat) — TDD RED→GREEN

_본 plan 의 `.planning/` 산출물(이 SUMMARY)은 `.gitignore` + commit_docs=false 라 로컬 전용 — 코드/테스트만 atomic commit._

## Files Created/Modified

- `src/stocksig/io/dart_client.py` (Task 1) - OpenDART finstate_all 페치 + 계정 매핑 + status 가드 + cache-first
- `src/stocksig/io/naver_scraper.py` (Task 1) - Naver PER 스크래핑(UTF-8) + D-07 폴백 상한
- `tests/test_dart_client.py` / `tests/test_naver_scraper.py` (Task 1) - 매핑·status·CAP·cache HIT 단언
- `src/stocksig/io/fundamentals.py` (Task 2) - `_fill_kr` KR 라우팅 + `fetch_fundamentals` 에 dart_fn/naver_fn 주입 파라미터 + US/KR 분기
- `tests/test_fundamentals.py` (Task 2) - KR 케이스 6종(전지표 DART / PER→Naver / PER→yf / GPM yf직행 naver call 0 / 전결손 / 예외흡수)

## Decisions Made

- **계정 매핑 account_id 1차 / account_nm 2차** — A3 [VERIFIED]. account_id 는 IFRS/DART 표준태그라 업종 안정, account_nm 은 회사 재량 한글이라 폴백.
- **Naver UTF-8** — A5 [VERIFIED], RESEARCH 의 euc-kr 가정 폐기.
- **Naver = PER 단일 폴백** — GPM/OPM 미노출(Open Q4) → GPM/OPM 은 DART→yf 직행. 테스트에서 GPM 결손 시 naver call_count==0 단언으로 강제.
- **D-07 상한** — naver_scraper 모듈 레벨 카운터로 통제(fundamentals.py 는 naver_fn 결과 None 만 보고 yf 직행). 상한 초과로 None 인 경우도 동일 경로.
- **기본 dart_fn quarter_label = 직전 회계연도 사업보고서(YYYY-11011)** — 본 plan 범위 밖(러너 연동은 후속). 테스트는 dart_fn 주입으로 우회하므로 영향 없음.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 기본 dart_fn 의 quarter_label 결정 함수 부재 보완**
- **Found during:** Task 2 (fetch_fundamentals KR 라우팅 기본 클라이언트 와이어링)
- **Issue:** plan 의도상 KR 기본 경로는 `dart_client.fetch_dart_cached(t, quarter_label)` 호출이 필요하나, `market.py` 에 `latest_quarter_label` 류 함수가 존재하지 않아 production import 경로가 깨질 수 있음.
- **Fix:** `_default_dart` 내부에서 직전 회계연도 사업보고서 라벨(`f"{today.year-1}-11011"`)을 inline 산출 — dart_client 의 `quarter_label="{bsns_year}-{reprt_code}"`(A7) 형식 준수. 러너의 정밀 quarter 결정은 후속 plan 으로 미룸.
- **Files modified:** src/stocksig/io/fundamentals.py
- **Verification:** 테스트는 dart_fn 주입으로 우회(기본 경로 미실행), 전체 스위트 186 GREEN. import-time 오류 없음.
- **Committed in:** `e7642be` (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** 기본 와이어링 import 안전성 확보용. 테스트 경로·KR 산식·폴백 체인 의도 불변. 스코프 크리프 없음.

## Issues Encountered

- 없음 — Task 2 RED(KR 케이스 `dart_fn` 미존재 TypeError)→GREEN(24 케이스 전부) 일발 통과. 전체 회귀 스위트 186 passed.

## User Setup Required

- `OPENDART_API_KEY` (opendart.fss.or.kr 무료 발급) — `.env` 에 설정해야 DART 라이브 호출 가능. 단위테스트는 mock 주입이라 키 불필요.
- (선택) `NAVER_FALLBACK_CAP` env override — 기본 20.

## Next Phase Readiness

- US(03-03)+KR(03-04) 펀더멘털 경로 동일 `FundamentalsResult` 형태로 통일 — xlsx 시트 빌더가 시장 무관하게 소비 가능.
- 잔여 통합 작업(러너에서 `fetch_fundamentals` 호출·정밀 quarter_label 결정·`reset_naver_count()` run 시작 훅)은 후속 plan 범위.

## Self-Check: PASSED

- FOUND: src/stocksig/io/fundamentals.py (modified, KR 분기 `_fill_kr` 포함)
- FOUND: tests/test_fundamentals.py (modified, KR 케이스 6종)
- FOUND: src/stocksig/io/dart_client.py (Task 1)
- FOUND: src/stocksig/io/naver_scraper.py (Task 1)
- FOUND: commit `8915b94` (Task 1)
- FOUND: commit `e7642be` (Task 2)
- Tests: `uv run pytest tests/test_fundamentals.py` → 24 passed; `uv run pytest` → 186 passed (회귀 없음)

---
*Phase: 03-edgar-dart-yfinance-naver*
*Completed: 2026-06-05*
