"""Board layout and drawing: tiles, Start marker, tokens and the scoreboard.

Tiles run clockwise around a rectangle. With 8 events that is exactly the
wireframe in the spec: 1-3 along the top, 4 on the right, 5-7 along the
bottom (right to left) and 8 on the left.
"""

from __future__ import annotations

import math

import pygame

from config import TEXT
from game import ui

BOARD_AREA = pygame.Rect(40, 120, 1240, 920)      # left part of the screen
SCOREBOARD = pygame.Rect(1310, 120, 570, 920)     # right part of the screen
START_W = 130                                     # Start marker column, left of tile 1
GAP = 24
TOKEN_R = 28
TOKEN_STEP = 64


class BoardLayout:
    """Where every tile, the Start marker and the middle of the board are."""

    def __init__(self, n_tiles: int, area: pygame.Rect = BOARD_AREA):
        rows = 3 if n_tiles <= 10 else 4
        sides = rows - 2 if n_tiles >= 6 else 0           # tiles on the left and right
        top = math.ceil((n_tiles - 2 * sides) / 2)
        bottom = n_tiles - 2 * sides - top
        cols = max(3, top)

        left = area.x + START_W + 20
        tile_w = (area.right - left - GAP * (cols - 1)) // cols
        tile_h = (area.h - GAP * (rows - 1)) // rows

        def cell(row: int, col: int) -> pygame.Rect:
            return pygame.Rect(left + col * (tile_w + GAP), area.y + row * (tile_h + GAP), tile_w, tile_h)

        cells = [(0, c) for c in range(top)]                          # top, left to right
        cells += [(r, cols - 1) for r in range(1, 1 + sides)]         # right side, downwards
        cells += [(rows - 1, cols - 1 - c) for c in range(bottom)]    # bottom, right to left
        cells += [(rows - 1 - r, 0) for r in range(1, 1 + sides)]     # left side, upwards
        self.tiles = [cell(r, c) for r, c in cells]                   # tiles[0] is tile 1

        first = self.tiles[0]
        self.start = pygame.Rect(area.x, first.y, START_W, first.h)
        self.center = pygame.Rect(cell(1, 1).x, cell(1, 1).y,
                                  cell(1, cols - 2).right - cell(1, 1).x,
                                  cell(rows - 2, 1).bottom - cell(1, 1).y)

    def tile_rect(self, tile: int) -> pygame.Rect:
        return self.tiles[tile - 1]

    def slots(self, position: int, count: int) -> list[tuple[int, int]]:
        """Centers for `count` tokens on a tile (or on Start), side by side."""
        if position == 0:
            r = self.start
            per_row, x0, y0 = 2, r.x + 34, r.y + 110
            return [(x0 + (i % per_row) * TOKEN_STEP, y0 + (i // per_row) * 60) for i in range(count)]
        r = self.tile_rect(position)
        per_row = max(1, (r.w - 20) // TOKEN_STEP)
        x0, y0 = r.x + 18 + TOKEN_R, r.bottom - 16 - TOKEN_R
        return [(x0 + (i % per_row) * TOKEN_STEP, y0 - (i // per_row) * TOKEN_STEP) for i in range(count)]

    def hop_point(self, position: int) -> tuple[int, int]:
        """Where a hopping token passes through a tile."""
        return self.slots(position, 1)[0]


def draw_board(surface, layout: BoardLayout, content, positions: dict, highlight: int | None,
               hidden: str | None = None) -> None:
    """Tiles, Start marker and every token except `hidden` (the one that is hopping)."""
    for number, rect in enumerate(layout.tiles, start=1):
        event = content.event_at_tile(number)
        ui.card(surface, rect, ui.PAPER, ui.LINE, 4)
        if number == highlight:
            pygame.draw.rect(surface, ui.INK, rect, 7, border_radius=12)
        ui.text(surface, str(number), "bold", 38, ui.INK, (rect.x + 18, rect.y + 10))
        good = event.kind == "good"
        ui.arrow(surface, (rect.right - 34, rect.y + 34), 40, good, ui.GAIN if good else ui.LOSS)
        lines = ui.wrap(event.title, "bold", 38, rect.w - 36)[:2]
        for i, line in enumerate(lines):
            ui.text(surface, line, "bold", 38, ui.INK, (rect.x + 18, rect.y + 62 + i * 44))

    start = layout.start
    ui.text(surface, TEXT["start"], "bold", 30, ui.INK, (start.centerx, start.y + 10), "midtop")
    ui.arrow(surface, (start.centerx, start.y + 66), 40, True, ui.INK, direction="right")

    colors = {c.code: c.color for c in content.countries}
    for position in range(0, content.n_tiles + 1):
        codes = [c for c in content.codes if positions.get(c) == position and c != hidden]
        for code, point in zip(codes, layout.slots(position, len(codes))):
            ui.disc(surface, point, TOKEN_R, colors[code], code)


def draw_scoreboard(surface, content, scores: dict, leaders: list[str], current: str | None) -> None:
    """GDP growth per team, in turn order. Leaders get a filled row with a thick outline."""
    box = SCOREBOARD
    ui.card(surface, box)
    ui.text(surface, TEXT["scoreboard_title"], "bold", 42, ui.INK, (box.x + 30, box.y + 22))
    n = len(content.countries)
    row_h = min(140, (box.h - 110) // n)
    for i, country in enumerate(content.countries):
        row = pygame.Rect(box.x + 14, box.y + 96 + i * row_h, box.w - 28, row_h - 12)
        cy = row.centery
        if country.code in leaders:
            ui.card(surface, row, ui.LINE, ui.INK, 4, 10)
        if country.code == current:
            ui.triangle(surface, (row.x + 16, cy), 20, "right", ui.INK)
        ui.disc(surface, (row.x + 62, cy), TOKEN_R, country.color, country.code)
        x = row.x + 104
        flag = ui.flag(country.code, 36)
        if flag is not None:
            surface.blit(flag, flag.get_rect(midleft=(x, cy)))
            x += flag.get_width() + 12
        ui.text(surface, country.name, "text", 42, ui.INK, (x, cy), "midleft")
        value = round(scores[country.code])
        num = ui.text(surface, ui.signed_pct(value), "display", 56, ui.value_color(value),
                      (row.right - 16, cy), "midright")
        ui.trend_mark(surface, (num.left - 24, cy), 30, value)
