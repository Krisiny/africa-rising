"""Drawing helpers for Africa Rising: colors, fonts, text, buttons and effects.

Everything here draws on a fixed 1920 x 1080 canvas. The look is "projector
first": flat paper cards, ink text, big type, nothing smaller than 30 px.
Arrows and icons are polygons, never font glyphs. The banknote touches
(guilloche, stamp, double border) are only used by the reveal card.
"""

from __future__ import annotations

import math
import random
import re
from pathlib import Path

import pygame

import config

# ---------------------------------------------------------------------------
# Canvas, colors and sizes
# ---------------------------------------------------------------------------

W, H = 1920, 1080

PAPER = (0xEE, 0xF3, 0xEC)
INK = (0x15, 0x39, 0x2B)
LINE = (0xA9, 0xC2, 0xB4)
GAIN = (0x1D, 0x83, 0x48)
LOSS = (0xB8, 0x32, 0x2A)
WHITE = (255, 255, 255)

MIN_SIZE = 30
SIZE = {"title": 140, "reveal": 160, "event_title": 72, "option": 46,
        "body": 38, "score_name": 42, "score_num": 56, "small": 30}

MINUS = "−"  # true minus sign, used when the fonts have it

# Fallback system fonts (comma-separated lists for SysFont)
_SYS_DISPLAY = "segoeuiblack,arialblack,arial"
_SYS_TEXT = "segoeui,arial"

# Module state, filled by init()
_assets = Path("assets")
_font_files: dict[str, tuple[Path, bool] | None] = {"display": None, "text": None, "bold": None}
_fonts: dict[tuple[str, int], pygame.font.Font] = {}
_text_cache: dict[tuple, pygame.Surface] = {}
_guilloche_cache: dict[tuple[int, int], pygame.Surface] = {}
_stamp_cache: dict[tuple, pygame.Surface] = {}
_flag_cache: dict[tuple[str, int], pygame.Surface | None] = {}
_background_cache: dict[str, pygame.Surface | None] = {}
_minus_ok: bool | None = None

_TEXT_CACHE_MAX = 600


def _rgb(color) -> tuple[int, int, int, int]:
    """Any pygame color value ((r, g, b), "#RRGGBB", Color) as an RGBA tuple."""
    c = pygame.Color(color)
    return (c.r, c.g, c.b, c.a)


def prep(surface: pygame.Surface) -> pygame.Surface:
    """convert_alpha() for faster blits, but only when a display exists."""
    try:
        if pygame.display.get_init() and pygame.display.get_surface() is not None:
            return surface.convert_alpha()
    except pygame.error:
        pass
    return surface


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

def _norm(name: str) -> str:
    """'Big Shoulders_Display-ExtraBold' -> 'bigshouldersdisplayextrabold'."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _weight(norm: str) -> str:
    """Guess the weight of a font from its normalized file name."""
    if "extrabold" in norm or "ultrabold" in norm:
        return "extrabold"
    if "semibold" in norm or "demibold" in norm:
        return "semibold"
    if "extralight" in norm or "ultralight" in norm:
        return "light"
    if "black" in norm or "heavy" in norm:
        return "black"
    if "bold" in norm:
        return "bold"
    if "medium" in norm:
        return "medium"
    if "light" in norm or "thin" in norm:
        return "light"
    return "regular"


def _is_variable(path: Path) -> bool:
    """Variable fonts look like 'Name[wght].ttf' or 'Name-VariableFont_wght.ttf'."""
    return "[" in path.name or "variable" in _norm(path.stem)


# Lower rank = better. Weights not listed are not used for that style.
_RANKS = {
    "display": {"extrabold": 0, "black": 1, "bold": 2, "semibold": 3, "medium": 4, "regular": 5},
    "text": {"regular": 0, "medium": 1, "light": 2},
    "bold": {"bold": 0, "semibold": 1, "extrabold": 2, "black": 3},
}
_VARIABLE_RANK = 50  # a variable font only if nothing static fits


def _family(style: str, norm: str) -> bool:
    """Does this file belong to the family used for `style`?"""
    if style == "display":
        return "bigshoulders" in norm and "stencil" not in norm and "inline" not in norm
    return "atkinson" in norm and "hyperlegible" in norm and "mono" not in norm


def _candidates(files: list[Path], style: str) -> list[tuple[float, Path, bool]]:
    """Font files for a style, best first, as (rank, path, needs_synthetic_bold)."""
    found = []
    for path in files:
        norm = _norm(path.stem)
        if not _family(style, norm) or "italic" in norm or "oblique" in norm:
            continue
        if _is_variable(path):
            # pygame can't pick a weight axis, so fake the bold for heavy styles
            found.append((_VARIABLE_RANK, path, style in ("display", "bold")))
            continue
        rank = _RANKS[style].get(_weight(norm))
        if rank is None:
            continue
        if style == "display" and "display" not in norm:
            rank += 0.5  # e.g. Big Shoulders Text: fine, but Display is better
        found.append((rank, path, False))
    found.sort(key=lambda item: (item[0], item[1].name.lower()))
    return found


def _font_dir_files(assets_dir: Path) -> list[Path]:
    folder = Path(assets_dir) / "fonts"
    try:
        return sorted(p for p in folder.iterdir()
                      if p.is_file() and p.suffix.lower() in (".ttf", ".otf"))
    except OSError:
        return []


def init(assets_dir: Path) -> None:
    """Find the game fonts in assets_dir/fonts and reset all caches. Never raises."""
    global _assets, _minus_ok
    try:
        if not pygame.font.get_init():
            pygame.font.init()
    except pygame.error:
        pass
    _assets = Path(assets_dir)
    _fonts.clear()
    _text_cache.clear()
    _guilloche_cache.clear()
    _stamp_cache.clear()
    _flag_cache.clear()
    _background_cache.clear()
    _minus_ok = None
    files = _font_dir_files(_assets)
    for style in ("display", "text", "bold"):
        _font_files[style] = None
        for _rank, path, synthetic in _candidates(files, style):
            try:
                pygame.font.Font(str(path), MIN_SIZE)  # can it be opened?
            except Exception:
                continue
            _font_files[style] = (path, synthetic)
            break


def font_file(style: str) -> Path | None:
    """The font file used for a style, or None when a system font is used."""
    entry = _font_files.get(style)
    return entry[0] if entry else None


def _make_font(style: str, size: int) -> pygame.font.Font:
    entry = _font_files.get(style)
    if entry:
        try:
            f = pygame.font.Font(str(entry[0]), size)
            if entry[1]:
                f.bold = True
            return f
        except Exception:
            pass
    if style == "display":
        return pygame.font.SysFont(_SYS_DISPLAY, size)
    return pygame.font.SysFont(_SYS_TEXT, size, bold=(style == "bold"))


def font(style: str, size: int) -> pygame.font.Font:
    """A cached font: style is "display", "text" or "bold"; size >= MIN_SIZE."""
    size = max(MIN_SIZE, int(size))
    key = (style, size)
    if key not in _fonts:
        if not pygame.font.get_init():
            pygame.font.init()
        _fonts[key] = _make_font(style, size)
    return _fonts[key]


def has_glyph(style: str, ch: str) -> bool:
    """True if the font for `style` really draws `ch` (not the empty-box glyph)."""
    try:
        f = font(style, MIN_SIZE)
        got = f.metrics(ch)
        missing = f.metrics("\U0010FFFD")  # private-use code point: never in a font
        return bool(got) and got[0] is not None and got[0] != missing[0]
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def render(s, style: str, size: int, color) -> pygame.Surface:
    """Rendered (anti-aliased, transparent) text surface, cached."""
    s = str(s)
    key = (s, style, max(MIN_SIZE, int(size)), _rgb(color))
    surf = _text_cache.get(key)
    if surf is None:
        if len(_text_cache) >= _TEXT_CACHE_MAX:
            _text_cache.clear()
        surf = prep(font(style, size).render(s, True, key[3]))
        _text_cache[key] = surf
    return surf


def text(surface, s, style, size, color, pos, anchor="topleft", alpha=255) -> pygame.Rect:
    """Draw one line of text; `pos` is where the rect's `anchor` point goes.

    `alpha` below 255 makes the text see-through (0 = invisible), for fading.
    """
    surf = render(s, style, size, color)
    rect = surf.get_rect()
    setattr(rect, anchor, (round(pos[0]), round(pos[1])))
    if alpha < 255:
        surf = surf.copy()
        surf.set_alpha(max(0, int(alpha)))
    surface.blit(surf, rect)
    return rect


def _split_word(word: str, fits) -> list[str]:
    """Hard-split a word that is too long for one line."""
    parts, current = [], ""
    for ch in word:
        if current and not fits(current + ch):
            parts.append(current)
            current = ch
        else:
            current += ch
    parts.append(current)
    return parts


def wrap(s, style, size, max_width, max_chars=70) -> list[str]:
    """Greedy word wrap by pixel width and characters per line.

    Words are never split unless one word alone is wider than max_width.
    Newlines in `s` start a new line. An empty string gives [""].
    """
    f = font(style, size)

    def fits(line: str) -> bool:
        if max_chars and len(line) > max_chars:
            return False
        return max_width is None or f.size(line)[0] <= max_width

    lines: list[str] = []
    for paragraph_text in str(s).split("\n"):
        current = ""
        for word in paragraph_text.split():
            candidate = f"{current} {word}" if current else word
            if fits(candidate):
                current = candidate
                continue
            if current:
                lines.append(current)
            if fits(word):
                current = word
            else:
                pieces = _split_word(word, fits)
                lines.extend(pieces[:-1])
                current = pieces[-1]
        lines.append(current)
    return lines or [""]


def line_step(size: int, line_gap: float = 1.15) -> int:
    """Distance between two baselines in a paragraph."""
    return round(max(MIN_SIZE, size) * line_gap)


def paragraph(surface, s, style, size, color, topleft, max_width,
              line_gap=1.15, max_chars=70) -> pygame.Rect:
    """Left-aligned wrapped text. Returns the rect that the lines cover."""
    x, y = round(topleft[0]), round(topleft[1])
    step = line_step(size, line_gap)
    covered = pygame.Rect(x, y, 0, 0)
    for i, line in enumerate(wrap(s, style, size, max_width, max_chars)):
        r = text(surface, line, style, size, color, (x, y + i * step))
        covered = r if i == 0 else covered.union(r)
    return covered


def signed_pct(value: int) -> str:
    """+3%, 0% or -1% (with a true minus sign when the fonts have it)."""
    global _minus_ok
    value = int(round(value))
    if value > 0:
        return f"+{value}%"
    if value == 0:
        return "0%"
    if _minus_ok is None:
        _minus_ok = all(has_glyph(st, MINUS) for st in ("display", "text", "bold"))
    return f"{MINUS if _minus_ok else '-'}{abs(value)}%"


def value_color(value):
    """GAIN for growth, LOSS for a drop, INK for zero."""
    if value > 0:
        return GAIN
    if value < 0:
        return LOSS
    return INK


# ---------------------------------------------------------------------------
# Shapes: arrows, cards, discs, die
# ---------------------------------------------------------------------------

def _aa_polygon(surface, color, points) -> None:
    """Filled polygon with smooth edges."""
    pygame.draw.polygon(surface, color, points)
    pygame.draw.aalines(surface, color, True, points)


def _rotate_points(points, center, angle_deg):
    a = math.radians(angle_deg)
    ca, sa = math.cos(a), math.sin(a)
    cx, cy = center
    return [(cx + (x - cx) * ca - (y - cy) * sa, cy + (x - cx) * sa + (y - cy) * ca)
            for x, y in points]


def arrow(surface, center, size, up: bool, color, direction: str | None = None) -> None:
    """Filled arrow polygon (triangle head plus stem), `size` px tall.

    `direction` ("up", "down", "left", "right") overrides `up` if given.
    """
    direction = direction or ("up" if up else "down")
    cx, cy = center
    top, bottom = cy - size / 2, cy + size / 2
    head_base = top + size * 0.55
    hw, sw = size * 0.45, size * 0.17
    pts = [(cx, top), (cx + hw, head_base), (cx + sw, head_base), (cx + sw, bottom),
           (cx - sw, bottom), (cx - sw, head_base), (cx - hw, head_base)]
    angle = {"up": 0, "right": 90, "down": 180, "left": 270}.get(direction, 0)
    if angle:
        pts = _rotate_points(pts, center, angle)
    _aa_polygon(surface, _rgb(color), pts)


def triangle(surface, center, size, direction: str, color) -> None:
    """Small solid triangle pointing "up", "down", "left" or "right"."""
    cx, cy = center
    h = size / 2
    pts = [(cx + h, cy), (cx - h, cy - h), (cx - h, cy + h)]  # pointing right
    angle = {"right": 0, "down": 90, "left": 180, "up": 270}.get(direction, 0)
    if angle:
        pts = _rotate_points(pts, center, angle)
    _aa_polygon(surface, _rgb(color), pts)


def trend_mark(surface, center, size, value) -> None:
    """Up arrow (GAIN) for > 0, down arrow (LOSS) for < 0, nothing for 0.

    (A flat bar for 0 was tried, but next to "0%" it reads like a minus sign.)
    """
    if value > 0:
        arrow(surface, center, size, True, GAIN)
    elif value < 0:
        arrow(surface, center, size, False, LOSS)


def card(surface, rect, fill=PAPER, border=INK, width=3, radius=12) -> None:
    """Flat card: fill plus border. No shadow, no gradient.

    A fill with alpha (r, g, b, a) is blended, for a see-through wash.
    """
    rect = pygame.Rect(rect)
    if fill is not None:
        c = _rgb(fill)
        if c[3] < 255:
            layer = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(layer, c, layer.get_rect(), border_radius=radius)
            surface.blit(layer, rect)
        else:
            pygame.draw.rect(surface, c, rect, border_radius=radius)
    if border is not None and width > 0:
        pygame.draw.rect(surface, _rgb(border), rect, width, border_radius=radius)


def _aa_circle(surface, color, center, radius) -> None:
    x, y, r = round(center[0]), round(center[1]), max(1, round(radius))
    if hasattr(pygame.draw, "aacircle"):          # pygame-ce 2.4+, also in the browser
        pygame.draw.aacircle(surface, color, (x, y), r)
    else:
        pygame.draw.circle(surface, color, (x, y), r)


def disc(surface, center, radius, color, code) -> None:
    """Team token: a circle in the team color with the code in white bold."""
    _aa_circle(surface, _rgb(color), center, radius)
    size = max(MIN_SIZE, round(radius * 0.95))
    text(surface, code, "bold", size, WHITE, (center[0], center[1] + 1), "center")


_PIPS = {1: [(0, 0)], 2: [(-1, -1), (1, 1)], 3: [(-1, -1), (0, 0), (1, 1)],
         4: [(-1, -1), (1, -1), (-1, 1), (1, 1)],
         5: [(-1, -1), (1, -1), (0, 0), (-1, 1), (1, 1)],
         6: [(-1, -1), (1, -1), (-1, 0), (1, 0), (-1, 1), (1, 1)]}


def die(surface, center, size, value) -> None:
    """Die face: rounded paper square, ink border, ink pips."""
    rect = pygame.Rect(0, 0, round(size), round(size))
    rect.center = (round(center[0]), round(center[1]))
    card(surface, rect, PAPER, INK, max(3, round(size / 18)), round(size * 0.18))
    off = size * 0.26
    for dx, dy in _PIPS.get(int(value), []):
        _aa_circle(surface, INK, (center[0] + dx * off, center[1] + dy * off), size * 0.09)


# ---------------------------------------------------------------------------
# Buttons
# ---------------------------------------------------------------------------

class Button:
    """Big numbered option button: number badge top-left, wrapped label."""

    STYLE = "bold"
    SIZE = 46
    PAD = 20        # inside the border
    BADGE = 62      # number badge (ink square with the number in paper color)
    GAP = 20        # between badge and label
    MIN_LINES = 2   # every button is at least two label lines high
    LINE_GAP = 1.12

    def __init__(self, rect, number: int, label: str):
        self.rect = pygame.Rect(rect)
        self.number = number
        self.label = label

    @classmethod
    def label_width(cls, width: int) -> int:
        return width - 2 * cls.PAD - cls.BADGE - cls.GAP

    @classmethod
    def height_for(cls, label: str, width: int) -> int:
        """Height a button of this width needs for its label (at least 2 lines)."""
        lines = len(wrap(label, cls.STYLE, cls.SIZE, cls.label_width(width)))
        lines = max(cls.MIN_LINES, lines)
        step = line_step(cls.SIZE, cls.LINE_GAP)
        text_h = (lines - 1) * step + font(cls.STYLE, cls.SIZE).get_height()
        return 2 * cls.PAD + max(cls.BADGE, text_h)

    def draw(self, surface) -> None:
        card(surface, self.rect, PAPER, INK, 3, 12)
        badge = pygame.Rect(self.rect.x + self.PAD, self.rect.y + self.PAD, self.BADGE, self.BADGE)
        pygame.draw.rect(surface, INK, badge, border_radius=8)
        text(surface, self.number, "bold", self.SIZE, PAPER, (badge.centerx, badge.centery + 1), "center")
        # first label line is vertically centered on the badge
        f = font(self.STYLE, self.SIZE)
        x = badge.right + self.GAP
        y = badge.centery - f.get_height() // 2
        step = line_step(self.SIZE, self.LINE_GAP)
        for i, line in enumerate(wrap(self.label, self.STYLE, self.SIZE, self.label_width(self.rect.w))):
            text(surface, line, self.STYLE, self.SIZE, INK, (x, y + i * step))

    def hit(self, pos) -> bool:
        return self.rect.collidepoint(pos)


# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------

def ease_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 1 - (1 - t) ** 3


def ease_in_out(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return 4 * t ** 3 if t < 0.5 else 1 - (-2 * t + 2) ** 3 / 2


def _speed() -> float:
    try:
        speed = float(config.ANIMATION_SPEED)
    except (AttributeError, TypeError, ValueError):
        return 1.0
    return speed if speed > 0 else 1.0


def secs(x: float) -> float:
    """Animation duration in seconds, scaled by config.ANIMATION_SPEED."""
    return x / _speed()


# ---------------------------------------------------------------------------
# Banknote touches (reveal card only)
# ---------------------------------------------------------------------------

# (R, r, d, rotation in degrees) for each hypotrochoid in the rosette
_ROSETTE = [(120, 44, 66, 0), (120, 50, 60, 9), (105, 40, 52, 4), (96, 36, 30, 0), (120, 54, 40, 15)]
_GUILLOCHE_ALPHA = 140
_SS = 3  # supersampling factor for smooth lines


def _hypotrochoid(R, r, d, rot, scale, cx, cy) -> list[tuple[float, float]]:
    turns = r // math.gcd(R, r)  # the curve closes after this many turns
    n = turns * 720
    a = math.radians(rot)
    pts = []
    for i in range(n):
        t = 2 * math.pi * turns * i / n
        x = (R - r) * math.cos(t) + d * math.cos((R - r) / r * t)
        y = (R - r) * math.sin(t) - d * math.sin((R - r) / r * t)
        xr = x * math.cos(a) - y * math.sin(a)
        yr = x * math.sin(a) + y * math.cos(a)
        pts.append((cx + xr * scale, cy + yr * scale))
    return pts


def guilloche(size) -> pygame.Surface:
    """Faint rosette of overlapping hypotrochoids in LINE color (cached).

    `size` is the side of the square surface (or a (w, h) pair).
    """
    w, h = (size, size) if isinstance(size, (int, float)) else size
    key = (int(w), int(h))
    if key in _guilloche_cache:
        return _guilloche_cache[key]
    big = pygame.Surface((key[0] * _SS, key[1] * _SS), pygame.SRCALPHA)
    big.fill((*LINE, 0))
    color = (*LINE, _GUILLOCHE_ALPHA)
    radius = min(key) * _SS / 2 - 2 * _SS
    cx, cy = key[0] * _SS / 2, key[1] * _SS / 2
    for R, r, d, rot in _ROSETTE:
        scale = radius / ((R - r) + d)
        pts = _hypotrochoid(R, r, d, rot, scale, cx, cy)
        # lines overwrite (no blending), so crossings don't build up dark spots
        pygame.draw.lines(big, color, True, pts, _SS + 1)
    surf = prep(pygame.transform.smoothscale(big, key))
    _guilloche_cache[key] = surf
    return surf


def stamp(text: str, color, angle_deg: float = -8) -> pygame.Surface:
    """'Best move!' stamp: bold text in a rounded outline, slightly rotated (cached)."""
    key = (str(text), _rgb(color)[:3], angle_deg)
    if key in _stamp_cache:
        return _stamp_cache[key]
    rgb = key[1]
    ss = 2  # draw at double size, rotozoom scales back down smoothly
    label = font("bold", 56 * ss).render(key[0], True, rgb)
    pad_x, pad_y, border = 30 * ss, 12 * ss, 5 * ss
    box = pygame.Rect(0, 0, label.get_width() + 2 * pad_x, label.get_height() + 2 * pad_y)
    surf = pygame.Surface(box.inflate(8 * ss, 8 * ss).size, pygame.SRCALPHA)
    surf.fill((*rgb, 0))
    box.center = surf.get_rect().center
    pygame.draw.rect(surf, rgb, box, border, border_radius=14 * ss)
    surf.blit(label, label.get_rect(center=box.center))
    result = prep(pygame.transform.rotozoom(surf, angle_deg, 1 / ss))
    _stamp_cache[key] = result
    return result


def banknote_border(surface, rect, color=INK, radius=12) -> None:
    """Thin double border: outer 3 px line, 8 px gap, inner 2 px line."""
    rect = pygame.Rect(rect)
    c = _rgb(color)
    pygame.draw.rect(surface, c, rect, 3, border_radius=radius)
    inner = rect.inflate(-2 * (3 + 8), -2 * (3 + 8))
    pygame.draw.rect(surface, c, inner, 2, border_radius=max(0, radius // 3))


# ---------------------------------------------------------------------------
# Confetti (final screen only)
# ---------------------------------------------------------------------------

class Confetti:
    """A short burst of paper rectangles that fall with gravity (about 2 s)."""

    COUNT = 120
    GRAVITY = 1500.0   # px/s^2
    DRAG = 2.2         # air resistance per second
    DURATION = 2.0     # seconds at ANIMATION_SPEED 1

    def __init__(self, colors: list):
        self.colors = [_rgb(c) for c in colors] or [_rgb(GAIN)]
        self.parts: list[list] = []
        self.t = 0.0
        self.duration = secs(self.DURATION)
        self.active = False

    def burst(self, origin) -> None:
        rng = random.Random()
        self.parts = []
        for i in range(self.COUNT):
            angle = math.radians(rng.uniform(-150, -30))   # upward fan
            speed = rng.uniform(500, 1300)
            self.parts.append([
                float(origin[0]), float(origin[1]),
                math.cos(angle) * speed, math.sin(angle) * speed,
                rng.uniform(12, 20), rng.uniform(7, 11),       # w, h
                rng.uniform(0, 360), rng.uniform(-540, 540),   # rotation, spin
                rng.uniform(0, 6.3), rng.uniform(6, 14),       # flip phase, flip speed
                self.colors[i % len(self.colors)],
            ])
        self.t = 0.0
        self.duration = secs(self.DURATION)
        self.active = True

    @property
    def done(self) -> bool:
        return not self.active

    def update(self, dt: float) -> None:
        if not self.active:
            return
        self.t += dt
        step = dt * _speed()
        damp = math.exp(-self.DRAG * step)
        for p in self.parts:
            p[3] += self.GRAVITY * step
            p[2] *= damp
            p[3] *= damp
            p[0] += p[2] * step
            p[1] += p[3] * step
            p[6] += p[7] * step
            p[8] += p[9] * step
        if self.t >= self.duration:
            self.active = False
            self.parts = []

    def draw(self, surface) -> None:
        if not self.active:
            return
        # pieces shrink away during the last quarter instead of popping out
        left = self.duration - self.t
        k = min(1.0, max(0.0, left / (0.25 * self.duration)))
        for x, y, _vx, _vy, w, h, rot, _spin, flip, _fs, color in self.parts:
            hw = w * k * abs(math.cos(flip)) / 2 + 0.5
            hh = h * k / 2
            a = math.radians(rot)
            ca, sa = math.cos(a), math.sin(a)
            pts = [(x + dx * ca - dy * sa, y + dx * sa + dy * ca)
                   for dx, dy in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]
            pygame.draw.polygon(surface, color, pts)


# ---------------------------------------------------------------------------
# Background photos and pulsing prompts
# ---------------------------------------------------------------------------

def background(name: str) -> pygame.Surface | None:
    """assets/backgrounds/{name}.jpg (or .png) filling the whole canvas, or None.

    Photos of another size are scaled to cover the screen (edges cropped),
    like a picture background in PowerPoint. Cached after the first load.
    """
    if name in _background_cache:
        return _background_cache[name]
    surf = None
    path = _find_file(_assets / "backgrounds", name, (".jpg", ".jpeg", ".png"))
    if path is not None:
        try:
            img = pygame.image.load(str(path))
            scale = max(W / img.get_width(), H / img.get_height())
            size = (max(W, round(img.get_width() * scale)), max(H, round(img.get_height() * scale)))
            if size != img.get_size():
                img = pygame.transform.smoothscale(img, size)
            crop = pygame.Rect(0, 0, W, H)
            crop.center = (size[0] // 2, size[1] // 2)
            surf = img.subsurface(crop).copy()
            if pygame.display.get_init() and pygame.display.get_surface() is not None:
                surf = surf.convert()
        except Exception:
            surf = None
    _background_cache[name] = surf
    return surf


def pulse(t: float, period: float = 1.0) -> int:
    """Alpha (0..255) that fades out and back in smoothly once per `period` seconds."""
    return round(255 * (0.5 + 0.5 * math.cos(2 * math.pi * t / period)))


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

def _find_file(folder: Path, stem: str, suffixes: tuple[str, ...]) -> Path | None:
    """Case-insensitive lookup of folder/stem.suffix."""
    try:
        files = list(folder.iterdir())
    except OSError:
        return None
    for suffix in suffixes:
        for p in files:
            if p.is_file() and p.stem.lower() == stem.lower() and p.suffix.lower() == suffix:
                return p
    return None


def flag(code: str, height: int) -> pygame.Surface | None:
    """assets/flags/{code}.png scaled to `height` with a thin ink outline, or None."""
    key = (str(code).upper(), int(height))
    if key in _flag_cache:
        return _flag_cache[key]
    surf = None
    path = _find_file(_assets / "flags", key[0], (".png",))
    if path is not None:
        try:
            img = pygame.image.load(str(path))
            rgba = pygame.Surface(img.get_size(), pygame.SRCALPHA)  # 32-bit for smoothscale
            rgba.blit(img, (0, 0))
            width = max(1, round(img.get_width() * key[1] / max(1, img.get_height())))
            surf = pygame.transform.smoothscale(rgba, (width, key[1]))
            pygame.draw.rect(surf, INK, surf.get_rect(), 2)
            surf = prep(surf)
        except Exception:
            surf = None
    _flag_cache[key] = surf
    return surf
