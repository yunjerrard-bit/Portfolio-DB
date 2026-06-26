# Roadmap: 표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트

**Core Value:** 중앙값 ± 표준편차를 기준으로 한 색상 신호가 통합 포트폴리오 시트에서 정확하고 직관적으로 보여야 한다.

## Milestones

- ✅ **v1.0 MVP** — Phases 1-4 (shipped 2026-06-12) — [archive](milestones/v1.0-ROADMAP.md)
- ✅ **v1.1 주봉 임펄스 주간화** — Phase 5 (completed 2026-06-16) — 진행형 주봉 임펄스를 금-금 주간 계단형 신호로 전환
- ✅ **v1.2 시트1 기업명 표시** — Phase 6 (completed 2026-06-16) — 시트1에 yfinance 일괄 조회 영문 기업명 열 추가
- 🚧 **v1.3 펀더멘털 히스토리 & 델타 추출** — Phases 7-10 (planning) — 펀더멘털 원천을 SQLite로 영구 누적, 접수번호 델타로 평소 외부 호출 ≈0, 트렌드 엑셀로 분기 추이 표시, 시트1을 통합 store/registry로 이관(단일 원천)

## Phases

<details>
<summary>✅ v1.0 MVP (Phases 1-4) — SHIPPED 2026-06-12</summary>

- [x] Phase 1: 기반 + 단일 티커 수직 슬라이스 (10 plans) — code-complete
- [x] Phase 2: N개 티커 스케일링 + 포트폴리오 요약 시트 (5 plans) — code-complete
- [x] Phase 3: 기본적 분석 데이터(EDGAR/DART/yfinance·Naver 보완) (5 plans) — completed 2026-06-05
- [x] Phase 4: 품질·견고성 마감(콘솔 요약·고정창·인증·색 톤) (3 plans) — completed 2026-06-12

전체 phase 상세·성공기준은 [milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md) 참조.
검증: 통합 62/62 WIRED · 244 테스트 · UAT 7/7 · 보안 7/7. 연기 항목: STATE.md Deferred Items.

</details>

### v1.1 주봉 임펄스 주간화

- [x] **Phase 5: 주봉 임펄스 주간화** - 주봉 임펄스를 금-금 주간 변화 부호 조합으로 산출하고 주중 행에 ffill 고정 (주 단위 계단형), 일봉 임펄스·진행형 추세 컬럼 불변 (completed 2026-06-16)

### v1.2 시트1 기업명 표시

- [x] **Phase 6: 시트1 기업명 열** - 시트1(통합 포트폴리오)의 티커 열과 시장 열 사이에 yfinance로 일괄 조회한 영문 기업명(Company) 열을 추가하고, 기존 컬럼·하이퍼링크·조건부서식·freeze가 시프트 후에도 정상 동작하게 한다 (completed 2026-06-16)

### v1.3 펀더멘털 히스토리 & 델타 추출

- [x] **Phase 7: 펀더멘털 SQLite 저장 + 접수번호 델타** - 분기별 원천 raw를 `data/fundamentals.db`에 영구 누적하고, 저장된 `last_accession`(EDGAR accession / DART rcept_no)과 최신 접수번호를 비교해 변경이 있을 때만 전체 facts를 재추출·누적한다 (평소 외부 호출 ≈0) (completed 2026-06-18)
- [x] **Phase 8: 지표 registry 계산** [검증 gaps_found 2026-06-19 — PEG 계산 경로 미완, /gsd:plan-phase 08 --gaps 대기] - 저량/유량(TTM)/하이브리드 유형의 지표 registry를 정의하고, 저장된 원천 raw로부터 PER/PEG/GPM/OPM 및 신규 지표(ROE·PBR 등)를 외부 재호출 없이 계산한다
 (completed 2026-06-22)
- [x] **Phase 9: 트렌드 엑셀 렌더** - DB에서 `fundamentals_history.xlsx`(별도 파일)를 렌더 — 지표별 분기 매트릭스 시트 + [원천] + [최신 스냅샷], 과거 PER/PBR은 분기말 종가·최신만 현재가
 (completed 2026-06-22)
- [x] **Phase 10: 시트1 펀더멘털 통합 store/registry 이관** - 기존 `portfolio_*.xlsx` 시트1의 PER/PEG/GPM/OPM을 통합 store/registry 계산값에서 읽도록 이관하고 구 `_compute_*`+7일 캐시 중복 경로를 제거한다 (단일 원천 — 두 파일 값 일치, 출처·NaN·색 신호 회귀 무손상) (completed 2026-06-23)

## Phase Details

### Phase 5: 주봉 임펄스 주간화
**Goal**: 사용자가 주봉 임펄스를 진행형(매일 출렁임)이 아닌 금요일-대-금요일 주간 신호로 보게 된다 — 시트1·종목 시트 모두에서 한 주 동안 같은 값으로 고정되고, 다음 주 마지막 거래일에만 갱신된다. 기존 금요일-앵커 주봉 통계 정책과 일관성이 맞춰진다.
**Depends on**: Phase 4 (v1.0 완료 — 기존 주봉 컬럼 산출부·week_close_mask·임펄스 표시 배선 위에서 동작)
**Requirements**: IMPULSE-01, IMPULSE-02, IMPULSE-03, IMPULSE-04
**Success Criteria** (what must be TRUE):
  1. 종목 시트의 주봉 임펄스 열이 한 주 내 모든 행에서 동일한 값(녹/적/청)을 가지며, 값은 주 마지막 거래일(금)에서 직전 완성 주 대비 주봉 EMA11·주봉 MACD-OSC의 변화 부호 조합으로 결정된다 (둘 다 ↑ 녹 / 둘 다 ↓ 적 / 혼조 청).
  2. 금요일이 휴장인 주에는 그 주 실제 마지막 거래일(목 등)을 주 경계로 삼아 임펄스가 산출·고정되며, 빈칸·오산출이 발생하지 않는다.
  3. 시트1 통합 포트폴리오의 각 티커 (주)임펄스 셀이 해당 종목 시트의 최신 주봉 임펄스(주 단위 계단형 값)와 일치한다.
  4. 일봉 임펄스 열과 표시용 진행형 주봉 추세 컬럼(`EMA_Close_11_week_trend`/`MACD_OSC_week` 등)은 v1.0과 동일하게 매일 변하며, 기존 동작에 회귀가 없다 (회귀 테스트 통과).
**Plans**: 1 plan
- [x] 05-01-PLAN.md — 주봉 임펄스 금-금 계단형 전환 (impulse.py 산출 + main_run 정합화 + 회귀/신규 테스트 + 수기 시각 검증)

### Phase 6: 시트1 기업명 열
**Goal**: 사용자가 시트1에서 티커 옆에 기업명을 보고 종목을 한눈에 식별할 수 있다 — 티커 열과 시장 열 사이에 영문 기업명(Company) 열이 추가되고, 모든 종목(미국·한국)의 이름이 yfinance에서 일괄 조회되어 영문으로 표시된다. 기존 시트1 레이아웃(컬럼·하이퍼링크·조건부서식·freeze·펀더멘털 셀)은 컬럼 시프트 후에도 회귀 없이 동작한다.
**Depends on**: Phase 2 (시트1 sheet_portfolio.py 레이아웃·행 writer), Phase 3 (티커 fetch 파이프라인·캐시·throttle)
**Requirements**: COMPANY-01, COMPANY-02, COMPANY-03, COMPANY-04
**Success Criteria** (what must be TRUE):
  1. 시트1의 티커 열(A)과 시장 열 사이에 '기업명' 열이 추가되고, 각 성공 티커 행에 해당 종목의 영문 기업명이 표시된다 (한국 종목도 영문).
  2. 기업명은 yfinance에서 조회한다 — DART를 호출하지 않는다. 조회 실패/결손 시 빈칸 또는 티커 폴백으로 안전 처리되며 다른 셀을 깨뜨리지 않는다.
  3. 컬럼 1칸 시프트 후 시트1의 모든 후속 열(시장·티어·산업·가격·σ·펀더멘털 PER/PEG/GPM/OPM)·티커 하이퍼링크·조건부 색 서식·freeze(B6 유지 — 티커 열만 고정, 사용자 결정)·실패 티커 행 마커가 정상 동작한다 (회귀 테스트 통과).
  4. 기업명 조회가 기존 OHLCV/펀더멘털 fetch의 throttle·retry·캐시 정책을 따르며, 다수 종목(목표 200) 처리가 비현실적으로 느려지지 않는다.
**Plans**: 1 plan
- [x] 06-01-PLAN.md — yfinance 영문 기업명 조회(+30일 캐시) + 시트1 헤더 기반 명명 인덱스 리팩터·기업명 B열 삽입 + 회귀 스위트·수기 시각 검증

### Phase 7: 펀더멘털 SQLite 저장 + 접수번호 델타
**Goal**: 사용자가 도구를 실행할 때마다 각 종목의 분기별 펀더멘털 원천이 영구 히스토리로 누적되고, 새 분기·정정공시가 없으면 외부 펀더멘털 호출이 사실상 발생하지 않는다. 과거 분기 데이터가 사라지지 않고 보존되어 추후 신규 지표 계산의 원천이 된다.
**Depends on**: Phase 3 (펀더멘털 fetch 층 — `edgar_client.py`/`dart_client.py`/`fundamentals.py` 위에 저장·델타 추가)
**Requirements**: FUND-07, FUND-08
**Success Criteria** (what must be TRUE):
  1. 실행 후 `data/fundamentals.db`가 생성/갱신되고, 각 종목의 분기별 원천 항목(매출·매출총이익·영업이익·순이익·EPS·자본총계·부채총계·발행주식수 등)이 raw long 테이블에 누적되며, 과거 분기 행이 재실행으로 사라지지 않는다 (TTL 없음).
  2. state 테이블에 종목·소스별 `last_accession`(EDGAR accession / DART rcept_no)이 기록되고, 다음 실행 시 최신 접수번호와 비교된다.
  3. 저장된 접수번호와 최신 접수번호가 같은 종목은 외부 펀더멘털 전체 호출이 생략되어, 변경 없는 평소 실행의 펀더멘털 외부 호출 건수가 0에 수렴한다 (가벼운 list/메타 조회만 발생).
  4. 접수번호가 달라진 종목(새 분기 또는 정정공시)만 전체 facts를 재추출·누적하고 `last_accession`을 갱신한다.
  5. `data/fundamentals.db`는 `.gitignore` 처리되어 커밋되지 않고, 기존 `.cache/`(OHLCV 7일 TTL)와 별개로 동작한다 (회귀 무손상).
**Plans**: 4 plans
- [x] 07-01-PLAN.md — fundamentals_store.py SQLite WAL store(raw_facts+delta_state DDL·upsert·state CRUD·델타 카운터) + Wave 0 테스트 스캐폴드·conftest 격리 fixture (FUND-07)
- [x] 07-02-PLAN.md — EDGAR/DART per-quarter raw 추출(additive) + dart_account_map BS/CF/현금흐름 매핑 슈퍼셋 확장 + fixture/테스트 (FUND-07, D-03/D-04)
- [x] 07-03-PLAN.md — fundamentals_delta.py 접수번호 probe + delta_state 비교 + skip/refetch 오케스트레이션(probe 실패 안전 폴백·DART 싱글톤) + ≈0 호출 spy 테스트 (FUND-08)
- [x] 07-04-PLAN.md — main_run 히스토리 경로 배선(시트1 불변·델타 요약) + .gitignore data/ + ≈0·시트1 불변 통합 테스트 (FUND-07/08, SC3/SC5)

### Phase 8: 지표 registry 계산
**Goal**: 저장된 분기별 원천 raw만으로 모든 펀더멘털 지표를 외부 재호출 없이 계산할 수 있다 — 지표가 유형(저량/유량 TTM/하이브리드)별 registry로 정의되어, 신규 지표(ROE·PBR 등)를 추가해도 원천 재수집 없이 즉시 산출된다.
**Depends on**: Phase 7 (raw 테이블에 원천이 누적되어 있어야 계산 입력이 존재)
**Requirements**: FUND-09
**Success Criteria** (what must be TRUE):
  1. 각 지표가 `{이름, 유형(저량/유량/하이브리드), 산식, 필요한 원천필드, 소스별 매핑}` registry로 정의되고, 기존 `dart_account_map.py` 매핑을 시작점으로 소스별 원천필드가 연결된다.
  2. 저량 지표는 최근 분기값, 유량 지표는 TTM(최근 4분기 합), 하이브리드는 분자 TTM ÷ 분모 최근값(또는 기초·기말 평균) 규칙으로 계산된다.
  3. 저장된 원천 raw만으로 PER/PEG/GPM/OPM가 외부 재호출 없이 재현되고, registry에 ROE·PBR 등 신규 지표를 추가하면 동일 원천에서 즉시 계산된다.
  4. TTM 4분기 중 결손 분기는 빈값 + 사유로 처리되고 0으로 대체되지 않는다 (D-05 결손 정책 일관).
  5. registry/계산 층이 단일 원천으로서 시트1 이관(Phase 10)의 백엔드 계약을 충족한다 — metric별 출처(provenance) 라벨, 기존 metric별 폴백 의미(PER: DART→Naver→yf 등), '최신값=현재가' 산정을 보존/수용한다.
**Plans**: 4 plans
- [x] 08-01-PLAN.md — raw 진실 확정 spike(DART thstrm_amount 분기/누적·EDGAR Q4 갭) + store fetch_raw_quarters 헬퍼 + 엔진 테스트 RED 스캐폴드·raw 행 builder fixture (FUND-09, Wave 1)
- [x] 08-02-PLAN.md — metrics_registry.py 9종 MetricDef(저량/유량/하이브리드/주당/파생) + 기존 dart_account_map/edgar concept 소스 매핑 연결 + 정의 무결성·확장성 테스트 (FUND-09 SC1/SC3, Wave 1)
- [x] 08-03-PLAN.md — metrics_engine.py compute_matrix(분기 매트릭스 전체) — 유형별 계산·TTM 결손 게이트·per-share/가격 분리·sanity bounds·per-metric provenance + PER/PEG/GPM/OPM 재현·ROE/PBR/PCR/PSR/ROA 신규 (FUND-09 SC2~5, Wave 2)
- [x] 08-04-PLAN.md — [gap closure] PEG 2단계 공개 API compute_peg_cell(_compute_peg 실호출 + Phase 9/10 소비 계약 docstring + value 단언 테스트) + fetch_raw_quarters source 우선순위(EDGAR→DART→yf, WR-01) — 검증 진실 #8·#9 블로커 해소 (FUND-09, Wave 3)
**Design note**: 이 registry는 트렌드 엑셀(Phase 9)과 시트1(Phase 10) 양쪽이 읽는 단일 원천이다 — 두 출력의 PER 등 값이 드리프트 없이 일치해야 한다.

### Phase 9: 트렌드 엑셀 렌더
**Goal**: 사용자가 `fundamentals_history.xlsx`(기존 `portfolio_YYYYMMDD.xlsx`와 별도 파일)를 열어 펀더멘털의 분기 트렌드, 원천 데이터, 최신 스냅샷을 육안으로 확인할 수 있다. 기존 시트1 색 신호(Core Value)는 전혀 건드리지 않는다.
**Depends on**: Phase 8 (지표 계산 결과가 있어야 렌더 입력이 존재), Phase 7 (DB가 소스 진실)
**Requirements**: FUND-10
**Success Criteria** (what must be TRUE):
  1. 실행 시 `fundamentals_history.xlsx`가 DB에서 렌더되어 별도 파일로 생성되고, 기존 `portfolio_YYYYMMDD.xlsx`의 레이아웃·색 신호는 변경되지 않는다.
  2. 지표별 시트(PER/PEG/ROE/GPM/OPM/PBR 등)가 행=종목·열=분기 매트릭스로 표시되어 분기 추이를 한눈에 볼 수 있다.
  3. `[원천]` 시트에 분기별 raw long이, `[최신 스냅샷]` 시트에 종목 1행 × 전 지표 최신값이 표시된다.
  4. 가격 의존 지표(PER/PBR)의 과거 열은 그 분기말 종가 기준으로, 최신 열만 현재가 기준으로 산정된다 (트렌드 일관성).
**Plans**: 3 plans
- [x] 09-01-PLAN.md — quarter_price(분기말 종가 D-09) + trend_color(상대색 D-05/06/07·YoY 글리프 D-08) 순수 로직 + 네트워크 0 fixture/테스트 스캐폴드
- [x] 09-02-PLAN.md — history_workbook 팩토리 + 지표 매트릭스 시트(식별5열·최신왼쪽·정적 상대색·결손 '-'·A열 freeze) + [원천]/[최신 스냅샷] 시트 (시트1 불변)
- [x] 09-03-PLAN.md — history_render 오케스트레이션(정렬 D-03·가격주입·분기별 PEG·매트릭스 재구성) + main.py history 서브커맨드(main_run 분리 D-15) + SC1~4·시트1 불변 통합 테스트
**UI hint**: yes

### Phase 10: 시트1 펀더멘털 통합 store/registry 이관
**Goal**: 기존 `portfolio_YYYYMMDD.xlsx` 시트1의 PER/PEG/GPM/OPM이 통합 store/registry(Phase 7·8)에서 계산된 값을 읽어 표시된다 — 펀더멘털 fetch·계산이 단일 원천으로 일원화되어 트렌드 엑셀과 시트1의 값이 항상 일치하고, 시트1도 접수번호 델타 덕에 평소 외부 호출이 ≈0이 된다. Core Value(시트1 색 신호)는 회귀 없이 보존된다.
**Depends on**: Phase 7 (store+델타), Phase 8 (registry 계산 — 시트1 백엔드 계약), Phase 6 (현 시트1 펀더멘털 셀 배선)
**Requirements**: FUND-11
**Success Criteria** (what must be TRUE):
  1. 시트1의 PER/PEG/GPM/OPM이 통합 store/registry 계산값을 읽어 표시되고, 같은 종목·시점의 값이 `fundamentals_history.xlsx` 최신 스냅샷과 일치한다 (드리프트 없음).
  2. 구 펀더멘털 경로(`fundamentals.py`의 `_compute_*` 직접 계산 + 7일 `.cache/fundamentals`)의 중복 fetch·계산이 제거되고, 시트1도 변경 없는 평소 실행에서 펀더멘털 외부 호출이 0에 수렴한다.
  3. 셀 출처(provenance) 주석(EDGAR/DART/yf/Naver), 결손 NaN→빈칸 안전 처리(WR-01), API 키 미누설(CR-01)이 이관 후에도 동일하게 동작한다 (회귀 테스트 통과).
  4. 시트1의 조건부 색 신호·하이퍼링크·freeze·기업명 열·실패행 마커가 회귀 없이 동작한다 (Core Value 보호 — 전 회귀 스위트 그린).
**Plans**: 3 plans
- [x] 10-01-PLAN.md — 공유 헬퍼 inject_prices_for_quarter 추출 + matrix_to_fundamentals 어댑터(provenance 라벨·PEG source 승계·빈DB 빈칸) + Wave 0 테스트 (FUND-11, D-06/08/09)
- [x] 10-02-PLAN.md — main_run.run 재배선(sync→read→write·_fundamentals_with_auth 제거·어댑터 주입) + 단일원천·외부호출 0 통합 테스트 (FUND-11, D-01/03/07)
- [x] 10-03-PLAN.md — 구 fetch 경로·.cache/fundamentals 헬퍼·요약 줄 제거(보존계약·store 추출기·OHLCV 캐시 무손상) + σ-bucket 색 회귀·D-02 빈칸 테스트 (FUND-11, D-03/04/05)

## Progress

| Phase | Milestone | Plans Complete | Status | Completed |
| ----- | --------- | -------------- | ------ | --------- |
| 1. 기반 + 단일 티커 | v1.0 | 10/10 | Complete | 2026-06 |
| 2. N티커 스케일링 + 포트폴리오 | v1.0 | 5/5 | Complete | 2026-06 |
| 3. 펀더멘털(EDGAR/DART/yf·Naver) | v1.0 | 5/5 | Complete | 2026-06-05 |
| 4. 품질·견고성 마감 | v1.0 | 3/3 | Complete | 2026-06-12 |
| 5. 주봉 임펄스 주간화 | v1.1 | 1/1 | Complete   | 2026-06-16 |
| 6. 시트1 기업명 열 | v1.2 | 1/1 | Complete   | 2026-06-16 |
| 7. 펀더멘털 SQLite 저장 + 접수번호 델타 | v1.3 | 4/4 | Complete   | 2026-06-18 |
| 8. 지표 registry 계산 | v1.3 | 4/4 | Complete   | 2026-06-22 |
| 9. 트렌드 엑셀 렌더 | v1.3 | 3/3 | Complete   | 2026-06-22 |
| 10. 시트1 펀더멘털 통합 이관 | v1.3 | 3/3 | Complete   | 2026-06-23 |
