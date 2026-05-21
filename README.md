<div align="center">

<img src="assets/claude-logo.svg" width="64" alt="Claude" />

# Claude Lifejacket

**Keep every Claude session aware of all your projects — safely.**

Claude Code, Cowork, the desktop app… each session starts amnesiac about the
others. Lifejacket keeps a tiny, curated logbook of your projects and quietly
syncs it into the memory every Claude session reads — so they all stay on the
same page, automatically.

[![License: MIT](https://img.shields.io/badge/License-MIT-D97757.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-D97757.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/tests-108%20passing-3F8F77.svg)](#safety--testing)

</div>

---

## Why

If you build with Claude across more than one surface, you've felt this: you
explain a project to Claude Code in the morning, then open Cowork in the
afternoon and explain it all over again. You are the integration layer, copying
context between sessions by hand.

Lifejacket makes that the tool's job. You describe each project once. Lifejacket
turns your logbook into a one-line-per-project digest and splices it into the
user-level `~/.claude/CLAUDE.md` — the memory file that **both Claude Code and
Cowork read** — inside a clearly marked, self-managed block. A SessionStart hook
refreshes it automatically, so every new session opens already knowing what
you're working on.

## Safety first (this edits your memory files)

A tool that writes to your Claude memory has exactly one unforgivable failure:
corrupting it. Lifejacket is built so that **cannot** happen. Every write goes
through an audited engine with seven non-negotiable guarantees:

1. **Never writes in place** — temp file → fsync → atomic rename. A crash
   mid-write can't leave a half-written file.
2. **Backs up before every change** and verifies afterward; mismatch → automatic
   rollback.
3. **Touches only the bytes between its own markers** — your content is never in
   range. Ambiguous markers → it refuses and changes nothing.
4. **Content-hashed for idempotency** — re-syncing identical content writes
   nothing, and a block you've hand-edited is detected and **left untouched**
   unless you explicitly `--force`.
5. **UTF-8, no BOM, your line endings preserved** (CRLF stays CRLF).
6. **Re-reads immediately before writing** and resolves symlinks.
7. **Never auto-resolves a conflict** in your file — it stops and hands it back.

`settings.json` (for the hook) gets the same care: if it won't parse as JSON,
Lifejacket refuses to write rather than risk your config.

> 108 tests cover all of the above, including hand-edit detection, ambiguous
> markers, CRLF preservation, unicode, and dry-run-writes-nothing.

## Install

**Easiest — the app (Windows):** download **`Claude Lifejacket.exe`** from the
[latest release](https://github.com/JackBhanded/claude-lifejacket/releases) and
double-click it. A little window opens showing your projects, with checkboxes to
pick what to share, a **Sync** button, an **Auto-sync** toggle, and **Open
dashboard**. No Python, no terminal.

**For the command line (any platform):** requires Python 3.9+
([get it here](https://www.python.org/downloads/) — on Windows tick "Add Python
to PATH").

- Windows: right-click `install.ps1` → **Run with PowerShell** (installs for you,
  no admin), or `pip install --user .`
- macOS/Linux: `pip install --user .`

After installing, `python -m claude_lifejacket <command>` always works; from the
project folder you can also run `.\lifejacket <command>` (Windows) or
`./lifejacket <command>` (macOS/Linux).

## Quickstart

```bash
lifejacket init                              # set up your local logbook
lifejacket discover                          # find your existing projects...
lifejacket discover --all                    # ...and add them (or --add 1,3,4)
lifejacket sync                              # share them with every Claude session
lifejacket install-hook                      # make sync automatic, forever
lifejacket dashboard                         # see it all in your browser
```

Prefer to add projects by hand? `lifejacket add "Claude Meter" --status shipped
--repo github.com/JackBhanded/claude-meter --focus "usage logging next"`.

That's it. From now on, every Claude Code session — and Cowork, via the same
file — starts already aware of your projects.

## The dashboard

`lifejacket dashboard` writes a self-contained HTML page and opens it: your
projects as cards, every Claude memory surface with a live status light, the
auto-sync hook state, and — most importantly — the **exact digest text** every
session is reading, shown verbatim. A tool that edits your memory should let you
see precisely what it wrote.

<div align="center">
<img src="assets/dashboard.png" width="680" alt="Claude Lifejacket dashboard" />
</div>

## Commands

| Command | What it does |
|---|---|
| `lifejacket init` | Create the local logbook (`~/.claude-lifejacket/`) |
| `lifejacket add "Name" [--status --focus --repo --path]` | Add a project |
| `lifejacket discover [--all] [--add 1,3]` | Find projects (Claude Code history + your Cowork Projects folder) not yet in the logbook, and add the ones you pick |
| `lifejacket list` | Show your projects |
| `lifejacket show <id>` | One project's details + a peek at its folder contents |
| `lifejacket update <id> [...]` | Change a project's fields |
| `lifejacket remove <id>` | Remove a project |
| `lifejacket sync [--dry-run] [--force]` | Push the digest into your Claude memory |
| `lifejacket status` | Where everything stands, per surface |
| `lifejacket log [--lines N]` | Recent sync activity (so you can see it's working) |
| `lifejacket dashboard [--no-open]` | Open the visual status page |
| `lifejacket install-hook` / `uninstall-hook` | Turn automatic syncing on/off |
| `lifejacket doctor` | Quick health check |

`--dry-run` previews every change without writing a byte. Start there if you're
nervous — you'll see exactly what would happen first.

## How it works

```
~/.claude-lifejacket/        your logbook (you own this)
  projects.json              the registry — the one file you'd hand-edit
  digest.md                  generated: the curated text that gets injected
  manifest.json              per-surface sync bookkeeping
  backups/                   timestamped backups of anything we change

         |  lifejacket sync
         v
~/.claude/CLAUDE.md          read by BOTH Claude Code and Cowork
  ...your own content, untouched...
  <!-- LIFEJACKET:BEGIN id=projects v=1 -->
  ...the curated digest...
  <!-- LIFEJACKET:END id=projects v=1 sha256=... -->
  ...your own content, untouched...
```

The digest is deliberately tiny — one line per project — because a giant
knowledge base just bloats every session's context and goes stale. Small and
current beats big and forgotten.

## Safety & testing

```bash
pip install -e ".[dev]"
pytest            # 108 tests
```

On Windows you can also just double-click `run-tests.bat`.

## Roadmap

- **v0.2** — deeper per-project notes (Memory Bank style), sync-*out* (harvest
  new learnings back into the logbook), a system-tray companion.
- **Claude Compass** — a sibling tool that syncs *you* (working style,
  preferences) into every session, sharing this same safe-write engine.

## Part of a little fleet

Lifejacket is one of a set of open tools for people who build with Claude:

- **[Claude Meter](https://github.com/JackBhanded/claude-meter)** — live usage on your taskbar.
- **[Claude Lifeboat](https://github.com/JackBhanded/claude-lifeboat)** — backup & restore for your Claude data.
- **Claude Lifejacket** — keep every session aware of your projects. *(you are here)*

## About the author

<table>
<tr>
<td width="120" valign="top">
<img src="https://www.SawYouAtSinai.com/_layouts/images/team/jackbio.jpg" width="100" alt="Jack Bhanded">
</td>
<td valign="top">

Built by **[Jack Bhanded](https://www.sawyouatsinai.com/jewish-dating-team.aspx)**, Lead developer and architect at [SawYouAtSinai](https://www.sawyouatsinai.com). Devotee of innovative technologies and gadgets. Built this because he runs Claude across Claude Code and Cowork all day and was tired of re-explaining the same projects to every fresh session.

</td>
</tr>
</table>

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for the version-by-version list of changes.

## License

[MIT](LICENSE) © Jack Bhanded — do whatever you want, just keep the copyright notice.
