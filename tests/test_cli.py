"""Tests for the CLI surface — drives main() with env-isolated home dirs."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_lifejacket.cli import main


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Isolate the store and the Claude home into tmp dirs."""
    lj = tmp_path / "lj"
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    monkeypatch.setenv("LIFEJACKET_HOME", str(lj))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(ch))
    return {"lj": lj, "ch": ch}


def test_init(env, capsys):
    assert main(["init"]) == 0
    assert (env["lj"] / "projects.json").exists()
    assert "ready" in capsys.readouterr().out.lower()


def test_add_and_list(env, capsys):
    main(["init"])
    assert main(["add", "Claude Meter", "--status", "shipped"]) == 0
    capsys.readouterr()
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "Claude Meter" in out


def test_add_duplicate_returns_error(env, capsys):
    main(["init"])
    main(["add", "Meter"])
    rc = main(["add", "Meter"])
    assert rc == 1
    assert "already" in capsys.readouterr().out.lower()


def test_sync_creates_block(env, capsys):
    main(["init"])
    main(["add", "Meter", "--status", "shipped"])
    capsys.readouterr()
    assert main(["sync"]) == 0
    cc = env["ch"] / "CLAUDE.md"
    assert cc.exists()
    text = cc.read_text(encoding="utf-8")
    assert "LIFEJACKET:BEGIN" in text
    assert "Meter" in text  # the project name lives in the synced block
    assert "Synced" in capsys.readouterr().out  # CLI prints a surface summary


def test_sync_dry_run_writes_nothing(env, capsys):
    main(["init"])
    main(["add", "Meter"])
    capsys.readouterr()
    assert main(["sync", "--dry-run"]) == 0
    assert not (env["ch"] / "CLAUDE.md").exists()
    assert "would" in capsys.readouterr().out.lower()


def test_status_runs(env, capsys):
    main(["init"])
    main(["add", "Meter"])
    main(["sync"])
    capsys.readouterr()
    assert main(["status"]) == 0
    out = capsys.readouterr().out
    assert "status" in out.lower()
    assert "Surfaces" in out


def test_install_and_uninstall_hook(env, capsys):
    main(["init"])
    assert main(["install-hook"]) == 0
    sp = env["ch"] / "settings.json"
    assert sp.exists()
    assert "claude_lifejacket" in sp.read_text(encoding="utf-8")
    capsys.readouterr()
    assert main(["uninstall-hook"]) == 0
    assert "claude_lifejacket" not in sp.read_text(encoding="utf-8")


def test_hook_emits_valid_json(env, capsys):
    main(["init"])
    main(["add", "Meter", "--status", "shipped"])
    capsys.readouterr()
    assert main(["hook"]) == 0
    out = capsys.readouterr().out.strip()
    payload = json.loads(out)  # must be the ONLY thing on stdout
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"
    assert "Meter" in payload["hookSpecificOutput"]["additionalContext"]


def test_remove(env, capsys):
    main(["init"])
    main(["add", "Meter"])
    capsys.readouterr()
    assert main(["remove", "meter"]) == 0
    assert main(["remove", "meter"]) == 1  # already gone


def test_update(env, capsys):
    main(["init"])
    main(["add", "Meter", "--status", "building"])
    capsys.readouterr()
    assert main(["update", "meter", "--status", "shipped"]) == 0
    assert "Updated" in capsys.readouterr().out


def test_show_details_and_folder_contents(env, capsys, tmp_path):
    # A real folder with a couple of files to peek into.
    proj = tmp_path / "MyRepo"
    proj.mkdir()
    (proj / "README.md").write_text("hi", encoding="utf-8")
    (proj / "src").mkdir()
    main(["init"])
    main(["add", "MyRepo", "--status", "active", "--path", str(proj)])
    capsys.readouterr()
    assert main(["show", "myrepo"]) == 0
    out = capsys.readouterr().out
    assert "MyRepo" in out
    assert "active" in out
    assert "README.md" in out      # peeked into the folder
    assert "src/" in out           # directories get a trailing slash


def test_show_missing_project(env, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["show", "ghost"]) == 1
    assert "No project" in capsys.readouterr().out


def test_no_command_prints_help(env, capsys):
    assert main([]) == 0
    assert "lifejacket" in capsys.readouterr().out.lower()


def test_log_empty_then_after_sync(env, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["log"]) == 0
    assert "No activity yet" in capsys.readouterr().out
    main(["add", "Meter"])
    main(["sync"])
    capsys.readouterr()
    assert main(["log"]) == 0
    out = capsys.readouterr().out
    assert "Recent activity" in out
    assert "sync" in out


def test_doctor(env, capsys):
    main(["init"])
    capsys.readouterr()
    assert main(["doctor"]) == 0
    assert "check-up" in capsys.readouterr().out.lower()
