# Phase 1 Discussion Log

**Date:** 2026-05-20
**Mode:** discuss (interactive)

## Gray Areas Presented

A. 프로젝트 구조 — `main.py` 단일 / `src/` 단일 패키지 평탄 / `src/stocksig/{io,compute,output}/` 도메인 레이어
B. 시트 열 배치/그룹 순서
C. 파스텔 색 톤 (구체 hex)
D. expanding window 초기 행 색 처리
E. 로깅 도구 (stdlib / rich / loguru)
F. OHLCV 수신 기간 인자 (`period="max"` vs `start=today-4000d`)

## User Selections

### D. expanding window 초기 행 색 처리
- **선택:** 기본 색깔로 표시 (별도 처리·threshold·마커 없음)
- **이유:** 간단한 답변. 시각적 노이즈 회피.

### A. 프로젝트 구조
- **선택:** 옵션 3 — 도메인 레이어 분리 `src/stocksig/{io,compute,output}/`
- **이유:** Phase 2~4 모듈 확장이 자연스러움.

## Claude's Discretion (사용자 위임)

사용자가 "나머지는 합리적 기본값으로 채워라" 선택.

- **B. 열 순서:** 원천 OHLCV → 1차 EMA → 2차 차이 → 2차 EMA 일변동 → 기술적 지표. 각 데이터 열 우측에 즉시 일별 med/std 인접 배치 (SHEET-07 + SHEET-08).
- **C. 색 톤:** Material Design 800/900 (글자) + 100 (배경). `color_rules.py` 모듈 상수로 한곳 튜닝.
- **E. 로깅:** Phase 1은 stdlib `logging` + 한국어 UTF-8. progress bar는 Phase 2에 도입.
- **F. OHLCV 기간:** `Ticker.history(start=today-timedelta(days=4000), end=today, auto_adjust=True)`. `period="max"` 미사용.

## Stoch Slow + RSI 포함 여부 확인

사용자 질문: "스토캐스틱 slow 와 RSI 부분도 추가되어 있는가?"
- 확인: REQUIREMENTS.md TECH-01~06 모두 Phase 1, TECH-07만 Phase 2. ROADMAP.md Phase 1 Requirements 라인 및 Success Criteria #6에 명시됨.

## Deferred Ideas

(CONTEXT.md `<deferred>` 섹션 참조)

---

*Discussion completed 2026-05-20*
