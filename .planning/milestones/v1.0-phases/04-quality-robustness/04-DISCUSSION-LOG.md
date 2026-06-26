# Phase 4: 품질·견고성 마감 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-11
**Phase:** 4-품질·견고성 마감
**Areas discussed:** 데이터 품질 시트(EXEC-04 처리), 시작 시 인증 사전검증

---

## 논의 영역 선택 (gray areas)

| Option | Description | Selected |
|--------|-------------|----------|
| 데이터 품질 시트 구성 | 행 단위·펀더멘털 결손 포함 여부·컬럼 구성 | (자유 입력으로 대체) |
| 콘솔 로그·캐시 통계 | 집계 형태·per-call 로그 유지·rich 도입 | |
| 색상 톤 검증·조정 | 현행 Material 팔레트 유지 vs 조정, 그레이스케일 검증 | |
| 시작 시 인증 사전검증 | Phase 3 deferred — EDGAR/DART ping | ✓ |

**User's choice:** "데이터 품질 시트는 만들지 않음. 현재 방식 유지" + "시작 시 인증 사전검증"
**Notes:** 데이터 품질 시트 미생성은 EXEC-04 범위 축소 결정 — 후속 질문으로 요구사항 정리 방법 확인.

---

## EXEC-04 처리 (데이터 품질 시트 미생성 시)

| Option | Description | Selected |
|--------|-------------|----------|
| 콘솔 요약으로 대체 (추천) | 콘솔 최종 실패 요약 + 시트1 실패행·셀 주석으로 충족 재정의, 시트 영구 미생성 | ✓ |
| v2 백로그로 보류 | v2 요구사항으로 이동 | |
| Out of Scope로 영구 제외 | REQUIREMENTS.md Out of Scope 표에 기록 | |

**User's choice:** 콘솔 요약으로 대체

---

## 인증 사전검증 — 실패 시 동작

| Option | Description | Selected |
|--------|-------------|----------|
| 경고 후 계속 진행 (추천) | 한국어 경고 후 시세·시트 정상, 해당 소스 펀더멘털만 결손 | ✓ |
| 즉시 종료 (fail-fast) | Phase 1 .env 누락과 동일 패턴 | |
| 사용자에게 선택 프롬프트 | y/n 입력 대기 (무인 실행 부적합) | |

**User's choice:** 경고 후 계속 진행

---

## 인증 사전검증 — ping 주기

| Option | Description | Selected |
|--------|-------------|----------|
| 매 실행 시작 시 (추천) | EDGAR 1회 + DART 1회, 항상 최신 상태 확인 | ✓ |
| 하루 1회 캐시 | 24h 캐시로 호출 최소화 | |
| 별도 ping 없이 lazy 감지 | 첫 펀더멘털 실패 시점에 분류 | |

**User's choice:** 매 실행 시작 시

---

## 인증 사전검증 — 검증 범위

| Option | Description | Selected |
|--------|-------------|----------|
| EDGAR + DART 둘 다 (추천) | UA 유효성 + API 키 유효성, 해당 시장 티커 존재 시에만 각각 ping | ✓ |
| DART만 | API 키 리스크 있는 쪽만 | |
| Claude 재량 | researcher/planner가 결정 | |

**User's choice:** EDGAR + DART 둘 다

---

## Claude's Discretion

- 콘솔 로그·캐시 통계 형식 (집계 형태, per-call 로그 유지 여부, rich 도입 여부)
- 색상 톤 검증·조정 (현행 팔레트 충족 여부 판단, 그레이스케일 검증 방법)
- ping 엔드포인트 선정 + throttle 경유 여부
- ping 실패 소스의 per-ticker 펀더멘털 fetch 스킵 최적화

## Deferred Ideas

- 데이터 품질 별도 시트 (EXEC-04 원형) — 필요해지면 기존 `TickerFailure`/`MetricCell.note` 구조로 작은 작업
- rich 진행바 — 도입 여부 재량, 미도입도 SC3 충족 가능
