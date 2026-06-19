"""펀더멘털 지표 선언적 registry (MetricType enum + MetricDef + REGISTRY 9종).

FUND-09 / Plan 08-02. 산식 자체는 **유형(MetricType)** 이 결정하므로, 신규 지표는
REGISTRY 튜플에 MetricDef 1줄을 추가하면 끝난다(SC3 확장성). 본 모듈은 *선언적
정의만* 담당하며, 실제 계산은 08-03(metrics_engine)이 REGISTRY를 순회한다.

설계 결정(권위 입력: 08-CONTEXT / 08-RESEARCH / fundamentals-history-delta.md):
- **D-01** 9종 = 재현 4종(PER/PEG/GPM/OPM) + 신규 5종(PBR/PCR/PSR/ROE/ROA).
- **D-02** FCF·EV/EBITDA는 저장 raw 부재로 이번 registry 제외. 단, 원천 확장 후
  MetricDef 1줄 추가로 들어올 수 있는 확장형 설계(REGISTRY 튜플 append).
- **D-03** 하이브리드(ROE/ROA) = 분자 TTM ÷ 분모 *최근값*(저량). 유형 enum이 규정.
- **D-05** 결손 = None (0/-999999 금지). registry는 정의만 — 결손 처리는 엔진.
- **D-07** 가격 의존 4종(PER/PBR/PCR/PSR)은 비율을 계산하지 *않고* `price_denominator`
  에 분모 metric 이름(EPS_ttm/BPS/OCF_ps/SPS)만 박는다. 가격은 호출자가 주입 →
  registry와 가격이 비결합(과거=분기말 종가 / 최신=현재가 분리 가능).
- **A4(08-RESEARCH)** EPS_ttm = net_income TTM ÷ *최근* shares. eps(per-share) 4분기
  합은 주식수 변동 시 부정확 → 분자 net_income·분모 shares_outstanding 로 정의.

소스 매핑(SC1 — 새 dict 발명 금지):
- numerator/denominator 논리 field명은 store field 어휘(raw_facts.field)를 *그대로*
  사용한다. 각 논리 field는 기존 `dart_account_map.DART_ACCOUNT_ID_MAP`(account_id)
  / `edgar_client._EDGAR_*_CONCEPTS`(concept) 매핑에 이미 연결돼 있다 — 본 모듈은
  그 매핑을 *재사용*(import)할 뿐, 별도 매핑 dict를 만들지 않는다.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

# SC1: 소스 매핑 재사용(시작점). 새 매핑 dict 발명 금지 — 아래 두 import가
# "MetricDef.numerator/denominator 논리 field → 소스별 원천 필드" 연결을 보증한다.
from stocksig.io.dart_account_map import DART_ACCOUNT_ID_MAP  # noqa: F401 (SC1 연결 증빙)
from stocksig.io.edgar_client import (  # noqa: F401 (SC1 연결 증빙)
    _EDGAR_DURATION_CONCEPTS,
    _EDGAR_INSTANT_CONCEPTS,
)


class MetricType(Enum):
    """지표 산식 유형 — 엔진(08-03)이 이 유형으로 계산 방식을 분기한다.

    - STOCK(저량): 최근 분기값 그대로.
    - FLOW_TTM(유량): 직전 4분기 합(TTM).
    - HYBRID(하이브리드): 분자 TTM ÷ 분모 최근값(저량). ROE/ROA (D-03).
    - PER_SHARE(주당): 분모만 노출(shares_outstanding). 가격은 호출자 주입(D-07).
    - DERIVED(파생): 다른 metric의 2차 파생(PEG = PER ÷ EPS 성장률, 엔진 계산).
    """

    STOCK = "저량"
    FLOW_TTM = "유량"
    HYBRID = "하이브리드"
    PER_SHARE = "주당"
    DERIVED = "파생"


@dataclass(frozen=True)
class MetricDef:
    """단일 지표 선언. 산식은 mtype이 결정 — 신규 지표는 본 dataclass 1줄 추가(SC3).

    - name: 지표 이름(REGISTRY 내 고유 키, 가격 의존 metric의 price_denominator 참조 대상).
    - mtype: 산식 유형(MetricType).
    - numerator/denominator: 논리 field명(store field 어휘 그대로). 가격 의존 4종은
      None(비율 미계산, D-07) — 분모 metric은 price_denominator로 참조.
    - is_ratio_0_1: 0~1 비율(마진 GPM/OPM) 표기 힌트.
    - price_denominator: 가격 의존 4종이 참조하는 분모 metric 이름(가격 비결합, D-07).
    """

    name: str
    mtype: MetricType
    numerator: str | None
    denominator: str | None
    is_ratio_0_1: bool = False
    price_denominator: str | None = None


# REGISTRY: D-01 9종(PER/PEG/GPM/OPM/PBR/PCR/PSR/ROE/ROA) + 가격 의존 4종이 참조할
# 분모 metric 4종(EPS_ttm/BPS/SPS/OCF_ps). 논리 field명은 store field 어휘 그대로.
REGISTRY: tuple[MetricDef, ...] = (
    # --- 유량 마진(FLOW_TTM, 0~1 비율) — 재현 2종 ---
    MetricDef("GPM", MetricType.FLOW_TTM, "gross_profit", "revenue", is_ratio_0_1=True),
    MetricDef("OPM", MetricType.FLOW_TTM, "op_income", "revenue", is_ratio_0_1=True),
    # --- 하이브리드(분자 TTM ÷ 분모 최근값, D-03) — 신규 2종 ---
    MetricDef("ROE", MetricType.HYBRID, "net_income", "total_equity"),
    MetricDef("ROA", MetricType.HYBRID, "net_income", "total_assets"),
    # --- 주당 분모 metric(PER_SHARE) — 가격 의존 4종이 참조 ---
    # EPS_ttm: net_income TTM ÷ 최근 shares (A4 — eps 4합 대신 분자 net_income).
    MetricDef("EPS_ttm", MetricType.PER_SHARE, "net_income", "shares_outstanding"),
    MetricDef("BPS", MetricType.PER_SHARE, "total_equity", "shares_outstanding"),
    MetricDef("SPS", MetricType.PER_SHARE, "revenue", "shares_outstanding"),
    MetricDef("OCF_ps", MetricType.PER_SHARE, "operating_cash_flow", "shares_outstanding"),
    # --- 가격 의존 4종(D-07 가격 비결합) — 비율 미계산, 분모 metric 이름만 참조 ---
    MetricDef("PER", MetricType.PER_SHARE, None, None, price_denominator="EPS_ttm"),
    MetricDef("PBR", MetricType.PER_SHARE, None, None, price_denominator="BPS"),
    MetricDef("PCR", MetricType.PER_SHARE, None, None, price_denominator="OCF_ps"),
    MetricDef("PSR", MetricType.PER_SHARE, None, None, price_denominator="SPS"),
    # --- 파생(2차) — PEG = PER ÷ EPS 성장률 (08-03 _compute_peg) ---
    MetricDef("PEG", MetricType.DERIVED, None, None),
)
