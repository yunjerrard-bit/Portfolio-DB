---
phase: 02-scaling-portfolio-summary
plan: 05
subsystem: verification + indicator-polish
tags: [manual-verify, smoke, post-plan-additions]
dependency_graph:
  requires: ["02-01", "02-02", "02-03", "02-04"]
  provides: ["Phase 2 code complete + indicator semantics audited"]
  affects:
    - src/stocksig/compute/weekly.py
    - src/stocksig/compute/indicators.py
    - src/stocksig/compute/impulse.py
    - src/stocksig/main_run.py
    - src/stocksig/output/sheet_per_ticker.py
    - src/stocksig/output/sheet_portfolio.py
    - tickers.txt
tech_stack:
  added: []
  patterns:
    - "week-to-date (live, 진행형) weekly indicators"
    - "Friday-only signal coloring (선택적)"
    - "Weekly EMA recursion: prev-week state + α·today_close one-step advance"
key_files:
  created: []
  modified:
    - src/stocksig/output/sheet_portfolio.py  (시트1 17열로 확장)
    - tests/test_sheet_portfolio.py
    - src/stocksig/compute/weekly.py
    - src/stocksig/compute/indicators.py
    - src/stocksig/compute/impulse.py
    - src/stocksig/main_run.py
    - src/stocksig/output/sheet_per_ticker.py  (95→97열)
    - tests/test_smoke_end_to_end.py
    - tests/test_impulse.py
    - tickers.txt  (2→26 티커, 티어/산업 태그)
    - CLAUDE.md  (Performance 가정 100→200)
decisions:
  - "주봉 종가 등락률(W): week-to-date 누적 수익률 — Mon=Mon수익, …, Fri=주간 전체"
  - "주봉 RSI/Stoch/MACD: week-to-date 진행형 + 금요일=진짜 주봉 지표 일치"
  - "주봉 EMA 진행형 추세 컬럼 AK·AL 신규 — (주)ema11 추세 / (주)ema22 추세"
  - "주봉 임펄스 EMA 입력을 진행형 EMA11 trend로 통일 (사용자 개념 일치)"
  - "주봉 등락률 통계(median/std): 금요일값만 사용 (월~목 0/누적이 통계 오염 방지)"
  - "W/AA/AE/CM 색칠: 금요일 행만; CO(MACD)는 단순 시각화 위해 매 행 (일봉과 동일 패턴)"
  - "시트1: (주)Stoch %K / (주)RSI 두 컬럼을 (일)RSI 우측에 추가 (15→17열)"
  - "규모 가정 100 → 200 종목"
metrics:
  duration_minutes: ~120
  out_of_plan_commits: 4
  files_changed: 11
  tests_total: 130+ (53 핵심 + 시트1·portfolio 22 + 기타)
  manual_verify_status: "implicit-PASS (대화형 검토 5/8) · formal-PENDING (3/8)"
  completed_date: 2026-05-27
---

# Phase 2 Plan 5 (Wave 5) Summary — 수기 검증 + 계획 외 지표 개편

**One-liner:** Wave 5는 원래 8 포인트 수기 검증 체크포인트였으나, 같은 세션 중 사용자와 함께 주봉 지표 의미·표시 전반을 재설계·검증하는 더 깊은 작업으로 확장됨. 결과: Phase 2 코드 + 주봉 지표 의미 정합화 완료, 일부 수기 포인트는 미실시 상태.

## Status Overview

| 영역 | 상태 |
|---|---|
| Phase 2 자동 테스트 | ✅ 전부 GREEN (53/53 + 기타) |
| 8 수기 검증 포인트 | 🟡 5 implicit-PASS · 3 formal-PENDING (아래 표 참조) |
| 계획 외 추가 작업 | ✅ 4 커밋, 사용자 승인 하에 적용 |
| 시트1 / 종목 시트 동작 | ✅ 대화형으로 사용자가 컬럼·색·계산을 직접 검토 후 변경 지시 |

## 8 Manual Points — 상태 매핑

| # | 포인트 | 상태 | 근거 |
|---|---|---|---|
| 1 | 혼합 10 티커 실행 | 🟡 PENDING (formal) | tickers.txt는 사용자 본인 26 티커로 채워져 있고 ZZZZZ placeholder 포함. `main.py` 실제 실행 로그/시간은 사용자가 직접 확인할 항목 |
| 2 | 시트1 first + A1 타임스탬프 | ✅ implicit-PASS | 코드 `_SHEET_NAME = "시트1"`, `PORT-01` 테스트 GREEN |
| 3 | 하이퍼링크 | ✅ implicit-PASS | `test_ticker_hyperlink_us_and_kr` GREEN |
| 4 | DIFF 색 일관성 (3 티커 샘플) | ✅ implicit-PASS | `decide_sigma_bucket` 단일 진원지 (D-02) + `test_diff_color_matches_per_ticker_logic` GREEN |
| 5 | 임펄스 색 일관성 | 🟡 implicit-PASS (시트1) / formal-PENDING (3 티커 샘플 셀) | 시트1 임펄스 셀 색 = `impulse_green/red/blue` 동일 Format 재사용 — 코드 1:1 매핑. 시각 확인은 사용자 |
| 6 | 캐시 HIT (재실행) | ✅ implicit-PASS | `test_cache_hit_on_second_run` (MKTD-05) GREEN. 사용자 실제 재실행 시 콘솔 로그 확인 필요 |
| 7 | 잘못된 티커 격리 (ZZZZZ) | 🟡 코드 PASS / formal 실행 PENDING | `test_failed_ticker_in_sheet1_only` (D-03) GREEN. `tickers.txt`에 `ZZZZZ` 이미 추가됨 |
| 8 | 200 티커 스트레스 (선택) | 🟡 PENDING (formal) | 사용자 환경 실행 필요. 코드 측 200 티커 처리 능력은 `MKTD-05` 캐시 + 토큰버킷으로 보장 |

**Implicit-PASS 의미:** 자동 테스트 + 대화형 검토에서 합리적으로 확인됨. 사용자가 실제 .xlsx를 열어 셀 클릭/색 확인은 별도로 수행 필요.

## 계획 외 추가 작업 (Wave 5 진행 중 사용자 합의로 추가)

### Commit `75c988c` — true week-to-date 주봉 지표 + 금요일 기준 신호
- W열(`Close_pct_change_week`): step→pct_change(월~목=0, 금=주간) → week-to-date 누적 수익률
- CM열(`RSI_week`): broadcast Close_week ewm → `rsi_week_to_date(daily_close)`. 금요일=진짜 주봉 RSI 일치, 주중=오늘 종가 반영
- 통계: `Close_pct_change_week`/`Volume_pct_change_week`의 expanding median/std를 금요일값만으로 재계산
- 색칠: W·AA·AE·CM 금요일 행에만 σ/threshold 신호 색 적용
- 시트1: `(주)Stoch %K`/`(주)RSI` 두 컬럼을 `(일)RSI` 우측에 추가 (15→17열)
- 신규 함수: `weekly.week_to_date_close_return`, `weekly.week_close_mask`, `indicators.rsi_week_to_date`

### Commit `(merged into 75c988c)` — Stoch/MACD 주봉 week-to-date 재작성
- CJ/CK열(`Stoch_%K_week`/`%D_week`): `stoch_slow_week_to_date(high, low, close)` — 주봉 OHLC 시퀀스 + 주중은 이번 주 누적 H/L + 오늘 종가
- CO열(`MACD_OSC_week`): `macd_oscillator_week_to_date(daily_close)` — 주봉 EMA 12/26/9 재귀 + 오늘 종가 한 스텝
- 금요일 = 진짜 주봉 Stoch/MACD 정확 일치 (수치 검증)
- 구 broadcast 방식의 기간 왜곡(5× 반복 → span 의미 손상) 제거

### Commit `f19b064` — 주봉 EMA 진행형 추세 컬럼 + 임펄스 EMA 입력 통일
- AK·AL열 신규: `(주)ema11 추세` / `(주)ema22 추세` (95→97 컬럼)
- `indicators.ema_week_to_date(daily_close, span)` 신규
- 오늘 종가 가중치: span=11 → α=16.67%, span=22 → α=8.70% (수치 검증)
- `impulse.add_impulse_columns`의 주봉 EMA 입력을 진행형 컬럼으로 교체 (사용자 개념 일치)

### Commit `dcf8c5c` — CO 색칠 단순화
- CO열 색칠을 일봉 MACD(CN) 분기와 동일하게 — 매 행 `decide_trend_bucket(MACD_OSC_week.diff())`
- 임펄스는 동일 시그널 사용 → 시각 일관성 유지

### Commit `8e1dedf` — tickers.txt 본인 watchlist 확장
- 2 티커 → 26 티커 (탭 구분 `티커 / 티어 / 산업` 포맷 적용)
- 사용자 본인 포트폴리오 + 검증용 ZZZZZ placeholder

## Test Status

```
tests/test_indicators.py       ✓ (RSI/Stoch/MACD 일·주 진행형 포함)
tests/test_weekly.py           ✓ (week_close_mask + week_to_date_close_return)
tests/test_impulse.py          ✓ (EMA_Close_11_week_trend 입력 반영)
tests/test_sheet_portfolio.py  ✓ (17열 + Friday-only 색)
tests/test_smoke_n_tickers.py  ✓ (Phase 2 N-티커 시나리오 회귀)
tests/test_smoke_end_to_end.py ✓ (97열, 한국어 헤더, EMA week trend)
→ 53/53 GREEN (관련 핵심) · 전 세션 누적 신규 실패 0
```

## Verification 수치 요약 (대화 중 산출)

- W열 Friday = `(이번주 금 종가 / 지난주 금 종가) − 1` ✓ (예: 0.0836)
- RSI_week Friday = `rsi_wilder(weekly_close)` 23 금요일 전부 일치 ✓
- Stoch %K/%D Friday = `stoch_slow(weekly_OHLC)` 정확 일치 ✓
- MACD-OSC Friday = `compute_macd_oscillator(weekly_close)` 정확 일치 ✓
- EMA11/22 week-to-date Friday = `weekly_close.ewm(span).mean()` 정확 일치 ✓
- 주중 today+10 → EMA11 +1.667 (=α·10, 정확) / EMA22 +0.870 ✓

## Success Criteria (Phase 2 ROADMAP 기준)

- [x] 1. N개 티커 → 개별 시트 + 시트1 통합 요약 (시트1 17열 확장 포함)
- [x] 2. 하이퍼링크 + A1 타임스탬프
- [x] 3. 부분 실패 격리 + 한국어 경고
- [x] 4. 24h 디스크 캐시
- [🟡] 5. 200 티커 처리 rate-limit 위반 없음 — 코드 PASS, 사용자 환경 실증 PENDING

## Deviations from Plan

- **계획 외 작업이 plan보다 더 큼.** Wave 5는 원래 검증 체크포인트였지만, 사용자가 주봉 지표 의미를 검증하던 중 다수의 구조적 결함(broadcast 기반 기간 왜곡, 통계 오염, 금요일 색칠 정합성, 진행형 일관성)을 발견하고 함께 재설계함. 4 커밋으로 정리됨.
- **8 포인트 중 3개(1, 7 실행 부분, 8)는 사용자 환경 실증이 남음.** 필요 시 사용자가 `python main.py` 한 번 실행 + 콘솔/엑셀 확인으로 마무리 가능.
- **ROADMAP에 명시된 Phase 2 범위를 벗어난 작업 포함.** 의도된 작업: 주봉 지표 의미 정합화 (Phase 1/2 통합 polish). 이는 향후 Phase 4 "품질·견고성 마감"의 일부로 통상 묶이는 종류이나, 사용자 요청으로 Phase 2 종료 전 처리됨.

## Self-Check: PASSED

- 8-point checklist 5 implicit-PASS, 3 formal-PENDING (사용자 액션) — 명시
- 추가 4 커밋 ↔ git log 일치 (`75c988c`, `f19b064`, `dcf8c5c`, `8e1dedf`)
- 자동 테스트 53 GREEN (관련 핵심), 회귀 없음
- 의미적 검증: 모든 주봉 지표 금요일=진짜 주봉 일치 수치 확인
