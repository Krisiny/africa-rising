"""Optional sounds and music. Nothing in here may ever crash the game.

Sounds: assets/sounds/{name}.wav (or .ogg). If a file is missing, a simple
placeholder made in code (a small WAV file built in memory) is played instead.
Music: assets/music/{key}.ogg/.wav/.mp3, where key is "title" or a country
code. Swapping in new files is all it takes; missing music is just silence.
"""

from __future__ import annotations

import io
import math
import random
import struct
from pathlib import Path

import pygame

SOUND_NAMES = ("dice", "step", "good", "bad", "best", "tick", "win")
RATE = 44100
SOUND_VOLUME = 0.8
FADE_MS = 500


def pre_init() -> None:
    """Call before pygame.init() for a small audio delay."""
    try:
        pygame.mixer.pre_init(RATE, -16, 2, 512)
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


# ----- The Audio class ----------------------------------------------------------

class Audio:
    """Plays sounds and music if it can; silently does nothing if it can't."""

    def __init__(self, assets_dir: Path, sound_on: bool, music_volume: float):
        self.assets = Path(assets_dir)
        self.music_volume = max(0.0, min(1.0, float(music_volume)))
        self.muted = not sound_on
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self.current: str | None = None      # music key that is playing
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
        try:
            self.sounds[name] = pygame.mixer.Sound(file=_wav_bytes(_placeholder(name)))
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
        """Loop the music for `key` ("title" or a country code). None = silence."""
        if not self.ok or key == self.current:
            return
        self.current = key
        try:
            path = _find(self.assets / "music", key, (".ogg", ".wav", ".mp3")) if key else None
            if path is None:
                pygame.mixer.music.fadeout(FADE_MS)
                return
            pygame.mixer.music.load(str(path))
            pygame.mixer.music.set_volume(0.0 if self.muted else self.music_volume)
            pygame.mixer.music.play(-1, fade_ms=FADE_MS)
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
