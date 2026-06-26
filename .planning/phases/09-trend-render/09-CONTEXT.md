# Phase 9: 트렌드 엑셀 렌더 - Context

**Gathered:** 2026-06-22
**Status:** Ready for planning

<domain>
## Phase Boundary

저장된 펀더멘털 히스토리(`data/fundamentals.db`)와 Phase 8 registry(`metrics_engine.compute_matrix`)를 입력으로, 사람이 분기 트렌드를 육안 확인하는 **별도 엑셀 파일을 렌더**한다(FUND-10). 산출물 = `fundamentals_history_YYYYMMDD.xlsx` — 지표별 분기 매트릭스 시트(행=종목·열=분기) + `[원천]` + `[최신 스냅샷]`. 가격 의존 지표(PER/PBR/PCR/PSR)의 과거 열은 분기말 종가, 최신 열만 현재가(D-07). **기존 시트1 `portfolio_*.xlsx`의 레이아웃·색 신호(Core Value)는 전혀 건드리지 않는다.**

**In scope:** 지표별 매트릭스 시트 렌더 · `[원천]`/`[최신 스냅샷]` 시트 · 이중 시각 인코딩(동종 산업군 상대 색 + 전년동기 화살표) · 분기말 종가 주입 + PEG 분기별 산출 · 결손/sanity-밖 셀 표기 · 독립 서브커맨드/플래그 진입점.

**Out of scope (다른 phase):** 시트1 PER/PEG/GPM/OPM의 통합 store/registry 이관 + 구 `_compute_*`·7일 캐시 제거 = Phase 10(FUND-11) / FCF·EV/EBITDA용 raw 원천 확장 = 추후 별도 phase / 펀더멘털 저장·델타 = Phase 7(완료) / 지표 계산 엔진 = Phase 8(완료). 시트1 색 신호는 **불변**.

</domain>

<decisions>
## Implementation Decisions

### 매트릭스 레이아웃 (지표별 시트)
- **D-01:** 분기 열 = **전체 저장 분기, 최신을 맨 왼쪽**(내림차순). 식별 선두 열 다음부터 분기 열이 왼←오 = 최신←과거 순.
- **D-02:** 각 지표 시트의 **선두 식별 열은 시트1 portfolio의 A~E열을 그대로 재사용** — 순서·헤더 동일: **티커 · 기업명 · 시장 · 티어 · 산업**. 그 뒤에 분기 열(D-01)이 붙는다.
- **D-03:** 종목 행 정렬 = **미국 → 한국 그룹화 후 각 그룹 내 알파벳(티커)순**.
- **D-04:** Freeze panes = **A열(티커)만 고정**(헤더행은 사용자 미요청 — 티커 열만 가로 스크롤 고정). 시장(C)·티어(D) 열은 **글자 보이는 폭만큼 최소 너비**로 설정.

### 트렌드 시각 인코딩 (이중·직교 신호 — 핵심 결정)
두 신호를 한 셀에 직교 적용한다. 색 = 동종 대비 우열(상대), 화살표 = 자기 전년 대비 추세(절대 모멘텀).
- **D-05:** **셀 배경색 = 동종 산업군 상대 비교**, 3단계 **초록 / 무색 / 빨강**. 의미 = **좋을수록 초록·나쁠수록 빨강**(finviz 스크리너 모델). 비교는 **분기 열 단위**로 같은 `산업(E열)` 그룹 내 종목들끼리 수행.
- **D-06:** **지표별 좋음/나쁨 방향 정의 필수**:
  - 낮을수록 좋음(낮을 때 초록): **PER · PEG · PBR · PCR · PSR** (밸류에이션 — 저평가=좋음)
  - 높을수록 좋음(높을 때 초록): **ROE · ROA · GPM · OPM** (수익성/마진)
- **D-07(상대비교 표본 게이트):** 동종 산업군 표본이 **N 미만(planner 권장 N=3)** 이면 상대색 = **무색**(오해 소지 제거). `산업`이 빈 문자열("")인 종목도 동일하게 무색(tickers.txt에서 산업 미입력 가능 — input.py).
- **D-08:** **화살표 = 전년동기(YoY) 증감 추이** — 각 셀을 **4분기 전(전년 동기) = 동일 지표의 4칸 오른쪽 열**과 비교해 ↑(증가)/↓(감소) 표시. **모수와 무관**하게(상대색이 무색이어도) 종목 자체 추세를 보여준다. 전년 동기 값이 결손이면 화살표 생략.
  - 화살표 구현 방식(아이콘셋 vs 유니코드 글리프 ▲▼ vs 별도 열)은 Claude 재량(researcher 조사 후 planner 결정). 색과 충돌하지 않게 적용.

### 가격 의존 지표 & PEG
- **D-09:** 가격 의존 4종(PER/PBR/PCR/PSR) 과거 열 = **그 분기 마지막 거래일 종가**(보유 10년치 OHLCV에서 조달), 최신 열만 **현재가**. `metrics_engine.price_ratio(denom_cell, price)`에 주입(D-07/Phase 8 계약).
- **D-10:** **PEG도 분기별 산출** — Phase 8 `compute_peg_cell(per_value, eps_ttm, eps_prior)` 2단계 API로 각 분기 PER(가격 주입 후) + EPS 성장률에서 산출. 과거 분기 PEG = 분기말 종가 기준 PER 사용.

### 결손 · 출처 표기
- **D-11:** 결손/sanity-밖 셀 = **`"-"` 표시 + 마우스오버 셀 코멘트(사유)**. 0 대체·부분합산 금지(Phase 8 D-05 일관).
- **D-12:** per-metric provenance(EDGAR/DART/yf/혼합 "+") = **`[원천]` 시트 중심**으로 표기 + 지표 셀 **코멘트 보조**. 매트릭스 가독성 유지.

### 시트 구성
- **D-13:** 지표별 시트(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA) + **`[원천]`**(분기별 raw long: ticker·source·quarter·field·value·provenance — 검증/디버깅 근거) + **`[최신 스냅샷]`**(종목 1행 × 전 지표 최신값, 시트1 "한눈에" 뷰와 동형).

### 파일 · 배선
- **D-14:** 파일명 = **`fundamentals_history_YYYYMMDD.xlsx`**(날짜 스탬프, 매 실행 새 파일). 프로젝트 "매 실행마다 새 파일 생성" 관례와 일치(백로그 D-H4의 고정명보다 우선 — 사용자 결정).
- **D-15:** 진입점 = **독립 서브커맨드/플래그**(예: `--history` 또는 별도 엔트리) — 시트1 산출 흐름(main_run)과 완전 분리. 소스 진실은 DB이므로, 평소엔 main 실행(Phase 7 sync가 DB 적재) 후 별도 호출로 렌더.

### Claude's Discretion (planner/executor 재량)
- 화살표 구현 기법(XlsxWriter iconset vs 글리프 vs 별도 열)·상대색 구현(conditional_format 컬러 vs Python 사전계산 후 정적 베이킹).
- 상대비교 표본 게이트 N의 최종값(권장 3) 및 동순위/동값 처리.
- `[원천]`/`[최신 스냅샷]` 시트의 구체 열 구성·정렬.
- 분기 열 헤더 라벨 형식(`2026Q1` 등 — Phase 8 캘린더 분기 키 그대로 권장).
- 서브커맨드/플래그의 정확한 CLI 형태 및 DB 미존재(아직 sync 안 함) 시 안내 메시지.
- 시장(C)·티어(D) 열 "최소 너비"의 구체 산정(autofit 근사).

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 권위 설계 입력 (LOCKED)
- `.planning/backlog/fundamentals-history-delta.md` §"D-H4 — 사람용 엑셀 출력" — 별도 파일·지표별 매트릭스 시트·`[원천]`/`[최신 스냅샷]`·가격 의존 과거=분기말 종가/최신=현재가. 본 phase 1차 권위 입력.
- `.planning/ROADMAP.md` §"Phase 9: 트렌드 엑셀 렌더" — Goal·Success Criteria 4종·의존(Phase 8 계산결과·Phase 7 DB).
- `.planning/REQUIREMENTS.md` §"FUND-10" — 본 phase 수용 요구사항.
- `.planning/STATE.md` §"Decisions (locked)" / "v1.3 기술 컨텍스트" — 렌더 산출물·불변(시트1) 제약.

### 직전 phase 컨텍스트 (입력 계약)
- `.planning/phases/08-registry/08-CONTEXT.md` — D-06(분기 매트릭스 전체)·D-07(가격 비결합 per-share 분모, 가격 호출자 주입)·D-08(per-metric provenance). 본 phase 렌더 입력의 의미.
- `.planning/phases/08-registry/08-04-SUMMARY.md` — `compute_peg_cell` 2단계 API·Phase 9 PEG 소비 계약(price_ratio→EPS_ttm 현·4분기전→compute_peg_cell).
- `.planning/phases/07-sqlite/07-CONTEXT.md` — 저장 raw 스키마·캘린더 분기 키 `YYYYQn`·결손=NULL.

### 의존 코드 (이 위에 렌더 층 추가)
- `src/stocksig/io/metrics_engine.py` — `compute_matrix(ticker, fetch_fn) -> {metric: {quarter: MetricCell}}`(분기 축)·`price_ratio(denom_cell, price)`(가격 주입)·`compute_peg_cell(per, eps_ttm, eps_prior)`(PEG). 렌더 매트릭스의 데이터 소스.
- `src/stocksig/io/metrics_registry.py` — REGISTRY 9종·MetricType·MetricDef. 지표 목록·유형(시트 구성·방향 결정 D-06 참조).
- `src/stocksig/io/fundamentals_store.py` — `fetch_raw_quarters(ticker)`(provenance 포함 raw long → `[원천]` 시트 입력)·DB 접근.
- `src/stocksig/output/writer.py` — `make_workbook(path) → (Workbook, formats_dict)` XlsxWriter 팩토리·Format 캐시·조건부서식 패턴. 히스토리 워크북 생성의 재사용 기반(단, 시트1 포맷과 분리).
- `src/stocksig/output/sheet_portfolio.py` — A~E열 헤더 구성(`_COL` 티커/기업명/시장/티어/산업)·종목 행 writer·freeze·열 너비 패턴. 식별 열(D-02) 재사용 참조 — **읽기만, 수정 금지(Core Value 불변)**.
- `src/stocksig/io/input.py` — `TickerSpec(symbol, tier, industry)`(tickers.txt 파싱). 산업(상대비교 D-05)·티어 데이터 출처. 산업 미입력 시 "".
- `src/stocksig/io/company.py` — yfinance 영문 기업명(Phase 6). 식별 열 기업명 출처.
- `src/stocksig/io/market_kind.py` — 시장(미국/한국) 분류. 식별 열 시장·종목 그룹 정렬(D-03) 출처.
- `src/stocksig/main_run.py` — main 실행 흐름. 독립 서브커맨드 배선(D-15) 시 진입점/엔트리 참조.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `output/writer.py::make_workbook` + Format 캐시: 히스토리 워크북·셀 서식 생성에 동일 패턴 재사용(조건부서식 `conditional_format` 기반 상대색·아이콘셋 후보).
- `sheet_portfolio.py`의 A~E열 헤더 인덱스(`_COL`)·행 writer·freeze·열 너비 로직: 식별 열(D-02)·정렬(D-03)·freeze(D-04)의 직접 모델.
- `metrics_engine.compute_matrix`/`price_ratio`/`compute_peg_cell`: 렌더 입력 전부 — 외부 재호출 0(Phase 8 보증).
- `fetch_raw_quarters`(provenance 포함): `[원천]` 시트 직공급.

### Established Patterns
- 캘린더 분기 키 `YYYYQn`(Phase 7/8): 분기 열 헤더·매트릭스 정렬·YoY(4분기 전) 기준 정렬에 그대로 사용.
- 결손 = None / 빈값+사유(Phase 8 D-05): 렌더에서 `"-"`+코멘트로 표현(D-11).
- XlsxWriter 정적 색 베이킹(인플레이스 미사용, CLAUDE.md): 상대색·화살표도 생성 시점 베이킹.

### Integration Points
- 입력: `data/fundamentals.db`(Phase 7 sync 적재) → `compute_matrix`/`fetch_raw_quarters` → 렌더.
- 가격 주입: 보유 10년치 OHLCV에서 분기말 마지막 거래일 종가(과거)·현재가(최신) → `price_ratio`/PEG.
- 식별/그룹: TickerSpec(산업·티어) + company(기업명) + market_kind(시장) → 식별 열·정렬·상대비교 그룹.
- 출력: 시트1 `portfolio_*.xlsx`와 **완전 별도 파일** — 상호 비결합(Core Value 보호).

</code_context>

<specifics>
## Specific Ideas

- 시각 모델 레퍼런스: **finviz 스크리너**(동종 산업군 상대 — 좋을수록 초록) + **tradingview**(전년동기 증감 화살표). 두 모델을 한 셀에 직교 결합(색=상대 우열, 화살표=자기 추세).
- 밸류에이션 지표(PER/PEG/PBR/PCR/PSR)는 "낮을수록 초록", 수익성 지표(ROE/ROA/GPM/OPM)는 "높을수록 초록" — 단순 값 방향이 아니라 **지표별 좋음/나쁨**으로 칠한다.
- 개인 포트폴리오라 산업군 표본이 1~2종목인 경우가 흔함 → 표본 부족 시 상대색은 무색, 화살표(YoY)는 그대로 유지해 정보 손실 최소화.
- 식별 열을 시트1과 동형(티커·기업명·시장·티어·산업)으로 두어 두 파일을 나란히 보기 쉽게.

</specifics>

<deferred>
## Deferred Ideas

- 헤더행 freeze(현재 A열만) — 필요 시 추후 행 고정 추가 가능(사용자 미요청).
- 스파크라인/미니차트 — 이번엔 색+화살표로 충분, 추후 시각 보조 확장 후보.
- FCF·EV/EBITDA 지표 시트 — raw 원천 확장(CapEx·현금잔액·D&A) 선행 필요(Phase 8 deferred 일관). 원천 확장 후 동일 registry·렌더에 합류.
- 상대비교 기준을 산업군 외 시가총액·티어 등 다른 동종 기준으로 확장 — 이번엔 산업(E열) 기준으로 고정.
- 기초·기말 평균 분모(ROE/ROA 정밀) — Phase 8 D-03대로 최근값 유지.

</deferred>

---

*Phase: 9-trend-render*
*Context gathered: 2026-06-22*
