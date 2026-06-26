# Phase 10: 시트1 펀더멘털 통합 store/registry 이관 - Context

**Gathered:** 2026-06-23
**Status:** Ready for planning

<domain>
## Phase Boundary

기존 `portfolio_YYYYMMDD.xlsx` **시트1**의 PER/PEG/GPM/OPM을 구 `fetch_fundamentals`(`_compute_*` 직접 계산 + 7일 `.cache/fundamentals`) 경로에서 떼어내, **Phase 7·8의 통합 store/registry**(`metrics_engine.compute_matrix`)가 계산한 값을 읽도록 이관한다.

목표 상태:
- 펀더멘털 fetch·계산이 단일 원천으로 일원화 → 시트1 값이 `fundamentals_history.xlsx` 최신 스냅샷과 **드리프트 없이 일치**
- 시트1도 접수번호 델타 덕에 평소 외부 펀더멘털 호출 ≈0
- **Core Value(시트1 조건부 색 신호) 회귀 무손상**

이 phase는 HOW(이관 방법)만 다룬다. 신규 지표 추가·트렌드 엑셀 변경·시트1 레이아웃 변경은 범위 밖.
</domain>

<decisions>
## Implementation Decisions

### 미적재/신규 종목 처리 (단계적 이관)
- **D-01:** run 흐름을 "PASS1 fetch+sync(DB 적재) → 시트1은 store에서 읽기"로 보장한다. `main_run`은 이미 `sync_ticker_history`(main_run.py:347)로 DB를 채우므로, **시트1 펀더멘털 읽기가 sync 이후가 되도록 읽기/쓰기 순서를 정렬**한다.
- **D-02:** sync 이후에도 DB에 분기 데이터가 없는 종목(첫 실행 후에도 EDGAR/DART fetch 실패·접수번호 probe 실패·완전 결손)은 **빈칸 + 한국어 사유**로 처리한다. **구 경로 폴백 없음** — 순수 단일 원천을 유지한다. 이 빈칸 동작은 구 경로의 "조회 실패" 표시와 동일해 회귀가 아니다.

### 구 경로 제거 범위
- **D-03:** 제거 대상은 **중복 fetch 경로만** — `fetch_fundamentals` / `_fill_us` / `_fill_kr` + 7일 `.cache/fundamentals` fetch 경로. `main_run`의 `_fundamentals_with_auth` 클로저와 `fetch_fundamentals` 호출을 store/registry 읽기로 대체한다.
- **D-04:** 다음 공유 계약은 **보존**한다 (registry·시트1·trend·color가 의존):
  - 순수 산식 헬퍼 `_compute_per` / `_compute_peg` / `_compute_margin` (metrics_engine.py:38,290이 `_compute_peg` import·재사용)
  - 데이터 모델 `MetricCell{value, source, note}` / `FundamentalsResult{per,peg,gpm,opm}` (sheet_portfolio.py:249가 소비)
  - 결손 게이트 `_is_missing` (WR-01 — fundamentals.py:72; trend_color/sheet_metric_matrix/sheet_raw/sheet_snapshot 공유)
- **D-05:** `.cache/fundamentals` 디렉터리/헬퍼가 `cache.py`의 OHLCV 7일 TTL 경로와 공유되는지 researcher가 확인 후 안전하게 제거한다 (OHLCV 캐시는 별개로 유지 — 깨면 안 됨).

### 현재가 주입 & 드리프트 0
- **D-06:** `history_render._inject_prices`(history_render.py:70)의 **최신분기 가격 주입 로직을 공유 헬퍼로 추출**해 시트1·트렌드 양쪽이 호출한다. 같은 `price_ratio` + `compute_peg_cell`(4분기 전 EPS) 경로를 쓰므로 드리프트가 구조적으로 차단된다.
- **D-07:** 시트1은 `compute_matrix(ticker)` 최신 분기 1열만 필요. 현재가는 시트1이 이미 보유한 OHLCV `last_close`를 주입한다 (트렌드의 "최신 분기=현재가" 규칙, Phase 9 D-09와 동일). 같은 last_close·같은 최신 분기를 써야 스냅샷과 값이 일치(SC1).
- **D-08:** compute_matrix 최신 열 → `FundamentalsResult{per,peg,gpm,opm}` 형태로 변환하는 **어댑터**를 둔다. 그래야 `sheet_portfolio.py`의 4셀 writer가 무변경으로 동작 (Core Value 보호).

### provenance 주석 표시 보존
- **D-09:** 시트1 셀 호버 주석은 **"소스 · 최신분기" 라벨을 재구성**한다 — 예: `EDGAR · 2026Q2`, 병합 소스는 D-08 규칙대로 `DART+yf · 2026Q2`. 어댑터가 최신 분기를 알고 있으므로 라벨 합성 가능. 구 경로와 동일한 사용자 경험 유지.
- **D-10:** 결손 셀은 구 경로와 동일하게 `MetricCell.note` 한국어 사유(`조회 실패: …`)를 보존하고, `sheet_portfolio.py:125`의 `cell.note or cell.source` 주석 로직은 변경하지 않는다.

### Claude's Discretion
- 어댑터/공유 헬퍼의 파일 위치·이름 (계약만 지키면 자유)
- D-05 캐시 제거 시점·테스트 격리 방식
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Roadmap & Requirements
- `.planning/ROADMAP.md` §"Phase 10" — Goal·Depends on(Phase 7·8·6)·Success Criteria 1~4
- `.planning/REQUIREMENTS.md` — FUND-11 (단일 원천·드리프트 없음·구 경로 제거·≈0 호출)

### Store / Registry 백엔드 계약 (단일 원천)
- `src/stocksig/io/metrics_engine.py` §`compute_matrix`(L299) — 9종 분기 매트릭스, PEG 3단 소비 계약(L309~325), `price_ratio`/`compute_peg_cell`/`_calendar_quarter_offset`
- `src/stocksig/io/fundamentals_store.py` — DB raw 적재·`fetch_raw_quarters`
- `src/stocksig/io/fundamentals_delta.py` — `sync_ticker_history` (접수번호 델타 적재)
- `.planning/phases/08-registry/08-CONTEXT.md` — registry 계약·D-08 provenance 병합 규칙
- `.planning/backlog/fundamentals-history-delta.md` — v1.3 권위 설계 입력

### 이관 대상 코드
- `src/stocksig/io/fundamentals.py` — 구 경로(`fetch_fundamentals` L296, `_fill_us` L123, `_fill_kr` L192) + 보존 계약(`MetricCell`/`FundamentalsResult`/`_is_missing`/`_compute_*`)
- `src/stocksig/main_run.py` §`run` — `_fundamentals_with_auth`(L272)·`fetch_fundamentals` 호출(L273)·`sync_ticker_history`(L347)·PASS1/PASS2 순서
- `src/stocksig/output/sheet_portfolio.py` — `_write_fund_cell`(L113~131)·시트1 4셀 소비(L248~264) — **무변경 목표**
- `src/stocksig/io/history_render.py` §`_inject_prices`(L70) — 공유 추출 원본
- `src/stocksig/io/cache.py` — `.cache/fundamentals` vs OHLCV 7일 TTL 경로 공유 여부 확인(D-05)
</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `metrics_engine.compute_matrix` / `price_ratio` / `compute_peg_cell`: 시트1이 읽을 단일 원천 계산 API (외부 호출 0)
- `history_render._inject_prices`: 최신분기 가격 주입 로직 — 공유 헬퍼로 추출해 시트1·트렌드 재사용 (D-06)
- `FundamentalsResult` / `MetricCell`: 시트1 writer 입력 계약 — 어댑터가 이 형태로 변환 (D-08)
- `sheet_snapshot.write_snapshot_sheet` 결과(최신 열, D-13): 시트1 값과 일치해야 하는 검증 기준점

### Established Patterns
- per-metric provenance 병합 "+"결합 (Phase 8 D-08)
- "최신값=현재가 / 과거=분기말 종가" (Phase 9 D-09)
- 결손 단일 게이트 `_is_missing`(WR-01), 0/-999999 금지(D-05), API 키 미누설(CR-01)
- 펀더멘털 결손 ≠ 티커 실패 (try/except 흡수, D-disc-10)

### Integration Points
- `main_run.run` PASS1(fetch+sync) ↔ PASS2(시트1 write) 순서 — sync 후 store 읽기 보장(D-01)
- 시트1 4셀 writer(`sheet_portfolio`) ← 어댑터 ← `compute_matrix` 최신 열 + `last_close` 주입
- 검증: 시트1 값 == `fundamentals_history.xlsx` 최신 스냅샷 (드리프트 0, SC1)
</code_context>

<specifics>
## Specific Ideas

- 시트1 writer(`sheet_portfolio.py`)는 **무변경**이 이상적 — 어댑터가 `FundamentalsResult`를 그대로 공급해 Core Value 회귀 위험을 최소화한다.
- 드리프트 0은 "같은 입력(가격·분기)·같은 로직(공유 헬퍼)"로 **구조적으로** 보장 — 사후 비교 테스트는 그 보강.
</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (검증 방법·실행 순서 재배치·메트릭 일치 범위는 plan-phase/research에서 구체화.)
</deferred>

---

*Phase: 10-1-store-registry*
*Context gathered: 2026-06-23*
