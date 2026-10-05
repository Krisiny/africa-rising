"""Optional sounds and music. Nothing in here may ever crash the game.

Sounds: assets/sounds/{name}.wav (or .ogg). If a file is missing, a simple
placeholder made in code (a small WAV file built in memory) is played instead.
Music: assets/music/{key}.ogg/.wav/.mp3, where key is "title" or a country
code. If there is no file for a key, the background playlist plays instead:
every file whose name starts with "background" (background1.mp3,
background2.mp3, ...), one after another in name order, then from the start
again. It keeps running from screen to screen without restarting.
Swapping in new files is all it takes; with no music files the game is silent.
"""

from __future__ import annotations

import io
import math
import random
import struct
import sys
import tempfile
from pathlib import Path

import pygame

SOUND_NAMES = ("dice", "step", "good", "bad", "best", "tick", "win", "select")
RATE = 44100
SOUND_VOLUME = 0.8
FADE_MS = 500
BACKGROUND = "background"      # background1.mp3, background2.mp3, ... form the background playlist
MUSIC_TYPES = (".ogg", ".wav", ".mp3")
MIN_TRACK_TIME = 2.0           # a song counts as finished only after it has played this long


def pre_init() -> None:
    """Call before pygame.init().

    A small buffer gives a short delay on a computer. In the browser the sound
    is mixed between frames, so a bigger buffer keeps it clean on slow phones.
    """
    buffer = 2048 if sys.platform == "emscripten" else 512
    try:
        pygame.mixer.pre_init(RATE, -16, 2, buffer)
    except Exception:
        pass


# ----- Placeholder sounds -------------------------------------------------------

def _tone(freq: float, length: float, volume: float = 0.35) -> list[float]:
    """A soft sine note with a short fade in and a longer fade out."""
    n = int(RATE * length)
    out = []
    for i in range(n):
        t = i / RATE
        env = min(1.0, i / (RATE * 0.005)) * (1 - i / n) ** 2
        out.append(volume * env * (math.sin(2 * math.pi * freq * t) + 0.3 * math.sin(4 * math.pi * freq * t)))
    return out


def _notes(freqs: list[float], length: float, volume: float = 0.35) -> list[float]:
    samples = []
    for f in freqs:
        samples += _tone(f, length, volume)
    return samples


def _rattle() -> list[float]:
    """Dice: a few short clicks of filtered noise."""
    rng = random.Random(7)
    samples = [0.0] * int(RATE * 0.5)
    for k in range(9):
        start = int(RATE * (0.02 + k * 0.05 + rng.uniform(0, 0.015)))
        last = 0.0
        for i in range(int(RATE * 0.025)):
            if start + i >= len(samples):
                break
            last = 0.6 * last + 0.4 * rng.uniform(-1, 1)      # simple low-pass
            samples[start + i] += 0.5 * last * (1 - i / (RATE * 0.025))
    return samples


def _placeholder(name: str) -> list[float]:
    if name == "dice":
        return _rattle()
    if name == "step":
        return _tone(660, 0.07, 0.25)
    if name == "good":
        return _notes([523, 784], 0.2)
    if name == "bad":
        return _notes([392, 262], 0.2)
    if name == "best":
        return _notes([523, 659, 784], 0.2)
    if name == "tick":
        return _tone(1200, 0.05, 0.3)
    if name == "select":
        return _notes([784, 1175], 0.16) + _tone(1568, 0.3)
    if name == "win":
        return _notes([523, 659, 784], 0.18) + _tone(1047, 0.66)
    return []


def _wav_bytes(samples: list[float]) -> io.BytesIO:
    """Pack samples (-1..1) into an in-memory stereo 16-bit WAV file.

    The 44-byte WAV header is written by hand because the web version's
    Python has no wave module.
    """
    frames = bytearray()
    for s in samples:
        v = int(max(-1.0, min(1.0, s)) * 32767)
        frames += struct.pack("<hh", v, v)
    channels, width = 2, 2
    header = struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + len(frames), b"WAVE", b"fmt ", 16, 1,
                         channels, RATE, RATE * channels * width, channels * width, 8 * width,
                         b"data", len(frames))
    return io.BytesIO(header + bytes(frames))


def _find(folder: Path, stem: str, suffixes: tuple[str, ...]) -> Path | None:
    """Case-insensitive lookup of folder/stem + one of the suffixes."""
    try:
        files = [p for p in folder.iterdir() if p.is_file()]
    except OSError:
        return None
    for suffix in suffixes:
        for p in files:
            if p.stem.lower() == stem.lower() and p.suffix.lower() == suffix:
                return p
    return None


def _playlist(folder: Path) -> list[Path]:
    """Background songs (names starting with "background"), in name order.

    If the same song exists in several formats, the one earliest in MUSIC_TYPES wins.
    """
    try:
        files = [p for p in folder.iterdir()
                 if p.is_file() and p.stem.lower().startswith(BACKGROUND) and p.suffix.lower() in MUSIC_TYPES]
    except OSError:
        return []
    best: dict[str, Path] = {}
    for p in sorted(files, key=lambda p: MUSIC_TYPES.index(p.suffix.lower())):
        best.setdefault(p.stem.lower(), p)
    return [best[stem] for stem in sorted(best)]


# ----- The Audio class ----------------------------------------------------------

class Audio:
    """Plays sounds and music if it can; silently does nothing if it can't."""

    def __init__(self, assets_dir: Path, sound_on: bool, music_volume: float):
        self.assets = Path(assets_dir)
        self.music_volume = max(0.0, min(1.0, float(music_volume)))
        self.muted = not sound_on
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.current: Path | str | None = None   # music file playing, or BACKGROUND for the playlist
        self.playlist = _playlist(self.assets / "music")
        self.track = 0                            # which playlist song is playing
        self.track_time = 0.0                     # how long it has been playing (seconds)
        self.ok = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            self.ok = pygame.mixer.get_init() is not None
        except Exception:
            self.ok = False
        if self.ok:
            for name in SOUND_NAMES:
                self._load_sound(name)

    def _load_sound(self, name: str) -> None:
        path = _find(self.assets / "sounds", name, (".wav", ".ogg"))
        try:
            if path is not None:
                self.sounds[name] = pygame.mixer.Sound(str(path))
                return
        except Exception:
            pass   # broken file: fall back to the placeholder
        wav = _wav_bytes(_placeholder(name))
        try:
            self.sounds[name] = pygame.mixer.Sound(file=wav)
            return
        except Exception:
            pass   # the browser version can't load sounds from memory...
        try:       # ...but it can from a file, so write the placeholder to a temporary file
            temp = Path(tempfile.gettempdir()) / f"africa_rising_{name}.wav"
            temp.write_bytes(wav.getvalue())
            self.sounds[name] = pygame.mixer.Sound(str(temp))
        except Exception:
            pass

    def play(self, name: str) -> None:
        if not self.ok or self.muted:
            return
        try:
            sound = self.sounds.get(name)
            if sound is not None:
                sound.set_volume(SOUND_VOLUME)
                sound.play()
        except Exception:
            pass

    def music(self, key: str | None) -> None:
        """Loop the music for `key` ("title" or a country code). None = silence.

        Without a file for `key`, the background playlist plays. Music that is
        already playing is never restarted, so it runs on from screen to screen.
        """
        if not self.ok:
            return
        want = _find(self.assets / "music", key, MUSIC_TYPES) if key else None
        if want is None and key and self.playlist:
            want = BACKGROUND
        if want == self.current:
            return
        self.current = want
        if want is None:
            try:
                pygame.mixer.music.fadeout(FADE_MS)
            except Exception:
                pass
        elif want == BACKGROUND:
            self._start(self.playlist[self.track], loops=0)       # once; update() moves on
        else:
            self._start(want, loops=-1)                            # a single loop, forever

    def update(self, dt: float) -> None:
        """Call every frame: starts the next playlist song when one has finished."""
        if not self.ok or self.current != BACKGROUND:
            return
        self.track_time += dt
        try:
            finished = self.track_time > MIN_TRACK_TIME and not pygame.mixer.music.get_busy()
        except Exception:
            return
        if finished:
            self.track = (self.track + 1) % len(self.playlist)
            self._start(self.playlist[self.track], loops=0)

    def _start(self, path: Path, loops: int) -> None:
        self.track_time = 0.0
        try:
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(0.0 if self.muted else self.music_volume)
            pygame.mixer.music.play(loops, fade_ms=FADE_MS)
        except Exception:
            pass

    def toggle_mute(self) -> bool:
        """Mute or unmute sounds and music. Returns True if now muted."""
        self.muted = not self.muted
        if self.ok:
            try:
                pygame.mixer.music.set_volume(0.0 if self.muted else self.music_volume)
                if self.muted:
                    pygame.mixer.stop()
            except Exception:
                pass
        return self.muted
