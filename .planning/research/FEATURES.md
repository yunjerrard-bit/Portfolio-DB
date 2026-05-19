# Feature Landscape

**Domain:** Personal stock-analysis xlsx generator (std-deviation-based visual signals)
**Researched:** 2026-05-19
**Confidence:** MEDIUM (mostly synthesized from domain conventions + PROJECT.md mechanics; volume-anomaly convention is HIGH from web verification)

---

## Table Stakes (must have — non-negotiable for this tool to be useful)

| # | Feature | Why Expected | Complexity | Dependencies |
|---|---------|-------------|------------|--------------|
| T1 | **Ticker input via file** (`tickers.txt` or `input.xlsx` A column) | PROJECT.md requirement; user maintains list manually | Low | — |
| T2 | **Per-ticker sheet creation, A1 = ticker** | PROJECT.md hard requirement; A1 is the Yahoo lookup key | Low | T1 |
| T3 | **10-yr daily OHLCV from Yahoo Finance**, descending from row 6 | Core data substrate; nothing works without this | Low | T2 |
| T4 | **EMA11/22/96/192** on close/high/low (12 columns) | Fixed by user; do not change | Low | T3 |
| T5 | **2nd-derived columns**: (close−EMA), (high−EMA), (low−EMA), daily EMA delta | PROJECT.md spec | Low | T4 |
| T6 | **Row 3 = cumulative median, Row 4 = cumulative σ** per data column | Spec; anchors the signal logic | Low | T3–T5 |
| T7 | **Per-row daily median / daily σ companion columns** | Spec; needed for conditional formatting comparisons | Low | T6 |
| T8 | **Conditional formatting bands**: −1σ green text / +1σ red text / ±2σ adds soft background; inside ±1σ = no format | The core value of the entire tool (per PROJECT.md "Core Value") | Medium | T7 |
| T9 | **Sheet 1 portfolio summary**: ticker, last close, day change %, 4 EMA signal colors, PER/PEG/GPM/OPM, volume-anomaly flag | PROJECT.md hard requirement | Medium | T8, T10, T11 |
| T10 | **Fundamentals fetch with source priority**: EDGAR (US) / DART (KR) primary; yfinance + Naver as fallback | PROJECT.md; data-quality decision already made | High | T3 |
| T11 | **Volume anomaly signal** (see definition below) | Spec | Low | T3 |
| T12 | **New file per run**, `portfolio_YYYYMMDD.xlsx` | PROJECT.md key decision | Low | — |
| T13 | **`python main.py` one-line manual run on Windows** | PROJECT.md constraint | Low | — |
| T14 | **Yahoo rate-limit handling**: throttle + retry/backoff | 100 tickers × API calls; production-realistic | Medium | T3 |
| T15 | **KR ticker suffix passthrough** (`.KS`/`.KQ` user-supplied) | PROJECT.md key decision; no auto-detection | Low | T1 |
| T16 | **Missing/delisted ticker handling**: skip with logged warning, continue batch; portfolio row shows "N/A" | A single bad ticker must not fail the whole run | Medium | T1, T9 |
| T17 | **Korean-language headers + log messages** | PROJECT.md constraint | Low | — |

---

## Differentiators (small additions with high ergonomic payoff)

| # | Feature | Value Proposition | Complexity | Dependencies |
|---|---------|-------------------|------------|--------------|
| D1 | **Run-metadata footer/header** on Sheet 1: generated-at timestamp, data-as-of date per ticker, source attribution per fundamental field | Trust + reproducibility; user knows which fields are stale | Low | T9, T10 |
| D2 | **Fundamentals cache** (SQLite or pickle, ~quarterly TTL) | EDGAR/DART filings change quarterly, not daily — re-fetching every run wastes time and triggers rate limits. Industry convention (yfinance-cache uses earnings-date-aware refresh). | Medium | T10 |
| D3 | **Frozen panes + sensible column widths + number formats** (% for change, comma for volume, 2dp for prices) | Without this, the xlsx is unreadable; with it, looks "finished" | Low | T2, T9 |
| D4 | **Sheet 1 ticker cell = hyperlink** to that ticker's sheet | One-click drill-down; trivial via openpyxl | Low | T9 |
| D5 | **Source-attribution column / suffix on fundamentals** (e.g. "PER 18.2 (EDGAR)" vs "PER 18.2 (yf)") | Makes the EDGAR/DART-first decision visible and auditable | Low | T10 |
| D6 | **Per-ticker sheet summary band** (rows 1–5): A1 ticker, B1 last close, C1 change%, D1 EMA signal snapshot — so the sheet is useful even without scrolling | Standard xlsx-tool convention; rows 3–4 already used by median/σ so this fits | Low | T2, T6 |
| D7 | **Graceful EDGAR/DART gap handling**: if primary returns null, automatically fall through to yfinance and tag source | PROJECT.md implies this; making it explicit prevents silent gaps | Medium | T10 |
| D8 | **Console progress** (e.g. `tqdm`): "[42/100] AAPL 처리 중..." | Long runs without feedback feel broken | Low | T13 |
| D9 | **Summary stats on Sheet 1**: count of tickers in ±2σ today (top of sheet) | Tiny addition, big "today's action" signal | Low | T8, T9 |

---

## Volume-Anomaly Signal — Recommended Definition

Industry convention is one of two approaches; recommend the **σ-based** one since it aligns with the project's existing statistical framing:

**Recommended:** `today_volume > rolling_mean_volume(20d) + 2 × rolling_std_volume(20d)` → flag as anomaly.
- Reuses the same median/σ mental model used everywhere else in the workbook.
- 20-day window is the standard "abnormal volume" lookback ([Scanz](https://scanz.com/scanning-for-stocks-with-abnormal-volume/), [Trade-Ideas](https://www.trade-ideas.com/help/filter.html?code=RV)).

**Alternative (simpler):** Relative Volume ratio `today_vol / avg_vol_20d`; flag if ≥ 2.0 (i.e. 200%).
- More common in retail scanners but less consistent with this tool's σ-philosophy.

Sheet 1 surfaces this as a single colored cell (e.g. orange background if ≥2σ above mean, no formatting otherwise). No numeric column needed — keep portfolio sheet readable.

---

## Portfolio Sheet Aggregation Strategy — Recommendation

Two options exist; recommend **Python-written values, not formula links**:

| Approach | Pros | Cons |
|----------|------|------|
| Formula links (`=AAPL!B2`) | Live recompute if user edits sheets | openpyxl formula handling is fragile; cross-sheet refs break on rename; defeats "new file every run" simplicity |
| **Python-written values + conditional formatting on those cells** | Simple, deterministic, matches "new file per run" philosophy; no formula evaluation risk | No live recompute — but user re-runs script anyway |

Recommendation: **write values directly**, apply the same `±1σ/±2σ` conditional-formatting rules at write time against the per-ticker latest median/σ.

---

## Fundamental-Data Refresh Cadence

EDGAR 10-Q/10-K cadence is quarterly; DART (분기/반기/사업보고서) likewise. yfinance fundamentals also refresh per quarter ([yfinance-cache](https://github.com/ValueRaider/yfinance-cache) is earnings-date-aware).

**Recommendation:**
- Price data (close/high/low/volume): always fetch fresh each run.
- Fundamentals (PER/PEG/GPM/OPM): cache locally (SQLite or JSON keyed by ticker), TTL = 7 days OR until next known earnings date. Avoids hammering EDGAR/DART for data that hasn't changed.
- Cache file lives next to script (e.g. `./.cache/fundamentals.sqlite`) — gitignored, regenerable.

Complexity: **Medium**. Without cache, 100 tickers × multiple endpoints = real rate-limit pain.

---

## Per-Sheet Layout Conventions (recommended defaults)

| Element | Convention |
|---------|-----------|
| Frozen pane (per-ticker sheet) | Freeze at row 6 (header rows 1–5 stay visible) and column B (date stays visible) |
| Frozen pane (Sheet 1) | Freeze row 1 (header) |
| Column widths | Auto-size based on content; minimum 10, cap at 18 |
| Date column format | `YYYY-MM-DD` |
| Price columns | `#,##0.00` |
| Volume column | `#,##0` |
| Change % | `0.00%` with red/green via conditional format (separate from σ-bands) |
| Font | Default (don't override — let user's Excel theme apply) |
| Color tones | Soft/desaturated per PROJECT.md ("강렬하지 않은 톤") — use light green `#E2F0D9`, light red `#FBE5D6`, deeper for ±2σ backgrounds |

---

## Error / Missing-Data Handling UX

| Scenario | Behavior |
|----------|----------|
| Delisted / invalid ticker | Log warning, skip sheet creation, portfolio row shows ticker + "조회 실패" in red |
| EDGAR/DART returns no filing (newly listed / foreign) | Fall through to yfinance, tag source as `(yf)` |
| yfinance returns NaN for fundamentals | Show empty cell, do not 0-fill (0 is misleading) |
| Yahoo rate-limit hit mid-batch | Exponential backoff, retry up to 3×, then skip with warning |
| Partial price history (<10yr, e.g. recent IPO) | Use whatever is available, mark per-ticker summary as "데이터 X년" |
| Network failure | Fail entire run with clear error message, do NOT write partial xlsx |

---

## Anti-Features (do NOT build — reinforces PROJECT.md Out of Scope)

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **BUY/SELL text labels / composite score column** | PROJECT.md key decision — color-only visualization is the intent | Color signals on Sheet 1 only |
| **Price prediction / forecasting** | Not in scope; this is a *current-state visualizer* | Show today's σ-position, let user decide |
| **Backtesting framework** | Massive scope creep; not the tool's purpose | If user wants backtests, that's a separate project |
| **Alerts / notifications / email / push** | "수동 실행" is a PROJECT.md decision | User runs script when they want to look |
| **Scheduler / cron / daily-batch automation** | PROJECT.md Out of Scope — explicitly deferred | `python main.py` on demand |
| **GUI / web dashboard / Streamlit** | PROJECT.md: "엑셀 자체가 사용자 인터페이스" | Excel IS the UI |
| **Broker API / auto-trading** | PROJECT.md Out of Scope; risk profile too different | Visual signals only |
| **Dynamic ticker discovery** (auto-pull S&P 500, etc.) | PROJECT.md Out of Scope — personal portfolio is small | User maintains tickers.txt manually |
| **JP/HK/EU markets** | PROJECT.md Out of Scope — EDGAR/DART consistency breaks | US + KR only |
| **In-place xlsx update** (preserve charts/formatting) | PROJECT.md key decision — new file each run | `portfolio_YYYYMMDD.xlsx` |
| **Charts / sparklines embedded in xlsx** | Tempting but openpyxl chart support is limited and brittle; conditional formatting *is* the visualization | Color-coded cells are the chart |
| **Real-time / intraday quotes** | 10-yr daily is the substrate; intraday adds API complexity for no benefit | EOD daily only |
| **Multi-user / shared portfolio** | PROJECT.md: single user (본인) | Local file only |
| **Configuration UI for EMA periods** | PROJECT.md key decision: 11/22/96/192 are fixed | Hardcoded constants |

---

## Feature Dependency Graph

```
T1 (ticker input)
 └→ T2 (per-ticker sheet, A1)
     └→ T3 (Yahoo OHLCV)
         ├→ T4 (EMA) → T5 (deltas) → T6 (cum median/σ) → T7 (daily med/σ) → T8 (cond formatting) ★ Core Value
         ├→ T11 (volume anomaly)
         └→ T14 (rate-limit handling)
     └→ T10 (fundamentals: EDGAR/DART → yf fallback)
         └→ D2 (fundamentals cache)
         └→ D5 (source attribution)
T8 + T10 + T11 → T9 (Sheet 1 portfolio summary)
T9 → D1, D4, D6, D9 (ergonomic polish)
T16 (error handling) spans T3, T10
```

★ = the keystone. T8 is what PROJECT.md calls "Core Value" — if this is wrong/buggy, nothing else matters.

---

## MVP Recommendation (minimal viable workbook)

Build, in order:

1. **T1 → T3**: ticker file in, 10yr OHLCV out, one sheet per ticker with A1=ticker.
2. **T4 → T8**: EMAs, derived columns, median/σ rows, conditional formatting. **Validate the color signals look right** before moving on.
3. **T11 + T16**: volume anomaly + error handling so a bad ticker doesn't tank the run.
4. **T9 + T10**: Sheet 1 portfolio with fundamentals (EDGAR/DART + fallback).
5. **D2, D3, D8**: cache + layout polish + progress bar (ergonomic completion).
6. **D1, D4, D5, D6, D7, D9**: nice-to-haves once core works.

Defer everything in Anti-Features. If user later wants alerts/scheduling, that's a future milestone.

---

## Sources

- [Scanz — Scanning for Stocks With Abnormal Volume](https://scanz.com/scanning-for-stocks-with-abnormal-volume/) — confirms 20d rolling lookback convention
- [Trade-Ideas — Relative Volume Filter](https://www.trade-ideas.com/help/filter.html?code=RV) — relative-volume ratio convention
- [Trade-Ideas — Volume in 1 Minute](https://www.trade-ideas.com/help/filter.html?code=Vol1) — EMA-based volume-spike approach
- [yfinance-cache (ValueRaider)](https://github.com/ValueRaider/yfinance-cache) — earnings-date-aware fundamentals caching pattern
- [yfinance Caching docs](https://ranaroussi.github.io/yfinance/advanced/caching.html) — official caching architecture (tz/cookie/ID caches)
- PROJECT.md (this repo) — authoritative for scope, constraints, key decisions

**Confidence:**
- Volume-anomaly convention: HIGH (multiple corroborating sources)
- Fundamentals caching cadence: HIGH (yfinance-cache + EDGAR filing schedule)
- Layout / UX conventions: MEDIUM (synthesized from openpyxl norms, no single authoritative source)
- Anti-feature list: HIGH (all directly mapped to PROJECT.md Out of Scope)
