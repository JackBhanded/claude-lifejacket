# Changelog

All notable changes to Claude Lifejacket are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.1.0] — 2026-05-21

First public release. Sync-in only — keep every Claude session aware of your
projects, safely.

### Added
- **Safe-write engine** (`safewrite.py`) — managed-block injection with seven
  safety guarantees: atomic writes, backup + verify + rollback, marker-bounded
  edits, content-hash idempotency, hand-edit/tamper detection, line-ending
  preservation, and never auto-resolving conflicts.
- **Project logbook** (`store.py`) — a local registry (`~/.claude-lifejacket/`)
  that renders a curated, one-line-per-project digest.
- **Surface detection + sync** — finds the user-level `~/.claude/CLAUDE.md`
  (read by both Claude Code and Cowork) and splices the digest in safely;
  records every outcome in a manifest.
- **CLI** — `init`, `add`, `list`, `update`, `remove`, `sync`, `status`,
  `dashboard`, `install-hook`, `uninstall-hook`, `doctor`.
- **SessionStart hook** — re-syncs and injects the digest at the start of every
  Claude Code session; `settings.json` is edited with the same never-corrupt
  care as your CLAUDE.md.
- **HTML dashboard** — a light "Claude brew" status page: project cards,
  per-surface status lights (with a gently pulsing "in sync" indicator), hook
  state, and the verbatim digest every session reads.
- **108 tests** covering the engine and the full pipeline.

[0.1.0]: https://github.com/JackBhanded/claude-lifejacket/releases/tag/v0.1.0
