---
phase: quick-260627-vpn
plan: 01
subsystem: io/edgar_client + data store
status: complete
tags: [bugfix, FUND-10, edgar, data-cleanup, regression-test]
requires:
  - edgar_client._calendar_quarter_key
  - data/fundamentals.db (raw_facts)
provides:
  - YYYYQn 분기키 게이트(비분기 키 None 차단)
  - 정리된 fundamentals.db raw_facts
affects:
  - history 경로 compute_matrix 분기축 (오염 제거)
tech-stack:
  added: []
  patterns:
    - "re.fullmatch 최종 게이트 — 정규화 출력이 정확히 YYYYQn 일 때만 통과"
key-files:
  created: []
  modified:
    - src/stocksig/io/edgar_client.py
    - tests/test_edgar_quarterly.py
    - data/fundamentals.db
decisions:
  - "비분기 키(FY-라벨 등) 실패 처리 = None (sentinel 0/-999999 금지, docstring 약속 일치)."
  - "DB 오염행 정리는 일회성 인라인 sqlite3 — 레포에 스크립트 영구 추가 안 함(데이터 정리는 코드 산출물 아님)."
metrics:
  duration: ~12 min (pytest 전체 7분 17초 포함)
  completed: 2026-06-27
  tasks: 2
  files: 3
---

# Phase quick Plan 260627-vpn: 트렌드 렌더 FY-라벨 quarter-key 가드 + DB 오염행 정리 Summary

`edgar_client._calendar_quarter_key` 가 연간 프레임("FY 2026")을 분기 키로 오인 반환하던 결함을 `re.fullmatch(r"\d{4}Q[1-4]")` 최종 게이트로 차단하고, 이미 적재된 비정상 quarter 6행을 `data/fundamentals.db` raw_facts 에서 삭제해 history 경로 `compute_matrix` 분기축의 `int("FY 2")` ValueError 연쇄 드롭을 제거했다.

## What Was Built

- **Task 1 (가드 + 회귀 테스트):** `_calendar_quarter_key` 의 무조건 `return disp` 를 정규식 게이트로 교체 — 두 split 분기를 통과한 뒤 정규화 출력이 정확히 `YYYYQn` 일 때만 disp 반환, 그 외는 None. `import re` 추가(alphabetical). "as-reported 보존" 주석을 게이트 설명으로 교체. 공백 없는 단일 토큰 "2026Q2"(이미 정규화된 키)는 split 분기를 건너뛰고 최종 게이트를 통과함을 회귀 테스트로 보장. `tests/test_edgar_quarterly.py` 에 `_FakeFact` 스텁(get_display_period_key 1개만)으로 behavior 5종 + 빈/None 가드 = 6 단언 추가(네트워크 0).
- **Task 2 (DB 오염행 정리):** 표준 라이브러리 sqlite3 인라인으로 (1) 삭제 전 COUNT, (2) `DELETE ... WHERE quarter NOT GLOB '[0-9][0-9][0-9][0-9]Q[0-9]'` + commit, (3) 재COUNT=0 확인. 삭제 6행 전부 `field=shares_outstanding, source=EDGAR`.

## Verification (actual outputs)

1. **전체 pytest 스위트:** `uv run python -m pytest -q` → **362 passed in 437.34s (0:07:17)** — 회귀 0. (단일 파일 `tests/test_edgar_quarterly.py` → 14 passed: 기존 8 + 신규 6.)
2. **DB 재COUNT:** 삭제 전 `before_delete_count= 6`, 삭제 후 `after_delete_count= 0`. 자동 검증 `non_yyyyqn_rows= 0` → VERIFY_PASS. 삭제된 6행:
   - CRDO / EDGAR / "FY 2026" / shares_outstanding
   - LEU  / EDGAR / "FY 2022" / shares_outstanding
   - NKE  / EDGAR / "FY 2015" / shares_outstanding
   - SIRI / EDGAR / "FY 2026" / shares_outstanding
   - TSLA / EDGAR / "FY 2026" / shares_outstanding
   - TTWO / EDGAR / "FY 2026" / shares_outstanding
3. **엔드투엔드 `uv run python main.py history`:** `완료: output\fundamentals_history_20260627.xlsx` 정상 생성. 로그 전체에서 `트렌드 렌더 실패(ValueError)` 경고는 **1건뿐 — `ZZZZZ`**(테스트/센티넬 티커, 스코프 외). **CRDO/LEU/NKE/SIRI/TTWO 5종목은 더 이상 ValueError 경고를 내지 않음**(전부 캐시 HIT 정상 처리). **TSLA**: raw_facts 에 그 1행(FY)뿐이라 삭제 후 트렌드 데이터 자체가 없음 — ValueError 도 없고 트렌드도 없음(별개 이슈, 본 스코프 아님 — 플랜 명시).

## Deviations from Plan

None — 플랜대로 정확히 실행했다.

부수 사항: 레포에 git author identity 가 설정되어 있지 않아 첫 커밋이 실패했다. 프로젝트 컨벤션(UA 이름 "Yunjae Kim", 사용자 이메일)에 맞춰 **로컬(레포 한정)** `git config user.name/user.email` 만 설정 후 커밋했다(--global 아님). 코드/DB 변경과 무관한 환경 설정.

## Commits

- `da0edde` fix(260627-vpn): _calendar_quarter_key 최종 반환 가드(YYYYQn fullmatch) + 회귀 테스트 (Task 1 — edgar_client.py + test)
- `51f044a` fix(260627-vpn): fundamentals.db raw_facts FY-라벨 오염행 6건 삭제 (Task 2 — data/fundamentals.db)

## Known Stubs

None.

## Scope Notes

- 시트1(`portfolio_YYYYMMDD.xlsx`) 색 신호 경로 무접근 — 본 수정은 edgar_client + DB + 테스트만 건드림. Core Value 불변.
- TSLA 트렌드 데이터 부재는 별개 이슈로 스코프 외(플랜에서 명시).
- `ZZZZZ` 센티넬 티커의 ValueError 경고는 본 결함과 무관(분기축 데이터 자체 부재 케이스).

## Self-Check: PASSED

- FOUND: src/stocksig/io/edgar_client.py
- FOUND: tests/test_edgar_quarterly.py
- FOUND: data/fundamentals.db
- FOUND: .planning/quick/260627-vpn-fix-trend-fy-label-quarter-key-guard-plu/260627-vpn-SUMMARY.md
- FOUND commit: da0edde
- FOUND commit: 51f044a
