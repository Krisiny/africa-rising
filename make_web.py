"""Build the web version of the game into the docs/ folder.

    python make_web.py

1. Checks content.xlsx (stops if it has problems) and saves it as content.json,
   because the browser can't read Excel files.
2. Copies only what the game needs into build_web/africa-rising/.
3. Packs it with pygbag (pip install pygbag) into docs/: index.html plus the
   game file. Publish docs/ (for example with GitHub Pages) and share the link.

Run it again after every change to the game or to content.xlsx.
"""

import json
import shutil
import subprocess
import sys
from pathlib import Path

import config
from game.content import ContentError, load_content

ROOT = Path(__file__).resolve().parent
STAGE = ROOT / "build_web" / "africa-rising"
DOCS = ROOT / "docs"

WEB_MAIN = '''"""Web entry point (written by make_web.py)."""
import asyncio
import pygame  # pygbag loads the packages it sees imported here, so pygame must be named

from game.app import run_web

asyncio.run(run_web())
'''


def main() -> int:
    try:
        content = load_content(ROOT / config.CONTENT_FILE)
    except ContentError as err:
        print(f"content.xlsx has {len(err.problems)} problem(s). Run python main.py --check and fix them first.")
        return 1

    print("Copying the game files...")
    shutil.rmtree(STAGE.parent, ignore_errors=True)
    STAGE.mkdir(parents=True)
    shutil.copy2(ROOT / "config.py", STAGE)
    shutil.copytree(ROOT / "game", STAGE / "game", ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(ROOT / "assets", STAGE / "assets", ignore=shutil.ignore_patterns("*.txt"))
    (STAGE / "content.json").write_text(json.dumps(content.to_json(), ensure_ascii=False, indent=1),
                                        encoding="utf-8")
    (STAGE / "main.py").write_text(WEB_MAIN, encoding="utf-8")

    print("Packing with pygbag (the first time this downloads its web template)...")
    done = subprocess.run([sys.executable, "-m", "pygbag", "--build", "--title", config.GAME_TITLE,
                           str(STAGE)])
    built = STAGE / "build" / "web"
    if done.returncode != 0 or not (built / "index.html").exists():
        print("pygbag failed; see the messages above.")
        return 1

    shutil.rmtree(DOCS, ignore_errors=True)
    shutil.copytree(built, DOCS)
    (DOCS / ".nojekyll").write_text("", encoding="utf-8")   # GitHub Pages: serve files as they are
    print(f"Done: the web version is in {DOCS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
