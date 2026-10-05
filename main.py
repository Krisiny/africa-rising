"""Africa Rising: start the game, or check the content and the rules.

    python main.py              play (fullscreen)
    python main.py --windowed   play in a window
    python main.py --check      check content.xlsx and list every problem
    python main.py --simulate   play 200 random games without a window to test the rules
"""

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")

import argparse
import importlib
import sys
from pathlib import Path

import config
from game.content import ContentError, load_content

# The game folder. In the Windows .exe (see make_exe.py) it is the folder of the .exe.
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent


def load_or_report(path: Path):
    """Load the content, or print every problem and return None."""
    try:
        return load_content(path)
    except ContentError as err:
        print(f"Found {len(err.problems)} problem(s) in {path.name}:")
        for number, problem in enumerate(err.problems, start=1):
            print(f"{number}. {problem}")
        return None


def import_run(module: str):
    """Import run() from a game module, with a clear note if that file doesn't exist yet."""
    try:
        return importlib.import_module(module).run
    except ModuleNotFoundError as err:
        if err.name != module:
            raise  # something else is missing: show the real error
        print(f"{module.replace('.', '/')}.py is missing, so this part of the game can't start.")
        sys.exit(1)


def main() -> int:
    parser = argparse.ArgumentParser(description="Africa Rising, a classroom board game.")
    parser.add_argument("--windowed", action="store_true", help="play in a window instead of fullscreen")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="check content.xlsx and list any problems")
    mode.add_argument("--simulate", action="store_true", help="play 200 random games headless to test the rules")
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="replace")  # never crash on text from the xlsx
    content_path = ROOT / config.CONTENT_FILE

    if args.check or args.simulate:
        content = load_or_report(content_path)
        if content is None:
            return 1
        if args.check:
            print(f"{content_path.name} is OK: {len(content.countries)} countries, "
                  f"{len(content.events)} events, {len(content.results)} results.")
            return 0
        return 0 if import_run("game.simulate")(content) else 1

    import_run("game.app")(windowed=args.windowed)
    return 0


if __name__ == "__main__":
    sys.exit(main())
