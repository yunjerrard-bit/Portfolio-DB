"""트렌드 히스토리 오케스트레이션 엔트리 (Plan 09-03, FUND-10 / D-09/10/14/15).

`run_history(tickers_path, output_dir)` — 시트1(portfolio) 흐름과 **완전 분리**된
별도 산출 경로(D-15). DB(`fundamentals.db`)에 적재된 분기 펀더멘털만으로
`fundamentals_history_YYYYMMDD.xlsx`를 별도 파일로 렌더한다(D-14). 신규 산식·외부
펀더멘털 호출 0 — Phase 8 엔진(`compute_matrix`/`price_ratio`/`compute_peg_cell`)·
Phase 9 Plan 01 가격(`quarter_end_prices`)·Plan 02 워크북/시트 writer 만 소비한다.

흐름:
  (1) DB 미적재 게이트: `count_rows()==0` → 한국어 안내 print 후 `return None`(예외 아님, D-15).
  (2) 종목 정렬: US → KR 그룹화 후 각 그룹 내 알파벳순(D-03).
  (3) ticker 별 `compute_matrix`(외부 호출 0) + `quarter_end_prices`(D-09) →
      가격 의존 4종(PER/PBR/PCR/PSR) `price_ratio` 주입 + 분기별 PEG `compute_peg_cell`(D-10).
  (4) 다종목 분기 합집합 → reversed(최신 왼쪽 D-01); (분기열×산업) peer/4분기 전 lookup 구성(WARNING-3).
  (5) `make_history_workbook` → 9 지표 시트 + [원천] + [최신 스냅샷] write → path 반환.

시트명 sanitize: Excel 금지문자 `[]` 를 제거한 한글명("원천"/"최신 스냅샷")으로 worksheet 생성(D-15 호출자 책임).
예외 격리: 종목별 try/except — 한 종목 실패가 전체 렌더를 막지 않음(T-09-08), `type(exc).__name__`만 로깅(T-09-07).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

from stocksig.io.metrics_engine import (
    _calendar_quarter_offset,
    compute_matrix,
    compute_peg_cell,
    price_ratio,
)
from stocksig.io.metrics_registry import REGISTRY

logger = logging.getLogger("history_render")

# 매트릭스에 가격을 주입해 채울 가격 의존 4종 → 분모 metric (D-07 price_denominator).
_PRICE_DEPENDENT: dict[str, str] = {
    m.name: m.price_denominator
    for m in REGISTRY
    if m.price_denominator is not None
}

# 시트1·종목시트 흐름과의 결손 게이트 공유(신규 정의 0).
from stocksig.io.fundamentals import _is_missing  # noqa: E402 (지표 lookup 가드)

# 9 지표 시트 순서(D-01) — REGISTRY 의 표시 대상 9종.
_SHEET_METRICS: list[str] = ["PER", "PEG", "GPM", "OPM", "PBR", "PCR", "PSR", "ROE", "ROA"]


def _sanitize_sheet_name(name: str) -> str:
    """Excel 금지문자(`[]:*?/\\`) 제거 — `[원천]`/`[최신 스냅샷]` → 한글명(D-15)."""
    out = name
    for ch in "[]:*?/\\":
        out = out.replace(ch, "")
    return out.strip()


def _sorted_tickers(specs) -> list:
    """US → KR 그룹화 후 각 그룹 내 심볼 알파벳순(D-03)."""
    from stocksig.io.market_kind import classify_market

    us = sorted((s for s in specs if classify_market(s.symbol) == "US"),
                key=lambda s: s.symbol)
    kr = sorted((s for s in specs if classify_market(s.symbol) == "KR"),
                key=lambda s: s.symbol)
    return us + kr


def _inject_prices(matrix: dict, quarters: list[str], qmap: dict, current: float | None,
                   latest_q: str | None) -> None:
    """가격 의존 4종 price_ratio 주입 + 분기별 PEG compute_peg_cell(D-09/10) — in-place.

    분기별 가격: 최신 분기 = 현재가, 그 외 = 분기말 종가(qmap.get, Pitfall 2 .get 가드).
    PEG = compute_peg_cell(PER.value, EPS_now, EPS_prior(4분기 전)).
    """
    eps_map = matrix.get("EPS_ttm", {})
    for q in quarters:
        price = current if (latest_q is not None and q == latest_q) else qmap.get(q)

        # (a) 가격 의존 4종 — 분모 per-share 셀에 가격 주입.
        for metric, denom in _PRICE_DEPENDENT.items():
            denom_cell = matrix.get(denom, {}).get(q)
            matrix.setdefault(metric, {})[q] = price_ratio(denom_cell, price)

        # (b) 분기별 PEG (3단 계약, D-10) — PER 가격 주입 후 EPS 성장률.
        per = matrix.get("PER", {}).get(q)
        per_value = per.value if per is not None else None
        eps_now = eps_map.get(q)
        eps_now_v = eps_now.value if eps_now is not None else None
        qp = _calendar_quarter_offset(q, -4)
        eps_prior = eps_map.get(qp)
        eps_prior_v = eps_prior.value if eps_prior is not None else None
        matrix.setdefault("PEG", {})[q] = compute_peg_cell(per_value, eps_now_v, eps_prior_v)


def run_history(tickers_path: str, output_dir: str) -> Path | None:
    """DB → fundamentals_history_YYYYMMDD.xlsx 별도 파일 렌더 (FUND-10).

    DB 미적재(count_rows()==0) 시 한국어 안내 후 None 반환(예외 아님, D-15).
    시트1(portfolio) 흐름·시트1 모듈 미참조(완전 분리, D-15).
    """
    # 늦은 import: --help 가 무거운 의존성 import 전에 동작하도록(main.py 컨벤션 정합).
    from stocksig.io.company import fetch_company_name
    from stocksig.io.fundamentals_store import count_rows, fetch_raw_quarters
    from stocksig.io.input import read_tickers_extended
    from stocksig.io.market_kind import classify_market
    from stocksig.io.quarter_price import quarter_end_prices
    from stocksig.output.history_workbook import make_history_workbook
    from stocksig.output.sheet_metric_matrix import write_metric_sheet
    from stocksig.output.sheet_raw import write_raw_sheet
    from stocksig.output.sheet_snapshot import write_snapshot_sheet

    # (1) DB 미적재 게이트 (D-15).
    if count_rows() == 0:
        print(
            "펀더멘털 DB가 비어 있습니다. 먼저 `uv run python main.py`를 실행해 "
            "분기 펀더멘털을 적재한 뒤 다시 `history`를 실행하세요."
        )
        return None

    # (2) 종목 정렬 (US → KR, 그룹 내 알파벳순 D-03).
    specs = _sorted_tickers(read_tickers_extended(tickers_path))
    sorted_symbols = [s.symbol for s in specs]
    industry_of = {s.symbol: (s.industry or "") for s in specs}
    tier_of = {s.symbol: (s.tier or "") for s in specs}
    market_of = {s.symbol: classify_market(s.symbol) for s in specs}

    # (3) ticker 별 매트릭스 + 가격 주입 (외부 펀더멘털 호출 0, 종목별 예외 격리 T-09-08).
    per_ticker: dict[str, dict] = {}
    company_of: dict[str, str] = {}
    raw_by_ticker: dict[str, list] = {}
    for sym in sorted_symbols:
        try:
            matrix = compute_matrix(sym)
            qmap, current = quarter_end_prices(sym)
            quarters = sorted({
                q for cells in matrix.values() for q in cells
            })
            latest_q = quarters[-1] if quarters else None
            _inject_prices(matrix, quarters, qmap, current, latest_q)
            per_ticker[sym] = matrix
            company_of[sym] = fetch_company_name(sym)
            raw_by_ticker[sym] = fetch_raw_quarters(sym)
        except Exception as exc:  # noqa: BLE001 — 종목 1개 실패가 전체 렌더 차단 방지(T-09-08)
            logger.warning(
                "%s | 트렌드 렌더 실패(%s) — 나머지 종목은 계속 진행",
                sym, type(exc).__name__,
            )

    rendered = [s for s in sorted_symbols if s in per_ticker]

    # (4) 분기 합집합 → reversed(최신 왼쪽 D-01, Pitfall 1).
    all_quarters = sorted({
        q
        for matrix in per_ticker.values()
        for cells in matrix.values()
        for q in cells
    })
    display_quarters = list(reversed(all_quarters))

    # (4b) (분기열×산업) peer 모집단 + 4분기 전 셀 lookup (WARNING-3 — 오케스트레이터 책임).
    def peer_lookup(metric: str, quarter: str, industry: str) -> list[float]:
        vals: list[float] = []
        for sym in rendered:
            if industry_of.get(sym, "") != industry:
                continue
            cell = per_ticker[sym].get(metric, {}).get(quarter)
            v = getattr(cell, "value", None) if cell is not None else None
            if not _is_missing(v):
                vals.append(float(v))
        return vals

    def prior_lookup(metric: str, ticker: str, quarter: str):
        qp = _calendar_quarter_offset(quarter, -4)
        return per_ticker.get(ticker, {}).get(metric, {}).get(qp)

    # (5) 워크북 + 시트 write (별도 파일 D-14).
    out_dir = Path(output_dir)
    out_path = out_dir / f"fundamentals_history_{date.today():%Y%m%d}.xlsx"
    wb, formats = make_history_workbook(out_path)
    try:
        # 9 지표 매트릭스 시트.
        for metric in _SHEET_METRICS:
            ws = wb.add_worksheet(_sanitize_sheet_name(metric))
            ticker_rows = [
                {
                    "ticker": sym,
                    "company": company_of.get(sym),
                    "market": market_of.get(sym),
                    "tier": tier_of.get(sym),
                    "industry": industry_of.get(sym),
                    "cells": per_ticker[sym].get(metric, {}),
                }
                for sym in rendered
            ]
            write_metric_sheet(
                wb, ws, metric, ticker_rows, display_quarters, formats,
                peer_lookup, prior_lookup,
            )

        # [원천] long 시트 (시트명 sanitize → "원천").
        ws_raw = wb.add_worksheet(_sanitize_sheet_name("[원천]"))
        write_raw_sheet(ws_raw, raw_by_ticker, formats, sorted_tickers=rendered)

        # [최신 스냅샷] — 매트릭스 최신 열 셀 재사용(재계산 0, D-13).
        ws_snap = wb.add_worksheet(_sanitize_sheet_name("[최신 스냅샷]"))
        snapshot_rows = []
        for sym in rendered:
            matrix = per_ticker[sym]
            sym_quarters = sorted({q for cells in matrix.values() for q in cells})
            sym_latest = sym_quarters[-1] if sym_quarters else None
            metrics = {
                m: matrix.get(m, {}).get(sym_latest)
                for m in _SHEET_METRICS
            }
            snapshot_rows.append({
                "ticker": sym,
                "company": company_of.get(sym),
                "market": market_of.get(sym),
                "tier": tier_of.get(sym),
                "industry": industry_of.get(sym),
                "metrics": metrics,
            })
        write_snapshot_sheet(ws_snap, snapshot_rows, formats)
    finally:
        wb.close()

    logger.info("트렌드 워크북 저장: %s", out_path)
    return out_path
