# 표준편차 기반 주식 매매신호 + 포트폴리오 관리 시트

## What This Is

표준편차를 활용한 매매 신호와 보유 종목을 한 눈에 관리할 수 있는 엑셀(.xlsx) 워크북을 자동 생성하는 개인용 주식 분석 도구입니다. 사용자가 보유/관심 종목 티커 목록을 입력하면, Python이 Yahoo Finance에서 10년치 시세를 받아오고 EMA·표준편차·중앙값을 계산해 종목별 시트와 통합 포트폴리오 시트를 만들어 줍니다. 사용자는 개인 투자자(본인) 한 명이며, 매매 판단의 시각적 보조 도구로 사용합니다.

## Core Value

**중앙값 ± 표준편차를 기준으로 한 색상 신호가 통합 포트폴리오 시트에서 정확하고 직관적으로 보여야 한다.** 이것이 무너지면 다른 모든 기능은 의미가 없습니다.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

(None yet — ship to validate)

### Active

<!-- Current scope. Building toward these. -->

- [ ] 사용자가 입력 파일(예: `tickers.txt` 또는 `input.xlsx` 시트1 A열)에 보유/관심 티커를 적으면 스크립트가 읽어서 워크북을 생성한다
- [ ] 미국(NYSE/NASDAQ)·한국(KOSPI/KOSDAQ) 종목을 모두 지원하며, 한국 종목은 사용자가 `.KS`/`.KQ` 접미사를 직접 포함해 입력한다
- [ ] 각 종목마다 개별 시트가 생성되며, A1 셀에 티커가 들어가고 그 티커를 트리거로 Yahoo Finance 데이터를 조회한다
- [ ] 개별 종목 시트에는 10년치(`today() - 4000 day`) 종가/고가/저가/거래량을 내림차순으로 6행부터 채운다
- [ ] EMA11/22/96/192를 종가·고가·저가에 대해 각각 계산해 별도 열로 채운다
- [ ] 종가/고가/저가와 각 EMA의 차이, 그리고 각 EMA의 일별 변동을 2차 가공 데이터로 채운다
- [ ] 각 데이터 열의 누적 중앙값을 3행에, 누적 표준편차를 4행에 표시한다
- [ ] 각 데이터 열 옆에 "일별 중앙값"·"일별 표준편차" 열을 추가하여 날짜별로 함께 표시한다
- [ ] 조건부 서식으로 색상 신호를 시각화한다: `값 < 중앙값 - 1σ` → 초록 글씨, `값 > 중앙값 + 1σ` → 빨강 글씨, `±2σ` 이상 → 글씨 + 셀 배경까지 변경 (강렬하지 않은 톤)
- [ ] 시트1(통합 포트폴리오)에는 종목 목록과 함께 다음이 표시된다: 최신 종가 + 전일대비 등락률, EMA11/22/96/192 신호색, PER/PEG/GPM/OPM 기본적 분석 지표, 거래량 이상 신호
- [ ] 기본적 분석 데이터는 미국 종목은 EDGAR(SEC) 최우선, 한국 종목은 DART 최우선으로 조회하고 부족한 정보는 yfinance / 네이버 금융 등 검증된 보완 소스 사용
- [ ] 매번 새 파일로 생성(`portfolio_YYYYMMDD.xlsx` 형태)하여 단순하고 안전하게 동작한다
- [ ] `python main.py` 한 줄로 수동 실행 가능하며 Windows 로컬 환경에서 동작한다

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- 매매 자동 실행 / 브로커 API 연동 — 시각 신호 도구가 목적이며 실제 주문 자동화는 위험 범주가 다름
- BUY/SELL 텍스트 라벨 컬럼·종합 점수 컬럼 — 사용자 결정에 따라 색상만으로 시각화 (시각적 단순성 우선)
- 동적 종목 디스커버리(S&P500 자동 수집 등) — 100개 수준의 개인 포트폴리오에 과한 복잡도
- 일배치/스케줄러 자동화 — 일단 수동 실행으로 단순화, 필요해지면 추후 milestone
- GUI / 웹 대시보드 — 엑셀 자체가 사용자 인터페이스
- 미국·한국 외 시장(일본·홍콩·유럽 등) — Yahoo Finance가 지원하나 재무지표(EDGAR/DART) 일관성 깨짐
- 기존 xlsx 인플레이스 업데이트(차트·서식 유지) — openpyxl 인플레이스 수정 난이도↑, 매번 새 파일 생성이 안전

## Context

- **사용자**: 개인 투자자 본인 1명. Windows 데스크탑 환경에서 직접 실행.
- **신호 철학**: 가격 자체보다 "정상 변동 범위 대비 어디 있나"가 매수/매도 판단의 핵심. 그래서 중앙값 ± 1σ/2σ 기준 색상 시각화가 본질.
- **EMA 기간 선정**: 11/22/96/192 — 약 0.5개월/1개월/4개월/8개월 거래일에 해당하는 사용자 자체 정의 주기.
- **데이터 신뢰도**: yfinance는 시세에 강하지만 재무지표는 누락·부정확이 잦음 → 재무는 1차 소스(EDGAR/DART) 우선, yfinance/네이버는 보완용.
- **포트폴리오 규모**: 100개 종목 × 10년 일봉 × 다수 파생 열 ≈ 한 워크북에 ~100시트, 시트당 수천 행. 성능·Yahoo rate-limit 고려 필요.

## Constraints

- **Tech stack**: Python (yfinance + openpyxl 등 표준 라이브러리). Windows 로컬 실행.
- **Output**: 단일 `.xlsx` 파일. 매 실행마다 새 파일 생성.
- **데이터 소스 우선순위**: 시세 = Yahoo Finance / 재무 = EDGAR(미) → DART(한) → yfinance/네이버 보완
- **Performance**: Yahoo Finance rate-limit 회피를 위한 합리적 throttle/retry 필요. 100종목 처리가 비현실적으로 오래 걸리면 안 됨.
- **언어**: 사용자 인터페이스(엑셀 헤더, 로그 메시지)는 한국어 우선.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| 매번 새 .xlsx 생성 (인플레이스 업데이트 X) | openpyxl로 기존 차트·서식 유지가 까다로움, 매번 새로 만들면 단순·안전 | — Pending |
| 색상만으로 신호 시각화 (BUY/SELL 라벨 X) | 사용자가 시각적 직관 우선, 텍스트 라벨은 노이즈 | — Pending |
| 한국 티커는 사용자가 `.KS`/`.KQ` 직접 입력 | 자동 판정 로직보다 입력 명시성이 단순·확실 | — Pending |
| 재무 데이터는 EDGAR/DART 우선, yfinance 보완 | 1차 소스 신뢰도가 yfinance 대비 압도적으로 높음 | — Pending |
| 종목 시드는 사용자 수동 입력 (input 파일) | 100개 수준 개인 포트폴리오에 동적 디스커버리는 과한 복잡도 | — Pending |
| EMA 기간 11/22/96/192 고정 | 사용자가 검증한 자체 매매 주기 — 변경하지 않음 | — Pending |
| 수동 실행(`python main.py`) | 우선 단순함, 스케줄링은 필요해지면 추후 추가 | — Pending |

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
*Last updated: 2026-05-19 after initialization*
