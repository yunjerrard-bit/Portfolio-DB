---
phase: 04-quality-robustness
verified: 2026-06-12T10:00:00Z
status: passed
score: 9/9 must-haves verified
overrides_applied: 0
re_verification:
  previous_status: gaps_found
  previous_score: 8/9
  gaps_closed:
    - "ping 예외 사유에 EDGAR UA/DART 키 원문이 fundamentals.py per-ticker 경로에서 노출되지 않음 (CR-01): 커밋 48f16be에서 수정 완료, 회귀 테스트 2개 추가, 244 passed 확인"
  gaps_remaining: []
  regressions: []
---

# Phase 4: 품질·견고성 마감 검증 보고서

**Phase Goal:** 일상 사용 품질로 마감. 누락·부분수신·인증실패를 콘솔 최종 요약 블록·시트1 실패행·셀 주석으로 한 곳에서 확인하고(D-01: 별도 시트 미생성), 1~5행 frozen panes를 적용하며, 콘솔 로그는 한국어로 진행률·캐시 hit/miss·실패 요약을 출력한다. 색상 톤은 강렬하지 않은 파스텔로 시각 검증한다.

**검증 일시:** 2026-06-12T10:00:00Z  
**상태:** passed  
**재검증 여부:** 예 — 갭 클로저 후 재검증 (최초 검증: 2026-06-12T08:30:00Z)

---

## 재검증 요약 (갭 클로저 확인)

| 항목 | 이전 상태 | 현재 상태 | 근거 |
|------|-----------|-----------|------|
| 진실9 (CR-01): fundamentals.py per-ticker 예외 보간 | ✗ FAILED | ✓ VERIFIED | 커밋 48f16be 수정 + 회귀 테스트 2개 GREEN |

**클로저 커밋:** `48f16be`  
**수정 내용:**
- `src/stocksig/io/fundamentals.py` US 외곽 except (L342-348): `logger.warning`에 `type(e).__name__` 만 사용, `_empty_result`는 고정 사유 `"조회 실패: 데이터 소스 오류"` 사용
- `src/stocksig/io/fundamentals.py` KR 외곽 except (L373-378): 동일 패턴 적용
- `src/stocksig/runner.py` (L98-103): 동일 패턴 적용
- `tests/test_fundamentals.py`: 누설 회귀 테스트 2개 추가
**전체 회귀:** 244 passed (오케스트레이터 확인, 2026-06-12) / `tests/test_fundamentals.py` 단독 실행 31 passed

---

## 검증 방법론 요약

ROADMAP.md Phase 4 성공기준(SC1~SC4) 4개 + PLAN 머스트해브(04-01/02/03)를 목표 역방향으로 추적. 아티팩트 존재·실체성·배선·데이터 흐름(Level 1~4)을 직접 코드 읽기로 확인. 오케스트레이터 확인 사항(244개 테스트 통과, 수기 검증 approved)을 보조 증거로 사용.

---

## 관측 가능한 진실(Truths) 검증

| # | 진실 | 상태 | 근거 |
|---|------|------|------|
| 1 | 모든 시트의 1~5행이 frozen 처리됨 | ✓ VERIFIED | `sheet_per_ticker.py:438` `ws.freeze_panes(5,0)` / `sheet_portfolio.py:303` `ws.freeze_panes(5,1)` 구현됨. `test_freeze_panes.py` 3개 테스트(test_all_sheets_freeze_rows_1_to_5, test_portfolio_sheet_freezes_rows_and_col_a, test_per_ticker_sheet_freezes_rows_only)가 openpyxl로 읽어 B6/A6 단언. 수기 검증 approved(2026-06-12). |
| 2 | 종목별 이슈가 (a) 콘솔 최종 실패 요약 블록 (b) 시트1 실패행 (c) 셀 주석으로 확인됨 (D-01: 별도 시트 미생성) | ✓ VERIFIED | (a) `main_run.py:319` `실행 요약` 블록 + `:339` 실패 티커 목록 출력. (b) 시트1 실패행은 Phase 2에서 구현. (c) 셀 주석은 Phase 3에서 write_comment로 구현. REQUIREMENTS.md EXEC-04가 D-01로 갱신됨. |
| 3 | 200 티커 실행 종료 시 콘솔에 한국어 진행률·캐시 hit/miss·최종 실패 요약 블록 출력 | ✓ VERIFIED | `main_run.py:319-340` 실행 요약 블록에 `티커:` / `인증:` / `캐시:` 줄 + failures>0 시 `실패 티커:` 줄. `cache.py`에 lock-보호 `_stats` 카운터 + `reset_cache_stats/get_cache_stats`. `test_summary_block_emitted` 테스트가 각 줄을 caplog으로 단언(green). 실데이터 25 티커 실행 로그 확인(오케스트레이터 확인). |
| 4 | 색상 톤이 파스텔/소프트이며 그레이스케일에서 ±1σ/±2σ 구분 가능 | ✓ VERIFIED | `test_color_tone.py`의 WCAG relative luminance 테스트: HARD 배경(GREEN_100 vs RED_100) 휘도차 0.0351 > 임계 0.03 통과. SOFT 글자색 휘도차 0.0180 > 하한 0.01 통과. 수기 시각 검증 approved(파스텔/흑백 구분, 2026-06-12). |
| 5 | 매 실행 시작 시 US/KR 티커에 따라 조건부 EDGAR/DART ping 1회씩 실행 | ✓ VERIFIED | `main_run.py:256-261` markets 집합 판단 후 조건부 ping_edgar/ping_dart. `test_ping_edgar_called_when_us_ticker`, `test_ping_conditional_us_only`, `test_ping_conditional_kr_only` 테스트 green. |
| 6 | ping 실패 시 raise없이 경고 후 계속, 실패 소스 1차 펀더멘털 스킵·yf 폴백 유지 | ✓ VERIFIED | `auth_check.py:80-88,117-127` 모두 except Exception 흡수·고정 사유 반환. `main_run.py:265-272` skip 클로저. `test_ping_failure_continues_and_builds_workbook`, `test_ping_failure_propagates_skip_edgar` green. |
| 7 | ping 예외 사유에 EDGAR UA/DART 키 원문이 auth_check에서 절대 포함되지 않음 | ✓ VERIFIED | `auth_check.py:41-43` 고정 상수만 사용. `test_source_notes_have_no_exception_interpolation` 소스 grep 단언. `test_ping_edgar_ua_not_leaked`, `test_ping_dart_key_not_leaked` 보안 테스트 green. |
| 8 | 종료부 요약 블록에 인증 상태(EDGAR/DART) 줄 포함 | ✓ VERIFIED | `main_run.py:325-329` `인증: EDGAR %s \| DART %s` 출력. `test_summary_has_auth_line` / `test_summary_auth_line_no_secret_leak` green. |
| 9 | ping 예외 사유에 EDGAR UA/DART 키 원문이 fundamentals.py per-ticker 경로에서 노출되지 않음 | ✓ VERIFIED | **커밋 48f16be 수정 확인.** `fundamentals.py:345-348` (US): `logger.warning(..., type(e).__name__)` + `_empty_result("조회 실패: 데이터 소스 오류")`. `fundamentals.py:374-378` (KR): 동일 패턴. `runner.py:99-103`: 동일 패턴. 회귀 테스트 `test_fetch_fundamentals_exception_no_secret_leak` / `test_fetch_fundamentals_us_exception_no_secret_leak` 모두 PASSED (secret 문자열이 caplog.text 및 cell.note에 없음을 단언). |

**점수: 9/9 진실 검증됨**

---

## 필수 아티팩트 검증

| 아티팩트 | 설명 | 상태 | 비고 |
|---------|------|------|------|
| `src/stocksig/io/cache.py` | lock-보호 hit/miss 카운터 + reset/get | ✓ VERIFIED | `_stats`, `_stats_lock`, `reset_cache_stats`, `get_cache_stats` 모두 존재. get_ohlcv/get_fund 각 HIT/MISS 분기에 lock-guarded `+=1`. |
| `src/stocksig/main_run.py` | 종료부 실행 요약 블록 + 시작부 reset + 조건부 ping + skip 클로저 | ✓ VERIFIED | `cache.reset_cache_stats()` 시작부, `실행 요약` 블록, `인증:` 줄, `실패 티커:` 줄 모두 존재. |
| `tests/test_freeze_panes.py` | OUT-04 frozen panes openpyxl 회귀 테스트 | ✓ VERIFIED | 파일 존재, freeze_panes 단언 3개, B6/A6 문자열 확인. |
| `tests/test_color_tone.py` | WCAG 휘도 그레이스케일 구분 테스트 | ✓ VERIFIED | WCAG 0.2126 계수 구현, HARD/SOFT 버킷 4개 테스트. |
| `src/stocksig/io/auth_check.py` | ping_edgar/ping_dart raise금지 + AuthStatus | ✓ VERIFIED | AuthStatus dataclass, ping 함수들, except Exception 흡수, fetch_*_cached 미사용. |
| `src/stocksig/io/fundamentals.py` | skip_edgar/skip_dart 인자 + T-04-03 예외 보간 금지 | ✓ VERIFIED | L294-295 skip 인자 정의됨, _fill_us/_fill_kr 각각에 skip 분기 존재. 외곽 except 2곳 모두 type(e).__name__ 로깅 + 고정 사유 note 사용(커밋 48f16be). |

---

## 핵심 링크 검증

| From | To | Via | 상태 | 비고 |
|------|-----|-----|------|------|
| `main_run.py` | `cache.py` | `reset_cache_stats()` 시작부 + `get_cache_stats()` 종료부 | ✓ WIRED | L249, L318 확인 |
| `main_run.py` | `auth_check.py` | `ping_edgar()` / `ping_dart()` 조건부 호출 | ✓ WIRED | L259, L261 확인 |
| `main_run.py` | `fundamentals.py` | `_fundamentals_with_auth` 클로저 → skip_edgar/skip_dart 주입 | ✓ WIRED | L265-272, L277 확인 |
| `tests/test_freeze_panes.py` | `sheet_per_ticker.py` / `sheet_portfolio.py` | run() end-to-end → openpyxl load_workbook | ✓ WIRED | 테스트가 실제 run() 호출 후 openpyxl로 읽어 단언 |
| `tests/test_color_tone.py` | `color_rules.py` | `GREEN_100/RED_100/GREEN_800/RED_800` import | ✓ WIRED | L27-34 import 확인 |
| `tests/test_fundamentals.py` (CR-01 회귀) | `fundamentals.py` 외곽 except | `fetch_fundamentals` 직접 호출 + caplog 단언 | ✓ WIRED | `test_fetch_fundamentals_exception_no_secret_leak`, `test_fetch_fundamentals_us_exception_no_secret_leak` PASSED |

---

## 요구사항 커버리지

| 요구사항 ID | 플랜 | 설명 | 상태 | 근거 |
|------------|------|------|------|------|
| EXEC-04 | 04-01, 04-03 | 종목별 이슈를 (a) 콘솔 요약 (b) 시트1 실패행 (c) 셀 주석으로 확인 (D-01 반영) | ✓ SATISFIED | (a) 실행 요약 블록 구현됨. (b) 시트1 실패행 Phase 2. (c) write_comment Phase 3. D-01 문서 정합 완료. CR-01 보안 갭 클로저 완료(커밋 48f16be). |
| OUT-04 | 04-02 | 모든 시트 1~5행 frozen | ✓ SATISFIED | sheet_per_ticker.py:438 + sheet_portfolio.py:303 구현됨. openpyxl 회귀 테스트 3개 green. 수기 검증 approved. |

---

## 데이터 흐름 추적 (Level 4)

| 아티팩트 | 데이터 변수 | 소스 | 실데이터 생성 여부 | 상태 |
|---------|-----------|------|-----------------|------|
| `main_run.py` 실행 요약 블록 | `stats` (cache.get_cache_stats()) | `cache.py _stats` dict (모든 HIT/MISS 분기에서 증가) | ✓ 실 카운터 | ✓ FLOWING |
| `main_run.py` 인증 요약 줄 | `auth` (AuthStatus 인스턴스) | ping_edgar/ping_dart 반환값 | ✓ 실 ping 결과 | ✓ FLOWING |
| `tests/test_freeze_panes.py` | freeze_panes 값 | openpyxl.load_workbook(out) 결과 | ✓ 실 워크북 읽기 | ✓ FLOWING |

---

## 행동 스팟 체크

| 행동 | 근거 | 상태 |
|------|------|------|
| cache.reset_cache_stats() 후 get_cache_stats()는 {0,0,0,0} 반환 | test_cache.py: reset 후 모든 값 0 단언 (5개 테스트 green) | ✓ PASS |
| 실행 요약 블록에 "실행 요약"/"티커:"/"캐시:" 포함 | test_summary_block_emitted green | ✓ PASS |
| OUT-04: freeze_panes("시트1")=="B6", 종목 시트=="A6" | test_freeze_panes.py 3개 테스트 green | ✓ PASS |
| WCAG HARD 배경 휘도차 > 0.03 | test_hard_buckets_distinguishable_grayscale green | ✓ PASS |
| ping 실패 시 skip_edgar=True 전파 | test_ping_failure_propagates_skip_edgar green | ✓ PASS |
| fundamentals.py 예외 보간에서 API 키 미노출 (CR-01) | 커밋 48f16be 코드 직접 확인 + 회귀 테스트 2개 PASSED | ✓ PASS |

---

## 안티패턴 스캔

| 파일 | 라인 | 패턴 | 심각도 | 영향 |
|------|------|------|--------|------|
| `src/stocksig/io/auth_check.py` | 84 | `"403" in str(e)` 문자열 매칭 | ⚠️ WARNING | WR-03: 구조화된 httpx 예외 비활용, URL 경로의 "403" 문자열에 오판 가능. 기능상 현재 테스트는 통과하지만 취약한 방어. |
| `tests/test_freeze_panes.py` | 65-86 | ping stub 누락 (WR-05) | ⚠️ WARNING | 테스트가 실제 SEC에 httpx GET 시도. 오프라인에서 타임아웃만큼 느려짐. smoke 패턴 회귀. |

**이전 블로커 항목 (CR-01) 해소됨:**
- `fundamentals.py:343,344,370,371` — 커밋 48f16be에서 `type(e).__name__` + 고정 사유로 수정 완료.
- `runner.py:99-100` — 동일 커밋에서 수정 완료.

**채무 마커(TBD/FIXME/XXX) 미발견** — 관련 파일 스캔 결과 공식 follow-up 없는 미해결 마커 없음.

---

## 인간 검증 항목

*자동화 검증 완료 항목*: 사용자가 2026-06-12에 04-02 수기 검증 체크포인트를 "approved"로 승인 (frozen panes 육안, 파스텔 톤, 흑백 방향 구분 확정).

현재 추가적인 인간 검증 항목 없음.

---

## 전체 판정

**상태: PASSED**

Phase 4의 모든 9개 진실이 코드베이스에서 검증됨.

- 핵심 기능(frozen panes, 한국어 요약 블록, EDGAR/DART 인증 사전검증, 색상 톤 검증, 캐시 통계, D-01 문서 정합)은 코드베이스에 실체적으로 구현되고 테스트가 통과됨.
- T-04-03(API 키 누설 방지) 위협이 `fundamentals.py` per-ticker 외곽 except 2곳 및 `runner.py`에서 커밋 48f16be로 완전히 차단됨.
- 회귀 테스트 `test_fetch_fundamentals_exception_no_secret_leak` / `test_fetch_fundamentals_us_exception_no_secret_leak` 추가 및 PASSED 확인.
- 전체 회귀 244 passed (오케스트레이터 확인, 2026-06-12).

수기 검증 approved(2026-06-12). 갭 없음. 다음 단계 진행 가능.

**9개 진실 중 9개 검증됨.**

---

_최초 검증: 2026-06-12T08:30:00Z_  
_재검증: 2026-06-12T10:00:00Z (갭 클로저 커밋 48f16be 확인)_  
_검증자: Claude (gsd-verifier)_
