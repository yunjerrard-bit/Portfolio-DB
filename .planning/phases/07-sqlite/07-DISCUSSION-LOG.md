# Phase 7: 펀더멘털 SQLite 저장 + 접수번호 델타 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-18
**Phase:** 7-sqlite
**Areas discussed:** 첫 실행 백필 깊이, raw 원천 필드 범위, 7일 캐시와 공존 방식, 분기 키 정규화

---

## 첫 실행 백필 깊이

### 백필 정책

| Option | Description | Selected |
|--------|-------------|----------|
| 소스별 차등 | EDGAR fetch에 딸려오는 과거 전부 저장(공짜), DART는 최근 N년만 backfill | ✓ |
| 전 소스 최대 backfill | DART도 가능한 과거 전부 — 첫 실행 DART 호출·쿼터 위험 | |
| forward-only | 현재 분기만 저장, 앞으로 누적 — 단순하나 트렌드는 시간 필요 | |

### DART 범위

| Option | Description | Selected |
|--------|-------------|----------|
| 최근 3년 | ~12분기, 호출 수십건/종목, 비용·추세 균형 | ✓ |
| 최근 5년 | 20분기, DART 호출 ~1.7배·쿼터 압박 | |
| 최근 1년 | 최신 분기만, 사실상 forward-only | |

### EDGAR 범위

| Option | Description | Selected |
|--------|-------------|----------|
| 딸려오는 과거 전부 저장 | 공짜로 온 분기 전부 보관, 트렌드 길이는 렌더에서 자름 | ✓ |
| DART와 동일 3년 제한 | 소스 간 길이 맞춤, 공짜 데이터 버림 | |

**User's choice:** 소스별 차등 — EDGAR 전부 저장, DART 최근 3년, 이후 forward 누적
**Notes:** EDGAR EntityFacts는 단일 fetch에 수년치 분기 포함 → backfill 거의 공짜. DART는 연도별 호출 필요해 3년으로 비용 통제.

---

## raw 원천 필드 범위

### 필드 목록

| Option | Description | Selected |
|--------|-------------|----------|
| ROE/PBR 포함 슈퍼셋 | 매출·매출총이익·영업이익·순이익·EPS·자본총계·부채총계·발행주식수 (D-H2) | |
| + 현금흐름·총자산 확장 | 위 + 영업현금흐름·총자산 → ROA·FCF까지 대비 | ✓ |
| 현재 지표만(최소) | PER/PEG/GPM/OPM 필요분만 — ROE/PBR 추가 시 재backfill | |

### raw 의미

| Option | Description | Selected |
|--------|-------------|----------|
| 소스 원뎌 그대로 | EDGAR period값·DART YTD 누적 그대로 저장, 분해는 Phase 8 | ✓ |
| 분기 단독값 정규화 저장 | 저장 시 분해 완료 — 분해 오류가 원천에 굳고 재복원 불가 | |

**User's choice:** 슈퍼셋+(현금흐름·총자산 포함), 소스 원뎌 그대로 저장
**Notes:** "무재호출" 취지 살리려 필드 인색하게 잡지 않음. 원천 보존으로 분해 오류 시에도 안전.

---

## 7일 캐시와 공존 방식

### 공존 방식

| Option | Description | Selected |
|--------|-------------|----------|
| 완전 별도 additive | 새 store/델타 모듈만 추가, 시트1 7일 캐시 경로 불변, 통합은 Phase 10 | ✓ |
| 기존 fetch에 intercept | 시트1 fetch도 델타/store 경유 — Phase 10 범위 침범·회귀 위험 | |

### 이중 호출

| Option | Description | Selected |
|--------|-------------|----------|
| 허용 — 분기 경계만, Phase 10 통합 | 드문 이벤트, 구현 단순·회귀 위험 0 | ✓ |
| 히스토리 fetch 재사용 | 이중 호출 제거하나 additive 원칙 깨고 시트1 건드림 | |

**User's choice:** 완전 별도 additive, 분기 경계 이중 호출 허용
**Notes:** Core Value(시트1 색 신호) 보호 최우선. 통합·중복 제거는 Phase 10(FUND-11).

---

## 분기 키 정규화

### canonical 분기 키

| Option | Description | Selected |
|--------|-------------|----------|
| 캘린더 분기 정규화 | period 종료일 기준 캘린더 분기 매핑 — 종목 간 열 정렬·교차 비교 용이 | ✓ |
| 보고 fiscal 그대로 | reprt_code/period → Qn 단순 매핑, 회계연도 다르면 열 시점 어긋남 | |

### 중복/upsert

| Option | Description | Selected |
|--------|-------------|----------|
| 최신값 upsert | (ticker, source, 캘린더분기, field) 유니크, 정정공시 시 덮어쓰기 | ✓ |
| 정정 이력 보존(append) | accession별 원본+정정 모두 저장 — 스키마·쿼리 복잡 | |

**User's choice:** 캘린더 분기 정규화, 최신값 upsert
**Notes:** 매트릭스 가독성·교차 비교 위해 캘린더 정렬. 정정 이력은 raw 원천 보존으로 추후 비파괴적 도입 가능.

---

## Claude's Discretion

- delta probe 실패 시 처리(안전 폴백 vs 보수적 재추출) — researcher 조사 후 planner 결정.
- SQLite 스키마 세부(PK/인덱스, value 타입, period 메타 컬럼, source enum), 동시 쓰기 lock, upsert SQL — planner/executor 재량.
- 신규 모듈 분리·main 호출 진입점 — planner 결정.

## Deferred Ideas

- 지표 registry 계산 → Phase 8(FUND-09).
- 트렌드 엑셀 렌더 → Phase 9(FUND-10).
- 시트1 통합 store/registry 이관 + 7일 캐시 제거 → Phase 10(FUND-11).
- 정정공시 이력 보존(audit trail) — 필요 시 별도 이력 테이블로 추후 도입.
- 폴백 소스(yf/Naver) 분기 라벨 보완 세부 정책 — 소수 종목, planner 검토.
