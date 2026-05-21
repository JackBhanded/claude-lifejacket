"""Exhaustive tests for safewrite.py — the bedrock.

If these pass, we can trust a tool that edits the user's memory files. Each test
maps to one of the seven safety non-negotiables (noted in the docstrings).

Run from the project root:

    pip install -e ".[dev]"   # or just: pip install pytest
    pytest -q
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from claude_lifejacket.safewrite import (
    MarkerError,
    SyncStatus,
    make_markers,
    read_managed_block,
    remove_managed_block,
    sync_managed_block,
    write_text_atomic,
)

BID = "projects"
V = 1


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def _begin(bid=BID, v=V):
    return f"<!-- LIFEJACKET:BEGIN id={bid} v={v} -->"


def write_raw(path: Path, text: str) -> None:
    path.write_bytes(text.encode("utf-8"))


# --------------------------------------------------------------------------- #
# Marker validation (#3 — markers must be unambiguous & safe)
# --------------------------------------------------------------------------- #

def test_make_markers_basic():
    begin, end_head = make_markers("projects", 1)
    assert begin == "<!-- LIFEJACKET:BEGIN id=projects v=1 -->"
    assert end_head == "<!-- LIFEJACKET:END id=projects v=1"


@pytest.mark.parametrize("bad", ["", "has space", "semi;colon", "star*", "a/b", "(grp)"])
def test_bad_block_id_raises(bad):
    with pytest.raises(MarkerError):
        make_markers(bad, 1)


# --------------------------------------------------------------------------- #
# Create (#1 atomic, #2 backup-not-needed-for-new)
# --------------------------------------------------------------------------- #

def test_create_new_file(tmp_path):
    f = tmp_path / "CLAUDE.md"
    r = sync_managed_block(f, BID, V, "hello world")
    assert r.status == SyncStatus.CREATED
    assert r.changed is True
    assert f.exists()
    text = f.read_text(encoding="utf-8")
    assert _begin() in text
    assert "hello world" in text
    assert "sha256=" in text
    # No backup for a brand-new file.
    assert r.backup_path is None


def test_create_when_disabled_skips(tmp_path):
    f = tmp_path / "CLAUDE.md"
    r = sync_managed_block(f, BID, V, "hi", create_if_missing=False)
    assert r.status == SyncStatus.SKIPPED
    assert not f.exists()


def test_no_bom_written(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "content")
    raw = f.read_bytes()
    assert not raw.startswith(b"\xef\xbb\xbf")  # never write a BOM (#5)


# --------------------------------------------------------------------------- #
# Append a block to a file that already has user content (#3 — touch only ours)
# --------------------------------------------------------------------------- #

def test_append_preserves_user_content(tmp_path):
    f = tmp_path / "CLAUDE.md"
    user_text = "# My notes\n\nThese are sacred.\n"
    write_raw(f, user_text)
    r = sync_managed_block(f, BID, V, "managed bit")
    assert r.status == SyncStatus.CREATED
    out = f.read_text(encoding="utf-8")
    assert out.startswith("# My notes")
    assert "These are sacred." in out
    assert "managed bit" in out


def test_append_disabled_leaves_file_untouched(tmp_path):
    f = tmp_path / "CLAUDE.md"
    user_text = "# Mine\n"
    write_raw(f, user_text)
    r = sync_managed_block(f, BID, V, "x", create_if_missing=False)
    assert r.status == SyncStatus.SKIPPED
    assert f.read_text(encoding="utf-8") == user_text


# --------------------------------------------------------------------------- #
# Idempotency (#4 — content hash → skip identical writes)
# --------------------------------------------------------------------------- #

def test_unchanged_is_idempotent(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "stable content")
    mtime1 = f.stat().st_mtime_ns
    r = sync_managed_block(f, BID, V, "stable content")
    assert r.status == SyncStatus.UNCHANGED
    assert r.changed is False
    # No write happened, so mtime is unchanged.
    assert f.stat().st_mtime_ns == mtime1


# --------------------------------------------------------------------------- #
# Update (#1 atomic, #2 backup-before-write)
# --------------------------------------------------------------------------- #

def test_update_rewrites_block_and_backs_up(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "version one")
    r = sync_managed_block(f, BID, V, "version two")
    assert r.status == SyncStatus.UPDATED
    assert r.changed is True
    assert r.backup_path is not None and r.backup_path.exists()
    out = f.read_text(encoding="utf-8")
    assert "version two" in out
    assert "version one" not in out
    # The backup holds the prior content.
    assert "version one" in r.backup_path.read_text(encoding="utf-8")


def test_update_preserves_surrounding_content(tmp_path):
    f = tmp_path / "CLAUDE.md"
    head = "# Top\n\n"
    tail = "\n\n# Bottom\n"
    block = _begin() + "\nold\n<!-- LIFEJACKET:END id=projects v=1 sha256=" + \
        ("0" * 64) + " -->"
    write_raw(f, head + block + tail)
    # Use force because the hand-written hash won't match (simulates our own
    # prior write only loosely); first read what's there.
    r = sync_managed_block(f, BID, V, "new", force=True)
    assert r.status == SyncStatus.UPDATED
    out = f.read_text(encoding="utf-8")
    assert out.startswith("# Top")
    assert out.rstrip().endswith("# Bottom")
    assert "new" in out
    assert "old" not in out


# --------------------------------------------------------------------------- #
# Tamper detection (#4, #7 — never clobber a hand-edit unless forced)
# --------------------------------------------------------------------------- #

def test_handedit_detected_and_refused(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "original")
    # Simulate the user editing inside our block by hand.
    text = f.read_text(encoding="utf-8").replace("original", "I changed this myself")
    write_raw(f, text)
    r = sync_managed_block(f, BID, V, "lifejacket wants this")
    assert r.status == SyncStatus.TAMPERED
    assert r.changed is False
    # File is untouched — the user's edit survives.
    assert "I changed this myself" in f.read_text(encoding="utf-8")
    assert "lifejacket wants this" not in f.read_text(encoding="utf-8")


def test_force_overrides_tamper(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "original")
    text = f.read_text(encoding="utf-8").replace("original", "hand edit")
    write_raw(f, text)
    r = sync_managed_block(f, BID, V, "forced new", force=True)
    assert r.status == SyncStatus.UPDATED
    assert "forced new" in f.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# Ambiguous markers → CONFLICT, change nothing (#3, #7)
# --------------------------------------------------------------------------- #

def test_duplicate_blocks_refused(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "first")
    # Append a second identical-id block by hand.
    text = f.read_text(encoding="utf-8")
    text = text + "\n\n" + _begin() + "\nsecond\n<!-- LIFEJACKET:END id=projects v=1 -->\n"
    write_raw(f, text)
    before = f.read_text(encoding="utf-8")
    r = sync_managed_block(f, BID, V, "third")
    assert r.status == SyncStatus.CONFLICT
    assert r.changed is False
    assert f.read_text(encoding="utf-8") == before  # untouched
    assert r.detail["block_count"] == 2


# --------------------------------------------------------------------------- #
# Line-ending preservation (#5)
# --------------------------------------------------------------------------- #

def test_crlf_preserved_on_update(tmp_path):
    f = tmp_path / "CLAUDE.md"
    # Create a CRLF file with our block.
    sync_managed_block(f, BID, V, "one")
    crlf = f.read_text(encoding="utf-8").replace("\n", "\r\n")
    write_raw(f, crlf)
    r = sync_managed_block(f, BID, V, "two", force=True)
    assert r.status in (SyncStatus.UPDATED, SyncStatus.UNCHANGED)
    raw = f.read_bytes()
    # Should still be CRLF-dominant, not have introduced bare LFs.
    assert raw.count(b"\r\n") > 0
    # No lone LF that isn't part of CRLF.
    assert raw.count(b"\n") == raw.count(b"\r\n")


def test_lf_stays_lf(tmp_path):
    f = tmp_path / "CLAUDE.md"
    write_raw(f, "# header\nbody\n")  # pure LF
    sync_managed_block(f, BID, V, "added")
    raw = f.read_bytes()
    assert b"\r\n" not in raw


# --------------------------------------------------------------------------- #
# Unicode content survives round-trip
# --------------------------------------------------------------------------- #

def test_unicode_content(tmp_path):
    f = tmp_path / "CLAUDE.md"
    inner = "café — naïve — 日本語 — 🛟 lifejacket"
    sync_managed_block(f, BID, V, inner)
    got = read_managed_block(f, BID)
    assert got == inner


# --------------------------------------------------------------------------- #
# Dry-run never writes (#1, #2 — safety: preview without risk)
# --------------------------------------------------------------------------- #

def test_dry_run_create_does_not_write(tmp_path):
    f = tmp_path / "CLAUDE.md"
    r = sync_managed_block(f, BID, V, "preview", dry_run=True)
    assert r.status == SyncStatus.CREATED
    assert r.changed is False
    assert not f.exists()


def test_dry_run_update_does_not_write(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "real")
    before = f.read_bytes()
    r = sync_managed_block(f, BID, V, "would change", dry_run=True)
    assert r.status == SyncStatus.UPDATED
    assert r.changed is False
    assert f.read_bytes() == before


# --------------------------------------------------------------------------- #
# read_managed_block
# --------------------------------------------------------------------------- #

def test_read_missing_file_returns_none(tmp_path):
    assert read_managed_block(tmp_path / "nope.md", BID) is None


def test_read_after_create(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "the inner stuff")
    assert read_managed_block(f, BID) == "the inner stuff"


def test_read_returns_none_when_duplicate(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, V, "a")
    text = f.read_text(encoding="utf-8")
    write_raw(f, text + "\n" + _begin() + "\nb\n<!-- LIFEJACKET:END id=projects v=1 -->\n")
    assert read_managed_block(f, BID) is None


# --------------------------------------------------------------------------- #
# remove_managed_block
# --------------------------------------------------------------------------- #

def test_remove_block_keeps_user_content(tmp_path):
    f = tmp_path / "CLAUDE.md"
    write_raw(f, "# Mine\n\nkeep me\n")
    sync_managed_block(f, BID, V, "managed")
    r = remove_managed_block(f, BID)
    assert r.status == SyncStatus.UPDATED
    out = f.read_text(encoding="utf-8")
    assert "keep me" in out
    assert "LIFEJACKET" not in out


def test_remove_nothing_to_do(tmp_path):
    f = tmp_path / "CLAUDE.md"
    write_raw(f, "# Mine\n")
    r = remove_managed_block(f, BID)
    assert r.status == SyncStatus.SKIPPED
    assert f.read_text(encoding="utf-8") == "# Mine\n"


# --------------------------------------------------------------------------- #
# Multiple blocks with different ids coexist
# --------------------------------------------------------------------------- #

def test_two_different_ids_coexist(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, "projects", V, "proj content")
    sync_managed_block(f, "profile", V, "profile content")
    assert read_managed_block(f, "projects") == "proj content"
    assert read_managed_block(f, "profile") == "profile content"
    # Updating one doesn't disturb the other.
    sync_managed_block(f, "projects", V, "proj v2")
    assert read_managed_block(f, "projects") == "proj v2"
    assert read_managed_block(f, "profile") == "profile content"


# --------------------------------------------------------------------------- #
# Version upgrade: a block written under v1 is recognised & updated to v2
# --------------------------------------------------------------------------- #

def test_version_upgrade(tmp_path):
    f = tmp_path / "CLAUDE.md"
    sync_managed_block(f, BID, 1, "v1 content")
    r = sync_managed_block(f, BID, 2, "v2 content")
    assert r.status == SyncStatus.UPDATED
    out = f.read_text(encoding="utf-8")
    assert "v=2" in out
    assert "v1 content" not in out
    assert read_managed_block(f, BID) == "v2 content"


# --------------------------------------------------------------------------- #
# The result object speaks human (#every message brings a smile)
# --------------------------------------------------------------------------- #

def test_results_have_friendly_messages(tmp_path):
    f = tmp_path / "CLAUDE.md"
    r = sync_managed_block(f, BID, V, "x")
    assert r.message and len(r.message) > 5
    assert r.ok


# --------------------------------------------------------------------------- #
# write_text_atomic — the public primitive the store reuses
# --------------------------------------------------------------------------- #

def test_write_text_atomic_creates_dirs_and_no_bom(tmp_path):
    f = tmp_path / "nested" / "deep" / "registry.json"
    bak = write_text_atomic(f, '{"hi": true}')
    assert f.exists()
    assert bak is None  # new file, nothing to back up
    assert not f.read_bytes().startswith(b"\xef\xbb\xbf")
    assert f.read_text(encoding="utf-8") == '{"hi": true}'


def test_write_text_atomic_overwrites(tmp_path):
    f = tmp_path / "x.txt"
    write_text_atomic(f, "first")
    write_text_atomic(f, "second")
    assert f.read_text(encoding="utf-8") == "second"


def test_write_text_atomic_backup(tmp_path):
    f = tmp_path / "x.txt"
    write_text_atomic(f, "original")
    bak = write_text_atomic(f, "changed", backup=True)
    assert bak is not None and bak.exists()
    assert bak.read_text(encoding="utf-8") == "original"
    assert f.read_text(encoding="utf-8") == "changed"
