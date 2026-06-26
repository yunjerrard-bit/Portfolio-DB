# Phase 8: 지표 registry 계산 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-19
**Phase:** 8-registry
**Areas discussed:** 신규 지표 범위, 하이브리드 분모 규칙, 재현 정합성 정책, 계산 산출 범위, 출처·폴백 의미

---

## 신규 지표 범위

| Option | Description | Selected |
|--------|-------------|----------|
| ROE + PBR만 (최소) | 로드맵 명시 2개로 registry 확장성 증명 | |
| ROE+PBR+ROA+부채비율 (권장) | 저장 raw로 완전 계산되는 지표 전부 | |
| 위 + FCF | FCF 포함 — CapEx 미저장으로 raw 확장 선행 필요 | |

**User's choice:** (Other) "PBR, PCR, PSR, ROE, ROA, FCF, EV/EBITDA 까지" — 폭넓은 세트 요청.
**Notes:** 계산 가능성 점검 결과 PBR·PCR·PSR·ROE·ROA(5종)은 저장 raw로 즉시 계산 가능, FCF(CapEx)·EV/EBITDA(현금잔액·D&A·이자성부채)는 raw 미저장 → 불가. 후속 결정으로 분기.

### 후속: FCF·EV/EBITDA 처리

| Option | Description | Selected |
|--------|-------------|----------|
| 5종 먼저, 2종은 연기 (권장) | PBR·PCR·PSR·ROE·ROA 완성, FCF·EV/EBITDA는 deferred(raw 확장 필요) | ✓ |
| raw 확장까지 이번에 포함 | Phase 7 재작업으로 CapEx·현금·D&A 추가 후 7종 전부 | |
| EV/EBITDA만 연기, FCF는 시도 | 절충안 | |

**User's choice:** 5종 먼저, 2종은 연기 (권장)
**Notes:** Phase 8 지표 = 재현 4(PER/PEG/GPM/OPM) + 신규 5(PBR/PCR/PSR/ROE/ROA) = 9종. FCF·EV/EBITDA는 raw 원천 확장 phase로 연기.

---

## 하이브리드 분모 규칙

| Option | Description | Selected |
|--------|-------------|----------|
| 최근 분기값 (권장) | 분모 = 가장 최근 분기 시점값. 단순·결손 강건·스크리닝 관행 | ✓ |
| 기초·기말 평균 | (전년동기말+최근분기말)÷2, 표준 회계 관행, 단 양 시점 raw 필요 | |

**User's choice:** 최근 분기값 (권장)
**Notes:** ROE·ROA 분모(자본·자산)에 적용. raw 한 분기만 있어도 산출 가능.

---

## 재현 정합성 정책

| Option | Description | Selected |
|--------|-------------|----------|
| registry가 새 단일 원천 (권장) | raw 4분기 합산이 canonical, sanity 범위 검증, Phase 10 표시값 미세 변동 수용 | ✓ |
| parity 검증 게이트 (중간) | registry canonical, ±1~2% 내 현 값과 일치 테스트, 초과만 조사 | |
| 정확한 parity 보장 | 현 값 정확 재현, TTM을 레거시에 맞춤, 드리프트 0 보장(유연성 속앗) | |

**User's choice:** registry가 새 단일 원천 (권장)
**Notes:** 현 경로(edgartools get_ttm)와 registry(4분기 직접 합산)의 미세 차이를 "더 일관된 값"으로 수용. 레거시 정확 일치 강제 안 함.

---

## 계산 산출 범위

| Option | Description | Selected |
|--------|-------------|----------|
| 분기 매트릭스 전체 (권장) | 매 분기 전 지표 시계열, 최신값=마지막 열. Phase 9·10 공통 단일 원천 | ✓ |
| 최신값만 (작은 범위) | 종목·지표별 최신 1값만, Phase 9가 나중에 매트릭스 확장 | |

**User's choice:** 분기 매트릭스 전체 (권장)

### 후속: 가격 의존 지표 가격 입력

| Option | Description | Selected |
|--------|-------------|----------|
| 분모만 산출, 가격은 주입 (권장) | registry는 per-share 분모(EPS/BPS/SPS/OCF-ps), 비율=price÷분모, price는 호출자 주입 | ✓ |
| registry가 가격까지 적용 | registry가 OHLCV에서 분기말/현재가 직접 조회해 최종 비율 산출 | |

**User's choice:** 분모만 산출, 가격은 주입 (권장)
**Notes:** 최신=현재가 / 과거=분기말 종가. 분기말 종가는 보유 중인 10년치 OHLCV에서 조달. 계산 층 순수성 유지.

---

## 출처·폴백 의미

| Option | Description | Selected |
|--------|-------------|----------|
| registry=순수계산+라벨, 폴백은 밖 (권장) | metric별 독립 계산 + provenance=사용 raw 필드 source. 폴백 fetch는 오케스트레이션(Phase 10) | ✓ |
| registry가 폴백까지 내장 | 1차 raw 결손 시 registry가 Naver/yf fetch 트리거 | |

**User's choice:** registry=순수계산+라벨, 폴백은 밖 (권장)
**Notes:** SC5 "폴백 의미 보존/수용"을 fetch 구현이 아닌 "폴백-소스 값 수용 가능" 계약으로 해석. 1차 결손 → metric 빈값+사유(0 금지).

---

## Claude's Discretion

- registry 자료구조·모듈 위치·지표 정의 표현(dataclass vs dict).
- EDGAR Q4=FY−9M 보정 / DART YTD 분해 구체 구현, 분기 분해 엣지케이스.
- 복수 source raw 혼합 시 provenance 라벨링 규칙.
- sanity bounds 검증의 구체 임계.

## Deferred Ideas

- FCF 지표 (CapEx 미저장 → raw 확장 선행).
- EV/EBITDA 지표 (현금잔액·D&A·이자성부채 미저장 → raw 확장 선행).
- 폴백 체인 fetch 오케스트레이션 + 폴백 값 DB 적재 → Phase 10.
- ROE/ROA 기초·기말 평균 분모 옵션 (이번엔 최근값 결정, 추후 비파괴적 도입 가능).
