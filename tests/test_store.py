"""Tests for store.py — the project registry + digest generator."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_lifejacket.store import (
    Project,
    Store,
    StoreError,
    default_home,
    slugify,
)


def fresh(tmp_path) -> Store:
    s = Store(home=tmp_path / "lj")
    s.init()
    return s


# --------------------------------------------------------------------------- #
# slugify
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("name,expected", [
    ("Claude Meter", "claude-meter"),
    ("  Spaced  Out  ", "spaced-out"),
    ("Weird!!Chars##", "weird-chars"),
    ("UPPER", "upper"),
    ("---", "project"),  # degenerate input still yields a safe id
])
def test_slugify(name, expected):
    assert slugify(name) == expected


# --------------------------------------------------------------------------- #
# init / exists
# --------------------------------------------------------------------------- #

def test_init_creates_store(tmp_path):
    s = Store(home=tmp_path / "lj")
    assert not s.exists()
    s.init()
    assert s.exists()
    assert s.registry_path.exists()
    assert s.backups_dir.exists()


def test_init_idempotent_keeps_data(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Keep Me"))
    s.init()  # second init must not wipe the registry
    assert [p.name for p in s.load()] == ["Keep Me"]


def test_load_empty_when_uninitialised(tmp_path):
    s = Store(home=tmp_path / "never")
    assert s.load() == []


# --------------------------------------------------------------------------- #
# add / get / remove / update
# --------------------------------------------------------------------------- #

def test_add_and_get(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Claude Meter", status="shipped",
                          repo="github.com/JackBhanded/claude-meter"))
    p = s.get("claude-meter")
    assert p is not None
    assert p.name == "Claude Meter"
    assert p.status == "shipped"


def test_add_duplicate_refused(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Meter"))
    with pytest.raises(StoreError):
        s.add(Project.create("Meter"))


def test_add_overwrite_allowed(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Meter", status="building"))
    s.add(Project.create("Meter", status="shipped"), overwrite=True)
    assert s.get("meter").status == "shipped"


def test_remove(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Doomed"))
    assert s.remove("doomed") is True
    assert s.get("doomed") is None
    assert s.remove("doomed") is False  # already gone


def test_update(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Lifejacket", status="building"))
    s.update("lifejacket", status="shipped", focus="sync-in v0.1")
    p = s.get("lifejacket")
    assert p.status == "shipped"
    assert p.focus == "sync-in v0.1"


def test_update_missing_raises(tmp_path):
    s = fresh(tmp_path)
    with pytest.raises(StoreError):
        s.update("ghost", status="x")


# --------------------------------------------------------------------------- #
# persistence: data survives a reload, JSON is valid
# --------------------------------------------------------------------------- #

def test_round_trip_to_disk(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Meter", status="shipped"))
    s.add(Project.create("Lifeboat", status="shipped"))
    # New Store instance reading the same files.
    s2 = Store(home=s.home)
    names = sorted(p.name for p in s2.load())
    assert names == ["Lifeboat", "Meter"]


def test_registry_is_valid_json_with_version(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Meter"))
    data = json.loads(s.registry_path.read_text(encoding="utf-8"))
    assert data["version"] >= 1
    assert isinstance(data["projects"], list)
    # None-valued optional fields are omitted, not written as null.
    assert "path" not in data["projects"][0] or data["projects"][0]["path"]


def test_corrupt_registry_raises_friendly(tmp_path):
    s = fresh(tmp_path)
    s.registry_path.write_text("{not valid json", encoding="utf-8")
    with pytest.raises(StoreError):
        s.load()


def test_tolerates_unknown_keys_and_missing_optionals(tmp_path):
    s = fresh(tmp_path)
    s.registry_path.write_text(json.dumps({
        "version": 1,
        "projects": [
            {"name": "Bare"},  # only a name
            {"name": "Extra", "mystery_field": 123, "status": "ok"},
            {"id": "noname"},  # no name -> skipped
        ],
    }), encoding="utf-8")
    names = sorted(p.name for p in s.load())
    assert names == ["Bare", "Extra"]


# --------------------------------------------------------------------------- #
# digest rendering
# --------------------------------------------------------------------------- #

def test_digest_is_one_line_per_project(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Meter", status="shipped",
                          repo="github.com/JackBhanded/claude-meter"))
    s.add(Project.create("Lifeboat", status="shipped"))
    digest = s.render_digest()
    body_lines = [l for l in digest.splitlines() if l.startswith("- **")]
    assert len(body_lines) == 2
    assert any("Meter" in l and "shipped" in l for l in body_lines)


def test_digest_deterministic_order(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Zebra"))
    s.add(Project.create("Apple"))
    d1 = s.render_digest()
    d2 = s.render_digest()
    assert d1 == d2  # same hash => safe-write idempotency works
    # Alphabetical regardless of insertion order.
    assert d1.index("Apple") < d1.index("Zebra")


def test_empty_digest_has_friendly_placeholder(tmp_path):
    s = fresh(tmp_path)
    digest = s.render_digest()
    assert "no projects added yet" in digest


def test_write_digest_creates_file(tmp_path):
    s = fresh(tmp_path)
    s.add(Project.create("Meter"))
    p = s.write_digest()
    assert p.exists()
    assert "Meter" in p.read_text(encoding="utf-8")


# --------------------------------------------------------------------------- #
# manifest / sync bookkeeping
# --------------------------------------------------------------------------- #

def test_record_sync_round_trips(tmp_path):
    s = fresh(tmp_path)
    s.record_sync("claude-code:user", path="/home/x/.claude/CLAUDE.md",
                  status="updated", digest_hash="abc123")
    m = s.load_manifest()
    entry = m["surfaces"]["claude-code:user"]
    assert entry["status"] == "updated"
    assert entry["digest_hash"] == "abc123"
    assert "last_sync" in entry


def test_manifest_missing_is_empty(tmp_path):
    s = fresh(tmp_path)
    m = s.load_manifest()
    assert m["surfaces"] == {}


# --------------------------------------------------------------------------- #
# default_home env override
# --------------------------------------------------------------------------- #

def test_default_home_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LIFEJACKET_HOME", str(tmp_path / "custom"))
    assert default_home() == Path(tmp_path / "custom")


def test_default_home_fallback(tmp_path, monkeypatch):
    monkeypatch.delenv("LIFEJACKET_HOME", raising=False)
    assert default_home().name == ".claude-lifejacket"
