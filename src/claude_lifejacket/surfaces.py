"""surfaces.py — find the Claude memory files we're allowed to sync into.

A *surface* is one place a Claude session reads its persistent memory from. The
research turned up an elegant fact: the user-level ``~/.claude/CLAUDE.md`` is
loaded by **both** Claude Code (CLI) *and* Cowork (desktop). So syncing that one
file makes every surface project-aware at once — no need to go spelunking into
fragile, undocumented Cowork space directories for v0.1.

Discovery is deliberately conservative:
  * We only offer the Claude Code user CLAUDE.md when ``~/.claude`` actually
    exists (i.e. Claude Code is installed) — we never scatter files into a
    home directory on spec.
  * Power users can register *extra* explicit paths (e.g. a project-level
    CLAUDE.md, or a specific Cowork memory file they trust) via the store's
    ``surfaces.json``. Those are opt-in by definition.

Everything here is pure path logic so it's fully testable without a real
Claude install — every entry point takes an injectable home directory.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

__all__ = [
    "Surface",
    "claude_code_home",
    "discover_surfaces",
    "load_extra_surfaces",
]


@dataclass
class Surface:
    """One syncable memory location."""

    key: str          # stable id, e.g. "claude-code:user"
    label: str        # human label for status output
    path: Path        # the CLAUDE.md (or memory .md) file we manage
    kind: str         # "claude-code" | "cowork" | "manual"
    exists: bool      # does the target file exist right now?

    @property
    def parent_exists(self) -> bool:
        return self.path.parent.exists()


def claude_code_home() -> Path:
    """The Claude Code config dir. Honours ``CLAUDE_CONFIG_DIR`` (which Claude
    Code itself respects); otherwise ``~/.claude``."""
    override = os.environ.get("CLAUDE_CONFIG_DIR")
    if override:
        return Path(override).expanduser()
    return Path.home() / ".claude"


def discover_surfaces(
    claude_home: Optional[Path] = None,
    extra_paths: Optional[List[Path]] = None,
) -> List[Surface]:
    """Return the surfaces we can sync into.

    Parameters
    ----------
    claude_home:
        Override the Claude Code home (for tests / unusual installs). Defaults
        to :func:`claude_code_home`.
    extra_paths:
        Additional explicit CLAUDE.md / memory files to manage (opt-in).
    """
    ch = Path(claude_home) if claude_home is not None else claude_code_home()
    surfaces: List[Surface] = []

    # The one that matters most: user-level CLAUDE.md, loaded by Claude Code AND
    # Cowork. We offer it whenever the ~/.claude dir exists (Claude Code present)
    # OR the file already exists.
    cc_file = ch / "CLAUDE.md"
    if ch.exists() or cc_file.exists():
        surfaces.append(Surface(
            key="claude-code:user",
            label="Claude Code + Cowork (user memory ~/.claude/CLAUDE.md)",
            path=cc_file,
            kind="claude-code",
            exists=cc_file.exists(),
        ))

    # Opt-in extras.
    seen = {s.path.resolve() for s in surfaces if s.path.exists()}
    for raw in (extra_paths or []):
        p = Path(raw).expanduser()
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        surfaces.append(Surface(
            key=f"manual:{p.name}:{abs(hash(str(rp))) % 100000}",
            label=f"Manual ({p})",
            path=p,
            kind="manual",
            exists=p.exists(),
        ))

    return surfaces


def load_extra_surfaces(store_home: Path) -> List[Path]:
    """Read opt-in extra surface paths from ``<store>/surfaces.json``.

    Format::

        { "paths": ["/abs/path/to/CLAUDE.md", "~/something/memory.md"] }

    Missing or malformed file → no extras (we never crash over a config file).
    """
    cfg = Path(store_home) / "surfaces.json"
    if not cfg.exists():
        return []
    try:
        data = json.loads(cfg.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    paths = data.get("paths", []) if isinstance(data, dict) else []
    out: List[Path] = []
    for entry in paths:
        if isinstance(entry, str) and entry.strip():
            out.append(Path(entry).expanduser())
    return out
