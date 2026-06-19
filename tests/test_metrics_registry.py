"""metrics_registry 정의 무결성·유형·소스 매핑·확장성 단언 (FUND-09 SC1/SC3).

선언적 registry(MetricType enum + MetricDef dataclass + REGISTRY 9종)가
- 9종 지표를 정확한 유형으로 선언하고,
- numerator/denominator 논리 field명이 store field 어휘와 정합하며(T-08-03),
- 각 논리 field가 기존 dart_account_map 매핑에 연결되고(SC1, 새 dict 발명 금지),
- 신규 지표 추가가 REGISTRY 튜플 1줄로 가능함(SC3 확장성)
을 강제한다. 네트워크·DB·파일 입력 0 (정적 선언 검증).
"""

from __future__ import annotations

from stocksig.io.dart_account_map import DART_ACCOUNT_ID_MAP
from stocksig.io.metrics_registry import (
    REGISTRY,
    MetricDef,
    MetricType,
)

# store field 어휘 (raw_facts.field — MetricDef numerator/denominator는 이 문자열을 그대로 사용).
_STORE_FIELD_VOCAB = {
    "revenue",
    "gross_profit",
    "op_income",
    "net_income",
    "eps",
    "operating_cash_flow",
    "total_equity",
    "total_liabilities",
    "total_assets",
    "shares_outstanding",
}


def _by_name() -> dict[str, MetricDef]:
    return {m.name: m for m in REGISTRY}


def test_registry_has_nine_metrics():
    """REGISTRY의 name 집합이 9종 핵심 지표를 포함한다(D-01 — 재현4종+신규5종)."""
    names = {m.name for m in REGISTRY}
    assert {"PER", "PEG", "GPM", "OPM", "PBR", "PCR", "PSR", "ROE", "ROA"} <= names


def test_roe_is_hybrid():
    """ROE = HYBRID (분자 TTM ÷ 분모 최근값, D-03), net_income/total_equity."""
    roe = _by_name()["ROE"]
    assert roe.mtype is MetricType.HYBRID
    assert roe.numerator == "net_income"
    assert roe.denominator == "total_equity"


def test_roa_is_hybrid():
    """ROA = HYBRID, net_income/total_assets."""
    roa = _by_name()["ROA"]
    assert roa.mtype is MetricType.HYBRID
    assert roa.numerator == "net_income"
    assert roa.denominator == "total_assets"


def test_gpm_opm_flow_ttm():
    """GPM/OPM = FLOW_TTM, is_ratio_0_1 True (0~1 비율 마진)."""
    bn = _by_name()
    gpm = bn["GPM"]
    opm = bn["OPM"]
    assert gpm.mtype is MetricType.FLOW_TTM
    assert gpm.is_ratio_0_1 is True
    assert (gpm.numerator, gpm.denominator) == ("gross_profit", "revenue")
    assert opm.mtype is MetricType.FLOW_TTM
    assert opm.is_ratio_0_1 is True
    assert (opm.numerator, opm.denominator) == ("op_income", "revenue")


def test_pershare_denominators():
    """주당 4종(EPS_ttm/BPS/SPS/OCF_ps)의 분모는 shares_outstanding (PER_SHARE 유형)."""
    bn = _by_name()
    for name in ("EPS_ttm", "BPS", "SPS", "OCF_ps"):
        m = bn[name]
        assert m.mtype is MetricType.PER_SHARE
        assert m.denominator == "shares_outstanding"


def test_price_metrics_reference_denominator():
    """가격 의존 4종(PER/PBR/PCR/PSR)은 비율을 계산하지 않고 분모 metric 이름만 참조(D-07)."""
    bn = _by_name()
    assert bn["PER"].price_denominator == "EPS_ttm"
    assert bn["PBR"].price_denominator == "BPS"
    assert bn["PCR"].price_denominator == "OCF_ps"
    assert bn["PSR"].price_denominator == "SPS"
    # 가격 비결합: 분모 metric만 참조하고 numerator/denominator는 노출하지 않는다.
    for name in ("PER", "PBR", "PCR", "PSR"):
        assert bn[name].numerator is None
        assert bn[name].denominator is None


def test_peg_is_derived():
    """PEG = DERIVED (08-03 엔진이 _compute_peg로 2차 계산)."""
    assert _by_name()["PEG"].mtype is MetricType.DERIVED


def test_field_vocab_matches_store():
    """모든 MetricDef의 numerator/denominator가 store field 어휘 집합에 속한다(T-08-03)."""
    for m in REGISTRY:
        for fld in (m.numerator, m.denominator):
            if fld is not None:
                assert fld in _STORE_FIELD_VOCAB, f"{m.name}: {fld!r} ∉ store 어휘"


def test_source_mapping_connected():
    """각 논리 field가 기존 dart_account_map.DART_ACCOUNT_ID_MAP 키에 존재(SC1)."""
    for m in REGISTRY:
        for fld in (m.numerator, m.denominator):
            if fld is not None:
                assert fld in DART_ACCOUNT_ID_MAP, f"{m.name}: {fld!r} 매핑 미연결"


def test_add_new_metric_is_one_line():
    """REGISTRY에 임의 MetricDef 1개 추가 시 기존 항목 불변·name 집합 확장됨(SC3 확장성)."""
    before = {m.name for m in REGISTRY}
    new_metric = MetricDef(
        name="FOO",
        mtype=MetricType.FLOW_TTM,
        numerator="revenue",
        denominator="total_assets",
    )
    extended = REGISTRY + (new_metric,)
    after = {m.name for m in extended}
    assert before <= after
    assert "FOO" in after
    # 기존 REGISTRY 불변 (frozen tuple — 원본 객체 미변경).
    assert {m.name for m in REGISTRY} == before


def test_metricdef_is_frozen():
    """MetricDef는 frozen dataclass — 선언 후 불변(상수 안전)."""
    import dataclasses

    m = REGISTRY[0]
    try:
        m.name = "MUTATED"  # type: ignore[misc]
    except dataclasses.FrozenInstanceError:
        return
    raise AssertionError("MetricDef must be frozen")
