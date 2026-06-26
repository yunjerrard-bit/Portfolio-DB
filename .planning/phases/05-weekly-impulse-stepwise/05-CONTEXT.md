# Phase 5: 주봉 임펄스 주간화 - Context

**Gathered:** 2026-06-12
**Status:** Ready for planning
**Source:** 대화 기반 discuss (사용자와 설계 결정 확정)

<domain>
## Phase Boundary

주봉 임펄스(`Impulse_weekly`)를 현재의 "진행형(week-to-date, 매 거래일 변동)"에서 "금요일-대-금요일 주간 신호(주 단위 계단형)"로 전환한다.

**범위 안:**
- 주봉 임펄스 산출 로직 (`impulse.py` 의 주봉 부분)
- 주중 행에 직전 완성 주 값 ffill 고정
- 시트1·종목 시트의 주봉 임펄스 표시가 주 단위 계단형이 되도록 배선 확인

**범위 밖 (잠긴 제외):**
- 일봉 임펄스 — 현행 유지, 변경 금지
- 표시용 진행형 주봉 추세 컬럼(`EMA_Close_11_week_trend`/`EMA_Close_22_week_trend`/`MACD_OSC_week`/`MACD_OSC_week_diff` 등) — 주중 정보용으로 진행형 그대로 유지
- 임펄스 입력 지표 교체(EMA 기간·MACD 외) — 범위 밖
- `decide_impulse` 부호 조합 로직 — 변경 불필요, 그대로 재사용
</domain>

<decisions>
## Implementation Decisions (LOCKED — 사용자 확정)

### D1: 산출 기준 = 금요일-대-금요일
주봉 임펄스는 주 마지막 거래일(W-FRI 기준 금요일, 휴장 시 그 주 실제 마지막 거래일) 시점에서 산출한다. 입력 두 개:
- 추세: 직전 완성 주 대비 **주봉 EMA11**의 변화 부호 (이번 금 EMA11 vs 지난 금 EMA11)
- 모멘텀: 직전 완성 주 대비 **주봉 MACD-OSC**의 변화 부호 (이번 금 vs 지난 금)
판정: 둘 다 상승 → 녹색 / 둘 다 하락 → 적색 / 혼조 → 청색 (기존 `decide_impulse` 재사용).

### D2: 주중 표시 = 직전 완성 주 값 ffill 고정
주 마지막 거래일 이전(월~목)의 행은 **직전 완성 주의 주봉 임펄스 값을 그대로 고정** 표시한다. 다음 주 마지막 거래일에만 값이 갱신된다. → 한 주 내 동일 값(계단형).

### D3: 시트1·종목 시트 모두 주 단위 계단형
시트1의 (주)임펄스 셀과 종목 시트의 주봉 임펄스 열 모두 D2의 계단형 값을 표시한다. 시트1은 `iloc[-1]`(최신 행) 표시이므로 자동으로 최신 완성 주 값을 보이게 됨 — 종목 시트 열과 일치해야 함.

### D4: 일봉 임펄스·진행형 추세 컬럼 불변
일봉 임펄스(`Impulse_daily`)와 표시용 진행형 주봉 추세 컬럼은 변경하지 않는다. 회귀 테스트로 기존 동작(매일 변동) 무손상을 증명한다. MACD 입력은 daily 임펄스와 동일하게 **MACD-OSC(히스토그램)** 사용.

### 메커니즘 메모 (코드 조사 확정)
- `weekly.py:week_close_mask(index)` — 각 행이 그 주(W-FRI)의 마지막 거래일인지 bool. **금요일 휴장 시 실제 마지막 거래일을 True로 처리** (이미 구현됨, 재사용).
- `main_run.py` 주석: `ema_week_to_date(Close,11)`·`macd_oscillator_week_to_date(Close)`는 **금요일 시점에 "진짜 주봉값"과 일치**. 따라서 이 시리즈를 `week_close_mask`에서 샘플링 → 금-금 diff(부호) → `reindex(daily_index, method='ffill')`로 broadcast 하면 D1+D2 달성.
- `compute_weekly`·주봉 통계(`_WEEKLY_FRIDAY_STAT_COLS`)가 이미 동일한 "금요일 샘플 → ffill" 패턴을 씀 — 정합적, 신규 패턴 아님.
- 현재 `impulse.py` 주봉부는 `EMA_Close_11_week_trend`(진행형 daily pct_change)와 `MACD_OSC_week.diff()`(진행형 daily diff)를 행마다 적용 → 이것이 "매일 변동"의 원인. 신규 로직으로 교체.

### Claude's Discretion (구현 세부)
- 새 주봉 임펄스를 `impulse.py` 내 별도 헬퍼로 분리할지, `add_impulse_columns` 내부에서 처리할지
- 금-금 diff에 쓸 EMA11/MACD-OSC 시리즈를 impulse.py에서 직접 주봉 샘플링할지, main_run.py에서 금요일 샘플 시리즈를 미리 만들어 넘길지 (단, 표시용 진행형 컬럼과 혼동되지 않게 분리)
- 첫 주(직전 주 없음) NaN → DEFAULT 처리 (기존 `_is_nanish` 재사용)
</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### 변경 대상
- `src/stocksig/compute/impulse.py` — `add_impulse_columns`, 주봉 임펄스 산출 (핵심 변경)
- `src/stocksig/main_run.py` (~145-169) — 주봉 컬럼 산출부, `add_impulse_columns` 호출 지점

### 재사용 인프라 (변경 금지)
- `src/stocksig/compute/weekly.py` — `week_close_mask`(금요일 휴장 처리), `compute_weekly`(ffill broadcast 패턴 참고), `week_to_date_close_return`
- `src/stocksig/compute/color_rules.py` — `decide_impulse`(부호 조합, 그대로 재사용), `ImpulseBucket`
- `src/stocksig/compute/indicators.py` — `ema_week_to_date`, `macd_oscillator_week_to_date`(금요일=진짜 주봉값)

### 표시 배선 (확인 대상)
- `src/stocksig/output/sheet_portfolio.py` (~214-219) — 시트1 `Impulse_weekly` = `last.get("Impulse_weekly")`
- `src/stocksig/output/sheet_per_ticker.py` — 종목 시트 주봉 임펄스 열

### 테스트
- `tests/test_impulse.py` — 기존 임펄스 테스트 (회귀 + 신규 주간화 케이스 추가)
- `tests/conftest.py` — autouse 캐시 격리, mock_ohlcv_df 픽스처
</canonical_refs>

<specifics>
## Specific Ideas

검증 시나리오(success criteria 도출용):
1. 한 주 내 모든 거래일의 `Impulse_weekly`가 동일 값 (계단형) — 합성 DataFrame로 단언
2. 값 = 금요일 EMA11·MACD-OSC의 금-금 부호 조합 (녹/적/청) — 알려진 입력으로 단언
3. 금요일 휴장 주: 그 주 마지막 거래일(목)을 경계로 산출·고정, 빈칸/오산출 없음
4. 첫 주(직전 주 없음) → DEFAULT
5. 일봉 임펄스·진행형 추세 컬럼은 매일 변동 유지 (회귀 무손상)
</specifics>

<deferred>
## Deferred Ideas

None — phase 범위가 명확. v1.0 부채(NaN 가드 등)는 별도(STATE.md Deferred Items), 이 phase 범위 아님.
</deferred>

---

*Phase: 05-weekly-impulse-stepwise*
*Context gathered: 2026-06-12 via 대화 기반 discuss*
