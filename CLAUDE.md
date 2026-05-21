# CLAUDE.md — Claude Lifejacket

Context for any Claude (or human) picking up this repo. Keep it current.

## What this is

A Python tool that keeps every Claude session aware of your projects. You keep a
small curated logbook of projects; Lifejacket renders it to a one-line-per-project
digest and safely splices it into `~/.claude/CLAUDE.md` — the user-level memory
file read by **both** Claude Code and Cowork — inside a self-managed block. A
SessionStart hook refreshes it automatically. Sync-IN only for v0.1.

## Architecture (`src/claude_lifejacket/`)

- `safewrite.py` — **the bedrock.** The only code that edits the user's files.
  Managed-block injection between `<!-- LIFEJACKET:BEGIN/END -->` markers with
  seven safety guarantees: atomic temp→fsync→`os.replace`; backup-before-write +
  verify + rollback; edits confined to our markers; content-hash idempotency +
  hand-edit/tamper detection; UTF-8 no-BOM + line-ending preservation; symlink
  resolve + re-read before write; never auto-resolve a conflict. Public helper
  `write_text_atomic` reused by the rest of the package.
- `store.py` — the logbook: `~/.claude-lifejacket/` (`projects.json` registry,
  generated `digest.md`, `manifest.json` sync bookkeeping, `backups/`,
  `activity.log`). Renders the curated digest (deterministic → hash-stable).
- `surfaces.py` — finds the target file(s): user-level `~/.claude/CLAUDE.md`
  (covers Claude Code AND Cowork); opt-in extras via `surfaces.json`.
- `sync.py` — the conductor: digest → surfaces → safewrite → manifest + activity log.
- `discover.py` — finds projects from Claude Code history (`~/.claude/projects/*`,
  reads real `cwd` from transcripts) + the Cowork Projects folder.
- `cli.py` / `__main__.py` — `init/add/discover/list/show/update/remove/sync/
  status/log/dashboard/install-hook/uninstall-hook/doctor/hook`.
- `hookconfig.py` — installs the SessionStart hook by editing `settings.json`
  with the same never-corrupt care (refuses if the JSON won't parse).
- `dashboard.py` — self-contained light-Claude HTML status page.
- `appmodel.py` (Qt-free, tested) + `app.py` (PySide6 window) — the double-click app.

## Key decisions

- **Inline digest, not `@import`** — guaranteed-present in both surfaces.
- **File injection beats an MCP memory server** — guaranteed-present vs model-opt-in recall.
- **Curated, tiny digest** (one line per project) — a big KB bloats every session and goes stale.
- Hook command is `"<python>" -m claude_lifejacket hook` to dodge Windows PATH issues.

## Testing

`pip install -e ".[dev]" && pytest` (or double-click `run-tests.bat`). ~140 tests,
incl. tamper/idempotency/CRLF/unicode/dry-run for the engine and the full pipeline.
The GUI logic is in the Qt-free `appmodel` so it's tested without a display.

## Build & ship

`build-exe.ps1` (PyInstaller + PySide6) → `dist/Claude Lifejacket.exe`. GitHub
Actions (`.github/workflows/build.yml`) builds + attaches the .exe on a `v*` tag.

## Roadmap

v0.2: deeper per-project notes (Memory-Bank style), sync-**out** (harvest learnings
back), system-tray companion. Sibling tool **Claude Compass** will reuse this
safe-write engine to sync *the person* (working style) instead of projects.

## Part of the fleet

- [Claude Meter](https://github.com/JackBhanded/claude-meter) — live usage on your taskbar.
- [Claude Lifeboat](https://github.com/JackBhanded/claude-lifeboat) — backup & restore for Claude data.
- **Claude Lifejacket** — you are here.

_Maintainer's working-style/personal context is kept in private notes, not in this public file._
