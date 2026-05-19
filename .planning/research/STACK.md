# Stack Research

**Domain:** Personal stock portfolio analyzer (Python CLI, Windows local, xlsx output)
**Researched:** 2026-05-19
**Confidence:** HIGH (core choices verified against official docs and current GitHub state)

## Executive Recommendation (one-liner)

**Python 3.13 + uv + yfinance 0.2.66+ (with curl_cffi session) + edgartools + OpenDartReader + XlsxWriter + pandas (ewm for EMA) + tenacity.** XlsxWriter is the load-bearing decision — it is the only mainstream library that cleanly supports the exact "font color + cell fill change at ±1σ/±2σ" pattern with a Pythonic API.

---

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.13.x (3.13.12+) | Runtime | 3.13 has full upstream support through Oct 2026, security through 2029. 3.12 is closer to EOL. Avoid 3.14 for now — pandas-ta-classic / yfinance / curl_cffi wheels are still catching up. |
| uv | 0.5+ (latest) | Dependency + venv + Python version manager | 10–100x faster than pip, 10x faster than Poetry. Single tool for `uv python install`, `uv venv`, `uv add`, `uv lock`, `uv run`. Windows-native, no compilation needed for this stack. Replaces pip + virtualenv + pyenv + Poetry. |
| yfinance | 0.2.66+ | Yahoo Finance OHLCV market data | De-facto standard for free historical OHLCV. Free, no API key, supports US tickers and `.KS`/`.KQ` suffixes natively. Caveats handled in `PITFALLS.md`. |
| curl_cffi | ≥0.15, <0.16 | TLS-fingerprinting HTTP session for yfinance | **Required by yfinance ≥0.2.60** (breaking change — old `requests.Session` no longer accepted). Impersonates Chrome TLS to reduce Yahoo blocking. Pin ≥0.15 (CVE-2743 in 0.14). |
| edgartools | 4.x (latest on PyPI) | SEC EDGAR US fundamentals | Official-quality, MIT-licensed, free, no API key. Returns typed Python objects + DataFrames from XBRL facts (income statement, balance sheet → derive PER/PEG/GPM/OPM). Far better DX than raw `data.sec.gov` JSON. |
| OpenDartReader | 0.2.x (latest) | Korean DART fundamentals | Simplest API over OpenDART. Requires free API key from `opendart.fss.or.kr` (env var `OPENDART_API_KEY`). Stable surface area, even if release cadence is slow — see fallback below. |
| XlsxWriter | 3.2.x | xlsx generation with conditional formatting | **The critical choice.** Native `conditional_format()` with `font_color` + `bg_color` per rule + `iconSet` support. Mature, single-purpose, Pythonic API. See "Critical Decision" below. |
| pandas | 2.2.x (or 3.0.x if released stable) | DataFrame + EMA + median + std | `df.ewm(span=N, adjust=False).mean()` is the canonical financial EMA (matches TradingView). No external TA library needed for our 4 EMAs. Includes `.expanding().median()` / `.std()` for cumulative row-3/row-4. |
| numpy | 2.x | Numerical primitives | pandas 2.2+ supports numpy 2. Faster, smaller wheels, current. |
| tenacity | 9.x | Retry / backoff for Yahoo + EDGAR + DART | Industry-standard Python retry decorator. Composable: `stop_after_attempt + wait_exponential + wait_random + retry_if_exception_type(YFRateLimitError)`. |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| httpx | 0.27+ | HTTP client for EDGAR raw fallback + DART | When edgartools/OpenDartReader miss a metric and we need direct REST calls. HTTP/2, timeouts, async-capable. Prefer over `requests` for new code. |
| python-dotenv | 1.0+ | Load `OPENDART_API_KEY` from `.env` | Keep API keys out of source. Windows-friendly (no shell-profile gymnastics). |
| pydantic | 2.x | Optional: validate ticker input + config schema | If we add a `config.toml`/`config.yaml` for EMA periods or thresholds. Defer until Phase 2+. |
| rich | 13.x | Pretty CLI progress bars + colored logs | 100 tickers × multiple API calls — progress visibility matters. Korean text renders correctly on Windows Terminal. |
| loguru | 0.7+ | Structured logging | Drop-in replacement for stdlib `logging`, single-call configuration, file rotation. Optional but cuts setup boilerplate. |
| pytest | 8.x | Tests | Standard. Mock yfinance/EDGAR/DART responses with `pytest-vcr` or `responses`. |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| ruff | Lint + format | Replaces flake8 + isort + black. Configure via `[tool.ruff]` in `pyproject.toml`. |
| mypy or ty | Type checking | Optional but recommended given financial-data correctness needs. `ty` (Astral) is faster but pre-1.0; mypy is the safe pick. |
| pre-commit | Git hook runner | Optional for a solo project but cheap insurance against committing unformatted code. |

---

## Critical Decision: XlsxWriter vs openpyxl

The portfolio's **core value proposition** is "median ± 1σ/2σ color signals." The chosen library must support:

1. Conditional rule on a cell range with custom formula (`= A6 < $median - $stddev`)
2. **Both font color change AND cell background fill change** per rule
3. Multiple stacked rules per range (1σ green text, 2σ green text + green fill, 1σ red text, 2σ red text + red fill = 4 rules per data column)
4. Writing ~100 sheets × thousands of rows performantly

| Capability | XlsxWriter | openpyxl | Winner |
|---|---|---|---|
| Conditional formatting API ergonomics | Single `worksheet.conditional_format(range, {'type':'formula', 'criteria': '...', 'format': fmt})` | Multi-class: `Rule`, `DifferentialStyle`, `Font`, `PatternFill`, `ConditionalFormattingList` — verbose | **XlsxWriter** |
| Font color + cell fill in same rule | Native via `Format` object (one place) | Requires `DifferentialStyle(font=Font(color=...), fill=PatternFill(...))` | **XlsxWriter** |
| Custom formula rules | First-class `'type': 'formula'` | First-class `FormulaRule` | Tie |
| Icon sets (for volume anomaly cell signals) | Built-in (`3_traffic_lights`, `3_arrows`, etc.) | Possible but more code | **XlsxWriter** |
| Write performance (100 sheets) | Faster (write-once design, `constant_memory` mode available) | Slower, especially on writes | **XlsxWriter** |
| Read/modify existing files | NOT supported (write-only) | Supported | openpyxl |
| Charts | Comprehensive native chart support | Supported but quirkier | **XlsxWriter** |

**Verdict: XlsxWriter.** PROJECT.md "Out of Scope" already excludes in-place editing of existing xlsx ("매번 새 파일 생성"), which is the *only* scenario where openpyxl wins. XlsxWriter's write-only model aligns perfectly with the "fresh `portfolio_YYYYMMDD.xlsx` each run" decision. Confidence: HIGH.

(If we ever need to read user-edited input files like `input.xlsx` Sheet1!A:A, use `openpyxl` *only* for that narrow read path, or simply require `tickers.txt` — text input is even simpler and avoids the dependency split.)

---

## Critical Decision: EMA computation — pandas.ewm vs pandas-ta vs TA-Lib

| Option | Verdict |
|---|---|
| **pandas `.ewm(span=N, adjust=False).mean()`** | **CHOSEN.** Native, zero extra deps, exact match to TradingView/standard financial EMA formula `EMA_t = α·P_t + (1-α)·EMA_{t-1}` with `α = 2/(span+1)`. We only need 4 EMA periods × 3 price series — trivial. |
| pandas-ta | **REJECTED.** Maintainer announced: unless additional support arrives by **July 2026**, project will be archived. Does not natively support NumPy 2 (must use `pandas-ta-openbb` fork). Adds a fragile dependency for a one-line builtin. |
| TA-Lib | **REJECTED.** Requires native C library install on Windows (vcpkg / prebuilt wheel hunting). Massive overkill for 4 EMAs. Justifiable only if we later need exotic indicators (Ichimoku, Wilder's, etc.). |

Cumulative median/std for rows 3 and 4 (per requirement): `series.expanding().median()` and `series.expanding().std()`. Native pandas. Confidence: HIGH.

---

## Critical Decision: Yahoo Finance rate-limit strategy

yfinance is **fragile by design** — it scrapes unofficial Yahoo endpoints. As of 2026, rate limiting is a known, recurring issue (GitHub Discussion #2431, Issue #2422). Strategy:

1. **Use the curl_cffi session** that yfinance ≥0.2.60 requires. It impersonates Chrome TLS fingerprints, which materially reduces blocks. Pass `session=curl_cffi.requests.Session(impersonate="chrome")` to `yf.Ticker` and `yf.download`.
2. **Batch via `yf.download(tickers=[...], period='10y', group_by='ticker', threads=False)`** for the bulk OHLCV pull rather than one `yf.Ticker(...).history()` per ticker. Fewer HTTP roundtrips → fewer rate-limit hits.
3. **Cap concurrency at `threads=False`** (sequential) or a small `threads=2` for 100-ticker batches. Yahoo throttles aggressive parallelism.
4. **Wrap every external call in `tenacity`:**
   ```python
   @retry(
       stop=stop_after_attempt(5),
       wait=wait_exponential(multiplier=2, min=2, max=60) + wait_random(0, 2),
       retry=retry_if_exception_type((YFRateLimitError, httpx.HTTPError)),
       reraise=True,
   )
   ```
5. **Inter-call sleep** between EDGAR/DART calls (EDGAR mandates ≤10 req/s and a `User-Agent: Name email@domain` header; DART has a documented daily quota).
6. **Optional cache** — `requests-cache` or a simple pickle on the OHLCV pull keyed by date — lets reruns within a day skip network entirely. Defer to Phase 2 if needed.

Confidence: HIGH on strategy. Rate-limit *outcome* is inherently uncertain because Yahoo can change behavior any day — this is documented in `PITFALLS.md`.

---

## Critical Decision: EDGAR client — edgartools

**edgartools** (`pip install edgartools`) is the clear 2026 winner over alternatives:

| Option | Verdict |
|---|---|
| **edgartools** | **CHOSEN.** MIT, free, no API key, no rate-limit subscription. Returns typed Python objects + pandas DataFrames for 10-K/10-Q/XBRL facts. Active maintenance (PyPI weekly releases). Just set the SEC-required identifying user-agent: `set_identity("Your Name your@email.com")`. |
| sec-edgar-api / sec-api.io | **REJECTED.** Hosted SaaS, $55–$239/mo after 100 free calls. No reason to pay for personal use. |
| Raw `data.sec.gov` HTTP | **FALLBACK ONLY.** Use via `httpx` for company-facts endpoint if edgartools ever misses a specific concept tag we need (e.g., a non-standard GAAP fact). |

Note: EDGAR exposes raw GAAP/IFRS XBRL facts (e.g., `Revenues`, `OperatingIncomeLoss`, `GrossProfit`). PER/PEG aren't reported — we compute them: `PER = price / EPS_TTM`, `PEG = PER / EPS_growth`, `GPM = GrossProfit / Revenues`, `OPM = OperatingIncomeLoss / Revenues`. edgartools' XBRL fact querying makes this straightforward.

Confidence: HIGH.

---

## Critical Decision: DART client — OpenDartReader (primary) + raw API (fallback)

| Option | Verdict |
|---|---|
| **OpenDartReader** | **CHOSEN as primary.** Simplest Pythonic surface, well-documented for Korean fundamentals (재무제표, 공시목록). Requires free API key from opendart.fss.or.kr. |
| dart-fss | **VIABLE ALTERNATIVE.** More feature-rich (full XBRL parsing, Excel export). Also active. If OpenDartReader proves stale (no PyPI release in past ~12 months noted in some advisories), swap to dart-fss with minimal API churn. |
| pyopendart | **REJECTED for primary.** Smaller community, less documentation. |
| Raw OpenDART REST | **FALLBACK.** `httpx` against `https://opendart.fss.or.kr/api/...` for endpoints not wrapped, or if both libraries fall behind. |

**Auth note:** Both libraries require `OPENDART_API_KEY` (free, register at opendart.fss.or.kr). Store in `.env`, load via `python-dotenv`. Daily quota: 20,000 calls/day per key — far more than 100 tickers needs.

Confidence: MEDIUM-HIGH (primary lib's release cadence is the only soft spot; mitigation is library-swap, not strategy-change).

---

## Installation

```bash
# 1. Install uv (one-time, Windows PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Bootstrap project
uv python install 3.13
uv init
uv venv

# 3. Core dependencies
uv add yfinance "curl_cffi>=0.15,<0.16"
uv add edgartools OpenDartReader
uv add XlsxWriter pandas numpy
uv add tenacity httpx python-dotenv

# 4. Optional UX
uv add rich loguru

# 5. Dev dependencies
uv add --dev pytest ruff mypy

# 6. Run
uv run python main.py
```

`pyproject.toml` snippet (uv-managed):
```toml
[project]
name = "portfolio-analyzer"
requires-python = ">=3.13,<3.14"
dependencies = [
  "yfinance>=0.2.66",
  "curl_cffi>=0.15,<0.16",
  "edgartools>=4.0",
  "OpenDartReader>=0.2",
  "XlsxWriter>=3.2",
  "pandas>=2.2",
  "numpy>=2.0",
  "tenacity>=9.0",
  "httpx>=0.27",
  "python-dotenv>=1.0",
  "rich>=13.0",
  "loguru>=0.7",
]
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| yfinance | Polygon.io / Tiingo / Alpha Vantage / Finnhub | If yfinance becomes consistently blocked or this graduates beyond "personal tool" — they offer authenticated, SLA-backed APIs (free tiers exist; serious use is paid). |
| XlsxWriter | openpyxl | Only if a future requirement adds in-place editing of an existing styled workbook — currently explicitly out of scope. |
| pandas `.ewm()` | pandas-ta / TA-Lib | If we add ≥10 different exotic indicators (Ichimoku, Wilder's RSI, Heikin-Ashi). For our 4 EMAs, native pandas wins. |
| edgartools | Raw `data.sec.gov` JSON via httpx | If edgartools doesn't expose a specific XBRL concept tag we need. |
| OpenDartReader | dart-fss | If OpenDartReader release cadence stays slow and we hit an unwrapped endpoint or a breaking DART API change. |
| uv | Poetry | If you must publish to PyPI as a library (Poetry's build/publish UX is still slightly more polished). Not our case. |
| uv | pip + venv | One-off scripts. Not our case. |
| tenacity | `backoff` library | tenacity is more composable and actively maintained; no real reason to pick `backoff` today. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| pandas-ta (main fork) | Maintainer warned of archival by July 2026; no native NumPy 2 support | pandas `.ewm()` (native, exact, zero-dep) |
| TA-Lib | Native C dependency painful to install on Windows; overkill for 4 EMAs | pandas `.ewm()` |
| openpyxl (as primary writer) | Verbose conditional-formatting API; slower; designed around read+modify, not bulk write | XlsxWriter |
| `requests` + manual `Session` (passed to yfinance) | yfinance ≥0.2.60 **rejects** plain `requests.Session` — breaking change | `curl_cffi.requests.Session(impersonate="chrome")` |
| `curl_cffi` 0.14 | CVE #2743; yfinance refuses to load it | `curl_cffi >= 0.15, < 0.16` |
| `sec-api.io` paid SaaS | $55–$239/mo for what edgartools does free | edgartools |
| Threaded yfinance pulls with `threads=True` and high concurrency | Triggers Yahoo rate-limit blocks within minutes | `threads=False` or `threads=2`, + tenacity backoff |
| Python 3.14 | Some scientific wheels (curl_cffi, pandas-ta-classic, etc.) still catching up in mid-2026 | Python 3.13.x |
| Python 3.12 | Approaching EOL window; new project should target 3.13 for longer support runway | Python 3.13.x |
| Hard-coded API keys in source | Leaks into git history | `.env` + `python-dotenv` + `.gitignore` |

---

## Stack Patterns by Variant

**If user adds non-US/KR markets later:**
- yfinance still works for OHLCV (.T, .HK, .L, etc.).
- EDGAR/DART do NOT cover them. Fundamentals will degrade to yfinance/Naver fallback.
- PROJECT.md "Out of Scope" excludes this — flagged here only because it's the most likely future ask.

**If the workbook grows past ~200 sheets / Yahoo blocks become daily:**
- Add `requests-cache` or a SQLite OHLCV cache keyed by `(ticker, date)`.
- Pull only the delta since last run.
- This is a Phase-2 optimization, not Phase 1.

**If user wants scheduled runs (out of scope today):**
- Windows Task Scheduler invoking `uv run python main.py` — no code change.
- Avoid pulling in APScheduler / cron-equivalents.

---

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| yfinance ≥0.2.60 | curl_cffi ≥0.15, <0.16 | Plain `requests.Session` no longer accepted; CVE #2743 blocks 0.14. |
| pandas ≥2.2 | numpy ≥1.26 or 2.x | pandas 2.2.2 added NumPy 2 support. |
| pandas-ta (if used despite recommendation) | numpy <2 | NumPy 2 requires the `pandas-ta-openbb` fork — another reason to skip. |
| Python 3.13 | All stack libs above | Verified — wheels available on PyPI for all listed packages. |
| edgartools | Python ≥3.10 | No conflict. |
| XlsxWriter | Pure-Python | No native deps; works identically on Windows/macOS/Linux. |

---

## Sources

- **yfinance / curl_cffi** — [yfinance CHANGELOG (GitHub)](https://github.com/ranaroussi/yfinance/blob/main/CHANGELOG.rst), [Discussion #2431 rate-limit](https://github.com/ranaroussi/yfinance/discussions/2431), [Issue #2422 YFRateLimitError](https://github.com/ranaroussi/yfinance/issues/2422), [Issue #2496 session change](https://github.com/ranaroussi/yfinance/issues/2496) — HIGH
- **XlsxWriter** — [Working with Conditional Formatting (official docs)](https://xlsxwriter.readthedocs.io/working_with_conditional_formats.html), [Example: Conditional Formatting](https://xlsxwriter.readthedocs.io/example_conditional_format.html), [The Format Class](https://xlsxwriter.readthedocs.io/format.html) — HIGH
- **openpyxl** — [Conditional Formatting (official docs)](https://openpyxl.readthedocs.io/en/stable/formatting.html) — HIGH
- **edgartools** — [GitHub: dgunning/edgartools](https://github.com/dgunning/edgartools), [PyPI](https://pypi.org/project/edgartools/), [Complete Guide to SEC Filings in Python (2026)](https://edgartools.readthedocs.io/en/stable/complete-guide/), [Query XBRL Facts](https://edgartools.readthedocs.io/en/latest/xbrl-querying/) — HIGH
- **OpenDartReader / dart-fss** — [PyPI: OpenDartReader](https://pypi.org/project/OpenDartReader/), [GitHub: FinanceData/OpenDartReader](https://github.com/FinanceData/OpenDartReader), [PyPI: dart-fss](https://pypi.org/project/dart-fss/), [GitHub: josw123/dart-fss](https://github.com/josw123/dart-fss) — MEDIUM-HIGH (OpenDartReader release cadence is the soft spot)
- **pandas ewm / EMA formula** — [pandas ewm docs](https://docs.vultr.com/python/third-party/pandas/DataFrame/ewm), [Statology: EMA in Pandas](https://www.statology.org/exponential-moving-average-pandas/) — HIGH
- **pandas-ta status** — [PyPI: pandas-ta](https://pypi.org/project/pandas-ta/), [PyPI: pandas-ta-openbb (NumPy 2 fork)](https://pypi.org/project/pandas-ta-openbb/) — HIGH (archival warning explicit in project README)
- **tenacity** — [GitHub: jd/tenacity](https://github.com/jd/tenacity), [Tenacity docs](https://tenacity.readthedocs.io/) — HIGH
- **uv** — [Best Python Package Managers 2026](https://scopir.com/posts/best-python-package-managers-2026/), [uv vs pip vs Poetry 2026](https://www.danilchenko.dev/posts/uv-vs-pip-vs-poetry/), [Python Dependency Management 2026 (Cuttlesoft)](https://cuttlesoft.com/blog/2026/01/27/python-dependency-management-in-2026/) — HIGH
- **Python version status** — [Python devguide: Status of Python versions](https://devguide.python.org/versions/), [What's New in Python 3.13](https://docs.python.org/3/whatsnew/3.13.html) — HIGH

---

*Stack research for: Python personal portfolio analyzer (Yahoo OHLCV + EDGAR/DART fundamentals → xlsx with conditional formatting)*
*Researched: 2026-05-19*
