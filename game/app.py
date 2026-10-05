"""The game window: scenes, keys, timer and the main loop.

Scenes, in the order a game goes through them:
  resume -> title -> howto -> mode -> (singleplayer: country ->) sound -> turn -> rolling
  -> moving -> landed -> event -> reveal -> score -> turn (next team) ... -> final -> credits
  -> title
plus "error" when content.xlsx has a problem and "crash" as a last-resort net.

All timing goes through update(dt), so tests can drive the App without a window.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")

import asyncio
import json
import random
import sys
import time
import traceback
from pathlib import Path

import pygame

import config
from config import TEXT
from game import screens, ui
from game.audio import Audio, pre_init
from game.board import BoardLayout
from game.content import ContentError, load_content
from game.state import GameState, delete_save, load_game, persist
from game.webstore import WEB, download, keep, restore

# The game folder. In the Windows .exe (see make_exe.py) it is the folder of the .exe.
ROOT = (Path(sys.executable).parent if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parent.parent)

INPUT_LOCK = 0.4          # seconds to ignore keys after every screen change
DOUBLE_PRESS = 2.0        # seconds to press E or Esc a second time
TOAST_TIME = 2.0
TUMBLE = 0.8              # die tumble (at most 1 s)
HOP = 0.4                 # per tile: the token moves slowly from tile to tile
LAND_HOLD = 2.0           # the landing tile is green this long before the question opens
PICK_HOLD = 1.0           # singleplayer: the chosen country lights up this long
FINAL_FILL = 6.0          # singleplayer: the progress bar fills this long (slow and smooth)
COUNT_UP = 0.8            # reveal number
SCORE_ANIM = 0.7          # scoreboard number
SCORE_HOLD = 0.3          # short pause before the next team
MAX_DT = 0.25             # a very slow frame never jumps the game ahead more than this

GAME_SCENES = ("turn", "rolling", "moving", "landed", "event", "reveal", "score")
BOARD_SCENES = ("turn", "rolling", "moving", "landed", "score")
DIGITS = {getattr(pygame, f"K_{n}"): n for n in range(1, 10)}
DIGITS.update({getattr(pygame, f"K_KP{n}"): n for n in range(1, 10)})
CONTINUE_KEYS = (pygame.K_SPACE, pygame.K_RETURN, pygame.K_KP_ENTER)


class App:
    def __init__(self, windowed: bool, headless: bool = False,
                 content_path=None, save_path=None, log_path=None):
        default_content = ROOT / ("content.json" if WEB else config.CONTENT_FILE)
        self.content_path = Path(content_path) if content_path else default_content
        self.save_path = Path(save_path) if save_path else ROOT / "savegame.json"
        self.log_path = Path(log_path) if log_path else ROOT / "game_log.csv"
        self.headless = headless

        pre_init()
        pygame.init()
        self.screen = pygame.Surface((ui.W, ui.H)) if headless else _open_display(windowed)
        ui.init(ROOT / "assets")
        self.audio = Audio(ROOT / "assets", config.SOUND_ON, config.MUSIC_VOLUME)

        self.running = True
        self.scene = ""
        self.scene_time = 0.0
        self.lock = 0.0
        self.toast, self.toast_left = "", 0.0
        self.esc_left = self.e_left = 0.0
        self.show_help = False
        self.show_card = config.SHOW_COUNTRY_CARD

        self.content = None           # what the current game uses (one country in singleplayer)
        self.all_content = None       # everything in content.xlsx
        self.saved_content = None
        self.player: str | None = None   # singleplayer: the chosen country code
        self.picked_at = 0.0
        self.problems = []
        self.state: GameState | None = None
        self.saved: GameState | None = None
        self.layout = None
        self.shown_scores: dict[str, float] = {}
        self.buttons = []
        self.mover = None
        self.die_face = 1
        self.timer_left = 0.0
        self.paused = False
        self.record = None
        self.counted = False
        self.score_from = 0.0
        self.confetti = ui.Confetti([])
        self.backdrop = None

        try:
            self.content = self.all_content = load_content(self.content_path)
        except ContentError as err:
            self.problems = err.problems
            self.set_scene("error")
            return
        self.layout = BoardLayout(self.content.n_tiles)
        restore(self.save_path)
        restore(self.log_path)
        self.saved = self._load_saved()
        self.set_scene("resume" if self.saved else "title")

    # ----- Small helpers ------------------------------------------------------------

    def set_scene(self, name: str) -> None:
        self.scene = name
        self.scene_time = 0.0
        self.backdrop = None          # redrawn once for the new screen (see screens._backdrop)
        self.lock = INPUT_LOCK
        if name in ("resume", "title", "howto", "mode", "country", "sound", "final", "credits"):
            self.audio.music("title")
        elif name in GAME_SCENES:
            self.audio.music(self.turn_team())
        else:
            self.audio.music(None)

    def input_ready(self) -> bool:
        return self.lock <= 0

    def turn_team(self) -> str:
        """The team the board is about: the one that just chose, or whose turn it is."""
        if self.scene in ("reveal", "score") and self.record is not None:
            return self.record.code
        return self.state.current_team

    def single(self) -> bool:
        """True while a singleplayer game is on (one country)."""
        return self.state is not None and len(self.state.codes) == 1

    def _load_saved(self) -> GameState | None:
        """The unfinished game in savegame.json (multiplayer or singleplayer), or None."""
        self.saved_content = self.all_content
        state = load_game(self.save_path, self.all_content)
        if state is not None:
            return state
        try:          # a singleplayer save lists just one country
            codes = json.loads(self.save_path.read_text(encoding="utf-8"))["codes"]
        except Exception:
            return None
        if isinstance(codes, list) and len(codes) == 1 and codes[0] in self.all_content.codes:
            self.saved_content = self.all_content.only(codes[0])
            return load_game(self.save_path, self.saved_content)
        return None

    def show_toast(self, message: str) -> None:
        self.toast, self.toast_left = message, TOAST_TIME

    def save(self) -> None:
        if self.state is not None:
            persist(self.state, self.save_path, self.log_path)
            keep(self.save_path)
            keep(self.log_path)

    def hop_position(self) -> tuple[float, float]:
        """Pixel position of the hopping token, with a small arc per hop."""
        m = self.mover
        hop = ui.secs(HOP)
        step = min(len(m["path"]) - 1e-6, self.scene_time / hop)
        index = int(step)
        frac = step - index
        before = m["start"] if index == 0 else m["path"][index - 1]
        a = self.layout.hop_point(before)
        b = self.layout.hop_point(m["path"][index])
        x = a[0] + (b[0] - a[0]) * frac
        y = a[1] + (b[1] - a[1]) * frac - 60 * (4 * frac * (1 - frac))
        return x, y

    def count_value(self) -> int:
        """The reveal number while it counts up."""
        if self.counted:
            return self.record.delta
        t = ui.ease_out(self.scene_time / ui.secs(COUNT_UP))
        return round(self.record.delta * t)

    # ----- Moving between scenes --------------------------------------------------------

    def new_game(self) -> None:
        delete_save(self.save_path)
        if self.player:       # singleplayer: only the chosen country, more rounds
            self.content = self.all_content.only(self.player)
            self.state = GameState(self.content, config.SINGLE_ROUNDS)
        else:
            self.content = self.all_content
            self.state = GameState(self.content, config.ROUNDS)
        self.shown_scores = dict(self.state.scores)
        self.save()
        self.set_scene("turn")

    def resume(self) -> None:
        self.content = self.saved_content
        self.state, self.saved = self.saved, None
        self.shown_scores = dict(self.state.scores)
        if self.state.phase == "choose":
            self.open_event()
        elif self.state.phase == "over":
            self.go_final()
        else:
            self.set_scene("turn")

    def start_roll(self, value: int, real_die: bool) -> None:
        code = self.state.current_team
        start = self.state.positions[code]
        path = self.state.roll(value)
        self.save()
        self.mover = {"code": code, "start": start, "path": path, "steps": 0}
        self.die_face = value
        if real_die:
            self.set_scene("moving")
        else:
            self.audio.play("dice")
            self.die_face = random.randint(1, 6)
            self.set_scene("rolling")

    def open_event(self) -> None:
        self.timer_left = float(config.TIMER_SECONDS)
        self.paused = False
        self.set_scene("event")

    def choose(self, option: int) -> None:
        self.record = self.state.choose(option)
        self.save()
        self.counted = self.record.delta == 0
        if self.record.delta > 0:
            self.audio.play("good")
        elif self.record.delta < 0:
            self.audio.play("bad")
        self.set_scene("reveal")
        if self.counted:
            self.finish_count()

    def finish_count(self) -> None:
        self.counted = True
        if self.record.best:
            self.audio.play("best")

    def go_score(self) -> None:
        self.score_from = self.shown_scores[self.record.code]
        self.set_scene("score")

    def after_score(self) -> None:
        self.shown_scores = dict(self.state.scores)
        if self.state.phase == "over":
            self.go_final()
        else:
            self.set_scene("turn")

    def undo(self) -> None:
        if self.state.undo() is None:
            return
        self.save()
        self.shown_scores = dict(self.state.scores)
        self.open_event()

    def go_final(self) -> None:
        if self.state.phase == "over":
            self.state.finish()              # all rounds played
        elif self.state.phase != "finished":
            self.state.end_now()             # E pressed twice
        self.save()
        self.shown_scores = dict(self.state.scores)
        colors = [self.content.country(c).color for c in self.state.winners()]
        self.confetti = ui.Confetti(colors)
        if self.single() and self.state.scores[self.state.codes[0]] <= 0:
            self.audio.play("bad")            # no party for a loss
        else:
            self.confetti.burst((ui.W // 2, 260))
            self.audio.play("win")
        self.set_scene("final")

    def back_to_start(self) -> None:
        """After the credits (or a quit on the web): ready for a new game."""
        self.state = None
        self.player = None
        self.content = self.all_content

    def quit(self) -> None:
        if self.state is not None and self.state.phase != "finished":
            self.save()
        if WEB:      # a web page can't close its own tab: say it's safe to close it
            self.back_to_start()
            self.toast_left = 0.0         # hide "Press Esc again to quit"
            self.set_scene("closed")
            return
        self.running = False

    # ----- Input ---------------------------------------------------------------------

    def handle(self, event) -> None:
        if event.type == pygame.QUIT:
            self.quit()
            return
        if event.type not in (pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
            return
        if self.lock > 0:
            return
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1 and self.scene == "event":
                for i, button in enumerate(self.buttons):
                    if button.hit(event.pos):
                        self.choose(i)
                        return
            return

        key = event.key
        if self._global_key(key):
            return
        handler = getattr(self, f"_key_{self.scene}", None)
        if handler is not None:
            handler(key)

    def _global_key(self, key) -> bool:
        """Keys that work on every screen. Returns True if the key was used."""
        if key == pygame.K_ESCAPE:
            if self.scene in ("final", "credits", "error", "crash") or self.esc_left > 0:
                self.quit()
            else:
                self.esc_left = DOUBLE_PRESS
                self.show_toast(TEXT["press_esc_again"])
            return True
        if key == pygame.K_e and self.scene in GAME_SCENES:
            if self.e_left > 0:
                self.e_left = 0
                self.go_final()
            else:
                self.e_left = DOUBLE_PRESS
                self.show_toast(TEXT["press_e_again"])
            return True
        if key == pygame.K_m:
            muted = self.audio.toggle_mute()
            self.show_toast(TEXT["sound_off"] if muted else TEXT["sound_on"])
            return True
        if key == pygame.K_F11:
            if not self.headless:
                try:
                    pygame.display.toggle_fullscreen()
                    if not WEB and not pygame.display.is_fullscreen():
                        _fit_window(_display_index())
                except pygame.error:
                    pass
            return True
        if key == pygame.K_h:
            self.show_help = not self.show_help
            return True
        if key == pygame.K_c:
            self.show_card = not self.show_card
            return True
        if key in (pygame.K_u, pygame.K_BACKSPACE):
            if self.scene in ("turn", "reveal", "score") and self.state.can_undo:
                self.undo()
            return True
        return False

    def _key_resume(self, key) -> None:
        if key == pygame.K_r:
            self.resume()
        elif key == pygame.K_n:
            self.saved = None
            delete_save(self.save_path)
            keep(self.save_path)
            self.set_scene("title")

    def _key_closed(self, key) -> None:
        if key == pygame.K_r:
            self.saved = self._load_saved() if self.all_content else None
            self.set_scene("resume" if self.saved else "title")

    def _key_title(self, key) -> None:
        if key in CONTINUE_KEYS:
            self.set_scene("howto")

    def _key_howto(self, key) -> None:
        if key in CONTINUE_KEYS:
            self.set_scene("mode")

    def _key_mode(self, key) -> None:
        if DIGITS.get(key) == 1:          # singleplayer: choose a country first
            self.player = None
            self.set_scene("country")
        elif DIGITS.get(key) == 2:        # multiplayer: the game as before
            self.player = None
            self.set_scene("sound")

    def _key_country(self, key) -> None:
        codes = self.all_content.codes
        number = DIGITS.get(key, 0)
        if self.player is None and 1 <= number <= len(codes):
            self.player = codes[number - 1]
            self.picked_at = self.scene_time
            self.backdrop = None              # redraw with the chosen card lit up
            self.audio.play("select")

    def _key_sound(self, key) -> None:
        if key in CONTINUE_KEYS:
            self.new_game()

    def _key_turn(self, key) -> None:
        if key in CONTINUE_KEYS:
            self.start_roll(random.randint(1, 6), real_die=False)
        elif DIGITS.get(key, 0) in range(1, 7):
            self.start_roll(DIGITS[key], real_die=True)

    def _key_rolling(self, key) -> None:
        if key in CONTINUE_KEYS:
            self.open_event()

    _key_moving = _key_landed = _key_rolling     # Space skips to the question

    def _key_event(self, key) -> None:
        if DIGITS.get(key, 0) in (1, 2, 3):
            self.choose(DIGITS[key] - 1)
        elif key == pygame.K_p and config.TIMER_SECONDS > 0:
            self.paused = not self.paused

    def _key_reveal(self, key) -> None:
        if key in CONTINUE_KEYS:
            if self.counted:
                self.go_score()
            else:
                self.finish_count()

    def _key_score(self, key) -> None:
        if key in CONTINUE_KEYS:
            self.after_score()

    def _key_final(self, key) -> None:
        if key == pygame.K_l and WEB:
            if self.log_path.exists() and download(self.log_path):
                self.show_toast(TEXT["log_downloaded"])
            else:
                self.show_toast(TEXT["log_missing"])
        elif key in CONTINUE_KEYS:
            self.set_scene("credits")

    def _key_credits(self, key) -> None:
        if key in CONTINUE_KEYS:
            self.back_to_start()
            self.set_scene("title")

    # ----- Time -------------------------------------------------------------------------

    def update(self, dt: float) -> None:
        self.scene_time += dt
        self.lock = max(0.0, self.lock - dt)
        self.toast_left = max(0.0, self.toast_left - dt)
        self.esc_left = max(0.0, self.esc_left - dt)
        self.e_left = max(0.0, self.e_left - dt)
        self.audio.update(dt)                 # next background song when one ends
        handler = getattr(self, f"_update_{self.scene}", None)
        if handler is not None:
            handler(dt)

    def _update_rolling(self, dt) -> None:
        if self.scene_time >= ui.secs(TUMBLE):
            self.die_face = self.state.last_roll
            self.set_scene("moving")
        elif int(self.scene_time / 0.08) != int((self.scene_time - dt) / 0.08):
            self.die_face = random.choice([f for f in range(1, 7) if f != self.die_face])

    def _update_moving(self, dt) -> None:
        hops = int(self.scene_time / ui.secs(HOP))
        if hops > self.mover["steps"] and self.mover["steps"] < len(self.mover["path"]):
            self.mover["steps"] = min(hops, len(self.mover["path"]))
            self.audio.play("step")
        if self.scene_time >= len(self.mover["path"]) * ui.secs(HOP):
            self.set_scene("landed")

    def _update_landed(self, dt) -> None:
        if self.scene_time >= ui.secs(LAND_HOLD):
            self.open_event()

    def _update_event(self, dt) -> None:
        if self.paused or self.timer_left <= 0:
            return
        before = self.timer_left
        self.timer_left = max(0.0, before - dt)
        # tick once per second during the last 5 seconds (at 5, 4, 3, 2 and 1 s left)
        for mark in range(1, 6):
            if self.timer_left <= mark < before:
                self.audio.play("tick")

    def _update_reveal(self, dt) -> None:
        if not self.counted and self.scene_time >= ui.secs(COUNT_UP):
            self.finish_count()

    def _update_score(self, dt) -> None:
        t = ui.ease_out(self.scene_time / ui.secs(SCORE_ANIM))
        code = self.record.code
        self.shown_scores[code] = self.score_from + (self.state.scores[code] - self.score_from) * t
        if self.scene_time >= ui.secs(SCORE_ANIM + SCORE_HOLD):
            self.after_score()

    def _update_country(self, dt) -> None:
        if self.player is not None and self.scene_time - self.picked_at >= ui.secs(PICK_HOLD):
            self.set_scene("sound")

    def final_progress(self) -> float:
        """Singleplayer final screen: the shown percentage while the bar fills."""
        t = ui.ease_in_out(self.scene_time / ui.secs(FINAL_FILL))   # gentle start and finish
        return self.state.scores[self.state.codes[0]] * t

    def _update_final(self, dt) -> None:
        self.confetti.update(dt)

    # ----- Drawing ----------------------------------------------------------------------

    def draw(self, surface) -> None:
        surface.fill(ui.PAPER)
        if self.scene in BOARD_SCENES:
            screens.draw_board_scene(surface, self)
        else:
            draw = getattr(screens, f"draw_{self.scene}", None)
            if draw is not None:
                draw(surface, self)
        screens.draw_overlays(surface, self)

    # ----- Main loop --------------------------------------------------------------------

    def frame(self, dt: float) -> None:
        """One frame: keys, time, drawing. Never lets an error escape."""
        try:
            for event in pygame.event.get():
                self.handle(event)
            self.update(min(MAX_DT, dt))
            self.draw(self.screen)
            pygame.display.flip()
        except Exception:
            self._crash()

    def run(self) -> None:
        clock = pygame.time.Clock()
        last = time.perf_counter()
        while self.running:
            clock.tick(60)                       # at most 60 frames per second
            now = time.perf_counter()
            self.frame(now - last)
            last = now
        pygame.quit()

    async def run_async(self) -> None:
        """The same loop for the web version: the browser draws the next frame
        when we pause with asyncio.sleep(0), so time is measured, not ticked."""
        last = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            self.frame(now - last)
            last = now
            await asyncio.sleep(0)

    def _crash(self) -> None:
        """Last-resort safety net: log the error, save, and show a calm message."""
        try:
            with (ROOT / "error_log.txt").open("a", encoding="utf-8") as f:
                f.write(traceback.format_exc() + "\n")
        except OSError:
            pass
        self.save()
        if self.scene == "crash":       # crashing while showing the crash screen: give up
            self.running = False
            return
        self.set_scene("crash")


def _open_display(windowed: bool) -> pygame.Surface:
    """1920 x 1080 canvas, scaled to the screen (letterboxed if needed)."""
    if WEB:      # the web page scales the canvas to the browser window itself
        pygame.display.set_caption(config.GAME_TITLE)
        return pygame.display.set_mode((ui.W, ui.H))
    fullscreen = config.FULLSCREEN and not windowed
    flags = pygame.SCALED | (pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE)
    index = _display_index()
    pygame.display.set_caption(config.GAME_TITLE)
    try:
        screen = pygame.display.set_mode((ui.W, ui.H), flags, display=index, vsync=1)
    except pygame.error:
        screen = pygame.display.set_mode((ui.W, ui.H), flags, display=index)
    if not fullscreen:
        _fit_window(index)
    return screen


def _display_index() -> int:
    """config.DISPLAY_INDEX, or 0 if that screen isn't connected."""
    try:
        if 0 <= config.DISPLAY_INDEX < pygame.display.get_num_displays():
            return config.DISPLAY_INDEX
    except (pygame.error, TypeError):
        pass
    return 0


def _fit_window(index: int) -> None:
    """Shrink the window (keeping 16:9) if it doesn't fit on the desktop."""
    try:
        desk_w, desk_h = pygame.display.get_desktop_sizes()[index]
        scale = min(1.0, desk_w * 0.9 / ui.W, desk_h * 0.85 / ui.H)
        if scale < 1.0:
            window = pygame.Window.from_display_module()
            window.minimum_size = (480, 270)   # SCALED starts with the full canvas as minimum
            window.size = (int(ui.W * scale), int(ui.H * scale))
            window.position = pygame.WINDOWPOS_CENTERED
    except Exception:
        pass


def run(windowed: bool = False) -> None:
    """Entry point used by main.py."""
    try:
        app = App(windowed)
    except pygame.error as err:
        print(f"Could not open the game window: {err}")
        return
    app.run()


async def run_web() -> None:
    """Entry point for the web version (see make_web.py)."""
    await App(windowed=True).run_async()
