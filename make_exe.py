"""Build the Windows version: a folder (and a zip) that runs without installing Python.

    python -m pip install pyinstaller
    python make_exe.py

Result: dist/Africa Rising/ with "Africa Rising.exe", content.xlsx and assets/,
plus dist/Africa Rising (Windows).zip to put on a USB stick or send around.
content.xlsx and assets/ stay next to the .exe, so they can still be edited or
swapped without rebuilding. Settings in config.py need a rebuild.
"""

import shutil
import subprocess
import sys
from pathlib import Path

import config
from game.content import ContentError, load_content

ROOT = Path(__file__).resolve().parent
NAME = "Africa Rising"
WORK = ROOT / "build_exe"
DIST = ROOT / "dist"


def main() -> int:
    try:
        load_content(ROOT / config.CONTENT_FILE)
    except ContentError as err:
        print(f"content.xlsx has {len(err.problems)} problem(s). Run python main.py --check and fix them first.")
        return 1

    print("Packing with PyInstaller (takes a minute)...")
    shutil.rmtree(DIST, ignore_errors=True)
    done = subprocess.run([
        sys.executable, "-m", "PyInstaller", str(ROOT / "main.py"),
        "--name", NAME,
        "--windowed",                     # no black console window
        "--noconfirm", "--clean",
        "--hidden-import", "game.app",    # main.py imports these only when needed
        "--hidden-import", "game.simulate",
        "--exclude-module", "pygbag",
        "--distpath", str(DIST),
        "--workpath", str(WORK),
        "--specpath", str(WORK),
    ])
    folder = DIST / NAME
    if done.returncode != 0 or not (folder / f"{NAME}.exe").exists():
        print("PyInstaller failed; see the messages above.")
        return 1

    # Files the group edits or swaps live next to the .exe, not inside it.
    shutil.copy2(ROOT / config.CONTENT_FILE, folder)
    shutil.copytree(ROOT / "assets", folder / "assets")
    (folder / "How to start.txt").write_text(
        f"Double-click \"{NAME}.exe\" to play.\r\n"
        "If Windows says \"Windows protected your PC\", click \"More info\" and then \"Run anyway\".\r\n"
        "Press H in the game to see the controls.\r\n", encoding="utf-8")

    zip_path = shutil.make_archive(str(DIST / f"{NAME} (Windows)"), "zip", DIST, NAME)
    print(f"Done: {folder}")
    print(f"Zip:  {zip_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
