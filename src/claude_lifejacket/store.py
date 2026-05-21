"""store.py — Claude Lifejacket's central logbook.

This is the single source of truth for *what projects exist*. It lives entirely
in Lifejacket's own home directory (``~/.claude-lifejacket/`` by default) and
never touches anything the user hand-edits — so unlike the managed-block engine,
it's allowed to own its files outright. It still writes them atomically (via
:func:`claude_lifejacket.safewrite.write_text_atomic`) so a crash can never
leave a half-written registry.

Layout of the store::

    ~/.claude-lifejacket/
        projects.json     # the registry — the only thing the user truly edits
        digest.md         # generated: the curated text we inject into memory
        manifest.json     # per-surface sync bookkeeping (hashes, timestamps)
        backups/          # timestamped backups of files we change

The *digest* is deliberately tiny: one line per project. The whole point of the
research was that injecting a giant knowledge base bloats every session's
context and goes stale; a curated one-liner-per-project digest is what stays
useful. Deep per-project notes are a v0.2 idea, not this.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from .safewrite import write_text_atomic

__all__ = [
    "Project",
    "Store",
    "StoreError",
    "slugify",
    "default_home",
    "REGISTRY_VERSION",
]

REGISTRY_VERSION = 1

# The block id + version the digest is injected under. Bumping DIGEST_VERSION
# lets the safe-write engine recognise and upgrade an older injected block.
DIGEST_BLOCK_ID = "projects"
DIGEST_VERSION = 1


class StoreError(Exception):
    """Something went wrong reading or writing the store. Messages are written
    to be shown straight to a human — kind and specific."""


# --------------------------------------------------------------------------- #
# Locating the store
# --------------------------------------------------------------------------- #

def default_home() -> Path:
    """Where the store lives. Overridable with the ``LIFEJACKET_HOME`` env var
    (handy for tests and for power users who keep dotfiles elsewhere)."""
    override = os.environ.get("LIFEJACKET_HOME")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude-lifejacket"


# --------------------------------------------------------------------------- #
# Slugs
# --------------------------------------------------------------------------- #

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Turn a project name into a stable, marker-safe id ('Claude Meter' ->
    'claude-meter'). Used as the project's key in the registry."""
    s = _SLUG_STRIP.sub("-", name.strip().lower()).strip("-")
    return s or "project"


# --------------------------------------------------------------------------- #
# Project record
# --------------------------------------------------------------------------- #

@dataclass
class Project:
    """One project in the logbook. Only ``name`` is required; everything else is
    optional context that makes the injected digest more useful."""

    id: str
    name: str
    path: Optional[str] = None      # local folder, if any
    repo: Optional[str] = None      # repo URL, if any
    status: Optional[str] = None    # e.g. "shipped", "building", "scoped"
    focus: Optional[str] = None     # one-line "what's top of mind right now"
    updated: str = field(default_factory=lambda: _today())

    @staticmethod
    def create(name: str, **kwargs) -> "Project":
        pid = kwargs.pop("id", None) or slugify(name)
        return Project(id=pid, name=name.strip(), **kwargs)

    def digest_line(self) -> str:
        """Render this project as a single curated digest line. Kept compact on
        purpose — this text is injected into every Claude session, so every word
        costs context budget."""
        bits: List[str] = []
        if self.status:
            bits.append(f"status: {self.status}")
        if self.focus:
            bits.append(f"focus: {self.focus}")
        if self.repo:
            bits.append(f"repo: {self.repo}")
        if self.path:
            bits.append(f"path: {self.path}")
        tail = (" — " + "; ".join(bits)) if bits else ""
        return f"- **{self.name}**{tail}"


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


# --------------------------------------------------------------------------- #
# The store
# --------------------------------------------------------------------------- #

class Store:
    """Read/write access to the project registry and generated digest."""

    def __init__(self, home: Optional[Path] = None):
        self.home = Path(home) if home is not None else default_home()

    # -- paths -------------------------------------------------------------- #
    @property
    def registry_path(self) -> Path:
        return self.home / "projects.json"

    @property
    def digest_path(self) -> Path:
        return self.home / "digest.md"

    @property
    def manifest_path(self) -> Path:
        return self.home / "manifest.json"

    @property
    def backups_dir(self) -> Path:
        return self.home / "backups"

    @property
    def activity_log_path(self) -> Path:
        return self.home / "activity.log"

    # -- activity log ------------------------------------------------------- #
    def log_event(self, message: str) -> None:
        """Append a timestamped line to the activity log so you can always see
        what Lifejacket has been doing. Best-effort — a logging hiccup must
        never break a sync."""
        try:
            self.home.mkdir(parents=True, exist_ok=True)
            ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with self.activity_log_path.open("a", encoding="utf-8") as fh:
                fh.write(f"{ts}  {message}\n")
        except OSError:
            pass

    def read_recent_events(self, limit: int = 20) -> List[str]:
        """The most recent activity lines, newest last. [] if nothing logged."""
        p = self.activity_log_path
        if not p.exists():
            return []
        try:
            lines = [l for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
        except OSError:
            return []
        return lines[-limit:]

    # -- lifecycle ---------------------------------------------------------- #
    def init(self) -> None:
        """Create the store directory and an empty registry if absent. Safe to
        call repeatedly — it never clobbers an existing registry."""
        self.home.mkdir(parents=True, exist_ok=True)
        self.backups_dir.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._save_projects([])

    def exists(self) -> bool:
        return self.registry_path.exists()

    # -- registry read/write ------------------------------------------------ #
    def load(self) -> List[Project]:
        """Load all projects. Returns [] if the store hasn't been initialised."""
        if not self.registry_path.exists():
            return []
        try:
            raw = json.loads(self.registry_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise StoreError(
                f"I couldn't read your project list at {self.registry_path}. "
                f"It may have been edited into invalid JSON ({exc}). I left it "
                "alone rather than guess."
            ) from exc
        items = raw.get("projects", []) if isinstance(raw, dict) else []
        projects: List[Project] = []
        for item in items:
            # Be tolerant: ignore unknown keys, require only id+name.
            known = {k: item.get(k) for k in (
                "id", "name", "path", "repo", "status", "focus", "updated"
            ) if k in item}
            if not known.get("name"):
                continue
            known.setdefault("id", slugify(known["name"]))
            known.setdefault("updated", _today())
            projects.append(Project(**known))
        return projects

    def _save_projects(self, projects: List[Project]) -> None:
        self.home.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": REGISTRY_VERSION,
            "projects": [
                {k: v for k, v in asdict(p).items() if v is not None}
                for p in projects
            ],
        }
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        write_text_atomic(self.registry_path, text, backup=self.registry_path.exists())

    # -- mutations ---------------------------------------------------------- #
    def add(self, project: Project, *, overwrite: bool = False) -> Project:
        """Add (or update) a project. Raises if the id already exists and
        ``overwrite`` is False, so a typo can't silently replace a project."""
        projects = self.load()
        for i, existing in enumerate(projects):
            if existing.id == project.id:
                if not overwrite:
                    raise StoreError(
                        f"A project with id '{project.id}' is already in your "
                        f"logbook ('{existing.name}'). Use overwrite to replace "
                        "it, or pick a different name."
                    )
                project.updated = _today()
                projects[i] = project
                self._save_projects(projects)
                return project
        projects.append(project)
        self._save_projects(projects)
        return project

    def remove(self, project_id: str) -> bool:
        """Remove a project by id. Returns True if something was removed."""
        projects = self.load()
        kept = [p for p in projects if p.id != project_id]
        if len(kept) == len(projects):
            return False
        self._save_projects(kept)
        return True

    def get(self, project_id: str) -> Optional[Project]:
        for p in self.load():
            if p.id == project_id:
                return p
        return None

    def update(self, project_id: str, **changes) -> Project:
        """Patch fields on an existing project (e.g. status, focus)."""
        projects = self.load()
        for i, p in enumerate(projects):
            if p.id == project_id:
                for k, v in changes.items():
                    if hasattr(p, k):
                        setattr(p, k, v)
                p.updated = _today()
                projects[i] = p
                self._save_projects(projects)
                return p
        raise StoreError(
            f"No project with id '{project_id}' in your logbook, so there was "
            "nothing to update."
        )

    # -- digest ------------------------------------------------------------- #
    def render_digest(self, projects: Optional[List[Project]] = None) -> str:
        """Render the curated digest text (the inner content of the injected
        block). This is the *only* text Lifejacket pushes into Claude's memory.
        Deterministic given the same projects, so the safe-write engine's hash
        idempotency works: re-running sync with no changes writes nothing."""
        if projects is None:
            projects = self.load()
        # Stable ordering by name so the digest (and its hash) doesn't churn
        # just because the registry's internal order shifted.
        projects = sorted(projects, key=lambda p: p.name.lower())
        lines = [
            "Jack's active projects (kept current by Claude Lifejacket — every "
            "Claude session sees this, so they share context across surfaces):",
            "",
        ]
        if projects:
            lines.extend(p.digest_line() for p in projects)
        else:
            lines.append("- _(no projects added yet — run `lifejacket add` to "
                         "start your logbook)_")
        return "\n".join(lines)

    def write_digest(self, text: Optional[str] = None) -> Path:
        """Write the rendered digest to ``digest.md`` for inspection/debugging.
        (The authoritative injection happens via the managed-block engine; this
        file is a human-readable mirror.)"""
        if text is None:
            text = self.render_digest()
        write_text_atomic(self.digest_path, text + "\n",
                          backup=self.digest_path.exists())
        return self.digest_path

    # -- manifest ----------------------------------------------------------- #
    def load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"version": 1, "surfaces": {}}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {"version": 1, "surfaces": {}}

    def save_manifest(self, manifest: dict) -> None:
        text = json.dumps(manifest, indent=2, ensure_ascii=False) + "\n"
        write_text_atomic(self.manifest_path, text,
                          backup=self.manifest_path.exists())

    def record_sync(self, surface_key: str, *, path: str, status: str,
                    digest_hash: str) -> None:
        """Note that we synced ``surface_key`` (e.g. a CLAUDE.md location) — what
        happened and the digest hash at the time. Lets `lifejacket status` show
        an honest, always-visible picture of every surface."""
        manifest = self.load_manifest()
        manifest.setdefault("surfaces", {})[surface_key] = {
            "path": path,
            "status": status,
            "digest_hash": digest_hash,
            "last_sync": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        self.save_manifest(manifest)
