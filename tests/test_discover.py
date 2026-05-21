"""Tests for discover.py + the `discover` CLI command."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_lifejacket.cli import main
from claude_lifejacket.discover import (
    Candidate,
    discover_candidates,
    discover_claude_code_projects,
    discover_cowork_projects,
)
from claude_lifejacket.store import Project, Store


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def make_projects_root(tmp_path, names):
    root = tmp_path / "Projects"
    root.mkdir()
    for n in names:
        (root / n).mkdir()
    return root


def make_cc_home_with_project(tmp_path, cwd_path):
    """A fake ~/.claude with one projects/<dir> holding a transcript that
    records `cwd`."""
    ch = tmp_path / "dot-claude"
    proj = ch / "projects" / "encoded-name"
    proj.mkdir(parents=True)
    (proj / "session.jsonl").write_text(
        json.dumps({"type": "user", "cwd": str(cwd_path)}) + "\n",
        encoding="utf-8",
    )
    return ch


# --------------------------------------------------------------------------- #
# cowork scan
# --------------------------------------------------------------------------- #

def test_cowork_scan_lists_subfolders(tmp_path):
    root = make_projects_root(tmp_path, ["Claude Lifeboat", "SYAS Change Log for Claude"])
    (root / ".hidden").mkdir()
    (root / "a_file.txt").write_text("x", encoding="utf-8")
    cands = discover_cowork_projects(root)
    names = sorted(c.name for c in cands)
    assert names == ["Claude Lifeboat", "SYAS Change Log for Claude"]
    assert all(c.source == "cowork" for c in cands)


def test_cowork_scan_missing_root(tmp_path):
    assert discover_cowork_projects(tmp_path / "nope") == []


# --------------------------------------------------------------------------- #
# claude code scan
# --------------------------------------------------------------------------- #

def test_claude_code_scan_reads_cwd(tmp_path):
    real = tmp_path / "work" / "MyRepo"
    real.mkdir(parents=True)
    ch = make_cc_home_with_project(tmp_path, real)
    cands = discover_claude_code_projects(ch)
    assert len(cands) == 1
    assert cands[0].name == "MyRepo"
    assert cands[0].source == "claude-code"
    assert Path(cands[0].path) == real


def test_claude_code_scan_skips_when_no_cwd(tmp_path):
    ch = tmp_path / "dot-claude"
    proj = ch / "projects" / "weird"
    proj.mkdir(parents=True)
    (proj / "s.jsonl").write_text("{}\n{not json\n", encoding="utf-8")
    assert discover_claude_code_projects(ch) == []


def test_claude_code_scan_missing(tmp_path):
    assert discover_claude_code_projects(tmp_path / "none") == []


# --------------------------------------------------------------------------- #
# merge / dedupe / exclude
# --------------------------------------------------------------------------- #

def test_candidates_exclude_existing_logbook_entries(tmp_path):
    s = Store(home=tmp_path / "lj")
    s.init()
    s.add(Project.create("Claude Lifeboat"))  # already known
    root = make_projects_root(tmp_path, ["Claude Lifeboat", "New Thing"])
    cands = discover_candidates(store=s, projects_root=root, claude_home=tmp_path / "no-cc")
    names = [c.name for c in cands]
    assert "Claude Lifeboat" not in names  # excluded — already in logbook
    assert "New Thing" in names


def test_candidates_dedupe_same_path(tmp_path):
    s = Store(home=tmp_path / "lj")
    s.init()
    # Same folder appears as both a Cowork project AND a Claude Code cwd.
    shared = tmp_path / "Projects" / "Shared"
    root = make_projects_root(tmp_path, ["Shared"])
    ch = make_cc_home_with_project(tmp_path, shared)
    cands = discover_candidates(store=s, projects_root=root, claude_home=ch)
    assert len([c for c in cands if c.name == "Shared"]) == 1  # collapsed


def test_candidates_sorted(tmp_path):
    s = Store(home=tmp_path / "lj")
    s.init()
    root = make_projects_root(tmp_path, ["Zeta", "alpha", "Mid"])
    cands = discover_candidates(store=s, projects_root=root, claude_home=tmp_path / "x")
    assert [c.name for c in cands] == ["alpha", "Mid", "Zeta"]


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

@pytest.fixture
def env(tmp_path, monkeypatch):
    lj = tmp_path / "lj"
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    proot = make_projects_root(tmp_path, ["Claude Lifeboat", "SYAS Change Log for Claude"])
    monkeypatch.setenv("LIFEJACKET_HOME", str(lj))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(ch))
    monkeypatch.setenv("LIFEJACKET_PROJECTS_ROOT", str(proot))
    return {"lj": lj, "ch": ch, "proot": proot}


def test_cli_discover_lists(env, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["discover"]) == 0
    out = capsys.readouterr().out
    assert "Claude Lifeboat" in out
    assert "SYAS Change Log for Claude" in out
    assert "[1]" in out and "[2]" in out
    # Listing alone adds nothing.
    assert Store(home=env["lj"]).load() == []


def test_cli_discover_add_all(env, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["discover", "--all"]) == 0
    names = sorted(p.name for p in Store(home=env["lj"]).load())
    assert names == ["Claude Lifeboat", "SYAS Change Log for Claude"]


def test_cli_discover_add_by_number(env, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["discover", "--add", "1"]) == 0
    names = [p.name for p in Store(home=env["lj"]).load()]
    assert len(names) == 1  # only the first (alphabetical) was added


def test_cli_discover_bad_number(env, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["discover", "--add", "99"]) == 1
    assert Store(home=env["lj"]).load() == []  # nothing added on bad input


def test_cli_discover_nothing_new(env, capsys):
    main(["init"])
    main(["discover", "--all"])      # add everything
    capsys.readouterr()
    assert main(["discover"]) == 0   # now nothing new
    assert "Nothing new" in capsys.readouterr().out
