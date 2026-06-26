# Phase 8: 지표 registry 계산 - Context

**Gathered:** 2026-06-19
**Status:** Ready for planning

<domain>
## Phase Boundary

저장된 분기별 원천 raw(`data/fundamentals.db`)**만으로** 모든 펀더멘털 지표를 외부 재호출 없이 계산하는 **계산 층**(FUND-09). 지표를 유형별(저량=최근 분기값 / 유량=TTM 4분기 합 / 하이브리드=유량분자÷저량분모) **registry**로 정의해, 신규 지표를 추가해도 원천 재수집 없이 즉시 산출한다. 이 registry는 Phase 9(트렌드 엑셀)·Phase 10(시트1 이관) 양쪽이 읽는 **단일 원천**이다 — 두 출력의 값이 드리프트 없이 일치해야 한다.

**In scope:** 9종 지표 산출(재현 4 + 신규 5) · 유형별 registry 정의 · 분기 매트릭스 전체 산출 · EDGAR Q4=FY−9M 보정 / DART YTD 분해 · per-metric provenance 라벨 · TTM 결손 빈값+사유.

**Out of scope (다른 phase):** 트렌드 엑셀 렌더 = Phase 9(FUND-10) / 시트1 이관 + 구 `_compute_*`·7일 캐시 제거·폴백 fetch 오케스트레이션 = Phase 10(FUND-11) / FCF·EV/EBITDA용 raw 원천 확장(CapEx·현금잔액·D&A) = 추후 별도 phase. 시트1 `portfolio_*.xlsx` 색 신호(Core Value)는 **불변**.

</domain>

<decisions>
## Implementation Decisions

### 신규 지표 범위
- **D-01:** Phase 8 산출 지표 = **9종**. 재현 4종(PER/PEG/GPM/OPM) + 신규 5종(PBR·PCR·PSR·ROE·ROA). 전부 저장 raw 슈퍼셋으로 외부 재호출 없이 계산 가능.
  - PBR = 주가 ÷ BPS(total_equity ÷ shares_outstanding) — 저량·가격
  - PCR = 주가 ÷ OCF-per-share(operating_cash_flow TTM ÷ shares) — 유량·가격
  - PSR = 주가 ÷ SPS(revenue TTM ÷ shares) — 유량·가격
  - ROE = net_income TTM ÷ total_equity — 하이브리드
  - ROA = net_income TTM ÷ total_assets — 하이브리드
- **D-02:** **FCF·EV/EBITDA는 연기.** 저장 raw에 없는 필드(FCF=CapEx / EV/EBITDA=현금잔액·D&A·이자성부채)가 필요 → Phase 7 원천 추출 재확장 필요(별도 phase 성격). registry는 신규 지표 추가가 쉽도록 설계하되, 이 2종은 원천 확장 후 추가. (Deferred 참조)

### 하이브리드 분모 규칙
- **D-03:** 하이브리드 지표(ROE·ROA)의 분모(자본·자산) = **최근 분기 시점값**(기초·기말 평균 아님). 단순·명확·결손 분기 영향 최소. raw 한 분기만 있어도 산출 가능.

### 재현 정합성 정책
- **D-04:** registry(저장 raw 4분기 합산)가 **새 단일 원천(canonical)**. 현 시트1 표시값과의 미세 차이는 "더 일관된 값"으로 수용 — Phase 10 이관 시 표시값이 약간 변할 수 있으며 이를 문서화한다.
- **D-05:** 검증은 **합리적 범위(sanity bounds)** 로 수행 — 레거시(`fundamentals.py`의 edgartools `get_ttm` accessor) 값과의 **정확 일치는 강제하지 않는다**. (현 경로 = 라이브러리 TTM, registry = 4분기 직접 합산 → 미세 차이 가능)

### 계산 산출 범위
- **D-06:** **분기 매트릭스 전체** 산출 — 매 분기별로 전 지표 시계열을 계산. 최신값 = 매트릭스의 마지막 열. Phase 9는 매트릭스 그대로, Phase 10은 최신열만 읽는다. 설계노트 "단일 원천"에 부합.
- **D-07:** 가격 의존 지표(PER·PBR·PCR·PSR)는 registry가 **가격 비의존 per-share 분모(EPS_ttm·BPS·SPS·OCF-ps)를 분기별로 산출**하고, 비율 = price ÷ 분모로 **가격은 호출자가 주입**한다. 최신=현재가 / 과거=분기말 종가(SC5 "최신값=현재가" 보존, Phase 9 "분기말 종가" 수용). 분기말 종가는 이미 보유한 10년치 OHLCV에서 조달. 계산 층은 가격 파이프라인과 비결합 → 순수·테스트 용이.

### 출처(provenance) & 폴백 의미
- **D-08:** registry = **순수 계산 + per-metric provenance 라벨**. 각 metric의 provenance = 계산에 사용한 raw 필드들의 `source` 라벨(EDGAR/DART/yf/Naver). metric별 독립 계산이므로 per-metric provenance가 보존된다(SC5).
- **D-09:** **폴백 체인(PER: DART→Naver→yf 등) fetch는 registry 책임이 아니다** — 오케스트레이션(Phase 10) 책임. registry는 어떤 source의 저장 raw든 균일하게 수용해 계산하고, 1차 raw 결손 시 해당 metric은 **빈값 + 사유**(0 대체 금지, D-05 결손 정책 일관). SC5 "폴백 의미 보존/수용" = fetch 구현이 아니라 폴백-소스 값을 수용 가능해야 한다는 계약으로 해석.

### TTM 결손 처리 (SC4 — 잠긴 정책, 재논의 안 함)
- TTM 4분기 중 결손 분기가 있으면 해당 TTM 지표는 **빈값 + 사유**로 처리(0 대체 금지). 부분 합산 금지(SC4·D-05 일관).

### Claude's Discretion (planner/executor 재량)
- registry 자료구조·모듈 위치(예: `metrics_registry.py` + 계산 엔진 분리), 지표 정의 표현(dataclass vs dict).
- EDGAR Q4=FY−9M 보정·DART YTD 분해(thisQ누적−직전Q누적)의 구체 구현 — 백로그 메모(D-H2) 기반, raw는 as-reported 보존(Phase 7 D-05)이므로 분해는 계산 시점 수행.
- 분기 분해 시 직전 분기 결손/정렬 엣지케이스 처리.
- provenance 라벨이 metric별 복수 source raw(예: ROE = net_income + total_equity가 다른 source일 때) 혼합 시 라벨링 규칙.
- sanity bounds 검증의 구체 임계(어떤 지표를 어떤 합리 범위로 체크할지) — researcher 조사 후 planner 결정.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 권위 설계 입력 (LOCKED)
- `.planning/backlog/fundamentals-history-delta.md` §"D-H2 — 원천 저장 + 지표 registry" — 유형(저량/유량 TTM/하이브리드) 정의 + registry 스키마 `{이름, 유형, 산식, 필요 원천필드, 소스별 매핑}` + 구현 메모(EDGAR Q4 보정·DART YTD 분해·TTM 결손 정책). 본 phase 1차 권위 입력.
- `.planning/ROADMAP.md` §"Phase 8: 지표 registry 계산" — Goal·Success Criteria 5종·Design note(단일 원천)·의존(Phase 7).
- `.planning/REQUIREMENTS.md` §"FUND-09" — 본 phase 수용 요구사항.
- `.planning/STATE.md` §"Decisions (locked)" / "v1.3 기술 컨텍스트" — 지표 유형·델타 키·불변 제약.

### 직전 phase 컨텍스트 (계산 입력의 출처)
- `.planning/phases/07-sqlite/07-CONTEXT.md` — 저장 raw 슈퍼셋·캘린더 분기 정규화(D-08)·as-reported 보존(D-05)·유니크 키 `(ticker,source,quarter,field)`(D-09). Phase 8 계산이 읽는 raw의 형식·의미 정의.

### 의존 코드 (이 위에 계산 층 추가)
- `src/stocksig/io/fundamentals_store.py` — raw_facts 스키마(field 목록·NULL 결손·period/reprt_code 메타·accession)·`upsert_quarters`·`count_rows`. registry 계산의 입력 store. (필드: revenue/gross_profit/op_income/net_income/eps/operating_cash_flow/total_equity/total_liabilities/total_assets/shares_outstanding)
- `src/stocksig/io/fundamentals.py` — 현 PER/PEG/GPM/OPM 산식(`_compute_per`/`_compute_peg`/`_compute_margin`)·`MetricCell`(value/source/note)·`_is_missing` NaN 게이트(WR-01)·per-metric 폴백 라우팅. **재현 대상 산식의 참조 기준**(단, TTM 출처는 D-04대로 registry가 canonical). Phase 8은 건드리지 않음 — 통합은 Phase 10.
- `src/stocksig/io/dart_account_map.py` — `DART_ACCOUNT_ID_MAP`/`DART_ACCOUNT_MAP` — 소스별 원천필드 매핑의 시작점(SC1).
- `src/stocksig/io/edgar_client.py` — per-quarter raw 추출의 concept↔field 매핑(`_EDGAR_DURATION_CONCEPTS`/`_INSTANT_CONCEPTS`) — registry 필요 원천필드의 EDGAR 소스 매핑 참조.

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `fundamentals.py`의 `MetricCell(value, source, note)` + `_is_missing`(None/NaN 단일 게이트, WR-01): registry 출력 셀·결손 게이트에 동일 패턴 재사용 가능 — provenance(source)·사유(note) 라벨링 구조가 이미 존재.
- `_compute_per`/`_compute_peg`/`_compute_margin` 산식(엣지케이스·한국어 사유 포함): PER/PEG/GPM/OPM 재현의 산식 시작점.
- `fundamentals_store.py`의 `count_rows`/조회 경로 + WAL/busy_timeout: registry 계산 입력 읽기에 그대로 사용.

### Established Patterns
- 결손 = `None`(0/-999999 금지, D-05) — registry 산출에도 동일 유지. TTM 부분 결손 = 전체 빈값+사유(SC4).
- 캘린더 분기 키 `YYYYQn`(D-08): 종목 간 매트릭스 정렬·교차 비교의 정렬 기준.
- raw = as-reported(D-05): 분기 분해(EDGAR Q4·DART YTD)는 **계산 시점에** 수행 — 원천 안전.

### Integration Points
- registry/계산 층 → Phase 9 트렌드 엑셀(매트릭스 입력)·Phase 10 시트1(최신열 입력)이 공통으로 읽는 단일 백엔드.
- 가격 의존 지표는 per-share 분모만 노출 → 가격 주입은 호출자(Phase 9=분기말 종가 / Phase 10·시트1=현재가). OHLCV(10년치)는 이미 파이프라인에 존재.
- 폴백 fetch(yf/Naver)는 registry 밖(Phase 10 오케스트레이션) — registry는 저장된 source raw만 균일 소비.

</code_context>

<specifics>
## Specific Ideas

- 사용자는 지표를 폭넓게 보길 원함(PBR·PCR·PSR·ROE·ROA·FCF·EV/EBITDA 언급) — registry는 "신규 지표 추가가 쉬운" 확장형이어야 한다(원천만 있으면 즉시 추가). FCF·EV/EBITDA는 원천 확장 후 동일 registry에 합류.
- "최신값 = 현재가, 과거 = 분기말 종가"는 가격 의존 지표의 핵심 일관성 규칙(Phase 9 트렌드와 시트1이 같은 분모를 공유).
- registry가 새 단일 원천이 되므로, Phase 10 이관 후 시트1 PER 등이 현재값과 미세하게 달라질 수 있음을 사용자가 수용함(드리프트 0보다 일관성·정확성 우선).

</specifics>

<deferred>
## Deferred Ideas

- **FCF** 지표 — `operating_cash_flow`는 저장되나 **CapEx 미저장** → Phase 7 raw 추출에 CapEx 필드 추가(EDGAR/DART) 선행 필요. 원천 확장 후 registry에 즉시 합류 가능.
- **EV/EBITDA** 지표 — **현금잔액·D&A(감가상각)·이자성부채 미저장** → raw 원천 확장 필요. FCF와 함께 "raw 원천 확장 phase"로 묶어 처리 권장.
- 폴백 체인(DART→Naver→yf) **fetch 오케스트레이션** 및 폴백-소스 값의 DB 적재 정책 → Phase 10(FUND-11) 시트1 이관 범위.
- 기초·기말 평균 분모(ROE/ROA 정밀 회계 관행) — 이번엔 최근값으로 결정(D-03). 필요 시 추후 registry 옵션으로 도입 가능(원천 보존되어 비파괴적).

</deferred>

---

*Phase: 8-registry*
*Context gathered: 2026-06-19*
