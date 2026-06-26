# Backlog: 펀더멘털 히스토리 & 델타 추출 (새 phase 후보)

**Origin:** 2026-06-04 사용자 설계 대화 (Q1·Q2·Q3)
**Status:** 설계 확정(locked) — 실행 보류. **현재 Phase 3 마무리 후 새 phase로 추가** 예정.
**Sequencing:** Phase 3(시트1 PER/PEG/GPM/OPM 최신값) 완료 → 이 설계를 새 phase로 discuss/plan.

> 현재 Phase 3는 "매 실행마다 전 종목 fetch + 7일 TTL 캐시 + 시트1 최신값 표시"까지가 범위.
> 이 백로그는 그것을 "영구 히스토리 + 변경분만 추출 + 트렌드 엑셀 + 확장형 지표 registry"로 확장한다.

---

## 확정 결정 (locked)

### D-H1 — 변경 감지 키 = 접수번호 (Q1)
- 매 실행 시 종목별로 **최신 접수번호를 가볍게(메타데이터만) 조회** → 저장된 `last_accession`과 비교.
  - 같음 → 외부 전체호출 **생략**(평소 실행 호출 ≈ 0, 분기 경계에서만 발생).
  - 다름 → 새 분기 **또는 정정공시** → 전체 facts 추출 → 누적 저장 → `last_accession` 갱신.
- 키 선택 근거: 단순 "분기 라벨(2026Q2)"만 비교하면 **정정공시(같은 분기 값 수정)를 놓침**.
  정정공시는 새 식별자를 부여받음 → 이를 키로 쓰면 새 분기 + 정정 둘 다 포착.
  - EDGAR: **accession number**
  - DART: **`rcept_no`(접수번호)**, 가벼운 조회는 `list` API
- 폴백 소스(yfinance/Naver)는 접수번호 개념 없음 → **분기 라벨**로 보완(폴백은 D-07대로 소수 전용).
  폴백으로 채운 값은 "다음 1차 성공 시 갱신".

### D-H2 — 원천 저장 + 지표 registry (Q2)
- **저량(stock)** = 재무상태표 시점값 → **가장 최근 분기 값** 그대로. 예: PBR(BPS), 부채비율, 유동비율, 자본총계, 발행주식수.
- **유량(flow)** = 손익 기간누적 → **TTM(최근 4분기 합)**. 예: PER(EPS), 매출, 영업이익, GPM, OPM.
- **하이브리드** = 유량분자 ÷ 저량분모 → **분자 TTM / 분모 최근값(또는 기초·기말 평균)**. 예: ROE(순이익TTM/자본), ROA.
- 저장은 **최종 지표가 아니라 분기별 원천 항목(raw)** 을 누적:
  매출·매출총이익·영업이익·순이익·EPS·자본총계·부채총계·발행주식수 등.
  → 추후 ROE·PBR 등 신규 지표 추가 시 **재호출 없이** 저장된 원천에서 즉시 계산.
- **지표 registry**: 각 지표 = `{이름, 유형(저량/유량/하이브리드), 산식, 필요한 원천필드, 소스별 매핑}`.
  기존 `src/stocksig/io/dart_account_map.py`(account_id 1차/account_nm 2차)가 소스별 매핑의 시작점.

#### 구현 시 처리할 디테일 (메모 — 지금 결정 불필요)
- EDGAR Q4 = 연간(FY) − 9개월누적(9M) 보정.
- DART는 누적(YTD) 보고가 흔함 → 분기 분해 = thisQ누적 − 직전Q누적.
- TTM 4분기 중 결손 분기 처리(결손 시 빈값 + 사유, 0 금지 — D-05 일관).

### D-H3 — 저장소 = SQLite (Q3-a)
- 파일: **`data/fundamentals.db`** (영구 보존, `.gitignore` — 생성 데이터, TTL 없음. 기존 `.cache/`와 별개).
- **raw 테이블**: `(ticker, source, quarter, accession_or_rcept, field, value, fetched_at)` — 분기별 원천 long 저장.
- **state 테이블**: `(ticker, source, last_accession, last_checked_at)` — D-H1 델타 감지용.
- 선택 근거: 델타 비교가 SELECT 한 번(효율), 누적·영구, `sqlite3` 표준 라이브러리 + diskcache가 이미 sqlite 기반, Claude가 직접 쿼리 가능, 단일 파일.
- 대안 기각: JSONL/Parquet — 200종목 규모 비교·집계에서 SQLite보다 불리.

### D-H4 — 사람용 엑셀 출력 (Q3-a)
- 파일: **`fundamentals_history.xlsx`** — 매 실행 시 DB에서 렌더(소스 진실은 DB).
- **지표별 시트**: `[PER] [PEG] [ROE] [GPM] [OPM] [PBR] …` 각 시트 = **행=종목 / 열=분기 누적** 매트릭스.
- **추가 시트 2개**:
  - `[원천]` — 분기별 raw long. 검증·디버깅·신규 지표 산출 근거.
  - `[최신 스냅샷]` — 종목 1행 × 전 지표 최신값(현 portfolio 시트1과 같은 "한눈에" 뷰).
- **가격 의존 지표 규칙(PER/PBR)**: 과거 열 = **그 분기말 종가** 기준(트렌드 일관성), **최신 열만 현재가**.
  raw(EPS·BPS 등)를 저장해두므로 이 산정 방식은 추후 변경 가능.

---

## 새 phase 제안 (Phase 3 완료 후)
- **가칭:** "펀더멘털 히스토리 & 델타 추출"
- **신규 요구사항 슬롯 후보:** `FUND-07 영구 히스토리 저장(SQLite)`, `FUND-08 접수번호 기반 델타 추출`,
  `FUND-09 지표 registry(저량/유량/하이브리드)`, `FUND-10 트렌드 엑셀(지표별 매트릭스)`.
- **의존:** Phase 3(edgar_client/dart_client/fundamentals.py 존재) — 그 fetch 층 위에 저장·델타·렌더 추가.
- **착수 명령(준비되면):** `/gsd-phase --add` 로 ROADMAP에 phase 추가 → `/gsd-discuss-phase N`(이 문서를 입력으로) → `/gsd-plan-phase N`.
