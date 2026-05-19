# Architecture Research

**Domain:** Personal stock portfolio analysis — Python data pipeline → .xlsx workbook
**Researched:** 2026-05-19
**Confidence:** HIGH (component boundaries, data flow, openpyxl mechanics, EDGAR limits) / MEDIUM (yfinance throttle exact numbers, DART daily quota exact value)

## Standard Architecture

A batch ETL pipeline producing a single artifact: **Load → Fetch → Compute → Render → Format → Save**. Single-process, ephemeral run, no server, no DB. Local on-disk cache for idempotency. Fan-out fetches under a global throttle, then funnel back into a synchronous workbook writer (openpyxl is not thread-safe).

### System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  ENTRY POINT  (main.py — orchestrator)                              │
│  Reads config → builds ticker list → drives pipeline → saves xlsx   │
└────────────┬────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────────┐
│  INPUT LAYER                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │ ticker_loader│  │ config_loader│  │ market_classifier        │  │
│  │ tickers.txt  │  │ .env / yaml  │  │ .KS/.KQ → KR else US     │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└────────────┬────────────────────────────────────────────────────────┘
             │  List[Ticker(symbol, market)]
┌────────────▼────────────────────────────────────────────────────────┐
│  FETCH LAYER  (I/O bound, rate-limited, parallel where safe)        │
│  ┌──────────────┐  ┌──────────────┐  ┌─────────────┐ ┌───────────┐ │
│  │ yahoo_prices │  │ edgar_client │  │ dart_client │ │ naver_fb  │ │
│  │ (OHLCV 10y)  │  │ (US fund.)   │  │ (KR fund.)  │ │ (KR aux.) │ │
│  └──────┬───────┘  └──────┬───────┘  └──────┬──────┘ └─────┬─────┘ │
│         └─────────────────┴────────┬────────┴──────────────┘       │
│                                    │                                │
│                   ┌────────────────▼────────────────┐               │
│                   │  throttle_pool (token-bucket)   │               │
│                   │  per-source rate limiter        │               │
│                   └────────────────┬────────────────┘               │
│                                    │                                │
│                   ┌────────────────▼────────────────┐               │
│                   │  http_cache (file-backed)       │               │
│                   │  Yahoo: 1d TTL / EDGAR,DART: 7d │               │
│                   └─────────────────────────────────┘               │
└────────────┬────────────────────────────────────────────────────────┘
             │  per-ticker {prices_df, fundamentals_dict}
┌────────────▼────────────────────────────────────────────────────────┐
│  COMPUTE LAYER  (pure functions, CPU-bound, no I/O)                 │
│  ┌────────────────────────────────────────────────────────────┐    │
│  │ indicators: EMA(11,22,96,192) on close/high/low            │    │
│  │ derived:    (price - EMA), EMA daily-delta                 │    │
│  │ stats:      rolling/cumulative median + stddev per column  │    │
│  │ signals:    σ-band classifier (only if precomputed cells   │    │
│  │             needed; else done by Excel conditional format) │    │
│  └────────────────────────────────────────────────────────────┘    │
└────────────┬────────────────────────────────────────────────────────┘
             │  per-ticker enriched DataFrame
┌────────────▼────────────────────────────────────────────────────────┐
│  RENDER LAYER  (openpyxl — single-threaded, sequential)             │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ workbook_builder │  │ sheet_per_ticker │  │ portfolio_sheet  │  │
│  │  styles/themes   │  │ writer           │  │ writer (sheet1)  │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────┘  │
│  ┌──────────────────────────────────────────────────────────────┐  │
│  │ conditional_format_layer (±1σ green/red, ±2σ + fill)         │  │
│  └──────────────────────────────────────────────────────────────┘  │
└────────────┬────────────────────────────────────────────────────────┘
             │
┌────────────▼────────────────────────────────────────────────────────┐
│  OUTPUT  →  portfolio_YYYYMMDD.xlsx                                 │
└─────────────────────────────────────────────────────────────────────┘

         ┌─────────────────────────────────────────────────┐
         │  CROSS-CUTTING                                  │
         │  logger (per-ticker progress + final summary)   │
         │  error_isolator (per-ticker try/except)         │
         │  retry/backoff (429-aware exponential)          │
         └─────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `ticker_loader` | Parse `tickers.txt` / xlsx col A, dedupe, validate | plain stdlib + openpyxl read |
| `market_classifier` | `.KS`/`.KQ` → KR market, else US | pure function on string suffix |
| `yahoo_prices` | 10y OHLCV per ticker | `yfinance.Ticker.history(period="10y")` or `yf.download(group_by="ticker")` batch |
| `edgar_client` | US fundamentals (PER, GPM, OPM, PEG) | `requests` against `data.sec.gov/api/xbrl/companyconcept/...` with required User-Agent |
| `dart_client` | KR fundamentals | `OpenDartReader` or direct `requests` to `opendart.fss.or.kr/api/...` |
| `naver_fb` | KR fallback when DART missing fields | scraper or 3rd-party lib (defer; only build if data gaps appear) |
| `throttle_pool` | Per-source token bucket; blocks calls to stay under limits | one `threading.Semaphore`+`time.monotonic` per source |
| `http_cache` | File-backed cache keyed by URL+date | `requests-cache` (sqlite backend) — drop-in for `requests` |
| `indicators`/`stats` | Compute EMA, median, σ over DataFrames | `pandas` `.ewm().mean()`, `.expanding().median()`, `.expanding().std()` |
| `workbook_builder` | Owns the `Workbook` object, named styles | `openpyxl.Workbook()` (normal mode — write_only blocks cond. formatting reuse) |
| `sheet_per_ticker` | Lay out one ticker sheet (A1 = ticker, rows 3/4 = stats, rows 6+ = data desc.) | openpyxl cell writes |
| `portfolio_sheet` | Sheet1 summary: latest close, %chg, EMA signals, fund. indicators | openpyxl with formulas referencing per-ticker sheets |
| `conditional_format_layer` | Add `ColorScaleRule`/`CellIsRule` per data column | `openpyxl.formatting.rule` applied per range |
| `logger` | Korean-language progress + end-of-run failure summary | stdlib `logging` + custom summary table |
| `error_isolator` | Wrap per-ticker pipeline in try/except, record failure, continue | decorator or `for` loop with collected exceptions |

## Recommended Project Structure

Single Python **package** (not single file). 100 tickers × 4 data sources × Excel rendering is too much for one `main.py`. But keep it flat — no `src/` layout, no `domain/infrastructure/` Clean-Architecture cosplay.

```
example/
├── main.py                        # entrypoint: 30-50 lines, just orchestrates
├── tickers.txt                    # user input
├── config.yaml                    # API keys, throttle settings, paths
├── pyproject.toml                 # deps: yfinance, openpyxl, pandas, requests-cache, OpenDartReader, python-dotenv, pyyaml
├── .cache/                        # http_cache sqlite + parquet snapshots (gitignored)
├── output/                        # portfolio_YYYYMMDD.xlsx (gitignored)
├── logs/                          # run logs (gitignored)
└── portfolio/                     # the package
    ├── __init__.py
    ├── config.py                  # load config.yaml, .env
    ├── io/
    │   ├── ticker_loader.py
    │   └── market.py              # market_classifier
    ├── fetch/
    │   ├── throttle.py            # token-bucket / Semaphore wrapper
    │   ├── cache.py               # requests-cache setup
    │   ├── yahoo.py               # yahoo_prices
    │   ├── edgar.py               # edgar_client (incl. UA header)
    │   ├── dart.py                # dart_client
    │   └── naver.py               # optional fallback
    ├── compute/
    │   ├── indicators.py          # EMA
    │   ├── stats.py               # median / stddev
    │   └── derived.py             # price-EMA, EMA-delta columns
    ├── render/
    │   ├── styles.py              # named styles, color tones
    │   ├── ticker_sheet.py
    │   ├── portfolio_sheet.py
    │   └── conditional_format.py
    ├── pipeline.py                # the per-ticker pipeline function (compose fetch→compute)
    └── runner.py                  # orchestration: thread pool, error isolation, progress
```

### Structure Rationale

- **`fetch/` vs `compute/` vs `render/`:** Mirrors the three I/O phases of the pipeline. Each is independently testable: `compute` is pure functions; `fetch` is mockable; `render` takes pre-computed DataFrames.
- **`throttle.py` and `cache.py` in `fetch/`:** They wrap network I/O exclusively — no business meaning outside fetch.
- **No `src/` layer:** Project ships nothing — no library users. Flat is faster to navigate.
- **`config.yaml` not hard-coded:** EDGAR User-Agent (required) and DART API key (required) must live outside code. `.env` is fine for secrets, YAML for non-secret tunables (throttle rates, EMA periods, paths).

## Architectural Patterns

### Pattern 1: Per-Ticker Pipeline + Fan-out Runner

**What:** Define one pure function `process_ticker(ticker) -> TickerResult` that does fetch + compute. The runner fans out N tickers across a thread pool, collects results, then sequentially renders.

**When to use:** Always for this project. Decouples "what to do per ticker" from "how to run them all", and isolates failures naturally.

**Trade-offs:** Slightly more boilerplate than a flat loop, but error isolation and concurrency are basically free.

**Example:**
```python
# portfolio/pipeline.py
def process_ticker(ticker: Ticker) -> TickerResult:
    prices = yahoo.fetch_prices(ticker)         # throttled, cached
    fund   = edgar.fetch(ticker) if ticker.market == "US" else dart.fetch(ticker)
    df     = compute.enrich(prices)             # EMA + derived + stats
    return TickerResult(ticker, df, fund)

# portfolio/runner.py
with ThreadPoolExecutor(max_workers=4) as ex:
    futures = {ex.submit(process_ticker, t): t for t in tickers}
    for fut in as_completed(futures):
        t = futures[fut]
        try: results.append(fut.result()); log.info(f"OK {t.symbol}")
        except Exception as e: failures.append((t, e)); log.warning(f"FAIL {t.symbol}: {e}")

# render phase — single-threaded
wb = build_workbook(results); wb.save(out_path)
```

### Pattern 2: Token-Bucket Throttle per Source

**What:** Each external source gets its own throttle with a known rate. Calls block until a token is available.

**When to use:** Mandatory — Yahoo, EDGAR, DART have *different* limits and a single global throttle would either under-use EDGAR or over-hammer Yahoo.

**Trade-offs:** Adds one synchronization primitive per source. Worth it. Recommended budgets:

| Source | Recommended client-side rate | Reason |
|--------|------------------------------|--------|
| Yahoo Finance (yfinance) | ~1 req/sec per worker, ≤4 workers | yfinance scrapes Yahoo's web endpoints; 429s common in 2025. Conservative pacing avoids IP-level bans. |
| SEC EDGAR | 8 req/sec (below 10/s ceiling) | Official limit is 10/s/IP; staying under leaves headroom and avoids 10-min IP block. Requires `User-Agent: "Name email"`. |
| DART (OpenDART) | 1-2 req/sec | Daily quota exists per key (commonly cited ~20,000/day, verify in current docs). Daily cap matters more than burst rate. |

**Example:**
```python
class RateLimiter:
    def __init__(self, per_sec: float):
        self.interval = 1.0 / per_sec
        self.lock = threading.Lock()
        self.next_t = 0.0
    def acquire(self):
        with self.lock:
            now = time.monotonic()
            wait = max(0.0, self.next_t - now)
            self.next_t = max(now, self.next_t) + self.interval
        if wait: time.sleep(wait)
```

### Pattern 3: File-Backed HTTP Cache with Tiered TTL

**What:** All HTTP responses go through `requests-cache` (sqlite). Different sources get different TTLs.

**When to use:** Mandatory. Re-running the script same-day for an Excel tweak should not re-hit Yahoo 100 times.

**Trade-offs:** Cache invalidation is the standard "two hard things" problem. Mitigation: short TTLs + cache-key includes UTC date for Yahoo intraday safety.

**TTL recommendation:**
- **Yahoo OHLCV:** 12-24h. Daily candles only change once after market close.
- **EDGAR XBRL:** 7d. 10-Q/10-K filings are quarterly — caching a week is conservative.
- **DART:** 7d. Same quarterly cadence.
- **Cache bypass flag:** `--no-cache` CLI arg for forced refresh.

### Pattern 4: Two-Pass Render (Build Then Format)

**What:** First pass writes all cell values across all sheets. Second pass applies conditional formatting rules per data column.

**When to use:** With openpyxl's standard mode (not `write_only`). `write_only` is faster (60MB vs 500MB, 25s vs 45s) but layering conditional formatting onto write_only worksheets is fiddly; for ~100 sheets the standard mode is fine.

**Trade-offs:** Memory ~500MB peak for 100 sheets × few thousand rows. Acceptable on modern Windows desktops. If memory becomes an issue, switch to write_only and pre-compute the signal color into a value column instead of using conditional formatting.

## Data Flow

### Request Flow (per-ticker pipeline)

```
tickers.txt
    ↓ ticker_loader
List[Ticker]
    ↓ runner.fan_out
┌───────────── per-ticker thread ─────────────┐
│  yahoo_prices ──→ [http_cache + throttle]   │
│       ↓                                      │
│   prices DataFrame (date, O/H/L/C/V)        │
│       ↓                                      │
│  edgar OR dart ──→ [http_cache + throttle]  │
│       ↓                                      │
│   fundamentals dict                          │
│       ↓                                      │
│  compute.indicators (EMA × 3 price types)   │
│       ↓                                      │
│  compute.derived (Δ vs EMA, EMA day-delta)  │
│       ↓                                      │
│  compute.stats (cum. median + σ per column) │
│       ↓                                      │
│   TickerResult                               │
└──────────────────────────────────────────────┘
    ↓ runner collects
List[TickerResult]
    ↓ render (single-threaded)
workbook
    ↓ workbook.save()
output/portfolio_YYYYMMDD.xlsx
```

### Key Data Flows

1. **Price flow (volume-heavy):** Yahoo → DataFrame (descending date) → 6th row onward of ticker sheet.
2. **Fundamentals flow (small):** EDGAR/DART → dict[metric → value] → portfolio sheet columns (PER/PEG/GPM/OPM) + (optionally) ticker-sheet header area.
3. **Stats flow (computed):** prices+EMAs → expanding median/σ → row 3 and row 4 of ticker sheet + per-day median/σ companion columns.
4. **Signal flow:** Conditional formatting rules reference each column's row-3 (median) and row-4 (σ) cells via formula — no signal value precomputed, Excel evaluates the rule at open time. This keeps logic where user can inspect it.
5. **Summary flow:** Portfolio sheet pulls latest values from each ticker sheet via cross-sheet formulas (`='AAPL'!E6` style), so the summary auto-updates if user manually edits any sheet.

## Build Order (Phase Dependency Implications)

Listed in the order phases should unblock each other. Each row notes the minimum prior work.

| Build order | Component | Unblocks | Why this order |
|-------------|-----------|----------|----------------|
| 1 | `config`, `ticker_loader`, `market_classifier` | everything | Smallest, pure stdlib, no external risk |
| 2 | `throttle` + `cache` skeletons | all fetchers | Every fetcher will need them — build infra first or rate-limit pain hits 4× later |
| 3 | `yahoo_prices` (single-ticker) | compute layer | Compute can't be exercised without real price shape |
| 4 | `compute.indicators` + `stats` + `derived` | render layer | Render needs the exact DataFrame shape Compute produces |
| 5 | `render.ticker_sheet` (one ticker end-to-end) | proves vertical slice | First milestone-worthy artifact: 1 sheet for 1 ticker with EMA + σ + conditional formatting |
| 6 | `render.conditional_format` | meets Core Value | Per PROJECT.md Core Value: ±σ color signal is *the* must-have |
| 7 | `runner` (fan-out + error isolation) | scaling to 100 tickers | Up to this point, single-ticker loops are fine for dev |
| 8 | `edgar_client` + `dart_client` | portfolio sheet fundamentals | Fundamentals are summary-sheet inputs only; can ship MVP without them and add |
| 9 | `render.portfolio_sheet` (sheet1 summary) | full deliverable | Requires all per-ticker sheets to exist for cross-sheet refs |
| 10 | `naver_fb` fallback | data completeness polish | Only needed once gaps in DART/EDGAR are observed in real runs |

**Roadmap implication:** The Core Value (Sheet1 portfolio summary with correct σ-based color signals) requires steps 1-7 + 9. Step 8 (fundamentals) is needed for the summary's PER/PEG/GPM/OPM columns but **not** for the σ-signal Core Value. Suggests a Phase ordering: **(P1) Foundation+yahoo+compute+single ticker sheet → (P2) Conditional formatting + fan-out to N tickers → (P3) Portfolio summary sheet (cross-refs) → (P4) Fundamentals (EDGAR/DART) → (P5) Polish (naver fallback, log summaries, perf).**

## Concurrency Model Recommendation

**Recommendation: `ThreadPoolExecutor` with `max_workers=4`, per-source throttling.**

Rationale:

- **Asyncio rejected:** `yfinance` is synchronous and uses `requests` internally. Wrapping it in `asyncio.to_thread` gains nothing over a thread pool and adds cognitive overhead. `OpenDartReader` and most EDGAR helpers are also sync.
- **Multiprocessing rejected:** Workload is I/O-bound (HTTP), not CPU-bound. EMA on 2500 rows × 100 tickers is sub-second in pandas. Process overhead + IPC for DataFrames > benefit.
- **Serial rejected:** 100 tickers × (~3s Yahoo + ~1s EDGAR/DART) ≈ 6-7 min serial. Threading at 4 workers brings this to ~2 min — meaningful UX win for a tool run multiple times per week.
- **Why 4 workers, not 16:** Yahoo Finance is the binding constraint. yfinance has been actively tightening rate limits through 2024-2025; users report 429s at modest concurrency. 4 workers × 1 req/sec ≈ 4 req/sec to Yahoo — well under EDGAR's 10/s ceiling and a reasonable middle for Yahoo. Make `max_workers` configurable so user can dial down if 429s appear.
- **Render layer stays single-threaded.** `openpyxl` is not thread-safe; concurrent writes to one Workbook corrupt the file. Render after all fetch+compute is done.

**Error isolation:** Each `process_ticker` future is wrapped in try/except inside `as_completed` loop. Failed tickers are collected with their exception; the run proceeds and the final log prints a "Failures (3/100)" table at the end. The Excel file is produced with whatever tickers succeeded.

**Retry strategy:** Inside each fetcher: exponential backoff on 429/5xx (`1s → 2s → 4s → 8s`, max 4 attempts). After that, the ticker is marked failed and skipped — do not block the whole run on one stubborn endpoint.

## Caching Strategy (Explicit)

Caching is **mandatory**, not optional. Reasoning:

| Source | Cache? | TTL | Why |
|--------|--------|-----|-----|
| Yahoo OHLCV | YES | 24h (key: ticker + UTC date) | Daily candles immutable after close; re-running same day for Excel tweaks must not re-hit Yahoo. Also the single biggest 429 risk. |
| EDGAR XBRL | YES | 7 days | Filings are quarterly — week TTL is conservative and slashes API load. EDGAR explicitly recommends caching. |
| DART | YES | 7 days | Same quarterly cadence + DART has a daily quota per key, caching protects that quota. |
| Naver fallback | YES | 24h | Same reasoning as Yahoo. |

Implementation: `requests-cache` with sqlite backend at `.cache/http.sqlite`. yfinance internally uses `requests`, so installing a `CachedSession` and passing it via `yf.Ticker(..., session=session)` (supported) captures Yahoo too. CLI flag `--no-cache` for forced refresh; `--clear-cache` to nuke.

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 10-100 tickers (current) | Current design as specified. Single-process, threaded fetch, normal openpyxl mode. |
| 100-500 tickers | (a) Switch openpyxl to `write_only` mode + precompute signal colors instead of conditional formatting. (b) Persist computed DataFrames as parquet in `.cache/` keyed by ticker+date, so re-runs only render. |
| 500+ tickers | Not a target. Would imply moving to a real DB (DuckDB/SQLite parquet) and decoupling fetch from render entirely. Out of scope. |

### Scaling Priorities (what breaks first)

1. **First bottleneck: Yahoo Finance 429.** Long before openpyxl performance matters. Mitigation: lower `max_workers`, lengthen throttle interval, lean harder on cache.
2. **Second bottleneck: openpyxl memory on render.** Around 200+ sheets the 500MB working set becomes uncomfortable on 8GB machines. Mitigation: `write_only` mode (60MB).
3. **Third bottleneck: Excel open time.** A workbook with 500 sheets × cross-sheet formulas × conditional formatting can take 30+ seconds to open. Mitigation: precompute everything as values, drop cross-sheet formulas, drop conditional formatting in favor of pre-rendered cell fills.

## Anti-Patterns

### Anti-Pattern 1: Stuffing fetch + compute + render into one loop

**What people do:** `for ticker in tickers: fetch(); compute(); write_sheet()` all in one go.
**Why it's wrong:** Mixes thread-safe pure code with thread-unsafe openpyxl; one fetch failure halfway through can corrupt the workbook; can't easily retry only the render step.
**Do this instead:** Three-phase pipeline. All fetches + computes finish into `List[TickerResult]`, then render runs once over the list.

### Anti-Pattern 2: Calling yfinance without a session or cache

**What people do:** `yf.Ticker("AAPL").history(period="10y")` in a hot loop.
**Why it's wrong:** Every call is a fresh HTTP session, no cache, no rate limit awareness. Hits 429 fast. Re-running for a render bug re-downloads everything.
**Do this instead:** One `CachedSession` (requests-cache) passed to every `yf.Ticker(symbol, session=session)`, gated by a `RateLimiter`.

### Anti-Pattern 3: Missing EDGAR User-Agent

**What people do:** Hit `data.sec.gov` without a `User-Agent: "Name email@x"` header.
**Why it's wrong:** SEC returns 403 immediately and may block the IP. Most common cause of EDGAR failures.
**Do this instead:** Centralize the User-Agent in `config.yaml`; `edgar_client` refuses to start if it's missing.

### Anti-Pattern 4: Computing σ-signal in Python and writing only the color

**What people do:** Compute "this cell is below median - 1σ" in pandas and apply a static fill to that cell.
**Why it's wrong:** User edits to the cell (e.g. manual price override) no longer re-color. Loses the spreadsheet's value as a live tool.
**Do this instead:** Write the median (row 3) and σ (row 4) as cells, then attach a `CellIsRule` / formula-based `FormatRule` that references those cells. Excel re-evaluates on edit.

### Anti-Pattern 5: One God-`main.py`

**What people do:** 1500-line `main.py` with everything inline.
**Why it's wrong:** No unit test surface, can't reuse fetchers in a REPL, every change risks breaking the whole pipeline.
**Do this instead:** Package layout above; `main.py` stays under 50 lines (parse args → call `runner.run(config)`).

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Yahoo Finance | `yfinance` library + `requests-cache` session + custom `RateLimiter` | No API key. 2025 rate limits tightened; expect 429s at modest concurrency. Consider `yf.download(tickers, group_by="ticker")` for batched OHLCV in one HTTP call as an optimization. |
| SEC EDGAR | Direct `requests` to `https://data.sec.gov/api/xbrl/companyconcept/...` + 10 req/s limit + required `User-Agent: "Name email"` | No API key. Failure mode: 403 if UA missing, 429 → 10-min IP block if rate exceeded. Bulk ZIP downloads exist for >1000 companies; not needed here. |
| DART (OpenDART) | API key (free, register at opendart.fss.or.kr) + `OpenDartReader` or direct `requests` | Daily quota per key (verify current value in docs — historically cited around 20,000/day, MEDIUM confidence). Cache aggressively. |
| Naver Finance | Scrape (no public API) — defer until DART gap proven | Fragile; only build if user reports missing KR fundamentals. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `fetch` ↔ `compute` | DataFrame + dict (in-memory, no serialization) | Compute must not import from `fetch` except for type hints |
| `compute` ↔ `render` | `TickerResult` dataclass | Render must not perform any computation beyond cell formatting |
| `runner` ↔ `pipeline` | `process_ticker(Ticker) -> TickerResult` function | Single function signature is the contract; pool runs N copies |
| `throttle` ↔ all fetchers | Function decorator or context manager | Throttle has no business logic; pure rate gate |

## Logging Strategy

- **Library:** stdlib `logging`, single logger configured in `main.py`.
- **Output:** Console (Korean messages per PROJECT.md) + `logs/run_YYYYMMDD_HHMMSS.log` file handler.
- **Per-ticker progress:** `INFO`-level line as each ticker completes: `[12/100] OK AAPL  (3.1s, cache=hit)`. Failures at `WARNING`: `[13/100] FAIL 005930.KS  (DART 503)`.
- **End-of-run summary block:** Always printed last, even on partial failure:
  ```
  ━━━ 실행 완료 ━━━
  성공: 97  실패: 3
  실패 종목:
    005930.KS  — DART 503 (3회 재시도)
    NVDA       — Yahoo 429 (할당량 소진)
    BRK-B      — EDGAR CIK 매핑 실패
  출력 파일: output/portfolio_20260519.xlsx  (47 MB, 100 시트)
  소요시간: 1m 52s
  ```
- **No DEBUG by default;** `--verbose` flag flips fetch-layer logging to DEBUG (URLs, cache hits/misses, retry attempts).
- **Progress bar optional:** `tqdm` over `as_completed` is one extra import and dramatically improves UX for 100-ticker runs. Recommended.

## Sources

- [yfinance rate limiting and 429 issues (2025)](https://www.slingacademy.com/article/rate-limiting-and-api-best-practices-for-yfinance/) — MEDIUM
- [yfinance new rate-limiting GitHub issue #2128](https://github.com/ranaroussi/yfinance/issues/2128) — HIGH (project maintainers)
- [SEC EDGAR API rate limit and User-Agent requirement](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data) — HIGH (official SEC)
- [SEC EDGAR API best practices: 10 req/s, UA header](https://tldrfiling.com/blog/sec-edgar-api-rate-limits-best-practices) — MEDIUM
- [openpyxl Optimised Modes (write_only)](https://openpyxl.readthedocs.io/en/stable/optimized.html) — HIGH (official docs)
- [openpyxl conditional formatting + write_only discussion](https://groups.google.com/g/openpyxl-users/c/fvGd5tZyat8) — MEDIUM
- [OPENDART Open API portal](https://opendart.fss.or.kr/intro/main.do) — HIGH for existence, MEDIUM for exact daily-quota value (verify in dev portal at runtime)
- [OpenDartReader Python wrapper](https://github.com/FinanceData/OpenDartReader) — HIGH

---
*Architecture research for: Python data pipeline → xlsx workbook for personal stock portfolio*
*Researched: 2026-05-19*
