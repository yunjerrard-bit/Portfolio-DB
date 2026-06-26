---
phase: 05-weekly-impulse-stepwise
plan: 01
subsystem: compute
tags: [pandas, ema, macd, impulse, weekly, ffill, week_close_mask, xlsx]

# Dependency graph
requires:
  - phase: 01-foundation
    provides: ema_week_to_date / macd_oscillator_week_to_date / week_close_mask / decide_impulse 인터페이스
  - phase: 04
    provides: 진행형 주봉 표시 컬럼(EMA_Close_11_week_trend 등) + 시트1 Impulse_weekly 표시 경로
provides:
  - 금-금 주간 계단형 주봉 임펄스(Impulse_weekly) 산출
  - week_close_mask 샘플링 → 직전 완성 주 대비 부호 → decide_impulse → reindex(ffill) broadcast 패턴
affects: [output, sheet_portfolio, sheet_per_ticker, weekly-stats]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "주봉 계단형: week_close_mask로 주 마지막 거래일 샘플 → diff 부호 → decide_impulse → reindex(daily, ffill) broadcast (기존 금요일-앵커 주봉 통계 정책과 동형)"

key-files:
  created: []
  modified:
    - src/stocksig/compute/impulse.py
    - src/stocksig/main_run.py
    - tests/test_impulse.py

key-decisions:
  - "D2 계단형: 완성 주 임펄스를 reindex(daily_index, method='ffill')로 주중 broadcast — 다음 주 마지막 거래일에만 갱신"
  - "D4 회귀 보호: 일봉부(Impulse_daily)와 진행형 표시 컬럼(EMA_Close_11/22_week_trend·MACD_OSC_week·MACD_OSC_week_diff)은 한 글자도 변경하지 않음 — main_run 주석만 사실에 맞게 갱신"
  - "첫 완성 주(직전 주 없음)는 diff=NaN → decide_impulse가 DEFAULT('') 반환; broadcast 후 첫 주 이전 행도 DEFAULT로 명시 채움(빈칸 누락 방지)"

patterns-established:
  - "주봉 신호 계단형화: 진행형(week-to-date) 컬럼 대신 ema_week_to_date/macd_oscillator_week_to_date를 week_close_mask 행에서 샘플링해 완성 주 시퀀스를 만들고 ffill broadcast"

requirements-completed: [IMPULSE-01, IMPULSE-02, IMPULSE-03, IMPULSE-04]

# Metrics
duration: ~10min
completed: 2026-06-16
---

# Phase 05: weekly-impulse-stepwise Summary

**주봉 임펄스를 매일 출렁이던 진행형에서 금-금 주간 계단형 신호로 전환 — 같은 주 내 모든 거래일이 직전 완성 주의 부호 조합으로 동일 값을 갖고, 일봉 임펄스·진행형 표시 컬럼은 무손상.**

## Performance

- **Duration:** ~10분 (코드+테스트 실행), 이후 수기 시각 검증 체크포인트
- **Started:** 2026-06-16 11:09 (+0900)
- **Completed:** 2026-06-16 (수기 검증 approved)
- **Tasks:** 3 (auto×2 + human-verify×1)
- **Files modified:** 3

## Accomplishments
- `impulse.py` 주봉부를 `_weekly_impulse_series` 헬퍼로 교체: `week_close_mask`로 주 마지막 거래일(금/휴장 시 실제 마지막일)을 잡아 `ema_week_to_date(Close,11)`·`macd_oscillator_week_to_date(Close)`를 샘플링 → 직전 완성 주 대비 diff 부호를 `decide_impulse`에 투입 → `reindex(daily_index, method='ffill')`로 주중 broadcast (계단형).
- `main_run.py` ~150행 허위 주석("impulse.py 가 이 컬럼을 읽음") 제거. 진행형 표시 컬럼 산출 라인은 D4에 따라 불변.
- 신규 7종 테스트(계단형 nunique==1 / 부호 녹·적 / 금요일 휴장 목요일 경계 / 첫주 DEFAULT / 진행형 회귀 `_compute_enriched` 파이프라인 / 시트1↔종목시트 iloc[-1] 경로) + 기존 테스트 DatetimeIndex 정비.
- 실제 워크북 시각 검증: 종목 시트 (주)임펄스 계단형, 시트1 셀 = 종목 시트 최신(6행, 내림차순) 값 일치, (일)임펄스 매일 변동, 금요일 휴장 무빈칸 — 사용자 approved.

## Task Commits

1. **Task 1: 주봉 임펄스 금-금 계단형 교체 (impulse.py + main_run 주석)** - `c5d930b` (feat)
2. **Task 2: 계단형·금요일휴장·첫주·부호·진행형회귀·시트1경로 테스트** - `5f893c7` (test)
3. **Task 3: 실제 .xlsx 수기 시각 검증** - 코드 변경 없음 (사용자 approved)

_TDD: Task 1은 RED(테스트 정비)→GREEN(impulse.py 교체) 단일 게이트로 진행._

## Files Created/Modified
- `src/stocksig/compute/impulse.py` - 주봉 임펄스 산출을 계단형으로 교체(일봉부 불변)
- `src/stocksig/main_run.py` - 임펄스 입력 관련 허위 주석 갱신(진행형 컬럼 산출 라인 불변)
- `tests/test_impulse.py` - 신규 계단형/금요일휴장/첫주/부호/진행형회귀(파이프라인)/시트1경로 테스트 + DatetimeIndex 정비

## Decisions Made
None beyond the plan — D1/D2/D4 LOCKED 결정을 그대로 따름. 산출 로직을 private 헬퍼 `_weekly_impulse_series`로 분리(Claude's Discretion).

## Deviations from Plan
None - plan executed exactly as written.

## Issues Encountered
None. 전체 pytest 251 passed (exit 0), tests/test_impulse.py 10 passed.

## User Setup Required
None - 외부 서비스 구성 불필요 (내부 순수 계산 변경).

## Next Phase Readiness
- 표시 배선(sheet_portfolio.py/sheet_per_ticker.py)은 코드 변경 없이 계단형 데이터를 반영함이 확인됨.
- **범위 외 추가 작업(사용자 요청, 별도 커밋 `3068058`):** 종목 시트 A열(날짜) 가로 고정 + `yyyy-mm-dd (요일)` 서식 — phase 05와 무관한 출력 표시 개선으로 분리 처리됨(테스트 freeze 회귀 A6→B6, add_format 44→45 갱신 포함).
- **후속 예정:** 시트1 '기업명' 열 추가(미국=영어 yfinance / 한국=한글 DART·네이버) — 데이터 조회 경로 신설 + 컬럼 인덱스 시프트 리팩터 필요 → 신규 페이즈로 계획.

---
*Phase: 05-weekly-impulse-stepwise*
*Completed: 2026-06-16*
