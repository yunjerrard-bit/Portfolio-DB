# BACKLOG: US(EDGAR) 펀더멘털 전 결손 — edgartools 5.35.0 API 변경

**상태:** ✅ 완료 (quick 260629-hec, 2026-06-29) — raw_facts 전수 재적재 검증
**작성:** 2026-06-28 (진단 PC) — 멀티 PC 인계용 핸드오프
**우선순위:** 높음 (US 종목 펀더멘털 트렌드 전부 무의미한 상태)

> **해결 (2026-06-29, quick 260629-hec):** 6단계 수정안 전부 실행. by_period_type quarterly 마이그레이션 + 파이썬 instant 필터 + period_end 분기키 + WARNING 로깅 + filing_date 정렬. delta_state EDGAR 정리 후 US 125종목 재동기화(ok=125) → 105종목 분기×9필드 회복(AAPL 536행/73분기 등). 전 스위트 368 passed, 시트1 색 신호 0줄(Core Value 불변). 커밋 6586935/70ffa9a/df621f4. 상세: `.planning/quick/260629-hec-edgartools-5-35-0-by-period-type-migrati/260629-hec-SUMMARY.md`.
>
> **다음 층 이슈 인계:** raw_facts 는 채워졌으나 **EDGAR Q4 갭** 때문에 트렌드 셀(GPM/PER 등) 최근 분기가 여전히 "-" → 별개 근본원인으로 `.planning/backlog/edgar-q4-gap-ttm-none.md` 에 정식 진단·인계.

> 이 문서는 다른 PC에서 콜드로 이어받기 위한 자족 핸드오프다. 메모리(`~/.claude/.../memory/`)는 PC 로컬이라 동기화되지 않으므로, 진단·수정안을 git 추적 경로(`.planning/`)에 옮겨 둔 것.

---

## 증상

`uv run python main.py history` 가 만드는 `output/fundamentals_history_YYYYMMDD.xlsx` 에서 **US 종목의 모든 지표(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA)가 전부 결손("-")**. KR(DART) 종목은 정상.

## 근본 원인 (라이브 재현 확정)

`edgartools` 5.35.0 에서 `EntityFacts.query().by_period_type()` 의 유효값이 바뀜 — 이제 `['annual','monthly','quarterly','ttm','ytd']`. **`'duration'`·`'instant'` 폐기.**

[src/stocksig/io/edgar_client.py](../../src/stocksig/io/edgar_client.py) 의 `fetch_edgar_quarterly_raw` 가:
- 유량 6종(매출·매출총이익·영업이익·순이익·EPS·영업현금흐름)을 `by_period_type("duration").by_period_length(3)` 로 (라인 ~212)
- 저량 3종(자산·부채·자본)을 `by_period_type("instant")` 로 (라인 ~219)
조회 → 둘 다 `ValidationError: Invalid period type` 발생.

그리고 `_query_facts`(라인 ~181)의 `except Exception: return []` 가 그 예외를 **조용히 삼켜** 9개 재무 필드가 전부 빈 리스트가 됨. `facts.shares_outstanding_fact` 만 `by_period_type` 을 안 쓰는 별도 경로라 살아남아 **종목당 1행(shares_outstanding)만** 적재됨.

**증거:** AAPL 라이브 추출 = `{'shares_outstanding': 1}`. DB(`data/fundamentals.db` raw_facts): EDGAR 88종목 × 1행, DART 42종목 × 117행(13분기·9필드).

## 왜 자가복구가 안 되나 (중요)

[src/stocksig/io/fundamentals_delta.py](../../src/stocksig/io/fundamentals_delta.py) `sync_ticker_history` 는 `delta_state.last_accession` 과 현재 최신 공시 accession 을 비교해 같으면 **델타 HIT → 즉시 return(재추출 0)**. US 종목 accession 이 2026-06-19 적재 때 다 기록돼 있어, 추출기를 고쳐도 **`delta_state` 의 EDGAR 행을 삭제/널 처리한 뒤 재동기화해야** 실제로 다시 적재된다.
- 확인됨: `delta_state(TSLA,EDGAR).last_accession='0001628280-26-026673'` == `Company("TSLA").latest("10-Q").accession_number` (동일) → 현재는 무조건 SKIP.

---

## 수정안 (6단계 — 조사 완료, 실행만 남음)

1. **duration → `by_period_type("quarterly")` 마이그레이션 + `by_period_length(3)` 제거.**
   현행 facts 는 `period_length=None` 이라 `by_period_length(3)` 필터가 결과를 0으로 만든다. quarterly 결과는 이미 ~3개월 사실만 포함.
   (TSLA 라이브 검증: quarterly 로 Revenue 426 / GrossProfit 170 / OpInc 90 / NetInc 306 / EPS 61 / OCF 30 facts 취득.)

2. **instant(BS) 경로 해소.** 새 어휘에 `instant` 대응어 없음 → `by_period_type` 필터 없이 `by_concept(C).execute()` 후 **파이썬에서 `period_type=='instant'` 만 필터링**.
   (TSLA: Equity 415 / Liabilities 992 / Assets 1568 instant facts ≈ 63분기.)

3. **`_calendar_quarter_key` 키 산출 버그 수정 (별개·중요).**
   현행은 `get_display_period_key()`(= `fiscal_period` 신뢰)를 쓰는데, 3개월 사실 일부가 `fiscal_period='FY'` 로 태깅돼 게이트(`\d{4}Q[1-4]`)에서 탈락 → 분기 손실(예: Revenue/GrossProfit/NetInc 48 vs **period_end 기준 60**, 분기당 ~12개 손실). docstring 은 "period 종료일 기준 캘린더 분기"라 했으나 구현 불일치.
   → **`period_end` 의 월로 `(month-1)//3 + 1` 분기 산출**하면 손실 복구 + docstring 일치. (quick 260627-vpn 의 `\d{4}Q[1-4]` 최종 가드는 유지하되, 키 소스를 period_end 로 교체.)

4. **`_query_facts` 의 조용한 `except Exception: return []` 제거/로깅** — 이 사고를 가린 주범. 최소한 예외 타입·concept 를 WARNING 으로 남겨 향후 API 변경이 드러나게.

5. **중복 facts 정렬.** 다중 공시·정정으로 같은 (quarter, field) 에 여러 fact 가 옴. upsert 가 `(ticker,source,quarter,field)` 로 collapse 하나 *마지막-쓰기 승*. `filing_date`(또는 `is_restated`)로 정렬해 최신/정정값이 마지막에 오게 → 정정값 정확.

6. **수정 후 재적재.** `delta_state` 의 EDGAR 행 삭제(또는 last_accession 널) → `uv run python main.py`(SYNC 단계가 재추출·upsert) → `uv run python main.py history` 로 xlsx 재생성 → US 종목 지표 채워짐 확인.

## 검증 기준

- `uv run python -m pytest` GREEN (회귀 0). 추출 단위 테스트는 네트워크 0 스텁/픽스처로 — 코드베이스 컨벤션상 **구조화된 값 단언**(렌더 텍스트 단언 금지).
- 재적재 후 raw_facts 의 EDGAR 종목들이 KR 처럼 분기×9필드를 갖는지(AAPL 등 표본 확인).
- `history` 재실행 시 US 종목 트렌드 셀이 더 이상 전부 "-" 가 아님.
- **Core Value 불변:** 시트1(`portfolio_YYYYMMDD.xlsx`) 색 신호·레이아웃 0줄 변경 (`git diff` 로 `sheet_portfolio.py` 빈 출력 확인). 이 버그·수정은 history 경로 전용.

## 관련 파일

- [src/stocksig/io/edgar_client.py](../../src/stocksig/io/edgar_client.py) — `fetch_edgar_quarterly_raw`, `_query_facts`, `_calendar_quarter_key`, `_EDGAR_DURATION_CONCEPTS`, `_EDGAR_INSTANT_CONCEPTS`
- [src/stocksig/io/fundamentals_delta.py](../../src/stocksig/io/fundamentals_delta.py) — `sync_ticker_history` (델타 SKIP)
- [src/stocksig/io/fundamentals_store.py](../../src/stocksig/io/fundamentals_store.py) — `delta_state` 테이블, `fetch_raw_quarters`, upsert
- `data/fundamentals.db` — raw_facts / delta_state (git 추적, 멀티 PC 동기화)
- 선행: quick 260627-vpn (트렌드 FY-라벨 가드) — 지운 6 FY행이 이 버그의 부산물(shares_outstanding 이 FY 프레임으로 태깅된 케이스).

---

## 다른 PC에서 이어받는 법

1. `git pull` (이 문서 포함 최신 수신)
2. `uv run python -m pytest` 로 환경 정상 확인 (uv/Node 세팅은 [CLAUDE.md](../../CLAUDE.md) 참조)
3. Claude 에 이 문서를 가리키며 착수:
   `/gsd-quick .planning/backlog/edgar-fundamentals-us-broken.md 의 6단계 수정안 실행 — edgartools 5.35.0 by_period_type 마이그레이션 + _calendar_quarter_key period_end 키 + 조용한 except 제거 + delta_state EDGAR 재동기화`
4. 수정·재적재·검증 후 backlog 에서 이 문서 제거(또는 "완료" 표기) + 커밋/푸시.
