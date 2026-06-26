# Requirements: v1.3 펀더멘털 히스토리 & 델타 추출

**Milestone:** v1.3
**Core Value:** 중앙값 ± 표준편차를 기준으로 한 색상 신호가 통합 포트폴리오 시트에서 정확하고 직관적으로 보여야 한다.

## v1.3 Requirements

### 펀더멘털 히스토리 & 델타 (FUND)

<!-- 입력: 백로그 fundamentals-history-delta.md (D-H1~D-H4, locked). 의존: Phase 3 fetch 층. -->

- [x] **FUND-07**: 매 실행 시 각 종목의 분기별 펀더멘털 원천 항목(매출·매출총이익·영업이익·순이익·EPS·자본총계·부채총계·발행주식수 등)이 SQLite(`data/fundamentals.db`)에 영구 누적 저장되어, 과거 분기 데이터가 사라지지 않고 보존된다 (raw long 테이블 + 델타용 state 테이블, TTL 없음).
- [x] **FUND-08**: 새 분기 공시·정정공시가 없으면(저장된 `last_accession`과 최신 접수번호 EDGAR accession / DART `rcept_no` 비교) 외부 펀더멘털 전체 호출이 생략되고, 변경이 있을 때만 해당 종목 전체 facts를 재추출·누적한다 — 평소 실행 시 펀더멘털 외부 호출이 사실상 0에 수렴한다.
- [x] **FUND-09**: 지표가 유형별(저량=최근 분기값 / 유량=TTM 4분기 합 / 하이브리드=유량분자÷저량분모) registry로 정의되어, 저장된 원천 raw로부터 PER/PEG/GPM/OPM 및 신규 지표(ROE·PBR 등)를 외부 재호출 없이 계산할 수 있다.
- [ ] **FUND-10**: 사용자가 `fundamentals_history.xlsx`(기존 `portfolio_YYYYMMDD.xlsx`와 별도 파일)를 열어 지표별 분기 트렌드(행=종목·열=분기 매트릭스), 분기별 원천 데이터, 종목별 최신 스냅샷을 육안 확인할 수 있다 (과거 PER/PBR은 분기말 종가, 최신 열만 현재가).
- [x] **FUND-11**: 기존 `portfolio_YYYYMMDD.xlsx` 시트1의 PER/PEG/GPM/OPM이 동일한 통합 store/registry에서 계산된 값을 읽어 표시된다 — 중복 fetch·계산 경로(구 `_compute_*` + 7일 캐시) 제거, 두 파일 간 값 드리프트 없음, 셀 출처(provenance)·결손 NaN 처리·조건부 색 신호가 회귀 없이 동작하며, 평소 외부 호출이 ≈0이다 (단일 원천 + 단계적 이관 결정).

## v1.1 Requirements (완료)

### 주봉 임펄스 (IMPULSE)

- [x] **IMPULSE-01**: 주봉 임펄스가 주 마지막 거래일(금요일, 휴장 시 그 주 실제 마지막 거래일) 기준으로 직전 완성 주 대비 주봉 EMA11과 주봉 MACD-OSC의 변화 부호를 조합해 산출된다 — 둘 다 상승 → 녹색, 둘 다 하락 → 적색, 혼조 → 청색
- [x] **IMPULSE-02**: 주중(주 마지막 거래일 이전) 행은 직전 완성 주의 주봉 임펄스 값을 그대로 고정 표시한다 (다음 주 마지막 거래일에만 갱신)
- [x] **IMPULSE-03**: 주봉 임펄스가 시트1과 종목 시트 모두에서 주 단위 계단형(한 주 내 동일 값)으로 표시된다
- [x] **IMPULSE-04**: 일봉 임펄스와 표시용 진행형 주봉 추세 컬럼(`EMA_Close_11_week_trend`/`MACD_OSC_week` 등)은 변경되지 않는다 (기존 동작 회귀 무손상)

## v1.2 Requirements (완료)

### 시트1 기업명 (COMPANY)

- [x] **COMPANY-01**: 시트1(통합 포트폴리오)의 티커 열(A)과 시장 열 사이에 '기업명(Company)' 열이 추가되고, 각 성공 티커 행에 해당 종목의 영문 기업명이 표시된다 (한국 종목도 영문).
- [x] **COMPANY-02**: 기업명은 yfinance에서 일괄 조회한다 — DART를 호출하지 않는다 (호출량 우려, 사용자 LOCKED 결정). 모든 종목 영문명만 기록.
- [x] **COMPANY-03**: 기업명 조회 실패/결손 시 빈칸 또는 티커 폴백으로 안전 처리하고, 컬럼 1칸 시프트 후 시트1의 후속 열·티커 하이퍼링크·조건부 색 서식·freeze(B6 유지 — 티커 열만 고정)·실패 티커 행 마커·펀더멘털 셀이 회귀 없이 동작한다.
- [x] **COMPANY-04**: 기업명 조회가 기존 OHLCV/펀더멘털 fetch의 throttle·retry·캐시 정책을 따르며, 다수 종목(목표 200) 처리가 비현실적으로 느려지지 않는다.

## Future Requirements (deferred)

- IN-01/03/04/05/06 위생 (US 진행 로그 정확성, 테스트 캐시 오염, 실패목록 3중 출력, PEG 턴어라운드 라벨, DART probe corp_code zip 비용) — v1.0 코드 리뷰 발견
- Phase 1·2 VERIFICATION.md 부재 (기능은 통합+UAT 사후 입증)
- Phase 2 200티커 실환경 부하 실증

## Out of Scope (v1.3)

- 시트1(`portfolio_*.xlsx`) 레이아웃·색 신호 변경 — 히스토리는 별도 파일(`fundamentals_history.xlsx`)로 분리, Core Value 불변
- 폴백 소스(yfinance/Naver)의 접수번호 기반 델타 — 접수번호 개념 없음 → 분기 라벨 보완만 (D-07대로 소수 전용)
- 신규 외부 데이터 소스 추가 — 기존 EDGAR/DART/yf/Naver fetch 층 재사용
- 가격 의존 지표(PER/PBR) 과거 열의 현재가 재산정 — 분기말 종가 기준 고정(트렌드 일관성), raw 저장으로 추후 변경 가능

## Traceability

| Req ID | Phase | Status |
|--------|-------|--------|
| IMPULSE-01 | Phase 5 | complete |
| IMPULSE-02 | Phase 5 | complete |
| IMPULSE-03 | Phase 5 | complete |
| IMPULSE-04 | Phase 5 | complete |
| COMPANY-01 | Phase 6 | Complete |
| COMPANY-02 | Phase 6 | Complete |
| COMPANY-03 | Phase 6 | Complete |
| COMPANY-04 | Phase 6 | Complete |
| FUND-07 | Phase 7 | Complete |
| FUND-08 | Phase 7 | Complete |
| FUND-09 | Phase 8 | Gaps (PEG 미완) |
| FUND-10 | Phase 9 | pending |
| FUND-11 | Phase 10 | Complete |
