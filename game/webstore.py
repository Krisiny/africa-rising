"""Browser helpers for the web version (on a normal computer they do nothing).

Keeps savegame.json and game_log.csv in the browser's storage, and helps with
touch screens: is this a phone or tablet, is it held upright, fullscreen.

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


def download(path: Path) -> bool:
    """Let the browser download the file (web version only). True if it worked."""
    if not WEB:
        return False
    try:
        import json
        import platform
        text = Path(path).read_text(encoding="utf-8-sig")
        script = ("(function(name, text) {"
                  " const blob = new Blob(['\ufeff' + text], {type: 'text/csv'});"
                  " const a = document.createElement('a');"
                  " a.href = URL.createObjectURL(blob); a.download = name;"
                  " document.body.appendChild(a); a.click(); a.remove();"
                  "})(%s, %s)" % (json.dumps(Path(path).name), json.dumps(text)))
        platform.window.eval(script)
        return True
    except Exception:
        return False


def _run_js(script: str):
    """Run a bit of JavaScript in the page. Returns its result, or None."""
    if not WEB:
        return None
    try:
        import platform
        return platform.window.eval(script)
    except Exception:
        return None


def touch_screen() -> bool:
    """True on phones and tablets (where the main pointer is a finger)."""
    return bool(_run_js("window.matchMedia('(pointer: coarse)').matches"))


def held_upright() -> bool:
    """True if the browser window is taller than wide (a phone held upright)."""
    return bool(_run_js("window.innerHeight > window.innerWidth * 1.05"))


def toggle_fullscreen() -> None:
    _run_js("(function () { var d = document, e = d.documentElement;"
            " if (d.fullscreenElement || d.webkitFullscreenElement) {"
            "   (d.exitFullscreen || d.webkitExitFullscreen).call(d); }"
            " else { (e.requestFullscreen || e.webkitRequestFullscreen).call(e); } })()")


def setup_touch() -> None:
    """Stop the browser from zooming or scrolling the page when the game is touched."""
    _run_js("document.body.style.touchAction = 'none';"
            " document.querySelectorAll('canvas').forEach(function (c) { c.style.touchAction = 'none'; });")
