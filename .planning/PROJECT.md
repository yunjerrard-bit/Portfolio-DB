# 표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트

## What This Is

표준편차를 활용한 매매 신호와 보유 종목을 한 눈에 관리할 수 있는 엑셀(.xlsx) 워크북을 자동 생성하는 개인용 주식 분석 도구입니다. 사용자가 보유/관심 종목 티커 목록을 입력하면, Python이 Yahoo Finance에서 10년치 시세를 받아오고 EMA·표준편차·중앙값을 계산해 종목별 시트와 통합 포트폴리오 시트를 만들어 줍니다. 사용자는 개인 투자자(본인) 한 명이며, 매매 판단의 시각적 보조 도구로 사용합니다.

## Core Value

**중앙값 ± 표준편차를 기준으로 한 색상 신호가 통합 포트폴리오 시트에서 정확하고 직관적으로 보여야 한다.** 이것이 무너지면 다른 모든 기능은 의미가 없습니다.

## Current Milestone: v1.3 펀더멘털 히스토리 & 델타 추출

**Goal:** Phase 3의 "매 실행 전종목 fetch + 7일 캐시 + 최신값 표시" 위에, 펀더멘털을 영구 히스토리로 누적·트렌드로 보여주고 분기 경계(새 분기·정정공시)에서만 외부를 호출하도록 확장한다. Core Value(색 신호)는 불변 — 별도 트렌드 산출물 추가.

**Target features (백로그 fundamentals-history-delta.md D-H1~D-H4, locked):**
- **SQLite 영구 저장** (`data/fundamentals.db`): 분기별 원천 raw long 테이블 + 델타용 state 테이블 (TTL 없음, `.gitignore`, 기존 `.cache/`와 별개)
- **접수번호 기반 델타 감지** (EDGAR accession / DART rcept_no): `last_accession` 비교로 같으면 외부 전체호출 생략(평소 ≈0), 다르면 새 분기 또는 정정공시 → 전체 facts 추출·누적
- **지표 registry** (저량/유량 TTM/하이브리드): 최종 지표가 아닌 분기별 원천 raw(매출·영업이익·순이익·EPS·자본총계 등)를 누적 → ROE·PBR 등 신규 지표 무재호출 계산
- **트렌드 엑셀** (`fundamentals_history.xlsx`, 별도 파일): 지표별 시트(행=종목·열=분기) + `[원천]` + `[최신 스냅샷]`. 과거 PER/PBR은 분기말 종가, 최신만 현재가. 서식·파일 정책 세부는 discuss-phase에서 확정.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- ✓ 기본적 분석 데이터는 미국 종목 EDGAR(SEC) 최우선, 한국 종목 DART 최우선 + yfinance/네이버 보완 — **Phase 3 (UAT 5/5, 2026-06-05).** 시트1 PER/PEG/GPM/OPM + 셀 주석 출처. 네이버 D-07 제약.
- ✓ `tickers.txt`에 보유/관심 티커를 적으면 스크립트가 읽어 워크북 생성 — **v1.0**
- ✓ 미국(NYSE/NASDAQ)·한국(KOSPI/KOSDAQ) 지원, 한국은 `.KS`/`.KQ` 접미사 직접 입력 — **v1.0**
- ✓ 종목마다 개별 시트 생성, A1=티커, 그 티커로 Yahoo 조회 — **v1.0**
- ✓ 개별 시트 10년치(`today()-4000d`) OHLCV 내림차순 6행부터 — **v1.0**
- ✓ EMA11/22/96/192를 종가·고가·저가에 각각 계산 — **v1.0**
- ✓ OHLC와 각 EMA의 차이 + EMA 일별 변동 2차 가공 — **v1.0**
- ✓ 누적 중앙값 3행 / 누적 표준편차 4행 + 일별 중앙값·표준편차 열 — **v1.0**
- ✓ 색상 신호 정적 베이킹: ±1σ 글자색 / ±2σ 글자+배경, 강렬하지 않은 파스텔 톤 — **v1.0 (UAT 7/7, WCAG 휘도 검증)**
- ✓ 시트1 통합 포트폴리오: 최신 종가·등락률·EMA 신호색·PER/PEG/GPM/OPM·거래량 신호 — **v1.0**
- ✓ 매 실행 새 파일 `portfolio_YYYYMMDD.xlsx` — **v1.0**
- ✓ `python main.py` 한 줄 실행, Windows 로컬 — **v1.0**
- ✓ 주봉 임펄스를 금요일-대-금요일 주간 신호로 산출 + 주중 행 고정(주 단위 계단형) — **v1.1 (Phase 5, 2026-06-16)**
- ✓ 시트1 티커·시장 사이 영문 기업명(Company) B열 (yfinance 일괄 조회, 한국 종목도 영문) — **v1.2 (Phase 6, 2026-06-16)**

### Active

<!-- Current scope (v1.3). Building toward these. -->

- [ ] 펀더멘털 영구 히스토리 저장 (SQLite `data/fundamentals.db`, 분기별 원천 raw + state) (v1.3 / FUND-07)
- [ ] 접수번호(EDGAR accession / DART rcept_no) 기반 델타 추출 — 평소 외부 호출 ≈0, 분기 경계·정정공시에만 갱신 (v1.3 / FUND-08)
- [ ] 지표 registry (저량/유량 TTM/하이브리드) — 원천 raw 누적으로 신규 지표 무재호출 계산 (v1.3 / FUND-09)
- [ ] 트렌드 엑셀 `fundamentals_history.xlsx` — 지표별 매트릭스 + 원천 + 최신 스냅샷 (v1.3 / FUND-10)

**연기(다음 후보):** IN-01/03/04/05/06 위생(로그·테스트·PEG 라벨·DART probe 비용), Phase 1·2 VERIFICATION.md 부재, 200티커 실환경 부하 실증 — STATE.md Deferred Items 참조.

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- 매매 자동 실행 / 브로커 API 연동 — 시각 신호 도구가 목적이며 실제 주문 자동화는 위험 범주가 다름
- BUY/SELL 텍스트 라벨 컬럼·종합 점수 컬럼 — 사용자 결정에 따라 색상만으로 시각화 (시각적 단순성 우선)
- 동적 종목 디스커버리(S&P500 자동 수집 등) — 200개 수준의 개인 포트폴리오에 과한 복잡도
- 일배치/스케줄러 자동화 — 일단 수동 실행으로 단순화, 필요해지면 추후 milestone
- GUI / 웹 대시보드 — 엑셀 자체가 사용자 인터페이스
- 미국·한국 외 시장(일본·홍콩·유럽 등) — Yahoo Finance가 지원하나 재무지표(EDGAR/DART) 일관성 깨짐
- 기존 xlsx 인플레이스 업데이트(차트·서식 유지) — openpyxl 인플레이스 수정 난이도↑, 매번 새 파일 생성이 안전

## Context

- **사용자**: 개인 투자자 본인 1명. Windows 데스크탑 환경에서 직접 실행.
- **신호 철학**: 가격 자체보다 "정상 변동 범위 대비 어디 있나"가 매수/매도 판단의 핵심. 그래서 중앙값 ± 1σ/2σ 기준 색상 시각화가 본질.
- **EMA 기간 선정**: 11/22/96/192 — 약 0.5개월/1개월/4개월/8개월 거래일에 해당하는 사용자 자체 정의 주기.
- **데이터 신뢰도**: yfinance는 시세에 강하지만 재무지표는 누락·부정확이 잦음 → 재무는 1차 소스(EDGAR/DART) 우선, yfinance/네이버는 보완용.
- **포트폴리오 규모**: 200개 종목 × 10년 일봉 × 다수 파생 열 ≈ 한 워크북에 ~200시트, 시트당 수천 행. 성능·Yahoo rate-limit 고려 필요.

## Constraints

- **Tech stack**: Python (yfinance + openpyxl 등 표준 라이브러리). Windows 로컬 실행.
- **Output**: 단일 `.xlsx` 파일. 매 실행마다 새 파일 생성.
- **데이터 소스 우선순위**: 시세 = Yahoo Finance / 재무 = EDGAR(미) → DART(한) → yfinance/네이버 보완
- **Performance**: Yahoo Finance rate-limit 회피를 위한 합리적 throttle/retry 필요. 200종목 처리가 비현실적으로 오래 걸리면 안 됨.
- **언어**: 사용자 인터페이스(엑셀 헤더, 로그 메시지)는 한국어 우선.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 매번 새 .xlsx 생성 (인플레이스 업데이트 X) | openpyxl로 기존 차트·서식 유지가 까다로움, 매번 새로 만들면 단순·안전 | — Pending |
| 색상만으로 신호 시각화 (BUY/SELL 라벨 X) | 사용자가 시각적 직관 우선, 텍스트 라벨은 노이즈 | — Pending |
| 한국 티커는 사용자가 `.KS`/`.KQ` 직접 입력 | 자동 판정 로직보다 입력 명시성이 단순·확실 | — Pending |
| 재무 데이터는 EDGAR/DART 우선, yfinance 보완 | 1차 소스 신뢰도가 yfinance 대비 압도적으로 높음 | — Pending |
| 종목 시드는 사용자 수동 입력 (input 파일) | 200개 수준 개인 포트폴리오에 동적 디스커버리는 과한 복잡도 | — Pending |
| EMA 기간 11/22/96/192 고정 | 사용자가 검증한 자체 매매 주기 — 변경하지 않음 | — Pending |
| 수동 실행(`python main.py`) | 우선 단순함, 스케줄링은 필요해지면 추후 추가 | — Pending |
| "일별 중앙값/표준편차" = **expanding window** | 그 날까지 누적된 모든 데이터로 계산 — look-ahead bias 없음, 안정적 | — Pending |
| 조건부서식 = **정적 색 베이킹** | Python이 σ 비교 후 셀에 직접 글자색·배경색 부여. 대규모 동적 CF의 성능·파일크기 문제 회피 | ✓ Good (v1.0 — color_rules.py 단일 진원지, WCAG 휘도 검증) |
| xlsx 라이브러리 = **XlsxWriter** | 매번 새 파일 생성 모델과 호환, 색 베이킹·서식 적용이 단순·빠름 | ✓ Good (v1.0) |
| 10년 데이터 범위 = **today() − 4000 달력일** | 사용자 원안 그대로 유지 (≈11년 달력일 / ≈10년 거래일) | — Pending |
| 거래량 이상 신호 = **expanding window ±σ** | 다른 모든 지표(가격·EMA)와 동일한 통계 프레임 유지 — 일관성 | — Pending |
| EDGAR User-Agent 이메일 = yunjerrard@gmail.com | EDGAR 정책상 필수, `.env`로 관리 | — Pending |
| DART API 키 = 사용자 보유 | `.env`의 `OPENDART_API_KEY`로 주입 | — Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-06-17 — v1.3 펀더멘털 히스토리 & 델타 추출 마일스톤 시작 (v1.1 주봉 임펄스·v1.2 시트1 기업명 출하 완료). WR-01·WR-02~06 안정성 부채 정리 완료.*
