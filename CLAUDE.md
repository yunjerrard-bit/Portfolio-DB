<!-- GSD:project-start source:PROJECT.md -->
## Project

**표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트**

표준편차를 활용한 매매 신호와 보유 종목을 한 눈에 관리할 수 있는 엑셀(.xlsx) 워크북을 자동 생성하는 개인용 주식 분석 도구입니다. 사용자가 보유/관심 종목 티커 목록을 입력하면, Python이 Yahoo Finance에서 10년치 시세를 받아오고 EMA·표준편차·중앙값을 계산해 종목별 시트와 통합 포트폴리오 시트를 만들어 줍니다. 사용자는 개인 투자자(본인) 한 명이며, 매매 판단의 시각적 보조 도구로 사용합니다.

**Core Value:** **중앙값 ± 표준편차를 기준으로 한 색상 신호가 통합 포트폴리오 시트에서 정확하고 직관적으로 보여야 한다.** 이것이 무너지면 다른 모든 기능은 의미가 없습니다.

### Constraints

- **Tech stack**: Python (yfinance + openpyxl 등 표준 라이브러리). Windows 로컬 실행.
- **Output**: 단일 `.xlsx` 파일. 매 실행마다 새 파일 생성.
- **데이터 소스 우선순위**: 시세 = Yahoo Finance / 재무 = EDGAR(미) → DART(한) → yfinance/네이버 보완
- **Performance**: Yahoo Finance rate-limit 회피를 위한 합리적 throttle/retry 필요. 100종목 처리가 비현실적으로 오래 걸리면 안 됨.
- **언어**: 사용자 인터페이스(엑셀 헤더, 로그 메시지)는 한국어 우선.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Executive Recommendation (one-liner)
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
## Critical Decision: XlsxWriter vs openpyxl
| Capability | XlsxWriter | openpyxl | Winner |
|---|---|---|---|
| Conditional formatting API ergonomics | Single `worksheet.conditional_format(range, {'type':'formula', 'criteria': '...', 'format': fmt})` | Multi-class: `Rule`, `DifferentialStyle`, `Font`, `PatternFill`, `ConditionalFormattingList` — verbose | **XlsxWriter** |
| Font color + cell fill in same rule | Native via `Format` object (one place) | Requires `DifferentialStyle(font=Font(color=...), fill=PatternFill(...))` | **XlsxWriter** |
| Custom formula rules | First-class `'type': 'formula'` | First-class `FormulaRule` | Tie |
| Icon sets (for volume anomaly cell signals) | Built-in (`3_traffic_lights`, `3_arrows`, etc.) | Possible but more code | **XlsxWriter** |
| Write performance (100 sheets) | Faster (write-once design, `constant_memory` mode available) | Slower, especially on writes | **XlsxWriter** |
| Read/modify existing files | NOT supported (write-only) | Supported | openpyxl |
| Charts | Comprehensive native chart support | Supported but quirkier | **XlsxWriter** |
## Critical Decision: EMA computation — pandas.ewm vs pandas-ta vs TA-Lib
| Option | Verdict |
|---|---|
| **pandas `.ewm(span=N, adjust=False).mean()`** | **CHOSEN.** Native, zero extra deps, exact match to TradingView/standard financial EMA formula `EMA_t = α·P_t + (1-α)·EMA_{t-1}` with `α = 2/(span+1)`. We only need 4 EMA periods × 3 price series — trivial. |
| pandas-ta | **REJECTED.** Maintainer announced: unless additional support arrives by **July 2026**, project will be archived. Does not natively support NumPy 2 (must use `pandas-ta-openbb` fork). Adds a fragile dependency for a one-line builtin. |
| TA-Lib | **REJECTED.** Requires native C library install on Windows (vcpkg / prebuilt wheel hunting). Massive overkill for 4 EMAs. Justifiable only if we later need exotic indicators (Ichimoku, Wilder's, etc.). |
## Critical Decision: Yahoo Finance rate-limit strategy
## Critical Decision: EDGAR client — edgartools
| Option | Verdict |
|---|---|
| **edgartools** | **CHOSEN.** MIT, free, no API key, no rate-limit subscription. Returns typed Python objects + pandas DataFrames for 10-K/10-Q/XBRL facts. Active maintenance (PyPI weekly releases). Just set the SEC-required identifying user-agent: `set_identity("Your Name your@email.com")`. |
| sec-edgar-api / sec-api.io | **REJECTED.** Hosted SaaS, $55–$239/mo after 100 free calls. No reason to pay for personal use. |
| Raw `data.sec.gov` HTTP | **FALLBACK ONLY.** Use via `httpx` for company-facts endpoint if edgartools ever misses a specific concept tag we need (e.g., a non-standard GAAP fact). |
## Critical Decision: DART client — OpenDartReader (primary) + raw API (fallback)
| Option | Verdict |
|---|---|
| **OpenDartReader** | **CHOSEN as primary.** Simplest Pythonic surface, well-documented for Korean fundamentals (재무제표, 공시목록). Requires free API key from opendart.fss.or.kr. |
| dart-fss | **VIABLE ALTERNATIVE.** More feature-rich (full XBRL parsing, Excel export). Also active. If OpenDartReader proves stale (no PyPI release in past ~12 months noted in some advisories), swap to dart-fss with minimal API churn. |
| pyopendart | **REJECTED for primary.** Smaller community, less documentation. |
| Raw OpenDART REST | **FALLBACK.** `httpx` against `https://opendart.fss.or.kr/api/...` for endpoints not wrapped, or if both libraries fall behind. |
## Installation
# 1. Install uv (one-time, Windows PowerShell)
# 2. Bootstrap project
# 3. Core dependencies
# 4. Optional UX
# 5. Dev dependencies
# 6. Run
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
## Stack Patterns by Variant
- yfinance still works for OHLCV (.T, .HK, .L, etc.).
- EDGAR/DART do NOT cover them. Fundamentals will degrade to yfinance/Naver fallback.
- PROJECT.md "Out of Scope" excludes this — flagged here only because it's the most likely future ask.
- Add `requests-cache` or a SQLite OHLCV cache keyed by `(ticker, date)`.
- Pull only the delta since last run.
- This is a Phase-2 optimization, not Phase 1.
- Windows Task Scheduler invoking `uv run python main.py` — no code change.
- Avoid pulling in APScheduler / cron-equivalents.
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| yfinance ≥0.2.60 | curl_cffi ≥0.15, <0.16 | Plain `requests.Session` no longer accepted; CVE #2743 blocks 0.14. |
| pandas ≥2.2 | numpy ≥1.26 or 2.x | pandas 2.2.2 added NumPy 2 support. |
| pandas-ta (if used despite recommendation) | numpy <2 | NumPy 2 requires the `pandas-ta-openbb` fork — another reason to skip. |
| Python 3.13 | All stack libs above | Verified — wheels available on PyPI for all listed packages. |
| edgartools | Python ≥3.10 | No conflict. |
| XlsxWriter | Pure-Python | No native deps; works identically on Windows/macOS/Linux. |
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
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, `.github/skills/`, or `.codex/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
