"""The lion on the singleplayer "Your final progress" screen.

It reacts to the GDP growth shown on screen while that number counts up:

* gains make its belly bigger; at the maximum it fills the whole screen
* it looks more and more surprised as it gets fatter
* above FLOAT_FROM % it floats like a balloon
* losses make it skinny and sad, and at SKELETON_AT % or lower only its
  skeleton is left

Everything is drawn with simple shapes, so no image file is needed.
The lion faces left, towards the progress bar.
"""

from __future__ import annotations

import math

import pygame

from game import ui

FUR = (227, 167, 63)
LIGHT = (246, 216, 152)       # belly and muzzle
MANE = (168, 91, 31)
OUTLINE = (90, 52, 18)
BONE = (244, 240, 228)
DARK = (40, 24, 10)
SHADOW = (205, 212, 202)

FLOAT_FROM = 5                # % growth from which the lion floats like a balloon
SKELETON_AT = -5              # % growth at or below which only bones are left
BODY_RX, BODY_RY = 150, 100   # body size at 0 %
LEG = 90                      # leg length
HEAD_R = 70                   # head size at 0 %


def draw_lion(surface, value: float, scale: float, t: float, home=(1580, 930)) -> None:
    """Draw the lion for a shown GDP growth of `value` %.

    `scale` is the biggest possible growth (the lion then fills the screen),
    `t` is the time in seconds (for bobbing and breathing), `home` is where
    its feet stand at 0 %.
    """
    gain = min(1.0, value / scale) if value > 0 and scale > 0 else 0.0
    loss = min(1.0, value / SKELETON_AT) if value < 0 else 0.0
    if value <= SKELETON_AT:
        _skeleton(surface, home)
        return

    breathe = 1 + 0.015 * math.sin(t * 3)
    rx = BODY_RX * (1 + 3.6 * gain) * (1 - 0.30 * loss) * breathe
    ry = BODY_RY * (1 + 5.0 * gain) * (1 - 0.55 * loss) * breathe
    hr = HEAD_R * (1 + 0.8 * gain) * (1 - 0.15 * loss)

    # standing on the ground, or floating up towards the middle of the screen
    gx, gy = home
    stand = (gx, gy - LEG - ry * 0.75)
    fly = (gx + (ui.W / 2 - gx) * gain, 470 + 18 * math.sin(t * 2.2))
    floating = max(0.0, min(1.0, (value - FLOAT_FROM) / 2))
    cx = stand[0] + (fly[0] - stand[0]) * floating
    cy = stand[1] + (fly[1] - stand[1]) * floating

    shadow_w = rx * 1.7 * (1 - 0.7 * floating)
    if shadow_w > 10:
        pygame.draw.ellipse(surface, SHADOW, _rect(gx, gy, shadow_w, 26))
    if floating > 0:
        _balloon_string(surface, cx, cy + ry, t)
    _tail(surface, cx + rx * 0.92, cy - ry * 0.15, rx, loss)
    lw = 36 * (1 + 0.6 * gain) * (1 - 0.45 * loss)
    for dx in (0.45, 0.2, -0.25, -0.5):            # back legs first, then front legs
        _leg(surface, cx + rx * dx, cy + ry * 0.35, cy + ry * 0.75 + LEG, lw)

    # body, belly and the balloon shine
    body = _rect(cx, cy, rx * 2, ry * 2)
    pygame.draw.ellipse(surface, FUR, body)
    pygame.draw.ellipse(surface, LIGHT, _rect(cx - rx * 0.08, cy + ry * 0.22, rx * 1.25, ry * 1.2))
    pygame.draw.ellipse(surface, OUTLINE, body, 5)
    if gain > 0.15:
        pygame.draw.circle(surface, OUTLINE, (round(cx - rx * 0.05), round(cy + ry * 0.45)), max(4, round(ry * 0.03)))
    if floating > 0:
        shine = _rect(cx - rx * 0.45, cy - ry * 0.55, rx * 0.5, ry * 0.3)
        pygame.draw.arc(surface, (255, 255, 255), shine, math.radians(100), math.radians(200), max(4, round(rx * 0.04)))
    if loss > 0.3:                                    # ribs show when it gets thin
        for i in range(3):
            rib = _rect(cx + rx * 0.1, cy - ry * 0.35 + i * ry * 0.32, rx * 1.1, ry * 0.7)
            pygame.draw.arc(surface, OUTLINE, rib, math.radians(205), math.radians(335), 4)

    # the head sits at the front of the body, but always stays on the screen
    hx = max(hr * 1.5, cx - rx * 0.78)
    hy = max(hr * 1.5, cy - ry * 0.55)
    _head(surface, hx, hy, hr, gain, loss)


# ----- Parts ----------------------------------------------------------------------------

def _rect(cx, cy, w, h) -> pygame.Rect:
    r = pygame.Rect(0, 0, max(1, round(w)), max(1, round(h)))
    r.center = (round(cx), round(cy))
    return r


def _thick_line(surface, points, width: int, color, outline=OUTLINE) -> None:
    pygame.draw.lines(surface, outline, False, points, width + 6)
    pygame.draw.lines(surface, color, False, points, width)
    for p in (points[0], points[-1]):
        pygame.draw.circle(surface, color, (round(p[0]), round(p[1])), width // 2)


def _tail(surface, x, y, rx, loss) -> None:
    length = 120 + rx * 0.15
    points = [(x + length * s, y - length * 0.9 * s * s) for s in (i / 12 for i in range(13))]
    _thick_line(surface, points, max(6, round(12 * (1 - 0.4 * loss))), FUR)
    tip = points[-1]
    pygame.draw.circle(surface, MANE, (round(tip[0]), round(tip[1])), 20)
    pygame.draw.circle(surface, OUTLINE, (round(tip[0]), round(tip[1])), 20, 3)


def _leg(surface, x, top, bottom, width) -> None:
    leg = pygame.Rect(0, 0, max(8, round(width)), max(8, round(bottom - top)))
    leg.midtop = (round(x), round(top))
    pygame.draw.rect(surface, FUR, leg, border_radius=leg.w // 2)
    pygame.draw.rect(surface, OUTLINE, leg, 4, border_radius=leg.w // 2)
    paw = _rect(x - width * 0.15, bottom - 6, width * 1.5, width * 0.7)
    pygame.draw.ellipse(surface, LIGHT, paw)
    pygame.draw.ellipse(surface, OUTLINE, paw, 3)


def _balloon_string(surface, x, y, t) -> None:
    points = [(x + 14 * math.sin(i * 0.5 + t * 3), y + i * 14) for i in range(14)]
    pygame.draw.lines(surface, OUTLINE, False, points, 3)
    pygame.draw.polygon(surface, FUR, [(x - 12, y + 16), (x + 12, y + 16), (x, y - 4)])
    pygame.draw.polygon(surface, OUTLINE, [(x - 12, y + 16), (x + 12, y + 16), (x, y - 4)], 3)


def _head(surface, hx, hy, hr, gain, loss) -> None:
    # mane: a ring of puffs behind the head, then the ears and the face
    puffs = 14
    for i in range(puffs):
        a = 2 * math.pi * i / puffs
        p = (round(hx + math.cos(a) * hr * 1.02), round(hy + math.sin(a) * hr * 1.02))
        pygame.draw.circle(surface, MANE, p, round(hr * 0.45))
        pygame.draw.circle(surface, OUTLINE, p, round(hr * 0.45), 3)
    for side in (-1, 1):
        ear = (round(hx + side * hr * 0.62), round(hy - hr * 0.78))
        pygame.draw.circle(surface, FUR, ear, round(hr * 0.26))
        pygame.draw.circle(surface, LIGHT, ear, round(hr * 0.13))
        pygame.draw.circle(surface, OUTLINE, ear, round(hr * 0.26), 3)
    head = (round(hx), round(hy))
    pygame.draw.circle(surface, FUR, head, round(hr))
    pygame.draw.circle(surface, OUTLINE, head, round(hr), 4)

    muzzle = _rect(hx - hr * 0.05, hy + hr * 0.38, hr * 0.95, hr * 0.6)
    pygame.draw.ellipse(surface, LIGHT, muzzle)
    nose = [(hx - hr * 0.2, hy + hr * 0.12), (hx + hr * 0.1, hy + hr * 0.12), (hx - hr * 0.05, hy + hr * 0.3)]
    pygame.draw.polygon(surface, DARK, nose)
    for side in (-1, 1):                              # whiskers
        for k in (-1, 1):
            start = (hx - hr * 0.05 + side * hr * 0.3, hy + hr * 0.38)
            end = (hx - hr * 0.05 + side * hr * 0.75, hy + hr * (0.32 + 0.1 * k))
            pygame.draw.line(surface, OUTLINE, start, end, 2)

    surprise = min(1.0, gain * 4)
    for side in (-1, 1):
        _eye(surface, hx - hr * 0.08 + side * hr * 0.35, hy - hr * 0.18, hr, surprise, loss)
    _mouth(surface, hx - hr * 0.05, hy + hr * 0.6, hr, surprise, loss)


def _eye(surface, ex, ey, hr, surprise, loss) -> None:
    er = hr * (0.15 + 0.1 * surprise)
    eye = (round(ex), round(ey))
    pygame.draw.circle(surface, (255, 255, 255), eye, round(er))
    pygame.draw.circle(surface, DARK, eye, round(er), 3)
    pupil = (round(ex - er * 0.2), round(ey + er * 0.15))      # looking down left, at the bar
    pygame.draw.circle(surface, DARK, pupil, max(3, round(hr * 0.07 * (1 - 0.45 * surprise))))
    if loss > 0:                                      # sad: heavy eyelids
        lid = pygame.Rect(0, 0, round(er * 2.3), round(er * (0.4 + 0.8 * loss)))
        lid.midtop = (eye[0], round(ey - er * 1.1))
        pygame.draw.rect(surface, FUR, lid)
        pygame.draw.line(surface, DARK, (lid.left, lid.bottom), (lid.right, lid.bottom), 3)
    brow_y = ey - er - hr * (0.08 + 0.18 * surprise)
    tilt = hr * 0.12 * loss
    pygame.draw.line(surface, DARK, (ex - er, brow_y - tilt * 0.3), (ex + er, brow_y + tilt), 5)


def _mouth(surface, mx, my, hr, surprise, loss) -> None:
    if surprise > 0.2:                                # a round "O" of surprise
        o = _rect(mx, my, hr * 0.22 * (0.6 + surprise), hr * 0.3 * (0.6 + surprise))
        pygame.draw.ellipse(surface, DARK, o)
    elif loss > 0.1:                                  # frown
        pygame.draw.arc(surface, DARK, _rect(mx, my + hr * 0.12, hr * 0.5, hr * 0.3),
                        math.radians(20), math.radians(160), 4)
    else:                                             # small happy smile
        pygame.draw.arc(surface, DARK, _rect(mx, my - hr * 0.05, hr * 0.5, hr * 0.3),
                        math.radians(200), math.radians(340), 4)


def _skeleton(surface, home) -> None:
    """What is left at SKELETON_AT % or lower: just the bones (and three mane hairs)."""
    gx, gy = home
    rx, ry = BODY_RX * 0.75, BODY_RY * 0.6
    cx, cy = gx, gy - LEG - ry * 1.3
    pygame.draw.ellipse(surface, SHADOW, _rect(gx, gy, rx * 2, 26))
    for dx in (0.6, 0.35, -0.35, -0.6):               # leg bones with knobbly ends
        top, bottom = (cx + rx * dx, cy + ry * 0.2), (cx + rx * dx - 8, gy - 8)
        _thick_line(surface, [top, ((top[0] + bottom[0]) / 2 + 10, (top[1] + bottom[1]) / 2), bottom], 9, BONE)
        for p in (top, bottom):
            pygame.draw.circle(surface, BONE, (round(p[0]), round(p[1])), 10)
            pygame.draw.circle(surface, OUTLINE, (round(p[0]), round(p[1])), 10, 3)
    spine_y = cy - ry * 0.55
    for i in range(4):                                # ribs: hoops hanging from the spine
        x = cx - rx * 0.42 + i * rx * 0.26
        rib = _rect(x, spine_y, rx * 0.5, ry * (2.3 - 0.25 * i))
        pygame.draw.arc(surface, OUTLINE, rib, math.radians(180), math.radians(360), 11)
        pygame.draw.arc(surface, BONE, rib, math.radians(183), math.radians(357), 6)
    pelvis = _rect(cx + rx * 0.62, cy - ry * 0.1, rx * 0.45, ry * 0.8)
    pygame.draw.ellipse(surface, BONE, pelvis)
    pygame.draw.ellipse(surface, OUTLINE, pelvis, 3)
    spine = [(cx + rx * (1.0 - 1.9 * s), cy - ry * 0.55 - 18 * math.sin(math.pi * s)) for s in (i / 11 for i in range(12))]
    tail = [(cx + rx * 1.0 + 16 * i, cy - ry * 0.55 - 9 * i * i / 4) for i in range(1, 8)]
    for p in tail + spine:                            # vertebrae
        pygame.draw.circle(surface, BONE, (round(p[0]), round(p[1])), 10)
        pygame.draw.circle(surface, OUTLINE, (round(p[0]), round(p[1])), 10, 3)

    # skull with empty eyes, a nose hole and a row of teeth
    hx, hy, hr = cx - rx * 1.05, cy - ry * 1.1, HEAD_R * 0.85
    for i, lean in enumerate((-0.5, 0.0, 0.5)):       # the last three mane hairs
        base = (hx + (i - 1) * hr * 0.3, hy - hr * 0.9)
        pygame.draw.lines(surface, MANE, False, [base, (base[0] + lean * 20, base[1] - 30), (base[0] + lean * 40, base[1] - 45)], 4)
    skull = (round(hx), round(hy))
    pygame.draw.circle(surface, BONE, skull, round(hr))
    pygame.draw.circle(surface, OUTLINE, skull, round(hr), 4)
    jaw = _rect(hx, hy + hr * 0.75, hr * 1.1, hr * 0.55)
    pygame.draw.rect(surface, BONE, jaw, border_radius=12)
    pygame.draw.rect(surface, OUTLINE, jaw, 4, border_radius=12)
    for side in (-1, 1):
        pygame.draw.ellipse(surface, DARK, _rect(hx + side * hr * 0.38, hy - hr * 0.1, hr * 0.42, hr * 0.5))
    pygame.draw.polygon(surface, DARK, [(hx - hr * 0.12, hy + hr * 0.38), (hx + hr * 0.12, hy + hr * 0.38), (hx, hy + hr * 0.2)])
    for i in range(5):
        tooth = pygame.Rect(0, 0, round(hr * 0.15), round(hr * 0.2))
        tooth.midtop = (round(hx - hr * 0.4 + i * hr * 0.2), round(hy + hr * 0.62))
        pygame.draw.rect(surface, (255, 255, 255), tooth)
        pygame.draw.rect(surface, OUTLINE, tooth, 2)
