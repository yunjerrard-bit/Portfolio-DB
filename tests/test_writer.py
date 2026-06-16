"""Phase 2 Wave 3 (02-03): Format cache 확장 테스트.

42 키 (Phase 1 01-14) + 2 키 (이 plan) = 44 키.
"""

from __future__ import annotations

import xlsxwriter

from stocksig.compute.color_rules import SigmaBucket
from stocksig.output.writer import make_workbook


def test_format_cache_has_failed_row_marker(tmp_path):
    wb, formats = make_workbook(tmp_path / "x.xlsx")
    try:
        assert "failed_row_marker" in formats
        assert isinstance(formats["failed_row_marker"], xlsxwriter.format.Format)
    finally:
        wb.close()


def test_format_cache_has_timestamp(tmp_path):
    wb, formats = make_workbook(tmp_path / "x.xlsx")
    try:
        assert "timestamp" in formats
        assert isinstance(formats["timestamp"], xlsxwriter.format.Format)
    finally:
        wb.close()


def test_phase1_keys_intact(tmp_path):
    wb, formats = make_workbook(tmp_path / "x.xlsx")
    try:
        # Sample 6 of the 42 prior keys.
        assert (SigmaBucket.DEFAULT, "price") in formats
        assert (SigmaBucket.HARD_GREEN, "volume") in formats
        assert "header" in formats
        assert "a1_title" in formats
        assert "impulse_green" in formats
        assert "header_bg_ema96" in formats
    finally:
        wb.close()


def test_add_format_count(tmp_path, monkeypatch):
    """Instrumented count of add_format calls — Phase 2 02-03 grew cache 42 → 44;
    표시 개선(날짜 Format) 으로 44 → 45.

    xlsxwriter.Workbook.__init__ itself invokes add_format twice for internal
    defaults (verified empirically). So user-driven calls = total − 2.
    """
    original = xlsxwriter.Workbook.add_format
    user_calls = {"n": 0}
    init_done = {"flag": False}

    def counting_add_format(self, *args, **kwargs):
        # Skip the 2 xlsxwriter-internal calls that happen during __init__.
        if init_done["flag"]:
            user_calls["n"] += 1
        return original(self, *args, **kwargs)

    monkeypatch.setattr(xlsxwriter.Workbook, "add_format", counting_add_format)

    # Probe to count internal __init__ calls first.
    _probe = xlsxwriter.Workbook(str(tmp_path / "probe.xlsx"))
    internal_during_init = user_calls["n"]  # actually 0 because flag still False
    _probe.close()
    # Now start counting user calls.
    init_done["flag"] = True
    user_calls["n"] = 0

    wb, _formats = make_workbook(tmp_path / "x.xlsx")
    try:
        # __init__ added 2 internal calls before make_workbook user calls.
        # We want user-driven add_format invocations from make_workbook.
        # Total observed minus the 2 from this wb's __init__:
        observed = user_calls["n"]
        user_only = observed - 2
        assert user_only == 45, (
            f"expected 45 user add_format calls, got {user_only} "
            f"(observed={observed}, internal_probe_was={internal_during_init})"
        )
    finally:
        wb.close()
