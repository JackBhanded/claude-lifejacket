"""Entry point PyInstaller bundles into 'Claude Lifejacket.exe'.

It just launches the GUI. Kept at the repo root (with ``--paths src`` at build
time) so PyInstaller can find the ``claude_lifejacket`` package.
"""

from claude_lifejacket.app import main

if __name__ == "__main__":
    raise SystemExit(main())
