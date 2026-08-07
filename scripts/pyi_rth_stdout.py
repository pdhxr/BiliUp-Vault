"""PyInstaller runtime hook: redirect stdout/stderr when not attached to a console.

uvicorn's ColourizedFormatter calls ``sys.stdout.isatty()`` at import time.
In a ``--windowed`` build, ``sys.stdout`` and ``sys.stderr`` are ``None`` and
that call raises ``AttributeError``. Redirecting to ``os.devnull`` is a safe
no-op when the streams are already attached, so this hook fixes the packaged
EXE without affecting console/dev-mode behaviour.
"""

import os
import sys

if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")
