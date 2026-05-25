"""Tests for startup.py — the Run-at-startup registry helper.

These are side-effect-free: the registry-touching calls are only exercised on
non-Windows (where they're guaranteed no-ops), so running the suite never edits
a real machine's Run key.
"""
from __future__ import annotations

import os

import pytest

from claude_lifejacket import startup


def test_value_name_and_key():
    assert startup.VALUE_NAME == "ClaudeLifejacket"
    assert startup.RUN_KEY.endswith(r"CurrentVersion\Run")


def test_unfrozen_in_dev():
    # Running the tests from source → not a frozen exe → nothing to pin.
    assert startup.is_frozen() is False
    assert startup.executable_path() is None


@pytest.mark.skipif(os.name == "nt", reason="off-Windows the calls must be no-ops")
def test_noops_off_windows():
    assert startup.is_enabled() is False
    assert startup.enable() is False
    assert startup.disable() is False
