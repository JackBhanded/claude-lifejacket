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

## Safety first (it edits your memory file)

A tool that writes into your Claude memory has one job it must never get wrong:
messing up that file. Lifejacket is built so it simply can't. In plain terms:

- **It can't leave your file half-written** — even if your computer crashes at the
  worst possible moment.
- **It backs up before every change** and checks its work afterward; if anything
  looks off, it puts the original right back.
- **It only ever touches its own little labelled section.** Your own notes are
  off-limits — and if it can't tell exactly where its section is, it stops and
  changes nothing.
- **It leaves your edits alone.** If you've hand-tweaked its section, it notices
  and won't overwrite you unless you explicitly tell it to.
- **It never guesses.** If something's unclear, it stops and hands the decision
  back to you rather than risk your file.

The settings file it uses to set up auto-syncing gets the same care: if that file
isn't valid, Lifejacket refuses to touch it.

> 108 automated tests cover all of this — including the "don't overwrite my
> hand-edits" and "a preview writes nothing" promises.

## Install

**Easiest — the app (Windows):** download **`Claude Lifejacket.exe`** from the
[latest release](https://github.com/JackBhanded/claude-lifejacket/releases/latest)
and double-click it. A little window opens showing your projects, with checkboxes to
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

## How it differs from the alternatives

The idea of "give the agent persistent memory" is a busy space — but most of it
solves a *different* problem than Lifejacket does. The honest comparison:

- **[Cline Memory Bank](https://docs.cline.bot/features/memory-bank)** and its
  Claude Code port **[claude-code-memory-bank](https://github.com/hudrazine/claude-code-memory-bank)**
  build a rich, multi-file knowledge base *per project*, maintained by the agent
  itself. If you want deep, structured docs about **one** codebase, they're
  excellent. Lifejacket goes the other way: a tiny, one-line-per-project digest
  that spans **all** your projects and is hand-curated, so every session gets
  cheap, current orientation rather than a big knowledge base to wade through.
- **CLAUDE.md generators** (e.g. [ClaudeForge](https://github.com/alirezarezvani/ClaudeForge),
  keeborg) do a great one-shot job of *writing* a CLAUDE.md for you. Lifejacket
  isn't a generator — it's an ongoing, **safe-write** sync that owns just its own
  labelled block and never clobbers your hand-edits.
- **[mem0 / OpenMemory MCP](https://github.com/mem0ai/mem0)** and the
  **[official memory MCP server](https://github.com/modelcontextprotocol/servers/tree/main/src/memory)**
  are powerful universal memories (vector stores, knowledge graphs) that the model
  *chooses* to query. They're the right tool if you want cross-tool, pull-based
  recall. Lifejacket's digest is the opposite by design: zero-dependency plain
  text that's **guaranteed present** in the file both Claude Code and Cowork
  always read — nothing to opt into, nothing to forget to call.
- **[claude-mem](https://github.com/thedotmack/claude-mem)** and
  context-keeper-style tools auto-capture and compress your *sessions* into memory.
  That's automatic but lossy, and per-session. Lifejacket is a hand-kept project
  logbook — small, deliberate, and yours to edit.

In short: if you want an agent-maintained, single-project knowledge base, or a
heavyweight universal memory, the tools above are great. Lifejacket fills the spot
none of them occupy — a **curated, cross-project, one-line digest, safely written
into the one file every Claude surface already reads.**

## Part of a little fleet

Lifejacket is one of a set of open tools for people who build with Claude:

- **[Claude Meter](https://github.com/JackBhanded/claude-meter)** — live usage on your taskbar.
- **[Claude Lifeboat](https://github.com/JackBhanded/claude-lifeboat)** — backup & restore for your Claude data.
- **Claude Lifejacket** — keep every session aware of your projects. *(you are here)*
- **[Claude Compass](https://github.com/JackBhanded/claude-compass)** — keep every session attuned to *you* (your working style).
- **[Claude Parachute](https://github.com/JackBhanded/claude-parachute)** — a safety net for the Bash changes Claude Code's `/rewind` can't see.

**Better together:** Lifejacket teaches every Claude session *what you're working
on*; [Compass](https://github.com/JackBhanded/claude-compass) teaches it *how you
like to work*. Install both and a fresh session opens already knowing your
projects **and** your style — context + personalization, zero re-explaining.

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
