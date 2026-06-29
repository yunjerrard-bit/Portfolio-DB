---
phase: quick-260629-hec
plan: 01
subsystem: io/edgar_client + data store
status: complete
tags: [bugfix, FUND-07, FUND-11, edgar, edgartools-5.35.0, data-reload]
requires:
  - edgar_client.fetch_edgar_quarterly_raw
  - edgar_client._query_facts
  - edgar_client._calendar_quarter_key
  - data/fundamentals.db (raw_facts, delta_state)
provides:
  - edgartools 5.35.0 by_period_type 마이그레이션 (quarterly + 파이썬 instant 필터)
  - period_end 월 기반 캘린더 분기키 (YYYYQn fullmatch 가드 유지)
  - _query_facts WARNING 로깅 (조용한 except 제거)
  - 중복 fact filing_date 정렬
  - US 105종목 raw_facts 전수 재적재 (분기×9필드)
affects:
  - history 경로 compute_matrix 분기축 (US 종목 데이터 공급)
tech-stack:
  added: []
  patterns:
    - "by_period_type('quarterly') ≡ by_period_length(3) — 내부 위임(edgartools 5.35.0)"
    - "instant(BS)은 by_concept().execute() 후 파이썬 period_type=='instant' 필터"
    - "period_end 월 → (month-1)//3+1 캘린더 분기키"
key-files:
  created: []
  modified:
    - src/stocksig/io/edgar_client.py
    - tests/fixtures/edgar_aapl_facts.py
    - tests/test_edgar_quarterly.py
    - tests/test_raw_semantics_spike.py
    - data/fundamentals.db
    - .gitignore
decisions:
  - "by_period_type 어휘 변경({annual,quarterly,monthly,ttm,ttm,ytd}만 유효, duration/instant 폐기)에 quarterly 마이그레이션 + 파이썬 instant 필터로 대응. 소스 검증 완료(LOCKED FACTS)."
  - "백로그 1단계의 '이유'(period_length=None→0) 정정 — 실제 결손 원인은 by_period_type('duration') ValidationError. 조치(quarterly)는 동일하게 유효."
  - "_calendar_quarter_key 키 소스를 period_end 월 기준으로 교체(docstring 계약 일치). period_end 부재 시 get_display_period_key 차선책 + YYYYQn fullmatch 가드 유지."
  - "전수 재동기화는 메인 트리에서 오케스트레이터가 직접 수행(워크트리 비활성 — 라이브 EDGAR + .venv 마찰 회피)."
  - "발견된 EDGAR Q4 갭/TTM-None 은 별개 근본원인 → 새 backlog edgar-q4-gap-ttm-none.md 로 인계(본 스코프 외)."
metrics:
  completed: 2026-06-29
  tasks: 3
  files: 6
  commits: 3
---

# Quick 260629-hec: edgartools 5.35.0 by_period_type 마이그레이션 (US 펀더멘털 전 결손 수정 + 재적재) Summary

`edgartools` 5.35.0 에서 `FactQuery.by_period_type` 의 유효 어휘가 `{annual, quarterly, monthly, ttm, ytd}` 로 바뀌어 `"duration"`·`"instant"` 가 `ValidationError` 를 던지고, 이를 `_query_facts` 의 조용한 `except Exception: return []` 가 삼켜 **US 전 종목 재무필드 9종이 전 결손**(종목당 `shares_outstanding` 1행만 생존)되던 버그를 수정했다. 유량은 `by_period_type("quarterly")`(= 내부 `by_period_length(3)`), 저량(BS)은 `by_concept().execute()` 후 파이썬 `period_type=='instant'` 필터로 마이그레이션하고, 분기키를 `period_end` 월 기반으로 교체, 조용한 except 를 WARNING 로깅으로 바꾸고, 중복 fact 를 `filing_date` 로 정렬했다. 코드 수정 후 US 125종목을 전수 재적재해 **105종목이 분기×9필드를 회복**했다.

## 착수 전 진단 전제 검증 (오케스트레이터, 소스 레벨)

핸드오프 문서가 다른 PC 작성이라, 이 PC `.venv` 의 edgartools 5.35.0 소스를 직접 읽어 6단계 수정안의 전제를 확정했다:
- `edgar/enums.py` `PeriodType` = `{annual, quarterly, monthly, ttm, ytd}` → `validate_period_type("duration")`·`("instant")` 은 ValidationError(ValueError 서브). **근본 원인 확인.**
- `edgar/entity/query.py::by_period_type("quarterly")` 는 `period_mapping['quarterly']=3` → **정확히 `by_period_length(3)` 로 위임.** 따라서 현행 `.by_period_length(3)` 중복 제거.
- `latest_instant()` 는 concept당 최신 1개만 남겨 분기 히스토리 부적합 → 파이썬 instant 필터가 정답.
- **백로그 1단계 정정:** "period_length=None 때문에 0" 은 부정확(by_period_length 는 period_start/period_end 로 개월수 계산). 실제 결손은 오직 `by_period_type("duration")` 예외. 조치는 동일하게 유효.

## What Was Built

- **Task 1 (코드 마이그레이션 + 회귀 테스트, TDD — 커밋 `6586935`):** `edgar_client.py` 102줄 변경.
  - 유량 6종: `_query_facts(facts, concept, "quarterly")`. `_query_facts` 시그니처에서 `period_length` 파라미터·`by_period_length` 분기 제거(중복).
  - 저량 3종(BS): `_query_facts(facts, concept, period_type=None)` (by_period_type 미적용) → 호출부 파이썬 `period_type=='instant'` 필터. `_instant_fallback` 유지.
  - `_calendar_quarter_key`: 신규 `_quarter_key_from_period_end`(period_end 월 → `(month-1)//3+1` → YYYYQn) 1순위, `get_display_period_key` 차선책, `re.fullmatch(r"\d{4}Q[1-4]")` 최종 가드 유지.
  - `_query_facts`: `except Exception as exc: logger.warning("EDGAR query 실패 concept=%s (%s)", concept, type(exc).__name__)` — 조용한 삼킴 제거(원문/PII 미포함, T-04-03).
  - 중복 정렬: `_fact_to_row` 에 `filing_date` 추가, `_row_sort_key`((quarter, field, filing_date|period_end))로 안정 오름차순 → 정정값 마지막(upsert 마지막-쓰기 승 정합). `FinancialFact.filing_date` 실재 확인(`edgar/entity/models.py:49`). `_rows_to_tuples` 는 11개 고정 키만 `r.get` → 추가 키 DB 누출 없음 확인.
  - fixture(`edgar_aapl_facts.py`) 유량 키 `(concept,"duration")`→`(concept,"quarterly")` 이동, instant 혼재 fact 추가. `test_edgar_quarterly.py` 신규 회귀 테스트(소스 grep·quarterly·instant 필터·period_end 분기키·WARNING·정렬).
- **collateral (커밋 `70ffa9a`):** `test_raw_semantics_spike.py` 의 `AAPL_QUARTERLY_STORE[("Revenue","duration")]` → `("Revenue","quarterly")` 키 정합. 의미 진실(EDGAR Q4·FY duration 부재) 불변.
- **Task 3 (전수 재적재 — 커밋 `df621f4`):** `delta_state` EDGAR 105행 정리(DELETE WHERE source='EDGAR', 멱등) → US 125종목 `sync_ticker_history(t,'EDGAR')` 재동기화(ok=125, fail=0, 129s). `.gitignore` 에 `*.db-wal`/`*.db-shm` 추가. data/fundamentals.db 933KB→7.38MB.

## Verification (actual outputs)

1. **전체 pytest:** `uv run python -m pytest -q` → **368 passed in 526.43s** (baseline 362 + 신규 6, 회귀 0).
2. **소스 grep:** `by_period_type("duration")`·`("instant")` 0건, `by_period_type("quarterly")` ≥1건.
3. **Core Value 불변:** `git diff fb48d86 -- sheet_portfolio.py·writer.py·color_rules.py` 빈 출력. 작업 전 base 대비 전체 변경 = edgar_client.py + 테스트 3종(시트1 코드 0줄).
4. **표본 라이브 회복:** AAPL 1행→**536행/73분기/10필드**, TSLA 0→**465/67/10**, MSFT 1→**605/76/10**. 종목당 1행(shares_outstanding) → 분기×9재무필드.
5. **전수 회복:** US 125종목 중 **105종목이 ≥6 재무필드 회복.** 20종목은 EDGAR 미커버(ETF: VOO/SCHD/SGOV/SPXU/SIL/COPX/BATT/MLPX, 외국 20-F/40-F: ARM/NOK/SNY/TM/TTE/SPOT/FNV/NBIS/PSNY/AXIA/RZLV, 센티넬 ZZZZZ) — CLAUDE.md 명시 범위 일치.
6. **history xlsx:** `uv run python main.py history` → `output/fundamentals_history_20260629.xlsx` 생성(4.55MB), `트렌드 렌더 실패(ValueError)` 0건(260627-vpn 가드 유지).

## Deviations / Scope Notes

- **중단 복구:** executor 가 Task 1 커밋(`6586935`) 직후 프로세스 종료로 중단. 오케스트레이터가 미커밋 collateral·Task 2 검증·Task 3 재적재·SUMMARY 를 직접 완료.
- **전수 재동기화** 는 plan Task 3 의 `main.py` 자동 실행 대신, 오케스트레이터가 `sync_ticker_history` 직접 루프로 US-EDGAR 만 재적재(OHLCV 전수 호출 회피·관찰 용이). KR(DART) delta_state 미정리 → 영향 없음.
- **⚠️ 스코프 외 발견 — 새 backlog 인계:** raw_facts 는 채워졌으나 **트렌드 셀(GPM/OPM/ROE/PER 등) 최근 분기는 여전히 "-"**. 원인은 **EDGAR Q4 갭**(4분기 중 3개만 3개월 단독 fact, Q4=연간−9M 미도출) + 잠긴 D-05(TTM 1결손=None). 제 수정으로 생긴 회귀가 아니라 US 데이터 공백에 가려져 있던 기존 설계 한계(STATE Plan 08-01 "FY−9M 보정 미구현" 일치). shares_outstanding 종목당 1행 희소성도 EPS_ttm/BPS/PER None 의 부차 원인. → `.planning/backlog/edgar-q4-gap-ttm-none.md` 로 정식 진단·인계(사용자 결정: 별도 작업 분리).

## Commits

- `6586935` fix(260629-hec): edgartools 5.35.0 by_period_type 마이그레이션 + period_end 분기키 + WARNING + 정렬 (Task 1 — edgar_client.py + fixtures + test)
- `70ffa9a` fix(260629-hec): test_raw_semantics_spike 픽스처 키 정합 (collateral)
- `df621f4` data(260629-hec): US EDGAR 펀더멘털 raw_facts 전수 재적재 + .gitignore wal/shm

## Self-Check

- FOUND: src/stocksig/io/edgar_client.py (by_period_type("quarterly"), _quarter_key_from_period_end, _row_sort_key, WARNING)
- FOUND: tests/test_edgar_quarterly.py (신규 회귀 테스트)
- FOUND: data/fundamentals.db (7.38MB, 105종목 회복)
- FOUND: output/fundamentals_history_20260629.xlsx
- FOUND commits: 6586935, 70ffa9a, df621f4
- HANDOFF: .planning/backlog/edgar-q4-gap-ttm-none.md (스코프 외 Q4 갭 인계)
