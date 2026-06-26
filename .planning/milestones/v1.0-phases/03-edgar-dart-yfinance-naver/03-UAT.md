---
status: complete
phase: 03-edgar-dart-yfinance-naver
source: [03-01-SUMMARY.md, 03-02-SUMMARY.md, 03-03-SUMMARY.md, 03-04-SUMMARY.md, 03-05-SUMMARY.md]
started: 2026-06-05
updated: 2026-06-05
---

## Current Test

[testing complete]

## Tests

### 1. 클린 재실행 (cold start)
expected: Excel 닫고 `uv run python main.py` 재실행 → 에러 없이 `완료: output/portfolio_20260605.xlsx` 생성. 콘솔 진행 로그 정상, ZZZZZ만 실패.
result: pass

### 2. 시트1 시세 컬럼 복구 (OHLCV NaN-trim fix)
expected: 새 workbook 시트1에서 실패했던 컬럼 — 최신종가(E)·전일등락률(F)·DIFF EMA(G~J)·거래량(K)·(일)Stoch(L)·(주)Stoch/RSI/임펄스(N/O/Q) — 가 대부분 종목에서 채워진다. 최신종가는 각 종목의 마지막 유효 거래일(미정산 NaN 봉이 잘려 06-03~06-04) 기준.
result: pass

### 3. 시트1 펀더멘털 — 미국 (PORT-05 / FUND-01·02·05)
expected: 시트1 미국 티커(AAPL 등) 행의 R/S/T/U(PER/PEG/GPM/OPM)에 숫자가 채워지고, 셀 위에 마우스를 올리면 출처 주석(예: "EDGAR" 또는 "yf")이 보인다. 결손 지표는 빈칸 + 사유 주석.
result: pass

### 4. 시트1 펀더멘털 — 한국 (FUND-03·05, D-04/D-07)
expected: 시트1 한국 티커(005930.KS·011070.KS) 행의 R/S/T/U에 값이 채워지고 출처 주석이 "DART"(결손 시 PER만 "Naver", GPM/OPM은 "yf")로 표시. 네이버는 PER만, 소수 폴백 전용.
result: pass

### 5. 캐시 HIT 재실행 (FUND-04 / MKTD-05)
expected: 방금 실행 직후 한 번 더 `uv run python main.py` 실행 → 콘솔에 OHLCV "캐시 HIT" 및 EDGAR/DART "펀더멘털 캐시 HIT" 로그가 다수 보이고 외부 API 호출이 거의 없이 빠르게 끝난다. (EDGAR UA 403/quota 에러 없음 = UA 헤더 정상.)
result: pass

## Summary

total: 5
passed: 5
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
