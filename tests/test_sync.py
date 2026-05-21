"""Tests for surfaces.py + sync.py — discovery and the end-to-end sync.

These exercise the real managed-block engine against a fake ~/.claude dir, so
they prove the whole pipeline (store -> digest -> safe injection -> manifest)
without needing an actual Claude install.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_lifejacket.safewrite import SyncStatus, read_managed_block
from claude_lifejacket.store import Project, Store
from claude_lifejacket.surfaces import (
    Surface,
    discover_surfaces,
    load_extra_surfaces,
)
from claude_lifejacket.sync import digest_fingerprint, preview_all, sync_all


# --------------------------------------------------------------------------- #
# fixtures
# --------------------------------------------------------------------------- #

def make_store(tmp_path) -> Store:
    s = Store(home=tmp_path / "lj")
    s.init()
    s.add(Project.create("Claude Meter", status="shipped",
                          repo="github.com/JackBhanded/claude-meter"))
    s.add(Project.create("Claude Lifejacket", status="building",
                          focus="sync-in v0.1"))
    return s


def make_claude_home(tmp_path) -> Path:
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    return ch


# --------------------------------------------------------------------------- #
# surface discovery
# --------------------------------------------------------------------------- #

def test_discovers_claude_code_user_surface(tmp_path):
    ch = make_claude_home(tmp_path)
    surfaces = discover_surfaces(claude_home=ch)
    assert len(surfaces) == 1
    s = surfaces[0]
    assert s.key == "claude-code:user"
    assert s.path == ch / "CLAUDE.md"
    assert s.exists is False  # dir exists, file doesn't yet
    assert s.parent_exists is True


def test_no_surface_when_claude_absent(tmp_path):
    ch = tmp_path / "nonexistent"
    assert discover_surfaces(claude_home=ch) == []


def test_existing_claude_md_detected(tmp_path):
    ch = make_claude_home(tmp_path)
    (ch / "CLAUDE.md").write_text("# mine\n", encoding="utf-8")
    s = discover_surfaces(claude_home=ch)[0]
    assert s.exists is True


def test_extra_paths_added(tmp_path):
    ch = make_claude_home(tmp_path)
    extra = tmp_path / "proj" / "CLAUDE.md"
    extra.parent.mkdir()
    surfaces = discover_surfaces(claude_home=ch, extra_paths=[extra])
    kinds = {s.kind for s in surfaces}
    assert "manual" in kinds
    assert any(s.path == extra for s in surfaces)


def test_load_extra_surfaces_reads_config(tmp_path):
    home = tmp_path / "lj"
    home.mkdir()
    (home / "surfaces.json").write_text(
        json.dumps({"paths": ["~/a/CLAUDE.md", "/tmp/b.md", ""]}),
        encoding="utf-8",
    )
    paths = load_extra_surfaces(home)
    assert len(paths) == 2  # empty string skipped


def test_load_extra_surfaces_missing_is_empty(tmp_path):
    assert load_extra_surfaces(tmp_path / "lj") == []


def test_load_extra_surfaces_malformed_is_empty(tmp_path):
    home = tmp_path / "lj"
    home.mkdir()
    (home / "surfaces.json").write_text("{ broken", encoding="utf-8")
    assert load_extra_surfaces(home) == []


# --------------------------------------------------------------------------- #
# digest fingerprint
# --------------------------------------------------------------------------- #

def test_fingerprint_stable_and_eol_immune(tmp_path):
    a = "line one\nline two"
    b = "line one\r\nline two\n"  # CRLF + trailing newline
    assert digest_fingerprint(a) == digest_fingerprint(b)


# --------------------------------------------------------------------------- #
# end-to-end sync
# --------------------------------------------------------------------------- #

def test_sync_creates_block_in_fresh_claude_md(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    reports = sync_all(s, claude_home=ch)
    assert len(reports) == 1
    r = reports[0]
    assert r.result.status == SyncStatus.CREATED
    assert r.changed is True
    cc = ch / "CLAUDE.md"
    assert cc.exists()
    text = cc.read_text(encoding="utf-8")
    assert "LIFEJACKET:BEGIN" in text
    assert "Claude Meter" in text
    assert "Claude Lifejacket" in text


def test_sync_preserves_existing_user_content(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    cc = ch / "CLAUDE.md"
    cc.write_text("# My own notes\n\nDo not lose this.\n", encoding="utf-8")
    sync_all(s, claude_home=ch)
    text = cc.read_text(encoding="utf-8")
    assert "Do not lose this." in text
    assert "LIFEJACKET:BEGIN" in text


def test_sync_is_idempotent(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    cc = ch / "CLAUDE.md"
    mtime1 = cc.stat().st_mtime_ns
    reports = sync_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.UNCHANGED
    assert cc.stat().st_mtime_ns == mtime1  # no write happened


def test_sync_updates_when_projects_change(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    s.update("claude-lifejacket", status="shipped")
    reports = sync_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.UPDATED
    block = read_managed_block(ch / "CLAUDE.md", "projects")
    assert "shipped" in block


def test_dry_run_writes_nothing(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    reports = preview_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.CREATED
    assert reports[0].changed is False
    assert not (ch / "CLAUDE.md").exists()  # nothing written
    # And no manifest entry recorded on a dry run.
    assert s.load_manifest()["surfaces"] == {}


def test_sync_records_manifest(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    m = s.load_manifest()
    entry = m["surfaces"]["claude-code:user"]
    assert entry["status"] == "created"
    assert entry["path"].endswith("CLAUDE.md")
    assert len(entry["digest_hash"]) == 64


def test_backups_land_in_store_not_claude_home(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)             # create
    s.update("claude-meter", status="v0.2") # change
    sync_all(s, claude_home=ch)             # update -> should back up
    backups = list(s.backups_dir.glob("CLAUDE.md.*.bak"))
    assert backups, "expected a backup of the prior CLAUDE.md in the store"
    # ~/.claude should contain only CLAUDE.md, no stray .bak files.
    stray = list(ch.glob("*.bak"))
    assert stray == []


def test_handedit_inside_block_is_not_clobbered(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    cc = ch / "CLAUDE.md"
    # User edits inside our block by hand.
    tampered = cc.read_text(encoding="utf-8").replace(
        "Claude Meter", "Claude Meter (my note)")
    cc.write_text(tampered, encoding="utf-8")
    reports = sync_all(s, claude_home=ch)
    assert reports[0].result.status == SyncStatus.TAMPERED
    assert "my note" in cc.read_text(encoding="utf-8")  # edit survived


def test_force_overrides_handedit(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    cc = ch / "CLAUDE.md"
    cc.write_text(cc.read_text(encoding="utf-8").replace(
        "Claude Meter", "scribble"), encoding="utf-8")
    reports = sync_all(s, claude_home=ch, force=True)
    assert reports[0].result.status == SyncStatus.UPDATED
    assert "Claude Meter" in cc.read_text(encoding="utf-8")


def test_no_surface_no_crash(tmp_path):
    s = make_store(tmp_path)
    ch = tmp_path / "no-claude-here"
    reports = sync_all(s, claude_home=ch)
    assert reports == []


def test_sync_writes_activity_log(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    sync_all(s, claude_home=ch)
    events = s.read_recent_events()
    assert events, "expected the sync to log activity"
    assert any("sync" in e and "created" in e for e in events)


def test_report_headline_is_friendly(tmp_path):
    s = make_store(tmp_path)
    ch = make_claude_home(tmp_path)
    reports = sync_all(s, claude_home=ch)
    h = reports[0].headline
    assert h.startswith("[")
    assert "Claude Code" in h
