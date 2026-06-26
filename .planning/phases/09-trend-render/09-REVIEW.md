---
phase: 09-trend-render
reviewed: 2026-06-22T00:00:00Z
depth: standard
files_reviewed: 13
files_reviewed_list:
  - main.py
  - src/stocksig/compute/trend_color.py
  - src/stocksig/io/history_render.py
  - src/stocksig/io/quarter_price.py
  - src/stocksig/output/history_workbook.py
  - src/stocksig/output/sheet_metric_matrix.py
  - src/stocksig/output/sheet_raw.py
  - src/stocksig/output/sheet_snapshot.py
  - tests/fixtures/history_fixtures.py
  - tests/test_history_render.py
  - tests/test_history_sheets.py
  - tests/test_quarter_price.py
  - tests/test_trend_color.py
findings:
  critical: 1
  warning: 4
  info: 4
  total: 9
status: issues_found
---

# Phase 09: Code Review Report

**Reviewed:** 2026-06-22
**Depth:** standard
**Files Reviewed:** 13
**Status:** issues_found

## Summary

Phase 09 renders a separate `fundamentals_history_*.xlsx` workbook from DB-loaded
quarterly fundamentals. The separation from 시트1 (portfolio) is clean: `history_render`
imports no `main_run`/`sheet_portfolio`/`color_rules` *functions* (only color hex
constants), sheet-name sanitization strips `[]`, missing values render as `"-" + 사유`
(never 0), and division/NaN guards in the price-ratio path are delegated to the Phase 8
engine. Network-0 / DB-0 test discipline holds.

However, the central relative-color logic in `trend_color.relative_bucket` —
the heart of the Core Value invariant ("accurate, intuitive color signals") — contains
a tercile-boundary misclassification that colors a company sitting at the **industry
median** as green/red instead of neutral. This is exactly the smallest, most common
real population (the D-07 minimum sample of 3 peers), and it is untested. This is a
BLOCKER against the stated Core Value.

## Critical Issues

### CR-01: `relative_bucket` colors the median-of-3 as a non-neutral signal (Core Value violation)

**File:** `src/stocksig/compute/trend_color.py:53-64`

**Issue:** The tercile classifier uses `lower_frac <= 1/3` / `upper_frac <= 1/3` with the
"low" branch tested first. For the minimum valid population of exactly 3 peers (the D-07
gate floor, and the most common industry size in a personal portfolio), the **median**
value produces `below=1, above=1, total=3` → `lower_frac = 1/3` which satisfies
`<= 1/3` → `rank = "low"`. A company sitting exactly at the industry median is therefore
colored:
- LOWER_IS_BETTER (e.g. PER) → "초록" (green)
- HIGHER_IS_BETTER (e.g. ROE) → "빨강" (red)

It should be "무색" (neutral). Verified empirically:

```
peers=[10,20,30], value=20 (median)  -> below=1, above=1, total=3
lower_frac = 1/3 -> "low"  (WRONG, should be "mid"/무색)
```

This directly breaks the Core Value: "중앙값 ± 표준편차를 기준으로 한 색상 신호가 ...
정확하고 직관적으로 보여야 한다." A median company is, by definition, neutral, yet it
is painted as a buy/sell signal. The existing test `test_tie_is_plain` only covers the
all-equal degenerate case (`below==0 and above==0`), so the median-of-3 path is
completely untested.

The boundary is also asymmetric/overlap-ambiguous: when both `lower_frac <= 1/3` and
`upper_frac <= 1/3` hold, "low" silently wins by branch order rather than by which
tail the value actually belongs to.

**Fix:** Use a strict boundary so the median tercile is excluded, and make the two tails
mutually exclusive. For example, classify by tail fraction strictly below 1/3, or rank
by the value's quantile position rather than raw counts:

```python
# strict: median-of-3 (lower_frac == 1/3) falls through to "mid"
if lower_frac < 1.0 / 3.0:
    rank = "low"
elif upper_frac < 1.0 / 3.0:
    rank = "high"
else:
    rank = "mid"
```

Then add a regression test asserting `relative_bucket("PER", 20.0, [10,20,30], "tech")
== "무색"` and `relative_bucket("ROE", 20.0, [10,20,30], "tech") == "무색"`. Confirm the
existing low/high tests (`value=5`/`value=40` of `[5,20,30,40]`) still pass under the
strict boundary (they do: `below=0` → `0 < 1/3`, `above=0` → `0 < 1/3`).

## Warnings

### WR-01: `relative_bucket` mid-quartile values still mis-tail on even populations

**File:** `src/stocksig/compute/trend_color.py:56-61`

**Issue:** Independent of CR-01, the raw below/above count approach mislabels interior
values for small even populations. For `peers=[5,20,30,40], value=20` → `below=1,
above=3, total=4` → `lower_frac=0.25 <= 1/3` → "low" → green (LOWER_IS_BETTER). A value
that is only the 2nd-lowest of 4 and has 3 peers above it is arguably mid, but is
painted as a strong-buy. The classifier conflates "fraction of peers below" with
"is in the bottom third of the value range," which are not the same for skewed samples.

**Fix:** Decide on an explicit definition (rank quantile vs. value-range tercile) and
implement it once. If rank-based: `position = below / (total - 1)` excluding self, then
`low` iff `position < 1/3`. Document the chosen definition in the docstring and cover
both small even and odd populations in tests.

### WR-02: Per-ticker exception isolation swallows the diagnostic detail needed to debug a silent column

**File:** `src/stocksig/io/history_render.py:145-149`

**Issue:** The per-ticker `try/except Exception` logs only `type(exc).__name__` (T-09-07
intent) at WARNING and drops the ticker from `rendered`. A ticker that fails
`compute_matrix`, `quarter_end_prices`, or `_inject_prices` vanishes from the workbook
with no row and no message tying the failure to a cause (no stack, no `str(exc)`).
For a financial tool where a missing ticker is itself a misleading signal (the user may
read "no AAPL row" as "no data exists" rather than "render crashed"), this is a
correctness-adjacent robustness gap. The blanket `except Exception` also hides
programming errors (e.g. a `KeyError`/`TypeError` introduced by a future refactor)
behind the same one-line warning.

**Fix:** Keep the isolation but raise the signal: log `exc` with `logger.warning(..., exc_info=True)`
or at minimum include `str(exc)`, and consider emitting a placeholder row / summary count
of dropped tickers so a silently-missing company is visible to the user. If T-09-07
forbids full tracebacks in normal logs, log the detail at DEBUG.

### WR-03: `_inject_prices` derives quarters before injection but relies on denominator coverage

**File:** `src/stocksig/io/history_render.py:137-141`

**Issue:** `quarters` is computed from `matrix.values()` **before** `_inject_prices` adds
PER/PEG/PBR/PCR/PSR, so the quarter set reflects only non-price metrics plus per-share
denominators. The injected `latest_q` is then `quarters[-1]` of that pre-injection set.
This is correct only as long as every displayed quarter has a per-share denominator cell;
if a quarter exists for, say, GPM (a flow-TTM metric) but the per-share denominators
(EPS_ttm/BPS/...) are absent for that quarter, the price-dependent metrics will still be
written for it via `qmap.get(q)`/`None`, but `latest_q` selection and the PEG path silently
assume denominator coverage. The coupling between "which quarters exist" and "which
quarters have a tradeable price/denominator" is implicit and undocumented.

**Fix:** Make the contract explicit: either assert that `latest_q` corresponds to a quarter
with a non-missing PER denominator, or compute `latest_q` from the union after injection and
document why pre-injection selection is safe. Add a test with a ticker whose newest quarter
has a flow metric but no per-share denominator to lock the behavior.

### WR-04: Snapshot recomputes `sym_latest` independently of the matrix injection's `latest_q`

**File:** `src/stocksig/io/history_render.py:210-216` vs `141`

**Issue:** `_inject_prices` injects current-price-based PER/PEG into the quarter chosen as
`latest_q = quarters[-1]` (pre-injection set). The snapshot section independently recomputes
`sym_latest = sym_quarters[-1]` from the **post-injection** matrix (which now contains PEG/PER
quarters). If injection ever introduces a quarter key not present in the pre-injection set
(e.g. a PEG written for a quarter via `_calendar_quarter_offset` math, or a price-only quarter),
the two "latest" definitions diverge and the snapshot would show a different quarter than the
one the matrix sheet treated as current — i.e. the snapshot's "current price" PER could be read
from a non-current column. Today they coincide because injection reuses existing denominator
quarters, but the duplicated, independently-derived "latest" logic is fragile.

**Fix:** Compute the latest quarter once per ticker (alongside `_inject_prices`) and pass it
through to the snapshot, rather than re-deriving it from the mutated matrix. Add an assertion
or test that `sym_latest == latest_q` used at injection time.

## Info

### IN-01: Dead numeric-format branch in matrix writer

**File:** `src/stocksig/output/sheet_metric_matrix.py:124`

**Issue:** `_bucket_formats` returns `(numeric_fmt, text_fmt)` but the matrix writer only
uses `fmt_text` (`_, fmt_text = _bucket_formats(...)`), and all value cells are written via
`ws.write_string`. The numeric `green`/`red`/`plain` formats (with `num_format`) are never
applied in this sheet — only their `_text` variants are. The numeric formats and the tuple's
first element are effectively dead in this writer.

**Fix:** Either drop the unused first tuple element from `_bucket_formats` (return only the
text format) or document that the numeric formats exist solely for a future numeric-cell mode.

### IN-02: Broad `except Exception: pass` on stdout reconfigure

**File:** `main.py:23-24`

**Issue:** The Windows UTF-8 `reconfigure` is wrapped in a bare `except Exception: pass`. If
reconfiguration fails, Korean console output may silently mojibake with no diagnostic. Low
risk (it is a best-effort console fix), but the silent swallow hides the failure mode.

**Fix:** Narrow to the expected exception or log at DEBUG when reconfigure fails.

### IN-03: `peer_lookup` float cast can raise inside the workbook write and abort the whole file

**File:** `src/stocksig/io/history_render.py:170-172`

**Issue:** `peer_lookup` does `vals.append(float(v))` after an `_is_missing` guard. `_is_missing`
only rejects `None`/NaN-float. If a `MetricCell.value` ever held a non-numeric (contract says
`float | None`, so unlikely), `float(v)` raises inside the `try/finally` that wraps all sheet
writes — the `finally` only calls `wb.close()`, so the exception propagates and the whole
workbook render fails (unlike the per-ticker isolation in step 3). Defensive only given current
typing.

**Fix:** If hardening is desired, guard the cast (`isinstance(v, (int, float))`) or wrap
per-sheet writes so one bad value degrades one sheet rather than the file.

### IN-04: Duplicated identifier-column / metric-list / `_format_value_text` / `_IS_RATIO` literals across sheets

**File:** `src/stocksig/output/sheet_metric_matrix.py:26-48`, `src/stocksig/output/sheet_snapshot.py:17-30`

**Issue:** `_IDENT_COLUMNS`, `_SHEET_METRICS`/`_SNAPSHOT_METRICS`, `_IS_RATIO`, and
`_format_value_text` are copy-pasted between the matrix and snapshot writers (and the 9-metric
list is repeated a third time in `history_render._SHEET_METRICS`). These must stay in lockstep
(WARNING-2 percent formatting, D-01 ordering); divergence would produce inconsistent display
between sheets. The duplication of the identifier-column literals is intentional per the
"시트1 비결합" decision, but the metric list and ratio-percent formatter are pure shared logic
with no coupling reason.

**Fix:** Extract the shared 9-metric ordering, `_IS_RATIO`, and `_format_value_text` into one
trend-local module imported by both writers and the orchestrator. Keep the identifier-column
literals separate if the no-coupling rule requires it, but add a test asserting matrix and
snapshot use the same metric order.

---

_Reviewed: 2026-06-22_
_Reviewer: Claude (gsd-code-reviewer)_
_Depth: standard_
