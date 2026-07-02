---
phase: quick-260702-nrs
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/stocksig/output/sheet_metric_matrix.py
  - src/stocksig/output/sheet_snapshot.py
  - src/stocksig/output/sheet_raw.py
  - tests/test_history_sheets.py
  - tests/test_history_render.py
autonomous: true
requirements: [QUICK-260702-nrs]

must_haves:
  truths:
    - "fundamentals_history_*.xlsx 의 모든 탭(지표 9탭 + 원천 + 최신 스냅샷)에서 1행 헤더가 세로 스크롤 시 고정된다"
    - "지표 9탭·최신 스냅샷 탭은 헤더행 + A열이 함께 고정된다(A2/B2부터 스크롤)"
    - "원천 탭은 헤더행만 고정된다(A2부터 스크롤, 키 컬럼 미고정)"
    - "ROE/ROA 값이 지표 매트릭스·최신 스냅샷 탭에서 퍼센트(예: 115.1%)로 표기된다"
    - "GPM/OPM 표기(.1f%)는 기존과 동일하게 유지된다"
    - "레지스트리 is_ratio_0_1 플래그는 변경되지 않는다(ROE/ROA 는 여전히 False)"
  artifacts:
    - path: "src/stocksig/output/sheet_metric_matrix.py"
      provides: "헤더행+A열 freeze, ROE/ROA 퍼센트 표기"
      contains: "freeze_panes(1, 1)"
    - path: "src/stocksig/output/sheet_snapshot.py"
      provides: "헤더행+A열 freeze, ROE/ROA 퍼센트 표기"
      contains: "freeze_panes(1, 1)"
    - path: "src/stocksig/output/sheet_raw.py"
      provides: "원천 탭 헤더행 freeze"
      contains: "freeze_panes(1, 0)"
  key_links:
    - from: "sheet_metric_matrix.py::_format_value_text"
      to: "ROE/ROA 퍼센트 분기"
      via: "metric in _PERCENT_METRICS or is_ratio_0_1"
      pattern: "ROE|ROA"
    - from: "sheet_snapshot.py::_format_value_text"
      to: "ROE/ROA 퍼센트 분기"
      via: "metric in _PERCENT_METRICS or is_ratio_0_1"
      pattern: "ROE|ROA"
---

<objective>
펀더멘털 트렌드 워크북(fundamentals_history_YYYYMMDD.xlsx) 표시 수정 2건.

1. 전 탭(지표 9탭 + 원천 + 최신 스냅샷) 헤더행(1행) 틀 고정.
2. ROE/ROA 값을 퍼센트(예: 115.1%)로 표기.

Purpose: 스크롤 시 헤더가 사라져 어떤 분기/지표인지 혼동되는 문제 해소, 그리고 ROE/ROA 가 0.xx 소수로 보여 오해되는 문제(특히 AAPL ROE 1.15 → 115.1%) 해소.
Output: 수정된 3개 writer + 갱신된 회귀 테스트 2개(+ 신규 회귀 단언).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md

@src/stocksig/output/sheet_metric_matrix.py
@src/stocksig/output/sheet_snapshot.py
@src/stocksig/output/sheet_raw.py
@tests/test_history_sheets.py
@tests/test_history_render.py

<interfaces>
<!-- 확정된 변경 지점 (오케스트레이터 사전조사 + 실행자 확인). 라인 번호는 실행 시 재확인. -->

sheet_metric_matrix.py:
- L44-48 `_format_value_text(metric, value)`: `if _IS_RATIO.get(metric, False):` → 퍼센트, else 소수 2자리.
- L138-139 끝부분 `ws.freeze_panes(0, 1)` (A열만, 헤더행 미고정).
- L6 docstring "A열만 freeze(D-04, 헤더행 미고정)", L138 주석 동일 문구.

sheet_snapshot.py:
- L27-30 `_format_value_text(metric, value)`: 매트릭스와 동일 규칙.
- L72-73 끝부분 `ws.freeze_panes(0, 1)`, L72 주석 "A열만 freeze(D-04 일관)".

sheet_raw.py:
- write_raw_sheet 끝(L58 뒤): freeze_panes 호출 전혀 없음 → 추가.

XlsxWriter freeze_panes(row, col) = "첫 비고정 셀" 규약:
- freeze_panes(1, 1) → 헤더행 1행 + A열 고정, B2 부터 스크롤. openpyxl read-back = "B2".
- freeze_panes(1, 0) → 헤더행 1행만 고정, A2 부터 스크롤. openpyxl read-back = "A2".
- 기존 freeze_panes(0, 1) → openpyxl read-back = "B1".

레지스트리(metrics_registry.REGISTRY): is_ratio_0_1=True 는 GPM/OPM 뿐. ROE/ROA 는 False.
_IS_RATIO = {m.name: m.is_ratio_0_1 for m in REGISTRY} — 이 플래그는 절대 변경 금지.
ROE 는 100% 초과 가능(AAPL 실측 115.1%) → is_ratio_0_1 의 "0~1 비율" 의미와 맞지 않음.
표기 확장은 display 함수 안에서만 한다.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: 3개 writer 헤더행 freeze + ROE/ROA 퍼센트 표기</name>
  <files>src/stocksig/output/sheet_metric_matrix.py, src/stocksig/output/sheet_snapshot.py, src/stocksig/output/sheet_raw.py</files>
  <action>
세 파일을 다음과 같이 수정한다. XlsxWriter 쓰기 API(freeze_panes) 사용, 한국어 주석 유지.

(A) 헤더행 freeze:
- sheet_metric_matrix.py 끝부분 `ws.freeze_panes(0, 1)` → `ws.freeze_panes(1, 1)` (헤더행 1행 + A열 고정, B2 부터 스크롤).
- sheet_snapshot.py 끝부분 `ws.freeze_panes(0, 1)` → `ws.freeze_panes(1, 1)`.
- sheet_raw.py 의 write_raw_sheet 마지막 데이터 루프 뒤에 `ws.freeze_panes(1, 0)` 추가(원천 시트는 키 컬럼 고정 불필요, 헤더행만 고정 → A2 부터 스크롤).

(B) ROE/ROA 퍼센트 표기:
- 두 파일(sheet_metric_matrix.py, sheet_snapshot.py)에 모듈 상수 `_PERCENT_METRICS = frozenset({"ROE", "ROA"})` 를 정의하고, 각 `_format_value_text` 를 `if _IS_RATIO.get(metric, False) or metric in _PERCENT_METRICS:` → `f"{value * 100:.1f}%"`, else `f"{value:.2f}"` 로 확장한다. 소수 자릿수는 기존 GPM/OPM 과 동일한 `.1f%` 유지. 두 파일 일관되게 적용.
- metrics_registry.py 의 is_ratio_0_1 플래그는 절대 건드리지 않는다. 표기 확장은 오직 display 함수(_format_value_text) 안에서만.

(C) docstring/주석 문구 갱신(사실 반영):
- sheet_metric_matrix.py 상단 docstring "A열만 freeze(D-04, 헤더행 미고정)" 및 끝부분 주석 → "헤더행+A열 freeze(D-04, 헤더행 고정)" 취지로 수정.
- sheet_snapshot.py 끝부분 주석 "A열만 freeze(D-04 일관)" → "헤더행+A열 freeze(D-04 일관)" 취지로 수정.
- ROE/ROA 퍼센트 확장을 반영하는 한 줄 주석을 각 _format_value_text 근처에 추가.
  </action>
  <verify>
    <automated>cd "$(git rev-parse --show-toplevel)" && python -c "import ast,sys; [ast.parse(open(f,encoding='utf-8').read()) for f in ['src/stocksig/output/sheet_metric_matrix.py','src/stocksig/output/sheet_snapshot.py','src/stocksig/output/sheet_raw.py']]; print('parse OK')" && grep -n 'freeze_panes' src/stocksig/output/sheet_metric_matrix.py src/stocksig/output/sheet_snapshot.py src/stocksig/output/sheet_raw.py</automated>
  </verify>
  <done>세 파일 파싱 성공. sheet_metric_matrix.py·sheet_snapshot.py 는 freeze_panes(1, 1), sheet_raw.py 는 freeze_panes(1, 0). _format_value_text 가 ROE/ROA 를 퍼센트로 반환. metrics_registry.py 미변경.</done>
</task>

<task type="auto">
  <name>Task 2: 회귀 테스트 갱신 + 신규 단언 추가</name>
  <files>tests/test_history_sheets.py, tests/test_history_render.py</files>
  <action>
새 동작에 맞게 기존 freeze 단언을 갱신하고 ROE/ROA 퍼센트·헤더행 freeze 회귀 단언을 추가한다.

(A) 기존 단언 갱신:
- tests/test_history_sheets.py::test_matrix_headers_and_freeze 의 `assert ws.freeze_panes == "B1"` → `assert ws.freeze_panes == "B2"` (헤더행+A열 고정). docstring/주석의 "헤더행 미고정" 문구도 "헤더행 고정"으로 갱신.
- tests/test_history_render.py::test_freeze 의 두 단언 `wb["PER"].freeze_panes == "B1"` / `wb["최신 스냅샷"].freeze_panes == "B1"` → 둘 다 `"B2"`. docstring 문구도 갱신.

(B) 신규 회귀 단언 추가:
- tests/test_history_sheets.py 에 원천 시트 freeze 단언을 test_raw_sheet_long_rows 에 추가하거나 신규 테스트로: 원천 시트 read-back `ws2.freeze_panes == "A2"` (헤더행만 고정).
- tests/test_history_sheets.py 에 ROE/ROA 퍼센트 표기 회귀 테스트 신규 추가: 매트릭스 ROE 셀 = _cell(1.151) → read-back 값에 "%" 포함 및 "115.1%" 포함. 스냅샷 경로도 확인(test_snapshot_sheet_one_row_per_ticker 의 ROE _cell(0.18)/ROA _cell(0.09) 셀이 read-back 시 "%" 포함 및 각각 "18.0%"/"9.0%" 포함하도록 단언 추가).

기존 GPM/OPM 퍼센트·PER 소수 표기 단언(test_matrix_ratio_percent_vs_decimal)은 불변 — 그대로 통과해야 한다.
  </action>
  <verify>
    <automated>cd "$(git rev-parse --show-toplevel)" && uv run pytest tests/test_history_sheets.py tests/test_history_render.py -q</automated>
  </verify>
  <done>test_history_sheets.py·test_history_render.py 전부 통과. freeze 단언은 B2(지표/스냅샷)·A2(원천), ROE/ROA 셀은 퍼센트 문자열("%"·"115.1%"/"18.0%"/"9.0%") 포함. GPM/OPM/PER 기존 단언 불변 통과.</done>
</task>

</tasks>

<verification>
- `uv run pytest tests/test_history_sheets.py tests/test_history_render.py tests/test_freeze_panes.py -q` 전부 통과(test_freeze_panes.py 는 시트1/종목시트 경로 = 무관, "B6" 기대값 불변이어야 함 — 회귀 없음 확인).
- metrics_registry.py git diff 없음(is_ratio_0_1 미변경).
</verification>

<success_criteria>
- 모든 트렌드 탭 헤더행 1행 고정: 지표 9탭·최신 스냅샷 = 헤더행+A열(B2), 원천 = 헤더행만(A2).
- ROE/ROA 가 매트릭스·스냅샷에서 퍼센트(.1f%)로 표기.
- GPM/OPM/PER 등 기존 표기·is_ratio_0_1 플래그·시트1 freeze("B6") 불변.
- 회귀 테스트 2파일 + freeze_panes 테스트 통과.
</success_criteria>

<output>
Create `.planning/quick/260702-nrs-fund-roe-roa-pct-header-freeze/260702-nrs-SUMMARY.md` when done
</output>
