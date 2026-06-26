---
phase: 09
slug: trend-render
status: approved
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-22
---

# Phase 09 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | pyproject.toml ([tool.pytest]) |
| **Quick run command** | `.venv/Scripts/python.exe -m pytest tests/test_history_render.py -q` |
| **Full suite command** | `.venv/Scripts/python.exe -m pytest -q` |
| **Estimated runtime** | ~470s (full suite, 341 passed baseline) |

---

## Sampling Rate

- **After every task commit:** Run the task's `<automated>` command (quick, <10s)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green (회귀 0 — 시트1 불변)
- **Max feedback latency:** ~10s (quick), full suite on wave boundary

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | FUND-10 | T-09-01 | 분기말 종가 네트워크 0(monkeypatch) | unit/tdd | `.venv/Scripts/python.exe -m pytest tests/test_quarter_price.py -x -q` | ❌ W0 | ⬜ pending |
| 09-01-02 | 01 | 1 | FUND-10 | T-09-02 | 상대색·YoY 순수 함수 네트워크 0 | unit/tdd | `.venv/Scripts/python.exe -m pytest tests/test_trend_color.py -x -q` | ❌ W0 | ⬜ pending |
| 09-01-03 | 01 | 1 | FUND-10 | T-09-02 | 다종목 fixture stub(외부 0) | unit | `.venv/Scripts/python.exe -m pytest tests/test_quarter_price.py tests/test_trend_color.py -q` | ❌ W0 | ⬜ pending |
| 09-02-01 | 02 | 2 | FUND-10 | T-09-03 | 트렌드 전용 워크북(시트1 캐시 비결합) | smoke | `.venv/Scripts/python.exe -c "from stocksig.output.history_workbook import make_history_workbook; ..."` | ❌ W0 | ⬜ pending |
| 09-02-02 | 02 | 2 | FUND-10 | T-09-03 | 정적 색 베이킹·식별열 import 0 | unit | `.venv/Scripts/python.exe -m pytest tests/test_history_sheets.py -k matrix -x -q` | ❌ W0 | ⬜ pending |
| 09-02-03 | 02 | 2 | FUND-10 | T-09-05 | provenance source만(키 미노출) | unit | `.venv/Scripts/python.exe -m pytest tests/test_history_sheets.py -k "raw or snapshot" -x -q` | ❌ W0 | ⬜ pending |
| 09-03-01 | 03 | 3 | FUND-10 | T-09-06/07/08 | DB 읽기전용·예외격리·외부 0 | integration | `.venv/Scripts/python.exe -m pytest tests/test_history_render.py -k "render or peg or missing or layout" -x -q` | ❌ W0 | ⬜ pending |
| 09-03-02 | 03 | 3 | FUND-10 | — | CLI 분리(main_run 비결합), 셸 체인 미사용 | integration | `.venv/Scripts/python.exe -m pytest tests/test_history_render.py -k cli -x -q` | ❌ W0 | ⬜ pending |
| 09-03-03 | 03 | 3 | FUND-10 | T-09-03 | 시트1 불변 git diff 0·전 스위트 회귀 0 | regression | `.venv/Scripts/python.exe -m pytest -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky. File Exists ❌ W0 = Wave 0(Plan 01)에서 생성될 신규 테스트/픽스처.*

**SC 매핑:** SC1(별도 파일·시트1 불변)=09-03-01/03 · SC2(매트릭스 행=종목·열=분기 최신왼쪽)=09-02-02, 09-03-01 · SC3([원천]·[최신 스냅샷])=09-02-03 · SC4(과거=분기말 종가·최신=현재가·분기별 PEG)=09-01-01, 09-03-01. D-05~08(이중 인코딩)=09-01-02, 09-02-02 · D-11(결손 "-"+코멘트)=09-02-02/03, 09-03-03 · D-14/15(파일명·서브커맨드 분리)=09-03-01/02.

---

## Wave 0 Requirements

- [x] `tests/fixtures/history_fixtures.py` — compute_matrix fetch_fn stub + 합성 OHLCV builder (Plan 01 Task 3, 네트워크 0)
- [x] `tests/test_quarter_price.py` — 분기말 종가·현재가 단언 (Plan 01 Task 1)
- [x] `tests/test_trend_color.py` — 상대색 방향/표본 게이트/YoY 글리프 단언 (Plan 01 Task 2)
- [x] openpyxl read-back 셀 단언 — `tests/test_history_sheets.py`(Plan 02)·`tests/test_history_render.py`(Plan 03)에서 워크북 셀/색/코멘트/freeze 검증

*Wave 0 산출물은 모두 Plan 01(Wave 1)에서 선행 생성되어 Plan 02/03 테스트가 재사용. 프레임워크(pytest)는 기설치 — 신규 설치 0. `wave_0_complete`는 Plan 01 실행 후 true로 전환.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 색·화살표 육안 직관성 | FUND-10 | 시각적 가독성은 자동 단언이 값/서식 존재까지만 가능 | 생성된 `fundamentals_history_YYYYMMDD.xlsx`를 열어 동종 상대색(초록/무색/빨강)·YoY 화살표(▲▼)가 의도대로 보이는지 확인 |

*값·서식·구조·색 fill rgb·코멘트·freeze·퍼센트 표기는 openpyxl read-back으로 자동 검증, "보기 좋음"만 수기.*

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (9/9 태스크 모두 `<automated>` 보유)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (전 태스크 자동 verify)
- [x] Wave 0 covers all MISSING references (fixture + 3 테스트 파일 = Plan 01에서 생성)
- [x] No watch-mode flags (pytest -x -q, watch 0)
- [x] Feedback latency < 10s (quick per-task)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-06-22 (plan-checker CONCERNS BLOCKER 해소 — per-task map 9행 동기화)
