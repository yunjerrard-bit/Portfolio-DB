---
phase: quick-260617-ijf
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - src/stocksig/io/fundamentals.py
  - tests/test_fundamentals.py
autonomous: true
requirements: [WR-01]

must_haves:
  truths:
    - "NaN last_close가 들어오면 PER MetricCell.value는 None(결손)이 된다 — 값 있는 셀로 통과하지 않는다."
    - "NaN PER이 _compute_peg로 전파되면 PEG MetricCell.value도 None이 된다."
    - "NaN eps_ttm/eps_prior/numer/denom도 결손(None)으로 처리된다."
    - "yf 폴백이 NaN 값을 돌려주면 cell.value로 채워지지 않고 결손이 유지된다."
    - "NaN 결손 셀에는 source(EDGAR/DART/yf)가 붙지 않는다."
    - "기존 전체 테스트 스위트가 네트워크 없이 그린 유지된다 (무회귀)."
  artifacts:
    - path: "src/stocksig/io/fundamentals.py"
      provides: "_is_missing(None/NaN) 헬퍼 + 산식 3종·yf 폴백 2경로 NaN 가드"
      contains: "_is_missing"
    - path: "tests/test_fundamentals.py"
      provides: "NaN last_close→PER None, NaN 전파→PEG None, yf NaN 거부 회귀 테스트"
      contains: "nan"
  key_links:
    - from: "_compute_per / _compute_peg / _compute_margin"
      to: "_is_missing"
      via: "is None 검사를 _is_missing(...) 으로 교체"
      pattern: "_is_missing\\("
    - from: "_fill_us / _fill_kr yf 폴백 루프"
      to: "_is_missing(float(v))"
      via: "float 변환 후 NaN 거부 가드"
      pattern: "_is_missing\\(float\\(v\\)\\)"
---

<objective>
WR-01 펀더멘털 NaN 가드. `runner.process_ticker`가 주입하는 `last_close = df.iloc[-1].get("Close")`가 장중 부분 행 등으로 `NaN`일 수 있는데, `_compute_per`는 `last_close is None`만 검사하므로 `NaN is not None` → `PER = NaN/eps = NaN`이 **값 있는 셀**로 통과하고 `source="EDGAR"` provenance까지 붙는다. NaN은 `_compute_peg`로 전파(NaN 비교가 모두 False라 모든 가드 통과)되고, yf 폴백의 `float(v)`도 `float('nan')`을 그대로 수용한다. 결과적으로 시트1에 NaN PER/PEG가 기록되어 D-05("결손은 None, 0/-999999 금지")를 위반하고 Core Value(시트 정확성)를 직접 훼손한다.

Purpose: NaN을 None과 동일하게 "결손"으로 취급하는 단일 게이트(`_is_missing`)를 도입해, NaN이 값 있는 셀·provenance로 시트에 새는 경로를 전부 차단한다.

Output: `_is_missing` 헬퍼 추가 + 산식 3종·yf 폴백 2경로 가드 교체 + 네트워크 없는 회귀 테스트.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/STATE.md
@./CLAUDE.md
@src/stocksig/io/fundamentals.py
@tests/test_fundamentals.py

<interfaces>
<!-- 수정 대상의 현재 시그니처 — executor는 코드베이스 재탐색 없이 이 계약대로 작업. -->
<!-- src/stocksig/io/fundamentals.py -->

MetricCell(value: float | None, source: str | None, note: str | None)  # dataclass

def _empty_cell(note: str | None = None) -> MetricCell  # value=None, source=None

def _compute_per(last_close: float | None, eps_ttm: float | None) -> MetricCell
    # 현재 가드: eps_ttm is None / eps_ttm <= 0 / last_close is None
def _compute_peg(per, eps_ttm, eps_prior: float | None) -> MetricCell
    # 현재 가드: per is None / eps_prior is None / eps_prior == 0 / eps_ttm is None / growth_pct <= 0
def _compute_margin(numer: float | None, denom: float | None) -> MetricCell
    # 현재 가드: numer is None / (denom is None or denom == 0)

# yf 폴백 NaN 미가드 위치:
#   _fill_us  L159-166:  if v is not None: cell.value = float(v); cell.source="yf"
#   _fill_kr  L253-261:  if v is not None: cell.value = float(v); cell.source="yf"
# (KR Naver 폴백 L238-242 naver_per 도 동일 패턴 — float(naver_per) NaN 가드 포함)

# 모듈은 현재 `import math` 미보유 — 추가 필요.
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: NaN 결손 회귀 테스트 추가 (RED)</name>
  <files>tests/test_fundamentals.py</files>
  <behavior>
    - test_compute_per_last_close_nan: `_compute_per(last_close=float("nan"), eps_ttm=8.0)` → cell.value is None, note에 "종가" 포함.
    - test_compute_per_eps_nan: `_compute_per(last_close=100.0, eps_ttm=float("nan"))` → cell.value is None (NaN을 결손으로; ≤0 비교에 NaN이 새지 않음).
    - test_compute_peg_per_nan: `_compute_peg(per=float("nan"), eps_ttm=10.0, eps_prior=8.0)` → cell.value is None (NaN PER 전파 차단).
    - test_compute_peg_eps_nan: `_compute_peg(per=12.5, eps_ttm=float("nan"), eps_prior=8.0)` → cell.value is None.
    - test_compute_margin_nan: numer 또는 denom이 NaN → cell.value is None.
    - test_fetch_fundamentals_us_nan_last_close: `fetch_fundamentals("AAPL", "US", last_close=float("nan"), edgar_fn=<eps_ttm 양수 반환 stub>, yf_fn=<{} 반환 stub>)` → result.per.value is None AND result.per.source is None (값 없는 결손 셀에 EDGAR provenance 미부여).
    - test_fill_us_yf_nan_rejected: yf_fn이 `{"PER": float("nan")}` 반환, EDGAR가 PER 결손 → result.per.value is None, result.per.source is None ("yf" 미부여).
  </behavior>
  <action>tests/test_fundamentals.py 끝에 위 7개 테스트를 추가한다. import에 필요 시 기존 `fetch_fundamentals`/`_compute_*` 재사용(이미 임포트됨). edgar_fn/yf_fn은 기존 테스트(test_runner.py analog, 본 파일 하단의 fetch_fundamentals 라우팅 테스트)와 동일한 콜러블 주입 패턴으로 네트워크 없이 stub. `float("nan")` 직접 사용(외부 의존 금지). 본 RED 단계에서는 테스트만 추가하고 production은 손대지 않는다 — NaN 케이스는 현재 코드에서 실패(value가 NaN으로 채워짐)해야 정상.</action>
  <verify>
    <automated>uv run pytest tests/test_fundamentals.py -q -k "nan" 2>&1 | Select-String -Pattern "failed|error" -Quiet</automated>
  </verify>
  <done>새 nan 테스트가 production 미수정 상태에서 FAIL(또는 NaN으로 채워져 단언 실패)한다 — RED 확인. 7개 테스트가 컬렉션됨.</done>
</task>

<task type="auto" tdd="true">
  <name>Task 2: _is_missing 헬퍼 + 산식·폴백 NaN 가드 (GREEN)</name>
  <files>src/stocksig/io/fundamentals.py</files>
  <behavior>
    - Task 1의 7개 nan 테스트가 전부 통과한다.
    - 기존 fundamentals 테스트(정상값·기존 결손 사유·provenance)는 무회귀.
  </behavior>
  <action>모듈 상단 import 블록에 `import math` 추가(없을 때만). `_compute_per` 직전(순수 산식 헬퍼 섹션 시작부)에 헬퍼 추가: `def _is_missing(x: float | None) -> bool: return x is None or (isinstance(x, float) and math.isnan(x))`. 다음 `is None` 검사를 `_is_missing(...)` 으로 교체 — `_compute_per`: `eps_ttm is None`→`_is_missing(eps_ttm)`, `last_close is None`→`_is_missing(last_close)` (단, `eps_ttm <= 0` 가드는 _is_missing 통과 후 실행되므로 NaN이 ≤0 비교에 도달하지 않음 — 순서 유지: missing 먼저). `_compute_peg`: `per is None`→`_is_missing(per)`, `eps_prior is None`→`_is_missing(eps_prior)`, `eps_ttm is None`→`_is_missing(eps_ttm)` (`eps_prior == 0` 가드는 _is_missing 후 유지). `_compute_margin`: `numer is None`→`_is_missing(numer)`, `denom is None`→`_is_missing(denom)` (`denom == 0` 가드 유지). yf 폴백 2경로 — `_fill_us` L159-166, `_fill_kr` L253-261: `if v is not None:` 를 `if v is not None and not _is_missing(float(v)):` 로 교체하고 내부 `cell.value = float(v)` 유지(중복 변환 최소화를 위해 `fv = float(v)` 지역변수로 묶어도 무방). KR Naver 폴백(L238-242)도 동일 가드 적용: `if naver_per is not None and not _is_missing(float(naver_per)):`. provenance/note/used 부여 로직은 가드 내부에 그대로 둔다(NaN이면 진입 자체를 막아 source 미부여 보장). 다른 동작 변경 금지 — 변경은 NaN→None 안전 처리에 국한.</action>
  <verify>
    <automated>uv run pytest tests/test_fundamentals.py -q 2>&1 | Select-String -Pattern "passed" ; uv run pytest -q 2>&1 | Select-String -Pattern "passed|failed|error"</automated>
  </verify>
  <done>tests/test_fundamentals.py 전체 통과(신규 nan 7개 포함). `uv run pytest -q` 전체 스위트 그린(네트워크 없음). NaN last_close→PER value None·source None, NaN 전파→PEG None, yf/Naver NaN 거부가 단언으로 입증됨.</done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| 외부 시세/펀더멘털 데이터 → 산식 입력 | Yahoo/EDGAR/DART/Naver가 NaN·부분 행 등 비정상 수치를 반환할 수 있음 (신뢰 불가 입력) |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-quick-01 | Tampering(데이터 무결성) | `_compute_per`/`_compute_peg`/`_compute_margin` + yf/Naver 폴백 | mitigate | `_is_missing(None/NaN)` 게이트로 NaN을 결손(None)으로 강제 — 값 있는 셀·provenance 위조 차단 (본 플랜 핵심) |
| T-quick-02 | Information Disclosure | 예외 note/로그 | accept | 본 플랜은 신규 외부 호출·예외 경로를 추가하지 않음; 기존 T-04-03(자격증명 누설 차단) 패턴 불변 |
</threat_model>

<verification>
- `uv run pytest tests/test_fundamentals.py -q` — 신규 nan 7개 + 기존 전부 통과.
- `uv run pytest -q` — 전체 스위트 그린, 네트워크 호출 없음(콜러블 주입 stub).
- `Select-String -Path src/stocksig/io/fundamentals.py -Pattern "_is_missing\("` — 헬퍼 정의 1 + 호출처(산식 3종 내 다수 + 폴백 3경로) 검출.
</verification>

<success_criteria>
- NaN last_close → PER 결손(value None, source None), NaN 전파 → PEG 결손, yf/Naver NaN 거부가 테스트로 입증.
- 산식 3종의 `is None` 검사가 `_is_missing`으로 교체됨 (NaN·None 동시 게이트).
- yf 폴백 2경로 + Naver 폴백이 NaN을 거부.
- 전체 테스트 스위트 무회귀 그린. production 변경은 NaN→None 안전 처리에 국한.
</success_criteria>

<output>
Create `.planning/quick/260617-ijf-wr-01-nan-is-missing-none-nan-per-peg-gp/260617-ijf-SUMMARY.md` when done
</output>
