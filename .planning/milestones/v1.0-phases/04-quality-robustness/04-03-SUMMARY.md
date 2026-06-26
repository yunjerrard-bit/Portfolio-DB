---
phase: 04-quality-robustness
plan: 03
subsystem: io
tags: [auth, edgar, dart, ping, fundamentals, security, korean-logs, fail-fast-not]

requires:
  - phase: 03-edgar-dart-yfinance-naver
    provides: "edgar_client._resolve_identity + @throttled_edgar; dart_client._resolve_api_key/OpenDartReader + @throttled_dart; fundamentals._fill_us/_fill_kr per-metric provenance + yf/Naver 폴백"
  - phase: 04-quality-robustness (plan 01)
    provides: "main_run.run() 종료부 한국어 실행 요약 블록 + # TODO(04-03) 인증 줄 자리"
provides:
  - "io/auth_check.py — ping_edgar()/ping_dart() raise-금지 순수 함수 + AuthStatus dataclass (키/UA 미노출)"
  - "fetch_fundamentals skip_edgar/skip_dart 인자 (1차만 스킵, yf/Naver 폴백 유지, A4)"
  - "main_run.run() 조건부 인증 ping 배선(D-04) + skip 클로저(Pattern 3) + 요약 인증 줄(Pattern 5)"
affects: []

tech-stack:
  added: []
  patterns:
    - "ping 함수는 raise 금지(except Exception 흡수) + (ok, 고정 한국어 사유) tuple 반환 — fail-fast 아님(D-02)"
    - "ping 예외 사유 note 에 예외 원문 e 보간 금지 — 고정 사유만(T-04-03 키/UA 누설 방지)"
    - "EDGAR ping = httpx 직접 GET 단일 경로(@throttled_edgar) — edgartools 부수효과 혼합 금지(Pitfall 2)"
    - "DART status 013/020 = 키 유효 → OK 판정(Pitfall 4 false-negative 방지)"
    - "ping 은 캐시 쓰기 경로(fetch_*_cached) 미사용 — 캐시 미경유 가벼운 호출(Pitfall 1 캐시 오염 방지)"
    - "skip 인자 기본 False = 무회귀; skip=True 시 1차 raw 호출+기본 클라이언트 lazy import 둘 다 생략"

key-files:
  created:
    - src/stocksig/io/auth_check.py
    - tests/test_auth_check.py
    - .planning/phases/04-quality-robustness/04-03-SUMMARY.md
  modified:
    - src/stocksig/io/fundamentals.py
    - tests/test_fundamentals.py
    - src/stocksig/main_run.py
    - tests/test_smoke_n_tickers.py

key-decisions:
  - "EDGAR ping 은 httpx 직접 GET(SEC browse-edgar 소형 엔드포인트) 단일 경로로 확정 — UA 는 edgar_client._resolve_identity 재사용, raise_for_status 로 403/4xx 검출"
  - "DART ping 은 _dart_probe() 헬퍼로 분리(opendartreader list 호출) — 테스트가 status 코드만 mock 하면 되도록 외부 호출 격리"
  - "EDGAR·DART note 양쪽 모두 고정 한국어 사유('EDGAR 인증 실패'/'EDGAR 403 (UA 확인)'/'DART 인증 실패') — 예외 원문 미보간"
  - "skip 클로저는 market 매칭까지 검사(skip_edgar=(market==US and edgar_ok is False)) — KR 종목에 EDGAR skip 이 잘못 전파되지 않음"

patterns-established:
  - "인증 사전검증: 티커 로드 직후 markets 집합 → 조건부 ping → AuthStatus 누적 → skip 클로저 → 요약 인증 줄"
  - "_auth_label(ok, note): None→해당없음, True→OK, False→실패(note) — note 는 이미 sanitize 됨"

requirements-completed: [EXEC-04]

duration: 18 min
completed: 2026-06-12
---

# Phase 4 Plan 03: 인증 사전검증 수직 슬라이스 Summary

**`io/auth_check.py` 의 raise-금지 `ping_edgar()`(httpx 단일 경로)/`ping_dart()`(status 013/020 키유효 판정) + `AuthStatus` dataclass 를 만들고, `fetch_fundamentals` 에 `skip_edgar`/`skip_dart`(1차만 스킵·yf 폴백 유지) 인자를 추가한 뒤, `main_run.run()` 이 티커 로드 직후 조건부로(US/KR) ping 해 결과를 (a) 경고, (b) skip 클로저, (c) 종료 요약 인증 줄로 흘려보낸다. ping 예외/요약 줄 어디에도 EDGAR UA·DART 키 원문이 노출되지 않는다.**

## Performance

- **Duration:** ~18 min
- **Tasks:** 3 (모두 TDD: RED → GREEN)
- **Files modified:** 7 (코드 3 + 테스트 3 + SUMMARY 1)
- **New tests:** 24 (auth_check 13 + fundamentals skip 4 + smoke ping 7)

## Accomplishments
- **Task 1:** `io/auth_check.py` 신규 — `AuthStatus`(4필드 기본 None=미실행) + `ping_edgar()`(httpx 직접 GET, `@throttled_edgar`, UA=`_resolve_identity`, 403/예외 흡수) + `ping_dart()`(`_dart_probe` 경유 opendartreader list, status 013/020 키유효, 예외 흡수). 두 ping 모두 raise 금지·캐시 미경유·예외 원문 미보간.
- **Task 2:** `fetch_fundamentals(skip_edgar=False, skip_dart=False)` 추가. `_fill_us(skip_edgar)`/`_fill_kr(skip_dart)` 가 1차 raw 호출을 건너뛰고 전 지표를 결손("EDGAR/DART 인증 실패")으로 둔 뒤 yf/Naver 폴백은 그대로 실행(A4). skip=True 시 기본 클라이언트 lazy import 도 생략.
- **Task 3:** `main_run.run()` 티커 로드 직후 `markets` 집합 → 조건부 `ping_edgar`/`ping_dart`(D-04) → `AuthStatus` 누적 → `_fundamentals_with_auth` skip 클로저로 `run_all` 배선 → 종료 요약 블록(04-01 자리)에 `_auth_label` 기반 "인증: EDGAR .. | DART .." 줄 삽입.
- 전체 회귀 231 tests 전부 green(무회귀; 04-01 baseline 207 + 신규 24).

## Task Commits

각 태스크는 원자적 TDD 커밋(test → feat):

1. **Task 1 (RED): auth_check ping/AuthStatus 실패 테스트** - `b2e6348` (test)
2. **Task 1 (GREEN): auth_check.py 구현** - `abfab54` (feat)
3. **Task 2 (RED): skip_edgar/skip_dart 실패 테스트** - `73b3d7e` (test)
4. **Task 2 (GREEN): fetch_fundamentals skip 인자** - `4fa180a` (feat)
5. **Task 3 (RED): main_run 조건부 ping/skip/요약 줄 실패 테스트** - `ad74121` (test)
6. **Task 3 (GREEN): main_run ping 배선 + skip 클로저 + 인증 줄** - `7cfe004` (feat)

**Plan metadata:** SUMMARY 커밋 (이 커밋)

## Files Created/Modified
- `src/stocksig/io/auth_check.py` (신규) - `AuthStatus` dataclass + `ping_edgar`/`ping_dart` + `_edgar_probe`(@throttled_edgar httpx GET)/`_dart_probe`(@throttled_dart opendartreader list). 고정 한국어 사유 상수 + `_DART_VALID_KEY_STATUS={000,013,020}`.
- `tests/test_auth_check.py` (신규) - 13 테스트: 소스 단언(except Exception·캐시 미경유·httpx·{e} 미보간), AuthStatus 기본 None, ping_edgar 성공/403/일반예외/UA 미노출, ping_dart 성공/013/020 키유효/무효/예외/키 미노출.
- `src/stocksig/io/fundamentals.py` - `_fill_us(skip_edgar)`/`_fill_kr(skip_dart)` 분기 + `fetch_fundamentals` skip 인자 2개 + skip 시 기본 클라이언트 lazy import 생략.
- `tests/test_fundamentals.py` - skip 경로 4 테스트(skip_edgar yf 유지/결손 사유, skip_dart Naver→yf 유지, 무회귀).
- `src/stocksig/main_run.py` - `auth_check` import + 조건부 ping + `_fundamentals_with_auth` 클로저 + `_auth_label` 헬퍼 + 요약 인증 줄(04-01 TODO 대체).
- `tests/test_smoke_n_tickers.py` - `mock_pipeline_env` 에 ping stub 추가(hermetic) + 7 신규 테스트(조건부 US/KR, D-04 US만/KR만, D-02 계속+워크북, skip 전파, 인증 줄, 보안 키/UA 미노출).

## Decisions Made
- EDGAR ping = httpx 직접 GET 단일 경로(Pitfall 2 혼합 금지). `_dart_probe`/`_edgar_probe` 를 별도 헬퍼로 분리해 테스트가 외부 호출만 mock 하도록 격리.
- skip 클로저는 `market == "US"`/`"KR"` 매칭을 함께 검사 — 한 시장 인증 실패가 다른 시장 종목에 잘못 전파되지 않음.
- ping note 는 Task 1 에서 이미 키/UA 미포함 고정 사유이므로 `_auth_label` 이 그대로 출력해도 보안상 안전(T-04-04).

## Deviations from Plan
None - 플랜이 작성된 그대로 실행됨 (3 태스크 모두 TDD RED→GREEN, REFACTOR 불필요). 신규 패키지 설치 0개(기존 httpx/edgartools/opendartreader 재사용, T-04-SC accept).

## Issues Encountered
- `.planning/` 가 gitignore 되어 SUMMARY 커밋에 `git add -f` 필요(04-01 과 동일). 코드/테스트 파일은 정상 추적됨.
- smoke 테스트가 2700행 compute × 다티커라 느림(ping 테스트 7개 ~46s) — `mock_pipeline_env` 에 ping stub 을 추가해 네트워크 없이 hermetic 유지.

## User Setup Required
기존 `.env` 재사용 — 신규 설정 없음:
- `EDGAR_USER_AGENT_EMAIL` (Phase 1 설정됨) — EDGAR ping UA 검증에 사용.
- `OPENDART_API_KEY` (사용자 보유) — DART ping 키 유효성 검증에 사용.

(수기, VALIDATION Manual-Only) 실제 `.env` 로 `uv run python main.py` 1회 — EDGAR/DART ping 콘솔 출력 + 종료 요약 "인증:" 줄 육안 확인.

## Next Phase Readiness
- EXEC-04 의 인증 부분 충족 — 조건부 ping(D-04)·실패 시 계속(D-02)·1차만 스킵+yf 폴백(A4)·키/UA 미노출(보안)·종료 요약 인증 줄 모두 구현.
- 전체 회귀 231 passed 무회귀 확인.

## TDD Gate Compliance
- Task 1: `test(04-03)` RED (`b2e6348`) → `feat(04-03)` GREEN (`abfab54`) ✓
- Task 2: `test(04-03)` RED (`73b3d7e`) → `feat(04-03)` GREEN (`4fa180a`) ✓
- Task 3: `test(04-03)` RED (`ad74121`) → `feat(04-03)` GREEN (`7cfe004`) ✓
- REFACTOR 단계 불필요 (구현 최소·명료).

## Threat Flags
신규 위협 표면 없음. 위협 레지스터 mitigate 항목 모두 충족:
- T-04-03 (정보노출, ping 예외 사유): EDGAR·DART note 양쪽 고정 한국어 사유로 치환, `{e}` 보간 없음 — 소스 grep + 보안 테스트(UA 이메일/DART 키 주입 미노출) 검증.
- T-04-04 (요약 인증 줄): `_auth_label` 이 ok 상태 + sanitize 된 note 만 출력 — 보안 테스트 검증.
- T-04-06 (캐시 오염): ping 은 `fetch_*_cached` 미사용 — 소스 grep 무매치 검증.
- T-04-05/T-04-SC: accept (매 실행 1회 throttle 경유 / 신규 설치 0개).

## Self-Check: PASSED
- `src/stocksig/io/auth_check.py` 존재; `AuthStatus`/`except Exception`/`httpx` 매치, `fetch_edgar_cached`/`fetch_dart_cached` 무매치 ✓
- `src/stocksig/io/fundamentals.py` `skip_edgar`/`skip_dart` 매치(16) ✓
- `src/stocksig/main_run.py` `ping_edgar`/`ping_dart`(조건부 2)·`skip_edgar`/`skip_dart`(클로저)·`인증:` 매치 ✓
- 커밋 b2e6348/abfab54/73b3d7e/4fa180a/ad74121/7cfe004 모두 `git log` 에 존재 ✓
- 전체 231 tests green (auth_check 13 + fundamentals 42 + smoke 17 + 나머지 모듈 전부 통과; 무회귀) ✓

---
*Phase: 04-quality-robustness*
*Completed: 2026-06-12*
