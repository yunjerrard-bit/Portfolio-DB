# Phase 4: 품질·견고성 마감 - Context

**Gathered:** 2026-06-11
**Status:** Ready for planning

<domain>
## Phase Boundary

일상 사용 품질로 마감하는 phase. **사용자 결정으로 "데이터 품질" 별도 시트는 만들지 않는다** — EXEC-04의 취지(이슈를 한곳에서 확인)는 콘솔 최종 실패 요약 블록 + 시트1 실패행 + 펀더멘털 셀 주석(기존 방식)으로 대체 충족한다. 신규 작업의 중심은 **시작 시 인증 사전검증(EDGAR/DART ping)**이며, 나머지는 검증·마감 성격이다: frozen panes(이미 구현됨 — 검증만), 한국어 콘솔 로그(진행률·캐시 hit/miss 통계·실패 요약), 파스텔 색상 톤 시각 검증.

**In scope:**
- 시작 시 인증 사전검증: EDGAR(UA 이메일 유효성/403 여부) + DART(API 키 유효성) ping — 신규 기능
- OUT-04 frozen panes 검증: `sheet_per_ticker.py:438` `freeze_panes(5, 0)`, `sheet_portfolio.py:303` `freeze_panes(5, 1)` 이미 존재 — 동작 확인만
- EXEC-04 대체 충족: 콘솔 최종 실패 요약 블록 + 캐시 hit/miss 집계 통계 (로드맵 SC3)
- COLOR-07/SC4 색상 톤 검증: 파스텔/소프트 톤 + 그레이스케일 ±1σ/±2σ 구분 가능성

**Out of scope:**
- "데이터 품질" 별도 시트 (사용자 결정 D-01로 미생성 — 아래 참조)
- 새 지표·새 컬럼·새 데이터 소스 (다른 phase)
- 자동 스케줄링 (v2 SCHED)

</domain>

<decisions>
## Implementation Decisions

### 데이터 품질 시트 (EXEC-04)

- **D-01 (시트 미생성, 콘솔 요약으로 대체):** 사용자 결정 — 데이터 품질 시트를 만들지 않는다. 현재 방식 유지: 티커 실패는 시트1 실패행(D-03 from Phase 2), 펀더멘털 결손은 셀 주석(D-05 from Phase 3)으로 이미 워크북 안에서 확인 가능. EXEC-04의 "이슈 한곳 확인" 취지는 **콘솔 최종 실패 요약 블록**으로 충족된 것으로 재정의. REQUIREMENTS.md의 EXEC-04와 ROADMAP.md Phase 4 성공 기준 2번은 이 결정에 맞게 갱신 필요(plan-phase에서 반영).

### 시작 시 인증 사전검증 (Phase 3에서 이월된 deferred idea)

- **D-02 (실패 시 동작 = 경고 후 계속):** 인증 ping 실패(DART 키 만료, EDGAR 403 등) 시 한국어 경고를 출력하고 실행은 계속한다. 시세·시트 생성은 정상 진행, 해당 소스 펀더멘털만 결손 처리(셀 주석에 "인증 실패" 계열 사유). 펀더멘털 결손 ≠ 티커 실패(D-disc-10) 원칙과 일관. fail-fast 아님.
- **D-03 (ping 주기 = 매 실행 시작 시):** 캐시 없이 매 실행 시작 시 1회씩 ping. EDGAR 1회 + DART 1회는 200티커 실행 대비 무시할 수준의 비용이며 항상 최신 인증 상태를 반영.
- **D-04 (검증 범위 = EDGAR + DART 둘 다, 조건부):** EDGAR는 UA 이메일 유효성(403 여부), DART는 API 키 유효성을 확인. 단 tickers.txt에 해당 시장 티커가 있을 때만 각각 ping (US 티커 없으면 EDGAR ping 생략, KR 티커 없으면 DART ping 생략).

### Claude's Discretion

사용자가 재량으로 위임한 영역 — researcher/planner가 결정:

1. **콘솔 로그·캐시 통계 형식:** 캐시 hit/miss 집계 통계 표시 형태(OHLCV/펀더멘털 분리 또는 합산), 최종 실패 요약 블록 포맷, 200티커 시 per-call HIT/MISS 로그 유지 여부. 기존 한국어 로그 패턴(`[k/N] OK <ticker>`, `총 N 중 성공 X / 실패 Y`)을 깨지 않는 선에서 확장. rich 진행바 도입 여부도 재량(STACK.md는 권장하나 필수 아님).
2. **색상 톤 검증·조정:** 현행 Material 팔레트(GREEN_800 #2E7D32 / RED_800 #C62828 글자 + GREEN_100 #C8E6C9 / RED_100 #FFCDD2 배경)가 "강렬하지 않은 톤" 기준 충족하는지 시각 검증. 그레이스케일 ±1σ/±2σ 구분 검증 방법(수기 스크린샷 vs 자동 휘도 계산 테스트)도 재량. 조정 필요 시 단일 진원지 `compute/color_rules.py` 상수만 변경.
3. **ping 엔드포인트 선정:** EDGAR/DART 각각 가장 가벼운 검증 호출(예: DART `/list.json` 1건, EDGAR company-facts 소형 요청 등). 기존 토큰버킷(`@throttled_edgar` 8 RPS / `@throttled_dart` 2 RPS) 경유 여부 포함.
4. **인증 실패 시 펀더멘털 fetch 스킵 최적화:** ping 실패한 소스에 대해 본 실행에서 per-ticker 펀더멘털 호출을 아예 건너뛸지(불필요한 재시도·throttle 대기 절약), 아니면 개별 호출에 맡길지.

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 프로젝트 기준 문서
- `.planning/PROJECT.md` — Core Value, Constraints ("강렬하지 않은 톤" 기준), Key Decisions
- `.planning/REQUIREMENTS.md` §OUT-04, §EXEC-04, §COLOR-07, §EXEC-05 — Phase 4 관련 요구사항 전문 (D-01에 따라 EXEC-04 갱신 필요)
- `.planning/ROADMAP.md` §"Phase 4" — Goal, Success Criteria 4개 (SC2는 D-01에 따라 갱신 필요)

### 이전 phase 결정 (재사용)
- `.planning/phases/03-edgar-dart-yfinance-naver/03-CONTEXT.md` — D-05 결손 셀 표시(빈 칸 + 주석), D-07 네이버 캡, D-disc-10 펀더멘털 결손 ≠ 티커 실패, deferred "API 키/UA 자동 검증"(이 phase의 D-02~D-04로 채택됨)
- `.planning/phases/02-scaling-portfolio-summary/02-CONTEXT.md` — D-02 색 단일 진원지(color_rules), D-03 실패행 표기, 한국어 로그 패턴

### 기존 코드 (검증·확장 대상)
- `src/stocksig/output/sheet_per_ticker.py` L438 — `ws.freeze_panes(5, 0)` 이미 구현 (OUT-04 검증 대상)
- `src/stocksig/output/sheet_portfolio.py` L303 — `ws.freeze_panes(5, 1)` 이미 구현 (행 1~5 + A열 고정)
- `src/stocksig/io/cache.py` — 캐시 HIT/MISS 한국어+영문 per-call 로그 존재 (집계 통계는 없음 — 추가 대상)
- `src/stocksig/runner.py` — `[k/N] OK/FAIL` 진행 로그 + `총 N 티커 중 성공 X / 실패 Y` 요약 존재, `TickerFailure(spec, reason)` 실패 수집 구조
- `src/stocksig/main_run.py` — 한국어 메인 로그 + 실패 목록 경고 출력, ping 삽입 지점(티커 로드 직후) 후보
- `src/stocksig/io/throttle.py` — `@throttled_edgar`(8 RPS) / `@throttled_dart`(2 RPS) — ping 호출도 같은 버킷 경유 가능
- `src/stocksig/compute/color_rules.py` L15-27 — 색 상수 단일 진원지 (GREEN/RED/BLUE 800·900·100)
- `src/stocksig/config.py` — `.env` 로드 (`EDGAR_USER_AGENT_EMAIL`, `OPENDART_API_KEY`) — ping이 사용할 자격증명 소스
- `src/stocksig/io/fundamentals.py` — `MetricCell(value, note)` 결손 사유 구조 — "인증 실패" 사유 추가 지점

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- **frozen panes 이미 구현:** 양쪽 시트 작성기 모두 `freeze_panes` 적용 완료. OUT-04는 신규 코드가 아니라 실파일 검증(수기 또는 openpyxl 읽기 테스트) 항목.
- **`TickerFailure` 수집 구조:** `runner.run_all`이 `(results, failures)` 튜플로 실패를 사유와 함께 이미 수집 — 콘솔 최종 요약 블록의 데이터 소스로 그대로 사용 가능.
- **캐시 per-call 로그:** `cache.py`가 HIT/MISS를 건별 로깅 — 집계 카운터(예: 모듈 레벨 카운터 또는 반환값 집계)만 추가하면 SC3 통계 충족.
- **throttle 데코레이터:** ping 함수에 `@throttled_edgar`/`@throttled_dart` 재사용 가능.

### Established Patterns
- **한국어 로그:** `logging` 모듈 + `[k/N] OK <ticker>` / `총 N 중 성공 X / 실패 Y` 패턴. 신규 ping·통계 로그도 동일 형식 유지.
- **색 단일 진원지:** 팔레트 변경이 필요하면 `color_rules.py` 상수만 수정 — writer/시트 코드는 무변경.
- **예외 흡수 원칙:** 펀더멘털 경로의 예외는 흡수하고 시세 흐름 보호 (D-disc-10) — ping 실패도 같은 원칙으로 경고만.

### Integration Points
- **`main_run.py` 시작부 (티커 로드 직후):** 인증 사전검증 삽입 지점. `classify_market`으로 US/KR 티커 존재 여부 판단 → 조건부 ping.
- **`main_run.py` 종료부:** 캐시 통계 + 최종 실패 요약 블록 출력 지점.
- **`fundamentals.py` / `runner.py` PASS 1b:** ping 실패 소스의 펀더멘털 스킵 플래그 전달 경로 (Claude 재량 4번).

</code_context>

<specifics>
## Specific Ideas

- 인증 실패 사유 주석은 기존 한국어 사유 매핑 패턴을 따름 (예: `"조회 실패: DART 인증 실패"`, `"조회 실패: EDGAR 403 (UA 확인)"`).
- 무인/스케줄 실행 호환을 위해 사용자 입력 대기(프롬프트)는 두지 않음 — 경고 후 자동 계속 (D-02에서 명시 선택).

</specifics>

<deferred>
## Deferred Ideas

- **데이터 품질 별도 시트 (EXEC-04 원형):** 사용자 결정으로 v1에서 미생성. 콘솔 요약으로 대체 충족. 추후 필요해지면 `TickerFailure` + `MetricCell.note` 수집 구조가 이미 있어 시트 추가는 작은 작업.
- **rich 진행바:** STACK.md 권장이나 도입 여부는 Claude 재량 — 도입하지 않아도 SC3 충족 가능.

### Reviewed Todos (not folded)
없음 — `gsd-sdk query todo.match-phase 4` 매치 0건.

</deferred>

---

*Phase: 4-quality-robustness*
*Context gathered: 2026-06-11*
