"""Keep savegame.json and game_log.csv in the browser's storage (web version only).

In the browser, files written by the game disappear when the page is reloaded.
These helpers copy them into the browser's localStorage and back, so resume
works there too. On a normal computer (not in a browser) they do nothing.
"""

from __future__ import annotations

import sys
from pathlib import Path

WEB = sys.platform == "emscripten"


def _storage():
    if not WEB:
        return None
    try:
        import platform          # in the browser this module gives access to the page
        return platform.window.localStorage
    except Exception:
        return None


def restore(path: Path) -> None:
    """Browser storage -> file (call before reading the file)."""
    store = _storage()
    if store is None:
        return
    try:
        text = store.getItem(Path(path).name)
        if text:
            Path(path).write_text(str(text), encoding="utf-8")
    except Exception:
        pass


def keep(path: Path) -> None:
    """File -> browser storage (call after writing or deleting the file)."""
    store = _storage()
    if store is None:
        return
    try:
        path = Path(path)
        if path.exists():
            store.setItem(path.name, path.read_text(encoding="utf-8"))
        else:
            store.removeItem(path.name)
    except Exception:
        pass
