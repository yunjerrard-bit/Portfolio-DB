# Phase 9: 트렌드 엑셀 렌더 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-22
**Phase:** 9-trend-render
**Areas discussed:** 매트릭스 레이아웃, 트렌드 시각 신호, 가격 의존 지표 & PEG, 결손·출처·파일 정책

---

## 매트릭스 레이아웃

| Option | Description | Selected |
|--------|-------------|----------|
| 전체 분기·최신 오른쪽 | 오름차순, 최신 맨 오른쪽 | |
| 최근 12분기·최신 오른쪽 | 폭 제한 | |
| 전체 분기·최신 왼쪽 | 내림차순, 최신 맨 왼쪽 | ✓ |

**User's choice:** 전체 분기·최신 왼쪽(내림차순).
**Notes (행 정렬/고정):** 미국→한국 그룹화 후 알파벳순. Freeze는 A열(티커)만. 각 지표 시트 선두에 portfolio A~E열 헤더 그대로(티커·기업명·시장·티어·산업) 사용. 시장(C)·티어(D) 열은 글자 폭만큼 최소화.

---

## 트렌드 시각 신호 (이중 인코딩으로 확정)

| Option | Description | Selected |
|--------|-------------|----------|
| 전년동기(YoY) 빨강/초록 | 4분기 전 대비 상승=초록·하락=빨강 | (화살표로 채택) |
| YoY + 무변동 회색 | 변동폭 작으면 중립 | |
| 컬러스케일(행 그라데이션) | 행 내 최소~최대 그라데이션 | |
| 순수 숫자 | 무서식 | |

**User's choice:** 두 신호를 직교 결합 — **셀 배경색 = 동종 산업군 상대 비교**(finviz식, 좋을수록 초록/나쁠수록 빨강, 3단계 초록/무색/빨강), **화살표 = 전년동기(YoY) 증감 추이**(tradingview식, 모수 무관).
**Notes:** 색 방향성 = **지표별 좋음/나쁨**(PER/PEG/PBR/PCR/PSR 낮을수록 초록, ROE/ROA/GPM/OPM 높을수록 초록). 동종 표본 부족(1~2종목) 시 상대색 무색, 화살표는 유지.

---

## 가격 의존 지표 & PEG

| Option | Description | Selected |
|--------|-------------|----------|
| 분기말 종가 + PEG 분기별 산출 | 과거=분기말 종가, PEG도 분기별 | ✓ |
| 분기말 종가, PEG 최신만 | 과거 PEG 생략 | |
| PEG 시트 제외 | PEG 추후 | |

**User's choice:** 분기말 종가 + PEG 분기별 산출(compute_peg_cell).

---

## 결손·출처·파일 정책

| 항목 | 선택 |
|------|------|
| 결손/sanity-밖 셀 | `"-"` 표시 + 마우스오버 코멘트(사유) |
| provenance 위치 | `[원천]` 시트 중심 + 코멘트 보조 |
| 파일명/덮어쓰기 | 날짜 스탬프 `fundamentals_history_YYYYMMDD.xlsx`(매 실행 새 파일) |
| main_run 배선 | 독립 서브커맨드/플래그 |

---

## Claude's Discretion

- 화살표 구현 기법(아이콘셋 vs 글리프 ▲▼ vs 별도 열), 상대색 구현(conditional_format vs Python 사전계산 정적 베이킹).
- 상대비교 표본 게이트 N(권장 3)·동순위 처리, `[원천]`/`[최신 스냅샷]` 시트 구체 구성, 분기 헤더 라벨, 서브커맨드 CLI 형태·DB 미존재 안내, 시장/티어 열 최소 너비 산정.

## Deferred Ideas

- 헤더행 freeze, 스파크라인/미니차트, FCF·EV/EBITDA 시트(raw 원천 확장 선행), 상대비교 기준 확장(시총·티어), ROE/ROA 기초·기말 평균 분모.
