"""Enable ``python -m claude_lifejacket ...``.

The SessionStart hook invokes the package this way (with the absolute Python
that installed it) so it works even when the ``lifejacket`` launcher script
isn't on PATH.
"""

from .cli import main

if __name__ == "__main__":
    raise SystemExit(main())
