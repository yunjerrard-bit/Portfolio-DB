# Phase 3 — Discussion Log

**Session:** 2026-05-27
**Workflow:** `/gsd-discuss-phase 3`
**Mode:** default (4 gray areas presented, 3 selected, single-question turns)

> 인간 참조용 — 감사/리트로 목적. 다운스트림 에이전트(researcher/planner)는 03-CONTEXT.md를 봅니다.

---

## Area selection (multiSelect)

**Question:** Phase 3에서 이번에 논의하고 싶은 영역은? (복수 선택)

**Options presented:**
1. PEG 산식 + EPS 데이터 구성
2. 시트1 펀더멘털 컬럼 배치 + 출처 표시 방식
3. 결손 시 폴백 우선순위 + 실패 표시
4. 종목별 시트에도 펀더멘털 노출 여부

**User selected:** 2, 3, 4 (3개 영역). PEG 산식은 Claude 재량으로 위임됨 — RESEARCH.md 권장식 채택 + researcher가 EDGAR 실데이터로 검증 예정.

---

## Area 2: 시트1 펀더멘털 컬럼 배치 + 출처 표시

### Q2.1 컬럼 위치

**Options presented:**
- 임펄스 뒤 (제일 우측 끝) — R/S/T/U
- 산업(D) 다음, 가격(E) 앞
- 거래량(K) 다음, 기술지표 앞

**User selected:** 임펄스 뒤 (제일 우측 끝) → R/S/T/U.

**Resulting decision (D-01):** PER/PEG/GPM/OPM 4셀을 시트1 R/S/T/U에 추가. 시트1 17→21열.

### Q2.2 출처 표시 방식

**Options presented:**
- 셀 주석(Excel 코멘트)
- 별도 출처 컬럼 1개
- 값별 개별 출처 컬럼 4개

**User selected:** 셀 주석(Excel 코멘트).

**Resulting decision (D-02):** `xlsxwriter.write_comment`로 출처 메타를 셀 주석에 표시. 값 셀은 숫자만 유지. 컬럼 수 21로 고정.

---

## Area 3: 결손 시 폴백 우선순위 + 실패 표시

### Q3.1 미국 종목 폴백 체인

**Options presented:**
- EDGAR → yfinance (단일 폴백)
- EDGAR 전용 (폴백 없음)
- EDGAR → yfinance → Naver Finance

**User selected:** EDGAR → yfinance (단일 폴백).

**Resulting decision (D-03):** 미국 종목 폴백 체인 = EDGAR → yfinance.

### Q3.2 한국 종목 폴백 체인

**Options presented:**
- DART → Naver Finance → yfinance
- DART → Naver Finance (yfinance 제외)
- DART 전용

**User selected:** DART → Naver Finance → yfinance.

**Resulting decision (D-04):** 한국 종목 폴백 체인 = DART → Naver Finance → yfinance.

### Q3.3 모든 소스 결손 시 셀 표시

**Options presented:**
- 빈 셀 (주석에 사유)
- "N/A" 텍스트
- 0 또는 특수값

**User selected:** 빈 셀 (주석에 사유).

**Resulting decision (D-05):** 결손 셀은 빈 칸 + 주석 `"조회 실패: <이유>"`.

---

## Area 4: 종목별 시트에도 펀더멘털 노출 여부

### Q4.1 종목별 시트 노출

**Options presented:**
- 시트1만 노출
- 종목별 시트 상단(A1 근처)에 최신 4값 메타 표시
- 종목별 시트에 분기별 시계열 컬럼 추가

**User selected:** 시트1만 노출.

**Resulting decision (D-06):** 종목별 시트(97열) 변경 없음. 펀더멘털은 시트1에만.

---

## Claude's Discretion (사용자가 결정 안 함 → research/plan-phase 책임)

- PEG 산식: `PEG = PER / (EPS_TTM/EPS_prior_year_TTM − 1) × 100` (SUMMARY.md 권장). researcher가 EDGAR 실데이터로 검증.
- EDGAR XBRL concept tag 매핑: researcher 책임.
- DART account_nm 매핑: researcher 책임.
- 캐시 키 디자인: `(source, ticker, quarter_label)` 권장.
- 토큰버킷 limiter 추가: `io/throttle.py` 패턴 확장.
- 출처 라벨: `'EDGAR'/'yf'/'DART'/'Naver'` 짧은 코드.
- Naver scraping 구현: `httpx + BeautifulSoup4`.
- 신규 의존성: `edgartools>=4`, `OpenDartReader>=0.2`, `beautifulsoup4`, `lxml`.

## Deferred Ideas

- 데이터 품질 별도 시트 — Phase 4 (EXEC-04)
- 펀더멘털 σ 색 신호 — 추후 v2/ADV
- 분기별 펀더멘털 시계열 — 추후 ADV-03 슬롯
- API 키 자동 검증 — Phase 4 또는 backlog

## Scope creep redirects

없음 — 사용자가 phase boundary 안에서만 결정.

---

*Discussion log written: 2026-05-27*
