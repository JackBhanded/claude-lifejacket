"""Tests for dashboard.py + the `dashboard` CLI command."""

from __future__ import annotations

import pytest

from claude_lifejacket.cli import main
from claude_lifejacket.dashboard import render_dashboard_html, write_dashboard
from claude_lifejacket.store import Project, Store
from claude_lifejacket.sync import sync_all


@pytest.fixture
def env(tmp_path, monkeypatch):
    lj = tmp_path / "lj"
    ch = tmp_path / "dot-claude"
    ch.mkdir()
    monkeypatch.setenv("LIFEJACKET_HOME", str(lj))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(ch))
    return {"lj": lj, "ch": ch}


def populated(tmp_path) -> Store:
    s = Store(home=tmp_path / "lj")
    s.init()
    s.add(Project.create("Claude Meter", status="shipped",
                          repo="github.com/JackBhanded/claude-meter",
                          focus="usage logging next"))
    s.add(Project.create("Claude Lifejacket", status="building"))
    return s


def test_render_contains_projects_and_digest(tmp_path):
    s = populated(tmp_path)
    htmlstr = render_dashboard_html(s)
    assert "<!DOCTYPE html>" in htmlstr
    assert "Claude Meter" in htmlstr
    assert "Claude Lifejacket" in htmlstr
    # The verbatim digest section is present.
    assert "What every session is reading" in htmlstr
    assert "usage logging next" in htmlstr


def test_render_includes_real_claude_logo(tmp_path):
    s = populated(tmp_path)
    htmlstr = render_dashboard_html(s)
    # The official logo's signature path start + Claude orange.
    assert "M4.709 15.955" in htmlstr
    assert "#D97757" in htmlstr
    assert "<title>Claude</title>" in htmlstr


def test_render_escapes_html(tmp_path):
    s = Store(home=tmp_path / "lj")
    s.init()
    s.add(Project.create("Evil", focus="<script>alert(1)</script>"))
    htmlstr = render_dashboard_html(s)
    assert "<script>alert(1)</script>" not in htmlstr
    assert "&lt;script&gt;" in htmlstr


def test_empty_logbook_renders(tmp_path):
    s = Store(home=tmp_path / "lj")
    s.init()
    htmlstr = render_dashboard_html(s)
    assert "logbook is empty" in htmlstr.lower()


def test_surface_status_light_reflects_sync(env):
    s = Store(home=env["lj"])
    s.init()
    s.add(Project.create("Meter", status="shipped"))
    # Before any sync, the discovered surface reads as "Never synced".
    assert "Never synced" in render_dashboard_html(s)
    # After a sync, it flips to "In sync".
    sync_all(s)
    assert "In sync" in render_dashboard_html(s)


def test_write_dashboard_creates_file_in_store(tmp_path):
    s = populated(tmp_path)
    out = write_dashboard(s)
    assert out.exists()
    assert out.parent == s.home  # lives in the store, not on the Desktop
    assert out.name == "dashboard.html"


def test_cli_dashboard_no_open(env, capsys, monkeypatch):
    # Guard: make sure we never actually launch a browser in tests.
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: pytest.fail(
        "should not open a browser with --no-open"))
    main(["init"])
    main(["add", "Meter", "--status", "shipped"])
    capsys.readouterr()
    assert main(["dashboard", "--no-open"]) == 0
    out = capsys.readouterr().out
    assert "dashboard is ready" in out.lower()
    assert (env["lj"] / "dashboard.html").exists()


def test_cli_dashboard_reflects_synced_state(env, capsys, monkeypatch):
    import webbrowser
    monkeypatch.setattr(webbrowser, "open", lambda *a, **k: None)
    main(["init"])
    main(["add", "Meter", "--status", "shipped"])
    main(["sync"])
    capsys.readouterr()
    main(["dashboard", "--no-open"])
    html_text = (env["lj"] / "dashboard.html").read_text(encoding="utf-8")
    assert "In sync" in html_text  # the green status light wording
