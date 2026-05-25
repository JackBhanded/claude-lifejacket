"""app.py — the double-click Claude Lifejacket window.

Deliberately thin: all the real work lives in :mod:`appmodel` (which is fully
unit-tested without a display). This file is just paint and button wiring, so a
non-developer can run the .exe, tick the projects they want, hit Sync, and never
see a terminal.

If PySide6 isn't installed, ``main()`` explains how to get it rather than
crashing — but the shipped .exe bundles it.
"""

from __future__ import annotations

import sys
import webbrowser

from . import startup
from .appmodel import add_candidates, build_snapshot, do_sync, set_autosync
from .dashboard import _claude_logo_svg, write_dashboard
from .store import Store, default_home

# Kept for the tray-glyph fill.
_ORANGE = "#C8632F"
_OK, _WARN, _ERR, _IDLE = "#2E7D63", "#B97E1E", "#B6492F", "#8C8174"
_STATE_COLOUR = {"in_sync": _OK, "out_of_date": _WARN, "never": _IDLE, "attention": _ERR}

# --- the fleet's elevated-brew look, tuned for Qt, with a sleek dark mode. ----
_LIGHT = {
    "bg": "#F4EFE6", "ink": "#1C1712", "muted": "#5F564B", "orange": "#C8632F",
    "orange2": "#E0875C", "line": "#E4DBCC", "btn": "#FBF6EE", "btnhover": "#FFFFFF",
    "scroll": "#D9CFBE", "shadow_a": 46,
}
_DARK = {
    "bg": "#17120E", "ink": "#F7F1E7", "muted": "#B7AEA2", "orange": "#E0875C",
    "orange2": "#EE9E75", "line": "#3A322A", "btn": "#241D16", "btnhover": "#312820",
    "scroll": "#43392F", "shadow_a": 150,
}


def _qss(dark: bool) -> str:
    c = _DARK if dark else _LIGHT
    grad = (f"qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 {c['orange2']}, "
            f"stop:1 {c['orange']})")
    return f"""
QWidget {{ background: {c['bg']}; color: {c['ink']};
           font-family: 'Segoe UI', -apple-system, Roboto, Arial; font-size: 13px; }}
QLabel#title {{ font-size: 22px; font-weight: 700; color: {c['ink']}; }}
QLabel#sub {{ color: {c['muted']}; font-size: 12px; }}
QLabel#section {{ color: {c['muted']}; font-size: 11px; font-weight: 700; }}
QFrame#card {{ background: transparent; border: 1px solid {c['line']}; border-radius: 14px; }}
QPushButton {{ background: {c['btn']}; border: 1px solid {c['line']};
               border-radius: 10px; padding: 8px 16px; color: {c['ink']}; }}
QPushButton:hover {{ background: {c['btnhover']}; border-color: {c['orange']}; }}
QPushButton#primary {{ background: {grad}; color: white; border: none; font-weight: 700; }}
QPushButton#primary:hover {{ background: {c['orange']}; }}
QPushButton#toggle {{ background: {c['btn']}; border: 1px solid {c['line']}; border-radius: 10px;
  padding: 7px 14px; color: {c['muted']}; font-weight: 600; }}
QPushButton#toggle:hover {{ color: {c['ink']}; border-color: {c['orange']}; background: {c['btnhover']}; }}
QCheckBox {{ padding: 3px; spacing: 8px; color: {c['ink']}; }}
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['scroll']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {c['muted']}; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
"""


def _missing_pyside_message() -> str:
    return (
        "Claude Lifejacket's window needs PySide6.\n\n"
        "Install it with:\n    pip install --user PySide6\n\n"
        "Or use the command line instead:\n"
        "    python -m claude_lifejacket dashboard\n"
    )


def _lifejacket_vest_svg(size=64):
    """A clean little life-vest glyph in Claude's orange. The tray icon uses this
    (rather than the Claude logo) so Lifejacket is easy to tell apart from the
    other fleet tools at a glance — they'd otherwise all show the same asterisk.
    The Claude logo stays the brand mark in the window header and the README."""
    o = _ORANGE
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" '
        f'xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><title>Lifejacket</title>'
        # the two front panels of the vest
        f'<rect x="3.5" y="7" width="6.2" height="13" rx="2" fill="none" '
        f'stroke="{o}" stroke-width="1.6"/>'
        f'<rect x="14.3" y="7" width="6.2" height="13" rx="2" fill="none" '
        f'stroke="{o}" stroke-width="1.6"/>'
        # the collar / neck opening
        f'<path d="M9 7 L12 4.5 L15 7" fill="none" stroke="{o}" '
        f'stroke-width="1.6" stroke-linejoin="round"/>'
        # the reflective strap across the middle
        f'<rect x="3" y="13.4" width="18" height="2.2" rx="0.6" fill="{o}"/>'
        f'</svg>'
    )


def _make_tray_icon():
    """Build the tray QIcon from the life-vest glyph (rendered SVG), with a dot
    fallback if SVG rendering isn't available."""
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QIcon, QPainter, QPixmap
    pm = QPixmap(64, 64)
    pm.fill(Qt.transparent)
    try:
        from PySide6.QtCore import QByteArray
        from PySide6.QtSvg import QSvgRenderer
        r = QSvgRenderer(QByteArray(_lifejacket_vest_svg(64).encode("utf-8")))
        p = QPainter(pm)
        r.render(p)
        p.end()
    except Exception:
        from PySide6.QtGui import QColor
        p = QPainter(pm)
        p.setBrush(QColor(_ORANGE))
        p.setPen(Qt.NoPen)
        p.drawEllipse(8, 8, 48, 48)
        p.end()
    return QIcon(pm)


def main(start_in_tray: bool = False) -> int:
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtWidgets import (
            QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QMenu,
            QPushButton, QScrollArea, QSystemTrayIcon, QVBoxLayout, QWidget,
        )
    except ImportError:
        sys.stderr.write(_missing_pyside_message())
        return 1

    try:
        from PySide6.QtSvgWidgets import QSvgWidget
        _have_svg = True
    except ImportError:
        _have_svg = False

    store = Store(default_home())
    store.init()

    class LifejacketWindow(QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("Claude Lifejacket")
            self.setMinimumSize(660, 660)
            self.resize(700, 720)
            from PySide6.QtCore import QSettings
            self._settings = QSettings("Jack", "ClaudeLifejacket")
            self._dark = self._settings.value("dark", False, type=bool)
            self.setStyleSheet(_qss(self._dark))
            self._candidate_boxes = []  # (QCheckBox, Candidate)
            self._tray = None
            self._build()
            self.refresh()

        def closeEvent(self, event):
            # Closing the window just tucks us into the tray (if there is one),
            # so auto-sync keeps quietly working. Quit from the tray menu to
            # actually exit.
            if self._tray is not None and self._tray.isVisible():
                event.ignore()
                self.hide()
                try:
                    self._tray.showMessage(
                        "Claude Lifejacket",
                        "Still here in your tray — keeping every session aware "
                        "of your projects.")
                except Exception:
                    pass
            else:
                event.accept()

        def _toggle_theme(self):
            self._dark = not self._dark
            try:
                self._settings.setValue("dark", self._dark)
            except Exception:
                pass
            self.setStyleSheet(_qss(self._dark))
            self._theme_btn.setText("Light" if self._dark else "Dark")

        # -- layout ------------------------------------------------------- #
        def _build(self):
            root = QVBoxLayout(self)
            root.setContentsMargins(22, 20, 22, 18)
            root.setSpacing(12)

            # Header
            header = QHBoxLayout()
            if _have_svg:
                logo = QSvgWidget()
                logo.load(_claude_logo_svg(30).encode("utf-8"))
                logo.setFixedSize(30, 30)
                header.addWidget(logo)
            titles = QVBoxLayout()
            titles.setSpacing(0)
            t = QLabel("Claude Lifejacket"); t.setObjectName("title")
            sub = QLabel("Every Claude session, aware of all your projects.")
            sub.setObjectName("sub")
            titles.addWidget(t); titles.addWidget(sub)
            header.addLayout(titles); header.addStretch(1)
            self._theme_btn = QPushButton("Light" if self._dark else "Dark")
            self._theme_btn.setObjectName("toggle")
            self._theme_btn.setCursor(Qt.PointingHandCursor)
            self._theme_btn.clicked.connect(self._toggle_theme)
            header.addWidget(self._theme_btn)
            root.addLayout(header)

            # Scroll body
            self._body = QVBoxLayout()
            self._body.setSpacing(8)
            container = QWidget(); container.setLayout(self._body)
            scroll = QScrollArea(); scroll.setWidgetResizable(True)
            scroll.setWidget(container)
            root.addWidget(scroll, 1)

            # Footer / actions
            self._status = QLabel(""); self._status.setObjectName("sub")
            root.addWidget(self._status)

            actions = QHBoxLayout()
            self._hook_btn = QPushButton("Auto-sync: …")
            self._hook_btn.clicked.connect(self._toggle_hook)
            log_btn = QPushButton("Open log")
            log_btn.clicked.connect(self._open_log)
            dash_btn = QPushButton("Open dashboard")
            dash_btn.clicked.connect(self._open_dashboard)
            sync_btn = QPushButton("Sync now"); sync_btn.setObjectName("primary")
            sync_btn.clicked.connect(self._sync)
            actions.addWidget(self._hook_btn)
            actions.addStretch(1)
            actions.addWidget(log_btn)
            actions.addWidget(dash_btn)
            actions.addWidget(sync_btn)
            root.addLayout(actions)

        def _clear_body(self):
            while self._body.count():
                item = self._body.takeAt(0)
                w = item.widget()
                if w:
                    w.deleteLater()
            self._candidate_boxes = []

        def _section(self, text):
            lbl = QLabel(text); lbl.setObjectName("section")
            self._body.addWidget(lbl)

        def _card(self):
            f = QFrame(); f.setObjectName("card")
            lay = QVBoxLayout(f); lay.setContentsMargins(14, 10, 14, 10); lay.setSpacing(2)
            return f, lay

        # -- data --------------------------------------------------------- #
        def refresh(self):
            snap = build_snapshot(store)
            self._clear_body()

            # Surfaces
            self._section("CLAUDE MEMORY SURFACES")
            if snap.surfaces:
                for sv in snap.surfaces:
                    card, lay = self._card()
                    row = QHBoxLayout()
                    dot = QLabel("●")
                    dot.setStyleSheet(f"color:{_STATE_COLOUR.get(sv.state, _IDLE)};")
                    name = QLabel(sv.label)
                    state = QLabel(sv.detail)
                    state.setStyleSheet(f"color:{_STATE_COLOUR.get(sv.state, _IDLE)};")
                    row.addWidget(dot); row.addWidget(name, 1); row.addWidget(state)
                    holder = QWidget(); holder.setLayout(row)
                    lay.addWidget(holder)
                    self._body.addWidget(card)
            else:
                self._body.addWidget(QLabel("  No Claude memory surfaces found yet."))

            # Logbook
            self._section(f"IN YOUR LOGBOOK · {len(snap.projects)}")
            if snap.projects:
                for p in snap.projects:
                    card, lay = self._card()
                    row = QHBoxLayout()
                    label = p.name + (f"   ({p.status})" if p.status else "")
                    row.addWidget(QLabel(label), 1)
                    rm = QPushButton("Remove")
                    rm.clicked.connect(lambda _=False, pid=p.id: self._remove(pid))
                    row.addWidget(rm)
                    holder = QWidget(); holder.setLayout(row); lay.addWidget(holder)
                    self._body.addWidget(card)
            else:
                self._body.addWidget(QLabel("  Nothing yet — add some from below."))

            # Discovered candidates
            self._section(f"DISCOVERED · {len(snap.candidates)} not yet added")
            if snap.candidates:
                for c in snap.candidates:
                    cb = QCheckBox(f"{c.name}   ({c.source})")
                    self._candidate_boxes.append((cb, c))
                    self._body.addWidget(cb)
            else:
                self._body.addWidget(QLabel("  Nothing new to add right now."))

            # Recent activity — so you can see syncing is working.
            self._section("RECENT ACTIVITY")
            if snap.recent:
                card, lay = self._card()
                for line in reversed(snap.recent):  # newest first
                    row = QLabel(line)
                    row.setStyleSheet(
                        f"color:{_MUTED}; font-family:'Cascadia Code',Consolas,"
                        "monospace; font-size:11px;")
                    lay.addWidget(row)
                self._body.addWidget(card)
            else:
                self._body.addWidget(QLabel("  No syncs yet — hit Sync now."))

            self._body.addStretch(1)

            self._hook_btn.setText(
                "Auto-sync: On" if snap.hook_on else "Auto-sync: Off")

        # -- actions ------------------------------------------------------ #
        def _sync(self):
            chosen = [c for cb, c in self._candidate_boxes if cb.isChecked()]
            added = add_candidates(store, chosen) if chosen else 0
            reports = do_sync(store)
            changed = sum(1 for r in reports if r.result.changed)
            bits = []
            if added:
                bits.append(f"added {added} project(s)")
            bits.append(f"synced {changed} surface(s)" if changed
                        else "everything already up to date")
            self._status.setText("  " + ", ".join(bits) + ". ")
            self.refresh()

        def _toggle_hook(self):
            now_on = self._hook_btn.text().endswith("On")
            res = set_autosync(not now_on)
            self._status.setText("  " + res.message)
            self.refresh()

        def _remove(self, pid):
            store.remove(pid)
            self.refresh()

        def _open_dashboard(self):
            out = write_dashboard(store)
            try:
                webbrowser.open(out.as_uri())
            except Exception:
                pass
            self._status.setText(f"  Dashboard written to {out}")

        def _open_log(self):
            p = store.activity_log_path
            if not p.exists():
                store.log_event("(log opened before any sync)")
            try:
                webbrowser.open(p.as_uri())
            except Exception:
                pass
            self._status.setText(f"  Activity log: {p}")

    app = QApplication.instance() or QApplication(sys.argv)

    # Single-instance guard: if Lifejacket is already running, don't open a second
    # window — just bow out quietly. (So a second double-click does nothing.)
    try:
        from PySide6.QtCore import QSharedMemory
        _lock = QSharedMemory("ClaudeLifejacketSingleInstance")
        if not _lock.create(1):
            return 0
        app._lifejacket_lock = _lock   # keep it alive for the process lifetime
    except Exception:
        pass

    win = LifejacketWindow()

    if QSystemTrayIcon.isSystemTrayAvailable():
        from PySide6.QtGui import QAction
        app.setQuitOnLastWindowClosed(False)   # closing the window hides to tray

        def _show():
            win.showNormal(); win.raise_(); win.activateWindow()

        tray = QSystemTrayIcon(_make_tray_icon())
        tray.setToolTip("Claude Lifejacket")
        menu = QMenu()
        a_open = QAction("Open Lifejacket", menu); a_open.triggered.connect(_show)
        a_sync = QAction("Sync now", menu); a_sync.triggered.connect(win._sync)
        a_dash = QAction("Open dashboard", menu)
        a_dash.triggered.connect(win._open_dashboard)
        a_quit = QAction("Quit", menu); a_quit.triggered.connect(app.quit)
        for a in (a_open, a_sync, a_dash):
            menu.addAction(a)

        # Start with Windows (per-user, no admin). Only meaningful for the
        # packaged .exe, so it's greyed out when running from source.
        a_startup = QAction("Run at startup", menu)
        a_startup.setCheckable(True)
        a_startup.setChecked(startup.is_enabled())
        a_startup.setEnabled(startup.is_frozen())

        def _toggle_startup(checked: bool) -> None:
            ok = startup.enable() if checked else startup.disable()
            if not ok:                       # registry wrote nothing — reflect reality
                a_startup.setChecked(startup.is_enabled())
        a_startup.toggled.connect(_toggle_startup)
        menu.addAction(a_startup)

        menu.addSeparator(); menu.addAction(a_quit)
        tray.setContextMenu(menu)
        tray.activated.connect(
            lambda reason: _show() if reason == QSystemTrayIcon.DoubleClick else None)
        tray.show()
        win._tray = tray
        if not start_in_tray:
            win.show()
    else:
        win.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
