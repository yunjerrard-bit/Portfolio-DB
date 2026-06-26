---
phase: 10-1-store-registry
verified: 2026-06-23T08:30:00Z
status: passed
score: 5/5 must-haves verified
overrides_applied: 0
re_verification: false
---

# Phase 10: 1-store-registry 검증 보고서

**단계 목표:** 시트1 펀더멘털을 store/registry 단일 원천으로 이관 (FUND-11)  
**검증 일시:** 2026-06-23  
**상태:** PASSED  
**재검증 여부:** 아니오 — 초기 검증

---

## 목표-역방향 분석

FUND-11 달성을 위해 반드시 참이어야 할 사실들을 먼저 도출한 뒤, 코드베이스에서 직접 확인했다.

---

## Observable Truths (관측 가능한 사실) 검증

| # | 사실 | 상태 | 근거 |
|---|------|------|------|
| T1 | `main_run.run` 흐름이 PASS1 → SYNC → READ(store) → PASS2 순으로 재배선됨 | ✓ VERIFIED | `main_run.py` L271-334: `fundamentals_fn=None` fan-out → `sync_ticker_history` 루프 → `compute_matrix`+`inject_prices_for_quarter`+`matrix_to_fundamentals` READ 블록 → `write_portfolio_sheet` |
| T2 | 시트1 경로에서 `fetch_fundamentals`·`fetch_edgar_cached`·`fetch_dart_cached` 호출 0 | ✓ VERIFIED | grep(`fetch_fundamentals\|fetch_edgar_cached\|fetch_dart_cached` in `main_run.py`) = **0건**. 세 심볼은 소스 자체에서 제거됨(`fundamentals.py`, `edgar_client.py`, `dart_client.py` grep 결과 0) |
| T3 | READ 단계는 SQLite SELECT만(외부 API 호출 0), 인증 skip은 SYNC에만 적용 | ✓ VERIFIED | `compute_matrix`는 `fetch_raw_quarters`(SQLite SELECT)만 호출. `skip_edgar/skip_dart` grep: 주석 1건뿐(L314), READ 블록에 조건분기 없음(L7 준수). `fetch_edgar_quarterly_raw`·`fetch_dart_quarterly_raw`(L2 추출기)는 SYNC 경로에서만 사용 |
| T4 | 죽은 코드 제거 완료, 보존 계약(D-04) 무손상 | ✓ VERIFIED | 제거 대상 심볼 def 0(grep 확인). 보존 계약 7종(`MetricCell`, `FundamentalsResult`, `_empty_cell`, `_is_missing`, `_compute_per`, `_compute_peg`, `_compute_margin`) `fundamentals.py`에 전부 존재. L2 추출기 2종(`fetch_edgar_quarterly_raw`, `fetch_dart_quarterly_raw`) 각 클라이언트에 존재. OHLCV/기업명 캐시(`_DEFAULT_DIR`, `get_ohlcv`, `make_key`, `_NAME_DIR`, `get_company_name`) `cache.py`에 무손상 |
| T5 | Core Value 불변 — `sheet_portfolio.py` 0줄 변경, σ-bucket 색 신호 회귀 테스트 GREEN | ✓ VERIFIED | `git diff HEAD src/stocksig/output/sheet_portfolio.py` = **0줄**. `test_sigma_color_unchanged_after_migration` + `test_missing_db_fund_cells_blank` 두 테스트 존재, 전 스위트 포함 GREEN |

**점수: 5/5 사실 검증 완료**

---

## Required Artifacts (필수 아티팩트) 검증

| 아티팩트 | 역할 | 존재 | 실질적 내용 | 배선 | 상태 |
|---------|------|------|------------|------|------|
| `src/stocksig/io/fundamentals_view.py` | compute_matrix 최신열 → FundamentalsResult 어댑터 (D-08) | ✓ | `matrix_to_fundamentals` 함수 구현 완료(78줄), provenance 라벨·PEG source 승계·_empty_cell 빈DB 처리 포함 | `main_run.py:49` import + L327 호출 | ✓ VERIFIED |
| `src/stocksig/io/metrics_engine.py` | `compute_matrix`(SQLite READ) + `inject_prices_for_quarter`(가격 주입) | ✓ | 두 함수 L308·L347에 완전 구현 | `main_run.py:51` import + L319·L324 호출 | ✓ VERIFIED |
| `src/stocksig/io/fundamentals.py` | D-04 공유 계약(데이터 모델·결손 게이트·순수 산식) | ✓ | 106줄 — 구 fetch 오케스트레이터 제거, MetricCell/FundamentalsResult/_empty_cell/_is_missing/_compute_* 만 보유 | 트렌드·시트1·metrics_engine이 import 재사용 | ✓ VERIFIED |
| `src/stocksig/io/cache.py` | OHLCV/기업명 캐시만 보유(펀더멘털 캐시 제거) | ✓ | `_stats` dict에 `ohlcv_hit/ohlcv_miss/name_hit/name_miss` 4키만 존재. `_FUND_DIR`, `make_fund_key`, `fund_hit`, `fund_miss` 0건 | `main_run.py`에서 `cache.get_cache_stats()` 호출, fund 키 참조 없음 | ✓ VERIFIED |
| `tests/test_history_integration.py` | 단일 원천 통합 테스트(T2/T3) | ✓ | `test_run_no_legacy_fetch`(심볼 부재 단언) + `test_run_single_source`(store→시트1 값 흐름) 포함 | 전 스위트에서 실행·GREEN | ✓ VERIFIED |
| `tests/test_sheet_portfolio.py` | σ-bucket 색 신호 불변 + 빈DB 빈칸 회귀 잠금(Core Value) | ✓ | `test_sigma_color_unchanged_after_migration`(openpyxl hex 바이트 일치) + `test_missing_db_fund_cells_blank`(빈 매트릭스 → 4셀 빈칸) | 전 스위트에서 실행·GREEN | ✓ VERIFIED |

---

## Key Link Verification (핵심 연결 고리)

| From | To | Via | 상태 | 근거 |
|------|-----|-----|------|------|
| `main_run.run` SYNC | `fundamentals_delta.sync_ticker_history` | L302 직접 호출 | ✓ WIRED | `main_run.py:302` |
| `main_run.run` READ | `compute_matrix(sym)` | L319 직접 호출 | ✓ WIRED | `main_run.py:319` |
| `main_run.run` READ | `inject_prices_for_quarter(matrix, latest_q, last_close, ...)` | L324 직접 호출 | ✓ WIRED | `main_run.py:324` |
| `main_run.run` READ | `matrix_to_fundamentals(matrix, latest_q)` → `res.fundamentals` 재할당 | L327 직접 호출·재할당 | ✓ WIRED | `main_run.py:327` |
| `res.fundamentals` | `write_portfolio_sheet` | L344 호출, `results` 리스트 경유 | ✓ WIRED | `main_run.py:344`, `sheet_portfolio.py` 0줄 변경 |
| `edgar_client` | `fetch_edgar_cached` | (제거됨) | ✓ REMOVED | grep def 0건 |
| `dart_client` | `fetch_dart_cached` | (제거됨) | ✓ REMOVED | grep def 0건 |
| `fundamentals` | `fetch_fundamentals` | (제거됨) | ✓ REMOVED | grep def 0건 |

---

## Data-Flow Trace (Level 4 — 데이터 흐름)

| 아티팩트 | 데이터 변수 | 소스 | 실제 데이터 흐름 | 상태 |
|---------|-----------|------|----------------|------|
| `main_run.py` READ 블록 | `matrix` | `compute_matrix(sym)` → `fetch_raw_quarters(sym)` → SQLite SELECT | `fundamentals_store.fetch_raw_quarters`가 `data/fundamentals.db` SQLite에서 행 조회 후 반환 | ✓ FLOWING |
| `fundamentals_view.matrix_to_fundamentals` | `per/peg/gpm/opm` | `matrix[metric][latest_q]` | 매트릭스 최신 분기 열에서 MetricCell 직접 추출, 빈 분기는 `_empty_cell`로 처리 | ✓ FLOWING |
| `write_portfolio_sheet` | `res.fundamentals` | `res.fundamentals` (READ 단계 재할당) | TickerResult.fundamentals가 store 파생값으로 채워진 채로 writer에 전달됨 | ✓ FLOWING |

---

## Behavioral Spot-Checks

| 동작 | 확인 방법 | 결과 | 상태 |
|------|----------|------|------|
| `fetch_fundamentals` 심볼 부재 | `hasattr(fundamentals, "fetch_fundamentals")` 단언 (test_run_no_legacy_fetch) | False (심볼 없음) | ✓ PASS |
| `fetch_edgar_cached` 심볼 부재 | `hasattr(edgar_client, "fetch_edgar_cached")` 단언 | False | ✓ PASS |
| `fetch_dart_cached` 심볼 부재 | `hasattr(dart_client, "fetch_dart_cached")` 단언 | False | ✓ PASS |
| store 적재 → 시트1 펀더멘털 채움 | `test_run_single_source` spy 캡처 | fund is not None 단언 통과 | ✓ PASS |
| σ-bucket 색 hex 불변 | `test_sigma_color_unchanged_after_migration` openpyxl read-back | C62828·B71C1C·2E7D32·1565C0 일치 | ✓ PASS |
| 빈 DB → 4셀 빈칸 | `test_missing_db_fund_cells_blank` | D-02 동작 확인 | ✓ PASS |

---

## Requirements Coverage

| 요구사항 | 상태 | 근거 |
|---------|------|------|
| **FUND-11**: 시트1 PER/PEG/GPM/OPM이 단일 store/registry에서 계산된 값을 읽어 표시, 중복 fetch·계산 경로 제거, 두 파일 간 값 드리프트 없음, 색 신호 회귀 없음, 평소 외부 호출 ≈0 | ✓ SATISFIED | - 단일 원천: `compute_matrix`(SQLite)→`inject_prices`→`matrix_to_fundamentals`→시트1 배선 완료<br>- 중복 경로 제거: 구 3개 심볼 소스 삭제<br>- 드리프트 없음: metrics_engine이 트렌드 엑셀·시트1 공통 백엔드<br>- 색 신호 불변: `sheet_portfolio.py` 0줄 diff + hex 바이트 일치 테스트<br>- 외부 호출 ≈0: READ는 SQLite SELECT만, SYNC는 델타 probe로 대부분 skip |

---

## Anti-Pattern Scan

| 파일 | 패턴 | 심각도 | 판정 |
|------|------|--------|------|
| `main_run.py` `_FUND_DIR`, `fund_hit`, `fund_miss` | 제거 대상 잔류 여부 | — | 0건 — 완전 제거됨 |
| `cache.py` 펀더멘털 캐시 헬퍼 잔류 | 제거 완료 여부 | — | `_FUND_DIR` 등 0건 — 완전 제거됨 |
| `sheet_portfolio.py` 변경 여부 | Core Value 보호 | — | `git diff` 0줄 — 무변경 확인 |
| TBD/FIXME/XXX 마커 (Phase 10 변경 파일) | 미해결 debt | — | 해당 없음 — 검출 없음 |

---

## 전 스위트 테스트 결과

```
PYTHONPATH="." uv run pytest tests/ --tb=no -q
356 passed in 385.11s (0:06:25)
```

- **356 passed, 0 failed** — 실회귀 0
- 알려진 선존 아티팩트 3건(`test_history_cli_dispatch`, `test_default_cli_dispatch`, `test_history_cli_db_empty_exit0`)은 본 테스트 실행에서 통과 — repo root가 PYTHONPATH에 포함되어 있어 환경 조건 충족 시 전부 GREEN.

---

## Human Verification Required

없음 — 모든 사실이 자동화된 그랩/테스트로 검증됨.

---

## Deferred Items

없음 — FUND-11 관련 모든 항목이 Phase 10에서 완결됨.

선존 deferred(이전부터 기록된 것, Phase 10과 무관):
- `test_history_render.py` CLI 디스패치 3종(`test_history_cli_dispatch`, `test_default_cli_dispatch`, `test_history_cli_db_empty_exit0`): `importlib.import_module("main")` 레포 루트 sys.path 아티팩트. Phase 10 코드 변경과 무관. `deferred-items.md` 기록됨.

---

## Gaps Summary

없음.

---

## Verdict

**PASS** — FUND-11 달성. 시트1 PER/PEG/GPM/OPM이 store/registry SQLite 단일 원천에서만 산출되고, 구 fetch 3개 경로가 소스 레벨에서 완전 제거됐으며, `sheet_portfolio.py` 0줄 변경으로 Core Value(색 신호) 회귀가 구조적으로 불가능함. 전 스위트 356 passed / 0 failed.

---

*Verified: 2026-06-23T08:30:00Z*
*Verifier: Claude (gsd-verifier)*
