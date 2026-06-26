# Phase 10: 시트1 펀더멘털 통합 store/registry 이관 - Research

**Researched:** 2026-06-23
**Domain:** 내부 리팩터/이관 (data single-source migration) — 외부 라이브러리 신규 도입 없음
**Confidence:** HIGH (모든 핵심 주장이 현 코드 직접 grep/read로 검증됨)

## Summary

이 phase는 **신규 기술 도입이 0**인 순수 내부 이관이다. 시트1(`portfolio_YYYYMMDD.xlsx`)의 PER/PEG/GPM/OPM이 현재는 `fundamentals.fetch_fundamentals`(EDGAR/DART 직접 fetch + `_compute_*` 직접 산식 + 7일 `.cache/fundamentals` 캐시)에서 산출된다. Phase 7·8이 이미 동일 4지표를 `data/fundamentals.db` raw에서 `metrics_engine.compute_matrix`로 외부 호출 0에 계산하므로(Phase 9 트렌드 엑셀이 이를 소비 중), 시트1도 같은 단일 원천을 읽도록 갈아끼우는 작업이다.

핵심 통찰 두 가지를 코드로 확인했다. (1) **캐시 분리(D-05)는 안전하다** — `.cache/fundamentals`는 `cache.py`의 `get_fund/put_fund/_get_fund_cache/_FUND_DIR`만 접근하고, 이들은 `fetch_edgar_cached`/`fetch_dart_cached` → `fundamentals.py`의 `_default_edgar`(L347)/`_default_dart`(L371) 두 클로저에서만 호출된다. OHLCV는 `_get_cache`/`_DEFAULT_DIR=.cache/ohlcv`/`get_ohlcv`/`put_ohlcv`로 **완전히 별개 경로**다. 따라서 펀더멘털 fetch 경로 제거가 OHLCV 캐시를 깨뜨릴 구조적 경로가 없다. (2) **드리프트 0은 이미 구조적으로 보장되는 패턴이 존재한다** — `history_render._inject_prices`(L70)가 `compute_matrix` 최신열 + 가격 주입 + 분기별 PEG 3단을 정확히 수행하며, 이를 공유 헬퍼로 추출하면 시트1·트렌드가 같은 코드·같은 입력(last_close·최신분기)을 쓰게 되어 두 파일 값이 구조적으로 일치한다.

**Primary recommendation:** `metrics_engine.compute_matrix` 최신열을 시트1의 `FundamentalsResult{per,peg,gpm,opm}`로 변환하는 **얇은 어댑터**(신규 산식 0, `compute_peg_cell`/`price_ratio` 재사용)를 신설하고, `main_run.run`의 PASS1 `_fundamentals_with_auth` 클로저·`fetch_fundamentals` 호출을 "sync 이후 store 읽기"로 대체한다. 시트1 writer(`sheet_portfolio.py`)는 **0줄 수정** 목표(Core Value 보호). 드리프트는 `_inject_prices` 추출 공유 헬퍼로 구조적 차단 + 사후 동치 테스트로 보강.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| 분기 raw 저장·델타 적재 | Database (`fundamentals_store`/`fundamentals_delta`) | — | Phase 7 완료. 단일 영속 원천 |
| 9종 지표 분기 매트릭스 계산 | Compute engine (`metrics_engine`) | — | Phase 8 완료. 외부 호출 0 순수 함수 |
| 가격 주입(최신=현재가) + 분기별 PEG | Compute orchestration (공유 헬퍼, `_inject_prices` 추출) | — | D-06. 시트1·트렌드 공통 |
| compute_matrix 최신열 → FundamentalsResult 변환 | Adapter (신규, Claude 재량 위치) | — | D-08. 시트1 writer 계약 보존 |
| run 흐름 PASS1 sync → PASS2 시트1 store 읽기 정렬 | Orchestration (`main_run.run`) | — | D-01. 읽기/쓰기 순서 |
| 4셀 색 신호·주석 렌더 | Output (`sheet_portfolio`) | — | **무변경 목표** (Core Value) |

## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** run 흐름 = "PASS1 fetch+sync(DB 적재) → 시트1은 store에서 읽기". 시트1 펀더멘털 읽기가 `sync_ticker_history`(main_run.py:347) **이후**가 되도록 읽기/쓰기 순서 정렬.
- **D-02:** sync 후에도 DB에 분기 데이터 없는 종목 = **빈칸 + 한국어 사유**. **구 경로 폴백 없음** (순수 단일 원천). 빈칸 동작은 구 경로 "조회 실패"와 동일 → 회귀 아님.
- **D-03:** 제거 대상 = **중복 fetch 경로만** — `fetch_fundamentals` / `_fill_us` / `_fill_kr` + 7일 `.cache/fundamentals` fetch 경로. `_fundamentals_with_auth` 클로저·`fetch_fundamentals` 호출을 store/registry 읽기로 대체.
- **D-04:** 보존 계약 — 순수 산식 헬퍼 `_compute_per`/`_compute_peg`/`_compute_margin`(metrics_engine import 재사용), 데이터 모델 `MetricCell`/`FundamentalsResult`(sheet_portfolio 소비), 결손 게이트 `_is_missing`(WR-01 공유).
- **D-05:** `.cache/fundamentals`가 OHLCV 7일 TTL과 공유되는지 researcher 확인 후 안전 제거 (OHLCV 캐시 별개 유지 — 깨면 안 됨). **→ 본 리서치 Q1에서 확인 완료: 공유 안 됨, 제거 안전.**
- **D-06:** `history_render._inject_prices`(L70) 최신분기 가격 주입 로직을 **공유 헬퍼로 추출** → 시트1·트렌드 양쪽 호출. 같은 `price_ratio`+`compute_peg_cell`(4분기 전 EPS) 경로 → 드리프트 구조적 차단.
- **D-07:** 시트1 = `compute_matrix(ticker)` 최신 분기 1열만 필요. 현재가 = 시트1 보유 OHLCV `last_close` 주입. 같은 last_close·같은 최신 분기 → 스냅샷과 값 일치(SC1).
- **D-08:** compute_matrix 최신열 → `FundamentalsResult{per,peg,gpm,opm}` 변환 **어댑터**. sheet_portfolio.py 4셀 writer 무변경 동작 (Core Value 보호).
- **D-09:** 시트1 셀 호버 주석 = **"소스 · 최신분기" 라벨 재구성** (예: `EDGAR · 2026Q2`, 병합 `DART+yf · 2026Q2`). 어댑터가 최신 분기 인지 → 라벨 합성.
- **D-10:** 결손 셀 = 구 경로와 동일하게 `MetricCell.note` 한국어 사유 보존. `sheet_portfolio.py:125`의 `cell.note or cell.source` 주석 로직 **무변경**.

### Claude's Discretion
- 어댑터/공유 헬퍼의 파일 위치·이름 (계약만 지키면 자유).
- D-05 캐시 제거 시점·테스트 격리 방식.

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope. (검증 방법·실행 순서 재배치·메트릭 일치 범위는 plan/research에서 구체화.)
- (REQUIREMENTS.md Out of Scope 재확인) 시트1 레이아웃·색 신호 변경 / 폴백 소스 접수번호 델타 / 신규 외부 소스 / 가격 의존 지표 과거열 현재가 재산정.

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| FUND-11 | 시트1 PER/PEG/GPM/OPM이 통합 store/registry 계산값을 읽어 표시 — 중복 fetch·계산(구 `_compute_*`+7일 캐시) 제거, 두 파일 드리프트 없음, provenance·결손 NaN·조건부 색 신호 회귀 없음, 평소 외부 호출 ≈0 | Q1(캐시 분리 안전), Q2(공유 헬퍼 추출 경계), Q3(어댑터 필드 매핑), Q4(run 변경 지점·순서), Q5(provenance 라벨), Q6(드리프트 0·Core Value 회귀 검증 스위트). 전 항목 코드 근거 확보 |

---

## 6개 핵심 리서치 질문 — 코드 근거 기반 답변

### Q1 (BLOCKING / D-05): `.cache/fundamentals`와 OHLCV 캐시 공유 여부 — **공유 안 됨, 제거 안전** [VERIFIED: 코드 grep]

`cache.py`를 정독한 결과 세 캐시는 **완전히 분리된 인스턴스·디렉터리·헬퍼**다:

| 캐시 | 디렉터리 상수 | 인스턴스 | 키 헬퍼 | 접근 헬퍼 | TTL |
|------|--------------|----------|---------|-----------|-----|
| OHLCV | `_DEFAULT_DIR = .cache/ohlcv` (L23) | `_cache` / `_get_cache()` (L65) | `make_key` (L75) | `get_ohlcv`/`put_ohlcv` (L81,100) | 24h (L24) |
| 펀더멘털 | `_FUND_DIR = .cache/fundamentals` (L108) | `_fund_cache` / `_get_fund_cache()` (L114) | `make_fund_key` (L124) | `get_fund`/`put_fund` (L129,147) | 7일 (L109) |
| 기업명 | `_NAME_DIR = .cache/company` (L156) | `_name_cache` / `_get_name_cache()` (L162) | `make_name_key` (L172) | `get_company_name`/`put_company_name` (L177,195) | 30일 (L157) |

세 경로가 공유하는 유일한 것은 (a) 초기화 lock `_cache_lock`(L49, 모든 싱글톤 lazy-init용 — 인스턴스 자체는 별개)와 (b) `_stats` 카운터 dict(`fund_hit`/`fund_miss` 키만 펀더멘털용). **데이터 디렉터리·Cache 객체·키 네임스페이스는 0% 공유.**

**`.cache/fundamentals`에 닿는 호출 사슬 (전체 — grep 확정):**
```
get_fund/put_fund (cache.py:129,147)
  ← fetch_edgar_cached (edgar_client.py:256,258,262)
  ← fetch_dart_cached  (dart_client.py:299,305,310)
      ← _default_edgar 클로저 (fundamentals.py:347)  ── fetch_fundamentals 내부에서만
      ← _default_dart  클로저 (fundamentals.py:371)  ── fetch_fundamentals 내부에서만
```
즉 `fetch_fundamentals`를 시트1 경로에서 떼어내면 `fetch_edgar_cached`/`fetch_dart_cached`의 호출자가 사라지고, `.cache/fundamentals`는 자연스럽게 죽은 코드가 된다.

**정확히 건드릴 대상 (D-05 안전 제거 범위):**
1. **시트1 경로에서 끊기:** `main_run.run`의 `_fundamentals_with_auth`(L272) + `fetch_fundamentals` 호출(L273)을 어댑터 읽기로 대체. (이것만으로 `.cache/fundamentals` 쓰기가 0이 됨)
2. **죽은 코드 제거 (D-03):** `fundamentals.py` `fetch_fundamentals`(L296)·`_fill_us`(L123)·`_fill_kr`(L192)·`_default_edgar`/`_default_dart` 클로저. `edgar_client.fetch_edgar_cached`·`dart_client.fetch_dart_cached`.
3. **cache.py에서 펀더멘털 캐시 헬퍼:** `_FUND_DIR`/`_FUND_TTL_SECONDS`/`_fund_cache`/`_get_fund_cache`/`make_fund_key`/`get_fund`/`put_fund` (L106~150). **단, `_stats`의 `fund_hit`/`fund_miss` 키와 요약 줄(main_run.py:370 "펀더멘털 HIT %d/MISS %d")은 별도 판단** — 제거 시 요약 포맷 문자열도 함께 정리해야 회귀 없음.

⚠️ **건드리면 안 되는 것:** `_get_cache`/`_DEFAULT_DIR`/`get_ohlcv`/`put_ohlcv`/`make_key`/`_cache_lock`(공유 lock — 다른 두 캐시도 사용). `_isolated_disk_cache` conftest fixture(`.cache` 격리)는 OHLCV 경로도 monkeypatch하므로 유지.

**LANDMINE:** `edgar_client`/`dart_client`의 `fetch_edgar_cached`/`fetch_dart_cached` 외에 **per-quarter raw 추출기**(`fetch_edgar_quarterly_raw`/`fetch_dart_quarterly_raw`, Phase 7)는 store 경로로 별개다 — 절대 제거 금지. 같은 모듈 안에 있으므로 함수명 정확히 구분할 것.

### Q2 (D-06): `_inject_prices` 추출 경계 [VERIFIED: history_render.py:70-94 read]

**현재 시그니처:**
```python
def _inject_prices(matrix: dict, quarters: list[str], qmap: dict,
                   current: float | None, latest_q: str | None) -> None  # in-place
```
**현재 의존성 (모두 import 가능, 상태 없음):**
- `_PRICE_DEPENDENT`(L38) — REGISTRY에서 도출한 `{metric: price_denominator}` (PER→EPS_ttm, PBR→BPS, PCR→OCF_ps, PSR→SPS).
- `price_ratio`(metrics_engine) — 분모셀+가격 → 비율셀.
- `compute_peg_cell`(metrics_engine) — PER.value, eps_now, eps_prior(4분기 전).
- `_calendar_quarter_offset`(metrics_engine) — q-4 산출.
- `matrix["EPS_ttm"]` — eps_map.

**동작:** quarters 각 q에 대해 가격 결정(`q==latest_q`면 current, 아니면 `qmap.get(q)`) → (a) 가격 의존 4종 `price_ratio` in-place 주입 → (b) PEG 3단 계약 산출.

**추출 경계 권고 — 트렌드 호출이 깨지지 않는 형태:**

시트1은 **최신 분기 1열만** 필요(D-07)하고 가격은 항상 `last_close`(현재가). 트렌드는 전 분기 루프. 가장 안전한 추출은 **단일 분기 단위 함수**로 코어를 빼고, 트렌드의 다분기 루프는 그 코어를 호출하도록 리팩터:

```python
# 신규 공유 헬퍼 (예: metrics_engine 또는 신규 fundamentals_view 모듈)
def inject_prices_for_quarter(matrix: dict, q: str, price: float | None,
                              eps_map: dict) -> None:
    """단일 분기 q에 가격 의존 4종 + PEG in-place 주입 (시트1·트렌드 공유 코어)."""
    for metric, denom in _PRICE_DEPENDENT.items():
        denom_cell = matrix.get(denom, {}).get(q)
        matrix.setdefault(metric, {})[q] = price_ratio(denom_cell, price)
    per = matrix.get("PER", {}).get(q)
    per_value = per.value if per is not None else None
    eps_now = eps_map.get(q)
    eps_now_v = eps_now.value if eps_now is not None else None
    eps_prior = eps_map.get(_calendar_quarter_offset(q, -4))
    eps_prior_v = eps_prior.value if eps_prior is not None else None
    matrix.setdefault("PEG", {})[q] = compute_peg_cell(per_value, eps_now_v, eps_prior_v)
```

- **트렌드 측 변경(비파괴):** `history_render._inject_prices`는 시그니처·외부 동작을 유지하되 본문 루프가 `inject_prices_for_quarter`를 호출하도록만 바꾼다. 입력/출력 계약(`matrix` in-place, quarters/qmap/current/latest_q)이 그대로라 `run_history`·기존 14개 통합 테스트가 깨지지 않는다.
- **시트1 측 사용:** `compute_matrix(ticker)` → `quarters` 최신값 = `latest_q` → `inject_prices_for_quarter(matrix, latest_q, last_close, matrix["EPS_ttm"])` 1회 호출 → 어댑터가 최신열 추출.

**핵심 드리프트 차단 입력 동일성(D-07):** 시트1과 트렌드가 최신 분기에 대해 **같은 price(현재가)**를 주입해야 한다. 트렌드의 `current`는 `quarter_price.quarter_end_prices`의 `Close.dropna().iloc[-1]`(quarter_price.py)이고, 시트1의 `last_close`는 runner의 `df.iloc[-1].get("Close")`(runner.py:100)다. **둘 다 동일 OHLCV 캐시(`fetch_ohlcv_cached`)의 마지막 종가** — 같은 날 같은 캐시면 동일하지만, 미세 차이 가능성(예: NaN 트리밍 차이)은 Q6 동치 테스트가 잡아야 한다. **이 점이 SC1 드리프트 0의 유일한 잠재 누수 지점이다.**

### Q3 (D-08): compute_matrix 최신열 → FundamentalsResult 어댑터 필드 매핑 [VERIFIED: metrics_engine.py:299, fundamentals.py:46]

**compute_matrix 반환 구조** (L302,305): `{metric_name: {quarter: MetricCell}}`. 분기 축 = raw 등장 분기 오름차순, **최신값 = 마지막 분기 열**(L305,330). MetricCell = `{value, source, note}`.

**가격 주입 후(Q2 헬퍼 적용 후)** 매트릭스는 PER/PBR/PCR/PSR/PEG가 채워진 상태. 시트1은 그중 **PER/PEG/GPM/OPM 4종만** 소비.

**어댑터 정확 필드 매핑:**
```python
def matrix_to_fundamentals(matrix: dict, latest_q: str | None) -> FundamentalsResult:
    def cell_or_empty(metric: str) -> MetricCell:
        c = matrix.get(metric, {}).get(latest_q) if latest_q else None
        return c if c is not None else _empty_cell("조회 실패: DB 분기 데이터 없음")  # D-02
    return FundamentalsResult(
        per=cell_or_empty("PER"),   # price_ratio(EPS_ttm, last_close) 결과
        peg=cell_or_empty("PEG"),   # compute_peg_cell 결과 (3단 소비 반영)
        gpm=cell_or_empty("GPM"),   # compute_cell FLOW_TTM (이미 완성, 가격 무관)
        opm=cell_or_empty("OPM"),   # compute_cell FLOW_TTM (이미 완성, 가격 무관)
    )
```

| 시트1 셀 | matrix 키 | 산출 경로 | 가격 의존? | 비고 |
|----------|-----------|-----------|-----------|------|
| `per` | `matrix["PER"][latest_q]` | `price_ratio(matrix["EPS_ttm"][q], last_close)` | 예 (Q2 헬퍼가 주입) | source = EPS_ttm 셀 source 보존 |
| `peg` | `matrix["PEG"][latest_q]` | `compute_peg_cell(PER.value, eps_now, eps_prior)` | 예 (PER에 의존) | sanity 0~10 적용됨 |
| `gpm` | `matrix["GPM"][latest_q]` | `compute_cell` FLOW_TTM (gross_profit TTM ÷ revenue TTM) | 아니오 | `compute_matrix`가 이미 완성 |
| `opm` | `matrix["OPM"][latest_q]` | `compute_cell` FLOW_TTM (op_income TTM ÷ revenue TTM) | 아니오 | `compute_matrix`가 이미 완성 |

**PEG 3단 소비 계약(L309~325)의 어댑터 반영:** 어댑터 자체는 PEG를 재계산하지 않는다. **3단 계약은 Q2의 공유 헬퍼(`inject_prices_for_quarter`)에서 이미 수행**되어 `matrix["PEG"][q]`에 결과가 들어있다. 어댑터는 그 셀을 그대로 꺼낸다. 즉 호출 순서는 **반드시** `compute_matrix → inject_prices_for_quarter(latest_q, last_close) → matrix_to_fundamentals`. 이 순서를 어기면 PEG/PER가 빈 셀("가격 의존 지표…", metrics_engine.py:205)로 나와 회귀가 된다. **LANDMINE — 호출 순서 강제.**

**MetricCell 동일성:** `compute_matrix`/`compute_peg_cell`/`price_ratio` 모두 `fundamentals.MetricCell`을 재사용(metrics_engine.py:36 import)하므로 어댑터에 타입 변환·복사 불필요 — 그대로 `FundamentalsResult`에 넣으면 `sheet_portfolio._write_fund_cell`(L112)이 무변경 소비.

### Q4 (D-03): main_run.run 변경 지점·읽기/쓰기 순서 정렬 [VERIFIED: main_run.py read 전체]

**현재 흐름 (문제 — 순서 역전):**
1. PASS1 fan-out(L283 `run_all`) — `_fundamentals_with_auth`(L272)가 `fetch_fundamentals`(구 경로)로 4지표 산출, `TickerResult.fundamentals`에 stash.
2. PASS2 write(L301) `write_portfolio_sheet` — 시트1 작성 (위 fundamentals 소비).
3. **그 후에야** 히스토리 sync 루프(L334~353) `sync_ticker_history`로 DB 적재.

→ 현재는 시트1이 **DB 적재(L347)보다 먼저** 펀더멘털을 만든다. D-01은 이를 뒤집어 **sync → store 읽기** 순서를 요구한다.

**변경 지점 (정확히):**

| 위치 | 현재 | 변경 |
|------|------|------|
| L272~279 `_fundamentals_with_auth` 클로저 | `fetch_fundamentals(...)` 호출 | **제거** (D-03). PASS1 fan-out에서 펀더멘털 산출 분리 |
| L283~289 `run_all(...)` 호출 | `fundamentals_fn=_fundamentals_with_auth` 전달 | `fundamentals_fn=None` (또는 인자 제거 — runner는 None시 `fundamentals=None` 하위호환, runner.py:147) |
| L334~353 히스토리 sync 루프 | PASS2 **이후** | **PASS2 write보다 앞으로 이동** (D-01) — sync로 DB 적재 후 시트1이 읽도록 |
| PASS2 직전(신규) | — | 종목별 `compute_matrix(sym)` → `inject_prices_for_quarter(latest_q, last_close)` → `matrix_to_fundamentals` → `TickerResult.fundamentals`에 주입 (또는 별도 dict로 `write_portfolio_sheet`에 전달) |

**권고 순서 (D-01 충족):**
```
PASS1: run_all(fundamentals_fn=None)  # 시세·기업명만 fan-out, last_close 확보
SYNC : for s in specs: sync_ticker_history(s.symbol, source)  # DB 적재 (L334 루프를 위로)
READ : for res in results:
           matrix = compute_matrix(res.spec.symbol)            # 외부 호출 0
           last_close = res.enriched_df.iloc[-1].get("Close")  # 시세 PASS1에서 확보
           inject_prices_for_quarter(matrix, latest_q, last_close, matrix["EPS_ttm"])
           res.fundamentals = matrix_to_fundamentals(matrix, latest_q)  # 어댑터
PASS2: write_portfolio_sheet(...)                              # 시트1 작성 (무변경)
```

**주의사항:**
- **last_close 출처 유지:** 현재 last_close는 PASS1 worker 안(runner.py:100)에서 `df.iloc[-1].get("Close")`. 이관 후엔 READ 단계가 `res.enriched_df`에서 같은 값을 꺼내야 동일성 유지(Q2 드리프트 누수 지점). `enriched_df.attrs`/`iloc[-1]` 경로 동일하게 쓸 것.
- **인증 실패 소스(skip_edgar/skip_dart) 처리:** 구 경로의 `skip_edgar`/`skip_dart`(L277)는 fetch 차단용이었다. store 읽기는 fetch가 아니라 **이미 적재된 DB raw 읽기**이므로 인증과 무관 — 인증 실패 시에도 과거 적재분이 있으면 표시 가능. 단 sync 루프는 여전히 인증 실패 소스를 skip(L338~343)하므로, **인증 실패 + 첫 실행 = DB 빈 종목 = D-02 빈칸**. 자연스러운 동작.
- **속도/외부 호출 ≈0:** `compute_matrix`는 `fetch_raw_quarters`(SQLite SELECT)만 — 외부 호출 0. sync 루프는 접수번호 델타로 평소 full-fetch 0(SC3, Phase 7 검증됨). 따라서 시트1도 평소 외부 펀더멘털 호출 ≈0 달성(FUND-11).
- **요약 줄 정리:** 캐시 요약(L370) "펀더멘털 HIT/MISS"는 `.cache/fundamentals` 제거 시 0 고정 → 줄 제거 또는 의미 재정의 필요(회귀 표시 아님, 단순 위생).

### Q5 (D-09): provenance "소스 · 최신분기" 라벨 재구성 [VERIFIED: metrics_engine 분기키·source]

구 경로는 `f"EDGAR · {quarter}"`(fundamentals.py:145)를 `MetricCell.note`로 넣고, `_write_fund_cell`(L125)이 `cell.note or cell.source`를 호버 주석으로 쓴다.

**신 경로에서 분기·소스 정보 획득:**
- **최신 분기:** `compute_matrix` 반환의 분기 키는 `"YYYYQn"`(metrics_engine.py:330 `sorted({q...})`). `latest_q = quarters[-1]`. 라벨의 "2026Q2" 부분 = `latest_q` 그대로.
- **소스:** 각 `MetricCell.source`가 이미 per-metric provenance. `compute_cell`의 `_merge_provenance`(L242)가 동일소스 단일·혼합 정렬 "+"결합(예 `"DART+yf"`, L160). PEG는 `compute_peg_cell`이 `source=None`(per_value만 받음, L282) — 이 경우 PER 셀 source를 승계하거나 빈 라벨.

**어댑터의 라벨 합성 (D-09 재구성):**
```python
def _provenance_note(cell: MetricCell, latest_q: str) -> str | None:
    if cell.source:
        return f"{cell.source} · {latest_q}"   # "EDGAR · 2026Q2", "DART+yf · 2026Q2"
    return cell.note  # 결손/사유 그대로 (D-10)
```
어댑터는 각 셀의 `note`를 위 합성값으로 덮어쓴다(값 있는 셀만). **결손 셀은 D-10대로 기존 한국어 사유 note 보존** — `_write_fund_cell`의 `cell.note or cell.source` 로직 무변경(L125), `write_blank` + 사유(L129~131) 그대로.

⚠️ **PEG source 누락 LANDMINE:** `compute_peg_cell`은 source=None을 반환(metrics_engine.py:282 명시). 어댑터가 PEG 셀에 PER 셀 source를 주입하지 않으면 PEG 주석이 분기만(또는 사유만) 나와 구 경로(`EDGAR · Q`) 대비 미세 회귀. **어댑터에서 PEG.source = PER.source 승계 권고** (docstring L283이 정확히 이 패턴 안내).

### Q6 (검증 / Nyquist): 드리프트 0 + Core Value 회귀 무손상 테스트 전략

**(A) 드리프트 0 (SC1) — 시트1 값 == fundamentals_history.xlsx 최신 스냅샷:**

두 출력이 **같은 함수 사슬**(`compute_matrix` → `inject_prices_for_quarter` → 최신열)을 쓰면 구조적으로 일치. 검증은 그 동일성을 단언:
- **단위 동치 테스트:** 동일 fixture(`fetch_fn_stub`, `tests/fixtures/history_fixtures.py` 재사용)로 `matrix_to_fundamentals(matrix, latest_q)`의 4셀 value와 `write_snapshot_sheet`가 쓰는 스냅샷 셀(매트릭스 최신열, sheet_snapshot.py:57-66)이 **동일 MetricCell 객체/값**임을 단언. 같은 `latest_q`·같은 가격(last_close==current) 가정.
- **가격 동일성 가드:** 시트1 `last_close`(runner.py:100)와 트렌드 `current`(quarter_price `Close.dropna().iloc[-1]`)가 같은 OHLCV에서 같은 값인지 단언하는 테스트(Q2 누수 지점). 동일 캐시 fixture로 두 추출 경로가 같은 float 반환 확인.

**(B) Core Value(조건부 색 신호) 회귀 무손상 — 최우선:**

색 신호는 시트1의 **σ-bucket**(`decide_sigma_bucket` 등, sheet_portfolio.py:174-203)이며 **펀더멘털 4셀과 무관**(펀더멘털은 색 없는 `(DEFAULT, num_fmt)`, L121). 따라서 이관이 색 로직을 건드리지 않음이 핵심:
- **시트1 셀 스냅샷 회귀 테스트:** `test_history_integration.py:test_sheet1_unchanged_by_history`(이미 존재) 패턴 차용 — 이관 전/후 `write_portfolio_sheet` 산출 xlsx를 openpyxl로 읽어 σ-bucket 색 서식·셀 값이 동일함을 직접 단언. 펀더멘털 4셀은 값 동치, 색 영역은 바이트 불변.
- **`sheet_portfolio.py` 0줄 diff 단언:** `git diff` 기반 가드(Phase 9 SUMMARY가 쓴 `git diff HEAD~N sheet_portfolio` 빈 출력 패턴) — writer 무변경 = 색 회귀 0 구조적 보장.
- **D-02 빈칸 동작:** DB 빈 종목 → 4셀 `write_blank`+한국어 사유, 색 신호 무영향 테스트.

**(C) 단일 원천·외부 호출 0:**
- 이관 후 시트1 경로에서 `fetch_edgar_cached`/`fetch_dart_cached`/`fetch_fundamentals`가 **호출 0**임을 mock 호출 카운트로 단언(네트워크 0).
- `compute_matrix`가 `fetch_raw_quarters`(SQLite)만 호출 — 외부 0.

상세는 아래 **## Validation Architecture** 참조.

---

## 이관 시 랜드마인 · 회귀 위험 목록

| # | 위험 | 근거 | 완화 |
|---|------|------|------|
| L1 | **호출 순서 위반** — 어댑터가 `inject_prices_for_quarter` 전에 PER/PEG 읽으면 빈 셀("가격 의존 지표…") | metrics_engine.py:205 | READ 단계 순서 강제(Q4) + 어댑터 단위 테스트 |
| L2 | **per-quarter 추출기 오삭제** — `fetch_edgar_quarterly_raw`/`fetch_dart_quarterly_raw`(store 경로)를 `fetch_edgar_cached`(구 경로)와 혼동해 제거 | Q1 호출사슬 | 제거 대상 함수명 정확 명시(D-03 = `fetch_fundamentals`/`_fill_*`/`fetch_*_cached`만) |
| L3 | **OHLCV 캐시 파손** — cache.py 편집 시 `_get_cache`/`get_ohlcv` 오삭제 | cache.py L23,65,81 | 펀더멘털 헬퍼(L106~150)만 제거, OHLCV/기업명 미접촉 + `test_cache.py`/`test_cache_isolation.py` 녹색 유지 |
| L4 | **last_close 불일치** — 시트1 last_close ≠ 트렌드 current → SC1 미세 드리프트 | runner.py:100 vs quarter_price | 가격 동일성 가드 테스트(Q6-A) |
| L5 | **PEG provenance 누락** — `compute_peg_cell` source=None → 주석 회귀 | metrics_engine.py:282 | 어댑터에서 PEG.source = PER.source 승계(Q5) |
| L6 | **요약 줄 회귀** — "펀더멘털 HIT/MISS" 줄이 캐시 제거 후 0 고정/KeyError | main_run.py:370, cache `_stats` | `fund_hit`/`fund_miss` 키·요약 포맷 동시 정리 |
| L7 | **인증-fetch 결합 잔재** — `skip_edgar`/`skip_dart` 분기를 store 읽기에 잘못 적용 | main_run.py:277 | store 읽기는 인증 무관(이미 적재분 읽음). sync 루프만 인증 skip 유지 |
| L8 | **분기 결손 종목** — DB raw 없으면 `compute_matrix`가 빈 분기축 → `latest_q=None` → 어댑터 빈칸 | metrics_engine.py:330 | D-02 빈칸+사유로 정상 처리(어댑터 `cell_or_empty`) |
| L9 | **시트1 writer 우발적 수정** — Core Value 색 신호 회귀 | sheet_portfolio.py | 0줄 diff 가드(Q6-B) |

## Standard Stack

신규 라이브러리 **0** — 전부 기존 의존성 재사용 (내부 이관). CLAUDE.md 스택 유지.

| Module/API | 역할 | 출처 |
|------------|------|------|
| `metrics_engine.compute_matrix` | 분기 매트릭스 (외부 호출 0) | 기존 (Phase 8) |
| `metrics_engine.price_ratio` / `compute_peg_cell` / `_calendar_quarter_offset` | 가격 주입·PEG 3단 | 기존 (Phase 8) |
| `fundamentals.MetricCell` / `FundamentalsResult` / `_is_missing` / `_empty_cell` | 데이터 모델·결손 게이트 (보존, D-04) | 기존 |
| `fundamentals_delta.sync_ticker_history` | DB 적재 (PASS1) | 기존 (Phase 7) |
| `fundamentals_store.fetch_raw_quarters` / `count_rows` | store 읽기 | 기존 (Phase 7) |
| `history_render._inject_prices` | 공유 헬퍼 추출 원본 (D-06) | 기존 (Phase 9) |

## Don't Hand-Roll

| 문제 | 직접 만들지 말 것 | 재사용 | 이유 |
|------|------------------|--------|------|
| PER/PEG/GPM/OPM 산식 | 새 `_compute_*` | `compute_matrix`/`compute_peg_cell`/`price_ratio` | 단일 원천(D-04) — 새 산식 = 드리프트 |
| 결손 판정 | `if v is None` | `_is_missing` (WR-01) | NaN 누수 차단(Core Value 직결) |
| 분기 산술 | 직접 q-4 계산 | `_calendar_quarter_offset` | Q1 경계 버그(Pitfall 5) |
| 가격 주입+PEG | 시트1 전용 사본 | `_inject_prices` 추출 공유 헬퍼(D-06) | 사본 = 드리프트 구조적 |
| 데이터 모델 | 새 dataclass | `MetricCell`/`FundamentalsResult`(D-04) | sheet_portfolio writer 무변경 |

## Runtime State Inventory (이관 phase)

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `.cache/fundamentals` diskcache (7일 TTL, 키 `SOURCE\|TICKER\|QUARTER`) — 구 경로 전용. `data/fundamentals.db`(store, 유지) | 코드 제거 후 `.cache/fundamentals` 디렉터리는 자연 소멸(미참조). 데이터 마이그레이션 불필요(store DB가 이미 단일 원천) |
| Live service config | None — 외부 서비스 UI 설정 없음 (로컬 도구) | None |
| OS-registered state | None — Windows Task Scheduler `uv run python main.py`는 명령 불변 (CLAUDE.md "no code change") | None |
| Secrets/env vars | `OPENDART_API_KEY`(.env) — DART 인증용. 구 경로/store 경로 공유, 이름 불변 | None — store sync도 동일 키 사용 |
| Build artifacts | None — 함수 제거는 소스 변경, 재설치 불요(uv editable) | None |

**`.cache/ohlcv`·`.cache/company`:** 무관·유지 (Q1 확인 — 별개 디렉터리·헬퍼).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.x (+ pytest-mock) |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (testpaths=["tests"], pythonpath=["src"]) |
| Quick run command | `uv run pytest tests/test_metrics_engine.py tests/test_history_render.py -x -q` |
| Full suite command | `uv run pytest -q` |
| 현재 baseline | 375 passed (Phase 9 완료 시점, STATE.md) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| FUND-11 | 어댑터 4셀 매핑 (matrix 최신열 → FundamentalsResult) | unit | `pytest tests/test_fundamentals_view.py::test_adapter_maps_latest_column -x` | ❌ Wave 0 (신규) |
| FUND-11 | 공유 헬퍼 `inject_prices_for_quarter` 단일분기 동작 | unit | `pytest tests/test_metrics_engine.py::test_inject_prices_for_quarter -x` | ❌ Wave 0 (신규) |
| FUND-11 | 드리프트 0 — 어댑터 4셀 == 스냅샷 최신열 (동일 fixture·가격) | unit | `pytest tests/test_fundamentals_view.py::test_sheet1_matches_snapshot -x` | ❌ Wave 0 (신규) |
| FUND-11 | last_close == quarter_price.current 동일성 가드 (L4) | unit | `pytest tests/test_fundamentals_view.py::test_price_source_parity -x` | ❌ Wave 0 (신규) |
| FUND-11 | PEG provenance 승계 (`source = PER.source`, L5) | unit | `pytest tests/test_fundamentals_view.py::test_peg_provenance_inherited -x` | ❌ Wave 0 (신규) |
| FUND-11 | 시트1 색 신호 회귀 0 (σ-bucket 셀 불변) | integration | `pytest tests/test_sheet_portfolio.py -k color -x` | ✅ (기존 패턴 확장) |
| FUND-11 | run 순서 sync→read→write, 외부 펀더멘털 호출 0 | integration | `pytest tests/test_history_integration.py -k single_source -x` | ✅ (확장) |
| FUND-11 | D-02 DB 빈 종목 → 4셀 빈칸+사유 | unit | `pytest tests/test_fundamentals_view.py::test_missing_db_blank -x` | ❌ Wave 0 (신규) |
| FUND-11 (위생) | `fetch_fundamentals`/`fetch_*_cached` 시트1 경로 호출 0 | integration | `pytest tests/test_history_integration.py -k no_legacy_fetch -x` | ❌ Wave 0 (신규) |

### Sampling Rate
- **Per task commit:** `uv run pytest tests/test_metrics_engine.py tests/test_history_render.py tests/test_fundamentals_view.py -x -q` (어댑터·헬퍼·엔진 < 5초)
- **Per wave merge:** `uv run pytest tests/test_sheet_portfolio.py tests/test_history_integration.py tests/test_cache.py tests/test_cache_isolation.py -q` (색 회귀·이관·캐시 분리)
- **Phase gate:** `uv run pytest -q` 전체 녹색 (≥375, 회귀 0) + `git diff sheet_portfolio.py` 빈 출력 확인 후 `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_fundamentals_view.py` — 신규 어댑터/공유헬퍼 모듈 테스트 (어댑터 매핑·드리프트 동치·가격 parity·PEG provenance·빈 DB). 위치는 Claude 재량(어댑터 모듈명에 맞춤).
- [ ] `tests/test_history_integration.py` 확장 — 시트1 단일원천 단언(`no_legacy_fetch`/`single_source`): `fetch_fundamentals`·`fetch_edgar_cached`·`fetch_dart_cached` mock 호출 카운트 0.
- [ ] `tests/test_sheet_portfolio.py` 확장 — 색 신호(σ-bucket) 셀 서식 불변 단언(이관 전후 비교 또는 고정 기대값).
- [ ] fixture 재사용: `tests/fixtures/history_fixtures.py`의 `fetch_fn_stub`/`build_ohlcv`/`TICKER_INDUSTRY` (네트워크 0) — 신규 테스트도 동일 stub로 격리. conftest `_isolated_fundamentals_db`/`_isolated_disk_cache` 유지.
- [ ] 프레임워크 설치: 불필요 (pytest 기존 설치).

## Security Domain

> `security_enforcement` 명시 false 아님 → 포함.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V5 Input Validation | yes | store 읽기는 `fetch_raw_quarters` `?`-바인딩 SELECT (Phase 7 확립, ASVS V5) — 신규 SQL 0 |
| V6 Cryptography | no | 해당 없음 |
| V7 Error Handling/Logging | yes | **예외 로그 `type(exc).__name__`만** — `OPENDART_API_KEY`/EDGAR UA가 예외 원문 URL에 실릴 수 있음 (T-04-03, fundamentals.py:356, main_run.py:352 패턴 유지) |
| V8 Data Protection | yes | API 키 .env + .gitignore (CLAUDE.md). `data/`·`.cache/` .gitignore (Phase 7 SC5) |

### Known Threat Patterns for 이 stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| API 키 로그 누설 (예외 원문 보간) | Information Disclosure | 예외 타입명만 로깅 (CR-01·T-04-03) — 이관 코드도 동일 준수 |
| 캐시 제거 시 OHLCV 파손 | Denial of Service (기능 마비) | Q1 분리 확인 + 캐시 격리 테스트 |

## Project Constraints (from CLAUDE.md)
- **Core Value 절대 보호:** 중앙값±표준편차 색 신호 (시트1) — 이관이 색 로직 0줄 변경.
- **단일 원천:** 시세=Yahoo, 재무=EDGAR→DART→yf/Naver. store/registry가 재무 단일 원천화 (FUND-11 목표).
- **한국어 UI:** 결손 사유·로그·요약 한국어 유지 (D-02/D-10).
- **pytest:** 모든 변경 테스트 (Validation Architecture).
- **Tech stack 불변:** yfinance/openpyxl/XlsxWriter/pandas — 신규 라이브러리 0.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | 시트1 `last_close`와 트렌드 `current`가 같은 OHLCV 캐시에서 동일 float | Q2/Q6/L4 | 미세 드리프트(SC1) — 가격 parity 테스트가 잡음 |
| A2 | 어댑터/공유헬퍼 모듈 위치는 Claude 재량 (계약만 준수) | Q2/Q3 | 낮음 — CONTEXT 명시 |
| A3 | `fund_hit`/`fund_miss` 요약 줄은 제거/재정의해도 회귀 아님 (위생) | Q4/L6 | 낮음 — 사용자 가시 카운트만 |

**나머지 모든 주장은 [VERIFIED: 코드 read/grep]** — cache.py·fundamentals.py·metrics_engine.py·history_render.py·main_run.py·runner.py·sheet_portfolio.py·sheet_snapshot.py 정독 기반.

## Open Questions

1. **어댑터를 `TickerResult.fundamentals`에 주입 vs 별도 dict 전달**
   - 알려진 것: `write_portfolio_sheet`(main_run.py:301)는 `results`를 받고 `res.fundamentals`를 읽음(sheet_portfolio.py:249).
   - 불확실: PASS1에서 fundamentals를 안 만들면 `res.fundamentals`는 None. READ 단계에서 `res.fundamentals = adapter(...)` 재할당(dataclass mutable) vs `{sym: FundamentalsResult}` 별도 dict.
   - 권고: `res.fundamentals` 재할당이 writer 무변경 유지에 가장 단순 — `TickerResult`는 frozen 아님(runner.py:34 `@dataclass`). planner 확정.

2. **요약 "펀더멘털 HIT/MISS" 줄 처리**
   - 캐시 제거 후 항상 0. 줄 삭제 vs 의미 재정의(store 델타 HIT/MISS는 이미 "히스토리:" 줄에 존재, L380).
   - 권고: 줄 제거 (중복 — 델타 줄이 단일 원천 호출 현황 대표). planner 확정.

## Sources

### Primary (HIGH — 코드 직접 read/grep, 본 세션)
- `src/stocksig/io/cache.py` (L23~199) — 3캐시 분리 확정 (Q1)
- `src/stocksig/io/fundamentals.py` (전체) — 구 경로·보존 계약 (D-03/D-04)
- `src/stocksig/io/metrics_engine.py` (전체) — compute_matrix/price_ratio/compute_peg_cell/PEG 3단 계약 (Q3/Q5)
- `src/stocksig/io/history_render.py` (L70~94) — `_inject_prices` 추출 원본 (Q2)
- `src/stocksig/main_run.py` (전체) — run 흐름·PASS1/PASS2·sync 루프 (Q4)
- `src/stocksig/runner.py` (L30~165) — last_close 출처·fundamentals_fn 계약
- `src/stocksig/output/sheet_portfolio.py` (L1~265) — 4셀 writer·색 신호 (Core Value)
- `src/stocksig/output/sheet_snapshot.py` (전체) — 드리프트 비교 기준점 (Q6)
- grep: `get_fund/put_fund/fetch_*_cached` 호출사슬, conftest 격리 fixture
- `.planning/config.json` — nyquist_validation: true

### Secondary
- `.planning/STATE.md` — Phase 7·8·9 SUMMARY (산식·계약·검증 진실)
- `.planning/REQUIREMENTS.md` — FUND-11·Out of Scope
- `CLAUDE.md` — 스택·Core Value·보안 제약

## Metadata

**Confidence breakdown:**
- 캐시 분리(Q1, BLOCKING): HIGH — 전체 호출사슬 grep 확정
- 어댑터·공유헬퍼 경계(Q2/Q3): HIGH — 시그니처·반환구조 직접 read
- run 변경 지점(Q4): HIGH — 흐름 전체 read, 순서 역전 명확
- provenance(Q5): HIGH — source 합성·PEG None 동작 확인
- 검증 전략(Q6): HIGH — 기존 테스트 패턴(test_history_integration) 확인, 신규 갭 명확
- 드리프트 가격 동일성(A1): MEDIUM — 두 추출 경로 동일 캐시이나 NaN 트리밍 미세 차이 가능성, 테스트로 보강 필요

**Research date:** 2026-06-23
**Valid until:** 코드 변경 시까지 (내부 리팩터 — 외부 의존성 currency 무관). 30일+.
