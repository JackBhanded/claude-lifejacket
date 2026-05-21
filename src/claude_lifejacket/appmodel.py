"""appmodel.py — the brains behind the double-click app, with NO GUI imports.

The PySide6 window in ``app.py`` is deliberately dumb: it asks this module for a
:class:`Snapshot` to render, and calls these functions when buttons are clicked.
Keeping the logic here (and Qt-free) means the whole app behaviour is unit-
testable without a display — the window is just paint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from .discover import Candidate, discover_candidates
from .hookconfig import (
    HOOK_TAG,
    install_session_start_hook,
    settings_path,
    uninstall_session_start_hook,
)
from .store import Project, Store
from .surfaces import claude_code_home, discover_surfaces, load_extra_surfaces
from .sync import digest_fingerprint, sync_all

__all__ = [
    "SurfaceView",
    "Snapshot",
    "build_snapshot",
    "hook_is_on",
    "add_candidates",
    "set_autosync",
    "do_sync",
]


@dataclass
class SurfaceView:
    label: str
    state: str   # "in_sync" | "out_of_date" | "never" | "attention"
    detail: str


@dataclass
class Snapshot:
    projects: List[Project]
    candidates: List[Candidate]
    surfaces: List[SurfaceView]
    hook_on: bool
    recent: List[str]


def hook_is_on(claude_home=None) -> bool:
    sp = settings_path(claude_home or claude_code_home())
    if not sp.exists():
        return False
    try:
        return HOOK_TAG in sp.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False


def build_snapshot(store: Store, *, claude_home=None, projects_root=None) -> Snapshot:
    """Everything the window needs to draw itself, in one read."""
    projects = sorted(store.load(), key=lambda p: p.name.lower())
    candidates = discover_candidates(
        store=store, projects_root=projects_root, claude_home=claude_home)

    digest = store.render_digest(projects)
    fp = digest_fingerprint(digest)
    manifest = store.load_manifest().get("surfaces", {})
    surfs = discover_surfaces(
        claude_home=claude_home, extra_paths=load_extra_surfaces(store.home))

    views: List[SurfaceView] = []
    for s in surfs:
        entry = manifest.get(s.key)
        if not entry:
            state, detail = "never", "Never synced"
        elif entry.get("status") in ("tampered", "conflict"):
            state, detail = "attention", "Needs your eyes"
        elif entry.get("digest_hash") == fp:
            state, detail = "in_sync", "In sync"
        else:
            state, detail = "out_of_date", "Out of date"
        views.append(SurfaceView(label=s.label, state=state, detail=detail))

    return Snapshot(
        projects=projects,
        candidates=candidates,
        surfaces=views,
        hook_on=hook_is_on(claude_home),
        recent=store.read_recent_events(8),
    )


def add_candidates(store: Store, candidates: List[Candidate]) -> int:
    """Add chosen discovered projects to the logbook. Returns how many landed."""
    added = 0
    for c in candidates:
        try:
            store.add(Project.create(c.name, path=c.path))
            added += 1
        except Exception:
            pass  # already present / clash — skip quietly
    return added


def set_autosync(on: bool, claude_home=None):
    """Turn the SessionStart auto-sync hook on or off. Returns a HookResult."""
    ch = claude_home or claude_code_home()
    return (install_session_start_hook(ch) if on
            else uninstall_session_start_hook(ch))


def do_sync(store: Store, *, claude_home=None, force: bool = False):
    """Run a sync and return the per-surface reports."""
    return sync_all(store, claude_home=claude_home, force=force)
