"""Smoke tests for app.py that run WITHOUT a display or PySide6 installed.

The Qt imports live inside ``main()`` on purpose, so importing the module is
always safe. The real app behaviour is covered by test_appmodel.py.
"""

from __future__ import annotations

from claude_lifejacket.app import _missing_pyside_message, main


def test_main_is_callable():
    assert callable(main)


def test_missing_pyside_message_is_helpful():
    msg = _missing_pyside_message()
    assert "PySide6" in msg
    assert "dashboard" in msg  # points to the no-GUI fallback


def test_module_imports_without_qt():
    # Importing app must not require PySide6 (it's imported lazily in main()).
    import claude_lifejacket.app as app
    assert hasattr(app, "main")
