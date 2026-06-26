# Phase 10 — Deferred Items (out-of-scope discoveries)

이 phase 실행 중 발견했으나 현재 task 범위 밖이라 고치지 않은 항목.

## 1. test_history_render.py CLI 디스패치 3종 — 환경/경로 아티팩트

- **발견 plan/task:** 10-01 Task 1 (history_render 리팩터 회귀 확인 중)
- **테스트:** `test_history_cli_dispatch`, `test_default_cli_dispatch`, `test_history_cli_db_empty_exit0`
- **증상:** `importlib.import_module("main")` / `subprocess [..., "main.py", ...]` → `ModuleNotFoundError: No module named 'main'`
- **원인:** `main.py`는 레포 루트에 있으나 `pyproject.toml [tool.pytest.ini_options] pythonpath`는 `["src"]`만 포함 — 레포 루트가 sys.path에 없음. `_inject_prices` 리팩터와 무관.
- **증거:** `PYTHONPATH="<repo-root>;src" uv run pytest <3종>` → 3 passed. 경로만 주면 통과.
- **범위 밖 이유:** Task 1 변경 코드(`metrics_engine`/`history_render`)가 일으킨 회귀 아님. 본 plan은 CLI/pytest 경로 설정 미접촉. (단, `from tests.fixtures` → `from fixtures` import 버그는 Rule 1로 수정 — 그게 막던 collection을 풀어 잠재 CLI 실패가 드러난 것.)
- **권장 후속:** quick task로 `pyproject.toml`에 레포 루트 pythonpath 추가 또는 CLI 테스트를 `conftest` rootdir 기반으로 정정.
