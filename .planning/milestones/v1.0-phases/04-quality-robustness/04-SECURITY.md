---
phase: 04
slug: quality-robustness
status: secured
threats_open: 0
asvs_level: 1
created: 2026-06-12
---

# Phase 04 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| 콘솔 로그 출력 → 사용자/로그파일 | 요약 블록·캐시 통계가 민감정보를 노출하면 안 됨 | 실행 통계(정수)·티커 심볼 (민감정보 없음) |
| .env 자격증명(EDGAR UA, OPENDART_API_KEY) → ping/펀더멘털 호출 | 키/UA가 로그·요약·예외 사유·워크북 note로 새어나가면 안 됨 | API 키, UA 이메일 (높음) |
| 외부 API 응답(SEC EDGAR, OpenDART) → ping 판정 | 외부 응답을 신뢰하지 않고 status/예외로만 판정 | HTTP status, 예외 (낮음) |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-04-01 | Information Disclosure | main_run 요약 블록 캐시/티커 통계 로그 | mitigate | main_run.py:317-340 카운트(정수)·티커 심볼만 출력. 키/UA/예외 원문 미포함. test_summary_block_emitted 등 | closed |
| T-04-02 | (n/a) | 04-02 테스트/색 상수 | accept | 외부 입력·민감정보 미관여. 정적 hex 상수만, 신규 프로덕션 코드 0 | closed |
| T-04-03 | Information Disclosure | ping/펀더멘털 예외 사유 (키/UA 보간) | mitigate | auth_check.py:41-43 고정 한국어 사유, except에서 {e} 미보간. CR-01 후속(48f16be): fundamentals.py 외곽 except(US/KR)·runner.py가 type(e).__name__만 로깅 + 고정 note. 누설 회귀 테스트 4개 | closed |
| T-04-04 | Information Disclosure | 요약 블록 인증 줄 | mitigate | main_run.py:217-228 _auth_label은 ok 상태 + sanitize된 note만 출력. test_summary_auth_line_no_secret_leak | closed |
| T-04-05 | DoS (타인 서비스) | ping의 EDGAR/DART 요청 | accept | 매 실행 1회 조건부 + @throttled_edgar/@throttled_dart 경유 — 무시할 부하 | closed |
| T-04-06 | Tampering | ping의 캐시 오염 | mitigate | auth_check.py는 fetch_*_cached 미사용 — httpx 직접 GET / dart.list()로 캐시 미경유. 소스 단언 테스트 | closed |
| T-04-SC | Tampering | 패키지 설치 | accept | 신규 설치 0개 (3개 SUMMARY tech-stack.added: []) — 기존 httpx/edgartools/opendartreader 재사용 | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| R-04-01 | T-04-02 | 테스트·정적 색 상수만 다루며 외부 입력/민감정보 경계 없음 | 사용자 (plan 승인) | 2026-06-12 |
| R-04-02 | T-04-05 | 매 실행 1회 ping + 기존 throttle 경유 — 외부 서비스 부하 무시 가능 | 사용자 (plan 승인) | 2026-06-12 |
| R-04-03 | T-04-SC | 신규 패키지 설치 0개 — 공급망 표면 변화 없음 | 사용자 (plan 승인) | 2026-06-12 |

*Accepted risks do not resurface in future audit runs.*

---

## Audit Trail

## Security Audit 2026-06-12

| Metric | Count |
|--------|-------|
| Threats found | 7 |
| Closed | 7 |
| Open | 0 |

- 감사자: gsd-security-auditor (opus), register_authored_at_plan_time: true — 완화 검증 모드
- 보안 관련 테스트 32개 전부 green (코드 검사 + 런타임 실행 양쪽 검증)
- Post-plan 동계열 수정 포함 검증: CR-01(fundamentals.py/runner.py 예외 원문 보간 → crtfc_key 누설 가능) — 커밋 48f16be에서 sanitize + 회귀 테스트 2개, 코드 존재 확인
- 비차단 메모: yf/Naver 폴백 로그(fundamentals.py:157/236/251)와 runner.py:149-155 reason=str(e)는 자격증명 무관 경로로 예외 원문 유지 적정
- Unregistered flags: none — SUMMARY Threat Flags 전부 레지스터에 매핑
