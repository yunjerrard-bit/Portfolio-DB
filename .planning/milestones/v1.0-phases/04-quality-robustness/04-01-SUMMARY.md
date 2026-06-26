---
phase: 04-quality-robustness
plan: 01
subsystem: infra
tags: [cache, logging, threading, lock, console-summary, korean-logs]

requires:
  - phase: 02-scaling-portfolio-summary
    provides: "runner.run_all 멀티티커 오케스트레이션 + main_run.run() 종료부 실패 경고 + cache.get_ohlcv/get_fund per-call HIT/MISS 로그"
  - phase: 03-edgar-dart-yfinance-naver
    provides: "펀더멘털 캐시(get_fund) + naver_scraper reset_naver_count 카운터 패턴"
provides:
  - "cache.py lock-보호 hit/miss 집계 카운터 (reset_cache_stats/get_cache_stats)"
  - "main_run.run() 종료부 한국어 실행 요약 블록 (티커 총/성공/실패 + 캐시 통계 + 실패 티커 목록)"
  - "D-01 정합: REQUIREMENTS EXEC-04 + ROADMAP Phase4 Goal/SC2 콘솔 요약 대체 재정의"
affects: [04-03-PLAN(인증 상태 줄을 같은 요약 블록에 삽입), 04-02-PLAN(같은 ROADMAP Goal 라인 frozen panes)]

tech-stack:
  added: []
  patterns:
    - "모듈 레벨 카운터 dict + threading.Lock 으로 read-modify-write(+=) 보호 (ThreadPoolExecutor fan-out 하의 lost-update 방지)"
    - "get_cache_stats() 는 dict(_stats) 복사본 반환 — 호출자 변형이 내부 상태를 오염시키지 않음"
    - "종료부 요약 블록은 카운트(정수)·티커 심볼만 출력 (T-04-01: API 키·예외 원문 미포함)"

key-files:
  created:
    - .planning/phases/04-quality-robustness/04-01-SUMMARY.md
  modified:
    - src/stocksig/io/cache.py
    - tests/test_cache.py
    - src/stocksig/main_run.py
    - tests/test_smoke_n_tickers.py
    - .planning/REQUIREMENTS.md
    - .planning/ROADMAP.md

key-decisions:
  - "캐시 카운터는 naver_scraper.reset_naver_count 패턴을 차용한 모듈 레벨 dict + Lock 으로 구현 (신규 의존성 0)"
  - "요약 블록은 기존 실패 경고/per-call 로그를 대체하지 않고 추가 (회귀 테스트로 무손상 증명)"
  - "ROADMAP Phase4 Goal 라인도 D-01 일관성을 위해 정렬 (Rule 2 — 플랜 명시 SC2 외 일관성 정정)"

patterns-established:
  - "lock-guarded 카운터: with _stats_lock 안에서만 += 및 스냅샷 읽기"
  - "한국어 실행 요약 블록: ════════ 실행 요약 ════════ 헤더 + 티커/캐시/실패 줄"

requirements-completed: [EXEC-04]

duration: 27 min
completed: 2026-06-11
---

# Phase 4 Plan 01: 콘솔 최종 요약 블록 수직 슬라이스 Summary

**lock-보호 캐시 hit/miss 집계 카운터(`cache.py`)와 `main_run.run()` 종료부 한국어 실행 요약 블록(티커 총/성공/실패 + OHLCV/펀더멘털 캐시 통계 + 실패 티커 목록)을 추가하고, D-01 결정에 맞춰 EXEC-04/ROADMAP SC2 문서를 "데이터 품질 시트" → "콘솔 요약 대체"로 재정의**

## Performance

- **Duration:** 27 min
- **Started:** 2026-06-11T07:54:00Z
- **Completed:** 2026-06-11T08:21:00Z
- **Tasks:** 3
- **Files modified:** 6 (코드 2 + 테스트 2 + 문서 2)

## Accomplishments
- `cache.py` 에 lock-보호 모듈 카운터(`_stats` + `_stats_lock`)와 `reset_cache_stats()`/`get_cache_stats()`(복사본 반환) 추가. `get_ohlcv`/`get_fund` 의 HIT/MISS 분기에서 lock-guarded `+= 1`.
- `main_run.run()` 시작부에 `cache.reset_cache_stats()` 추가, 종료부에 한국어 "실행 요약" 블록(티커 총/성공/실패 · 캐시 OHLCV/펀더멘털 HIT/MISS · failures>0 시 실패 티커 심볼 목록) 추가.
- D-01 정합: REQUIREMENTS EXEC-04 + ROADMAP Phase4 Goal/SC2 를 "별도 데이터 품질 시트 미생성, 콘솔 요약+시트1 실패행+셀 주석으로 대체"로 갱신.
- 신규 테스트 7개(카운터 5 + 요약 블록 2) 추가, 전체 회귀 207 passed (무회귀).

## Task Commits

각 태스크는 원자적으로 커밋(TDD: test → feat):

1. **Task 1 (RED): cache 카운터 실패 테스트** - `b369563` (test)
2. **Task 1 (GREEN): cache.py hit/miss 카운터 + reset/get** - `0c3a688` (feat)
3. **Task 2 (RED): main_run 요약 블록 실패 테스트** - `cb03323` (test)
4. **Task 2 (GREEN): main_run 요약 블록 + reset_cache_stats** - `a08fc59` (feat)
5. **Task 3: D-01 문서 정합 (REQUIREMENTS/ROADMAP)** - `58686bd` (docs)

**Plan metadata:** SUMMARY 커밋 (이 커밋)

## Files Created/Modified
- `src/stocksig/io/cache.py` - `_stats` 카운터 dict + `_stats_lock` + `reset_cache_stats`/`get_cache_stats`; get_ohlcv/get_fund HIT/MISS 분기에 lock-guarded `+= 1`. 기존 per-call `cache HIT/MISS` 로그 무손상.
- `tests/test_cache.py` - 카운터 5개 테스트(리셋·OHLCV·펀더멘털·복사본·race(ThreadPoolExecutor max_workers=4, 200 호출 합계 일치)).
- `src/stocksig/main_run.py` - 시작부 `cache.reset_cache_stats()`; 종료부 "실행 요약" 블록(티커/캐시/실패 티커 목록) + `# TODO(04-03): 인증 상태 줄` 자리.
- `tests/test_smoke_n_tickers.py` - `test_summary_block_emitted`(헤더+티커+캐시+실패 목록+회귀), `test_summary_block_omits_failure_line_when_no_failures`.
- `.planning/REQUIREMENTS.md` - EXEC-04 D-01 재정의.
- `.planning/ROADMAP.md` - Phase4 Goal + SC2 D-01 재정의.

## Decisions Made
- 캐시 카운터는 신규 의존성 없이 `threading.Lock`+모듈 dict 로 구현 (naver_scraper 카운터 패턴 차용).
- 요약 블록은 기존 실패 경고(`실패 N개 — 시트1에 표시됨`)와 per-call 캐시 로그를 **대체하지 않고 추가** — 회귀 테스트로 두 로그가 여전히 출력됨을 증명.
- 인증 상태 줄은 Plan 04-03 소관이므로 `# TODO(04-03)` 주석으로 자리만 표시.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - 일관성] ROADMAP Phase4 Goal 라인의 "데이터 품질 시트" 문구 정렬**
- **Found during:** Task 3 (D-01 문서 정합)
- **Issue:** 플랜 Task 3 는 EXEC-04 + ROADMAP SC2 만 명시했으나, ROADMAP Phase4 **Goal** 라인(L101)에도 `"데이터 품질" 시트를 두어` 문구가 남아 D-01(별도 시트 미생성)과 정면 모순되는 문서 상태가 됨.
- **Fix:** Goal 라인의 해당 구절을 "콘솔 최종 요약 블록·시트1 실패행·셀 주석으로 한 곳에서 확인(D-01: 별도 시트 미생성)"으로 정렬. 다른 Goal 요소(frozen panes·색 톤)는 미변경 (Plan 04-02 소관 유지).
- **Files modified:** .planning/ROADMAP.md
- **Verification:** `grep '데이터 품질' 시트를 두어` 가 EXEC-04/SC2/Goal 어디에도 더 이상 매치하지 않음.
- **Committed in:** 58686bd (Task 3 커밋)

**2. [Rule 3 - Blocking] `.planning/` 디렉터리가 gitignore 되어 있어 문서/SUMMARY 커밋에 `-f` 필요**
- **Found during:** Task 3 (REQUIREMENTS/ROADMAP 커밋 시도)
- **Issue:** 프로젝트 `.gitignore` L1 이 `.planning/` 전체를 무시 → 워크트리 베이스(23b01a7)에 `.planning/phases/`·REQUIREMENTS.md·ROADMAP.md 가 존재하지 않았고, 일반 `git add` 가 거부됨. (플랜 파일 자체도 메인 레포 워킹트리에만 untracked 로 존재했음.)
- **Fix:** 메인 레포 워킹트리에서 필요한 `.planning/` 파일을 워크트리로 복사 후 `git add -f` 로 강제 추가하여 태스크 내용(문서 편집 + SUMMARY)을 git 히스토리에 보존. (오케스트레이터가 워크트리를 강제 제거하기 전 손실 방지 — #2070.)
- **Files modified:** .planning/REQUIREMENTS.md, .planning/ROADMAP.md, .planning/phases/04-quality-robustness/04-01-SUMMARY.md
- **Verification:** `git log` 에 docs/Task3 커밋과 SUMMARY 커밋 존재.
- **Committed in:** 58686bd + SUMMARY 커밋

---

**Total deviations:** 2 auto-fixed (1 일관성/Rule 2, 1 blocking/Rule 3)
**Impact on plan:** 둘 다 문서 정합·아티팩트 보존을 위한 필수 조정. 코드 스코프 변경 없음, 스코프 크리프 없음.

## Issues Encountered
- **워크트리 베이스에 `.planning/` 부재:** `.planning/` 가 gitignore 되어 worktree 베이스(23b01a7)에 플랜/요구사항/로드맵 파일이 없었음. 메인 레포 워킹트리(`C:/.../example/.planning/`)에서 untracked 상태로 존재하는 파일을 워크트리로 복사하여 실행을 진행. `git add -f` 로 태스크 산출물을 커밋해 워크트리 제거 후에도 보존되도록 처리.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- **04-03 (인증 상태 줄):** 요약 블록 골격이 준비됨. `main_run.py` 종료부 `# TODO(04-03): 인증 상태 줄` 위치에 EDGAR/DART 인증 결과 줄을 삽입하면 됨.
- **04-02 (frozen panes / 색 톤):** ROADMAP Phase4 Goal 라인은 본 plan 에서 D-01 정합만 정렬했고 frozen panes/색 톤 요소는 그대로 유지 — 04-02 소관에 영향 없음.
- 전체 회귀 207 passed, 무회귀 확인.

## TDD Gate Compliance
- Task 1: `test(04-01)` RED (`b369563`) → `feat(04-01)` GREEN (`0c3a688`) ✓
- Task 2: `test(04-01)` RED (`cb03323`) → `feat(04-01)` GREEN (`a08fc59`) ✓
- REFACTOR 단계 불필요 (구현이 최소·명료).

## Threat Flags
신규 위협 표면 없음. T-04-01(요약 블록 정보노출)은 카운트·심볼만 출력하여 mitigate 됨(키/UA/예외 원문 미포함). T-04-SC(패키지 설치) 해당 없음 — 신규 설치 0개.

## Self-Check: PASSED
- `src/stocksig/io/cache.py` 존재, `reset_cache_stats`/`get_cache_stats`/`_stats_lock` 매치 ✓
- `src/stocksig/main_run.py` 존재, `실행 요약`/`실패 티커:`/`reset_cache_stats`/`get_cache_stats` 매치 ✓
- `.planning/REQUIREMENTS.md` D-01 매치, `.planning/ROADMAP.md` D-01 매치 ✓
- 커밋 b369563/0c3a688/cb03323/a08fc59/58686bd 모두 `git log` 에 존재 ✓
- `uv run pytest` 전체 207 passed (무회귀) ✓

---
*Phase: 04-quality-robustness*
*Completed: 2026-06-11*
