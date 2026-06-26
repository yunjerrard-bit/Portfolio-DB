# Phase 10: 시트1 펀더멘털 통합 store/registry 이관 - Pattern Map

**Mapped:** 2026-06-23
**Files analyzed:** 7 (신규 2 · 수정 3 · 무변경-계약 2)
**Analogs found:** 7 / 7 (전부 동일 코드베이스 내 강한 analog 존재 — 순수 내부 이관 phase)

> 이 phase는 신규 기술 0·내부 이관이다. 모든 산출물은 기존 코드를 추출·재배선하거나
> 기존 데이터 모델 계약(`FundamentalsResult`/`MetricCell`)에 정확히 맞추는 작업이다.
> "새로 짤 패턴"은 없고 "어떤 기존 코드를 복제·추출하는가"만 있다.

## File Classification

| 신규/수정 파일 | Role | Data Flow | Closest Analog | Match Quality |
|----------------|------|-----------|----------------|---------------|
| 어댑터 `matrix_to_fundamentals` (위치 재량, 예: `src/stocksig/io/fundamentals_view.py` 신규) | utility/adapter | transform | `src/stocksig/io/history_render.py` (matrix 소비) + `src/stocksig/io/fundamentals.py` (`FundamentalsResult`/`_empty_cell` 생성) | exact (transform + 데이터 모델 둘 다 존재) |
| 공유 헬퍼 `inject_prices_for_quarter` (위치 재량, 예: `metrics_engine` 또는 신규 모듈) | utility | transform | `src/stocksig/io/history_render.py` `_inject_prices` (L70-94) | exact (추출 원본) |
| `src/stocksig/main_run.py` §`run` (수정) | orchestration | request-response/batch | 동일 함수 현재 흐름 (self-analog) + 히스토리 sync 루프 (L334-353) | exact (재배선) |
| `src/stocksig/output/sheet_portfolio.py` (**무변경 목표**) | output/writer | transform→render | self (현재 입력 계약 = 어댑터 출력 명세) | exact (계약 고정) |
| `tests/test_fundamentals_view.py` (신규) | test | — | `tests/test_history_integration.py` + `tests/fixtures/history_fixtures.py` | exact (fixture 재사용) |
| `tests/test_history_integration.py` (확장) | test | — | self (기존 `mocker.spy` 호출 카운트 패턴) | exact |
| `tests/test_sheet_portfolio.py` (확장) | test | — | `test_history_integration.py::test_sheet1_unchanged_by_history` (셀 불변 단언) | role-match |

---

## Pattern Assignments

### 어댑터 `matrix_to_fundamentals` (utility/adapter, transform)

**Analog A (소비측):** `src/stocksig/io/history_render.py` — `compute_matrix` 반환 매트릭스에서 `matrix.get(metric, {}).get(q)`로 셀을 꺼내는 패턴 (L83, L87-94).
**Analog B (생성측):** `src/stocksig/io/fundamentals.py` — `FundamentalsResult`/`MetricCell`/`_empty_cell` dataclass와 결손 placeholder 생성.

**데이터 모델 계약 (복제 대상, `fundamentals.py` L32-67):**
```python
@dataclass
class MetricCell:
    value: float | None      # None = 결손 (0/-999999 금지, D-05)
    source: str | None       # "EDGAR" | "DART" | "yf" | "DART+yf" | None
    note: str | None         # "EDGAR · 2026Q2" 또는 "조회 실패: <사유>"

@dataclass
class FundamentalsResult:
    per: MetricCell
    peg: MetricCell
    gpm: MetricCell
    opm: MetricCell

def _empty_cell(note: str | None = None) -> MetricCell:
    return MetricCell(value=None, source=None, note=note)
```

**핵심:** `compute_matrix`/`compute_peg_cell`/`price_ratio`는 모두 `fundamentals.MetricCell`을 그대로 재사용한다 (`metrics_engine.py` import). 따라서 어댑터는 **타입 변환·복사 없이** 매트릭스 셀을 `FundamentalsResult`에 그대로 넣는다 — 이것이 `sheet_portfolio` 무변경 소비를 가능하게 한다 (D-08).

**필드 매핑 (RESEARCH Q3 확정):**

| 시트1 셀 | matrix 키 | 가격 의존? | source 비고 |
|----------|-----------|-----------|-------------|
| `per` | `matrix["PER"][latest_q]` | 예 (헬퍼가 주입) | EPS_ttm 셀 source 보존 |
| `peg` | `matrix["PEG"][latest_q]` | 예 (PER 의존) | **`compute_peg_cell`은 source=None → 어댑터가 PER.source 승계 (L5 LANDMINE)** |
| `gpm` | `matrix["GPM"][latest_q]` | 아니오 | 이미 완성 |
| `opm` | `matrix["OPM"][latest_q]` | 아니오 | 이미 완성 |

**provenance 라벨 재구성 (D-09, RESEARCH Q5):** 구 경로는 `f"EDGAR · {quarter}"`를 `note`에 넣고 `_write_fund_cell`이 `cell.note or cell.source`를 호버 주석으로 쓴다. 어댑터는 값 있는 셀의 `note`를 `f"{cell.source} · {latest_q}"`로 합성, 결손 셀은 기존 한국어 사유 `note` 보존 (D-10).

**결손 처리 (D-02, L8):** `latest_q is None`(DB 빈 종목) 또는 셀 없음 → `_empty_cell("조회 실패: DB 분기 데이터 없음")`. 구 경로 "조회 실패" 표시와 동일 → 회귀 아님.

**LANDMINE — 호출 순서 강제 (L1):** `compute_matrix → inject_prices_for_quarter(latest_q, last_close) → matrix_to_fundamentals` 순서 필수. 헬퍼 전에 어댑터가 PER/PEG를 읽으면 빈 셀("가격 의존 지표…", `metrics_engine.py:205")이 나온다.

---

### 공유 헬퍼 `inject_prices_for_quarter` (utility, transform)

**Analog (추출 원본):** `src/stocksig/io/history_render.py` `_inject_prices` (L70-94).

**현재 시그니처 (다분기 in-place):**
```python
def _inject_prices(matrix: dict, quarters: list[str], qmap: dict,
                   current: float | None, latest_q: str | None) -> None:  # in-place
```

**현재 본문 (L77-94) — 분기 루프 안의 코어가 추출 대상:**
```python
    eps_map = matrix.get("EPS_ttm", {})
    for q in quarters:
        price = current if (latest_q is not None and q == latest_q) else qmap.get(q)
        # (a) 가격 의존 4종 — 분모 per-share 셀에 가격 주입.
        for metric, denom in _PRICE_DEPENDENT.items():
            denom_cell = matrix.get(denom, {}).get(q)
            matrix.setdefault(metric, {})[q] = price_ratio(denom_cell, price)
        # (b) 분기별 PEG (3단 계약, D-10).
        per = matrix.get("PER", {}).get(q)
        per_value = per.value if per is not None else None
        eps_now = eps_map.get(q)
        eps_now_v = eps_now.value if eps_now is not None else None
        qp = _calendar_quarter_offset(q, -4)
        eps_prior = eps_map.get(qp)
        eps_prior_v = eps_prior.value if eps_prior is not None else None
        matrix.setdefault("PEG", {})[q] = compute_peg_cell(per_value, eps_now_v, eps_prior_v)
```

**추출 후 코어 시그니처 (단일 분기 — RESEARCH Q2 권고):**
```python
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

**비파괴 추출 계약 (트렌드 측 무손상):** `_inject_prices`는 시그니처·외부 동작을 유지하되 본문 루프가 `inject_prices_for_quarter(matrix, q, price, eps_map)`를 호출하도록만 바꾼다. quarters/qmap/current/latest_q 입출력 계약 그대로 → `run_history` + 기존 14개 통합 테스트 무손상.

**의존성 (전부 import 가능·무상태):** `_PRICE_DEPENDENT` (history_render.py:38, REGISTRY 도출), `price_ratio`/`compute_peg_cell`/`_calendar_quarter_offset` (metrics_engine).

**시트1 측 사용 (1회 호출):** `inject_prices_for_quarter(matrix, latest_q, last_close, matrix["EPS_ttm"])`.

---

### `src/stocksig/main_run.py` §`run` (orchestration, 재배선)

**Analog:** 동일 함수 현재 흐름 (self) + 히스토리 sync 루프.

**제거 대상 — `_fundamentals_with_auth` 클로저 (L272-289):**
```python
    def _fundamentals_with_auth(ticker, market, last_close):
        return fetch_fundamentals(
            ticker, market, last_close,
            skip_edgar=(market == "US" and auth.edgar_ok is False),
            skip_dart=(market == "KR" and auth.dart_ok is False),
        )
    results, failures = run_all(
        specs, classify_market, pipeline,
        fundamentals_fn=_fundamentals_with_auth,   # → None (runner.py:147 하위호환)
        company_name_fn=fetch_company_name,
    )
```

**재사용 패턴 — 히스토리 sync 루프 (L334-353, 이 루프를 PASS2 write보다 앞으로 이동, D-01):**
```python
    for s in specs:
        market = classify_market(s.symbol)
        if market == "US":
            source = "EDGAR"
            if auth.edgar_ok is False:
                continue
        elif market == "KR":
            source = "DART"
            if auth.dart_ok is False:
                continue
        else:
            continue
        try:
            fundamentals_delta.sync_ticker_history(s.symbol, source)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                "%s | 히스토리 경로 실패(%s) — 시트1 산출물은 영향 없음",
                s.symbol, type(exc).__name__,   # T-04-03: 예외 타입명만 (CR-01)
            )
```

**last_close 출처 (동일성 유지 — L4 드리프트 누수):** 구 경로 `runner.py:100` `last_close = df.iloc[-1].get("Close")`. 이관 후 READ 단계는 `res.enriched_df.iloc[-1].get("Close")`로 **같은 경로** 사용 필수.

**권고 순서 (RESEARCH Q4):**
```
PASS1: run_all(fundamentals_fn=None)               # 시세·기업명만, last_close 확보
SYNC : for s in specs: sync_ticker_history(...)     # L334 루프를 위로 (DB 적재)
READ : for res in results:
           matrix = compute_matrix(res.spec.symbol)        # 외부 호출 0 (SQLite SELECT)
           last_close = res.enriched_df.iloc[-1].get("Close")
           inject_prices_for_quarter(matrix, latest_q, last_close, matrix["EPS_ttm"])
           res.fundamentals = matrix_to_fundamentals(matrix, latest_q)  # 어댑터 재할당
PASS2: write_portfolio_sheet(...)                   # 시트1 작성 (무변경)
```

**TickerResult.fundamentals 재할당:** `TickerResult`는 frozen 아님(`runner.py:34 @dataclass`) → READ 단계에서 `res.fundamentals = adapter(...)` 직접 재할당이 writer 무변경 유지에 가장 단순 (Open Q1).

**요약 줄 정리 (L6):** 캐시 요약 줄 (L370) `"펀더멘털 HIT %d/MISS %d"`는 `.cache/fundamentals` 제거 시 0 고정 → `stats["fund_hit"]`/`["fund_miss"]` 참조와 함께 줄 제거/재정의 (KeyError 회귀 방지).

**인증-fetch 결합 잔재 금지 (L7):** store 읽기(`compute_matrix`)는 fetch가 아니라 적재된 DB raw 읽기 → `skip_edgar`/`skip_dart` 적용 금지. 인증 skip은 SYNC 루프에만 유지.

---

### `src/stocksig/output/sheet_portfolio.py` (output/writer — **무변경 목표**)

**역할:** 어댑터 출력이 정확히 맞아야 하는 **입력 계약 명세** (Core Value 보호 — 0줄 diff 목표).

**입력 계약 — `_write_fund_cell` (L112-131):**
```python
def _write_fund_cell(ws, row, col, cell, num_fmt, formats) -> None:
    fmt = formats[(SigmaBucket.DEFAULT, num_fmt)]   # 펀더멘털은 색 없음 (DEFAULT)
    value = cell.value
    if value is not None and not _nan(value):
        ws.write_number(row, col, float(value), fmt)
        comment = cell.note or cell.source          # ← 어댑터의 합성 note가 여기로
        if comment:
            ws.write_comment(row, col, str(comment))
    else:
        ws.write_blank(row, col, None, fmt)         # D-02 빈칸
        ws.write_comment(row, col, str(cell.note or "조회 실패"))  # D-10 한국어 사유
```

**소비부 (L248-264):**
```python
    fund = res.fundamentals
    if fund is not None:
        _write_fund_cell(ws, row, _FUND_COL_PER, fund.per, "price", formats)
        _write_fund_cell(ws, row, _FUND_COL_PEG, fund.peg, "price", formats)
        _write_fund_cell(ws, row, _FUND_COL_GPM, fund.gpm, "percent_ratio", formats)
        _write_fund_cell(ws, row, _FUND_COL_OPM, fund.opm, "percent_ratio", formats)
    else:
        # 하위호환: fundamentals=None → 4셀 빈칸 + "펀더멘털 미수집"
```

**계약 요약 (어댑터가 반드시 충족):**
- `res.fundamentals`는 `FundamentalsResult(per, peg, gpm, opm)` — 각각 `MetricCell(value, source, note)`.
- 값 있는 셀: `value` float, `note` = `"{source} · {latest_q}"` (호버 주석으로 출력).
- 결손 셀: `value=None`, `note` = 한국어 사유 (`"조회 실패: …"`).
- **색 신호(σ-bucket)는 펀더멘털 4셀과 완전 무관** (L121 `(DEFAULT, num_fmt)`) — 이관이 색 로직을 건드리지 않는 것이 Core Value 회귀 0의 핵심 (L9).

---

### `tests/test_fundamentals_view.py` (신규 test)

**Analog (fixture):** `tests/fixtures/history_fixtures.py` — `fetch_fn_stub`/`build_ohlcv`/`TICKER_INDUSTRY` (네트워크 0, 결정적).

**fixture 재사용 패턴:**
```python
# fetch_fn_stub: compute_matrix(ticker, fetch_fn=fetch_fn_stub) 주입 — 외부 호출 0.
#   AAPL(EDGAR/tech), 005930.KS(DART/semis) 5분기(2025Q1~2026Q1) raw 7-tuple.
# build_ohlcv: fetch_ohlcv_cached monkeypatch용 합성 OHLCV (분기말 Close 단조 증가).
matrix = compute_matrix("AAPL", fetch_fn=fetch_fn_stub)
latest_q = sorted(set(...))[-1]   # "2026Q1"
inject_prices_for_quarter(matrix, latest_q, last_close=48.0, eps_map=matrix["EPS_ttm"])
result = matrix_to_fundamentals(matrix, latest_q)
```

**커버할 신규 테스트 (RESEARCH Validation Architecture, Wave 0):**
- `test_adapter_maps_latest_column` — 4셀 매핑 (PER/PEG/GPM/OPM = 최신열).
- `test_inject_prices_for_quarter` — 단일 분기 가격 주입 + PEG 3단.
- `test_sheet1_matches_snapshot` — 드리프트 0: 어댑터 4셀 value == `sheet_snapshot` 최신열 셀 (동일 fixture·가격).
- `test_price_source_parity` — `last_close`(runner.py:100) == 트렌드 `current`(quarter_price) 동일 float (L4 가드).
- `test_peg_provenance_inherited` — PEG.source = PER.source 승계 (L5).
- `test_missing_db_blank` — DB 빈 종목(`latest_q=None`) → 4셀 빈칸+한국어 사유 (D-02/L8).

**conftest 격리 (유지):** `_isolated_fundamentals_db`/`_isolated_disk_cache`.

---

### `tests/test_history_integration.py` (확장 test)

**Analog (self — 기존 호출 카운트/셀 불변 패턴):**

**mock 호출 카운트 패턴 (L102, L51-66) — 단일 원천 단언용:**
```python
def _setup_mock_yfinance(mocker, df):
    ticker_class = mocker.patch("stocksig.io.market.yf.Ticker")
    mocker.patch("stocksig.main_run.fetch_company_name", side_effect=lambda t: t)

def _disable_history(mocker):
    mocker.patch.object(fd, "probe_edgar_accession", return_value=None)
    mocker.patch.object(fd, "probe_dart_rcept", return_value=None)

spy = mocker.spy(edgar_client, "fetch_edgar_quarterly_raw")   # 호출 카운트 단언
```

**확장할 테스트 (Wave 0):**
- `no_legacy_fetch` — 시트1 경로에서 `fetch_fundamentals`/`fetch_edgar_cached`/`fetch_dart_cached` **호출 카운트 0** (`mocker.spy` + `assert spy.call_count == 0`).
- `single_source` — run 순서 sync→read→write, 외부 펀더멘털 호출 0.

---

### `tests/test_sheet_portfolio.py` (확장 test)

**Analog:** `test_history_integration.py::test_sheet1_unchanged_by_history` (L133-188) — 이관 전/후 `write_portfolio_sheet` 산출 xlsx를 openpyxl로 읽어 셀 값·서식 불변 단언 패턴.

**확장할 테스트 (Wave 0):**
- `-k color` — σ-bucket 셀 서식 불변 단언 (이관 전후 비교 또는 고정 기대값). 펀더멘털 4셀은 값 동치, 색 영역은 불변 (Core Value 회귀 0, L9).
- D-02 빈칸 동작 — DB 빈 종목 → 4셀 `write_blank`+사유, 색 신호 무영향.

---

## Shared Patterns

### 결손 게이트 `_is_missing` (WR-01)
**Source:** `src/stocksig/io/fundamentals.py` L72-78
**Apply to:** 어댑터·공유 헬퍼·모든 셀 lookup. 신규 정의 0 — import 재사용 (D-04).
```python
def _is_missing(x: float | None) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x))
```
> `history_render.py:45`가 이미 `from stocksig.io.fundamentals import _is_missing`로 공유 중 — 동일 패턴 따를 것.

### 예외 격리 + 타입명만 로깅 (CR-01 / T-04-03 보안)
**Source:** `runner.py` L102-107, `main_run.py` L348-353
**Apply to:** 어댑터·READ 단계 종목별 처리 (펀더멘털 결손 ≠ 티커 실패, D-disc-10).
```python
    except Exception as exc:  # noqa: BLE001
        logger.warning("%s | … 예외 흡수: %s", sym, type(exc).__name__)  # 원문·API키 미보간
```

### provenance "+" 병합 + 분기 라벨 합성 (D-09)
**Source:** `metrics_engine` `_merge_provenance` (예: `"DART+yf"`) + `compute_matrix` 분기 키 `"YYYYQn"`
**Apply to:** 어댑터 note 합성 (`f"{cell.source} · {latest_q}"`). PEG는 source=None → PER.source 승계 (L5).

### 캐시 분리 — 펀더멘털만 제거, OHLCV 미접촉 (D-05, L3)
**Source:** `cache.py` — `_FUND_DIR`/`get_fund`/`put_fund`/`make_fund_key`/`_fund_cache` (L106-150) 제거 대상; `_get_cache`/`_DEFAULT_DIR`/`get_ohlcv`/`make_key`/`_cache_lock` **미접촉**.
**Apply to:** 캐시 정리 task. `test_cache.py`/`test_cache_isolation.py` 녹색 유지로 OHLCV 무손상 검증.

---

## No Analog Found

해당 없음 — 모든 산출물이 동일 코드베이스 내 강한 analog를 가진다 (순수 내부 이관 phase).

## 절대 제거 금지 (LANDMINE L2)

`fetch_edgar_quarterly_raw` / `fetch_dart_quarterly_raw` (Phase 7 per-quarter raw 추출기, **store 경로**) — 구 경로 `fetch_edgar_cached`/`fetch_dart_cached`와 같은 모듈(`edgar_client`/`dart_client`)에 있으므로 함수명 정확히 구분. 제거 대상은 `*_cached`만 (D-03).

## Metadata

**Analog search scope:** `src/stocksig/io/` (fundamentals.py, history_render.py, metrics_engine.py, main_run.py, runner.py, cache.py), `src/stocksig/output/` (sheet_portfolio.py, sheet_snapshot.py), `tests/` (test_history_integration.py, fixtures/history_fixtures.py)
**Files scanned:** 10 (전부 RESEARCH가 코드 read로 검증한 파일)
**Pattern extraction date:** 2026-06-23
