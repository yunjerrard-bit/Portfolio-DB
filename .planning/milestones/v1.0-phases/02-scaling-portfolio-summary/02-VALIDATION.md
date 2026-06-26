# Phase 2 Validation Map

각 요구사항 → 자동 verify 명령 / 검증 plan.

## Automated

| Req | Plan | Test | Expected |
|-----|------|------|----------|
| INPUT-04 | 02-02 | `tests/test_runner.py::test_invalid_ticker_isolated` | 잘못된 티커 1개 + 정상 1개 → results 1 + failures 1 |
| MKTD-04 | 02-02 | `tests/test_runner.py::test_network_error_isolated` | fetch 예외 → `TickerFailure` + 정상 티커 계속 |
| MKTD-05 | 02-01, 02-02 | `tests/test_cache.py::test_hit_within_ttl`, `test_miss_after_24h` | freezegun으로 23h59m → HIT, 24h01m → MISS |
| MKTD-06 | 02-02 | `tests/test_runner.py::test_partial_data_marked_failure` | row=1000 (40%) → `TickerFailure(reason='부분 데이터 ...')` |
| PORT-01 | 02-04 | `tests/test_smoke_n_tickers.py::test_portfolio_is_first_sheet` | `openpyxl.load_workbook(...).sheetnames[0] == "시트1"` |
| PORT-02 | 02-03 | `tests/test_sheet_portfolio.py::test_one_row_per_ticker` | 3 티커 입력 → 시트1 A6/A7/A8 셀에 티커 3개 |
| PORT-03 | 02-03 | `tests/test_sheet_portfolio.py::test_columns_ticker_market_close_change` | A=티커, B=시장(US/KR), E=최신 종가, F=등락률 |
| PORT-04 | 02-03 | `tests/test_sheet_portfolio.py::test_diff_ema_4cells_color` | DIFF 색이 종목 시트 최신 행 σ-bucket과 동일 (cell.font.color 비교) |
| PORT-06 | 02-03 | `tests/test_sheet_portfolio.py::test_volume_color` | Volume σ-bucket 색 적용 |
| PORT-07 | 02-03 | `tests/test_sheet_portfolio.py::test_ticker_hyperlink` | A6 셀 hyperlink target = `'AAPL'!A1` (또는 KR `'005930.KS'!A1`) |
| PORT-08 | 02-03 | `tests/test_sheet_portfolio.py::test_timestamp_row1` | 시트1 A1 셀 = "실행 시각: YYYY-MM-DD HH:MM:SS" 패턴 |
| TECH-07 | 02-03 | `tests/test_sheet_portfolio.py::test_stoch_rsi_color` | %K ≤20 → soft green, ≥80 → soft red |
| EXEC-03 | 02-02, 02-04 | `tests/test_runner.py::test_throttle_enforced`, smoke 10 ticker | 5초 안에 10 티커, Yahoo 2 RPS 위반 없음 (mock clock) |
| EXEC-05 | 02-02 | `tests/test_runner.py::test_korean_progress_log` | caplog에 `[N/M] OK`, `cache HIT/MISS` 한국어 패턴 포함 |
| D-01 (tickers.txt 호환) | 02-02 | `tests/test_input_extended.py::test_single_column_backcompat` | "AAPL\nMSFT" 한 컬럼 → `TickerSpec(symbol='AAPL', tier='', industry='')` |
| D-01 (tab 확장) | 02-02 | `tests/test_input_extended.py::test_tab_separated` | "AAPL\t1\tTechnology" → `TickerSpec('AAPL','1','Technology')` |
| D-01 (공백 구분) | 02-02 | `tests/test_input_extended.py::test_whitespace_separated` | "AAPL 1 Technology" → 동일 |
| D-01 (헤더 주석) | 02-02 | `tests/test_input_extended.py::test_comment_lines_skipped` | "# header\nAAPL" → 1 spec |
| D-02 (DIFF σ 단일 source) | 02-03 | `tests/test_sheet_portfolio.py::test_diff_color_matches_per_ticker` | 동일 ticker 시트 cell color == 시트1 cell color |
| D-03 (실패 행 시각화) | 02-03 | `tests/test_sheet_portfolio.py::test_failed_row_in_sheet1` | failures 1개 → 마지막 셀 "실패: <reason>", pastel red bg |
| D-04 (token bucket 2 rps) | 02-01 | `tests/test_throttle.py::test_yahoo_2rps` | 10회 호출 5초 이상 소요 (mock clock) |
| D-05 (.cache/) | 02-01 | `tests/test_cache.py::test_cache_dir_created` | `.cache/ohlcv/` 디렉터리 존재 |
| D-06 (부분 <50%) | 02-02 | (위 MKTD-06과 동일) | — |
| D-07 (deps installed) | 02-01 | `uv pip show diskcache pyrate-limiter` | non-empty 출력 |
| D-08 (컬럼 순서) | 02-03 | `tests/test_sheet_portfolio.py::test_column_order` | 5행 헤더 = `["티커","시장","티어","산업","최신 종가","전일 등락률","DIFF Close vs EMA11", ...]` |
| 백로그 PORT-09 (티어) | 02-03 | `tests/test_sheet_portfolio.py::test_tier_column` | C6 = "1" |
| 백로그 PORT-10 (산업) | 02-03 | `tests/test_sheet_portfolio.py::test_industry_column` | D6 = "Technology" |
| 백로그 PORT-11/12 (임펄스) | 02-03 | `tests/test_sheet_portfolio.py::test_impulse_cells` | N6/O6 = "녹색"/"적색"/"청색" + impulse_* font color |

## Manual-Only (Wave 5 = 02-05)

1. `tickers.txt`에 10개 혼합 티커 (US 5 + KR 5) 작성, `uv run python main.py` 실행 → `output/portfolio_YYYYMMDD.xlsx` 생성
2. xlsx 열어 첫 시트가 "시트1"이고 1행 타임스탬프 보임
3. 시트1에서 티커 셀 클릭 → 해당 종목 시트로 이동
4. 시트1 DIFF 색이 종목 시트 최신 행 DIFF 색과 일관 (3 티커 샘플링)
5. 시트1 임펄스 셀 색이 종목 시트 CP/CQ 최신 행과 일관
6. 같은 날 재실행 → 콘솔에 `cache HIT` 메시지 다수 + 실행 시간 단축
7. tickers.txt에 일부러 잘못된 티커(예: `ZZZZZZ`) 1개 추가 → 콘솔 한국어 경고 + 시트1 마지막 행에 "실패" 표시 + 다른 티커는 정상 처리
8. 100 티커 stress (사용자 보유 리스트) → 5분 내 완료, 429/403 없음
