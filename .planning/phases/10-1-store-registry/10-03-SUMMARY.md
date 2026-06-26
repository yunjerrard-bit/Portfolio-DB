---
phase: 10-1-store-registry
plan: 03
subsystem: io
tags: [fundamentals, store-registry, dead-code-removal, cache, single-source, FUND-11]
requires:
  - phase: 10-02
    provides: "main_run.run PASS1→SYNC→READ(어댑터)→PASS2 재배선 — 구 fetch 경로 호출자 소멸"
  - phase: 10-01
    provides: "fundamentals_view.matrix_to_fundamentals 어댑터 + 보존 계약(D-04) 확립"
provides:
  - "구 펀더멘털 fetch 경로 제거 — fetch_fundamentals/_fill_us/_fill_kr/_empty_result/_log_* (D-03)"
  - "구 cache-first 페치 제거 — edgar_client.fetch_edgar_cached / dart_client.fetch_dart_cached"
  - ".cache/fundamentals 7일 캐시 헬퍼·통계 키 제거 — fund 디렉터리/조회/저장/카운터 (D-05/L6)"
  - "단일 원천 완성(FUND-11 SC2) — 시트1 펀더멘털은 store/registry SQLite 읽기만"
  - "σ-bucket 색 신호 불변 + D-02 빈DB 빈칸 회귀 잠금 테스트"
affects:
  - "Phase 10 검증(/gsd:verify-phase 10) — FUND-11 엔드투엔드 완성 확인"
tech-stack:
  added: []
  patterns:
    - "죽은 코드 안전 제거 — grep 호출자 0 확인 후 삭제, 보존 계약은 grep 단언으로 가드"
    - "제거 collateral 테스트 정리 — 죽은 심볼 참조 테스트는 보존계약 단언만 잔류 + 심볼-부재 단언으로 강화"
key-files:
  created:
    - ".planning/phases/10-1-store-registry/10-03-SUMMARY.md"
  modified:
    - "src/stocksig/io/fundamentals.py"
    - "src/stocksig/io/edgar_client.py"
    - "src/stocksig/io/dart_client.py"
    - "src/stocksig/io/cache.py"
    - "src/stocksig/main_run.py"
    - "tests/conftest.py"
    - "tests/test_cache.py"
    - "tests/test_cache_isolation.py"
    - "tests/test_fundamentals.py"
    - "tests/test_edgar_client.py"
    - "tests/test_dart_client.py"
    - "tests/test_history_integration.py"
    - "tests/test_sheet_portfolio.py"
key-decisions:
  - "구 fetch·캐시 제거는 grep 호출자 0 확인 후 진행 — fetch_*_cached 호출자는 fetch_fundamentals 내부뿐, 시트1 경로(10-02)가 소멸시킴"
  - "보존 계약(D-04: MetricCell/FundamentalsResult/_empty_cell/_is_missing/_compute_*)·store 추출기(L2: fetch_*_quarterly_raw)·OHLCV·기업명 캐시(L3) 무접촉 — grep 단언으로 가드"
  - "요약 캐시 줄에서 펀더멘털 HIT/MISS 토막·통계 키 동시 정리(L6) — KeyError 회귀 방지(stats 에 fund 키 부재)"
  - "no_legacy_fetch/single_source 통합 테스트를 spy 호출 0 → 심볼-부재(hasattr False) 단언으로 강화 — 구 경로 재유입 시 import 실패로 즉시 발각"
patterns-established:
  - "Dead-code removal: grep 호출자 0 → 삭제 → 보존 심볼 grep 단언 → 전 스위트 회귀 0"
  - "Color regression-lock: openpyxl 폰트 색 hex 바이트 일치 + 펀더멘털 색-누출 0 동시 단언(sheet_portfolio 0줄 diff 구조적 보장)"
requirements-completed: [FUND-11]
duration: ~50min
completed: 2026-06-23
---

# Phase 10 Plan 03: 구 펀더멘털 fetch·캐시 죽은 코드 제거 + 시트1 색 회귀 잠금 Summary

**Plan 10-02 가 호출자를 소멸시킨 구 펀더멘털 fetch 경로(`fetch_fundamentals`/`_fill_*`)·구 cache-first 페치(`fetch_edgar/dart_cached`)·`.cache/fundamentals` 7일 캐시 헬퍼군을 grep 호출자-0 확인 후 안전 제거하고, 보존 계약·store 추출기·OHLCV/기업명 캐시 무손상과 시트1 σ-bucket 색 신호 회귀 0 을 검증해 FUND-11 단일 원천을 완성했다.**

## Performance

- **Duration:** ~50 min
- **Completed:** 2026-06-23T07:26Z
- **Tasks:** 2 (Task 1 제거, Task 2 TDD 회귀 테스트)
- **Files modified:** 13 (소스 5 + 테스트 8)

## Accomplishments
- 구 펀더멘털 fetch 경로 전면 제거(D-03): `fundamentals.py` 가 공유 계약(데이터 모델·결손 게이트·순수 산식 헬퍼)만 보유하는 ~130줄 모듈로 축소(이전 389줄).
- 구 cache-first 페치(`fetch_edgar_cached`/`fetch_dart_cached`)·`.cache/fundamentals` 캐시 헬퍼군(`_FUND_DIR`/`get_fund`/`put_fund`/`make_fund_key`/`fund_hit`/`fund_miss`) 제거 — OHLCV·기업명 캐시는 별개 디렉터리·헬퍼·통계 키로 무손상(L3).
- 요약 캐시 줄에서 펀더멘털 HIT/MISS 토막·통계 키 정리(L6) — KeyError 회귀 0.
- σ-bucket 색 신호 회귀 0 + D-02 빈DB 빈칸 동작을 openpyxl read-back 테스트로 잠금 — `sheet_portfolio.py` 0줄 diff(Core Value 구조적 보장).

## Task Commits

1. **Task 1: 구 fetch 경로 + .cache/fundamentals 헬퍼 제거 + 요약 줄 정리** — `2db5fae` (refactor)
2. **Task 2: 시트1 σ-bucket 색 신호 불변 + D-02 빈DB 빈칸 회귀 테스트** — `aabd526` (test)

_Task 2 는 회귀-잠금 테스트로, 산출물 writer 가 이미 존재(10-01/10-02)하므로 단일 test 커밋(RED→GREEN 동시 충족, sheet_portfolio 0줄 diff)._

## Files Created/Modified
- `src/stocksig/io/fundamentals.py` — 구 fetch 오케스트레이터 제거, 공유 계약(D-04)만 보존. 미사용 import(logging/Callable/classify_market) 정리.
- `src/stocksig/io/edgar_client.py` — `fetch_edgar_cached` + `cache` import 제거. `fetch_edgar_raw`/`fetch_edgar_quarterly_raw` 보존(L2).
- `src/stocksig/io/dart_client.py` — `fetch_dart_cached` + `cache` import 제거. `fetch_dart_raw`/`fetch_dart_quarterly_raw` 보존(L2).
- `src/stocksig/io/cache.py` — 펀더멘털 캐시 헬퍼군·`fund_hit`/`fund_miss` 통계 키 제거. OHLCV(`_DEFAULT_DIR`/`get_ohlcv`/`make_key`)·기업명(`_NAME_DIR`/`get_company_name`)·공유 `_cache_lock` 무접촉(L3).
- `src/stocksig/main_run.py` — 요약 캐시 줄 펀더멘털 HIT/MISS 토막·`stats["fund_*"]` 참조 제거(L6).
- `tests/conftest.py` — autouse `_isolated_disk_cache` 에서 `_FUND_DIR`/`_fund_cache` 격리 제거, OHLCV·기업명만 격리.
- `tests/test_cache.py` — 펀더멘털 캐시 단위 테스트 제거, stats 단언에서 fund 키 제거.
- `tests/test_cache_isolation.py` — `_FUND_DIR` 격리 단언 → `_NAME_DIR` 격리 단언.
- `tests/test_fundamentals.py` — `fetch_fundamentals`/`_fill_*` 라우팅·폴백·skip·예외흡수 테스트 제거. 보존 계약 산식(11) + WR-01 NaN 게이트(5) = 16 테스트 잔류.
- `tests/test_edgar_client.py` / `tests/test_dart_client.py` — `fetch_*_cached_hit` 테스트·`_isolated_fund_cache` 픽스처·`diskcache.Cache`/`pytest` 미사용 import 제거.
- `tests/test_history_integration.py` — `no_legacy_fetch`/`single_source` 를 spy 호출 0 → `hasattr` 심볼-부재 단언으로 강화.
- `tests/test_sheet_portfolio.py` — σ-bucket 색 불변(`test_sigma_color_unchanged_after_migration`) + D-02 빈DB(`test_missing_db_fund_cells_blank`) 2 테스트 추가(+100줄).

## Decisions Made
- 제거 전 `grep -r` 로 모든 제거 대상의 호출자가 src 에서 0 임을 확인(`fetch_*_cached` 호출자는 `fetch_fundamentals` 내부뿐 → 함께 제거). 보존 대상(`fetch_*_quarterly_raw`/`_compute_*`/`fetch_*_raw`)은 별개 store/계산 경로로 호출자 유지.
- `dart_client` 의 라인 44 주석("cache.py double-checked locking 패턴 복제")은 `cache.` 심볼 사용이 아닌 역사적 메모라 유지.
- 색 회귀 테스트는 폰트 색 hex 바이트 일치(σ 영역) + 펀더멘털 4셀 색 누출 0(DEFAULT) 을 동시 단언 — 이관이 색 로직 무접촉임을 셀 단위로 증명.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] 제거된 심볼을 참조하는 테스트/픽스처 정리 (collateral)**
- **Found during:** Task 1 (제거 후 회귀 검증)
- **Issue:** 플랜 `files_modified` 는 소스 5 + `test_sheet_portfolio.py` 만 선언했으나, 제거 대상 심볼(`fetch_fundamentals`/`fetch_*_cached`/`_FUND_DIR`/`get_fund`/`put_fund`/`fund_hit`/`fund_miss`)을 직접 참조하는 다수 테스트·픽스처가 존재. 특히 autouse `conftest._isolated_disk_cache` 가 `_FUND_DIR`/`_fund_cache` 를 monkeypatch 해 **전 스위트 28+ 테스트가 AttributeError 로 즉시 차단**. 10-02 가 freeze/smoke stub 을 collateral 로 수정한 것과 동일 성격(죽은 코드 제거가 강제하는 필수 수정).
- **Fix:** (1) conftest autouse 픽스처에서 fund 격리 제거(OHLCV·기업명만 격리), (2) `test_cache.py` 펀더멘털 캐시 단위 테스트·stats fund 키 제거, (3) `test_cache_isolation.py` `_FUND_DIR`→`_NAME_DIR` 격리 단언 교체, (4) `test_fundamentals.py` 라우팅 테스트 제거·보존계약 산식만 잔류(41→16), (5) `test_edgar/dart_client.py` cached_hit 테스트·fund 픽스처·미사용 import 제거, (6) `test_history_integration.py` spy → 심볼-부재 단언 강화.
- **Files modified:** tests/conftest.py, tests/test_cache.py, tests/test_cache_isolation.py, tests/test_fundamentals.py, tests/test_edgar_client.py, tests/test_dart_client.py, tests/test_history_integration.py
- **Verification:** 해당 7 + sheet_portfolio 파일 GREEN; 전 스위트 353 passed(회귀 0, baseline 대비 죽은-코드 테스트 -32 + 신규 +2).
- **Committed in:** `2db5fae` (Task 1 — collateral 테스트는 제거와 원자적으로 묶임)

---

**Total deviations:** 1 auto-fixed (Rule 3 blocking collateral)
**Impact on plan:** 죽은 코드 제거가 구조적으로 강제한 필수 테스트 정리. 보존 계약 테스트 커버리지(산식 16종·OHLCV/기업명 캐시·store 추출기)는 전부 유지. scope creep 없음.

## Issues Encountered
- **선존 deferred 3종(본 plan 무관):** `test_history_render.py::{test_history_cli_dispatch, test_default_cli_dispatch, test_history_cli_db_empty_exit0}` 가 `ModuleNotFoundError: No module named 'main'` 로 실패. baseline(제거 전)에서도 동일 실패 — `importlib.import_module("main")`/`subprocess [..., "main.py"]` 가 레포 루트 sys.path 부재로 발생하는 경로 아티팩트(10-01 SUMMARY 에 deferred 기록). 본 plan 변경 코드 무관, deferred-items.md 참조.

## Verification

| 항목 | 결과 |
|------|------|
| 전 스위트 (repo root on PYTHONPATH) | **353 passed / 3 failed(선존 deferred)** — 회귀 0 |
| `grep "def fetch_fundamentals\|_fill_us\|_fill_kr\|fetch_edgar_cached\|fetch_dart_cached" src/stocksig/io/` | 0 (구 fetch 제거) |
| `grep "def fetch_edgar_quarterly_raw"` / `fetch_dart_quarterly_raw` | 1 / 1 (store 추출기 보존, L2) |
| D-04 보존 grep(_compute_*·MetricCell·FundamentalsResult·_is_missing) | 6 (계약 전체 보존) |
| `grep "_FUND_DIR\|make_fund_key\|get_fund\|put_fund\|fund_hit\|fund_miss" cache.py` | 0 (펀더멘털 캐시 제거) |
| `grep "_DEFAULT_DIR\|def get_ohlcv\|def make_key" cache.py` | 5 (≥3 — OHLCV 무손상, L3) |
| `grep "fund_hit\|fund_miss\|펀더멘털 HIT" main_run.py` | 0 (L6 요약 정리) |
| `test_cache.py`/`test_cache_isolation.py` | GREEN (OHLCV 캐시 무손상 — T-10-07 DoS 방지) |
| `test_sheet_portfolio.py -k "color or missing_db"` | GREEN (σ-bucket 색 불변·D-02 빈칸) |
| `git diff src/stocksig/output/sheet_portfolio.py` | 빈 출력 (Core Value 색 신호 0줄 변경, L9) |

## Threat Surface
신규 보안 surface 0 — 순수 제거 + 회귀 테스트. T-10-07(DoS): OHLCV/기업명 캐시 무접촉, grep 5건 + 캐시 테스트 GREEN 가드. T-10-08(Tampering): store 추출기 `fetch_*_quarterly_raw` 보존, 제거는 `*_cached` 만. T-10-09(Info Disclosure): 요약 줄 정수 카운트만(API 키·예외 원문 미포함). T-10-10(Tampering): `_compute_*` 보존, grep 6건. T-10-SC: 신규 패키지 0(제거만).

## Next Phase Readiness
- FUND-11 단일 원천 완성 — 시트1 PER/PEG/GPM/OPM 이 store/registry SQLite 읽기로만 산출, 외부 펀더멘털 fetch 0, 구 7일 캐시·중복 산식 경로 제거 완료(SC2).
- **다음:** `/gsd:verify-phase 10` — 전 스위트 353 GREEN(+선존 deferred 3)·시트1 색 불변·`git diff sheet_portfolio` 빈 출력 확인. Phase 10 = v1.3 마지막 phase.
- **선존 deferred(권고):** `test_history_render.py` CLI 디스패치 3종 sys.path 아티팩트 — 별도 quick task 로 conftest sys.path 보정 또는 테스트 invocation 조정.

## Self-Check: PASSED

- 산출/핵심 파일 존재: `10-03-SUMMARY.md` · `fundamentals.py`(보존 계약) · `fundamentals_view.py`(어댑터).
- 커밋 2건 존재: `2db5fae`(refactor — Task 1 제거+collateral) · `aabd526`(test — Task 2 색 회귀).
- 보존 계약·store 추출기·OHLCV/기업명 캐시 grep 단언 전부 통과. sheet_portfolio.py 0줄 diff.

---
*Phase: 10-1-store-registry*
*Completed: 2026-06-23*
