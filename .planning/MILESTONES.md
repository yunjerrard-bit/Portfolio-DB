# Milestones

## v1.0 MVP (Shipped: 2026-06-12)

**Phases completed:** 4 phases, 27 plans

**Delivered:** `tickers.txt`의 US·KR 혼합 티커 목록을 입력하면 Yahoo Finance 10년 시세 + EDGAR/DART/yfinance·Naver 펀더멘털을 받아 EMA·표준편차·중앙값 기반 색 신호를 정적 베이킹한 단일 `portfolio_YYYYMMDD.xlsx`를 생성하는 개인용 주식 분석 도구.

**Key accomplishments:**

- **Phase 1** — 단일 US 티커 수직 슬라이스: OHLCV 수신 → EMA11/22/96/192 + expanding-window 중앙값/표준편차 → 정적 색 베이킹(±1σ 글자색 / ±2σ 글자+배경) → 1-시트 xlsx. Stochastic Slow·RSI(Wilder) native 구현.
- **Phase 2** — N티커 스케일링: ThreadPoolExecutor(max_workers=4) 팬아웃 + 24h OHLCV 디스크 캐시 + tenacity 재시도 + curl_cffi 세션. 시트1 통합 포트폴리오(종가·등락률·EMA 신호·거래량·하이퍼링크).
- **Phase 3** — 펀더멘털: EDGAR(미)·DART(한) 1차 + yfinance·Naver 보완, metric별 차등 폴백 체인(PER: DART→Naver→yf 등)과 per-metric provenance 라벨. 시트1 PER/PEG/GPM/OPM + 출처 셀 주석.
- **Phase 4** — 품질·견고성: 한국어 콘솔 실행 요약 블록(티커/인증/캐시/실패) + 캐시 hit/miss 집계 + EDGAR/DART 인증 사전검증(raise 없는 ping + 1차 소스 스킵) + frozen panes(1~5행) + WCAG 휘도 색 톤 검증.

**검증:** 통합 체커 62/62 요구사항 WIRED · 자동 테스트 244 passed · 최종 UAT 7/7 통과 · 보안 7/7 위협 CLOSED.

**Known deferred items at close:** 5 (see STATE.md Deferred Items) — Phase 3 펀더멘털 NaN 가드(WR-01, Core Value 직결), 04-REVIEW Warning 6건, Phase 1·2 VERIFICATION.md 부재(기능 사후 입증됨), Phase 2 200티커 실환경 부하 실증, OHLCV NaN 종가 quick task. 상세: milestones/v1.0-MILESTONE-AUDIT.md

---
