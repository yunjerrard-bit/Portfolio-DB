---
phase: quick-260617-ijf
plan: 01
subsystem: io/fundamentals
tags: [WR-01, nan-guard, data-integrity, tdd]
requires: []
provides: ["_is_missing NaN 게이트", "산식 3종·폴백 3경로 NaN 차단"]
affects: [src/stocksig/io/fundamentals.py]
tech-stack:
  added: []
  patterns: ["단일 결손 게이트(_is_missing)로 None/NaN 동시 처리"]
key-files:
  created: []
  modified:
    - src/stocksig/io/fundamentals.py
    - tests/test_fundamentals.py
decisions:
  - "NaN 을 None 과 동일한 '결손'으로 취급 — 값 있는 셀·provenance 위조(D-05 위반) 차단."
  - "missing 가드는 ≤0/==0 비교보다 먼저 — NaN 이 비교 분기에 도달하지 못하게 순서 유지."
metrics:
  duration: ~6min
  completed: 2026-06-17
  tasks: 2
  files: 2
---

# Phase quick-260617-ijf Plan 01: WR-01 펀더멘털 NaN 가드 Summary

`_is_missing(None/NaN)` 단일 게이트를 도입해 NaN last_close·EPS·PER 가 값 있는 셀과 EDGAR/DART/Naver/yf provenance 로 시트1에 새는 경로를 산식 3종 + 폴백 3경로에서 전부 차단했다.

## What Was Built

- **`_is_missing(x)` 헬퍼** (`src/stocksig/io/fundamentals.py` L72): `x is None or (isinstance(x, float) and math.isnan(x))`. 모듈에 `import math` 추가.
- **산식 3종 가드 교체**: `_compute_per`(eps_ttm·last_close), `_compute_peg`(per·eps_prior·eps_ttm), `_compute_margin`(numer·denom)의 `is None` → `_is_missing(...)`. `eps_ttm <= 0` / `eps_prior == 0` / `denom == 0` 비교는 missing 가드 통과 후로 순서 유지 — NaN 이 비교 분기에 도달하지 않음.
- **폴백 3경로 가드**: yf 폴백(US `_fill_us` L172, KR `_fill_kr` L266), Naver 폴백(KR L248)의 `if v is not None:` → `if v is not None and not _is_missing(float(v)):`. NaN 이면 진입 자체를 막아 source/note 미부여 보장.
- **회귀 테스트 7종** (`tests/test_fundamentals.py`): NaN last_close→PER None(+종가 note), NaN EPS→PER None, NaN PER 전파→PEG None, NaN eps_ttm→PEG None, NaN numer/denom→margin None, fetch_fundamentals NaN last_close→PER value/source 둘 다 None, yf NaN PER 거부→PER value/source None.

## How It Works

`runner.process_ticker` 가 주입하는 `last_close = df.iloc[-1].get("Close")` 는 장중 부분 행 등으로 NaN 일 수 있다. NaN 은 `<=0` 등 모든 비교가 False 라 기존 `is None` 가드를 통과해 `PER = NaN/eps = NaN` 이 값 있는 셀로 통과하고 `source="EDGAR"` 까지 붙었으며, NaN PER 이 `_compute_peg` 로 전파됐다. `_is_missing` 을 산식·폴백 진입 전 단일 게이트로 두어 NaN→결손(None) 으로 강제, D-05("결손은 None, 0/-999999 금지") 와 Core Value(시트 정확성)를 보호한다.

## TDD Gate Compliance

- RED: `test(quick-260617-ijf)` 커밋 `988bf64` — 미수정 production 에서 7종 모두 FAIL(value 가 NaN 으로 채워져 단언 실패) 확인.
- GREEN: `feat(quick-260617-ijf)` 커밋 `222a37b` — 7종 통과 + 전 스위트 무회귀.
- REFACTOR: 불필요(변경이 NaN→None 안전 처리에 국한).

## Verification

- `uv run pytest tests/test_fundamentals.py -q` → 38 passed (신규 nan 7 + 기존 31).
- `uv run pytest -q` → 268 passed, 0 failed (네트워크 호출 없음, 콜러블 주입 stub).
- `_is_missing(` 호출처: 정의 1 + 산식 7 + 폴백 3 = 11곳 검출.

## Deviations from Plan

None - 플랜대로 실행. 변경은 NaN→None 안전 처리에 국한, 다른 동작 변경 없음.

## Threat Model Compliance

- **T-quick-01 (Tampering/데이터 무결성, mitigate)**: `_is_missing` 게이트로 NaN 을 결손으로 강제 — 값 있는 셀·provenance 위조 차단. 본 플랜 핵심으로 구현 완료.
- **T-quick-02 (Information Disclosure, accept)**: 신규 외부 호출·예외 경로 미추가, 기존 T-04-03 자격증명 누설 차단 패턴 불변.

## Commits

- `988bf64` test(quick-260617-ijf): NaN 결손 회귀 테스트 7종 추가 (RED)
- `222a37b` feat(quick-260617-ijf): _is_missing NaN 게이트 + 산식·폴백 NaN 가드 (GREEN)

## Self-Check: PASSED
- FOUND: src/stocksig/io/fundamentals.py (수정, _is_missing 11곳)
- FOUND: tests/test_fundamentals.py (수정, nan 7종)
- FOUND: commit 988bf64
- FOUND: commit 222a37b
