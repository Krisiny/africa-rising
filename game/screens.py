"""Drawing for every screen: resume, title, how to play, board, event card,
reveal, final results, content error and the overlays.

These functions only draw. What happens on a key press lives in app.py.
Each function gets the App, reads what it needs and draws on `surface`.
"""

from __future__ import annotations

import math

import pygame

import config
from config import TEXT
from game import ui
from game.board import draw_board, draw_scoreboard
from game.webstore import WEB

CARD = pygame.Rect(80, 50, 1760, 890)        # event card (the photo shows below it)
BOARD_SHADE = 100                             # how much the board photo is darkened
REVEAL = pygame.Rect(160, 60, 1600, 960)     # reveal card


def _name(app, code: str) -> str:
    return app.content.country(code).name


def _country_line(surface, app, code: str, pos, size=42, style="text", label=None) -> pygame.Rect:
    """Team disc, optional flag and the country name (or `label`) in one line."""
    country = app.content.country(code)
    x, cy = pos
    ui.disc(surface, (x + 30, cy), 30, country.color, country.code)
    x += 76
    flag = ui.flag(code, 36)
    if flag is not None:
        surface.blit(flag, flag.get_rect(midleft=(x, cy)))
        x += flag.get_width() + 12
    return ui.text(surface, label or country.name, style, size, ui.INK, (x, cy), "midleft")


def _prompt(surface, s: str, y: int = 1000) -> None:
    ui.text(surface, s, "text", 38, ui.INK, (ui.W // 2, y), "center")


# ----- Simple screens ---------------------------------------------------------------

def draw_resume(surface, app) -> None:
    ui.text(surface, TEXT["resume_found"], "bold", 46, ui.INK, (ui.W // 2, 470), "center")
    ui.text(surface, TEXT["resume_prompt"], "text", 46, ui.INK, (ui.W // 2, 560), "center")


def _photo(surface, name: str, shade: int = 0) -> bool:
    """Full-screen background photo (assets/backgrounds/{name}.jpg) with an optional dark tint.

    Returns False (and leaves the plain paper background) if the photo is missing.
    """
    photo = ui.background(name, shade)
    if photo is None:
        return False
    surface.blit(photo, (0, 0))
    return True


def _pulsing_button(surface, label: str, center, t: float, on_photo: bool) -> None:
    """A rounded button with a label that fades out and back in every half second."""
    color = ui.WHITE if on_photo else ui.INK
    text_surf = ui.render(label, "bold", 40, color)
    box = text_surf.get_rect().inflate(90, 34)
    button = pygame.Surface(box.size, pygame.SRCALPHA)
    shape = button.get_rect()
    if on_photo:
        pygame.draw.rect(button, (*ui.INK, 200), shape, border_radius=box.h // 2)
    pygame.draw.rect(button, color, shape, 3, border_radius=box.h // 2)
    button.blit(text_surf, text_surf.get_rect(center=shape.center))
    button.set_alpha(ui.pulse(t))
    surface.blit(button, button.get_rect(center=(round(center[0]), round(center[1]))))


def _cached(surface, app, draw_static) -> None:
    """Draw the parts of a screen that don't move only once, then reuse them.

    Full-screen photos with see-through layers are slow to draw in the browser,
    so they are drawn into app.backdrop when the screen opens.
    """
    if app.backdrop is None:
        app.backdrop = pygame.Surface((ui.W, ui.H))
        app.backdrop.fill(ui.PAPER)
        draw_static(app.backdrop, app)
    surface.blit(app.backdrop, (0, 0))


def draw_title(surface, app) -> None:
    _cached(surface, app, _title_static)
    on_photo = ui.background("title") is not None
    _pulsing_button(surface, TEXT["press_start"], (ui.W // 2, 900), app.scene_time, on_photo)


def _title_static(surface, app) -> None:
    on_photo = _photo(surface, "title", shade=70)
    color = ui.WHITE if on_photo else ui.INK
    ui.text(surface, config.GAME_TITLE, "display", 140, color, (ui.W // 2, 420), "center")
    ui.text(surface, TEXT["subtitle"], "text", 46, color, (ui.W // 2, 540), "center")


def draw_howto(surface, app) -> None:
    _cached(surface, app, _howto_static)
    on_photo = ui.background("howto") is not None
    _pulsing_button(surface, TEXT["how_continue"], (ui.W // 2, 900 if on_photo else 1000),
                    app.scene_time, on_photo)


def _howto_static(surface, app) -> None:
    if _photo(surface, "howto"):      # the text sits on a see-through paper card so it stays readable
        ui.card(surface, pygame.Rect(110, 40, 1700, 745), (*ui.PAPER, 225), ui.INK, 3, 18)
    x = 160
    ui.text(surface, TEXT["how_title"], "display", 72, ui.INK, (x, 80))
    steps = [TEXT["how_step_1"],
             TEXT["how_step_2"].format(seconds=config.TIMER_SECONDS) if config.TIMER_SECONDS > 0
             else TEXT["how_step_2_no_timer"],
             TEXT["how_step_3"].format(rounds=config.ROUNDS)]
    y = 220
    for number, step in enumerate(steps, start=1):
        badge = pygame.Rect(x, y, 62, 62)
        pygame.draw.rect(surface, ui.INK, badge, border_radius=8)
        ui.text(surface, str(number), "bold", 46, ui.PAPER, (badge.centerx, badge.centery + 1), "center")
        rect = ui.paragraph(surface, step, "text", 46, ui.INK, (x + 90, y + 4), 1500)
        y = max(rect.bottom, badge.bottom) + 40
    ui.text(surface, TEXT["how_teams"], "bold", 42, ui.INK, (x, y + 20))
    y += 110
    for i, code in enumerate(app.content.codes):
        col, row = i % 3, i // 3
        _country_line(surface, app, code, (x + col * 540, y + row * 80))


def draw_error(surface, app) -> None:
    x, width = 120, 1680
    ui.text(surface, TEXT["error_title"], "display", 72, ui.INK, (x, 60))
    y = 180
    limit = 860
    shown = 0
    for number, problem in enumerate(app.problems, start=1):
        where = problem.where() or "content.xlsx"
        body = f"{problem.message} Fix: {problem.fix}"
        lines = ui.wrap(body, "text", 32, width - 60, 90)
        needed = 42 + len(lines) * 38 + 14
        if y + needed > limit:
            break
        ui.text(surface, f"{number}. {where}", "bold", 32, ui.INK, (x, y))
        for i, line in enumerate(lines):
            ui.text(surface, line, "text", 32, ui.INK, (x + 60, y + 42 + i * 38))
        y += needed
        shown += 1
    if shown < len(app.problems):
        ui.text(surface, TEXT["error_more"].format(count=len(app.problems) - shown), "bold", 32, ui.LOSS, (x, y))
    ui.text(surface, TEXT["error_fix_hint"], "text", 38, ui.INK, (x, 940))
    ui.text(surface, TEXT["error_quit"], "bold", 38, ui.INK, (x, 995))


def draw_closed(surface, app) -> None:
    """Web version only: shown after Esc twice, because a web page can't close its tab."""
    ui.text(surface, TEXT["closed_title"], "display", 72, ui.INK, (ui.W // 2, 440), "center")
    ui.text(surface, TEXT["closed_body"], "text", 46, ui.INK, (ui.W // 2, 540), "center")
    _prompt(surface, TEXT["closed_resume"], 900)


def draw_crash(surface, app) -> None:
    ui.text(surface, TEXT["crash_title"], "display", 72, ui.INK, (ui.W // 2, 440), "center")
    ui.text(surface, TEXT["crash_body"], "text", 38, ui.INK, (ui.W // 2, 540), "center")
    _prompt(surface, TEXT["error_quit"], 900)


# ----- Board ---------------------------------------------------------------------

def draw_board_scene(surface, app) -> None:
    """Header, board, tokens, middle of the board and scoreboard (on a photo if there is one)."""
    state = app.state
    on_photo = _photo(surface, "board", shade=BOARD_SHADE)
    head = ui.WHITE if on_photo else ui.INK
    ui.text(surface, config.GAME_TITLE, "display", 56, head, (60, 56), "midleft")
    ui.text(surface, TEXT["round"].format(round=state.display_round, rounds=state.rounds),
            "bold", 42, head, (ui.W // 2, 56), "center")
    if on_photo:      # paper behind the Start marker and the middle, so they stay readable
        ui.card(surface, app.layout.start.inflate(14, 0), ui.PAPER, ui.INK, 3, 12)
        ui.card(surface, app.layout.center, ui.PAPER, ui.INK, 3, 12)

    mover = app.mover if app.scene in ("rolling", "moving") else None
    current = app.turn_team()
    positions = dict(state.positions)
    if app.scene == "rolling":
        positions[mover["code"]] = mover["start"]     # stays put while the die rolls
    highlight = None if app.scene in ("rolling", "moving", "landed") else (state.positions.get(current) or None)
    landed = state.tile if app.scene == "landed" else None
    draw_board(surface, app.layout, app.content, positions, highlight,
               hidden=mover["code"] if mover and app.scene == "moving" else None, landed=landed)
    if mover and app.scene == "moving":
        country = app.content.country(mover["code"])
        ui.disc(surface, app.hop_position(), 34, country.color, country.code)

    _draw_middle(surface, app, current)
    leaders = [s.code for s in state.ranking() if s.place == 1] if state.history else []
    draw_scoreboard(surface, app.content, app.shown_scores, leaders, current)


def _draw_middle(surface, app, code: str) -> None:
    box = app.layout.center
    cx = box.centerx
    if app.scene in ("rolling", "moving", "landed"):
        face = app.die_face
    else:
        face = app.state.last_roll or 1
    # die and team disc side by side, then "{name}'s turn" (two lines if needed)
    country = app.content.country(code)
    ui.die(surface, (cx - 60, box.y + 62), 100, face)
    ui.disc(surface, (cx + 60, box.y + 62), 40, country.color, country.code)
    label = TEXT["turn"].format(name=country.name)
    width = box.w - 20
    size = 46
    lines = ui.wrap(label, "bold", size, width)
    y = box.y + 128
    for line in lines[:2]:
        ui.text(surface, line, "bold", size, ui.INK, (cx, y), "midtop")
        y += 50
    if app.scene == "turn":       # fades out and in, like the other "press space" prompts
        ui.text(surface, TEXT["space_to_roll"], "bold", 38, ui.INK, (cx, box.bottom - 10), "midbottom",
                alpha=ui.pulse(app.scene_time))


# ----- Event card ------------------------------------------------------------------

def _backdrop(surface, app, photo: str, card: pygame.Rect, banknote: bool = False) -> None:
    """Background photo (or the washed-out board without one) plus the card on top.

    Nothing behind the card's text changes while it is open, so this is drawn
    once per screen and reused (this keeps the web version smooth).
    """
    if app.backdrop is None:
        app.backdrop = pygame.Surface((ui.W, ui.H))
        app.backdrop.fill(ui.PAPER)
        if not _photo(app.backdrop, photo):
            draw_board_scene(app.backdrop, app)
            ui.card(app.backdrop, app.backdrop.get_rect(), (*ui.PAPER, 215), None, 0, 0)
        if banknote:
            ui.card(app.backdrop, card, (*ui.PAPER, 240), None)
            ui.banknote_border(app.backdrop, card.inflate(-24, -24))
        else:
            ui.card(app.backdrop, card, (*ui.PAPER, 240))
    surface.blit(app.backdrop, (0, 0))


def draw_event(surface, app) -> None:
    _backdrop(surface, app, "event", CARD)
    state = app.state
    code = state.current_team
    country = app.content.country(code)
    event = state.current_event
    x, width = CARD.x + 50, CARD.w - 100

    # header: team name in its color (and the seconds left, if there is a timer)
    hx = x
    flag = ui.flag(code, 40)
    if flag is not None:
        surface.blit(flag, flag.get_rect(midleft=(hx, CARD.y + 58)))
        hx += flag.get_width() + 14
    ui.text(surface, TEXT["turn"].format(name=country.name), "bold", 46, country.color,
            (hx, CARD.y + 58), "midleft")
    if config.TIMER_SECONDS > 0:
        _draw_timer(surface, app, x, width)

    # event title with its good/bad arrow, then the description
    y = CARD.y + (160 if config.TIMER_SECONDS > 0 else 120)
    good = event.kind == "good"
    ui.arrow(surface, (x + 26, y + 44), 54, good, ui.GAIN if good else ui.LOSS)
    ui.text(surface, event.title, "display", 72, ui.INK, (x + 70, y))
    rect = ui.paragraph(surface, event.description, "text", 38, ui.INK, (x, y + 104), width)
    _draw_options_and_card(surface, app, event, country, x, width, rect.bottom)


def _draw_timer(surface, app, x: int, width: int) -> None:
    """Seconds left at the top right and the timer bar (only when TIMER_SECONDS > 0)."""
    seconds = max(0, math.ceil(app.timer_left - 1e-6))
    last = app.timer_left <= 5
    if app.timer_left <= 0:
        ui.text(surface, TEXT["times_up"], "bold", 46, ui.LOSS, (CARD.right - 50, CARD.y + 58), "midright")
    else:
        num = ui.text(surface, TEXT["seconds_left"].format(seconds=seconds), "display", 56,
                      ui.LOSS if last else ui.INK, (CARD.right - 50, CARD.y + 58), "midright")
        if app.paused:
            ui.text(surface, TEXT["paused"], "bold", 38, ui.INK, (num.left - 30, CARD.y + 58), "midright")

    # timer bar
    track = pygame.Rect(x, CARD.y + 106, width, 24)
    pygame.draw.rect(surface, ui.LINE, track, border_radius=12)
    share = max(0.0, min(1.0, app.timer_left / max(1, config.TIMER_SECONDS)))
    if share > 0:
        fill = pygame.Rect(track.x, track.y, max(24, round(track.w * share)), track.h)
        pygame.draw.rect(surface, ui.LOSS if last else ui.INK, fill, border_radius=12)


def _draw_options_and_card(surface, app, event, country, x: int, width: int, top: int) -> None:
    """The three option buttons and, below them, the country card."""
    # three option buttons: text only, never the values
    y = top + 40
    bw = (width - 2 * 30) // 3
    bh = max(ui.Button.height_for(o, bw) for o in event.options)
    app.buttons = []
    for i, option in enumerate(event.options):
        button = ui.Button((x + i * (bw + 30), y, bw, bh), i + 1, option)
        button.draw(surface)
        app.buttons.append(button)

    # country card
    if app.show_card:
        y += bh + 44
        ui.text(surface, country.name, "bold", 42, ui.INK, (x, y))
        for i, fact in enumerate(country.card):
            ui.text(surface, fact, "text", 38, ui.INK, (x, y + 58 + i * 48))


# ----- Reveal ----------------------------------------------------------------------

def draw_reveal(surface, app) -> None:
    _backdrop(surface, app, "reveal", REVEAL, banknote=True)

    record = app.record
    country = app.content.country(record.code)
    event = app.content.event_by_id(record.event_id)
    result = app.content.result(record.event_id, record.code)
    x, width = REVEAL.x + 70, REVEAL.w - 140

    ui.text(surface, TEXT["chose"].format(name=country.name, option=event.options[record.choice]),
            "bold", 46, ui.INK, (x, REVEAL.y + 60))

    # the big number over the guilloche rosette
    center = (ui.W // 2, REVEAL.y + 330)
    rosette = ui.guilloche(400)
    surface.blit(rosette, rosette.get_rect(center=center))
    shown = app.count_value()
    num = ui.text(surface, ui.signed_pct(shown), "display", 160, ui.value_color(record.delta),
                  center, "center")
    ui.trend_mark(surface, (num.left - 60, center[1]), 80, record.delta)

    if app.counted:
        if record.best:
            seal = ui.stamp(TEXT["best_move"], country.color)
            surface.blit(seal, seal.get_rect(center=(num.right + 250, center[1] - 10)))
        else:
            names = TEXT["options_join"].join(event.options[i] for i in result.best_indices)
            ui.text(surface, TEXT["best_for"].format(name=country.name, options=names,
                                                     value=ui.signed_pct(result.best_value)),
                    "bold", 42, ui.INK, (x, REVEAL.y + 500))

    # all three options with their values for this country
    y = REVEAL.y + 590
    col_w = width // 3
    for i, option in enumerate(event.options):
        cx = x + i * col_w
        lines = ui.wrap(option, "text", 38, col_w - 40)[:2]
        for k, line in enumerate(lines):
            ui.text(surface, line, "text", 38, ui.INK, (cx, y + k * 44))
        vy = y + 100
        value = result.values[i]
        ui.trend_mark(surface, (cx + 16, vy + 22), 30, value)
        r = ui.text(surface, ui.signed_pct(value), "bold", 38, ui.value_color(value),
                    (cx + 42 if value else cx, vy))
        if i in result.best_indices:
            tag = ui.render(TEXT["best_tag"], "bold", 30, ui.INK)
            box = tag.get_rect(midleft=(r.right + 24, r.centery)).inflate(20, 6)
            pygame.draw.rect(surface, ui.INK, box, 3, border_radius=8)
            surface.blit(tag, tag.get_rect(center=box.center))

    ui.paragraph(surface, result.reason, "text", 38, ui.INK, (x, REVEAL.y + 760), width)
    ui.text(surface, TEXT["space_continue"], "bold", 34, ui.INK,
            (REVEAL.right - 50, REVEAL.bottom - 40), "bottomright", alpha=ui.pulse(app.scene_time))


# ----- Final results ------------------------------------------------------------------

def draw_final(surface, app) -> None:
    app.confetti.draw(surface)       # behind the text, so names stay readable
    state = app.state
    ranking = state.ranking()
    winners = [s.code for s in ranking if s.place == 1]
    names = [_name(app, c) for c in winners]
    if len(names) == 1:
        headline = TEXT["winner"].format(name=names[0])
    else:
        headline = TEXT["winners"].format(names=TEXT["names_join"].join(names))
    size = 120
    while size > 72 and ui.font("display", size).size(headline)[0] > 1700:
        size -= 8
    ui.text(surface, headline, "display", size, ui.INK, (ui.W // 2, 110), "center")
    ui.text(surface, TEXT["final_title"], "bold", 42, ui.INK, (360, 230))

    y = 300
    row_h = min(110, 640 // max(1, len(ranking)))
    for s in ranking:
        cy = y + row_h // 2
        if s.place == 1:
            ui.card(surface, pygame.Rect(330, y + 4, 1260, row_h - 8), ui.LINE, ui.INK, 4, 10)
        ui.text(surface, TEXT["place"].format(place=s.place), "bold", 46, ui.INK, (360, cy), "midleft")
        _country_line(surface, app, s.code, (430, cy))
        num = ui.text(surface, ui.signed_pct(s.score), "display", 56, ui.value_color(s.score),
                      (1170, cy), "midright")
        ui.trend_mark(surface, (num.left - 26, cy), 30, s.score)
        ui.text(surface, TEXT["best_moves"].format(best=s.best_moves, turns=s.turns),
                "text", 38, ui.INK, (1210, cy), "midleft")
        y += row_h
    if WEB:
        _prompt(surface, TEXT["download_log"], 915)
    _pulsing_button(surface, TEXT["final_continue"], (ui.W // 2, 1005), app.scene_time, False)


# ----- Sound check and credits ----------------------------------------------------------

def draw_sound(surface, app) -> None:
    """Big speaker and a shaking "SOUND ON!!!" before the game starts."""
    _cached(surface, app, _sound_static)
    on_photo = ui.background("sound") is not None
    t = app.scene_time
    shake = (9 * math.sin(t * 43), 6 * math.sin(t * 57 + 1.3))
    ui.text(surface, TEXT["sound_title"], "display", 150, ui.WHITE if on_photo else ui.INK,
            (ui.W // 2 + shake[0], 770 + shake[1]), "center")
    _pulsing_button(surface, TEXT["sound_continue"], (ui.W // 2, 985), t, on_photo)


def _sound_static(surface, app) -> None:
    _photo(surface, "sound", shade=90)
    center = (ui.W // 2, 370)
    pygame.draw.circle(surface, ui.WHITE, center, 260)
    pygame.draw.circle(surface, ui.INK, center, 260, 5)
    icon = ui.image("sound.png", 360)
    if icon is not None:
        surface.blit(icon, icon.get_rect(center=center))


def draw_credits(surface, app) -> None:
    """White screen with the team's photos and roles."""
    _cached(surface, app, _credits_static)
    _pulsing_button(surface, TEXT["play_again"], (ui.W // 2, 985), app.scene_time, False)


def _credits_static(surface, app) -> None:
    surface.fill(ui.WHITE)
    people = TEXT["credits"]
    photo_h, gap = 620, 160
    pictures = [ui.image(file, photo_h) for file, _role in people]
    widths = [p.get_width() if p else photo_h * 3 // 4 for p in pictures]
    x = (ui.W - sum(widths) - gap * (len(people) - 1)) // 2
    for (file, role), picture, width in zip(people, pictures, widths):
        frame = pygame.Rect(x, 80, width, photo_h)
        if picture is not None:
            surface.blit(picture, frame)
        else:
            ui.card(surface, frame, ui.LINE, None)
        pygame.draw.rect(surface, ui.INK, frame, 5)
        ui.text(surface, role, "display", 84, ui.INK, (frame.centerx, frame.bottom + 30), "midtop")
        x += width + gap


# ----- Overlays ----------------------------------------------------------------------

def draw_overlays(surface, app) -> None:
    if app.show_help:
        rows = TEXT["controls"]
        if config.TIMER_SECONDS <= 0:
            rows = [r for r in rows if r[0] != "P"]      # no timer, so nothing to pause
        box = pygame.Rect(1120, 120, 740, 110 + len(rows) * 54)
        ui.card(surface, box)
        ui.text(surface, TEXT["controls_title"], "bold", 42, ui.INK, (box.x + 30, box.y + 24))
        for i, (key, action) in enumerate(rows):
            y = box.y + 96 + i * 54
            ui.text(surface, key, "bold", 30, ui.INK, (box.x + 30, y))
            ui.text(surface, action, "text", 30, ui.INK, (box.x + 300, y))
    if app.toast_left > 0 and app.toast:
        label = ui.render(app.toast, "bold", 34, ui.INK)
        box = label.get_rect(center=(ui.W // 2, 1030)).inflate(60, 24)
        ui.card(surface, box)
        surface.blit(label, label.get_rect(center=box.center))
