"""Tests for hookconfig.py — safely editing ~/.claude/settings.json."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from claude_lifejacket.hookconfig import (
    HOOK_TAG,
    hook_command,
    install_session_start_hook,
    settings_path,
    uninstall_session_start_hook,
)

CMD = '"python" -m claude_lifejacket hook'


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_install_into_empty_home(tmp_path):
    res = install_session_start_hook(tmp_path, command=CMD)
    assert res.status == "installed"
    data = read(settings_path(tmp_path))
    groups = data["hooks"]["SessionStart"]
    assert any(HOOK_TAG in h["command"]
               for g in groups for h in g["hooks"])


def test_install_is_idempotent(tmp_path):
    install_session_start_hook(tmp_path, command=CMD)
    res2 = install_session_start_hook(tmp_path, command=CMD)
    assert res2.status == "unchanged"
    # Still exactly one Lifejacket hook.
    data = read(settings_path(tmp_path))
    count = sum(1 for g in data["hooks"]["SessionStart"]
                for h in g["hooks"] if HOOK_TAG in h["command"])
    assert count == 1


def test_install_preserves_existing_hooks(tmp_path):
    sp = settings_path(tmp_path)
    sp.write_text(json.dumps({
        "model": "opus",
        "hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "echo hi"}]}
        ]},
    }), encoding="utf-8")
    install_session_start_hook(tmp_path, command=CMD)
    data = read(sp)
    assert data["model"] == "opus"  # unrelated keys preserved
    cmds = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
    assert "echo hi" in cmds          # their hook preserved
    assert any(HOOK_TAG in c for c in cmds)  # ours added


def test_install_updates_changed_command(tmp_path):
    install_session_start_hook(tmp_path, command='"oldpy" -m claude_lifejacket hook')
    res = install_session_start_hook(tmp_path, command='"newpy" -m claude_lifejacket hook')
    assert res.status == "updated"
    data = read(settings_path(tmp_path))
    cmds = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
    assert any("newpy" in c for c in cmds)
    assert not any("oldpy" in c for c in cmds)


def test_install_refuses_invalid_json(tmp_path):
    sp = settings_path(tmp_path)
    sp.write_text("{ this is not json", encoding="utf-8")
    res = install_session_start_hook(tmp_path, command=CMD)
    assert res.status == "refused"
    assert res.ok is False
    # The bad file is left exactly as it was.
    assert sp.read_text(encoding="utf-8") == "{ this is not json"


def test_uninstall_removes_only_ours(tmp_path):
    sp = settings_path(tmp_path)
    sp.write_text(json.dumps({
        "hooks": {"SessionStart": [
            {"hooks": [{"type": "command", "command": "echo hi"}]}
        ]},
    }), encoding="utf-8")
    install_session_start_hook(tmp_path, command=CMD)
    res = uninstall_session_start_hook(tmp_path)
    assert res.status == "removed"
    data = read(sp)
    cmds = [h["command"] for g in data["hooks"]["SessionStart"] for h in g["hooks"]]
    assert "echo hi" in cmds                 # theirs survives
    assert not any(HOOK_TAG in c for c in cmds)  # ours gone


def test_uninstall_tidies_empty_containers(tmp_path):
    install_session_start_hook(tmp_path, command=CMD)
    uninstall_session_start_hook(tmp_path)
    data = read(settings_path(tmp_path))
    # With nothing else, the SessionStart (and hooks) containers are cleaned up.
    assert "SessionStart" not in data.get("hooks", {})


def test_uninstall_absent_is_graceful(tmp_path):
    res = uninstall_session_start_hook(tmp_path)
    assert res.status == "absent"
    assert res.ok is True


def test_hook_command_quotes_python():
    cmd = hook_command(python="/path with space/python")
    assert cmd.startswith('"/path with space/python"')
    assert "claude_lifejacket hook" in cmd
