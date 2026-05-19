# Research Summary

**Project:** 표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트
**Domain:** Personal stock-analysis xlsx generator (Python CLI, Windows local)
**Researched:** 2026-05-19
**Confidence:** HIGH (stack and architecture), MEDIUM (EDGAR/DART XBRL concept mapping, exact color hex values)

---

## Executive Summary

This tool is a single-user, single-command Python script that ingests a flat list of tickers and produces a fresh `portfolio_YYYYMMDD.xlsx` workbook on every run. The architecture is a classic batch ETL pipeline — Load → Fetch → Compute → Render → Save — where the Fetch phase fans out across up to 4 concurrent threads (Yahoo OHLCV + EDGAR/DART fundamentals) and the Render phase is strictly single-threaded. The entire value of the tool rests on one primitive: **expanding-window median ± 1σ/2σ color signals baked statically into cells at write time**. If that computation or its visual expression is wrong, nothing else in the workbook matters.

The most consequential architecture decision is the library split: **XlsxWriter** (not openpyxl) writes the workbook because static cell-color baking at write time — rather than dynamic Excel conditional formatting — is the explicitly chosen rendering strategy. This eliminates openpyxl's 4,000-CF-rule performance cliff and the associated Excel-open-time explosion. The trade-off — colors do not recompute if the user manually edits cells — is explicitly acceptable: the file is a read-only output artifact, not an interactive model. openpyxl is retained solely for the narrow read path if a user supplies an `input.xlsx` ticker file.

The biggest operational risk is Yahoo Finance rate limiting. At 100 tickers, naive per-ticker `history()` loops reliably produce 429 blocks and — worse — silent partial-history DataFrames that generate statistically wrong σ values with no visible error. The mitigation is mandatory and multi-layered: batched `yf.download()` in 20-symbol chunks, a `curl_cffi` Chrome-impersonating session, a per-source token-bucket throttle, exponential backoff via `tenacity`, a 24-hour on-disk HTTP cache, and post-fetch row-count validation before any computation runs.

---

## Locked Decisions

These questions were flagged by researchers and resolved by the user before roadmapping. They are not open questions — treat them as hard requirements.

| # | Decision | Locked Value | Implication |
|---|----------|--------------|-------------|
| 1 | "일별 중앙값/표준편차" definition | **Expanding window** — computed over all data up to and including that date | Use `df.expanding().median()` / `df.expanding().std()`; never broadcast the full-series scalar |
| 2 | Conditional formatting strategy | **Static color baking** — Python compares value vs σ band and writes font color + background color directly to cells; no dynamic Excel CF rules | Eliminates Pitfall #4 (CF rule explosion); colors do not recompute on user edits — acceptable by design |
| 3 | xlsx write library | **XlsxWriter** (not openpyxl for writing) | ARCHITECTURE.md recommended openpyxl; user overrode to XlsxWriter. openpyxl-specific CF concurrency/write-only concerns are superseded. openpyxl used only for reading `input.xlsx` if supplied. |
| 4 | 10-year data range | **today() minus 4000 calendar days** (~10.95 calendar years / ~2750 trading days) | Compute explicit `start` date: `date.today() - timedelta(days=4000)` |
| 5 | Volume anomaly signal window | **Expanding window ±σ** — same statistical frame as price indicators | `vol_zscore = (volume - volume.expanding().mean()) / volume.expanding().std()`; flag if abs(zscore) > 2 |
| 6 | EDGAR User-Agent email | **yunjerrard@gmail.com** (stored in `.env` as `EDGAR_USER_AGENT_EMAIL`) | Required by SEC policy; centralize in `edgar_client.py`; assert non-empty at startup |
| 7 | DART API key | **User-supplied** (stored in `.env` as `OPENDART_API_KEY`) | Load via `python-dotenv`; assert non-empty at startup before any DART call |

---

## Key Findings

### Stack (locked choices)

| Technology | Version | Role | Why |
|------------|---------|------|-----|
| Python | 3.13.x | Runtime | Full upstream support through Oct 2026; all wheel deps available |
| uv | 0.5+ | Package/venv manager | 10-100x faster than pip; single tool for Python install + venv + deps on Windows |
| yfinance | 0.2.66+ | OHLCV market data | De-facto free standard; supports `.KS`/`.KQ`; must use curl_cffi session |
| curl_cffi | >=0.15, <0.16 | TLS session for yfinance | Required breaking change in yfinance >=0.2.60; Chrome impersonation reduces 429s; 0.14 has CVE-2743 |
| XlsxWriter | 3.2.x | xlsx generation | Write-once, static-color-baking model; Pythonic format API; faster than openpyxl for bulk writes |
| pandas | 2.2.x | DataFrames, EMA, stats | `ewm(span=N, adjust=False)` for EMA; `.expanding()` for cumulative stats; no TA library needed |
| numpy | 2.x | Numerical primitives | pandas 2.2+ supports numpy 2; faster wheels |
| edgartools | 4.x | US (EDGAR) fundamentals | MIT, free, no key, typed XBRL objects; weekly PyPI releases; `set_identity()` for UA |
| OpenDartReader | 0.2.x | KR (DART) fundamentals | Simplest Pythonic wrapper; free API key from opendart.fss.or.kr; fallback to dart-fss if stale |
| tenacity | 9.x | Retry / backoff | Composable decorators; handles YFRateLimitError + httpx.HTTPError + 429/5xx |
| httpx | 0.27+ | Direct REST fallback | For EDGAR/DART endpoints not covered by the primary libraries |
| python-dotenv | 1.0+ | Secret management | Loads `.env` on Windows without shell-profile gymnastics |
| rich / loguru | 13.x / 0.7+ | Progress + logging | Korean text renders correctly on Windows Terminal; per-ticker progress critical at 100 tickers |

**Rejected alternatives (do not revisit):**

- pandas-ta: maintainer warned of archival by July 2026; no NumPy 2 support
- TA-Lib: native C install pain on Windows; overkill for 4 EMAs
- openpyxl as writer: verbose CF API; slower bulk write; designed for read+modify not bulk write
- `requests.Session` passed to yfinance: breaking change in >=0.2.60; rejected by library
- sec-api.io: $55-$239/mo for what edgartools does free

### Features (table stakes — all must ship)

| ID | Feature | Complexity |
|----|---------|-----------|
| T1 | Ticker input via `tickers.txt` or `input.xlsx` col A | Low |
| T2 | Per-ticker sheet, A1 = ticker symbol | Low |
| T3 | 10yr daily OHLCV from Yahoo Finance (today minus 4000 days), descending from row 6 | Low |
| T4 | EMA 11/22/96/192 on close/high/low (12 derived columns) | Low |
| T5 | 2nd-order derived columns: (price minus EMA), daily EMA delta | Low |
| T6 | Row 3 = cumulative expanding-window median per column; Row 4 = cumulative σ | Low |
| T7 | Per-row daily expanding-window median + σ companion columns | Low |
| T8 | Static color baking: value < median-1σ → soft green text; value > median+1σ → soft red text; ±2σ → text + soft background | Medium |
| T9 | Sheet 1 portfolio summary: ticker, last close, day change %, 4 EMA signal colors, PER/PEG/GPM/OPM, volume anomaly | Medium |
| T10 | Fundamentals: EDGAR (US primary) / DART (KR primary) → yfinance fallback; source-tagged | High |
| T11 | Volume anomaly signal: expanding-window zscore; flag if abs(zscore) > 2 | Low |
| T12 | New file per run: `portfolio_YYYYMMDD.xlsx` | Low |
| T13 | `python main.py` one-line Windows execution | Low |
| T14 | Yahoo rate-limit handling: batched download (~20-symbol chunks), throttle, retry, 24h cache | Medium |
| T15 | KR ticker suffix passthrough (`.KS`/`.KQ` user-supplied; no auto-detection) | Low |
| T16 | Bad ticker isolation: skip with warning, portfolio row shows "조회 실패"; run continues | Medium |
| T17 | Korean-language headers and log messages | Low |

**High-value differentiators (build after core works):**

- D1: Run-metadata footer on Sheet 1 (generated-at timestamp, data-as-of per ticker, source attribution per metric)
- D2: Fundamentals cache (SQLite, 7-day TTL) — mandatory for 100-ticker runs to avoid EDGAR/DART rate-limit pain
- D3: Frozen panes + auto-sized columns + number formats (price `#,##0.00`, volume `#,##0`, change `0.00%`)
- D4: Sheet 1 ticker cell = hyperlink to that ticker's sheet
- D5: Source-attribution suffix on each fundamental value, e.g. "PER 18.2 (EDGAR)" vs "(yf)"
- D7: Graceful EDGAR/DART gap handling with automatic source fallthrough
- D8: Console progress bar (rich or tqdm) — critical UX for 100-ticker runs
- D9: Summary stats on Sheet 1 header: count of tickers currently at ±2σ

**Anti-features (do not build):** BUY/SELL labels, price forecasting, backtesting, alerts, scheduler, GUI/web, broker API, dynamic ticker discovery, JP/HK/EU markets, in-place xlsx update, embedded charts, real-time quotes, multi-user.

### Architecture Overview

**Pattern:** Batch ETL pipeline, single-process, ephemeral run. Three clean phases separated by data contracts.

```
tickers.txt
    | ticker_loader + market_classifier
List[Ticker(symbol, market)]
    | runner (ThreadPoolExecutor, max_workers=4)
    +-- per-ticker thread ------------------------------------------+
    |  yahoo_prices [batched ~20, cached 24h, throttled]             |
    |    => prices DataFrame (OHLCV, 4000-day window)               |
    |  edgar_client OR dart_client [cached 7d, throttled]            |
    |    => fundamentals dict (PER/PEG/GPM/OPM + source tag)        |
    |  compute.indicators (EMA 11/22/96/192 x 3 prices)             |
    |  compute.derived (price-EMA, EMA daily delta)                  |
    |  compute.stats (expanding median + stddev per column)          |
    |    => TickerResult dataclass                                   |
    +---------------------------------------------------------------+
List[TickerResult]
    | render (single-threaded, XlsxWriter)
    +-- per-ticker sheet (A1=ticker, rows 3/4=stats, rows 6+=data, colors baked)
    +-- portfolio sheet (Sheet 1: summary row per ticker)
output/portfolio_YYYYMMDD.xlsx
```

**Key architectural boundaries (enforce strictly):**

- fetch / compute: DataFrame + dict in-memory; compute never imports from fetch
- compute / render: `TickerResult` dataclass is the only contract; render does zero math
- runner / pipeline: single `process_ticker(Ticker) -> TickerResult` function signature
- Render is always single-threaded (XlsxWriter is not thread-safe during active write session)

**Recommended project structure:**

```
main.py               # <=50 lines, parse args -> call runner.run(config)
tickers.txt
.env                  # OPENDART_API_KEY, EDGAR_USER_AGENT_EMAIL
pyproject.toml
portfolio/
  config.py
  io/ticker_loader.py, market.py
  fetch/throttle.py, cache.py, yahoo.py, edgar.py, dart.py, naver.py
  compute/indicators.py, stats.py, derived.py
  render/styles.py, ticker_sheet.py, portfolio_sheet.py
.cache/               # http.sqlite + parquet snapshots (gitignored)
output/               # portfolio_YYYYMMDD.xlsx (gitignored)
logs/
```

**Note on ARCHITECTURE.md vs locked decisions:** ARCHITECTURE.md recommended openpyxl with write-only mode. The user locked XlsxWriter instead. Data flow, module boundaries, threading model, and caching strategy from ARCHITECTURE.md remain valid — only the render library and color-application strategy differ. ARCHITECTURE.md's openpyxl-specific CF concurrency concerns are resolved by the static color-baking decision.

### Critical Pitfalls

| # | Pitfall | Severity | Phase | Prevention |
|---|---------|----------|-------|-----------|
| 1 | yfinance 429 cascade + silent partial-history DataFrames | CRITICAL | Phase 2 | Batch `yf.download()` in ~20-symbol chunks; validate row count >=~2300 post-fetch; 24h disk cache; exponential backoff |
| 2 | EDGAR 403 from missing/wrong User-Agent + 10-minute IP block | CRITICAL | Phase 2 | Centralize `User-Agent: "Name email"` header; token-bucket at 8 req/s; cache `company_tickers.json` once/day; log all HTTP status codes |
| 3 | DART corp_code mapping drift + daily quota exhaustion | CRITICAL (KR) | Phase 2 | Refresh `corpCode.xml` if older than 7 days; cache DART responses by (corp_code, period, type); bail at 80% quota; log remaining quota |
| 4 | Look-ahead σ bias (full-series scalar broadcast to every row) | CRITICAL — RESOLVED | Phase 1/3 | Expanding window locked. Use `df.expanding().std()` for per-row σ; row 3/4 = full-series scalar labeled "전체 기간 통계" |
| 5 | EMA seed value + NaN propagation on KR halt days | IMPORTANT | Phase 3 | `pandas.ewm(span=N, adjust=False, min_periods=N).mean()`; forward-fill NaN before EMA; cross-check vs TradingView |

Additional pitfalls to handle by phase:

- **Phase 2:** KR ticker validation (suffix correctness, delisted/halted handling, <100-row result = skip); yfinance non-reproducible historicals (snapshot raw parquet per run)
- **Phase 4:** USD/KRW currency column + per-cell number format on portfolio sheet; color accessibility (explicit RGB hex, grayscale screenshot test)

---

## Implications for Roadmap

### Suggested Phase Structure

**Phase 1 — Foundation + Single-Ticker Vertical Slice**

- Rationale: Prove the core value (color signal) on one ticker end-to-end before scaling fetch infrastructure.
- Delivers: Working `main.py` that reads `tickers.txt`, fetches one ticker's OHLCV, computes all EMAs + expanding stats, writes one correctly colored ticker sheet.
- Features: T1, T2, T3 (single ticker), T4, T5, T6, T7, T8 (static baking on one sheet), T12, T13, T17
- Pitfalls to avoid: #5 (EMA formula correctness), #4 (sigma definition — locked to expanding window)
- Research flag: No additional research needed. All patterns well-documented.
- Milestone gate: Open xlsx, verify color signals at rows 6, ~1250, and ~2500 match the σ formula manually. Cross-check EMA vs TradingView.

**Phase 2 — Data Acquisition Layer (All Sources, N Tickers)**

- Rationale: The fetcher is the highest-risk component. Build it fully before scaling computation.
- Delivers: Robust fetch layer (Yahoo batched, EDGAR, DART, fallback chain) with throttling, caching, retry, error isolation, row-count validation, and fan-out runner.
- Features: T14, T15, T16, T10, D2 (fundamentals cache), D8 (progress bar)
- Pitfalls to avoid: #1 (Yahoo 429), #2 (EDGAR UA + 403), #3 (DART corp_code + quota), KR ticker edge cases, non-reproducible historicals
- Research flag: Needs implementation-time research for EDGAR XBRL concept tag mapping and DART financial statement key mapping (see Open Questions).

**Phase 3 — Computation at Scale + Portfolio Sheet**

- Rationale: With reliable data flowing for all tickers, extend to N tickers and build the Sheet 1 summary.
- Delivers: Full workbook with all per-ticker sheets (colors baked) + Sheet 1 portfolio summary (close, change %, EMA signals, PER/PEG/GPM/OPM, volume anomaly).
- Features: T3 (all tickers), T9, T11
- Pitfalls to avoid: row-count validation before compute; use `df.expanding().std()` (O(N)) not manual rolling (O(N^2))
- Research flag: No additional research needed.

**Phase 4 — Polish + Robustness**

- Rationale: Core value proven; make it production-quality for daily use.
- Delivers: Frozen panes, auto-sized columns, number formats, currency column (USD/KRW), source attribution, run-metadata footer, data-quality summary sheet, hyperlinks.
- Features: D1, D3, D4, D5, D7, D9; currency labeling fix; color accessibility verification
- Pitfalls to avoid: File size < 30 MB, Excel open time < 10s; verify with XlsxWriter Format object reuse
- Research flag: No additional research needed.

### Phase Ordering Rationale

- Phase 1 before Phase 2: Cannot validate color-baking logic without real OHLCV data, but also cannot trust the fetcher before the signal math is known-correct on one ticker. Vertical slice locks the computation contract all downstream phases depend on.
- Phase 2 before Phase 3: At 100 tickers, broken fetchers produce subtly wrong data (partial histories, missing fundamentals) that corrupts computation silently. Fetcher must be provably correct before scaling.
- Phase 3 before Phase 4: Polish on top of broken computation is wasted work.

### Research Flags

- Phase 2 (EDGAR XBRL concept mapping): Needs implementation-time research. See Open Questions.
- Phase 2 (DART financial statement key mapping): Needs implementation-time research. See Open Questions.
- Phases 1, 3, 4: Standard well-documented patterns. No additional research phase needed.

---

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All choices verified against official docs, PyPI, GitHub issues. Version pins confirmed. |
| Features | HIGH | Anti-features and table-stakes directly mapped to PROJECT.md. Volume-anomaly convention confirmed from multiple sources. |
| Architecture | HIGH | Data flow, threading model, caching strategy well-documented. Library swap (openpyxl to XlsxWriter) is the only deviation; implications are well-understood. |
| Pitfalls | HIGH (documented APIs) / MEDIUM (yfinance exact behavior) | EDGAR/DART/openpyxl pitfalls verified from official sources. yfinance rate-limit behavior is a moving target — mitigation strategy is solid but outcome is probabilistic. |

**Overall confidence: HIGH**

---

## Open Implementation-Time Questions

Not open design questions. Implementation details requiring a brief research spike during Phase 2 development.

| Question | Phase | How to Resolve |
|----------|-------|----------------|
| EDGAR XBRL concept tag for EPS TTM: `EarningsPerShareBasic`, `EarningsPerShareDiluted`, or `EarningsPerShareDilutedTwoClassMethod`? Which form/period for TTM? | Phase 2 | Inspect XBRL facts via edgartools for AAPL + MSFT; cross-check vs yfinance EPS value |
| EDGAR XBRL tags for GPM and OPM: `GrossProfit` / `Revenues` or `RevenueFromContractWithCustomerExcludingAssessedTax`? Multiple revenue tags exist across filers. | Phase 2 | Inspect XBRL facts for 3 large-cap tickers; build a prioritized fallback tag list |
| EDGAR PEG computation: EPS growth is not a reported XBRL fact. Which period comparison to use (YoY TTM vs annual)? | Phase 2 | Compute as `PEG = PER / (EPS_TTM / EPS_prior_year_TTM - 1) * 100`; fetch 2 years of EPS facts via edgartools |
| DART financial statement keys: which `account_nm` strings map to gross profit, operating income, revenue for Korean filings? | Phase 2 | Run `OpenDartReader.finstate()` for Samsung (005930.KS) and inspect returned DataFrame; map to a DART_ACCOUNT_MAP constants file |
| Exact soft-tone hex colors: PITFALLS.md suggests green `#2E7D32` on `#E8F5E9`, red `#C62828` on `#FFEBEE`. FEATURES.md suggests `#E2F0D9` / `#FBE5D6`. Which palette passes grayscale contrast? | Phase 4 | Run both palettes through WebAIM contrast checker in grayscale; pick the pair with higher luminance contrast ratio |
| XlsxWriter per-cell Format object performance: does writing ~2.5M colored cells complete in under 3 minutes? | Phase 1 | Benchmark with a synthetic 100-sheet x 2500-row workbook during Phase 1; if slow, cache Format objects by color-combination key |
| OpenDartReader release staleness: library release cadence has been noted as slow. | Phase 2 | Check PyPI release date at project start; if no release in past 12 months, use dart-fss instead |

---

## Sources

### Primary (HIGH confidence)

- yfinance CHANGELOG + issues #2422, #2518, #2496 (github.com/ranaroussi/yfinance) — rate limits, session changes, partial-history failures
- XlsxWriter conditional formatting docs (xlsxwriter.readthedocs.io) — format object API, font/fill per rule
- edgartools GitHub + PyPI (github.com/dgunning/edgartools) — XBRL fact querying, set_identity(), MIT license
- SEC EDGAR API policy (sec.gov/search-filings) — 10 req/s limit, User-Agent requirement
- pandas ewm docs — `adjust=False` recursive EMA formula
- OpenDART developer guide (engopendart.fss.or.kr) — corp_code mapping, daily quota
- OpenDartReader GitHub (github.com/FinanceData/OpenDartReader) — corp_code patterns, API surface

### Secondary (MEDIUM confidence)

- SEC EDGAR rate limits best practices (tldrfiling.com) — 10-minute IP block behavior
- yfinance rate limiting (slingacademy.com) — throttle strategy
- Scanz abnormal volume (scanz.com) — 20-day rolling window convention (superseded by expanding-window lock)
- yfinance-cache (github.com/ValueRaider/yfinance-cache) — fundamentals caching cadence

### Tertiary (context)

- PROJECT.md (this repo, 2026-05-19) — authoritative for all scope, constraint, and key-decision items

---

*Research completed: 2026-05-19*
*Ready for roadmap: yes*
