---
phase: 04-quality-robustness
plan: 02
subsystem: tests
tags: [freeze-panes, color-tone, wcag-luminance, grayscale, regression, human-verify]

requires:
  - phase: 04-quality-robustness (plan 01)
    provides: "main_run.run() 시작부 reset_cache_stats + 종료부 실행 요약 블록 (run() end-to-end 테스트 전제)"
  - phase: 02-scaling-portfolio-summary
    provides: "color_rules.py 색 단일 진원지(D-02) + sheet_per_ticker/sheet_portfolio freeze_panes 구현"
provides:
  - "tests/test_freeze_panes.py — OUT-04 frozen panes openpyxl 읽기 회귀 (시트1 B6 / 종목 시트 A6, 3 tests)"
  - "tests/test_color_tone.py — WCAG 상대 휘도 공식 + HARD/SOFT 버킷 그레이스케일 구분 자동 측정 (4 tests)"
  - "수기 시각 검증 approved — frozen panes 육안 + 파스텔 톤 + 흑백 방향 구분 (2026-06-12)"
affects: []

tech-stack:
  added: []
  patterns:
    - "WCAG relative luminance(0.2126R+0.7152G+0.0722B, sRGB 선형화) 헬퍼를 테스트 파일 내장 — 프로덕션 의존 없음"
    - "휘도 임계는 실측 기반 정직 설정 — HARD 배경 0.0351 실측 → 임계 0.03 (억지 하향 금지)"
    - "SOFT(±1σ) 글자색 휘도차 0.0180 — bold + 셀 위치 의존을 테스트 docstring 에 문서화 (Pitfall 5)"

key-files:
  created:
    - tests/test_freeze_panes.py
    - tests/test_color_tone.py
  modified: []

key-decisions:
  - "color_rules.py 상수 무수정 — HARD 휘도차 실측 0.0351 이 임계 통과, SOFT 는 bold 의존 문서화로 충족 (D-02 단일 진원지 보존)"
  - "수기 검증 중 발견된 AAPL 캐시 오염 버그는 본 plan 범위 밖 갭으로 처리 — 오케스트레이터가 즉시 수정 (aff5366)"

duration: "~10min (자동 task) + 수기 검증"
---

# 04-02 검증 수직 슬라이스 — frozen panes 회귀 + 색 톤 휘도 검증

## 무엇을 만들었나

신규 프로덕션 코드 없이 기존 구현을 자동 회귀로 못박는 검증 슬라이스.

1. **Task 1 — test_freeze_panes.py** (`1fc7476`): `run()` end-to-end 로 AAPL+MSFT 워크북을 생성하고 openpyxl 로 다시 읽어, 모든 시트 `freeze_panes` 가 행 6 시작(1~5행 고정), 시트1 == "B6"(A열 추가 고정), 종목 시트 == "A6" 임을 단언. 3개 테스트 green.
2. **Task 2 — test_color_tone.py** (`32480f2`): WCAG 상대 휘도 공식 구현 검증(흑 0.0/백 1.0) + HARD 배경(GREEN_100 vs RED_100) 휘도차 0.0351 > 임계 0.03 단언 + SOFT 글자색(GREEN_800 vs RED_800) 휘도차 0.0180 측정 단언. `color_rules.py` 는 **수정하지 않음** — 실측이 임계를 통과해 D-02 단일 진원지를 건드릴 이유가 없었다. 기존 test_color_rules.py 무회귀. 4개 테스트 green.
3. **Task 3 — 수기 시각 검증 (checkpoint:human-verify)**: 사용자가 실데이터 25개 티커로 `main.py` 실행 후 frozen panes 스크롤 고정, 파스텔/소프트 톤, 흑백 인쇄 미리보기 방향 구분을 확인하고 **approved** (2026-06-12).

## 검증 결과

- `uv run pytest tests/test_freeze_panes.py tests/test_color_tone.py tests/test_color_rules.py` green
- 전체 회귀 242 passed (병합 후 통합 게이트)
- 수기 체크포인트 approved — SC1(frozen panes), SC4(파스텔 톤 + 그레이스케일 구분) 사람 확정

## 일탈/특이사항

- **체크포인트 중 별도 버그 발견·수정**: 수기 검증용 실행에서 AAPL 시트가 합성 테스트 데이터(2026-05-20 종료, ~90$ 가격)로 채워지는 문제 발견. 원인은 test_smoke_end_to_end.py 가 yf.Ticker(캐시 계층 아래)만 mock 한 채 운영 `.cache/ohlcv` 에 합성 OHLCV 를 저장한 테스트 격리 누락. conftest autouse `_isolated_disk_cache` 픽스처 + 카나리 테스트 2개로 수정(`aff5366`), 오염 캐시 키 2개 정화. 본 plan 의 산출물(검증 테스트)과는 독립이지만, 체크포인트가 잡아낸 실질 갭이므로 여기 기록한다.
- HARD 배경 휘도 마진(0.0351, 임계 0.03)이 크지 않음 — 흑백 인쇄에서 ±2σ 배경 구분이 약하게 느껴지면 `color_rules.py` GREEN_100/RED_100 상수만 조정하면 된다(후속 개선 후보).
