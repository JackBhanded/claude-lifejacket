"""hookconfig.py — install/remove the Claude Code SessionStart hook, safely.

The hook is what makes Lifejacket *automatic*: every time a Claude Code session
starts, it runs ``lifejacket hook``, which (a) re-syncs the digest into your
memory files and (b) prints the digest as the session's ``additionalContext`` so
the very session that's starting already knows about all your projects.

Editing ``~/.claude/settings.json`` is delicate — it's strict JSON the user may
have customised. We treat it with the same paranoia as CLAUDE.md:

  * If the file won't parse as JSON, we DO NOT write. We refuse and tell the
    user how to add the hook by hand, rather than risk clobbering their config.
  * We back it up (timestamped) before any change and write atomically.
  * We detect our own hook by a tag in the command string, so installing twice
    is a no-op and uninstalling removes only our entry.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .safewrite import write_text_atomic

__all__ = [
    "HookResult",
    "hook_command",
    "settings_path",
    "install_session_start_hook",
    "uninstall_session_start_hook",
    "HOOK_TAG",
]

# Substring that uniquely identifies *our* hook command in settings.json.
HOOK_TAG = "claude_lifejacket"


@dataclass
class HookResult:
    status: str          # "installed" | "updated" | "unchanged" | "removed"
                         # | "absent" | "refused"
    path: Path
    backup_path: Optional[Path] = None
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status != "refused"


def hook_command(python: Optional[str] = None) -> str:
    """The command Claude Code should run on SessionStart.

    We invoke the package as a module with the *absolute* Python that installed
    Lifejacket, so it works even when the ``lifejacket`` launcher script isn't on
    PATH (a very common situation on Windows pip-user installs)."""
    py = python or sys.executable
    # Quote the interpreter path in case it contains spaces (Windows).
    return f'"{py}" -m claude_lifejacket hook'


def settings_path(claude_home: Path) -> Path:
    return Path(claude_home) / "settings.json"


def _load_settings(path: Path):
    """Return (data, error). On a parse error, data is None and error is a
    friendly string — the caller must then refuse to write."""
    if not path.exists():
        return {}, None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, f"couldn't read {path} ({exc})"
    if not text.strip():
        return {}, None
    try:
        return json.loads(text), None
    except json.JSONDecodeError as exc:
        return None, (
            f"{path} isn't valid JSON ({exc}). I didn't touch it. You can add "
            "the hook by hand, or fix the JSON and re-run."
        )


def _dump(data) -> str:
    return json.dumps(data, indent=2, ensure_ascii=False) + "\n"


def install_session_start_hook(
    claude_home: Path, command: Optional[str] = None
) -> HookResult:
    """Add (or update) the SessionStart hook in settings.json. Idempotent."""
    path = settings_path(claude_home)
    command = command or hook_command()
    data, err = _load_settings(path)
    if err:
        return HookResult(status="refused", path=path, message=err)

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        return HookResult(
            status="refused", path=path,
            message="The 'hooks' section of your settings.json isn't an object, "
                    "so I left it alone. Please add the SessionStart hook by hand.",
        )
    session_start = hooks.setdefault("SessionStart", [])
    if not isinstance(session_start, list):
        return HookResult(
            status="refused", path=path,
            message="Your settings.json has a 'SessionStart' that isn't a list, "
                    "so I left it alone to be safe.",
        )

    # Look for an existing Lifejacket hook anywhere under SessionStart.
    for group in session_start:
        if not isinstance(group, dict):
            continue
        for h in group.get("hooks", []):
            if isinstance(h, dict) and HOOK_TAG in str(h.get("command", "")):
                if h.get("command") == command:
                    return HookResult(
                        status="unchanged", path=path,
                        message="The SessionStart hook is already in place — "
                                "you're all set.",
                    )
                # Same hook, but the path/command changed (e.g. new Python).
                h["command"] = command
                bak = write_text_atomic(path, _dump(data), backup=True)
                return HookResult(
                    status="updated", path=path, backup_path=bak,
                    message="Refreshed the SessionStart hook command (and kept a "
                            "backup of your old settings).",
                )

    # Not present — append a new matcher group with just our command.
    session_start.append({"hooks": [{"type": "command", "command": command}]})
    bak = write_text_atomic(path, _dump(data), backup=path.exists())
    return HookResult(
        status="installed", path=path, backup_path=bak,
        message="Installed the SessionStart hook — Lifejacket will now keep "
                "every session current automatically. ",
    )


def uninstall_session_start_hook(claude_home: Path) -> HookResult:
    """Remove only Lifejacket's SessionStart hook, leaving everything else."""
    path = settings_path(claude_home)
    data, err = _load_settings(path)
    if err:
        return HookResult(status="refused", path=path, message=err)
    if not data:
        return HookResult(status="absent", path=path,
                          message="No settings.json yet — nothing to remove.")

    hooks = data.get("hooks")
    session_start = hooks.get("SessionStart") if isinstance(hooks, dict) else None
    if not isinstance(session_start, list):
        return HookResult(status="absent", path=path,
                          message="No SessionStart hooks here — nothing to remove.")

    removed = False
    new_groups = []
    for group in session_start:
        if not isinstance(group, dict):
            new_groups.append(group)
            continue
        kept = [h for h in group.get("hooks", [])
                if not (isinstance(h, dict) and HOOK_TAG in str(h.get("command", "")))]
        if len(kept) != len(group.get("hooks", [])):
            removed = True
        if kept:
            group = dict(group)
            group["hooks"] = kept
            new_groups.append(group)
        # else: drop the now-empty group entirely
    if not removed:
        return HookResult(status="absent", path=path,
                          message="No Lifejacket hook found — nothing to remove.")

    # Tidy: drop empty SessionStart / hooks containers so we leave it clean.
    if new_groups:
        hooks["SessionStart"] = new_groups
    else:
        hooks.pop("SessionStart", None)
    if isinstance(hooks, dict) and not hooks:
        data.pop("hooks", None)

    bak = write_text_atomic(path, _dump(data), backup=True)
    return HookResult(status="removed", path=path, backup_path=bak,
                      message="Removed the Lifejacket SessionStart hook. Your "
                              "other settings are untouched.")
