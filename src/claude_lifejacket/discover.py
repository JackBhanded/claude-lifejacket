"""discover.py — find projects you haven't added to the logbook yet.

The logbook stays *curated* (you decide what every Claude session should know
about), but you shouldn't have to remember and re-type every project. This does
the finding; you do the choosing.

Two sources, both heuristics (so we propose, never add silently):

  * **Cowork projects** — subfolders of your Claude Projects folder
    (``~/Documents/Claude/Projects/`` by default). Each folder is a candidate.
  * **Claude Code projects** — directories under ``~/.claude/projects/``. Each
    one stores session transcripts that record the real working directory
    (``cwd``); we read that to get an accurate name + path rather than trying to
    un-mangle the encoded folder name.

Candidates already in the logbook (by slug) are filtered out, and duplicates
(same resolved path, or same name from both sources) are collapsed.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .store import Store, slugify
from .surfaces import claude_code_home

__all__ = [
    "Candidate",
    "default_projects_root",
    "discover_cowork_projects",
    "discover_claude_code_projects",
    "discover_candidates",
]


@dataclass
class Candidate:
    name: str
    path: str
    source: str  # "cowork" | "claude-code"


def default_projects_root() -> Path:
    """Where Cowork keeps project folders. Overridable with
    ``LIFEJACKET_PROJECTS_ROOT`` for unusual setups / tests."""
    override = os.environ.get("LIFEJACKET_PROJECTS_ROOT")
    if override:
        return Path(override).expanduser()
    return Path.home() / "Documents" / "Claude" / "Projects"


def discover_cowork_projects(projects_root) -> List[Candidate]:
    """Each direct subfolder of the projects root is a candidate project."""
    root = Path(projects_root)
    out: List[Candidate] = []
    if not root.exists():
        return out
    try:
        children = list(root.iterdir())
    except OSError:
        return out
    for child in children:
        if child.is_dir() and not child.name.startswith("."):
            out.append(Candidate(name=child.name, path=str(child), source="cowork"))
    return out


def discover_claude_code_projects(claude_home) -> List[Candidate]:
    """Each ``~/.claude/projects/<dir>`` is a project Claude Code has worked in.
    We read the real ``cwd`` from its transcripts for an accurate name/path."""
    base = Path(claude_home) / "projects"
    out: List[Candidate] = []
    if not base.exists():
        return out
    try:
        children = list(base.iterdir())
    except OSError:
        return out
    for child in children:
        if not child.is_dir():
            continue
        cwd = _read_cwd(child)
        if not cwd:
            continue  # can't determine a real path → skip rather than guess junk
        p = Path(cwd)
        out.append(Candidate(name=p.name, path=str(p), source="claude-code"))
    return out


def _read_cwd(project_dir: Path) -> Optional[str]:
    """Pull a ``cwd`` value out of the newest session transcript in a Claude
    Code project dir. Returns None if nothing usable is found."""
    try:
        jsonls = sorted(
            project_dir.glob("*.jsonl"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
    except OSError:
        return None
    for jf in jsonls:
        try:
            with jf.open(encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    cwd = obj.get("cwd") if isinstance(obj, dict) else None
                    if cwd:
                        return cwd
        except OSError:
            continue
    return None


def discover_candidates(
    *,
    store: Store,
    projects_root=None,
    claude_home=None,
) -> List[Candidate]:
    """Merge both sources, drop anything already in the logbook, collapse
    duplicates, and return a stable, name-sorted list."""
    projects_root = projects_root if projects_root is not None else default_projects_root()
    claude_home = claude_home if claude_home is not None else claude_code_home()

    found = (
        discover_cowork_projects(projects_root)
        + discover_claude_code_projects(claude_home)
    )

    existing_slugs = {p.id for p in store.load()}
    seen_paths = set()
    seen_slugs = set()
    out: List[Candidate] = []
    for c in found:
        try:
            rp = str(Path(c.path).expanduser().resolve())
        except OSError:
            rp = c.path
        slug = slugify(c.name)
        if slug in existing_slugs or rp in seen_paths or slug in seen_slugs:
            continue
        seen_paths.add(rp)
        seen_slugs.add(slug)
        out.append(c)

    return sorted(out, key=lambda c: c.name.lower())
