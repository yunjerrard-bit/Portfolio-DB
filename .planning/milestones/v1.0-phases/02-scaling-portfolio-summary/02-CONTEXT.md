# Phase 2 Context — N개 티커 스케일링 + 포트폴리오 요약 시트

**Created:** 2026-05-22
**Source:** STATE.md Phase 2 backlog (사용자 결정) + ROADMAP Phase 2 Success Criteria + RESEARCH.md

> 본 phase는 `/gsd:discuss-phase` 인터랙티브 세션 없이, 사용자가 STATE.md 및 본 plan-phase 호출 메시지에서 직접 잠근 8개 결정을 입력으로 사용한다.

## Decisions (locked — non-negotiable)

- **D-01** (tickers.txt 마이그레이션): 단일 컬럼 행 = 후방 호환 (티커만, tier/industry = `""`). 탭 또는 공백 구분 모두 허용. `#` 시작 줄 = 주석 skip. 빈 줄 skip.
- **D-02** (시트1 EMA σ 신호 소스): `decide_sigma_bucket(DIFF_Close_{N}, DIFF_Close_{N}_median, DIFF_Close_{N}_std)` 사용. 종목 시트의 DIFF 컬럼 색과 정확히 일치. **단일 source of truth = `compute/color_rules.decide_sigma_bucket`** (Phase 1에서 정의됨).
- **D-03** (실패 티커 시트1 반영): 시트1에 실패 행 포함. 형식: `티커 | "실패" | 이유` (예: 네트워크 오류, 부분 데이터 <50%). 콘솔 한국어 경고 + xlsx 시각 트레일 모두. RESEARCH.md L-08의 "시트1 제외" 안을 **사용자 결정으로 override** — Phase 4 데이터 품질 시트와 별도로 시트1에도 표시.
- **D-04** (Yahoo throttle): 2 req/s 토큰버킷 (`pyrate-limiter`). max_workers=4와 결합.
- **D-05** (캐시): `.cache/` 프로젝트 루트 디렉터리. `diskcache` sqlite 백엔드, 24h TTL. 키 = `(ticker, today_iso)`.
- **D-06** (부분 데이터 임계): 거래일 수 < 예상 2500의 50% → 실패 처리 (시트1에 "부분 데이터" 사유로 기록).
- **D-07** (신규 패키지 승인): `diskcache>=5.6`, `pyrate-limiter>=3` 둘 다 `uv add`.
- **D-08** (시트1 컬럼 순서):
  티커(하이퍼링크) | 시장 | 티어 | 산업 | 최신 종가 | 전일 등락률 | DIFF Close vs EMA11 (값+색) | DIFF Close vs EMA22 | DIFF Close vs EMA96 | DIFF Close vs EMA192 | 거래량 색 | (일)Stoch %K | (일)RSI | (일)임펄스 | (주)임펄스
  실패 행: 티커 + "?" (시장) + 빈 컬럼 + 마지막 컬럼 `실패: <사유>` (pastel red bg + italic).

## Deferred Ideas (out of scope — Phase 3/4)

- PER/PEG/GPM/OPM 컬럼 — Phase 3 (PORT-05, FUND-*)
- 데이터 품질 전용 시트 — Phase 4 (EXEC-04)
- frozen panes 1~5행 — Phase 4 (OUT-04)
- 색상 톤 그레이스케일 검증 — Phase 4
- 캐시 hit/miss 통계 시트 표시 — 콘솔만, Phase 4 시트
- `yf.download` 일괄 배치 — v2 PERF-01

## Claude's Discretion

- 시트1 상단 1행 레이아웃 (타임스탬프 단독 vs merge vs 부가 통계). 기본: 1행 = "실행 시각: YYYY-MM-DD HH:MM:SS", 2~4행 빈, 5행 헤더 — Phase 1 시트와 동일 컨벤션.
- `runner.py` vs `pipeline.py` 모듈명 — `runner.py` (RESEARCH 권장).
- 실패 사유 한국어 매핑 (네트워크/형식/부분/타임아웃 등).
- 시트1 색이 적용된 셀의 num_format 선택 (DIFF는 `percent_ratio`, EMA 값은 `price`, %K/RSI는 `percent_literal`, 임펄스는 string).
- Format 캐시 신규 키 (`failed_row`, 필요 시 `portfolio_title`/`portfolio_timestamp` — 기존 `a1_title`/`header` 재사용 가능 여부 확인).

## Multi-Source Coverage Audit

| Source | Item | Plan |
|--------|------|------|
| GOAL (ROADMAP) | 시트1 = 첫 시트, 모든 티커 한 행씩 | 02-03, 02-04 |
| GOAL | 미국·한국 혼합 N개 → 개별 시트 + 시트1 색 | 02-03, 02-04 |
| GOAL | 하이퍼링크 + 실행 시각 타임스탬프 | 02-03 |
| GOAL | 실패 티커 → 한국어 경고 + xlsx 트레일 | 02-02, 02-03, 02-04 |
| GOAL | 24h sqlite 캐시 hit/miss 로그 | 02-01, 02-02 |
| GOAL | 100 티커 rate-limit 위반 없이 완료 | 02-01, 02-02, 02-04 |
| REQ | INPUT-04 (잘못된 형식 격리) | 02-02 (`runner.py` try/except) |
| REQ | MKTD-04 (수신 실패 격리) | 02-02 |
| REQ | MKTD-05 (sqlite 캐시 24h) | 02-01, 02-02 |
| REQ | MKTD-06 (행 수 <50% 경고) | 02-02 |
| REQ | PORT-01~04, 06, 07, 08 | 02-03 |
| REQ | TECH-07 (시트1 Stoch/RSI 색) | 02-03 |
| REQ | EXEC-03 (max_workers=4 + throttle) | 02-02 |
| REQ | EXEC-05 (한국어 로그) | 02-02, 02-04 |
| RESEARCH | Pattern 1 (tickers.txt 확장) | 02-02 |
| RESEARCH | Pattern 2 (diskcache 24h) | 02-01 |
| RESEARCH | Pattern 3 (pyrate-limiter 2 RPS) | 02-01 |
| RESEARCH | Pattern 4 (ThreadPool fan-out + 격리) | 02-02 |
| RESEARCH | Pattern 5 (write_portfolio_sheet) | 02-03 |
| RESEARCH | Pattern 6 (classify_market US/KR) | 02-02 |
| RESEARCH | Pattern 7 (2-pass main_run) | 02-04 |
| RESEARCH | `.cache/` to .gitignore | 02-01 |
| RESEARCH | Format cache 신규 키 (failed_row) | 02-03 |
| CONTEXT | D-01~D-08 모두 위 plans에 분산 | 02-01..05 |
| CONTEXT (backlog) | 티어/산업 컬럼 (PORT-09/10 슬롯) | 02-03 |
| CONTEXT (backlog) | (일/주)임펄스 컬럼 (PORT-11/12 슬롯) | 02-03 |

**Gaps:** 없음. 모든 source item이 plan에 매핑됨.
