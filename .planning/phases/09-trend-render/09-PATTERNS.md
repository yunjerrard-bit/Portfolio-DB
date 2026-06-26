# Phase 9: 트렌드 엑셀 렌더 - Pattern Map

**Mapped:** 2026-06-22
**Files analyzed:** 9 (신규 6 + 수정 1 + 테스트 3, planner 분할 재량)
**Analogs found:** 9 / 9 (전부 강한 아날로그 존재 — 신규 외부 패턴 0)

> **Core Value 불변 (CRITICAL):** 시트1 `src/stocksig/output/sheet_portfolio.py`·`src/stocksig/compute/color_rules.py`(로직)·`writer.py::make_workbook` 시그니처는 **읽기 전용 참조**다. 색 신호(중앙값±σ)·레이아웃을 **절대 수정하지 않는다.** 트렌드는 완전 별도 파일(`fundamentals_history_*.xlsx`)·별도 워크북 팩토리·별도 Format 캐시로 작성한다. 색 **상수**(`GREEN_100` 등)는 import 허용, 함수·로직은 미수정.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `src/stocksig/output/history_workbook.py` (신규) | config/factory | file-I/O | `src/stocksig/output/writer.py::make_workbook` | role-match (별도 Format 셋) |
| `src/stocksig/output/sheet_metric_matrix.py` (신규) | output/writer | transform→file-I/O | `src/stocksig/output/sheet_portfolio.py` | exact (식별열+행writer+freeze) |
| `src/stocksig/output/sheet_raw.py` (신규) | output/writer | file-I/O (long) | `sheet_portfolio.py` (헤더+행 루프) | role-match |
| `src/stocksig/output/sheet_snapshot.py` (신규) | output/writer | file-I/O | `sheet_portfolio.py` (1행/종목 + `_write_fund_cell`) | exact |
| `src/stocksig/compute/trend_color.py` (신규) | compute/utility | transform (순수) | `src/stocksig/compute/color_rules.py` (decide_*_bucket) | role-match (순수 함수·네트워크0) |
| `src/stocksig/io/quarter_price.py` (신규) | service/utility | transform | `src/stocksig/io/market.py::fetch_ohlcv_cached` 소비 | role-match |
| `src/stocksig/io/history_render.py` (신규) | orchestration/service | request-response | `src/stocksig/main_run.py::run` | exact (2-pass·import·로깅) |
| `main.py` (수정 — 서브커맨드 추가) | route/CLI | request-response | `main.py::main` (기존 argparse) | exact (동일 파일 확장) |
| `tests/test_*.py` + `tests/fixtures/` (신규) | test | — | `tests/test_metrics_engine.py`·`tests/test_sheet_portfolio.py`·`tests/fixtures/raw_quarters.py` | exact |

*(파일 분할은 planner 재량 — RESEARCH 권장 구조 차용. 위는 단일책임 가이드.)*

---

## Pattern Assignments

### `src/stocksig/output/history_workbook.py` (config/factory, file-I/O)

**Analog:** `src/stocksig/output/writer.py::make_workbook` (L70-142)

**왜 패턴만 차용하고 직접 호출 금지:** `make_workbook`은 시트1·종목시트용 **45키** Format 캐시(SigmaBucket/TechBucket/impulse 등)를 만든다. 트렌드는 다른 Format 셋(초록/빨강/무색 + header + comment)만 필요 → 별도 팩토리 신설(결합 회피, Pitfall 5).

**워크북 생성 옵션 패턴** (writer.py L86-88 — 그대로 차용):
```python
wb = xlsxwriter.Workbook(
    str(p), {"constant_memory": False, "nan_inf_to_errors": True}
)
```
- `nan_inf_to_errors=True`: IPO 직후·0-나누기 NaN/Inf가 셀 도달 시 TypeError 대신 Excel 오류 셀로 폴백.
- `[원천]` 시트가 수만 행이면 `constant_memory=True` 옵션화 검토(writer.py 주석 L83-85 근거).

**부모 디렉터리 자동 생성** (writer.py L81-82):
```python
p = Path(path)
p.parent.mkdir(parents=True, exist_ok=True)
```

**Format 캐시 베이킹 패턴** (writer.py L90-97 — 트렌드 전용 셋으로 재구성):
```python
formats: dict = {}
formats["green"] = wb.add_format({"bg_color": GREEN_100, "font_color": GREEN_900, "num_format": "#,##0.00", "bold": True})
formats["red"]   = wb.add_format({"bg_color": RED_100,   "font_color": RED_900,   "num_format": "#,##0.00", "bold": True})
formats["plain"] = wb.add_format({"num_format": "#,##0.00"})  # 무색 (D-07 게이트)
formats["header"] = wb.add_format({"bold": True, "align": "center"})
return wb, formats
```
**색 상수 import (로직 미수정 — 상수만):** `from stocksig.compute.color_rules import GREEN_100, GREEN_900, RED_100, RED_900` (color_rules.py L16-21: `GREEN_900="#1B5E20"`, `GREEN_100="#C8E6C9"`, `RED_900="#B71C1C"`, `RED_100="#FFCDD2"`).

---

### `src/stocksig/output/sheet_metric_matrix.py` (output/writer, transform→file-I/O)

**Analog:** `src/stocksig/output/sheet_portfolio.py` (전체 — 식별열·행writer·freeze·결손셀)

**식별 열 단일 진실 출처 패턴 (D-02 — A~E열 재사용)** (sheet_portfolio.py L37-63):
```python
PORTFOLIO_COLUMNS: list[str] = ["티커", "기업명", "시장", "티어", "산업", ...]
_COL: dict[str, int] = {name: i for i, name in enumerate(PORTFOLIO_COLUMNS)}
```
→ 트렌드 매트릭스도 동일 5개 식별열(`티커·기업명·시장·티어·산업`)을 선두에 두고, 명명 인덱스 dict로 시프트 회귀를 구조적으로 차단. 그 뒤에 분기 열(D-01)을 붙인다. **sheet_portfolio.py의 `_COL`/`PORTFOLIO_COLUMNS`는 import하지 말고 동일 헤더 리터럴로 트렌드 전용 정의**(시트1 결합 회피·22열 vs 5열+분기열 구조 다름).

**헤더 행 + 식별 셀 쓰기 패턴** (sheet_portfolio.py L313-315 헤더, L143-162 식별):
```python
for col_idx, name in enumerate(COLUMNS):
    ws.write(HEADER_ROW, col_idx, name, formats["header"])
# 식별 셀 (시장/티어/산업은 None 폴백)
ws.write_string(row, _COL["시장"], res.market)
ws.write_string(row, _COL["티어"], spec.tier or "")
ws.write_string(row, _COL["산업"], spec.industry or "")
```

**결손/sanity-밖 셀 = 빈값+코멘트 패턴 (D-11 — 0 대체 금지)** (sheet_portfolio.py `_write_fund_cell` L112-131):
```python
value = cell.value
if value is not None and not _nan(value):
    ws.write_number(row, col, float(value), fmt)
    comment = cell.note or cell.source
    if comment:
        ws.write_comment(row, col, str(comment))
else:
    ws.write_blank(row, col, None, fmt)          # 0/-999999 절대 금지 (D-11)
    ws.write_comment(row, col, str(cell.note or "조회 실패"))
```
→ **트렌드 차이:** D-11은 빈칸이 아니라 `"-"` 문자열 + 사유 코멘트 요구. `write_blank` 대신 `ws.write_string(row, col, "-")` + `ws.write_comment(...)`. 결손 게이트는 **신규 정의 금지**, `fundamentals._is_missing` 재사용(`from stocksig.io.fundamentals import _is_missing`; fundamentals.py L72-78 — None+NaN 동시 게이트).

**열 너비 + freeze panes 패턴 (D-04)** (sheet_portfolio.py L307·L336):
```python
ws.set_column(0, len(COLUMNS) - 1, 14)   # 기본 너비
ws.freeze_panes(5, 1)                     # (row, col) — 시트1은 헤더행(5)+A열(1) 고정
```
→ **D-04 차이:** "A열(티커)만 고정, 헤더행 freeze 안 함" → `ws.freeze_panes(0, 1)`(col 1 = B부터 스크롤, 행 미고정). 시장(C)·티어(D)는 글자폭 최소 너비 → `ws.set_column(_COL["시장"], _COL["시장"], 6)` 등 개별 폭(autofit 근사는 Claude 재량).

**Excel 금지문자 sheet명 sanitize 패턴** (sheet_portfolio.py L74·L80-83) — 지표 시트명은 고정 리터럴(PER/PEG/...)이라 불요하나, 동적 시트명 필요 시:
```python
_FORBIDDEN_SHEET_CHARS = re.compile(r"[\[\]:\*\?/\\]")
def _sanitize_sheet_name(name: str) -> str:
    return _FORBIDDEN_SHEET_CHARS.sub("_", name)[:31]
```

---

### `src/stocksig/output/sheet_snapshot.py` (output/writer, file-I/O) — [최신 스냅샷]

**Analog:** `sheet_portfolio.py` (종목 1행 × 전 지표 — 시트1 "한눈에" 뷰와 동형, D-13)

스냅샷 = 종목 1행 × 9지표 최신값. **매트릭스 최신 열 셀을 재계산 없이 재사용**(RESEARCH Open Q2). `_write_fund_cell`(위) 패턴으로 각 지표 셀 작성. PEG 결손 시 `"-"`.

---

### `src/stocksig/output/sheet_raw.py` (output/writer, file-I/O long) — [원천]

**Analog:** `sheet_portfolio.py` (헤더 + 행 루프 L313-334)

**입력 데이터 계약 (CRITICAL):** `fetch_raw_quarters(ticker)` 반환 = **7-tuple** `(quarter, source, field, value, period_type, reprt_code, unit)` — **`period_end`/`period_start`/`accession` 미포함**(RESEARCH Runtime State, store SELECT 컬럼 제외). [원천] 시트는 이 7-tuple로 구성. 분기말 종가는 raw에서 못 꺼냄(OHLCV 리샘플에서 별도 조달).

```python
from stocksig.io.fundamentals_store import fetch_raw_quarters
for r in fetch_raw_quarters(ticker):
    quarter, source, field, value, period_type, reprt_code, unit = r
    # long 행으로 write
```

---

### `src/stocksig/compute/trend_color.py` (compute/utility, transform 순수)

**Analog:** `src/stocksig/compute/color_rules.py` (decide_sigma_bucket/decide_rsi_bucket — 순수 함수·네트워크0·import만으로 테스트)

**상대색 결정 (D-05/06/07 — 신규 순수 로직, CLAUDE.md 정적 베이킹 정합):**
```python
LOWER_IS_BETTER = {"PER", "PEG", "PBR", "PCR", "PSR"}   # 낮을수록 초록 (D-06)
# HIGHER_IS_BETTER = {"ROE", "ROA", "GPM", "OPM"}        # 높을수록 초록

def relative_bucket(metric: str, value, peer_values: list, industry: str) -> str:
    valid = [v for v in peer_values if not _is_missing(v)]
    if industry == "" or len(valid) < 3:        # D-07 표본 게이트 (권장 N=3)
        return "무색"
    # peer 내 분위 → 상/중/하 3분할, LOWER_IS_BETTER면 방향 반전
    ...  # 동값/동순위 처리는 planner 재량 (RESEARCH A4 — 동률은 무색 또는 중위)
    return "초록" | "무색" | "빨강"
```
- **모집단 = (분기 열, 산업 그룹) 2차원** (Pitfall 3). 전 종목·전 분기 한 모집단 금지.
- 결손 게이트는 `fundamentals._is_missing` 재사용(신규 정의 금지).

**YoY 화살표 (D-08 — 유니코드 글리프, icon_set 기각):**
```python
from stocksig.io.fundamentals import _is_missing
def yoy_glyph(cell_q, cell_q_prior) -> str:
    if cell_q is None or cell_q_prior is None or _is_missing(cell_q.value) or _is_missing(cell_q_prior.value):
        return ""                                # 전년동기 결손 → 화살표 생략 (D-08)
    return " ▲" if cell_q.value > cell_q_prior.value else (" ▼" if cell_q.value < cell_q_prior.value else "")
```
- 4분기 전 키 = `metrics_engine._calendar_quarter_offset(q, -4)` (표시순과 독립).
- 색(Format)과 화살표(텍스트 글리프)는 직교 — 셀 = `ws.write_string(row, col, f"{v:.2f}{glyph}", fmt_<bucket>)`.

---

### `src/stocksig/io/quarter_price.py` (service/utility, transform) — D-09

**Analog:** `src/stocksig/io/market.py::fetch_ohlcv_cached` 소비 (24h TTL, 캐시 HIT 시 무호출)

```python
import pandas as pd
from stocksig.io.market import fetch_ohlcv_cached

def quarter_end_prices(ticker: str) -> tuple[dict[str, float], float]:
    df = fetch_ohlcv_cached(ticker)            # 캐시 HIT 시 외부호출 0
    close = df["Close"].dropna()
    qe = close.resample("QE").last()           # 분기말 마지막 거래일 종가 (휴장일 자동 처리)
    keys = qe.index.to_period("Q").astype(str) # ['2024Q1', ...] ← 엔진 분기키와 동일 표기 (Pitfall 4)
    qmap = dict(zip(keys, qe.to_numpy()))
    current_price = float(close.iloc[-1])      # 최신 열 = 현재가 (시트1과 동일 진입점 → 드리프트0)
    return qmap, current_price
```
- `"QE"`(pandas 2.2+), 구 `"Q"` deprecated. 키는 반드시 `to_period("Q").astype(str)`로 `YYYYQn` 일치(Pitfall 4).

---

### `src/stocksig/io/history_render.py` (orchestration, request-response) — 엔트리

**Analog:** `src/stocksig/main_run.py::run` (L235-391 — 2-pass·import 블록·카운터 리셋·한국어 로깅)

**import·로깅 컨벤션** (main_run.py L14-58):
```python
from __future__ import annotations
import logging
from pathlib import Path
logger = logging.getLogger(__name__)
```

**DB 미적재 게이트 (D-15 안내)** — `count_rows() == 0` 분기:
```python
from stocksig.io.fundamentals_store import count_rows
def run_history(tickers_path, output_dir):
    if count_rows() == 0:
        print("펀더멘털 DB가 비어 있습니다. 먼저 `uv run python main.py` 를 실행해 "
              "분기 펀더멘털을 적재한 뒤 다시 `history` 를 실행하세요.")
        return None
    ...
```

**다종목 매트릭스 재구성 (RESEARCH Pattern 2 — 외부호출 0):**
```python
from stocksig.io.metrics_engine import compute_matrix, price_ratio, compute_peg_cell, _calendar_quarter_offset
per_ticker = {t: compute_matrix(t) for t in sorted_tickers}   # ticker별 호출 (엔진 L299)
all_quarters = sorted({q for m in per_ticker.values() for cells in m.values() for q in cells})
display_quarters = list(reversed(all_quarters))               # D-01 최신 왼쪽 (엔진 오름차순 → reversed 필수, Pitfall 1)
```
- 종목마다 분기집합 다름 → `matrix[metric].get(q)` `.get` 가드(Pitfall 2). KeyError 금지.

**입력 소스 재사용** (main_run.py L50-53 import 그대로):
```python
from stocksig.io.input import read_tickers_extended      # TickerSpec(symbol, tier, industry)
from stocksig.io.company import fetch_company_name        # 식별열 기업명
from stocksig.io.market_kind import classify_market       # 시장 + D-03 정렬 (US→KR)
```
- D-03 정렬: `classify_market`로 US/KR 그룹화 후 각 그룹 내 `sorted(symbol)`.

**파일명 패턴 (D-14)** (main_run.py L294 차용):
```python
output_path = out_dir / f"fundamentals_history_{date.today():%Y%m%d}.xlsx"
```

**예외 격리 로깅** (main_run.py L348-353 — 보안: 타입명만):
```python
except Exception as exc:  # noqa: BLE001
    logger.warning("... 실패(%s)", type(exc).__name__)   # API 키·예외 원문 미노출
```

---

### `main.py` (route/CLI, request-response) — D-15 서브커맨드 (수정)

**Analog:** `main.py::main` (L37-81 기존 argparse — **동일 파일 확장**)

기존 구조: `argparse.ArgumentParser` + `--tickers`/`--env`/`--output-dir`/`--summary-only` + **늦은 import**(L63-64) + UTF-8 reconfigure(L19-24) + 종료코드 반환.

**서브커맨드 추가 (D-15 — main_run.run과 완전 분리):**
```python
sub = parser.add_subparsers(dest="cmd")
p_hist = sub.add_parser("history", help="펀더멘털 트렌드 엑셀 렌더 (DB → fundamentals_history_*.xlsx)")
p_hist.add_argument("--tickers", default="tickers.txt")
p_hist.add_argument("--output-dir", default="output")
args = parser.parse_args()

if args.cmd == "history":
    from stocksig.io.history_render import run_history   # 늦은 import (기존 L63 컨벤션)
    path = run_history(args.tickers, args.output_dir)
else:
    from stocksig.main_run import run                    # 기존 흐름 불변
    path = run(args.tickers, args.env, args.output_dir, summary_only=args.summary_only)
```
- 기존 플래그·기본 동작(서브커맨드 없음 = portfolio 흐름) **하위호환 유지**.
- 서브커맨드 vs 단일 `--history` 플래그는 Claude 재량.

---

### 테스트 파일 (test) — 신규

**Analog A — fetch_fn stub·네트워크0:** `tests/test_metrics_engine.py` (L21-40) + `tests/fixtures/raw_quarters.py`

```python
from fixtures.raw_quarters import raw_row   # 12-tuple 디폴트 인자 팩토리
# compute_matrix(ticker, fetch_fn=<stub>) — 엔진이 fetch_fn 노출(L301) → DB 비결합 주입
matrix = compute_matrix("AAPL", fetch_fn=lambda t: [_to_fetch_row(raw_row(...)) for ...])
```
- `raw_quarters.raw_row(quarter=, value=, source=, ...)` 그대로 재사용. 다종목·다산업 fixture 신규 추가.
- OHLCV는 `fetch_ohlcv_cached` monkeypatch(합성 OHLCV → `resample` 검증).

**Analog B — 워크북 read-back (openpyxl):** `tests/test_sheet_portfolio.py` (L13-24)
```python
import openpyxl
from stocksig.output.writer import make_workbook   # 트렌드는 history_workbook
wb = openpyxl.load_workbook(path)
ws = wb["PER"]
assert ws["F6"].value == "-"                        # 결손 (D-11)
assert ws["F6"].comment.text.startswith("...")      # 사유
assert "▲" in ws["C6"].value                        # YoY (D-08)
assert ws.freeze_panes == "B1"                       # A열만 고정 (D-04)
```
- 합성 DataFrame·fixture만, yfinance 호출 0(test_sheet_portfolio.py 머리주석 L5 정책).

---

## Shared Patterns

### 결손 게이트 (None+NaN 동시) — 신규 정의 금지
**Source:** `src/stocksig/io/fundamentals.py::_is_missing` (L72-78)
**Apply to:** `trend_color.py`·`sheet_metric_matrix.py`·`sheet_snapshot.py` 전 셀 판정
```python
from stocksig.io.fundamentals import _is_missing
# x is None or (isinstance(x, float) and math.isnan(x)) — 단일 게이트
```
시트1 `_nan`(sheet_portfolio.py L91-99)도 동형이나, 엔진 셀은 `_is_missing` 계약. **재사용만**(Don't Hand-Roll).

### 가격 의존 비율·PEG 산식 — 신규 산식 금지
**Source:** `src/stocksig/io/metrics_engine.py` — `price_ratio`(L251-264)·`compute_peg_cell`(L267-296)·`_calendar_quarter_offset`
**Apply to:** `history_render.py`(PER/PBR/PCR/PSR 주입 + 분기별 PEG, D-09/D-10)
```python
cell = price_ratio(matrix[denom_metric][q], price)            # 분모None/≤0·price결손 → 빈값+사유 일관
per_cell  = price_ratio(matrix["EPS_ttm"][q], price)
q_prior   = _calendar_quarter_offset(q, -4)                   # YoY·PEG 전년 EPS
eps_prior = matrix["EPS_ttm"][q_prior].value if q_prior in matrix["EPS_ttm"] else None
peg_cell  = compute_peg_cell(per_cell.value, matrix["EPS_ttm"][q].value, eps_prior)
```

### 셀 코멘트 = 출처/사유 (provenance·결손)
**Source:** `sheet_portfolio.py::_write_fund_cell` (L112-131)
**Apply to:** 전 지표 셀 — `ws.write_comment(row, col, str(cell.note or cell.source))`. provenance는 `[원천]` 시트 중심 + 셀 코멘트 보조(D-12).

### 색 상수 import (로직 미수정)
**Source:** `src/stocksig/compute/color_rules.py` (L16-21)
**Apply to:** `history_workbook.py` Format 베이킹
```python
from stocksig.compute.color_rules import GREEN_100, GREEN_900, RED_100, RED_900
# 함수(decide_*_bucket)는 import/호출 금지 — 상수만.
```

---

## No Analog Found

없음 — 9개 신규/수정 파일 전부 코드베이스에 강한 아날로그 존재(신규 외부 패턴 0).

다만 다음 2개 **신규 순수 로직**은 기존 함수의 직접 복제가 아니라 RESEARCH 권장 알고리즘 기반(아날로그 = 구조·테스트 방식만):
| File | Role | Data Flow | Note |
|------|------|-----------|------|
| `compute/trend_color.py::relative_bucket` | compute | transform | (분기열×산업) 2차원 순위·표본 게이트는 신규. 구조·순수성은 `color_rules.decide_*` 모델. |
| `io/quarter_price.py::quarter_end_prices` | utility | transform | `resample("QE").last()` 분기 경계 매핑은 신규. 입력 소스만 `fetch_ohlcv_cached` 재사용. |

---

## Metadata

**Analog search scope:** `src/stocksig/output/`, `src/stocksig/io/`, `src/stocksig/compute/`, `tests/`, `tests/fixtures/`, 루트 `main.py`
**Files scanned (read):** writer.py, sheet_portfolio.py, sheet_per_ticker.py(헤더), main.py(루트+shim), main_run.py, metrics_engine.py(L240-338), color_rules.py(상수), fundamentals.py(MetricCell/_is_missing), test_metrics_engine.py, test_sheet_portfolio.py, raw_quarters.py
**Pattern extraction date:** 2026-06-22
