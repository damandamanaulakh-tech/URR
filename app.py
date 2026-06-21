"""Render entrypoint. Render runs: ``python app.py``.

Keeps it dead simple for a non-technical owner: no install step needed, because
the engine is stdlib-only. Just adds ``src`` to the path and starts the web
service (binds to 0.0.0.0:$PORT as Render expects).
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

from sourceborn.server import main  # noqa: E402

if __name__ == "__main__":
    main()
