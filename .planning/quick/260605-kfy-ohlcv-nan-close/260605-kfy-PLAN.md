---
phase: quick-260605-kfy
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/stocksig/io/market.py
  - tests/test_market.py
autonomous: true
requirements: []

must_haves:
  truths:
    - "Yahoo가 최신 봉의 Close를 NaN으로 내려도 enriched_df.iloc[-1]은 항상 실제 마지막 거래일(Close 비-NaN)을 가리킨다"
    - "Close=NaN인 후행 미정산 봉은 24h OHLCV 캐시에 저장되지 않는다"
    - "트리밍이 발생하면 한국어 info 로그 1줄이 출력된다"
    - "내부 NaN-close가 없는 정상 OHLCV는 행 수가 변하지 않는다(회귀 없음)"
  artifacts:
    - path: "src/stocksig/io/market.py"
      provides: "fetch_ohlcv 내 Close-NaN 행 트리밍 (캐시 저장 이전)"
      contains: "dropna"
    - path: "tests/test_market.py"
      provides: "후행 Close=NaN 트리밍 회귀 테스트"
  key_links:
    - from: "src/stocksig/io/market.py:fetch_ohlcv"
      to: "src/stocksig/io/cache.py:put_ohlcv"
      via: "fetch_ohlcv가 트리밍된 깨끗한 df를 반환 → fetch_ohlcv_cached가 그대로 put_ohlcv"
      pattern: "dropna\\(subset=\\[.Close.\\]\\)"
---

<objective>
Yahoo Finance가 최신 일봉(예: 미국주식 2026-06-04)의 Close/High/Low를 NaN(Volume만 존재)으로 내려줄 때, 파이프라인이 `enriched_df.iloc[-1]`로 마지막 행을 그대로 읽어 시트1의 최신종가·전일등락률·DIFF EMA 4개·거래량·(일)Stoch·(주)Stoch·(주)RSI·(주)임펄스가 빈칸이 되는 버그를 수정한다.

근본 원인: `fetch_ohlcv`가 yfinance 원시 DataFrame을 트리밍 없이 반환 → 후행 미정산 봉(Close=NaN)이 마지막 행으로 남고, 24h 캐시에도 그대로 저장됨. 기존 D-06 부분데이터 가드(행<50%)는 전체 히스토리가 멀쩡하고 마지막 1행만 NaN이라 못 걸러냄.

Purpose: Core Value(중앙값 ± 표준편차 색상 신호)가 통합 포트폴리오 시트에서 정확히 보이는 것이 프로젝트 핵심이다. 마지막 거래일 값이 빈칸이면 신호 자체가 무의미해지므로 데이터 진입 지점에서 차단한다.

Output: `fetch_ohlcv`가 Close=NaN 행을 제거한 깨끗한 프레임만 반환 → `fetch_ohlcv_cached`의 `put_ohlcv`가 깨끗한 프레임만 캐싱 → `iloc[-1]`이 항상 실제 마지막 거래일.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@CLAUDE.md
@src/stocksig/io/market.py
@src/stocksig/io/cache.py
@tests/test_market.py

<interfaces>
<!-- 수정 대상 함수 (src/stocksig/io/market.py) — 현재 구조. 탐색 불필요. -->

fetch_ohlcv(ticker: str) -> pd.DataFrame
  - line 70-72: today / start(today-4000d) / end 산출
  - line 74-78: df = yf.Ticker(ticker, session=_SESSION).history(start, end, auto_adjust=True)
  - line 80-83: 빈 df → ValueError fail-fast (Pitfall B)
  - line 85: logger.info("%s | OHLCV %d 거래일 수신 완료", ticker, len(df))
  - line 86: return df

fetch_ohlcv_cached(ticker: str) -> pd.DataFrame  (line 89-102)
  - cache.get_ohlcv(ticker) → HIT 반환 / MISS → fetch_ohlcv(ticker) → cache.put_ohlcv(ticker, df) → return df
  - ★ put_ohlcv는 fetch_ohlcv가 돌려준 df를 그대로 저장하므로, 트리밍을 fetch_ohlcv 내부에서 하면 캐시도 자동으로 깨끗해진다 (fetch_ohlcv_cached 수정 불필요).

cache.put_ohlcv(ticker, df)  (src/stocksig/io/cache.py:57-60)
  - 24h TTL diskcache set. fetch_ohlcv가 반환한 프레임을 신뢰하고 저장만 함.

D-06 부분데이터 가드 위치: src/stocksig/runner.py (행<50% of 2500 → ValueError → TickerFailure).
  - runner는 fetch_ohlcv_cached가 돌려준(=트리밍된) df의 len으로 판정하므로, fetch_ohlcv 내부 트리밍이면 D-06이 NaN행을 카운트에 포함하지 않아 자동으로 일관됨. runner.py 수정 불필요.

테스트 픽스처: tests/conftest.py:mock_ohlcv_df — 2700행 정상 OHLCV (Close 드리프트~100, NaN 없음), DatetimeIndex, freq="B", index end=2026-05-20.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: fetch_ohlcv에 Close-NaN 후행봉 트리밍 추가 (캐시 저장 이전)</name>
  <files>src/stocksig/io/market.py</files>
  <behavior>
    - 정상 케이스: Close에 NaN이 없는 df → 행 수 불변, 기존과 동일하게 반환.
    - 미정산봉 케이스: 마지막 행 Close=NaN(Volume만 존재) → 해당 행 제거 후 반환, iloc[-1]["Close"]가 비-NaN.
    - 빈 df 케이스: 기존 ValueError fail-fast 동작 유지 (트리밍 추가가 이를 깨면 안 됨).
    - 트리밍이 1개 이상 행을 제거하면 한국어 info 로그 1줄 출력.
    - 트리밍 후 df가 비면(모든 Close가 NaN인 비정상 응답) ValueError로 fail-fast (빈 df 가드와 동일 취지).
  </behavior>
  <action>
    src/stocksig/io/market.py `fetch_ohlcv` 함수 본문에서, 빈 df 가드(line 80-83) **직후**·성공 로그(line 85) **직전** 위치에 Close-NaN 행 트리밍을 삽입한다. 트리밍 전 원본 행 수를 변수(예: original_rows = len(df))로 보관한 뒤 `df = df.dropna(subset=["Close"])`를 적용한다. removed = original_rows - len(df) 가 0보다 크면 한국어 info 로그를 1줄 출력한다: `logger.info("%s | 미정산/NaN 최신봉 %d개 제외", ticker, removed)`. 후행 NaN만이 실제 문제이나 dropna(subset=["Close"])가 안전하고 단순하다(일봉에 내부 NaN-close는 사실상 없음) — RESEARCH/CONSTRAINT 결정대로 subset=["Close"]만 사용하고 High/Low/Open은 건드리지 않는다(EWM carry-forward 경로 보존). 트리밍 후 df가 비면 기존 빈-df ValueError와 동일한 메시지 취지로 `raise ValueError(f"{ticker} | Close 유효 행이 없습니다 (전 봉 NaN)")`를 던져 fail-fast 한다. 기존 성공 로그 `logger.info("%s | OHLCV %d 거래일 수신 완료", ticker, len(df))`는 트리밍 **이후** len(df)를 쓰도록 그대로 두되, 트리밍 코드가 그 위에 오게 한다. fetch_ohlcv_cached / put_ohlcv / runner.py는 수정하지 않는다(트리밍된 df가 자동 전파됨). 신규 의존성 없음 — pandas만 사용.
  </action>
  <verify>
    <automated>uv run pytest tests/test_market.py -x -q</automated>
  </verify>
  <done>fetch_ohlcv가 Close=NaN 행을 제거한 뒤 반환한다. 트리밍 시 한국어 info 로그가 출력된다. 정상 df는 행 수 불변. 빈 df / 전봉 NaN df는 ValueError fail-fast. 기존 test_market.py 전체 통과.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: 후행 Close=NaN 트리밍 회귀 테스트 추가</name>
  <files>tests/test_market.py</files>
  <behavior>
    - 후행 NaN 트리밍 단언: mock history가 마지막 1~2행 Close=NaN(Volume 존재) df를 반환 → fetch_ohlcv 결과의 iloc[-1]["Close"]가 비-NaN(=마지막 유효 거래일), 그리고 결과 길이 == 원본 - removed.
    - 정상 행수 불변 단언: 내부 NaN-close 없는 mock_ohlcv_df는 fetch_ohlcv 후 len 불변.
    - (선택) 트리밍 로그 단언: caplog에 "미정산/NaN 최신봉" 한국어 메시지 substring 존재.
  </behavior>
  <action>
    tests/test_market.py에 회귀 테스트를 추가한다. 기존 패턴(test_fetch_ohlcv_date_window 등)을 그대로 따른다: `mocker.patch("stocksig.io.market.yf.Ticker")` 후 `.return_value.history.return_value`에 mock df를 세팅. (1) `test_trailing_nan_close_trimmed`: conftest의 `mock_ohlcv_df`를 fixture 인자로 받아 복사한 뒤 마지막 1행(또는 2행)의 "Close"(원하면 High/Low도)를 `float("nan")` 또는 `np.nan`으로 세팅하고 Volume은 유지한 df를 history 반환값으로 patch → `df = fetch_ohlcv("AAPL")` → `assert pd.notna(df.iloc[-1]["Close"])` 그리고 `assert len(df) == len(mock_ohlcv_df) - 1`(2행 NaN이면 -2). np는 이미 conftest에서 쓰이므로 `import numpy as np` 추가(파일 상단 import 블록). (2) `test_clean_ohlcv_row_count_unchanged`: 정상 mock_ohlcv_df를 그대로 history 반환값으로 patch → `assert len(fetch_ohlcv("AAPL")) == len(mock_ohlcv_df)`. (3) `test_trim_logs_korean_info`(선택): caplog.at_level("INFO")로 후행 NaN df fetch 시 `"미정산/NaN 최신봉"`이 caplog.text에 포함되는지 단언. 신규 fixture/conftest 변경 없이 mock_ohlcv_df 재사용. autouse `_no_retry_wait` fixture가 이미 retry wait를 0으로 만들므로 추가 조치 불필요.
  </action>
  <verify>
    <automated>uv run pytest tests/test_market.py -x -q</automated>
  </verify>
  <done>후행 Close=NaN df에 대해 iloc[-1]["Close"]가 비-NaN이고 길이가 원본-removed임을 단언하는 테스트가 통과한다. 정상 df 행수 불변 테스트가 통과한다. test_market.py 전체 GREEN.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_market.py -q` — 신규 회귀 테스트 포함 전체 GREEN.
- `uv run pytest -q` — 전체 스위트(195+ 테스트) 회귀 없음.
- 코드 리뷰: 트리밍이 빈-df 가드 직후·성공 로그 직전에 위치(캐시 저장 이전), subset=["Close"]만 사용, fetch_ohlcv_cached/cache.py/runner.py 무변경 확인.

오염된 기존 캐시 정리(코드 아님 — executor 수동 처리): 수정 적용 후 `.cache/ohlcv` 디렉터리를 비워 NaN 봉이 들어간 24h 캐시 항목을 무효화한다 (PowerShell: `Remove-Item -Recurse -Force .cache\ohlcv` 또는 해당 키 만료 대기). 이는 fetch_ohlcv_cached가 다음 실행에서 깨끗한 프레임을 새로 받아 저장하게 한다.
</verification>

<success_criteria>
- fetch_ohlcv가 Close=NaN 행을 제거한 프레임만 반환·캐싱한다.
- enriched_df.iloc[-1]이 항상 실제 마지막 거래일(Close 비-NaN)을 가리킨다 → 시트1 최신종가/전일등락률/DIFF EMA/거래량/(일)(주) 지표 빈칸 버그 해소.
- 트리밍 발생 시 한국어 info 로그 1줄 출력.
- 정상 OHLCV는 행 수 불변 — D-06 가드 및 EWM carry-forward 경로 회귀 없음.
- 전체 자동 테스트 GREEN (신규 추가분 포함).
- 신규 의존성 없음 (pandas만).
</success_criteria>

<output>
Create `.planning/quick/260605-kfy-ohlcv-nan-close/260605-kfy-SUMMARY.md` when done
</output>
