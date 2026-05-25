# Changelog

All notable changes to Claude Lifejacket are documented here.
This project follows [Semantic Versioning](https://semver.org/).

## [0.1.2] — 2026-05-25

### Changed
- **A gorgeous new look (elevated Claude-brew + dark mode).** The dashboard is now
  frosted glassmorphism over a soft drifting aurora — a count-up stat row, a glassy
  project grid, status-light surfaces, the verbatim digest, and a sleek dark mode.
  The double-click window is restyled to match (gradient buttons, soft cards,
  light/dark toggle).

### Added
- **System-tray companion** — run `lifejacket tray` (or close the window) and
  Lifejacket tucks into your system tray with a small life-vest icon, so it can
  keep quietly syncing in the background. Right-click for Open / Sync now / Open
  dashboard / Quit; double-click to reopen the window. Closing the window now
  hides to the tray instead of quitting.
- **`lifejacket tray` command** to launch straight into the tray.
- **Run at startup** — a "Run at startup" toggle in the tray menu pins Lifejacket
  to your per-user Windows startup (no admin needed), so it keeps your sessions
  project-aware from the moment you log in. Greyed out when running from source.

### Changed
- The tray icon is a distinct life-vest glyph (in Claude orange) rather than the
  Claude asterisk, so Lifejacket is easy to tell apart from the other fleet tools
  at a glance in the tray. The Claude logo stays the brand mark in the window
  header, dashboard, and README.
- README: added an honest **"How it differs from the alternatives"** section.

[0.1.2]: https://github.com/JackBhanded/claude-lifejacket/compare/v0.1.1...v0.1.2

## [0.1.1] — 2026-05-21

Release-automation fix so the prebuilt `Claude Lifejacket.exe` builds and
attaches to the GitHub release automatically (the workflow now has the
permission it needs). No functional changes to the app itself.

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
- **CLI** — `init`, `add`, `discover`, `list`, `show`, `update`, `remove`,
  `sync`, `status`, `dashboard`, `install-hook`, `uninstall-hook`, `doctor`.
- **`discover`** — finds projects from your Claude Code history and your Cowork
  Projects folder that aren't in the logbook yet, and adds the ones you pick (so
  you never have to remember and re-type them).
- **`show <id>`** — a project's full details plus a peek at its folder contents.
- **Activity log** — every sync writes a timestamped line to
  `~/.claude-lifejacket/activity.log`. See it via `lifejacket log`, the
  "Recent activity" panel in the app window and dashboard, or the app's
  "Open log" button — so you can always tell syncing is working.
- **Double-click app** — `Claude Lifejacket.exe` (PySide6): a light-Claude
  window with your projects, checkboxes to pick what to share, and Sync /
  Auto-sync / Open-dashboard buttons. No terminal. Built via PyInstaller +
  GitHub Actions, same as Claude Meter. GUI logic lives in a fully-tested,
  Qt-free `appmodel`.
- **Easy install** — a one-click Windows `install.ps1`, plus `lifejacket`/
  `lifejacket.bat` wrappers so you can run it from the folder without touching
  PATH.
- **SessionStart hook** — re-syncs and injects the digest at the start of every
  Claude Code session; `settings.json` is edited with the same never-corrupt
  care as your CLAUDE.md.
- **HTML dashboard** — a light "Claude brew" status page: project cards,
  per-surface status lights (with a gently pulsing "in sync" indicator), hook
  state, and the verbatim digest every session reads.
- **108 tests** covering the engine and the full pipeline.

[0.1.0]: https://github.com/JackBhanded/claude-lifejacket/releases/tag/v0.1.0
