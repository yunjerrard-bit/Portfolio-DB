# 컬럼 인덱스 매핑 표 (Phase 1, gap-fix 01-07 통합)

Wave 3 (01-04) 산출물 + gap-fix 01-07 갱신 — Phase 2 시트1 hyperlink 작성용 reference.

**총 컬럼 수: 76** (Date 1 + OHLCV 12 + EMA_Close 12 + DIFF 36 + dailychg 12 + Tech 3)

## 의미 변경 요지 (gap-fix 01-07)

사용자 결정으로 **모든 DIFF 차이 컬럼이 종가 EMA 기준으로 통일**되었다.
- EMA 컬럼은 종가만 남는다 (High/Low EMA 제거): `EMA_Close_{11,22,96,192}` (4개, 가격 단위)
- DIFF는 비율로 재정의: `DIFF_{Close,High,Low}_N = (price - EMA_Close_N) / EMA_Close_N` (12개)
  - 값은 0.0123 같은 비율로 저장, Excel num_format `'0.00%'`가 자동으로 ×100 표시 → 1.23%
- dailychg도 종가 EMA만 남는다: `EMA_Close_N_dailychg = EMA_Close_N.diff()` (4개, 가격 단위)
- 색 베이킹 (SigmaBucket)은 그대로 — 각 컬럼의 expanding median±σ가 기준 (비율이든 가격이든 동일)

이전 124 컬럼 레이아웃과의 차이:
- 제거: `EMA_{High,Low}_N` (8개) + 그 _median/_std (16개) = 24
- 제거: `EMA_{High,Low}_N_dailychg` (8개) + 그 _median/_std (16개) = 24
- 합계: 124 − 48 = 76

## 컬럼 인덱스 표

| Col Index | 원본 컬럼명 | 한국어 헤더 | 색 규칙 | num_format | 그룹 |
|-----------|-------------|-------------|---------|------------|------|
| 0 | Date | 날짜 | (없음) | (날짜) | 0 (Date) |
| 1 | Close | 종가 | SigmaBucket | price | 1 원천 OHLCV |
| 2 | Close_median | 종가 일별 중앙값 | (없음) | price | 1 |
| 3 | Close_std | 종가 일별 표준편차 | (없음) | price | 1 |
| 4 | High | 고가 | SigmaBucket | price | 1 |
| 5 | High_median | 고가 일별 중앙값 | (없음) | price | 1 |
| 6 | High_std | 고가 일별 표준편차 | (없음) | price | 1 |
| 7 | Low | 저가 | SigmaBucket | price | 1 |
| 8 | Low_median | 저가 일별 중앙값 | (없음) | price | 1 |
| 9 | Low_std | 저가 일별 표준편차 | (없음) | price | 1 |
| 10 | Volume | 거래량 | SigmaBucket | volume | 1 |
| 11 | Volume_median | 거래량 일별 중앙값 | (없음) | volume | 1 |
| 12 | Volume_std | 거래량 일별 표준편차 | (없음) | volume | 1 |
| 13 | EMA_Close_11 | 종가 EMA11 | SigmaBucket | price | 2 EMA_Close |
| 14 | EMA_Close_11_median | 종가 EMA11 일별 중앙값 | (없음) | price | 2 |
| 15 | EMA_Close_11_std | 종가 EMA11 일별 표준편차 | (없음) | price | 2 |
| 16 | EMA_Close_22 | 종가 EMA22 | SigmaBucket | price | 2 |
| 17 | EMA_Close_22_median | 종가 EMA22 일별 중앙값 | (없음) | price | 2 |
| 18 | EMA_Close_22_std | 종가 EMA22 일별 표준편차 | (없음) | price | 2 |
| 19 | EMA_Close_96 | 종가 EMA96 | SigmaBucket | price | 2 |
| 20 | EMA_Close_96_median | 종가 EMA96 일별 중앙값 | (없음) | price | 2 |
| 21 | EMA_Close_96_std | 종가 EMA96 일별 표준편차 | (없음) | price | 2 |
| 22 | EMA_Close_192 | 종가 EMA192 | SigmaBucket | price | 2 |
| 23 | EMA_Close_192_median | 종가 EMA192 일별 중앙값 | (없음) | price | 2 |
| 24 | EMA_Close_192_std | 종가 EMA192 일별 표준편차 | (없음) | price | 2 |
| 25 | DIFF_Close_11 | 종가-EMA11 차이 | SigmaBucket | percent_ratio | 3 DIFF |
| 26 | DIFF_Close_11_median | 종가-EMA11 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 27 | DIFF_Close_11_std | 종가-EMA11 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 28 | DIFF_Close_22 | 종가-EMA22 차이 | SigmaBucket | percent_ratio | 3 |
| 29 | DIFF_Close_22_median | 종가-EMA22 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 30 | DIFF_Close_22_std | 종가-EMA22 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 31 | DIFF_Close_96 | 종가-EMA96 차이 | SigmaBucket | percent_ratio | 3 |
| 32 | DIFF_Close_96_median | 종가-EMA96 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 33 | DIFF_Close_96_std | 종가-EMA96 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 34 | DIFF_Close_192 | 종가-EMA192 차이 | SigmaBucket | percent_ratio | 3 |
| 35 | DIFF_Close_192_median | 종가-EMA192 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 36 | DIFF_Close_192_std | 종가-EMA192 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 37 | DIFF_High_11 | 고가-EMA11 차이 | SigmaBucket | percent_ratio | 3 |
| 38 | DIFF_High_11_median | 고가-EMA11 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 39 | DIFF_High_11_std | 고가-EMA11 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 40 | DIFF_High_22 | 고가-EMA22 차이 | SigmaBucket | percent_ratio | 3 |
| 41 | DIFF_High_22_median | 고가-EMA22 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 42 | DIFF_High_22_std | 고가-EMA22 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 43 | DIFF_High_96 | 고가-EMA96 차이 | SigmaBucket | percent_ratio | 3 |
| 44 | DIFF_High_96_median | 고가-EMA96 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 45 | DIFF_High_96_std | 고가-EMA96 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 46 | DIFF_High_192 | 고가-EMA192 차이 | SigmaBucket | percent_ratio | 3 |
| 47 | DIFF_High_192_median | 고가-EMA192 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 48 | DIFF_High_192_std | 고가-EMA192 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 49 | DIFF_Low_11 | 저가-EMA11 차이 | SigmaBucket | percent_ratio | 3 |
| 50 | DIFF_Low_11_median | 저가-EMA11 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 51 | DIFF_Low_11_std | 저가-EMA11 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 52 | DIFF_Low_22 | 저가-EMA22 차이 | SigmaBucket | percent_ratio | 3 |
| 53 | DIFF_Low_22_median | 저가-EMA22 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 54 | DIFF_Low_22_std | 저가-EMA22 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 55 | DIFF_Low_96 | 저가-EMA96 차이 | SigmaBucket | percent_ratio | 3 |
| 56 | DIFF_Low_96_median | 저가-EMA96 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 57 | DIFF_Low_96_std | 저가-EMA96 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 58 | DIFF_Low_192 | 저가-EMA192 차이 | SigmaBucket | percent_ratio | 3 |
| 59 | DIFF_Low_192_median | 저가-EMA192 차이 일별 중앙값 | (없음) | percent_ratio | 3 |
| 60 | DIFF_Low_192_std | 저가-EMA192 차이 일별 표준편차 | (없음) | percent_ratio | 3 |
| 61 | EMA_Close_11_dailychg | 종가 EMA11 일변동 | SigmaBucket | price | 4 dailychg |
| 62 | EMA_Close_11_dailychg_median | 종가 EMA11 일변동 일별 중앙값 | (없음) | price | 4 |
| 63 | EMA_Close_11_dailychg_std | 종가 EMA11 일변동 일별 표준편차 | (없음) | price | 4 |
| 64 | EMA_Close_22_dailychg | 종가 EMA22 일변동 | SigmaBucket | price | 4 |
| 65 | EMA_Close_22_dailychg_median | 종가 EMA22 일변동 일별 중앙값 | (없음) | price | 4 |
| 66 | EMA_Close_22_dailychg_std | 종가 EMA22 일변동 일별 표준편차 | (없음) | price | 4 |
| 67 | EMA_Close_96_dailychg | 종가 EMA96 일변동 | SigmaBucket | price | 4 |
| 68 | EMA_Close_96_dailychg_median | 종가 EMA96 일변동 일별 중앙값 | (없음) | price | 4 |
| 69 | EMA_Close_96_dailychg_std | 종가 EMA96 일변동 일별 표준편차 | (없음) | price | 4 |
| 70 | EMA_Close_192_dailychg | 종가 EMA192 일변동 | SigmaBucket | price | 4 |
| 71 | EMA_Close_192_dailychg_median | 종가 EMA192 일변동 일별 중앙값 | (없음) | price | 4 |
| 72 | EMA_Close_192_dailychg_std | 종가 EMA192 일변동 일별 표준편차 | (없음) | price | 4 |
| 73 | Stoch_%K | Stoch %K | TechBucket | percent_literal | 5 기술 지표 |
| 74 | Stoch_%D | Stoch %D | TechBucket | percent_literal | 5 |
| 75 | RSI | RSI | TechBucket | percent_literal | 5 |

## num_format 키 (gap-fix 01-07)

Format 캐시 33키 = 8 buckets × 4 fmt_types + 1 header. fmt_type:

| fmt_type | Excel 문자열 | 적용 컬럼 |
|----------|--------------|-----------|
| price | `#,##0.00` | Close/High/Low + 그 _median/_std, EMA_Close_N + _median/_std, dailychg + _median/_std |
| volume | `#,##0` | Volume, Volume_median, Volume_std |
| percent_literal | `0.00"%"` | Stoch_%K, Stoch_%D, RSI (값 0~100 그대로 + 리터럴 %) |
| percent_ratio | `0.00%` | DIFF_* 및 DIFF_*_median/_std (Excel가 자동 ×100 표시) |
