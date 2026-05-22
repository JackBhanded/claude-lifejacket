"""cli.py — the friendly ``lifejacket`` command line.

Commands:
    lifejacket init                 set up the local logbook
    lifejacket add  "Name" [...]    add a project to the logbook
    lifejacket list                 show your projects
    lifejacket remove <id>          remove a project
    lifejacket update <id> [...]    change a project's status/focus/etc
    lifejacket sync  [--dry-run]    push the digest into your Claude memory
    lifejacket status               show where things stand on every surface
    lifejacket install-hook         make sync automatic (SessionStart hook)
    lifejacket uninstall-hook       remove the automatic hook
    lifejacket hook                 (internal) run by Claude Code on session start
    lifejacket tray                 run quietly in your system tray
    lifejacket doctor               quick health check

Every line of output is meant to bring a small smile — even the unhappy ones.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import List, Optional

from . import __version__
from .dashboard import write_dashboard
from .discover import discover_candidates
from .hookconfig import (
    hook_command,
    install_session_start_hook,
    settings_path,
    uninstall_session_start_hook,
)
from .store import Project, Store, StoreError, default_home, slugify
from .surfaces import claude_code_home, discover_surfaces, load_extra_surfaces
from .sync import preview_all, sync_all

LIFE_RING = "[~]"  # ASCII-safe little buoy for headers


def _out(msg: str = "") -> None:
    print(msg)


def _store() -> Store:
    return Store(default_home())


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #

def cmd_init(args) -> int:
    s = _store()
    s.init()
    _out(f"{LIFE_RING} Your logbook is ready at {s.home}")
    _out("    Add your first project with:  lifejacket add \"My Project\"")
    return 0


def cmd_add(args) -> int:
    s = _store()
    s.init()
    try:
        p = s.add(
            Project.create(
                args.name, status=args.status, focus=args.focus,
                repo=args.repo, path=args.path,
            ),
            overwrite=args.overwrite,
        )
    except StoreError as exc:
        _out(f"{LIFE_RING} {exc}")
        return 1
    _out(f"{LIFE_RING} Added '{p.name}' to your logbook (id: {p.id}).")
    _out("    Run  lifejacket sync  to share it with all your Claude sessions.")
    return 0


def cmd_list(args) -> int:
    s = _store()
    projects = s.load()
    if not projects:
        _out(f"{LIFE_RING} Your logbook is empty — add one with: "
             "lifejacket add \"My Project\"")
        return 0
    _out(f"{LIFE_RING} {len(projects)} project(s) in your logbook:")
    _out("")
    for p in sorted(projects, key=lambda x: x.name.lower()):
        line = f"  - {p.name}  ({p.id})"
        meta = [b for b in (
            f"status: {p.status}" if p.status else "",
            f"focus: {p.focus}" if p.focus else "",
        ) if b]
        if meta:
            line += "\n      " + " | ".join(meta)
        _out(line)
    return 0


def cmd_show(args) -> int:
    s = _store()
    p = s.get(args.id) or s.get(slugify(args.id))
    if not p:
        _out(f"{LIFE_RING} No project '{args.id}' in your logbook. "
             "Run  python -m claude_lifejacket list  to see what's there.")
        return 1
    _out(f"{LIFE_RING} {p.name}")
    _out(f"    id:       {p.id}")
    _out(f"    status:   {p.status or '—'}")
    _out(f"    focus:    {p.focus or '—'}")
    _out(f"    repo:     {p.repo or '—'}")
    _out(f"    path:     {p.path or '—'}")
    _out(f"    updated:  {p.updated}")
    # Peek inside the folder so you can actually see what's in the project.
    if p.path and Path(p.path).exists():
        try:
            entries = sorted(os.listdir(p.path))
        except OSError:
            entries = []
        if entries:
            shown = entries[:25]
            _out("")
            _out(f"    What's inside ({len(entries)} item(s)):")
            for e in shown:
                tag = "/" if Path(p.path, e).is_dir() else ""
                _out(f"      - {e}{tag}")
            if len(entries) > len(shown):
                _out(f"      … and {len(entries) - len(shown)} more")
    elif p.path:
        _out("")
        _out("    (That folder isn't on this machine right now.)")
    return 0


def cmd_remove(args) -> int:
    s = _store()
    if s.remove(args.id):
        _out(f"{LIFE_RING} Removed '{args.id}'. Run  lifejacket sync  to update "
             "your sessions.")
        return 0
    _out(f"{LIFE_RING} No project with id '{args.id}' — nothing to remove.")
    return 1


def cmd_update(args) -> int:
    s = _store()
    changes = {k: v for k, v in (
        ("status", args.status), ("focus", args.focus),
        ("repo", args.repo), ("path", args.path),
    ) if v is not None}
    if not changes:
        _out(f"{LIFE_RING} Nothing to change — pass --status / --focus / --repo "
             "/ --path.")
        return 1
    try:
        p = s.update(args.id, **changes)
    except StoreError as exc:
        _out(f"{LIFE_RING} {exc}")
        return 1
    _out(f"{LIFE_RING} Updated '{p.name}'. Run  lifejacket sync  to share it.")
    return 0


def cmd_sync(args) -> int:
    s = _store()
    s.init()
    if args.dry_run:
        reports = preview_all(s)
        _out(f"{LIFE_RING} Dry run — here's what I *would* do (nothing written):")
    else:
        reports = sync_all(s, force=args.force)
        _out(f"{LIFE_RING} Synced your logbook into every Claude memory surface:")
    if not reports:
        _out("    (No Claude memory surfaces found yet. Is Claude Code "
             "installed? Looked in: " + str(claude_code_home()) + ")")
        return 0
    _out("")
    any_blocked = False
    for r in reports:
        _out("    " + r.headline)
        if r.result.status.value in ("tampered", "conflict"):
            any_blocked = True
    if any_blocked:
        _out("")
        _out("    A surface needs your eyes (a block was hand-edited or is "
             "ambiguous). Re-run with --force to let me overwrite, once you're "
             "happy. I changed nothing there.")
        return 2
    return 0


def cmd_status(args) -> int:
    s = _store()
    _out(f"{LIFE_RING} Claude Lifejacket status")
    _out("")
    projects = s.load()
    _out(f"  Logbook:   {len(projects)} project(s)  ({s.home})")
    surfaces = discover_surfaces(extra_paths=load_extra_surfaces(s.home))
    _out(f"  Surfaces:  {len(surfaces)} found")
    manifest = s.load_manifest().get("surfaces", {})
    for surf in surfaces:
        entry = manifest.get(surf.key)
        if entry:
            _out(f"    - {surf.label}")
            _out(f"        last sync: {entry.get('last_sync','?')} "
                 f"({entry.get('status','?')})")
        else:
            _out(f"    - {surf.label}")
            _out("        never synced yet — run  lifejacket sync")
    # Hook state
    sp = settings_path(claude_code_home())
    hooked = sp.exists() and "claude_lifejacket" in sp.read_text(
        encoding="utf-8", errors="ignore")
    _out("")
    _out(f"  Auto-sync hook: {'ON' if hooked else 'off'}"
         + ("" if hooked else "  (turn on with: lifejacket install-hook)"))
    return 0


def cmd_install_hook(args) -> int:
    res = install_session_start_hook(claude_code_home())
    _out(f"{LIFE_RING} {res.message}")
    if res.backup_path:
        _out(f"    (backup: {res.backup_path})")
    return 0 if res.ok else 1


def cmd_uninstall_hook(args) -> int:
    res = uninstall_session_start_hook(claude_code_home())
    _out(f"{LIFE_RING} {res.message}")
    return 0 if res.ok else 1


def cmd_hook(args) -> int:
    """Run by Claude Code on SessionStart. Must print ONLY the JSON the hook
    protocol expects on stdout — so we keep the sync silent and emit the digest
    as additionalContext for the session that's starting right now."""
    s = _store()
    try:
        s.init()
        sync_all(s)  # refresh the file for next time; ignore per-surface detail
        digest = s.render_digest()
    except Exception:
        # A hook must never break the user's session. On any trouble, emit an
        # empty (valid) response and bail quietly.
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "SessionStart", "additionalContext": ""}}))
        return 0
    payload = {
        "hookSpecificOutput": {
            "hookEventName": "SessionStart",
            "additionalContext": digest,
        }
    }
    print(json.dumps(payload))
    return 0


def cmd_discover(args) -> int:
    s = _store()
    s.init()
    cands = discover_candidates(store=s, projects_root=args.projects_root)
    if not cands:
        _out(f"{LIFE_RING} Nothing new to discover — your logbook already has "
             "everything I can see. ")
        return 0

    def _add(chosen):
        added = 0
        for c in chosen:
            try:
                s.add(Project.create(c.name, path=c.path))
                added += 1
            except StoreError:
                pass  # already there / slug clash — skip quietly
        return added

    if args.all:
        n = _add(cands)
        _out(f"{LIFE_RING} Added {n} project(s) to your logbook.")
        _out("    Run  python -m claude_lifejacket sync  to share them with "
             "every Claude session.")
        return 0

    if args.add:
        picks = []
        for tok in args.add.replace(" ", "").split(","):
            if not tok:
                continue
            if not tok.isdigit() or not (1 <= int(tok) <= len(cands)):
                _out(f"{LIFE_RING} '{tok}' isn't one of the numbers below "
                     f"(1–{len(cands)}). Nothing added.")
                return 1
            picks.append(cands[int(tok) - 1])
        n = _add(picks)
        _out(f"{LIFE_RING} Added {n} project(s) to your logbook.")
        _out("    Run  python -m claude_lifejacket sync  to share them.")
        return 0

    # Default: just show what was found and how to add it.
    _out(f"{LIFE_RING} Found {len(cands)} project(s) not yet in your logbook:")
    _out("")
    for i, c in enumerate(cands, 1):
        _out(f"  [{i}] {c.name}   ({c.source})")
        _out(f"      {c.path}")
    _out("")
    _out("  Add some:  python -m claude_lifejacket discover --add 1,2,3")
    _out("  Add all:   python -m claude_lifejacket discover --all")
    return 0


def cmd_dashboard(args) -> int:
    s = _store()
    s.init()
    out = write_dashboard(s)
    _out(f"{LIFE_RING} Your dashboard is ready: {out}")
    if not args.no_open:
        try:
            import webbrowser
            webbrowser.open(out.as_uri())
            _out("    Opening it in your browser now. ")
        except Exception:
            _out("    Open that file in any browser to see it.")
    return 0


def cmd_log(args) -> int:
    s = _store()
    events = s.read_recent_events(args.lines)
    if not events:
        _out(f"{LIFE_RING} No activity yet — run a sync and it'll show up here.")
        return 0
    _out(f"{LIFE_RING} Recent activity ({len(events)} line(s)):")
    _out("")
    for line in events:
        _out("  " + line)
    _out("")
    _out(f"    Full log: {s.activity_log_path}")
    return 0


def cmd_tray(args) -> int:
    try:
        from .app import main as app_main
    except Exception:
        _out(f"{LIFE_RING} The tray needs the desktop app. Install PySide6: "
             "pip install --user PySide6")
        return 1
    return app_main(start_in_tray=True)


def cmd_doctor(args) -> int:
    s = _store()
    _out(f"{LIFE_RING} Lifejacket check-up")
    _out("")
    _out(f"  Python:      {sys.version.split()[0]}")
    _out(f"  Store:       {'ok' if s.exists() else 'not initialised (run init)'} "
         f"({s.home})")
    ch = claude_code_home()
    _out(f"  Claude home: {'found' if ch.exists() else 'not found'}  ({ch})")
    surfaces = discover_surfaces(extra_paths=load_extra_surfaces(s.home))
    _out(f"  Surfaces:    {len(surfaces)} reachable")
    _out(f"  Hook cmd:    {hook_command()}")
    _out("")
    _out("  If all of the above looks right, you're seaworthy. ")
    return 0


# --------------------------------------------------------------------------- #
# parser
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lifejacket",
        description="Keep every Claude session aware of your projects — safely.",
    )
    p.add_argument("--version", action="version",
                   version=f"claude-lifejacket {__version__}")
    sub = p.add_subparsers(dest="command")

    sub.add_parser("init", help="set up the local logbook").set_defaults(
        func=cmd_init)

    a = sub.add_parser("add", help="add a project to the logbook")
    a.add_argument("name")
    a.add_argument("--status")
    a.add_argument("--focus")
    a.add_argument("--repo")
    a.add_argument("--path")
    a.add_argument("--overwrite", action="store_true",
                   help="replace an existing project with the same id")
    a.set_defaults(func=cmd_add)

    sub.add_parser("list", help="show your projects").set_defaults(func=cmd_list)

    sh = sub.add_parser("show", help="show one project's details + folder contents")
    sh.add_argument("id")
    sh.set_defaults(func=cmd_show)

    dsc = sub.add_parser("discover",
                         help="find projects not yet in your logbook")
    dsc.add_argument("--all", action="store_true", help="add everything found")
    dsc.add_argument("--add", help="add by number, e.g. --add 1,3,4")
    dsc.add_argument("--projects-root",
                     help="folder to scan for Cowork projects "
                          "(default ~/Documents/Claude/Projects)")
    dsc.set_defaults(func=cmd_discover)

    r = sub.add_parser("remove", help="remove a project by id")
    r.add_argument("id")
    r.set_defaults(func=cmd_remove)

    u = sub.add_parser("update", help="change a project's fields")
    u.add_argument("id")
    u.add_argument("--status")
    u.add_argument("--focus")
    u.add_argument("--repo")
    u.add_argument("--path")
    u.set_defaults(func=cmd_update)

    sy = sub.add_parser("sync", help="push the digest into your Claude memory")
    sy.add_argument("--dry-run", action="store_true",
                    help="preview without writing anything")
    sy.add_argument("--force", action="store_true",
                    help="overwrite a block you've hand-edited (use with care)")
    sy.set_defaults(func=cmd_sync)

    sub.add_parser("status", help="show where things stand").set_defaults(
        func=cmd_status)

    lg = sub.add_parser("log", help="show recent sync activity")
    lg.add_argument("--lines", type=int, default=20, help="how many lines")
    lg.set_defaults(func=cmd_log)

    d = sub.add_parser("dashboard", help="open the visual status dashboard")
    d.add_argument("--no-open", action="store_true",
                   help="write the HTML file but don't open a browser")
    d.set_defaults(func=cmd_dashboard)
    sub.add_parser("install-hook", help="make sync automatic").set_defaults(
        func=cmd_install_hook)
    sub.add_parser("uninstall-hook", help="remove the automatic hook").set_defaults(
        func=cmd_uninstall_hook)
    sub.add_parser("hook", help=argparse.SUPPRESS).set_defaults(func=cmd_hook)
    sub.add_parser("tray", help="run quietly in your system tray").set_defaults(
        func=cmd_tray)
    sub.add_parser("doctor", help="quick health check").set_defaults(
        func=cmd_doctor)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
