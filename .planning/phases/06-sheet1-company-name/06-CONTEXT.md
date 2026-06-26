# Phase 6 Context: 시트1 기업명 열

**Milestone:** v1.2 시트1 기업명 표시
**Requirements:** COMPANY-01, COMPANY-02, COMPANY-03, COMPANY-04
**Source:** 사용자가 `/gsd-plan-phase` 호출 시 핵심 결정을 직접 제공 (discuss-phase 대체).

## Goal

시트1(통합 포트폴리오)의 티커 열(A)과 시장 열 사이에 영문 기업명(Company) 열을 추가해, 사용자가 티커만 보고도 종목을 한눈에 식별할 수 있게 한다. 기존 시트1 레이아웃은 컬럼 1칸 시프트 후에도 회귀 없이 동작해야 한다.

## LOCKED Decisions (사용자 확정 — 변경 금지)

### D1 (LOCKED): 데이터 소스 = yfinance 일괄 조회, DART 미사용
- 모든 종목(미국·한국)의 기업명을 yfinance에서 받아온다.
- DART를 거치지 않는다 — 사용자 우려: "DART를 거치면 불필요하게 호출 양이 늘 것 같아서."
- 함의/주의: 현재 파이프라인은 yfinance `.info`(`Ticker(...).info`/`longName`)를 **전혀 조회하지 않는다** (grep 0건, OHLCV는 `download`/`history` 경로만 사용). 따라서 기업명 조회는 **티커당 신규 yfinance 호출**을 추가한다. 이 비용을 어떻게 throttle/retry/캐시로 흡수할지가 핵심 (→ COMPANY-04, 연구 대상). CLAUDE.md는 yfinance 레이트리밋(`threads=False`/`threads=2` + tenacity backoff)을 강하게 경고.

### D2 (LOCKED): 영문명만 기록 (한국 기업 포함)
- 한국 종목(`.KS`/`.KQ`)도 한글이 아닌 영문 기업명으로 기록한다 (yfinance `longName`은 한국 종목도 대개 영문 반환).

### D3 (LOCKED): 위치·범위 = 시트1 단일 열, 종목 시트 불변
- 기업명 열은 **시트1에만** 추가. 티커 열(A)과 시장 열 사이 → 새 B열 (이후 기존 열 전부 +1 시프트).
- 종목별 시트(sheet_per_ticker.py)는 변경하지 않는다 (A1=티커 유지). — 사용자 확정: "시트1만".

## Claude's Discretion (구현 자유 — 연구·계획에서 결정)

- yfinance 기업명 필드 선택: `longName` vs `shortName` (longName 우선, 결손 시 shortName 폴백 권장 — 연구로 확정).
- 조회 시점·구조: 기존 fetch 파이프라인(OHLCV/펀더멘털)과 같은 단계에서 함께 받을지, 별도 경량 조회 함수로 분리할지. 캐시 키 설계(티커→기업명, 만료 정책).
- 컬럼 시프트 구현 방식: sheet_portfolio.py의 하드코딩 인덱스(col 0~20+)를 상수/오프셋으로 정리할지, 헤더 리스트 기반으로 인덱스를 도출하도록 리팩터할지.
- 실패/결손 폴백: 빈칸 vs 티커 표시 — 사용자 직관에 맞는 쪽 (연구·계획 제안).

## Out of Scope (Phase 6)

- 종목 시트 A1에 기업명 병기 — 이번 범위 아님 (시트1만).
- 한글 기업명 표기 / DART·네이버 기업명 조회 — D1/D2로 배제.
- 기업명 기반 정렬·필터·검색 기능 — 표시만.

## Risks / Notes

- **회귀 위험(최대):** sheet_portfolio.py는 `write_*(row, <하드코딩 col>)`을 다수 사용. 한 칸 시프트가 모든 후속 열·하이퍼링크 타깃·조건부 서식·열 너비·실패 행 마커에 영향. 충분한 회귀 테스트 필요 (test_sheet_portfolio.py 좌표 +1).
- **freeze 결정 (LOCKED, 사용자 확정):** 시트1 freeze는 `freeze_panes(5,1)` = **B6 유지**(티커 열만 고정). 기업명까지 고정(C6)하지 **않는다**. → `test_freeze_panes.py`는 무수정.
- **호출량(D1 직결):** 기업명 조회가 추가 yfinance 왕복을 만든다 — 캐시·throttle 없이는 200종목에서 레이트리밋 위험. COMPANY-04로 명시.
