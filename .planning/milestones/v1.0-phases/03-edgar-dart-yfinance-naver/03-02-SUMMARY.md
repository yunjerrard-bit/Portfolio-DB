---
phase: 03-edgar-dart-yfinance-naver
plan: 02
subsystem: io-fundamentals
tags: [spike, edgar, dart, naver, yfinance, fixtures, fundamentals]
requires: ["03-01 (throttle/cache 확장)"]
provides:
  - "DART_ACCOUNT_ID_MAP / DART_ACCOUNT_MAP 상수 (실데이터 확정)"
  - "EDGAR/DART/Naver/yfinance mock fixture 4종 (Wave 3/4 단위테스트 입력)"
  - "A1~A7 확정 결과 (03-SPIKE-FINDINGS.md)"
affects:
  - "Wave 3: edgar_client.py / dart_client.py / naver_scraper.py / yf_fundamentals.py"
tech-stack:
  added: []
  patterns:
    - "edgartools 5.x EntityFacts 타입드 접근자(get_revenue/get_ttm 등) — to_pandas 부재"
    - "DART account_id 1차 / account_nm 2차 매핑"
    - "Naver UTF-8 디코딩 (euc-kr 가정 반증)"
key-files:
  created:
    - src/stocksig/io/dart_account_map.py
    - tests/fixtures/edgar_aapl_facts.py
    - tests/fixtures/dart_005930_finstate.py
    - tests/fixtures/naver_005930.html
    - tests/fixtures/yf_info_sample.py
    - .planning/phases/03-edgar-dart-yfinance-naver/03-SPIKE-FINDINGS.md
  modified: []
decisions:
  - "EDGAR 4지표 취득은 EntityFacts 타입드 접근자 경로 채택(facts.to_pandas 5.35.0 부재)"
  - "DART 매핑 1차키=account_id(표준태그), 2차키=account_nm(한글 라벨)"
  - "Naver 인코딩 UTF-8로 확정(RESEARCH euc-kr 가정 정정)"
metrics:
  duration: "~25분"
  completed: "2026-06-04"
  tasks: 1
  files: 6
requirements: [FUND-01, FUND-03]
---

# Phase 3 Plan 02: 실데이터 검증 스파이크 Summary

A1~A7 가정을 AAPL/MSFT/GOOGL(EDGAR) + 005930(DART·Naver) + AAPL/005930.KS(yfinance) 라이브 호출로 전부 [VERIFIED] 확정하고, 확정 상수(`dart_account_map.py`)와 Wave 3/4 단위테스트용 mock fixture 4종을 작성했다.

## 무엇을 했나

- **A1 (edgartools 5.x 경로):** `Company(tk).get_facts()` → `EntityFacts` 타입드 접근자(`get_revenue/get_gross_profit/get_operating_income/get_net_income/get_ttm_revenue/get_ttm_net_income/get_ttm("EarningsPerShareDiluted")`)가 4지표를 가장 안정적으로 채움을 확정. RESEARCH가 가정한 `facts.to_pandas("us-gaap:...")`는 5.35.0에 부재(AttributeError)임을 반증.
- **A2 (concept tag):** EPS=`get_ttm("EarningsPerShareDiluted")`, Revenue=`get_ttm_revenue()`(get_ttm("Revenues")는 stale → 금지), GPM=`get_gross_profit()`(GOOGL=None 결손 케이스 확인 → yf 폴백 필요).
- **A3/A6 (DART):** 005930 2025 사업보고서 연결 229행 실호출. account_id 1차/account_nm 2차 매핑 확정(매출액=ifrs-full_Revenue 등). 6자리 stock_code 직접 수용·corp_code(00126380) 내부 해석 확인. fs_div는 응답 컬럼 아닌 요청 파라미터.
- **A4 (yfinance .info):** US 전 키 존재, KR(005930.KS) trailingPE 결손이나 GPM/OPM/PEG 존재. PEG=pegRatio 우선·trailingPegRatio 폴백.
- **A5 (Naver):** `#_per`=28.94/`#_eps`=12,372/`#_pbr`=4.98 확정. **인코딩 UTF-8**(euc-kr 가정 반증). GPM/OPM 미노출.
- **A7 (quarter_label):** EDGAR=TTMMetric.periods[-1]→"2026Q2", DART=bsns_year+reprt_code→"2025-11011".
- 상수 `dart_account_map.py` + fixture 4종 작성, 전 fixture import·재구성·셀렉터 파싱 검증.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Naver 인코딩 euc-kr → UTF-8 정정**
- **Found during:** Task 1 (A5 Naver 스파이크)
- **Issue:** RESEARCH/PLAN의 `r.encoding="euc-kr"` 가정으로 디코드 시 한글 깨짐. 실페이지는 `charset=utf-8` 선언, euc-kr/cp949 디코드 시 `UnicodeDecodeError`.
- **Fix:** fixture·SPIKE-FINDINGS에 UTF-8로 확정 기록. naver_scraper(Wave 3)는 `r.content.decode("utf-8")` 사용하도록 정정 명시.
- **Files:** tests/fixtures/naver_005930.html, 03-SPIKE-FINDINGS.md §A5
- **Commit:** f1d015a

**2. [Rule 2 - 누락 핵심] DART 매핑 1차키를 account_id로 보강**
- **Found during:** Task 1 (A3 DART 스파이크)
- **Issue:** PLAN 시드는 account_nm(한글 라벨) 단일 매핑. account_nm은 회사 재량 라벨이라 업종 간 변동 → 결손 위험.
- **Fix:** `DART_ACCOUNT_ID_MAP`(표준 account_id 1차) + `DART_ACCOUNT_MAP`(account_nm 2차 폴백) 이중 매핑으로 보강. 안정성 향상.
- **Files:** src/stocksig/io/dart_account_map.py
- **Commit:** f1d015a

**3. [Rule 1 - Bug] EDGAR EPS/Revenue 취득 메서드 정정**
- **Found during:** Task 1 (A1/A2)
- **Issue:** `facts.to_pandas(...)` 부재, `get_concept/get_fact` bare name 미인식, `get_ttm("Revenues")` stale 기간 선택.
- **Fix:** EPS=`get_ttm("EarningsPerShareDiluted")`, Revenue=`get_ttm_revenue()` 로 확정. fixture에 정확 경로·값 기록.
- **Files:** tests/fixtures/edgar_aapl_facts.py, 03-SPIKE-FINDINGS.md §A1/A2
- **Commit:** f1d015a

## 인증 게이트 / 체크포인트

- Task 0(checkpoint:human-action — .env + 네트워크): 오케스트레이터가 사전 승인·확인(uv·.venv·PyPI·EDGAR/DART 키 SET). 정상 흐름으로 통과, executor에서 추가 대기 없음.
- 라이브 외부 API 4종(EDGAR/DART/Naver/yfinance) 전부 호출 성공 — UNVERIFIED 폴백 경로 미발동.

## 검증 결과

- `uv run python -c "from stocksig.io.dart_account_map import DART_ACCOUNT_MAP; assert 'revenue' in ... and 'eps' in ..."` → 종료코드 0, len=5.
- fixture 4종 import·재구성·셀렉터 파싱 검증 통과(edgar EPS_TTM=8.07/quarter_label=2026Q2, dart df 9×18/revenue=333605938000000, naver #_per=28.94/#_eps=12,372, yf AAPL trailingPE=37.6/KR=None).
- 03-SPIKE-FINDINGS.md A1~A7 전부 [VERIFIED] 기록, [UNVERIFIED] 0건.

## 보안 (T-03-03/04/05)

- OPENDART_API_KEY·UA 이메일 평문 노출 0건(fixture·SUMMARY·SPIKE-FINDINGS·로그·커밋).
- 임시 스파이크 스크립트·출력 JSON 전부 삭제(git 미추적, 커밋 미포함).
- Naver 파싱은 텍스트 추출 + `float(t.replace(",",""))` 가드 전제(T-03-04).

## 비고

- `.planning/`은 .gitignore + commit_docs=false → 03-SPIKE-FINDINGS.md·본 SUMMARY는 로컬 문서(git 미추적). 코드/fixture 5종만 atomic commit(f1d015a).
- 사전 존재 untracked `docs_cache/`는 본 작업 범위 외 — 손대지 않음.

## Self-Check: PASSED

- 파일 6종 전부 FOUND.
- 커밋 f1d015a 존재 확인(5 files changed, 401 insertions).
