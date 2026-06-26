---
status: complete
phase: 04-quality-robustness
source: [04-01-SUMMARY.md, 04-02-SUMMARY.md, 04-03-SUMMARY.md]
started: 2026-06-12T11:00:00Z
updated: 2026-06-12T11:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. 콜드스타트 스모크 (캐시 버그 재발 확인)
expected: |
  `uv run python main.py` 첫 실행 → AAPL 캐시 MISS → 실데이터 수신. AAPL 시트가
  최신 거래일까지 채워지고 실제 가격대로 표시(2026-05-20 멈춤/90달러대 합성값 아님).
result: pass

### 2. 한국어 실행 요약 블록
expected: |
  실행 종료부 콘솔에 "════════ 실행 요약 ════════" 헤더와 함께
  "티커: 총 N / 성공 N / 실패 N" 줄이 한국어로 출력된다.
result: pass

### 3. 캐시 hit/miss 집계
expected: |
  요약 블록에 "캐시: OHLCV HIT n/MISS n · 펀더멘털 HIT n/MISS n" 줄이 표시되고,
  숫자가 실제 실행 동작과 일치한다(첫 실행은 대부분 MISS).
result: pass
note: "실측 'OHLCV HIT 0/MISS 125 · 펀더멘털 HIT 96/MISS 28' — OHLCV 날짜별 키 정화 후 전부 MISS, 펀더멘털 7일 TTL 재사용 정상"

### 4. 실패 티커 목록
expected: |
  존재하지 않는 티커(예: ZZZZZ)가 있으면 요약 블록에 "실패 티커: ZZZZZ"로
  나열되고, 시트1에도 실패 행으로 표시된다. 실패가 0건이면 실패 줄이 생략된다.
result: pass

### 5. EDGAR/DART 인증 사전검증
expected: |
  US 티커가 있으면 시작부에 "auth | EDGAR 인증 OK"(또는 실패 경고),
  KR 티커가 있으면 "auth | DART 인증 OK"가 한국어로 출력되고, 요약 블록의
  "인증: EDGAR OK | DART OK" 줄에 결과가 반영된다. 인증 실패 시에도 프로그램이
  죽지 않고 해당 1차 소스만 스킵하며 키/UA가 로그에 노출되지 않는다.
result: pass

### 6. Frozen panes (행 1~5 고정)
expected: |
  생성된 .xlsx를 Excel로 열어 임의 시트를 6행 이하로 스크롤해도
  1~5행(헤더·중앙값·표준편차)이 항상 화면에 고정되어 보인다.
  (04-02 체크포인트에서 approved — 재확인)
result: pass

### 7. 파스텔 색 톤 + 흑백 구분
expected: |
  시트1·종목 시트의 ±1σ(글자색)/±2σ(글자색+배경) 색 신호가 강렬하지 않은
  파스텔/소프트 톤이고, 흑백 인쇄 미리보기에서도 매수/과열 방향이 구분된다.
  (04-02 체크포인트에서 approved — 재확인)
result: pass

## Summary

total: 7
passed: 7
issues: 0
pending: 0
skipped: 0

## Gaps

[none yet]
