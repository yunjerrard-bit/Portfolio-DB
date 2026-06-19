"""metrics_engine RED 스캐폴드 + fetch_raw_quarters store 헬퍼 GREEN (FUND-09).

본 파일은 두 부분:
  1) store 입력 경로(fetch_raw_quarters) — **GREEN** (08-01에서 구현·검증).
  2) 08-03 Wave 2 엔진 계산 테스트 — **RED 스캐폴드**. `stocksig.io.metrics_engine`
     모듈이 아직 없으므로 본문은 `pytest.skip`으로 collect만 통과시킨다.
     08-03이 모듈을 채우면서 각 함수 본문을 실제 단언으로 교체한다.

-k 마커 ↔ RESEARCH Test Map(L449-454):
  test_type_rules               (SC2) 저량=최근/유량=TTM4합/하이브리드=분자TTM÷분모최근
  test_reproduce                (SC3) 저장 raw만으로 PER/PEG/GPM/OPM 재현 + ROE/PBR 신규
  test_ttm_missing              (SC4) TTM 4분기 결손 → 빈값+사유(0 대체·부분합산 금지, D-05)
  test_provenance_or_pershare   (SC5) per-metric provenance 라벨 + per-share 분모/가격 분리
  test_edgar_q4                 (Pitfall 1) EDGAR Q4 = 빈값+사유(FY raw 부재로 보정 불가)
"""

from __future__ import annotations

import pytest

from fixtures.raw_quarters import raw_row
from stocksig.io import fundamentals_store as fs

# 08-03 Wave 2에서 stocksig.io.metrics_engine 구현 전까지 collect만 통과시키는 사유.
_ENGINE_TODO = "08-03 Wave 2에서 구현 (stocksig.io.metrics_engine 미존재)"


# === store 입력 경로 — GREEN (08-01 구현) ===================================


def test_fetch_raw_quarters_returns_sorted():
    """upsert한 2026Q1·2025Q4 revenue 행 → quarter 오름차순 list 반환."""
    fs.upsert_quarters(
        [
            raw_row(quarter="2026Q1", value=2000.0, accession="acc-q1"),
            raw_row(quarter="2025Q4", value=1000.0, accession="acc-q4"),
        ]
    )
    rows = fs.fetch_raw_quarters("AAPL")

    quarters = [r[0] for r in rows]
    assert quarters == ["2025Q4", "2026Q1"], "quarter 오름차순 정렬"

    # 각 행에 (quarter, source, field, value, period_type, reprt_code, unit) 포함.
    first = rows[0]
    assert len(first) == 7
    quarter, source, field, value, period_type, reprt_code, unit = first
    assert quarter == "2025Q4"
    assert source == "EDGAR"
    assert field == "revenue"
    assert value == 1000.0
    assert period_type == "duration"
    assert reprt_code is None
    assert unit == "USD"


def test_fetch_raw_quarters_empty():
    """미존재 ticker → 빈 list."""
    assert fs.fetch_raw_quarters("NOSUCH") == []


# === 엔진 계산 — RED 스캐폴드 (08-03이 채움) ================================


def test_type_rules():
    """SC2: 저량=최근값 / 유량=TTM 4분기 합 / 하이브리드=분자TTM÷분모최근."""
    pytest.skip(_ENGINE_TODO)


def test_reproduce():
    """SC3: 저장 raw만으로 PER/PEG/GPM/OPM 재현 + ROE/PBR 신규 무재호출 산출."""
    pytest.skip(_ENGINE_TODO)


def test_ttm_missing():
    """SC4: TTM 4분기 중 결손 → 빈값+사유 (0 대체·부분합산 금지, D-05)."""
    pytest.skip(_ENGINE_TODO)


def test_provenance_or_pershare():
    """SC5: per-metric provenance 라벨 + per-share 분모/가격 주입 분리."""
    pytest.skip(_ENGINE_TODO)


def test_edgar_q4():
    """Pitfall 1: EDGAR Q4 = 빈값+사유 (FY raw 부재 → FY−9M 보정 미구현, 자연 결손)."""
    pytest.skip(_ENGINE_TODO)
