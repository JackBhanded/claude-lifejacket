"""Tests for appmodel.py — the GUI's brains, verified without any GUI."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_lifejacket.appmodel import (
    add_candidates,
    build_snapshot,
    do_sync,
    hook_is_on,
    set_autosync,
)
from claude_lifejacket.discover import Candidate
from claude_lifejacket.store import Project, Store


def make_env(tmp_path):
    lj = tmp_path / "lj"
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    proot = tmp_path / "Projects"
    proot.mkdir()
    (proot / "Found Project").mkdir()
    s = Store(home=lj)
    s.init()
    s.add(Project.create("In Logbook", status="active"))
    return s, ch, proot


def test_snapshot_lists_projects_and_candidates(tmp_path):
    s, ch, proot = make_env(tmp_path)
    snap = build_snapshot(s, claude_home=ch, projects_root=proot)
    assert [p.name for p in snap.projects] == ["In Logbook"]
    assert "Found Project" in [c.name for c in snap.candidates]
    assert snap.hook_on is False
    # One surface (the fake ~/.claude exists), never synced yet.
    assert snap.surfaces and snap.surfaces[0].state == "never"


def test_snapshot_surface_in_sync_after_sync(tmp_path):
    s, ch, proot = make_env(tmp_path)
    do_sync(s, claude_home=ch)
    snap = build_snapshot(s, claude_home=ch, projects_root=proot)
    assert snap.surfaces[0].state == "in_sync"


def test_add_candidates(tmp_path):
    s, ch, proot = make_env(tmp_path)
    snap = build_snapshot(s, claude_home=ch, projects_root=proot)
    n = add_candidates(s, snap.candidates)
    assert n >= 1
    assert "Found Project" in [p.name for p in s.load()]


def test_set_autosync_toggles(tmp_path):
    s, ch, proot = make_env(tmp_path)
    assert hook_is_on(ch) is False
    set_autosync(True, claude_home=ch)
    assert hook_is_on(ch) is True
    set_autosync(False, claude_home=ch)
    assert hook_is_on(ch) is False


def test_do_sync_writes_block(tmp_path):
    s, ch, proot = make_env(tmp_path)
    reports = do_sync(s, claude_home=ch)
    assert reports and reports[0].result.changed
    assert (ch / "CLAUDE.md").exists()


def test_snapshot_includes_recent_activity(tmp_path):
    s, ch, proot = make_env(tmp_path)
    do_sync(s, claude_home=ch)
    snap = build_snapshot(s, claude_home=ch, projects_root=proot)
    assert snap.recent, "snapshot should carry recent activity lines after a sync"
    assert any("sync" in line for line in snap.recent)
