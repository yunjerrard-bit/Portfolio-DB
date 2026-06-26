---
phase: 4
slug: quality-robustness
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-06-11
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x (existing — tests/ directory established Phases 1–3) |
| **Config file** | pyproject.toml |
| **Quick run command** | `uv run pytest tests/ -x -q --no-header -k "<task-relevant pattern>"` |
| **Full suite command** | `uv run pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds |

---

## Sampling Rate

- **After every task commit:** Run `uv run pytest tests/ -x -q -k "<task pattern>"`
- **After every plan wave:** Run `uv run pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 60 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 1 | EXEC-04 | T-04-01 | 요약/통계에 키 미포함 | unit | `uv run pytest tests/test_cache.py -x -q` | ❌ W0 (test_cache 확장) | ⬜ pending |
| 4-01-02 | 01 | 1 | EXEC-04 | T-04-01 | 요약 블록 키 미포함 | integration | `uv run pytest tests/test_smoke_n_tickers.py -x -q` | ⚠️ 확장 | ⬜ pending |
| 4-01-03 | 01 | 1 | EXEC-04 | — | — | doc-grep | `grep -c "D-01" .planning/REQUIREMENTS.md` | n/a (문서) | ⬜ pending |
| 4-02-01 | 02 | 2 | OUT-04 | T-04-02 | — | integration (openpyxl) | `uv run pytest tests/test_freeze_panes.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-02 | 02 | 2 | OUT-04 (COLOR-07/SC4) | T-04-02 | — | unit (luminance) | `uv run pytest tests/test_color_tone.py tests/test_color_rules.py -x -q` | ❌ W0 | ⬜ pending |
| 4-02-03 | 02 | 2 | OUT-04 (SC4) | T-04-02 | — | manual | — (수기 시각 검증) | manual-only | ⬜ pending |
| 4-03-01 | 03 | 2 | EXEC-04 | T-04-03/04/06 | ping 사유 EDGAR·DART 키/UA 미포함, 캐시 미오염 | unit (mock) | `uv run pytest tests/test_auth_check.py -x -q` | ❌ W0 | ⬜ pending |
| 4-03-02 | 03 | 2 | EXEC-04 | — | — | unit | `uv run pytest tests/test_fundamentals.py tests/test_auth_check.py -x -q` | ⚠️ 확장 | ⬜ pending |
| 4-03-03 | 03 | 2 | EXEC-04 | T-04-03/04/05 | 인증 줄 키/UA 미포함, throttle 경유 | integration (smoke) | `uv run pytest tests/test_smoke_n_tickers.py tests/test_auth_check.py -x -q` | ⚠️ 확장 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_auth_check.py` — stubs for 인증 사전검증 (ping_edgar/ping_dart 계약: raise 금지, (ok, 한국어 사유) 반환, EDGAR UA·DART API 키 양쪽 미노출)
- [ ] `tests/test_cache.py` (확장) — 캐시 hit/miss 카운터 + reset_cache_stats()/get_cache_stats() 스텁
- [ ] `tests/test_freeze_panes.py` — openpyxl 읽기 회귀 (freeze_panes == "A6"/"B6")
- [ ] `tests/test_color_tone.py` — WCAG relative luminance 그레이스케일 구분 테스트

*Existing pytest infrastructure covers framework needs — no install required.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 파스텔 색 톤 "강렬하지 않음" 주관 판정 | OUT-04 | 미적 판단은 자동화 불가 (휘도차는 자동, 톤 선호는 수기) | 생성된 .xlsx를 열어 ±1σ/±2σ 색상이 파스텔 톤인지 육안 확인, 그레이스케일 인쇄 미리보기로 구분 확인 |
| 200 티커 실행 콘솔 출력 확인 | EXEC-04 | 실 API 대량 호출은 CI 부적합 | 실제 티커 목록으로 `uv run python main.py` 실행, 한국어 진행률·캐시 통계·실패 요약 블록 육안 확인 |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 60s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** planner-filled 2026-06-11 (revised: Wave 0 filenames corrected to match Plans, 04-02 wave 2)
</content>
