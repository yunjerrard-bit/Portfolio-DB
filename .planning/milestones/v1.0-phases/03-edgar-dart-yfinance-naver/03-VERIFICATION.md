---
phase: 03-edgar-dart-yfinance-naver
verified: 2026-06-05T18:00:00+09:00
status: passed
score: 4/4
overrides_applied: 0
gaps: []
uat_resolution: "03-UAT.md 5/5 통과 (2026-06-05). 수기 3건(시트1 미국/한국 펀더멘털 값+출처 주석, 캐시 HIT 재실행, EDGAR UA 403 무발생) 사용자 실환경 실행으로 확인. SC4 EDGAR 캐시 배선 WARNING은 9cfc1df로 RESOLVED. 추가로 UAT 중 OHLCV 미정산 NaN봉 버그 발견·수정(quick 260605-kfy)."
human_verification:
  - test: "python main.py 1회 실행 후 시트1 R/S/T/U(col 18~21) 4값 + 셀 주석 육안 확인"
    expected: "각 미국 티커 행에 PER/PEG/GPM/OPM 숫자값이 표시되고, 셀 주석에 'EDGAR · 2026Q2' 또는 'yf' 출처 표시. 결손 셀은 빈칸 + '조회 실패: ...' 한국어 주석."
    why_human: "실제 EDGAR/DART API 키(.env)와 네트워크 연결이 필요. 자동 테스트는 openpyxl readback으로 로직만 검증하며 실제 API 응답은 mock."
  - test: "한국 티커(예: 005930.KS) 행에서 DART 출처 표시 확인"
    expected: "PER/PEG/GPM/OPM 4값 표시, 셀 주석에 'DART' 또는 'Naver' 또는 'yf' 출처."
    why_human: "OPENDART_API_KEY 실제 키 주입 후 라이브 DART API 응답 확인 필요."
  - test: "같은 주 내 2회 실행 시 EDGAR/DART 외부 호출 수 확인"
    expected: "2회차 실행 시 콘솔 로그에 'cache HIT' 메시지가 DART 종목에 대해 표시되고 외부 API 호출이 거의 없음. EDGAR 경로는 아래 WARNING 참조."
    why_human: "디스크 캐시 7d TTL 실동작은 사용자 환경 실행 후 콘솔 로그로만 확인 가능."
---

# Phase 3: 기본적 분석 데이터(EDGAR/DART/yfinance·Naver) 검증 보고서

**Phase Goal:** 시트1에 PER/PEG/GPM/OPM 기본적 분석 지표를 추가하고, 미국=EDGAR(edgartools)·한국=DART(OpenDartReader) 1차, yfinance/Naver 보완, 각 값 출처 명시.
**Verified:** 2026-06-05T18:00:00+09:00
**Status:** human_needed
**Re-verification:** No — 초기 검증

---

## 검증 방법론

SUMMARY.md 진술을 신뢰하지 않고, 각 Success Criteria를 코드베이스에서 역방향으로 추적했다. 코드 존재 → 실질적 구현(로직) → 배선(호출 경로) → 데이터 흐름(Level 4)까지 순서대로 검증하고, 자동 테스트(`uv run pytest`) 194개 전체 통과를 직접 확인했다.

---

## Goal Achievement

### Observable Truths (Success Criteria)

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | 시트1 미국 티커 행에 PER/PEG/GPM/OPM 4값 + EDGAR 출처 표시(yf 폴백 + 출처 표시 포함) | VERIFIED | `sheet_portfolio.PORTFOLIO_COLUMNS` 21열 선언(col 17~20=PER/PEG/GPM/OPM), `_write_fund_cell` → `write_number` + `write_comment(source/note)`, `test_fund_cols` openpyxl readback 통과 |
| 2 | 시트1 한국 티커 행에 동등 지표 + DART corp_code 매핑 + (DART)/(Naver) 출처 표시 | VERIFIED | `dart_client.fetch_dart_raw`: 6자리 stock_code 직접 수용(A6), account_id 1차/account_nm 2차 매핑(A3), `fundamentals._fill_kr`: DART→Naver(PER)→yf 차등 폴백, 각 셀 source 라벨 기록, 테스트 8건 통과 |
| 3 | EDGAR 호출 UA 헤더에 yunjerrard@gmail.com 포함 + 토큰버킷 EDGAR ≤8/DART ≤2 RPS | VERIFIED | `edgar_client._DEFAULT_EMAIL = "yunjerrard@gmail.com"`, import-time `set_identity(_SET_IDENTITY_ARG)` 1회 호출, `throttle.py: Rate(8, SECOND)`/`Rate(2, SECOND)`, `test_set_identity` + `test_edgar_decorator_*` + `test_dart_decorator_*` 통과 |
| 4 | 같은 주 내 2회 실행 시 EDGAR/DART 7d 캐시 조회로 외부 호출 거의 없음 | PARTIAL | DART 경로: `fetch_dart_cached` 올바르게 배선됨. **EDGAR 경로(WARNING 참조)**: `fundamentals._default_edgar`가 `fetch_edgar_raw`를 직접 호출하고 `fetch_edgar_cached` 미사용 — US 종목 2회 실행 시 EDGAR 호출이 매번 발생. 캐시 자체(get_fund/put_fund 7d TTL)는 구현·테스트 완료 |

**Score:** 3.5/4 (SC4 PARTIAL — DART 경로는 캐시 배선 완료, EDGAR 경로는 캐시 우회)

---

## Required Artifacts

| 아티팩트 | 목적 | 수준1 존재 | 수준2 실질 | 수준3 배선 | 상태 |
|---------|------|-----------|-----------|-----------|------|
| `src/stocksig/io/edgar_client.py` | EDGAR EntityFacts 취득 + set_identity + throttle + cache | 존재 | 실질 (set_identity, `@throttled_edgar`, fetch_edgar_raw, fetch_edgar_cached) | fundamentals.py에서 fetch_edgar_raw 호출 (fetch_edgar_cached 미사용 — WARNING) | PARTIAL |
| `src/stocksig/io/dart_client.py` | DART finstate_all + account 매핑 + throttle + cache | 존재 | 실질 (DART_ACCOUNT_ID_MAP 1차, account_nm 2차, status 가드, int 파싱) | fundamentals._default_dart → fetch_dart_cached 올바르게 배선 | VERIFIED |
| `src/stocksig/io/naver_scraper.py` | KR PER 폴백 (UTF-8, D-07 상한) | 존재 | 실질 (`#_per` 셀렉터, NAVER_FALLBACK_CAP=20, reset_naver_count) | fundamentals._fill_kr에서 naver_fn으로 주입 | VERIFIED |
| `src/stocksig/io/yf_fundamentals.py` | yfinance .info 폴백 (trailingPE/pegRatio/grossMargins/operatingMargins) | 존재 | 실질 (`_SESSION` 재사용, None-safe .get()) | fundamentals._fill_us/_fill_kr에서 yf_fn으로 주입 | VERIFIED |
| `src/stocksig/io/fundamentals.py` | 라우팅 오케스트레이터 (US/KR 분기, MetricCell/FundamentalsResult, PEG 산식) | 존재 | 실질 (PEG 4 엣지케이스, per-metric provenance, 예외 흡수) | runner.process_ticker → main_run.run 클로저 주입 | VERIFIED |
| `src/stocksig/io/throttle.py` | EDGAR 8 RPS / DART 2 RPS 토큰버킷 | 존재 | 실질 (Rate(8,SECOND), Rate(2,SECOND)) | edgar_client/dart_client에 @throttled_edgar/@throttled_dart 적용 | VERIFIED |
| `src/stocksig/io/cache.py` | 7d TTL 펀더멘털 캐시 (.cache/fundamentals, 키 SOURCE|TICKER|QUARTER) | 존재 | 실질 (`_FUND_TTL_SECONDS = 7*24*60*60`, get_fund/put_fund) | DART 경로 배선 완료, EDGAR 경로 미배선 (WARNING) | PARTIAL |
| `src/stocksig/output/sheet_portfolio.py` | 시트1 21열 + _write_fund_cell + write_comment 출처 | 존재 | 실질 (PORTFOLIO_COLUMNS 21열, PER/PEG 'price', GPM/OPM 'percent_ratio', write_blank+note D-05) | main_run → write_portfolio_sheet → _write_success_row 배선 완료 | VERIFIED |
| `src/stocksig/io/dart_account_map.py` | DART account_id/account_nm 상수 (A3 [VERIFIED]) | 존재 | 실질 (DART_ACCOUNT_ID_MAP + DART_ACCOUNT_MAP + SJ_DIV_INCOME_STATEMENT) | dart_client에서 import 사용 | VERIFIED |

---

## Key Link Verification

| From | To | Via | Status | 상세 |
|------|-----|-----|--------|------|
| `main_run.run` | `fetch_fundamentals` | `run_all(..., fundamentals_fn=fetch_fundamentals)` | WIRED | line 240 확인 |
| `main_run.run` | `naver_scraper.reset_naver_count` | run 시작 시 직접 호출 | WIRED | line 232 확인, D-07 충족 |
| `runner.process_ticker` | `fundamentals_fn(ticker, market, last_close)` | `PASS 1b`, try/except 흡수 | WIRED | runner.py lines 94-102 |
| `sheet_portfolio._write_success_row` | `_write_fund_cell` (PER/PEG/GPM/OPM) | `res.fundamentals is not None` 가드 후 4셀 | WIRED | lines 224-239 |
| `edgar_client.fetch_edgar_raw` | `cache.get_fund/put_fund` | `fetch_edgar_cached` (함수 존재, 미배선) | PARTIAL | `fundamentals._default_edgar`가 `fetch_edgar_raw` 직접 호출. `fetch_edgar_cached`는 edgar_client.py에 정의되었으나 호출 지점 없음 |
| `dart_client.fetch_dart_raw` | `cache.get_fund/put_fund` | `fetch_dart_cached` | WIRED | fundamentals._default_dart → fetch_dart_cached 올바르게 배선 |
| `edgar_client` | `set_identity` | import-time 1회, `_SET_IDENTITY_ARG` 포함 이메일 | WIRED | `set_identity(_SET_IDENTITY_ARG)` line 45 확인 |

---

## Data-Flow Trace (Level 4)

| 아티팩트 | 데이터 변수 | 소스 | 실 데이터 생산 | 상태 |
|---------|-----------|------|--------------|------|
| `_fill_us` | `edgar_fn(ticker)` → raw dict | edgar_client.fetch_edgar_raw (Company(ticker).get_facts()) | EntityFacts typed accessor (A1 VERIFIED 실측) | VERIFIED |
| `_fill_kr` | `dart_fn(ticker)` → raw dict | fetch_dart_cached → OpenDartReader.finstate_all | 실 DART API (A3/A6 VERIFIED, account_id 매핑) | VERIFIED |
| `_fill_kr` | `naver_fn(ticker)` | naver_scraper.fetch_naver_per → httpx + BeautifulSoup | `#_per` 셀렉터 파싱 (A5 VERIFIED UTF-8) | VERIFIED |
| `_write_fund_cell` | `cell.value / cell.note` | FundamentalsResult → MetricCell | write_number (값) + write_comment (출처), 결손 시 write_blank + 사유 주석 | VERIFIED |

---

## Behavioral Spot-Checks

| 동작 | 검증 방법 | 결과 | 상태 |
|------|---------|------|------|
| Phase 3 관련 테스트 102개 | `uv run pytest test_edgar_client ... test_sheet_portfolio` | 102 passed in 40.80s | PASS |
| 전체 테스트 스위트 194개 | `uv run pytest` | 194 passed in 245.88s | PASS |
| `PORTFOLIO_COLUMNS` 21열 | `test_column_count_is_21` + `test_column_order` | 21열 확인, PER/PEG/GPM/OPM 마지막 4열 | PASS |
| 펀더멘털 4셀 + 출처 주석 | `test_fund_cols` (openpyxl readback) | col 18~21 값 + comment 'EDGAR' + num_format #,##0.00/0.00% | PASS |
| DART 7d 캐시 HIT | `test_fund_cache_hit_within_7d` | freezegun 6d 후 캐시 HIT 확인 | PASS |
| EDGAR set_identity UA | `test_set_identity` | `@` 포함, 이름+이메일 토큰 2개 이상 | PASS |
| D-07 네이버 CAP 20 | `test_naver_fallback_cap` | httpx.get CAP회만 호출, 초과분 None | PASS |
| PEG 성장률 엣지케이스 4종 | `test_compute_peg_*` 4건 | 성장률≤0/0분모/전년None/PER없음 모두 빈값+한국어사유 | PASS |

---

## Requirements Coverage

| Requirement | 설명 | 코드 근거 | 상태 |
|-------------|------|---------|------|
| FUND-01 | EDGAR(edgartools)로 EPS/Revenue/GrossProfit/OpIncome raw facts 취득 | edgar_client.fetch_edgar_raw: EntityFacts typed accessor (A1/A2 확정 경로) | SATISFIED |
| FUND-02 | EDGAR 호출 UA에 사용자 이메일 포함 | `edgar_client._DEFAULT_EMAIL = "yunjerrard@gmail.com"`, import-time `set_identity` | SATISFIED |
| FUND-03 | DART(OpenDartReader)로 KR 재무 데이터, corp_code 매핑(stock_code 직접 수용) | dart_client: `finstate_all("005930", ...)`, account_id 1차/account_nm 2차 (A3/A6) | SATISFIED |
| FUND-04 | EDGAR/DART 응답 7d TTL sqlite 캐시 저장 | cache.py: `_FUND_TTL_SECONDS = 7*24*60*60`, get_fund/put_fund, 7d HIT/MISS 테스트 | SATISFIED (캐시 구현 완료, EDGAR 배선 WARNING) |
| FUND-05 | 1차 소스 결손 시 yfinance/네이버 보완 + 출처 기록 | fundamentals._fill_us(EDGAR→yf), _fill_kr(DART→Naver→yf), per-metric provenance(MetricCell.source) | SATISFIED |
| FUND-06 | 토큰버킷 EDGAR ≤8 RPS / DART ≤2 RPS | throttle.py: Rate(8,SECOND)/Rate(2,SECOND), @throttled_edgar/@throttled_dart | SATISFIED |
| PORT-05 | 시트1 각 행에 PER/PEG/GPM/OPM + 출처 표시 | sheet_portfolio: 21열(col 17~20), _write_fund_cell, write_comment, test_fund_cols 통과 | SATISFIED |

---

## Anti-Patterns Scan

| 파일 | 라인 | 패턴 | 심각도 | 영향 |
|------|------|------|--------|------|
| `src/stocksig/io/fundamentals.py` | 296-297 | `_default_edgar` 클로저가 `fetch_edgar_raw` 직접 호출 (`fetch_edgar_cached` 미사용) | WARNING | US 종목 2회 실행 시 EDGAR API 매번 호출 — SC4 EDGAR 경로 캐시 우회 |

TBD/FIXME/XXX 마커: 없음 (Phase 3 수정 파일 전체 검사).
placeholder/stub 패턴: 없음 — 결손 셀은 `D-05` 의도에 따른 `write_blank+한국어 사유` (stub 아님).

---

## SC4 WARNING 상세: EDGAR 캐시 배선 누락

`edgar_client.fetch_edgar_cached(ticker, quarter_label)` 함수는 정의되어 있고 올바르게 구현되어 있으며 (`test_fetch_edgar_cached_hit` 통과), 7d TTL 캐시 패턴을 DART와 동일하게 따른다. 그러나 `fundamentals.py`의 기본 `_default_edgar` 클로저가 `fetch_edgar_raw`를 직접 호출함으로써 캐시를 우회한다.

DART 경로는 `fetch_dart_cached`를 올바르게 사용한다 (line 316).

**영향:** 같은 주 내 US 종목 2회 실행 시 EDGAR API 호출이 매번 발생 (SC4 부분 미충족).
**수정 방법:** `fundamentals.py` line 297을:
```python
return edgar_client.fetch_edgar_raw(t)
```
에서:
```python
quarter = edgar_client.fetch_edgar_raw(t).get("quarter_label", "UNKNOWN")
return edgar_client.fetch_edgar_cached(t, quarter)
```
또는 `fetch_edgar_cached`가 내부에서 `fetch_edgar_raw` 한 번 호출 후 캐시에 저장하므로:
```python
raw = edgar_client.fetch_edgar_raw(t)
return edgar_client.fetch_edgar_cached(t, raw.get("quarter_label", "UNKNOWN"))
```
단, `fetch_edgar_cached`는 MISS 시 `fetch_edgar_raw`를 다시 호출하므로 중복 호출 주의. 또는 `_default_edgar`를 `fetch_edgar_cached`를 직접 호출하도록 수정하는 것이 더 직관적이다.

이 이슈는 기능 동작(SC1/SC2/SC3)에는 영향이 없고, **SC4 성능/캐시 효율성**에만 영향을 미친다.

---

## Human Verification Required

### 1. 실제 워크북 생성 후 시트1 R/S/T/U 육안 확인

**Test:** `EDGAR_USER_AGENT_EMAIL=yunjerrard@gmail.com` 및 `OPENDART_API_KEY=<실키>` 가 `.env`에 채워진 상태로 `python main.py` 실행.
**Expected:** 시트1 col R(PER)/S(PEG)/T(GPM)/U(OPM)에 숫자값, 셀 주석에 `"EDGAR · 2026Q2"` 또는 `"yf"` 출처. 한국 종목 행에 `"DART"` 또는 `"Naver"` 또는 `"yf"`.
**Why human:** 실제 API 키 + 네트워크 필요. 자동 테스트는 mock/openpyxl readback으로 로직 검증, 실 API 응답 불가.

### 2. 같은 주 내 2회 실행 시 콘솔 캐시 로그 확인

**Test:** 1회 실행 후 동일 주 내 재실행. 콘솔 출력 확인.
**Expected:** DART 종목에 대해 `"펀더멘털 캐시 HIT (cache HIT, ..."` 메시지 출력, DART API 호출 없음. (EDGAR 경로는 SC4 WARNING 참조 — `fetch_edgar_cached` 배선 수정 전까지 캐시 HIT 미발생 예상.)
**Why human:** 디스크 캐시 7d TTL 실동작은 사용자 환경 실행 후 로그로만 확인 가능.

### 3. EDGAR UA 헤더 403 회피 확인

**Test:** EDGAR 호출 포함 실행 후 403 에러 미발생 확인.
**Expected:** AAPL/MSFT 등 미국 티커 PER/GPM/OPM 값 정상 표시, 에러 없음.
**Why human:** SEC 정책상 실제 UA 헤더 검사는 라이브 호출에서만 확인 가능.

---

## Gaps Summary

**BLOCKER 없음.** SC1/SC2/SC3는 코드+테스트로 완전 검증.

**WARNING 1개 — ✅ RESOLVED (commit `9cfc1df`):** SC4 — EDGAR 7d 캐시 배선 누락이었음(`fundamentals._default_edgar`가 `fetch_edgar_raw` 직접 호출). **수정 완료**: `_default_edgar`가 현재 분기 "YYYYQn"(주 단위 안정) 라벨로 `fetch_edgar_cached`를 호출(DART `_default_dart`와 동일 패턴) → 같은 주 US 종목 재실행 시 캐시 HIT. 회귀 가드 `test_default_us_path_uses_edgar_cache` 추가(cached 1회·raw 0회 단언). SC4 코드 배선은 이제 EDGAR·DART 양쪽 완료. 정밀 분기/접수번호 델타는 후속 '펀더멘털 히스토리' phase에서 교체.

**Human Needed 3개:** 실제 API 키+네트워크 환경에서의 워크북 생성 확인, 캐시 HIT 로그, EDGAR 403 미발생. 이는 VALIDATION.md의 "Manual-Only Verifications" 항목과 일치.

---

_Verified: 2026-06-05T18:00:00+09:00_
_Verifier: Claude (gsd-verifier)_
