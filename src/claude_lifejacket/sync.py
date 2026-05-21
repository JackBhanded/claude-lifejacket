"""sync.py — push the curated digest into every Claude memory surface, safely.

This is the conductor. It does no risky byte-twiddling itself: it asks the
:mod:`store` for the digest, asks :mod:`surfaces` where to put it, and hands the
actual file edit to the audited managed-block engine in :mod:`safewrite`. Then
it records what happened in the manifest so ``lifejacket status`` can always
show an honest, up-to-the-second picture.

Design choices that keep this safe and calm:
  * The digest is injected **inline** into a delimited managed block (not via an
    ``@import`` to a second file). Inline is guaranteed-present and behaves
    identically in Claude Code and Cowork — no dependency on import resolution.
  * All backups land in the store's own ``backups/`` dir, so we never litter
    the user's ``~/.claude`` folder.
  * ``dry_run=True`` previews every surface without writing a byte — the
    friendly way to let a nervous user see exactly what would change first.
  * A hand-edited block returns TAMPERED and is left untouched unless the
    caller passes ``force=True`` after confirming with the user.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .safewrite import SyncResult, SyncStatus, sync_managed_block
from .store import DIGEST_BLOCK_ID, DIGEST_VERSION, Store
from .surfaces import Surface, discover_surfaces, load_extra_surfaces

__all__ = ["SurfaceReport", "sync_all", "preview_all", "digest_fingerprint"]


@dataclass
class SurfaceReport:
    """What happened (or would happen) for one surface."""

    surface: Surface
    result: SyncResult

    @property
    def changed(self) -> bool:
        return self.result.changed

    @property
    def headline(self) -> str:
        """A one-line, smile-bringing summary for status output."""
        icons = {
            SyncStatus.CREATED: "+",
            SyncStatus.UPDATED: "~",
            SyncStatus.UNCHANGED: "=",
            SyncStatus.SKIPPED: ".",
            SyncStatus.TAMPERED: "!",
            SyncStatus.CONFLICT: "!",
        }
        icon = icons.get(self.result.status, "?")
        return f"[{icon}] {self.surface.label}: {self.result.message.strip()}"


def digest_fingerprint(digest: str) -> str:
    """A short, stable fingerprint of the digest text for manifest bookkeeping.
    (Not a security boundary — just a 'did the content change?' marker.)"""
    norm = digest.replace("\r\n", "\n").replace("\r", "\n").strip("\n")
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def sync_all(
    store: Store,
    *,
    claude_home: Optional[Path] = None,
    extra_paths: Optional[List[Path]] = None,
    force: bool = False,
    create_if_missing: bool = True,
    dry_run: bool = False,
) -> List[SurfaceReport]:
    """Sync the store's digest into every discovered surface.

    Returns one :class:`SurfaceReport` per surface. Never raises for an
    awkward user file — those come back as TAMPERED/CONFLICT reports so the
    caller can show a diff and decide.
    """
    digest = store.render_digest()
    fp = digest_fingerprint(digest)

    # Gather opt-in extras from the store config plus any passed in directly.
    extras = list(load_extra_surfaces(store.home))
    if extra_paths:
        extras.extend(Path(p) for p in extra_paths)

    surfaces = discover_surfaces(claude_home=claude_home, extra_paths=extras)

    reports: List[SurfaceReport] = []
    for surface in surfaces:
        result = sync_managed_block(
            surface.path,
            DIGEST_BLOCK_ID,
            DIGEST_VERSION,
            digest,
            create_if_missing=create_if_missing,
            force=force,
            backup_dir=store.backups_dir,
            dry_run=dry_run,
        )
        if not dry_run:
            store.record_sync(
                surface.key,
                path=str(surface.path),
                status=str(result.status),
                digest_hash=fp,
            )
        reports.append(SurfaceReport(surface=surface, result=result))

    # Keep the human-readable mirror in step (skip on dry-run — preview only).
    if not dry_run:
        store.write_digest(digest)

    return reports


def preview_all(
    store: Store,
    *,
    claude_home: Optional[Path] = None,
    extra_paths: Optional[List[Path]] = None,
) -> List[SurfaceReport]:
    """Dry-run convenience: show what `sync_all` would do, writing nothing."""
    return sync_all(
        store,
        claude_home=claude_home,
        extra_paths=extra_paths,
        dry_run=True,
    )
