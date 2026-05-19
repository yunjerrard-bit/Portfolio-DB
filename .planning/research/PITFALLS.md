# Pitfalls Research

**Domain:** Personal stock-portfolio analytics tool (Python → .xlsx) using Yahoo Finance + EDGAR + DART with statistical (median / σ) signal coloring
**Researched:** 2026-05-19
**Confidence:** HIGH for documented API behaviour (EDGAR, DART, openpyxl), MEDIUM for yfinance landmines (moving target — symptoms confirmed through 2025-Q2 issues, exact fixes unstable)

This file is opinionated and domain-specific. Generic advice ("write tests", "handle errors") is intentionally absent.

---

## CRITICAL ambiguity flagged from PROJECT.md

Before any pitfall list: **the spec contains a contradiction that must be resolved before Phase 2 (data computation).**

PROJECT.md line 29 says: row 3 = 누적 중앙값, row 4 = 누적 표준편차 ("cumulative median / std-dev").
PROJECT.md line 30 then says: each data column also has a separate "일별 중앙값 / 일별 표준편차" column displayed per-date.

**"일별 (daily) median / std-dev" is not a defined quantity.** A median or standard deviation is defined over a *sample*, never a single day. There are three plausible intended meanings:

| Interpretation | What it actually means | Look-ahead bias? | Recommended |
|---|---|---|---|
| (A) Expanding window per row | For row at date D, compute median/σ over all rows ≥ D (i.e. data available *at that date*) | No — uses only past data | YES — this is the only definition consistent with "signal at the time" |
| (B) Trailing rolling window (e.g. 60-day) | Rolling window ending at D | No | Acceptable if window size is fixed in spec |
| (C) Fixed full-period median/σ broadcast to every row | Same number on every row, repeated per date | YES — every row "knows" the full 10-year stats | NO — breaks the signal philosophy |

**Action for Phase 1 (spec finalization):** force the user to pick (A) or (B), and write the chosen definition into PROJECT.md before Phase 2 starts. Default recommendation: **(A) expanding window**, because PROJECT.md line 52's signal philosophy ("정상 변동 범위 대비 어디 있나") implies the σ band should grow as more data accumulates, and because row 3/4 ("누적") already imply expanding.

If the user actually wants (C), the entire signal is look-ahead biased — color on row 6 (most recent date) uses σ computed including itself, which is fine, but color on row 2500 (10 years ago) is colored using σ that includes 10 years of *future* data. That is the single most common methodological mistake in retail backtesting.

---

## Critical Pitfalls

### Pitfall 1: yfinance 429 rate-limit cascade in 2025

**What goes wrong:**
Yahoo tightened anti-bot defences during 2024–2025. Even modest loops (100 tickers × 10y daily) now reliably hit `YFRateLimitError: Too Many Requests. Rate limited. Try after a while` ([issue #2422](https://github.com/ranaroussi/yfinance/issues/2422), [issue #2518](https://github.com/ranaroussi/yfinance/issues/2518) in 2025). Once your IP is flagged, blocks persist for minutes-to-hours, and `curl_cffi` impersonation no longer fully bypasses it as of mid-2025.

**Worse — partial-data silent failure:** rate-limited requests sometimes return *partial* DataFrames (e.g. only the last 200 rows of a 10-year history) without raising. The script then computes EMA/σ on truncated data and produces wrong colors with no error.

**Why it happens:**
- Per-ticker `Ticker().history()` calls in a tight loop trigger per-IP throttling
- yfinance internally retries silently and may stitch together degraded responses
- Yahoo cookie/crumb refresh logic fails under load → empty frames returned as `pd.DataFrame()` instead of exceptions

**How to avoid:**
1. **Use `yf.download(tickers, period="10y", group_by="ticker", threads=False, auto_adjust=True)` batched in chunks of ~20 symbols** rather than per-ticker loops. One HTTP request per chunk.
2. **Pin yfinance version explicitly** in `requirements.txt` (e.g. `yfinance==0.2.65`) — the API surface and rate-limit handling change between minor versions.
3. **Validate row count after every fetch** — if returned rows < ~2300 for a 10-year query, treat as failure and retry with exponential backoff (60s, 180s, 600s).
4. **Disk-cache historicals** keyed by `(ticker, date)`. On re-runs of the same day, re-read from cache rather than refetching.
5. **Use `session=curl_cffi.requests.Session(impersonate="chrome")`** as a passive helper but do not rely on it.
6. **Fail loud per ticker** — if a ticker yields empty/short data after retries, write a placeholder sheet with a "DATA INCOMPLETE" banner; do *not* silently compute σ on 200 rows.

**Warning signs:**
- A few tickers in a run produce sheets with only 2024–2026 data
- σ for some tickers is suspiciously small (because computed over a short window)
- 429s start appearing partway through a run after working fine for the first 30 tickers

**Phase to address:** Phase 2 (data acquisition layer). Must precede Phase 3 (computation), because broken historicals invalidate every downstream calculation.

**Severity:** CRITICAL — this is the #1 cause of wrong colored signals in personal-finance scripts.

---

### Pitfall 2: SEC EDGAR silently 403s without a proper User-Agent

**What goes wrong:**
SEC requires every EDGAR HTTP request to carry a `User-Agent` header in the form `"<Name or Company> <email>"`. Requests with the default `python-requests/X.Y.Z` or `Mozilla/...` UA receive **HTTP 403 Forbidden**, and the IP is then **soft-blocked for ~10 minutes** ([source](https://tldrfiling.com/blog/sec-edgar-api-rate-limits-best-practices), [source](https://blog.finxter.com/solving-response-403-http-forbidden-error-scraping-sec-edgar/)). Worse, some wrappers swallow the 403 and return `None`/empty JSON, so the script proceeds with missing PER/PEG/GPM/OPM.

**Why it happens:**
- The User-Agent rule is policy, not technical — easy to miss because non-EDGAR APIs don't require it
- Many "edgar" PyPI packages do not set a proper UA by default
- 10-minute IP block compounds with retry loops, escalating to longer blocks

**How to avoid:**
1. Centralize the EDGAR client; set `headers={"User-Agent": "Portfolio Tool yunj95@keti.re.kr", "Accept-Encoding": "gzip, deflate", "Host": "data.sec.gov"}` once.
2. Respect the **10 req/sec hard cap**. Use a token-bucket limiter; do not parallelize EDGAR fetches across threads.
3. Cache the **CIK lookup file** (`https://www.sec.gov/files/company_tickers.json`) once per day on disk, do not refetch per ticker.
4. Log raw status codes from every EDGAR call. If a 403 appears, halt all EDGAR traffic for 15 minutes.
5. Do not use `User-Agent: Mozilla/5.0` to "look like a browser" — SEC documents this as a policy violation.

**Warning signs:**
- All US ticker fundamentals are missing in the portfolio sheet after a previously-working run
- HTTP 403 in logs (if you log status codes)
- Run "works fine" for one ticker but fails for the next 99

**Phase to address:** Phase 2 (data acquisition).

**Severity:** CRITICAL — silent fundamentals loss is hard to detect from the xlsx alone.

---

### Pitfall 3: DART corp_code mapping drift + 20,000/day quota

**What goes wrong:**
DART's OpenAPI ([engopendart.fss.or.kr](https://engopendart.fss.or.kr/intro/main.do)) does *not* accept Korean stock tickers (e.g. `005930`) directly for most endpoints — it requires `corp_code`, an 8-digit internal identifier obtained from the bulk `corpCode.xml` ZIP. People hard-code an old mapping, ship the tool, and it silently breaks for newly-listed or renamed companies. Additionally, DART enforces a **per-API-key daily quota** (commonly cited as 20,000 calls/day; verify against the current dashboard at opendart.fss.or.kr because the cap has been adjusted historically). Once the quota is hit, every call returns an error JSON for the rest of the day (KST).

**Why it happens:**
- corp_code lookup is a one-time bootstrap step that gets forgotten on refresh
- `005930.KS` (yfinance format) ≠ `005930` (KRX stock_code) ≠ `00126380` (DART corp_code) — three different identifiers
- Quota is per *key*, not per IP — a single shared key across debug runs depletes fast

**How to avoid:**
1. On every run, check `corpCode.xml` `mtime`. If older than 7 days, redownload. Store as `corp_codes.parquet` with columns `(stock_code, corp_code, corp_name, modify_date)`.
2. Build a `ticker → corp_code` resolver that strips `.KS`/`.KQ` and looks up `stock_code`. Fail loud if not found.
3. **Cache DART responses by `(corp_code, report_period, report_type)` on disk.** Re-runs should make zero DART calls for unchanged periods.
4. Log remaining quota — DART responses include `status` and the dashboard shows usage. Bail out at ~80% to leave headroom for the final portfolio summary fetch.
5. Use a single dedicated API key per machine; never share between dev and "production" runs.

**Warning signs:**
- KR tickers' PER/PEG show blank in the portfolio sheet while US tickers are fine
- Newly added KR ticker (recently IPO'd or renamed) silently fails while older ones work
- DART responses return `{"status": "020", "message": "사용한도를 초과하였습니다"}` (quota exceeded)

**Phase to address:** Phase 2 (data acquisition).

**Severity:** CRITICAL for KR coverage; degraded portfolio sheet otherwise.

---

### Pitfall 4: openpyxl conditional formatting on huge ranges silently degrades

**What goes wrong:**
Each `ConditionalFormattingRule` attached to a range like `D6:D2505` is stored as XML in the worksheet. With ~100 sheets × ~10 colored columns × 4 rules each (< median−1σ, > median+1σ, < median−2σ, > median+2σ), you get **~4000 CF rules** in one workbook. Symptoms:
- File size balloons (50–150 MB)
- Excel takes 30–90 seconds to open the file
- Excel sometimes silently drops rules during the first save if it exceeds internal limits
- openpyxl writes valid XML but Excel's *de facto* per-sheet rule limit (~65k entries, much lower for some renderers) causes silent rule loss

**Worse:** openpyxl's `FormulaRule(formula=["$C6<$E6-$F6"])` is **per-row relative-referenced** but the formula must use `$`-anchoring consistent with the range's top-left cell — getting absolute/relative wrong shifts the comparison row, producing wrong colors that look "almost right".

**Why it happens:**
- Per-cell rules instead of per-range rules
- Misunderstanding of "formula reference origin = top-left of applied range"
- Not knowing Excel re-evaluates all CF on every recalc → death by O(rules × cells)

**How to avoid:**
1. **One rule per column per threshold, applied to the whole column range** — not per cell. e.g. apply `CellIsRule(operator='lessThan', formula=['$median - $sigma'])` once to `D6:D2505`.
2. Use **relative-row + absolute-column references** in formulas: `=$D6<$E$3-$F$3` not `=D6<E3-F3`. The origin row of the formula must equal the first row of the applied range (here, row 6).
3. Reuse `DifferentialStyle` (`dxf`) objects — define 4 colors once, reference everywhere.
4. **Test file open time on Excel before declaring done.** If > 10s, reduce rules.
5. For the 100-sheet workbook, consider applying CF rules **only on the portfolio summary sheet** and using static `Font(color=...)` (no CF) on the per-ticker sheets — color is computed in Python and baked in. Trade-off: colors don't recompute if user edits cells, but it's a personal tool, not an interactive model.

**Warning signs:**
- Saved .xlsx > 50 MB
- Excel "Recovered" dialog on first open (means it dropped invalid CF)
- Colors are off-by-one row in some columns

**Phase to address:** Phase 4 (xlsx output).

**Severity:** CRITICAL — this directly threatens the Core Value (line 9 of PROJECT.md).

---

### Pitfall 5: EMA seed value + business-day vs calendar-day window

**What goes wrong:**
EMA(period=N) needs an initialization. Three common methods:
- (a) Start with `price[0]` itself (industry-standard, what TA-Lib does)
- (b) Start with `SMA(price[0:N])` and only emit values from index N onward
- (c) `pandas.ewm(span=N, adjust=True).mean()` — uses a weighted average of all prior points (different formula entirely)

Picking (c) and labeling it "EMA11" gives values that don't match any chart software the user might cross-check against. Worse, if the data series has NaN values (delisted days, halted sessions, KR market holidays), `ewm` *propagates NaN* differently depending on `adjust=` and `ignore_na=` flags.

Separately: PROJECT.md line 26 says `today() - 4000 day`. 4000 calendar days ≈ 10.95 years ≈ 2750 trading days. EMA192 needs ~192 trading days to stabilize — that's fine — but the spec says "10년치" (10 years). 10 calendar years = 3652 days, 10 trading years ≈ 2520 rows. The user's intent is unclear.

**Why it happens:**
- Multiple EMA conventions exist; users assume "EMA is EMA"
- `pandas.ewm` defaults are not the trader's intuitive EMA
- Confusing calendar days with trading days

**How to avoid:**
1. Document the exact EMA formula in code comments: `EMA_t = α·price_t + (1−α)·EMA_{t−1}, α = 2/(N+1), EMA_0 = price_0`. This matches TradingView and most charting tools.
2. Use `pandas.ewm(span=N, adjust=False, min_periods=N).mean()` — `adjust=False` is the recursive formula; `min_periods=N` blanks the first N rows so the seed effect doesn't dominate.
3. **Forward-fill NaN before EMA**, not after. KR halt days produce gaps; carry-forward the prior close.
4. **Confirm with user**: is "10년" 10 calendar years (use `today() - relativedelta(years=10)`) or ~2500 trading rows? Most likely the former, since `today() - 4000 day` ≈ 10.95 calendar years, suggesting a calendar-year intent with buffer.
5. Drop or warn about tickers with < 192 + 100 trading days of history (EMA192 can't stabilize, σ has too few samples).

**Warning signs:**
- EMA11 on a known ticker doesn't match TradingView's "EMA(11)" plot
- First ~200 rows of EMA192 are all roughly equal to the first close (seed bias)
- EMAs full of NaN on KR tickers due to holidays

**Phase to address:** Phase 3 (computation).

**Severity:** IMPORTANT — wrong EMA produces wrong color signals.

---

### Pitfall 6: "Daily std-dev" / cumulative std-dev look-ahead bias

**What goes wrong:**
See the ambiguity block at the top. If the implementer chooses (C) "single value broadcast to every row", every historical color is biased by future data. The user looks at a 2018 row, sees green, and concludes "this signal would have told me to buy" — but the σ used to compute that green came partly from 2025 data that didn't exist in 2018.

**Why it happens:**
- "Cumulative" is ambiguous in Korean ("누적") — can mean "expanding window" or "totalized once"
- Pandas `.expanding().std()` and `.std()` are both one-liners; easy to pick the wrong one

**How to avoid:**
1. Resolve the ambiguity with the user before writing computation code.
2. Default to **expanding-window** for row-aligned σ: `df['sigma'] = df['close'].expanding(min_periods=30).std()`. Result: row at date D uses only data ≤ D.
3. For row 3/4 ("누적 중앙값/표준편차"), use the *full series* values, but explicitly label them "전체 기간 통계" so the user knows these are full-sample (and therefore biased for any backtest).
4. Add a "as-of date" column showing how many data points the per-row σ was computed from. Sparse early-history sigmas should be flagged or hidden.

**Warning signs:**
- Per-row σ is constant for all rows (means you used the full-series scalar, broadcast)
- Per-row σ is highest at row 6 (most recent) and lowest at row 2505 (oldest) — backwards from expanding-window expectation
- Signals look "uncannily prescient" historically — classic look-ahead tell

**Phase to address:** Phase 1 (spec) + Phase 3 (computation).

**Severity:** CRITICAL — this is the integrity of the entire signal system.

---

### Pitfall 7: KR ticker handling — `.KS`/`.KQ`, delisted, halted, preferred shares

**What goes wrong:**
- Same company, different suffix: `005930.KS` (Samsung common) vs `005935.KS` (Samsung preferred) — different prices, different EMAs
- KOSDAQ ticker with `.KS` (or vice versa) returns empty data silently
- Delisted tickers return historical data up to the delisting date but no recent data → recent rows are NaN → EMA breaks
- Halted/suspended tickers (정리매매, 거래정지) return zero-volume rows or skip days entirely
- yfinance occasionally treats `.KS` symbols differently from US symbols for adjusted close (dividend/split adjustments inconsistent for KR)

**Why it happens:**
- User-entered suffix is the only validation, per PROJECT.md decision
- Yahoo's KR data quality is lower than US data quality
- No equivalent of EDGAR's ticker-to-CIK ground truth for KR (DART corp_code is the closest, but mapping must be maintained)

**How to avoid:**
1. **Validate ticker existence on first fetch.** If 10-year `download()` returns < 100 rows, alert and skip (don't compute garbage).
2. **Cross-check `.KS` vs `.KQ`** against a KRX listing file or DART `corp_code` listing. If user typed `005930.KQ` but DART says KOSPI, warn.
3. For delisted/halted symbols, write a sheet but with a banner "거래정지 또는 상장폐지 — 마지막 거래일: YYYY-MM-DD". Do not include in portfolio σ summary.
4. Document explicitly that preferred shares require their own ticker (`005935.KS`) and are not auto-derived from common.
5. Use `auto_adjust=True` consistently — never mix adjusted and unadjusted in the same workbook.

**Warning signs:**
- Two "Samsung" sheets with different prices (user typo)
- Recent rows blank on a delisted ticker
- KR EMA values do not match Naver Finance's chart

**Phase to address:** Phase 2 (data acquisition).

**Severity:** IMPORTANT for KR portfolio correctness.

---

### Pitfall 8: USD/KRW currency mixing in the portfolio sheet

**What goes wrong:**
The portfolio summary shows "최신 종가" for AAPL ($230) next to 005930.KS (₩72,000). Without explicit currency labeling, the eye conflates magnitudes. Worse, if any aggregation column (e.g. portfolio total value) sums these naively, the result is nonsense. Sorting by "price" mixes scales.

**Why it happens:**
- yfinance returns prices in the native exchange currency without a `currency` flag in the historical frame (you must call `Ticker().info` separately, which is itself rate-limited)
- xlsx number format is set once per column — can't have `$#,##0.00` and `₩#,##0` in the same column

**How to avoid:**
1. Add an explicit **currency column** (`USD` / `KRW`) on the portfolio sheet, right next to ticker.
2. Apply per-cell number format: use openpyxl's `cell.number_format = '"$"#,##0.00'` for USD rows and `'"₩"#,##0'` for KRW rows.
3. Do **not** create any aggregate columns that sum across currencies. If portfolio total value is wanted, add a hard-coded USD/KRW FX rate at workbook generation time and a separate `value_usd` column (note the FX rate snapshot date).
4. Color signals (green/red) are scale-invariant (compare against the ticker's own σ band) — confirm visually that color logic is per-row, not per-column-relative.

**Warning signs:**
- Portfolio sheet sorted by "price" shows all KR tickers first or last (magnitude effect)
- Number format wrong on one currency

**Phase to address:** Phase 4 (xlsx output).

**Severity:** IMPORTANT for usability; LOW for signal correctness (colors per ticker are independent).

---

### Pitfall 9: Color tones that look fine on screen but print badly / lose meaning

**What goes wrong:**
PROJECT.md line 31 explicitly says "강렬하지 않은 톤" (muted tones). Common failure modes:
- Light pastel red + light pastel green look nearly identical when printed grayscale or viewed by red-green colorblind users (~8% of males)
- Light yellow `±2σ` background washes out white-cell ±1σ neighbors when many adjacent cells fire simultaneously
- Default Excel red (`#FF0000`) and green (`#00FF00`) are exactly the "강렬한 톤" the user explicitly forbade
- Dark mode in Excel (Windows 11 default for some users) inverts cell backgrounds and can make light pastels unreadable

**Why it happens:**
- Designers pick colors on monitor without testing print/grayscale/colorblind
- Excel themes can override custom colors if not specified via explicit RGB

**How to avoid:**
1. Use a tested colorblind-safe palette. Suggested: green = `#2E7D32` (text) on `#E8F5E9` (bg for 2σ); red = `#C62828` (text) on `#FFEBEE` (bg for 2σ). These have sufficient luminance contrast in grayscale.
2. **Always specify color via explicit RGB hex**, not theme indices.
3. Run a grayscale screenshot test before declaring Phase 4 done.
4. Consider adding a **subtle icon (▲/▼) or symbol in addition to color** in a separate column — pure-color signaling is an accessibility anti-pattern even for personal tools (the user may use the tool on a phone, projector, or in low-battery dark mode).

**Warning signs:**
- "Looks fine on my monitor but I can't tell green from red on the laptop"
- Print preview is monochrome and signals disappear

**Phase to address:** Phase 4 (xlsx output) + Phase 5 (visual review).

**Severity:** IMPORTANT — directly affects Core Value usability.

---

### Pitfall 10: yfinance non-reproducible historicals

**What goes wrong:**
Run the script today, get a 10-year history. Run it tomorrow without changing tickers, and **some 2-year-old closing prices change by a few cents or fractions of a percent**. Causes:
- Adjusted close is recomputed daily after dividends/splits/corporate actions
- Yahoo backfills delisted-replaced symbol histories
- Source provider (originally ICE, then refit) substitutions for older data

This means σ computed today ≠ σ computed yesterday, even for the same date — and color signals can flip subtly between runs.

**Why it happens:**
- `auto_adjust=True` (now the default) bakes in *current* split/dividend factors into all historical prices
- Yahoo treats history as a derived view, not an immutable record

**How to avoid:**
1. **Snapshot the raw fetched historical data to disk every run** (`historicals_YYYYMMDD.parquet`). Always recompute σ from a snapshot if reproducibility matters.
2. Decide explicitly: `auto_adjust=True` (recommended for technical analysis — splits/dividends adjusted) vs `False` (raw OHLC). Document the choice; don't switch between runs.
3. If reproducibility is critical, consider Stooq or a paid data feed for historicals. For a personal tool, snapshot-on-disk is sufficient.
4. Tolerate small color flips between runs; do not chase a yfinance bug if the same ticker σ changes by 0.5% between two runs — that's a feature of the data source, not a bug.

**Warning signs:**
- Re-running on the same day produces different colors for some cells
- σ in row 4 changes between runs without ticker list changes

**Phase to address:** Phase 2 (data acquisition).

**Severity:** NICE-TO-KNOW (small effect for technical signals); IMPORTANT only if user expects deterministic reproducibility.

---

### Pitfall 11: openpyxl write performance + memory for 100-sheet workbook

**What goes wrong:**
Naive openpyxl: ~100 sheets × ~2500 rows × ~30 columns = 7.5M cells. Each `ws.cell(row, col, value).font = Font(...)` call creates Python objects. Full run can take 5–15 minutes of CPU and 2–4 GB RAM, and the resulting xlsx is 80+ MB.

**Why it happens:**
- Per-cell styling without style reuse
- Default openpyxl is in-memory, not streaming
- Each style object is potentially duplicated unless explicitly shared

**How to avoid:**
1. Use **write-only mode**: `Workbook(write_only=True)` — append rows as tuples, ~5x faster, lower memory. Caveat: write-only doesn't support all features; verify conditional formatting works in your version.
2. **Reuse `Font`, `Fill`, `Border` objects** — define once at module level, reference per cell. openpyxl will deduplicate on save.
3. Write data first (no styling), apply CF rules at the end (per range, not per cell — see Pitfall 4).
4. **Time the run**: if > 3 minutes for 100 tickers, profile with `cProfile`. Hot path is usually `ws.cell()` + style assignment.
5. Consider an alternative for the per-ticker sheets: write CSV, batch-convert with xlsxwriter (faster writer but no CF on existing files and can't edit). Trade-off: lose openpyxl's read-back capability.

**Warning signs:**
- Memory > 2 GB during run
- File > 50 MB
- Excel takes > 10s to open the saved file

**Phase to address:** Phase 4 (xlsx output).

**Severity:** IMPORTANT if the user dislikes slow runs; not a correctness issue.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|---|---|---|---|
| Hard-code US tickers' CIK mapping | Skip EDGAR ticker-lookup call | Breaks on new IPOs / ticker changes; silent missing data | Never — `company_tickers.json` is cheap to fetch daily |
| Cache historicals forever, never invalidate | Fast re-runs | Stale data after splits/dividends; colors stop updating with new days | Acceptable for backtest mode; never for "current signal" mode |
| One ConditionalFormattingRule per cell | "Easy" to reason about per-cell | File size + Excel open time explosion (see Pitfall 4) | Never |
| Skip DART, use only yfinance for KR fundamentals | Simpler code path | yfinance KR fundamentals are notoriously sparse and stale | Acceptable for MVP only; document as known gap |
| Run all yfinance fetches in parallel threads | 10x speedup | Guaranteed 429 within minutes | Never |
| Bake color into static font (no CF) on per-ticker sheets | Smaller file, faster open | User can't tweak σ multiplier interactively | **Recommended** for this project — Excel is output, not model |
| Use `pandas.ewm` defaults for EMA | Two lines of code | Different formula than charting tools; user cross-check fails | Never — always set `adjust=False, min_periods=N` |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|---|---|---|
| Yahoo Finance (yfinance) | Per-ticker `.history()` loops | Batched `yf.download(list, group_by='ticker')`, chunks of ~20 |
| Yahoo Finance | Trust DataFrame returned without validation | Assert min row count post-fetch; retry on degraded responses |
| Yahoo Finance | Use `Ticker.info` for fundamentals | `info` is rate-limited and often stale — use EDGAR/DART first |
| SEC EDGAR | Default `python-requests` UA | Custom UA `"Name email@domain"` — policy requirement |
| SEC EDGAR | Threaded fetches | Single-thread, 10 req/sec hard limit, token bucket |
| SEC EDGAR | Ticker → CIK lookup per ticker | Download `company_tickers.json` once per day |
| DART | Pass `.KS`-suffixed ticker to API | Use 8-digit `corp_code` from `corpCode.xml` |
| DART | Refetch `corpCode.xml` every run | Refresh weekly, cache to parquet |
| DART | Hot-loop calls deplete quota | Cache responses by `(corp_code, period, type)`; bail at 80% quota |
| openpyxl | Per-cell CF rules | Per-range CF rules with correct relative/absolute references |
| openpyxl | Default mode for 7M cells | Write-only mode + style reuse |
| Naver Finance (fallback) | Scrape every run | Only fallback when EDGAR/DART/yfinance all missing the field |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|---|---|---|---|
| Per-ticker yfinance loop | 429s after ~30 tickers, run takes hours | Batched download, ~20-symbol chunks, exponential backoff | At ~30 tickers in default rate-limit budget |
| Per-cell openpyxl writes | 5–15 min runtime, 2+ GB RAM | Write-only mode, style reuse, batched row append | At ~50+ sheets |
| Thousands of CF rules | 60+ second Excel open time, 100+ MB file | Per-range rules; or static font color baked in Python | At ~2000 rules per workbook |
| `pandas.ewm` over NaN-heavy KR data | EMAs full of NaN, signals missing for KR | Forward-fill before EMA; `min_periods=N` | Whenever KR holidays / halts intersect |
| Recomputing σ on full history each row | O(N²) — minutes per ticker | `df.expanding().std()` is O(N), use it | At ~5000-row series |
| Refetching `company_tickers.json` per US ticker | EDGAR 403 block within minutes | Cache file once per day | At ~5 US tickers |

---

## Security / Privacy Mistakes

| Mistake | Risk | Prevention |
|---|---|---|
| Hard-code DART API key in `main.py` | Key exposed if file is shared / committed | Load from `.env` (python-dotenv); `.env` in `.gitignore` |
| Commit `portfolio_YYYYMMDD.xlsx` to git | Leaks personal holdings + watchlist | `.gitignore` the output dir; no portfolio file should ever be committed |
| Use real email in EDGAR User-Agent committed to public repo | Email scraping / spam | Acceptable for personal tool (yunj95@keti.re.kr is research email), but be aware it appears in SEC access logs |
| Cache files contain account-level info | If laptop is compromised, watchlist + holdings exposed | Cache only public market data, never order/position data; this tool is read-only by design |
| Hard-code US/KR FX rate from public source | Stale FX in summary; not a security risk per se | Snapshot FX rate with date at run-time |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---|---|---|
| Color-only signals | Colorblind / grayscale print loses meaning | Add subtle ▲/▼ glyph column |
| Most-recent row at row 6 (descending order per spec) | User expects "latest at bottom" by Excel convention | Honor spec (line 26 explicitly says descending) but freeze rows 1–5 and add header note "최신 = 위" |
| 100 sheets with no index sheet | User scrolls tabs forever | Portfolio sheet (line 32) doubles as TOC — make ticker cell a hyperlink to that ticker's sheet |
| Run silently succeeds despite missing data | User trusts colors that were computed on degraded data | Phase 5 should write a "데이터 품질" sheet listing tickers with < expected row counts or missing fundamentals |
| New file each run with no diff | User can't tell what changed since yesterday | Acceptable per PROJECT.md design; if requested later, add a "changed signals" sheet diffing against prior file |
| Excel "Recovered" dialog on open | Looks broken on first impression | Validate file by reopening with openpyxl post-write and asserting CF rule count |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Historical fetch:** Every ticker returns ≥ ~2300 rows for 10-year window (verify by row-count assertion, not by "no exception thrown")
- [ ] **EDGAR fundamentals:** Every US ticker has non-blank PER/PEG/GPM/OPM, or is explicitly flagged in the data-quality sheet
- [ ] **DART fundamentals:** Every KR ticker resolved to a `corp_code`; failures logged with the unresolved ticker
- [ ] **EMA formula:** Cross-checks against TradingView/Naver chart for one US + one KR ticker (manual visual)
- [ ] **σ definition:** Documented in code AND in PROJECT.md as expanding-window (or rolling-N) — not the look-ahead version
- [ ] **CF rules:** Workbook opens in Excel in < 10 seconds, no "Recovered" dialog
- [ ] **Color signals:** Tested at row 6 (most recent), row ~1250 (mid), row 2500 (oldest) — colors match definition
- [ ] **Currency labeling:** Portfolio sheet shows currency column, per-cell number format correct
- [ ] **Colorblind check:** Grayscale screenshot still distinguishes green/red signals
- [ ] **Rate limiting:** Run 3 times in a row within 10 minutes succeeds (no 429 / 403 cascades — proves caching works)
- [ ] **Secrets:** No DART key in source; `.env` git-ignored
- [ ] **KR halt/delisting:** At least one halted ticker tested — handled gracefully, not silent NaN

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---|---|---|
| yfinance IP-banned mid-run | LOW | Wait 60 min, resume from cache for completed tickers, refetch remaining |
| EDGAR 10-min block | LOW | Pause EDGAR for 15 min, retry; verify UA is set correctly |
| DART quota exhausted | MEDIUM | Wait until KST midnight; do not request second key (policy violation) |
| Excel "Recovered" dialog (CF dropped) | MEDIUM | Reduce CF rules per Pitfall 4; rerun; if persistent, switch to baked-in static color |
| Wrong EMA seed discovered after release | LOW | Recompute; re-run is idempotent (new file each time per design) |
| Look-ahead σ discovered post-ship | HIGH | Recompute all colors with expanding window; explain to user that historical signals shown previously were biased |
| 80MB file too slow to open | MEDIUM | Bake colors into static font on per-ticker sheets; CF only on portfolio sheet |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---|---|---|
| #1 yfinance rate limit / partial data | Phase 2 (data acquisition) | Row-count assertion per ticker; 3-runs-in-10min test |
| #2 EDGAR UA / 403 | Phase 2 | Logs show 200s only; UA header asserted in test |
| #3 DART corp_code / quota | Phase 2 | corp_code refresh timestamp logged; quota usage logged |
| #4 openpyxl CF performance | Phase 4 (xlsx output) | File open < 10s in Excel; rule count < 500/sheet |
| #5 EMA seed / NaN | Phase 3 (computation) | Cross-check vs TradingView for 2 tickers |
| #6 σ look-ahead bias | Phase 1 (spec) + Phase 3 | Per-row σ varies row-to-row, increases over time |
| #7 KR ticker edge cases | Phase 2 | Halted/delisted ticker handled in test set |
| #8 USD/KRW mixing | Phase 4 | Currency column present; per-cell number format applied |
| #9 Color tones | Phase 4 + Phase 5 (review) | Grayscale-mode screenshot test |
| #10 yfinance non-reproducibility | Phase 2 | Disk snapshot per run; documented behaviour |
| #11 openpyxl perf | Phase 4 | Runtime < 3 min, RAM < 1 GB, file < 30 MB |

---

## Sources

- [yfinance issue #2422 — YFRateLimitError in 0.2.57](https://github.com/ranaroussi/yfinance/issues/2422) (2025)
- [yfinance issue #2518 — Still 429 in 0.2.61](https://github.com/ranaroussi/yfinance/issues/2518) (2025)
- [yfinance issue #2125 — Rate limit in loops](https://github.com/ranaroussi/yfinance/issues/2125)
- ["Why yfinance Keeps Getting Blocked, and What to Use Instead" — Medium, Trading Dude](https://medium.com/@trading.dude/why-yfinance-keeps-getting-blocked-and-what-to-use-instead-92d84bb2cc01)
- [SEC EDGAR rate limit & User-Agent — TLDR Filing](https://tldrfiling.com/blog/sec-edgar-api-rate-limits-best-practices)
- [SEC EDGAR 403 fix — Finxter](https://blog.finxter.com/solving-response-403-http-forbidden-error-scraping-sec-edgar/)
- [python-sec PR #6 — UA fix](https://github.com/areed1192/python-sec/pull/6)
- [sec-edgar-downloader issue #77 — 403 Forbidden is Back](https://github.com/jadchaar/sec-edgar-downloader/issues/77)
- [OpenDART Developer Guide (EN)](https://engopendart.fss.or.kr/intro/main.do)
- [OpenDartReader — FinanceData (Korean wrapper, corp_code patterns)](https://github.com/FinanceData/OpenDartReader)
- [openpyxl conditional formatting docs (3.1)](https://openpyxl.readthedocs.io/en/3.1/formatting.html)
- PROJECT.md (this project, 2026-05-19) — spec ambiguity around "일별 중앙값/표준편차"

---
*Pitfalls research for: Python stock-portfolio xlsx tool*
*Researched: 2026-05-19*
