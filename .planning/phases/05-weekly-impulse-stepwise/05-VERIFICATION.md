---
phase: 05-weekly-impulse-stepwise
verified: 2026-06-16T00:00:00+09:00
status: passed
score: 4/4 must-haves verified
overrides_applied: 0
---

# Phase 05: weekly-impulse-stepwise 검증 보고서

**페이즈 목표:** 사용자가 주봉 임펄스를 진행형(매일 출렁임)이 아닌 금요일-대-금요일 주간 신호로 보게 된다 — 시트1·종목 시트 모두에서 한 주 동안 같은 값으로 고정되고, 다음 주 마지막 거래일에만 갱신된다.
**검증일:** 2026-06-16
**상태:** PASSED
**재검증 여부:** 아니오 — 최초 검증

---

## 목표 달성 여부

### 관찰 가능한 진실(Must-Have Truths)

| # | 진실 | 상태 | 근거 |
|---|------|------|------|
| 1 | 종목 시트의 주봉 임펄스 열이 한 주 내 모든 거래일에서 동일 값(녹/적/청/빈칸)으로 표시된다 (계단형) | VERIFIED | `impulse.py:63` — `reindex(df.index, method="ffill")` 로 주중 broadcast. `test_weekly_impulse_stepwise_same_value_within_week` (nunique==1 단언) PASS |
| 2 | 주봉 임펄스 값은 주 마지막 거래일(금, 휴장 시 그 주 실제 마지막 거래일) 시점 주봉 EMA11·주봉 MACD-OSC의 직전 완성 주 대비 변화 부호 조합으로 결정된다 | VERIFIED | `impulse.py:40-58` — `week_close_mask`로 샘플링, `.diff()` 부호 → `decide_impulse`. `test_weekly_impulse_sign_green_on_accelerating_uptrend` / `test_weekly_impulse_sign_red_on_accelerating_downtrend` PASS |
| 3 | 금요일 휴장 주에도 빈칸·오산출 없이 그 주 실제 마지막 거래일을 경계로 임펄스가 산출·고정된다 | VERIFIED | `impulse.py:40` — `week_close_mask`가 목요일을 True로 처리(기존 구현 재사용). `test_weekly_impulse_friday_holiday_no_gap` (nunique==1, notna().all() 단언) PASS |
| 4 | 시트1 통합 포트폴리오의 각 티커 (주)임펄스 셀이 해당 종목 시트의 최신 주봉 임펄스 값과 일치한다 | VERIFIED | `test_sheet1_path_matches_per_ticker_stepwise` — `df.iloc[-1]["Impulse_weekly"]` == `last.get("Impulse_weekly")` 단언 PASS. Task 3 수기 시각 검증 사용자 approved |
| 5 | 일봉 임펄스·진행형 주봉 추세 컬럼(EMA_Close_11_week_trend/MACD_OSC_week 등)은 v1.0과 동일하게 매일 변동한다 (회귀 무손상) | VERIFIED | `test_progressive_week_columns_unchanged_in_pipeline` — `_compute_enriched(mock_ohlcv_df)` 결과에서 두 컬럼 존재 + 주중 변동(nunique>1) 단언 PASS |

**점수:** 4/4 요구사항 검증 (진실 5개 전부 VERIFIED)

---

## 필수 아티팩트

| 아티팩트 | 역할 | 상태 | 세부 내용 |
|---------|------|------|---------|
| `src/stocksig/compute/impulse.py` | 금-금 부호 조합 + week_close_mask 샘플링 + ffill broadcast 기반 주봉 임펄스 산출 | VERIFIED | `_weekly_impulse_series` 헬퍼(30-64행) + 신규 import 3종 존재. 일봉부 불변 확인 |
| `tests/test_impulse.py` | 계단형/금요일휴장/첫주DEFAULT/부호/진행형회귀(파이프라인)/시트1경로 신규 케이스 | VERIFIED | 신규 7개 테스트 포함 총 10개 테스트, 전부 PASS |

---

## 키 링크(Key Link) 검증

| From | To | Via | 상태 | 세부 내용 |
|------|-----|-----|------|---------|
| `impulse.py` | `color_rules.py` | `decide_impulse` 부호 조합 재사용 | WIRED | `impulse.py:22` import + 54·86행에서 호출 |
| `impulse.py` | `weekly.py` | `week_close_mask` 로 주 마지막 거래일 샘플링 | WIRED | `impulse.py:27` import + 40행에서 호출 |
| `impulse.py` | `indicators.py` | `ema_week_to_date` / `macd_oscillator_week_to_date` 샘플링 | WIRED | `impulse.py:23-26` import + 41·42행에서 호출 |

---

## IMPULSE 요구사항별 판정

| 요구사항 | 설명 | 상태 | 근거 |
|---------|------|------|------|
| IMPULSE-01 | 주봉 임펄스를 주 마지막 거래일(금/휴장 시 실제 마지막) 기준 직전 완성 주 대비 주봉 EMA11·MACD-OSC 변화 부호 조합으로 산출 (둘↑녹/둘↓적/혼조청) | MET | `impulse.py:40-58` 구현 + 녹·적 부호 테스트 PASS |
| IMPULSE-02 | 주중 행이 직전 완성 주 값으로 ffill 고정 (계단형) | MET | `impulse.py:63` reindex ffill + `test_weekly_impulse_stepwise_same_value_within_week` PASS |
| IMPULSE-03 | 시트1·종목 시트 주봉 임펄스가 주 단위 계단형이고 두 시트 값 일치 | MET | `test_sheet1_path_matches_per_ticker_stepwise` PASS + 사용자 수기 시각 검증 approved (Task 3) |
| IMPULSE-04 | 일봉 임펄스·진행형 주봉 추세 컬럼 매일 변동 (회귀 무손상) | MET | `test_progressive_week_columns_unchanged_in_pipeline` PASS + 전체 pytest 251 passed |

---

## 수락 기준(Acceptance Criteria) 체크

| 기준 | 검증 방법 | 결과 |
|------|---------|------|
| `week_close_mask` 코드 참조(비주석) ≥1 | `impulse.py:40` — `mask = week_close_mask(df.index)` | PASS |
| `from stocksig.compute.weekly import week_close_mask` import 존재 | `impulse.py:27` | PASS |
| `ema_week_to_date` 코드 참조(비주석) ≥1 | `impulse.py:41` | PASS |
| `macd_oscillator_week_to_date` 코드 참조(비주석) ≥1 | `impulse.py:42` | PASS |
| 주봉부가 더 이상 `EMA_Close_11_week_trend`·`MACD_OSC_week`를 임펄스 입력으로 읽지 않음 | `impulse.py` 전체 grep — 주석 내 언급(76행)만 존재, Impulse_weekly 산출 경로에서 직접 참조 없음 | PASS |
| 일봉부(`Impulse_daily = EMA_Close_11_trend + MACD_OSC.diff()`)는 변경되지 않음 | `impulse.py:83-87` — 불변 | PASS |
| `main_run.py` 진행형 컬럼 산출 라인(EMA_Close_11_week_trend 등) 존재·불변 | `main_run.py:133,135,153,154` 확인 | PASS |
| `main_run.py` 허위 주석 "impulse.py 가 이 컬럼을 읽음" 제거 | grep 0건 | PASS |
| `test_impulse.py` 모든 DataFrame index가 DatetimeIndex | 5개 신규 테스트 전부 `pd.date_range` 사용, basic/blue_mixed도 `dates` 부여 | PASS |
| `nunique` 단언 테스트 ≥1 존재 | `test_weekly_impulse_stepwise_same_value_within_week` 등 다수 | PASS |
| `mock_ohlcv_df` 사용 테스트 ≥1 | `test_progressive_week_columns_unchanged_in_pipeline`, `test_sheet1_path_matches_per_ticker_stepwise` | PASS |
| `_compute_enriched` 사용 테스트 ≥1 | 동상 | PASS |
| `Impulse_weekly` + `iloc[-1]` 단언 존재 | `test_sheet1_path_matches_per_ticker_stepwise:229-233` | PASS |
| `uv run pytest tests/test_impulse.py -x -q` exit 0 | 10 passed in 1.37s | PASS |
| `uv run pytest -q` 전체 스위트 exit 0 | 251 passed in 347.72s | PASS |

---

## 안티 패턴 검사

수정된 파일(`impulse.py`, `main_run.py`, `test_impulse.py`) 대상 검사:

- `TBD / FIXME / XXX` 마커: 없음
- `TODO / HACK / PLACEHOLDER` 마커: 없음
- `return null / return {}` 스텁: 없음
- 진행형 표시 컬럼이 `Impulse_weekly` 산출 경로에 잔존: 없음 (주석 내 언급만, 연산 경로 외)

안티 패턴 없음.

---

## 동작 스팟체크

| 동작 | 명령 | 결과 | 상태 |
|------|------|------|------|
| `tests/test_impulse.py` 전부 통과 | `uv run pytest tests/test_impulse.py -q` | 10 passed in 1.37s | PASS |
| 전체 스위트 무회귀 | `uv run pytest -q` | 251 passed in 347.72s | PASS |

---

## 수기 시각 검증 (Task 3 — 사용자 confirmed)

Task 3는 `checkpoint:human-verify` 게이트로서 PLAN에 명시된 블로킹 체크포인트였다. SUMMARY.md에 따르면 사용자가 실제 .xlsx를 열어 다음을 confirmed(approved):

- 종목 시트 (주)임펄스 열이 같은 주(월~금) 내 동일 값으로 계단형 표시됨
- 시트1 (주)임펄스 셀 = 해당 종목 시트 최신(맨 아래) (주)임펄스 값과 일치
- (일)임펄스 열은 매일 변동 유지 (회귀 무손상)
- 금요일 휴장 주에서 빈칸·오산출 없이 임펄스 채워짐

이 수기 검증은 단위 테스트(test_sheet1_path_matches_per_ticker_stepwise)로 경량 자동 커버되었으며, 시각·미적 확정은 사용자 approved로 완료되었다.

---

## 범위 외 변경 사항 (점수에 불포함)

커밋 `3068058` (종목 시트 A열 날짜 고정 + `yyyy-mm-dd (요일)` 서식)은 Phase 05 요구사항(IMPULSE-01~04)의 범위 밖이다. SUMMARY.md에서도 "phase 05와 무관한 출력 표시 개선으로 분리 처리"로 명시하였으며, 이 검증은 해당 변경을 IMPULSE 요구사항에 대해 평가하지 않는다.

---

## 요약

Phase 05 주봉 임펄스 주간화 목표가 코드베이스 상에서 완전히 달성되었다.

- `impulse.py` 주봉부가 `week_close_mask` + `ema_week_to_date` + `macd_oscillator_week_to_date` + `reindex(ffill)` 패턴으로 교체됨 (계단형 구현).
- 일봉부 및 `main_run.py` 진행형 표시 컬럼 산출 라인은 불변.
- 허위 주석 제거 완료.
- 신규 7개 테스트(계단형/금요일휴장/첫주/부호녹·적/진행형회귀/시트1경로) 포함 전체 10개 테스트 PASS.
- 전체 스위트 251 passed (exit 0).
- 사용자 수기 시각 검증 approved.

**IMPULSE-01: MET / IMPULSE-02: MET / IMPULSE-03: MET / IMPULSE-04: MET**

---

_검증일: 2026-06-16_
_검증자: Claude (gsd-verifier)_
