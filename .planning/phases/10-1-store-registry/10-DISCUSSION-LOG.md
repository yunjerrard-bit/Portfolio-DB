# Phase 10: 시트1 펀더멘털 통합 store/registry 이관 - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-06-23
**Phase:** 10-1-store-registry
**Areas discussed:** 미적재/신규 종목 처리, 구 경로 제거 범위, 현재가 주입 & 드리프트 0, provenance 주석 표시 보존

---

## 미적재/신규 종목 처리

| Option | Description | Selected |
|--------|-------------|----------|
| sync 선행 → 빈칸 폴백 | PASS1 fetch+sync로 DB 적재 → 시트1은 store에서 읽기. 미적재(fetch 실패)는 빈칸+사유, 구 폴백 없음 | ✓ |
| 구 경로 임시 폴백 | DB 미적재 종목만 구 fetch_fundamentals로 폴백 — 두 경로 공존(단일 원천 위배) | |
| 빈칸 (sync 순서 변경 없음) | 현재 구조 그대로, store에 없으면 빈칸 (첫 실행 대부분 빈칸 위험) | |

**User's choice:** sync 선행 → 빈칸 폴백 (권장)
**Notes:** main_run이 이미 sync_ticker_history(L347)로 DB를 채우므로 읽기/쓰기 순서 정렬이 관건. 빈칸 동작은 구 경로 "조회 실패"와 동일해 회귀 아님.

---

## 구 경로 제거 범위

| Option | Description | Selected |
|--------|-------------|----------|
| 중복 fetch만 제거·계약 보존 | fetch_fundamentals/_fill_us/_fill_kr + 7일 .cache/fundamentals만 제거. 산식 헬퍼·MetricCell·_is_missing 보존 | ✓ |
| 적극 정리 (헬퍼도 이동) | 순수 산식 헬퍼를 metrics_engine로 이동, fundamentals.py를 어댑터/모델만 남김 (import 대규모 이동·회귀 위험) | |
| 캐시 디렉터리는 유지 | fetch 경로만 제거하되 .cache/fundamentals 헬퍼는 잔존 | |

**User's choice:** 중복 fetch만 제거·계약 보존 (권장)
**Notes:** _compute_peg는 metrics_engine(L290)이 재사용 중. MetricCell/FundamentalsResult/_is_missing은 시트1·trend·color 공유 계약. .cache/fundamentals가 OHLCV 7일 TTL과 공유되는지는 researcher 확인 후 제거.

---

## 현재가 주입 & 드리프트 0

| Option | Description | Selected |
|--------|-------------|----------|
| 공유 헬퍼 추출 · 양쪽 재사용 | history_render._inject_prices 최신분기 주입 로직을 공유 헬퍼로 추출 → 시트1·트렌드 둘 다 호출 | ✓ |
| 시트1 전용 어댑터 신규 작성 | compute_matrix 최신 열 + last_close로 별도 작성 (로직 분기 → 드리프트 회귀 위험) | |
| 스냅샷 셀 직접 재사용 | history_render 스냅샷 셀을 시트1이 재사용 (실행 순서 결합 발생) | |

**User's choice:** 공유 헬퍼 추출 · 양쪽 재사용 (권장)
**Notes:** price_ratio + compute_peg_cell(4분기 전 EPS) 동일 경로 → 드리프트 구조적 차단. 같은 last_close·같은 최신 분기 사용이 SC1 일치 조건.

---

## provenance 주석 표시 보존

| Option | Description | Selected |
|--------|-------------|----------|
| 소스 + 최신분기 라벨 재구성 | "EDGAR · 2026Q2" 형식 합성, 병합은 "DART+yf · 2026Q2". 구 경로와 동일 UX | ✓ |
| registry provenance 그대로 | compute_matrix source/note 그대로 사용 (분기 라벨 누락 가능 → 체감 변화) | |
| 소스만 표시 | 분기 라벨 없이 소스만 (정보 손실) | |

**User's choice:** 소스 + 최신분기 라벨 재구성 (권장)
**Notes:** 어댑터가 최신 분기를 알고 있으므로 라벨 합성 가능. 결손 셀은 구와 동일하게 한국어 사유 note 보존, sheet_portfolio.py:125 주석 로직 무변경.

---

## Claude's Discretion

- 어댑터/공유 헬퍼의 파일 위치·이름 (계약만 지키면 자유)
- D-05 캐시 제거 시점·테스트 격리 방식

## Deferred Ideas

None — discussion stayed within phase scope.
