"""dashboard.py — a calm, light-Claude status page for Lifejacket.

`lifejacket dashboard` renders a single self-contained HTML file (no external
assets, no dependencies) into the store directory and opens it in the browser.
It's the *face* of an otherwise-invisible safety tool: you can see, at a glance,

  * every project in your logbook,
  * every Claude memory surface and whether it's in sync (a status light),
  * when each was last synced,
  * whether the auto-sync hook is on,
  * and the EXACT digest text that every Claude session is reading.

That last part matters most: a tool that edits your memory should let you see
precisely what it wrote, verbatim.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from .hookconfig import HOOK_TAG, settings_path
from .store import Store
from .surfaces import claude_code_home, discover_surfaces, load_extra_surfaces
from .sync import digest_fingerprint

__all__ = ["render_dashboard_html", "write_dashboard"]

# Light "Claude brew" palette (matches Lifeboat / Meter).
_CREAM = "#F4EEE4"
_CARD = "#FBF8F2"
_INK = "#2B2722"
_MUTED = "#8A8178"
_ORANGE = "#D97757"
_LINE = "#E7DFD2"
# Refined status colours (no crude greens — a calm teal reads as "all good").
_OK = "#3F8F77"
_WARN = "#D9A757"
_ERR = "#C0563F"
_IDLE = "#B8AFA3"


# The official Claude logo (the orange asterisk), identical to the mark used in
# Claude Meter and Claude Lifeboat. Kept verbatim so it can never drift into an
# approximation.
_CLAUDE_LOGO_PATH = (
    "M4.709 15.955l4.72-2.647.08-.23-.08-.128H9.2l-.79-.048-2.698-.073-2.339"
    "-.097-2.266-.122-.571-.121L0 11.784l.055-.352.48-.321.686.06 1.52.103 "
    "2.278.158 1.652.097 2.449.255h.389l.055-.157-.134-.098-.103-.097-2.358"
    "-1.596-2.552-1.688-1.336-.972-.724-.491-.364-.462-.158-1.008.656-.722.881"
    ".06.225.061.893.686 1.908 1.476 2.491 1.833.365.304.145-.103.019-.073-.164"
    "-.274-1.355-2.446-1.446-2.49-.644-1.032-.17-.619a2.97 2.97 0 01-.104-.729L6"
    ".283.134 6.696 0l.996.134.42.364.62 1.414 1.002 2.229 1.555 3.03.456.898"
    ".243.832.091.255h.158V9.01l.128-1.706.237-2.095.23-2.695.08-.76.376-.91.747"
    "-.492.584.28.48.685-.067.444-.286 1.851-.559 2.903-.364 1.942h.212l.243-.242"
    ".985-1.306 1.652-2.064.73-.82.85-.904.547-.431h1.033l.76 1.129-.34 1.166"
    "-1.064 1.347-.881 1.142-1.264 1.7-.79 1.36.073.11.188-.02 2.856-.606 1.543"
    "-.28 1.841-.315.833.388.091.395-.328.807-1.969.486-2.309.462-3.439.813-.042"
    ".03.049.061 1.549.146.662.036h1.622l3.02.225.79.522.474.638-.079.485-1.215"
    ".62-1.64-.389-3.829-.91-1.312-.329h-.182v.11l1.093 1.068 2.006 1.81 2.509 "
    "2.33.127.578-.322.455-.34-.049-2.205-1.657-.851-.747-1.926-1.62h-.128v.17"
    ".444.649 2.345 3.521.122 1.08-.17.353-.608.213-.668-.122-1.374-1.925-1.415"
    "-2.167-1.143-1.943-.14.08-.674 7.254-.316.37-.729.28-.607-.461-.322-.747.322"
    "-1.476.389-1.924.315-1.53.286-1.9.17-.632-.012-.042-.14.018-1.434 1.967-2.18"
    " 2.945-1.726 1.845-.414.164-.717-.37.067-.662.401-.589 2.388-3.036 1.44"
    "-1.882.93-1.086-.006-.158h-.055L4.132 18.56l-1.13.146-.487-.456.061-.746"
    ".231-.243 1.908-1.312-.006.006z"
)


def _claude_logo_svg(size: int = 30) -> str:
    """The real Claude logo, sized in pixels."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true">'
        f'<title>Claude</title>'
        f'<path d="{_CLAUDE_LOGO_PATH}" fill="{_ORANGE}" fill-rule="nonzero"></path>'
        f'</svg>'
    )


def _surface_state(current_fp: str, entry) -> Tuple[str, str, str]:
    """Return (colour, label, detail) for a surface given the manifest entry."""
    if not entry:
        return _IDLE, "Never synced", "Run a sync to share your logbook here."
    status = entry.get("status", "")
    if status in ("tampered", "conflict"):
        return _ERR, "Needs your eyes", (
            "A block was hand-edited or is ambiguous — I left it untouched.")
    if entry.get("digest_hash") == current_fp:
        return _OK, "In sync", "This surface has your latest logbook."
    return _WARN, "Out of date", "Your logbook changed since the last sync here."


def _dot(colour: str) -> str:
    """A status light. The healthy/teal state gently breathes (shrink + dim) so
    the dashboard feels alive; everything else holds steady."""
    live = " live" if colour == _OK else ""
    return f'<span class="dot{live}" style="background:{colour}"></span>'


def _fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%a %d %b, %I:%M %p").lstrip("0")
    except (ValueError, TypeError):
        return iso or "—"


def render_dashboard_html(store: Store) -> str:
    """Build the full HTML document as a string (pure — easy to test)."""
    projects = sorted(store.load(), key=lambda p: p.name.lower())
    digest = store.render_digest(projects)
    current_fp = digest_fingerprint(digest)
    manifest = store.load_manifest().get("surfaces", {})
    surfaces = discover_surfaces(extra_paths=load_extra_surfaces(store.home))

    # Hook state.
    sp = settings_path(claude_code_home())
    hook_on = sp.exists() and HOOK_TAG in sp.read_text(
        encoding="utf-8", errors="ignore")

    esc = html.escape
    now = datetime.now(timezone.utc).astimezone().strftime(
        "%a %d %b %Y, %I:%M %p").lstrip("0")

    # ---- project cards ----
    if projects:
        cards = []
        for p in projects:
            meta_bits: List[str] = []
            if p.status:
                meta_bits.append(
                    f'<span class="pill">{esc(p.status)}</span>')
            if p.focus:
                meta_bits.append(
                    f'<div class="focus">{esc(p.focus)}</div>')
            link = ""
            if p.repo:
                href = p.repo if p.repo.startswith("http") else f"https://{esc(p.repo)}"
                link = f'<a class="repo" href="{esc(href)}">{esc(p.repo)}</a>'
            cards.append(f"""
      <div class="card project">
        <div class="project-head">
          <h3>{esc(p.name)}</h3>
          {''.join(b for b in meta_bits if b.startswith('<span'))}
        </div>
        {''.join(b for b in meta_bits if b.startswith('<div'))}
        {link}
      </div>""")
        projects_html = "\n".join(cards)
    else:
        projects_html = """
      <div class="card empty">
        <p>Your logbook is empty.</p>
        <code>lifejacket add "My Project"</code>
      </div>"""

    # ---- surface rows ----
    if surfaces:
        rows = []
        for surf in surfaces:
            colour, label, detail = _surface_state(
                current_fp, manifest.get(surf.key))
            last = _fmt_time(manifest.get(surf.key, {}).get("last_sync", ""))
            rows.append(f"""
      <div class="card surface">
        {_dot(colour)}
        <div class="surface-body">
          <div class="surface-label">{esc(surf.label)}</div>
          <div class="surface-detail">{esc(detail)}</div>
          <div class="surface-path">{esc(str(surf.path))}</div>
        </div>
        <div class="surface-state">
          <div class="state-label" style="color:{colour}">{esc(label)}</div>
          <div class="state-time">{esc(last)}</div>
        </div>
      </div>""")
        surfaces_html = "\n".join(rows)
    else:
        surfaces_html = f"""
      <div class="card empty">
        <p>No Claude memory surfaces found.</p>
        <div class="surface-path">Looked in: {esc(str(claude_code_home()))}</div>
      </div>"""

    hook_colour = _OK if hook_on else _IDLE
    hook_text = ("On — every session re-syncs automatically"
                 if hook_on else "Off — turn on with: lifejacket install-hook")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Claude Lifejacket</title>
<style>
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0 0 56px;
    background: {_CREAM}; color: {_INK};
    font: 15px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 860px; margin: 0 auto; padding: 0 24px; }}
  header {{
    display: flex; align-items: center; gap: 14px;
    padding: 34px 0 8px;
  }}
  header .logo {{ display: inline-flex; }}
  header h1 {{ font-size: 24px; margin: 0; font-weight: 650; letter-spacing: -0.2px; }}
  header .sub {{ color: {_MUTED}; font-size: 13px; margin-top: 2px; }}
  h2 {{
    font-size: 13px; text-transform: uppercase; letter-spacing: 0.8px;
    color: {_MUTED}; margin: 30px 0 12px; font-weight: 600;
  }}
  .card {{
    background: {_CARD}; border: 1px solid {_LINE}; border-radius: 14px;
    padding: 16px 18px; margin-bottom: 12px;
  }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .grid .card {{ margin-bottom: 0; }}
  .project-head {{ display: flex; align-items: center; gap: 10px; }}
  .project h3 {{ margin: 0; font-size: 16px; font-weight: 600; }}
  .pill {{
    font-size: 11px; font-weight: 600; color: {_ORANGE};
    background: rgba(217,119,87,0.12); padding: 2px 9px; border-radius: 999px;
    text-transform: lowercase;
  }}
  .focus {{ color: {_MUTED}; font-size: 13.5px; margin-top: 8px; }}
  .repo {{ display: inline-block; margin-top: 8px; font-size: 12.5px;
           color: {_ORANGE}; text-decoration: none; }}
  .repo:hover {{ text-decoration: underline; }}
  .surface {{ display: flex; align-items: center; gap: 14px; }}
  .surface-body {{ flex: 1; min-width: 0; }}
  .surface-label {{ font-weight: 600; }}
  .surface-detail {{ color: {_MUTED}; font-size: 13px; margin-top: 2px; }}
  .surface-path {{
    color: {_MUTED}; font-size: 11.5px; margin-top: 4px;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
  }}
  .surface-state {{ text-align: right; white-space: nowrap; }}
  .state-label {{ font-weight: 600; font-size: 13.5px; }}
  .state-time {{ color: {_MUTED}; font-size: 11.5px; margin-top: 2px; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; flex: none;
          box-shadow: 0 0 0 4px rgba(0,0,0,0.03); }}
  @keyframes lj-pulse {{
    0%, 100% {{ transform: scale(1);    opacity: 1;   }}
    50%      {{ transform: scale(0.68); opacity: 0.5; }}
  }}
  .dot.live {{ animation: lj-pulse 1.9s ease-in-out infinite; }}
  @media (prefers-reduced-motion: reduce) {{ .dot.live {{ animation: none; }} }}
  .hookbar {{ display: flex; align-items: center; gap: 12px; }}
  .digest {{
    background: #fff; border: 1px dashed {_LINE}; border-radius: 12px;
    padding: 16px 18px; white-space: pre-wrap; font-size: 13.5px;
    font-family: ui-monospace, "Cascadia Code", Consolas, monospace;
    color: #4a443c; overflow-x: auto;
  }}
  .empty {{ text-align: center; color: {_MUTED}; }}
  .empty code {{ display: inline-block; margin-top: 8px; background: {_CREAM};
                 padding: 6px 12px; border-radius: 8px; color: {_INK}; }}
  footer {{ color: {_MUTED}; font-size: 12px; text-align: center; margin-top: 34px; }}
</style>
</head>
<body>
  <div class="wrap">
    <header>
      <span class="logo">{_claude_logo_svg(34)}</span>
      <div>
        <h1>Claude Lifejacket</h1>
        <div class="sub">Every Claude session, aware of all your projects.</div>
      </div>
    </header>

    <h2>Projects &middot; {len(projects)}</h2>
    <div class="grid">
      {projects_html}
    </div>

    <h2>Claude memory surfaces</h2>
    {surfaces_html}

    <h2>Auto-sync</h2>
    <div class="card hookbar">
      {_dot(hook_colour)}
      <div>{esc(hook_text)}</div>
    </div>

    <h2>What every session is reading</h2>
    <div class="digest">{esc(digest)}</div>

    <footer>Snapshot taken {esc(now)} &middot; re-run <code>lifejacket dashboard</code> to refresh</footer>
  </div>
</body>
</html>"""


def write_dashboard(store: Store) -> Path:
    """Render and write the dashboard into the store dir. Returns its path.
    (Lives in the store, never on the Desktop — no clutter.)"""
    store.home.mkdir(parents=True, exist_ok=True)
    out = store.home / "dashboard.html"
    out.write_text(render_dashboard_html(store), encoding="utf-8")
    return out
