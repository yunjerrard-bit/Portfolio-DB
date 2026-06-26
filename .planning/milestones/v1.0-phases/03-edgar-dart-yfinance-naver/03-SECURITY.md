---
phase: 03-edgar-dart-yfinance-naver
slug: 03-edgar-dart-yfinance-naver
status: verified
threats_open: 0
asvs_level: 1
created: 2026-06-10
auditor: gsd-security-auditor (claude-sonnet-4-6)
uat_note: "UAT 5/5 통과(2026-06-05 실환경 — EDGAR 403 무발생·캐시 HIT 확인). SC4 캐시 배선 fix 9cfc1df 포함."
---

# Phase 3 (03-edgar-dart-yfinance-naver) — Security

> Per-phase 보안 계약: 위협 레지스터, 수용된 리스크 로그, 감사 기록.
> **T-03-12 ID 중복 주의**: 03-04-PLAN의 T-03-12(DoS·탐지차단 / Naver 볼륨)와
> 03-05-PLAN의 T-03-12(Tampering / 결손 펀더멘털 셀)는 별개 위협이다.
> 본 문서에서 후자를 **T-03-15**로 renumber한다.

---

## Trust Boundaries

| 경계 | 설명 | 교차 데이터 |
|------|------|------------|
| 외부 API(EDGAR/DART) → 본 프로세스 | rate-limit 정책 경계. 위반 시 403/쿼터차단. | EDGAR EntityFacts, DART finstate_all JSON |
| 디스크 캐시 → 메모리 | pickle 역직렬화 경계(.cache/fundamentals). | pandas dict (본인 생성 캐시만) |
| `.env` 비밀 → 런타임 | OPENDART_API_KEY·EDGAR UA email 유출 금지 경계. | API 키, 실이메일 |
| Naver HTML → 파서 | 신뢰 불가 외부 입력, float 파싱 경계. | HTML 텍스트 (bs4 + float) |
| SEC EDGAR UA → SEC 로그 | 실이메일 노출(SEC 정책상 필수) 경계. | UA header |
| FundamentalsResult → 시트1 셀 | 결손값이 0/특수값으로 시트·평균을 오염시키지 않게(D-05). | MetricCell.value (float | None) |
| 펀더멘털 fetch 예외 → 파이프라인 | 결손이 시세 처리 흐름을 깨지 않게. | Exception propagation |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-03-01 | Denial of Service | EDGAR/DART 호출 빈도 | mitigate | `throttled_edgar` 8 RPS / `throttled_dart` 2 RPS 토큰버킷 | closed |
| T-03-02 | Tampering | diskcache pickle | accept | 본인 프로세스 생성 캐시만 역직렬화, 외부 주입 경로 없음. 개인 로컬 도구. | closed |
| T-03-SC | Tampering | uv add 4 패키지 | accept | slopcheck 4종 전부 [OK], [SLOP]/[SUS] 0건. | closed |
| T-03-03 | Information Disclosure | OPENDART_API_KEY / UA email | mitigate | `.env` + python-dotenv + gitignore. 평문 기록 금지. | closed |
| T-03-04 | Tampering | Naver HTML 파싱 | mitigate | bs4 텍스트만, `float(text.replace(",",""))` try/except, eval 금지(ASVS V5). | closed |
| T-03-05 | Information Disclosure | EDGAR UA 실이메일 | accept | SEC 정책 필수(PROJECT.md yunjerrard@gmail.com). .env 미커밋으로 통제. | closed |
| T-03-06 | Tampering (도메인 무결성) | EDGAR/yf 결손값 | mitigate | None-safe `.get()`, MetricCell.value=None(0/-999999 금지). PEG 엣지케이스 4종 빈값+한국어 사유. | closed |
| T-03-07 | Information Disclosure | set_identity UA 이메일 | accept | SEC 정책 필수. edgar_client.py 가 config.load_env EDGAR_USER_AGENT_EMAIL 사용, .env gitignore. | closed |
| T-03-08 | Denial of Service | EDGAR 403/15분차단 | mitigate | set_identity import-time 1회(per-call 금지)·@throttled_edgar 8 RPS·ThreadPool 고동시성 금지. | closed |
| T-03-09 | Tampering | Naver HTML 파싱 | mitigate | bs4 텍스트만, float try/except, select_one None 가드, eval 금지. UTF-8 디코딩(A5 [VERIFIED]). | closed |
| T-03-10 | Tampering (도메인 무결성) | DART status/thstrm_amount | mitigate | status 4분기 한국어 사유, int 파싱 try/except, 결손 시 value=None(0 금지 D-05). | closed |
| T-03-11 | Denial of Service | DART 쿼터 소진 | mitigate | @throttled_dart 2 RPS·7d 캐시·status "020" 폴백. | closed |
| T-03-12 | Denial of Service / 탐지차단 | Naver 스크래핑 볼륨 (ToS·IP 차단) | mitigate | D-07 — NAVER_FALLBACK_CAP=20·PER 단일 지표·@throttled_yahoo 2 RPS·429/403 None 처리·reset_naver_count(). | closed |
| T-03-13 | Denial of Service (가용성) | 펀더멘털 fetch 예외 | mitigate | process_ticker try/except 흡수 — 시세 정상 티커는 시트 생성, 펀더멘털만 빈 셀(D-disc-10). | closed |
| T-03-14 | 회귀 | 종목별 시트 97열 / Format 캐시 | mitigate | D-06 — 펀더멘털은 시트1만. 신규 Format 0개·freeze_panes 유지. 전체 스위트 회귀 게이트. | closed |
| T-03-15 | Tampering (도메인 무결성) | 결손 펀더멘털 셀 (원 ID: T-03-12 in 03-05-PLAN) | mitigate | D-05 — write_blank(빈셀) + write_comment(한국어 사유). 0/-999999 미사용. | closed |

*renumber 주석: 03-05-PLAN T-03-12 = 03-04-PLAN T-03-12 ID 충돌 → 본 문서에서 T-03-15로 정정. 두 플랜 원문은 수정하지 않음(구현 파일 READ-ONLY 정책 준수).*

---

## Accepted Risks Log

| Risk ID | Threat Ref | 사유 | Accepted By | 날짜 |
|---------|------------|------|-------------|------|
| AR-03-01 | T-03-02 | diskcache pickle 역직렬화는 본인이 작성한 캐시 파일만(.cache/fundamentals) 대상. 외부 주입 경로(HTTP 인입·원격 파일 마운트 등) 없음. 단일 사용자 개인 로컬 도구이므로 공격면 무의미. | kimyunjae | 2026-06-10 |
| AR-03-02 | T-03-SC | slopcheck 0.6.1 로 4종 신규 패키지(edgartools / opendartreader / beautifulsoup4 / lxml) 전부 [OK] 판정, [SLOP]/[SUS] 0건. 별도 checkpoint 불필요. | kimyunjae | 2026-06-10 |
| AR-03-03 | T-03-05 | SEC EDGAR 정책(https://www.sec.gov/os/accessing-edgar-data)이 UA에 연락 가능한 실이메일 포함을 의무화함. 공개 레포에 .env 미커밋(.gitignore line 3)으로 이메일 소스코드 노출 차단. 정책 준수 없이는 EDGAR 접근 자체가 불가. | kimyunjae | 2026-06-10 |
| AR-03-04 | T-03-07 | T-03-05와 동일 근거. edgar_client.py 가 하드코딩 대신 config.load_env의 EDGAR_USER_AGENT_EMAIL 환경변수 사용(코드 하드코딩 금지). | kimyunjae | 2026-06-10 |

---

## Threat Verification Detail

### T-03-01 — EDGAR/DART throttle (mitigate)

- `src/stocksig/io/throttle.py:31` — `_EDGAR_RATE = Rate(8, Duration.SECOND)` + `_edgar_limiter`
- `src/stocksig/io/throttle.py:35-43` — `def throttled_edgar(fn)` (`try_acquire("edgar")`)
- `src/stocksig/io/throttle.py:46` — `_DART_RATE = Rate(2, Duration.SECOND)` + `_dart_limiter`
- `src/stocksig/io/throttle.py:50-58` — `def throttled_dart(fn)` (`try_acquire("dart")`)
- `src/stocksig/io/edgar_client.py:63` — `@throttled_edgar` 데코레이터 실제 적용
- `src/stocksig/io/dart_client.py:114` — `@throttled_dart` 데코레이터 실제 적용
- `tests/test_throttle.py` — `test_edgar_decorator_preserves_return_and_acquires`, `test_dart_decorator_preserves_return_and_acquires` 존재

### T-03-02 / T-03-SC — accept (수용 리스크)

- 코드 검증 불요 — Accepted Risks Log AR-03-01, AR-03-02 참조.

### T-03-03 — .env + gitignore (mitigate)

- `src/stocksig/config.py:18` — `REQUIRED_KEYS: tuple[str, ...] = ("EDGAR_USER_AGENT_EMAIL", "OPENDART_API_KEY")` fail-fast
- `src/stocksig/config.py:45-47` — 빈값 시 `sys.exit(1)` (한국어 stderr 출력)
- `.gitignore:3` — `.env` 등록 확인
- `src/stocksig/io/dart_client.py:51` — `_resolve_api_key()` 가 `os.environ.get("OPENDART_API_KEY")` 사용 (하드코딩 없음)
- `src/stocksig/io/edgar_client.py:39` — `_resolve_identity()` 가 `os.environ.get("EDGAR_USER_AGENT_EMAIL")` 사용
- SPIKE-FINDINGS.md / fixture / SUMMARY에 API 키 평문 노출 0건 (03-02-SUMMARY.md "보안" 섹션 확인)

### T-03-04 — Naver HTML 파싱 가드 (mitigate)

- `src/stocksig/io/naver_scraper.py:80` — `BeautifulSoup(html, "lxml")` (텍스트만 추출)
- `src/stocksig/io/naver_scraper.py:81-84` — `select_one("#_per")` None 가드 → `float(text.replace(",",""))` 패턴
- `src/stocksig/io/naver_scraper.py:86-89` — `except (httpx.HTTPError, ValueError, AttributeError, UnicodeDecodeError, RuntimeError)` — eval 없음

### T-03-05 / T-03-07 — accept (수용 리스크)

- 코드 검증 불요 — Accepted Risks Log AR-03-03, AR-03-04 참조.

### T-03-06 — EDGAR/yf 결손값 무결성 (mitigate)

- `src/stocksig/io/yf_fundamentals.py:33-38` — `info.get("trailingPE")`, `info.get("pegRatio") or info.get("trailingPegRatio")`, `info.get("grossMargins")`, `info.get("operatingMargins")` — 전부 None-safe `.get()`, KeyError 없음
- `src/stocksig/io/fundamentals.py:73-79` — `_compute_per`: eps_ttm None / ≤0 시 빈값+사유
- `src/stocksig/io/fundamentals.py:82-99` — `_compute_peg`: 4종 엣지케이스(PER없음/전년EPS없음/전년EPS0/성장률≤0) 각각 한국어 note
- `src/stocksig/io/fundamentals.py:102-108` — `_compute_margin`: 분모 0/None · 분자 None 가드
- `src/stocksig/io/fundamentals.py:35-37` — `MetricCell.value: float | None` (0/-999999 금지 명시 docstring)
- `tests/test_fundamentals.py:141` — `test_fallback_chain` 존재 (FUND-05 검증)

### T-03-08 — EDGAR 403 방지 (mitigate)

- `src/stocksig/io/edgar_client.py:44-45` — `set_identity(_SET_IDENTITY_ARG)` import-time 1회 (per-call 아님)
- `src/stocksig/io/edgar_client.py:63` — `@throttled_edgar` (8 RPS)
- ThreadPool 고동시성 금지: `runner.py:27` — `_MAX_WORKERS = 4` (EDGAR per-ticker 호출이 ThreaPool 내 분산되지만 throttle이 8 RPS 하드캡 적용)
- `tests/test_edgar_client.py:38` — `test_set_identity`: set_identity 호출 형식 단언

### T-03-09 — Naver HTML 파싱(03-04) (mitigate)

- T-03-04와 동일 코드 경로. 추가 확인:
- `src/stocksig/io/naver_scraper.py:7-8` — UTF-8 확정 주석(A5 [VERIFIED]) + euc-kr 사용 금지 명시
- `src/stocksig/io/naver_scraper.py:79` — `html = r.text or r.content.decode("utf-8")` (euc-kr 없음)

### T-03-10 — DART status/thstrm_amount 파싱 (mitigate)

- `src/stocksig/io/dart_client.py:42-47` — `_STATUS_NOTES`: "013"/"020" 한국어 사유 dict
- `src/stocksig/io/dart_client.py:133-138` — dict 형태 응답 status 가드, `_empty_raw(note)` 반환
- `src/stocksig/io/dart_client.py:60-70` — `_parse_amount`: `int(s.replace(",","").strip())` try/except → None (ASVS V5)
- `src/stocksig/io/dart_client.py:141-143` — 빈 df 가드(데이터없음/쿼터초과 빈 df 경우)
- `tests/test_dart_client.py` — status 000/013/020 및 thstrm_amount 파싱 단언 존재

### T-03-11 — DART 쿼터 소진 방지 (mitigate)

- `src/stocksig/io/dart_client.py:114` — `@throttled_dart` (2 RPS)
- `src/stocksig/io/dart_client.py:164-176` — `fetch_dart_cached`: 7d TTL 캐시 우선 조회
- `src/stocksig/io/dart_client.py:42-47` — status "020" 한국어 사유("DART 쿼터 초과") + `_empty_raw` 반환(폴백 유도)

### T-03-12 — Naver 스크래핑 볼륨 (mitigate)

- `src/stocksig/io/naver_scraper.py:32` — `NAVER_FALLBACK_CAP: int = int(os.getenv("NAVER_FALLBACK_CAP", "20"))` (env override)
- `src/stocksig/io/naver_scraper.py:35` — `_naver_calls: int = 0` (모듈 레벨 카운터)
- `src/stocksig/io/naver_scraper.py:41-44` — `def reset_naver_count()` 존재
- `src/stocksig/io/naver_scraper.py:64-66` — `_naver_calls >= NAVER_FALLBACK_CAP` 선행 체크 → 스크래핑 미수행 None 반환
- `src/stocksig/io/naver_scraper.py:47` — `@throttled_yahoo` (2 RPS)
- `src/stocksig/io/naver_scraper.py:74-76` — 429/403 시 None 안전 처리
- `src/stocksig/main_run.py` — `reset_naver_count()` run 시작 시 1회 호출(03-05-SUMMARY.md Task 1 확인)
- `tests/test_naver_scraper.py:91` — `test_naver_fallback_cap`: CAP 초과 시 httpx.get call_count==NAVER_FALLBACK_CAP 단언

### T-03-13 — 펀더멘털 fetch 예외 흡수 (mitigate)

- `src/stocksig/runner.py:93-102` — `fundamentals_fn` 호출 감싸는 try/except, 예외 시 `logger.warning(...)` + `fundamentals=None`, TickerResult 정상 반환
- `src/stocksig/io/fundamentals.py:309-313` — US 분기 `try/except Exception` 흡수
- `src/stocksig/io/fundamentals.py:333-337` — KR 분기 `try/except Exception` 흡수
- `tests/test_runner.py:147` — `test_fundamentals_fn_exception_absorbed`: 예외 시 failures 미등록·fund=None 단언
- `tests/test_runner.py:163` — `test_fundamentals_fn_exception_absorbed_logs`: 한국어 warning 로그 단언

### T-03-14 — 종목별 시트 회귀 / Format 캐시 (mitigate)

- `src/stocksig/output/sheet_portfolio.py:34-56` — `PORTFOLIO_COLUMNS` 길이 21 (펀더멘털은 시트1만, 종목별 시트 불변)
- `src/stocksig/output/sheet_portfolio.py:242-248` — `_write_failure_row`: col 16 사유만, 펀더멘털 셀 미작성
- `src/stocksig/output/sheet_portfolio.py:303` — `ws.freeze_panes(5, 1)` 유지
- 신규 `add_format` 0개: `_write_fund_cell` 이 `formats[(SigmaBucket.DEFAULT, num_fmt)]` 기존 키 재사용
- `tests/test_sheet_portfolio.py` — `test_fund_failure_row_no_fund_cells`, `test_column_count_is_21` 존재

### T-03-15 (원 T-03-12 in 03-05-PLAN) — 결손 펀더멘털 셀 무결성 (mitigate)

- `src/stocksig/output/sheet_portfolio.py:105-124` — `_write_fund_cell`: 결손 시 `write_blank` + `write_comment(note or "조회 실패")`, 0/-999999 미사용
- `src/stocksig/output/sheet_portfolio.py:231-239` — `fund is None` 시 4셀 빈칸 + "펀더멘털 미수집" 주석
- `tests/test_sheet_portfolio.py:337` — `test_fund_cols`: openpyxl readback으로 값+주석 단언
- `tests/test_sheet_portfolio.py:376` — `test_fund_missing_cell_blank_with_note`: D-05 빈셀+사유 단언

---

## Unregistered Flags

### SUMMARY.md Threat Flags에서 신규 매핑 없는 항목

03-01~05-SUMMARY.md의 Threat Flags 섹션을 점검한 결과:

- **UTF-8 인코딩 정정(A5)**: euc-kr → UTF-8 — T-03-09 기존 위협에 매핑됨 (informational).
- **DART account_id 1차 매핑 보강**: account_nm 단일 매핑의 업종간 결손 리스크 — T-03-10 기존 위협에 매핑됨 (informational).
- **edgartools 5.x EntityFacts API 정정(A1)**: `facts.to_pandas()` 부재 → typed accessor — T-03-06 기존 위협에 매핑됨 (informational).
- **eps_prior(US PEG 입력) 한계**: 5.35.0 EntityFacts에 전년 EPS TTM accessor 미확정 → eps_prior=None, PEG는 "전년 EPS 미존재" 사유 — T-03-06에 포함, 의도된 limitation으로 문서화됨.

등록되지 않은 신규 공격면(unregistered_flag): **없음**.

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-06-10 | 16 (renumber 후 T-03-15 포함) | 16 | 0 | gsd-security-auditor (claude-sonnet-4-6) |

---

## Sign-Off

- [x] 모든 위협에 disposition 부여 (mitigate / accept)
- [x] 수용된 리스크 Accepted Risks Log에 문서화 (4건)
- [x] `threats_open: 0` 확인
- [x] T-03-12 ID 중복 → T-03-15 renumber 처리 및 주석 기록
- [x] `status: verified` 설정

**승인:** verified 2026-06-10
