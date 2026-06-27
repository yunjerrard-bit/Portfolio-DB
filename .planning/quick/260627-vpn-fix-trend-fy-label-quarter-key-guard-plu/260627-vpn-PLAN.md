---
phase: quick-260627-vpn
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/stocksig/io/edgar_client.py
  - tests/test_edgar_quarterly.py
  - data/fundamentals.db
autonomous: true
requirements:
  - FUND-10
must_haves:
  truths:
    - "_calendar_quarter_key('FY 2026')는 None을 반환한다 (docstring '실패 시 None' 약속 준수)."
    - "기존 정상 경로 'Q2 2026'→'2026Q2', '2026 Q2'→'2026Q2', '2026Q2'→'2026Q2'가 그대로 동작한다."
    - "data/fundamentals.db raw_facts 에 quarter 가 YYYYQn 형식이 아닌 행이 0건이다."
    - "uv run python main.py history 재실행 시 CRDO/LEU/NKE/SIRI/TTWO 5종목이 '트렌드 렌더 실패(ValueError)' 경고를 내지 않는다."
  artifacts:
    - src/stocksig/io/edgar_client.py
    - tests/test_edgar_quarterly.py
  key_links:
    - "_calendar_quarter_key 의 정규화 출력 → raw_facts.quarter 적재 → metrics_engine.compute_matrix 분기축 → _calendar_quarter_offset int() 파싱"
---

<objective>
트렌드 렌더 FY-라벨 버그를 근본 원인에서 차단하고, 이미 오염된 DB 행을 정리한다.

`edgar_client._calendar_quarter_key` 가 연간 프레임("FY 2026") 키를 정규화 분기 키로 오인 반환하던 결함을 가드로 막고(A), 그로 인해 `data/fundamentals.db` raw_facts 에 적재된 비정상 quarter 6행을 삭제한다(B). 회귀 테스트로 정상/비정상 경로를 동시에 잠근다.

Purpose: history 경로 compute_matrix 의 분기축에 "FY 2026" 이 섞여 `_calendar_quarter_offset` 의 `int("FY 2")` ValueError → run_history broad except 가 해당 종목 전체(정상 분기 포함)를 드롭하는 연쇄 실패를 제거한다. 시트1/메인 경로는 단일 TTM 경로라 영향 없음 — 본 수정은 history 경로에만 작용한다.

Output: 가드된 `_calendar_quarter_key`, 정리된 fundamentals.db, 회귀 테스트 1세트.
</objective>

<execution_context>
@$HOME/.claude/gsd-core/workflows/execute-plan.md
@$HOME/.claude/gsd-core/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

@src/stocksig/io/edgar_client.py
@tests/test_edgar_quarterly.py
@tests/test_edgar_client.py
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: _calendar_quarter_key 최종 반환 가드 + 회귀 테스트</name>
  <files>src/stocksig/io/edgar_client.py, tests/test_edgar_quarterly.py</files>
  <behavior>
    - "FY 2026" 입력(연간 프레임) → None
    - "UNKNOWN" / "" / None 입력 → None
    - "Q2 2026" 입력 → "2026Q2" (정상 경로 유지)
    - "2026 Q2" 입력 → "2026Q2" (정상 경로 유지)
    - "2026Q2" 입력(이미 정규화된 단일 토큰) → "2026Q2" (회귀 주의: 공백 없는 정상 키)
  </behavior>
  <action>
edgar_client.py 의 `_calendar_quarter_key` 함수에서, 두 split 분기를 빠져나간 뒤의 마지막 무조건 `return disp` 를, 정규화 후 문자열이 정확히 4자리연도+Q+1~4 패턴일 때만 disp 를 반환하고 그렇지 않으면 None 을 반환하도록 교체한다. 패턴 판정은 표준 라이브러리 정규식 fullmatch 로 한다(앵커 불필요). 패턴 리터럴은 연도 4자리 숫자 클래스 다음 대문자 Q 다음 1~4 단일 숫자 클래스로 구성한다. 함수 상단에서 사용 중인 import 목록에 정규식 모듈(re)이 없으면 추가한다(현재 logging, os 만 import — alphabetical 위치 유지). docstring 의 "실패 시 None" 약속이 이제 모든 경로에서 지켜지므로 docstring 본문은 그대로 둔다. "as-reported 보존" 주석은 동작이 바뀌었으므로 제거하거나 정규식 게이트 설명으로 교체한다. 공백 없는 단일 토큰 "2026Q2"(이미 정규화된 키)는 split 분기를 통과하지 않으므로 반드시 이 최종 게이트를 통과해야 한다 — 패턴이 이 케이스를 매치하는지 회귀 주의(Task behavior 5번째 케이스). NEVER 0/-999999 등 sentinel 반환 금지 — 실패는 None.

tests/test_edgar_quarterly.py 에 `_calendar_quarter_key` 직접 단위 테스트를 추가한다. 기존 파일 컨벤션(from stocksig.io.edgar_client import ..., 구조화된 값 단언, 렌더 텍스트 단언 금지)을 따른다. FinancialFact 를 흉내내는 최소 스텁 클래스를 정의한다 — `get_display_period_key` 메서드 하나만 가지고 생성자 인자로 받은 표시 키를 그대로 돌려주는 클래스. 각 케이스(behavior 5종)에 대해 스텁 인스턴스를 만들어 `_calendar_quarter_key(stub)` 호출 결과를 `==` 로 단언한다("FY 2026"→None, "Q2 2026"→"2026Q2", "2026 Q2"→"2026Q2", "2026Q2"→"2026Q2"). 추가로 빈 키 가드("" 입력 → None)와 None 키 가드(get_display_period_key 가 None 반환 → None)도 단언한다. get_display_period_key 미보유 객체 가드는 기존 callable 체크가 담당하므로 선택. 네트워크/외부 호출 0 — 순수 스텁만 사용.
  </action>
  <verify>
    <automated>cd "C:/Users/yunsa/Documents/Claude/Projects/Portfolio-DB" && uv run python -m pytest tests/test_edgar_quarterly.py -q</automated>
  </verify>
  <done>tests/test_edgar_quarterly.py 신규 _calendar_quarter_key 단언 전부 통과. "FY 2026"→None, 정상 3경로 유지, 빈/None 가드 통과. 전체 스위트에 회귀 0.</done>
</task>

<task type="auto">
  <name>Task 2: fundamentals.db 오염행 정리 (YYYYQn 비형식 raw_facts 삭제)</name>
  <files>data/fundamentals.db</files>
  <action>
data/fundamentals.db 의 raw_facts 테이블에서 quarter 가 YYYYQn 형식이 아닌 행을 삭제한다. 표준 라이브러리 sqlite3 만 사용한다(추가 의존성 금지). 절차는 정확히 다음 3단계로 한다: (1) 삭제 전 SELECT COUNT(*) FROM raw_facts WHERE quarter NOT GLOB 의 GLOB 패턴(연도 4자리 숫자 클래스 + 대문자 Q + 1자리 숫자 클래스)으로 건수를 출력 — 예상 6 (CRDO/LEU/NKE/SIRI/TSLA/TTWO, 전부 field=shares_outstanding, source=EDGAR). (2) 동일 WHERE 절로 DELETE 후 commit. (3) 삭제 후 동일 COUNT 재실행하여 0 을 출력·확인. 이 작업은 스크래치 디렉터리에 일회성 파이썬 스크립트로 작성해 uv run python 으로 실행하거나 uv run python -c 인라인으로 실행한다(레포에 스크립트 파일을 영구 추가하지 말 것 — 데이터 정리는 코드 산출물이 아님). data/fundamentals.db 는 git 추적 중(멀티 PC 동기화)이므로 정리 후 변경된 .db 가 커밋 대상에 포함되어야 한다. GLOB 패턴은 metrics_engine 분기축이 기대하는 YYYYQn 과 동일 형식만 보존한다.
  </action>
  <verify>
    <automated>cd "C:/Users/yunsa/Documents/Claude/Projects/Portfolio-DB" && uv run python -c "import sqlite3,sys; c=sqlite3.connect('data/fundamentals.db'); n=c.execute('SELECT COUNT(*) FROM raw_facts WHERE quarter NOT GLOB ?', ('[0-9][0-9][0-9][0-9]Q[0-9]',)).fetchone()[0]; print('non_yyyyqn_rows=', n); sys.exit(0 if n==0 else 1)"</automated>
  </verify>
  <done>삭제 전 COUNT=6 출력, DELETE+commit 후 COUNT=0 확인. raw_facts 에 YYYYQn 비형식 행 0건. 변경된 data/fundamentals.db 가 다음 커밋에 포함됨.</done>
</task>

</tasks>

<verification>
순차 검증(코드 가드 → DB 정리 → 엔드투엔드 재현 해소):

1. `uv run python -m pytest` — 전체 스위트 GREEN(회귀 0). 신규 _calendar_quarter_key 단언 통과.
2. DB 정리 후 `uv run python -c "import sqlite3; c=sqlite3.connect('data/fundamentals.db'); print(c.execute(\"SELECT COUNT(*) FROM raw_facts WHERE quarter NOT GLOB '[0-9][0-9][0-9][0-9]Q[0-9]'\").fetchone()[0])"` → 0.
3. 엔드투엔드: `uv run python main.py history` 재실행 → 로그에서 CRDO/LEU/NKE/SIRI/TTWO 5종목의 "트렌드 렌더 실패(ValueError)" 경고가 더 이상 나오지 않음을 확인. (TSLA 는 raw_facts 에 그 1행뿐이라 트렌드 데이터 자체가 없음 — 별개 이슈, 본 스코프 아님.)
</verification>

<success_criteria>
- _calendar_quarter_key("FY 2026") == None (docstring 약속 일치).
- 정상 경로 "Q2 2026"/"2026 Q2"/"2026Q2" → "2026Q2" 유지(회귀 0).
- data/fundamentals.db raw_facts YYYYQn 비형식 행 0건.
- main.py history 재실행 시 5종목 ValueError 경고 소멸.
- 전체 pytest 스위트 GREEN, 시트1 색 신호 경로 무접근(스코프 외 — 본 수정은 edgar_client + DB + 테스트만).
</success_criteria>

<output>
Create `.planning/quick/260627-vpn-fix-trend-fy-label-quarter-key-guard-plu/260627-vpn-SUMMARY.md` when done.
</output>