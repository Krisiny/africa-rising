"""Headless test of the rules: `python main.py --simulate`.

Plays many random games with game/state.py (no window, no pygame) and checks
after every step that the rules were applied correctly: the right GDP value,
scores that add up, undo, save/load and the log. Uses a temporary folder, so
the real savegame.json and game_log.csv are never touched.
"""

from __future__ import annotations

import csv
import json
import random
import tempfile
import time
from pathlib import Path

from game.content import Content
from game.state import (START, GameState, delete_save, load_game, move, persist)

MAX_REPORTED = 20


class Checker:
    """Collects failed checks instead of stopping at the first one."""

    def __init__(self):
        self.failures: list[str] = []

    def check(self, ok: bool, message: str) -> None:
        if not ok:
            self.failures.append(message)


def run(content: Content, games: int = 200, seed: int = 12345) -> bool:
    """Play `games` random games and print a short summary. True if all checks passed."""
    started = time.perf_counter()
    rng = random.Random(seed)
    c = Checker()
    turns = 0
    with tempfile.TemporaryDirectory() as folder:
        folder = Path(folder)
        for number in range(games):
            try:
                turns += _play_one(content, rng, c, folder, number)
            except Exception as error:     # a rule broke so badly that the game stopped
                c.check(False, f"game {number + 1}: {type(error).__name__}: {error}")
        try:
            _scenarios(content, c, folder)
        except Exception as error:
            c.check(False, f"scenarios: {type(error).__name__}: {error}")
    seconds = time.perf_counter() - started

    if c.failures:
        print(f"Simulated {games} games ({turns} turns): {len(c.failures)} check(s) FAILED.")
        for line in c.failures[:MAX_REPORTED]:
            print(" -", line)
        if len(c.failures) > MAX_REPORTED:
            print(f" ...and {len(c.failures) - MAX_REPORTED} more.")
        return False
    print(f"Simulated {games} games ({turns} turns) in {seconds:.1f} s: all checks passed.")
    return True


def _play_one(content: Content, rng: random.Random, c: Checker, folder: Path, number: int) -> int:
    """One random game with undo, save/load and maybe an early end. Returns turns played."""
    rounds = rng.choice([1, 2, 3, 3, 3])
    save = folder / f"save{number}.json"
    log = folder / f"log{number}.csv"
    state = GameState(content, rounds)
    end_early_at = rng.randrange(1, rounds * len(content.codes) + 1) if rng.random() < 0.05 else None
    tag = f"game {number + 1}"

    while state.phase in ("roll", "over"):
        if state.phase == "over":
            if rng.random() < 0.3:       # undo the very last choice, then choose again
                _undo_and_check(state, c, tag)
                _choose(state, rng, c, tag)
                persist(state, save, log)
            break
        # roll
        code = state.current_team
        before = state.positions[code]
        value = rng.randint(1, 6)
        path = state.roll(value)
        c.check(path == move(before, value, content.n_tiles), f"{tag}: wrong hop path")
        c.check(START not in path and state.positions[code] == path[-1], f"{tag}: bad landing")
        persist(state, save, log)

        if end_early_at is not None and len(state.history) + 1 >= end_early_at and rng.random() < 0.5:
            state.end_now()                       # E pressed during the event card
            persist(state, save, log)
            break

        _choose(state, rng, c, tag)
        if rng.random() < 0.2:                    # undo, then choose again
            _undo_and_check(state, c, tag)
            _choose(state, rng, c, tag)
        persist(state, save, log)

        if rng.random() < 0.1:                    # quit and resume
            loaded = load_game(save, content)
            c.check(loaded is not None and loaded.to_dict() == state.to_dict(),
                    f"{tag}: save/load round trip changed the game")
            if loaded is not None:
                state = loaded

        if end_early_at is not None and len(state.history) >= end_early_at:
            state.end_now()
            persist(state, save, log)
            break
        _check_totals(state, c, tag)

    if state.phase != "finished":
        c.check(state.phase == "over", f"{tag}: game stopped in phase {state.phase}")
        c.check(len(state.history) == rounds * len(content.codes), f"{tag}: wrong number of turns")
        state.finish()
        persist(state, save, log)

    _check_totals(state, c, tag)
    c.check(not save.exists(), f"{tag}: save not deleted after the game finished")
    c.check(_log_rows(log) == len(state.history), f"{tag}: log has {_log_rows(log)} rows, "
                                                  f"expected {len(state.history)}")
    _check_ranking(state, c, tag)
    return len(state.history)


def _choose(state: GameState, rng: random.Random, c: Checker, tag: str) -> None:
    code, tile = state.current_team, state.tile
    event = state.content.event_at_tile(tile)
    result = state.content.result(event.id, code)
    option = rng.randrange(3)
    score_before = state.scores[code]
    record = state.choose(option)
    c.check(record.delta == result.values[option], f"{tag}: wrong GDP change for {code} on tile {tile}")
    c.check(state.scores[code] == score_before + result.values[option], f"{tag}: score not updated")
    c.check(record.best == (result.values[option] == max(result.values)), f"{tag}: wrong best flag")


def _undo_and_check(state: GameState, c: Checker, tag: str) -> None:
    after = state.to_dict()
    record = state.undo()
    c.check(record is not None, f"{tag}: undo returned nothing")
    c.check(state.phase == "choose" and state.tile == record.tile, f"{tag}: undo did not reopen the card")
    redo = GameState.from_dict(state.to_dict(), state.content)   # undo state must be a valid save too
    c.check(redo.to_dict() == state.to_dict(), f"{tag}: undo state does not survive save/load")
    c.check(after["history"][:-1] == state.to_dict()["history"], f"{tag}: undo changed older turns")


def _check_totals(state: GameState, c: Checker, tag: str) -> None:
    for code in state.codes:
        mine = [r for r in state.history if r.code == code]
        c.check(state.scores[code] == sum(r.delta for r in mine), f"{tag}: {code} score doesn't add up")
        c.check(state.best_moves[code] == sum(r.best for r in mine), f"{tag}: {code} best moves wrong")
        c.check(state.turns_played[code] == len(mine), f"{tag}: {code} turn count wrong")
        position = START
        for r in mine:
            c.check(r.start_position == position, f"{tag}: {code} start position wrong")
            position = move(position, r.roll, state.n_tiles)[-1]
            c.check(r.tile == position, f"{tag}: {code} landed on the wrong tile")


def _check_ranking(state: GameState, c: Checker, tag: str) -> None:
    ranking = state.ranking()
    keys = [(s.score, s.best_moves) for s in ranking]
    c.check(keys == sorted(keys, reverse=True), f"{tag}: ranking not sorted")
    for s in ranking:
        better = sum(1 for k in keys if k > (s.score, s.best_moves))
        c.check(s.place == better + 1, f"{tag}: wrong place for {s.code}")


def _log_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8-sig", newline="") as f:
        return max(0, len(list(csv.reader(f))) - 1)


def _scenarios(content: Content, c: Checker, folder: Path) -> None:
    """A few hand-made situations that random play may not hit."""
    n = content.n_tiles
    c.check(move(0, 3, n) == [1, 2, 3], "move from Start")
    c.check(move(n - 1, 3, n) == [n, 1, 2], "wrap-around from the last tile")

    # Ties in the ranking: equal score -> best moves decide; still equal -> shared place.
    state = GameState(content, 1)
    a, b, d = state.codes[0], state.codes[1], state.codes[2]
    state.scores.update({a: 3, b: 3, d: 3})
    state.best_moves.update({a: 1, b: 2, d: 1})
    places = {s.code: s.place for s in state.ranking()}
    c.check(places[b] == 1 and places[a] == 2 and places[d] == 2, "tie-break by best moves")
    others = [s for s in state.ranking() if s.code not in (a, b, d)]
    c.check(all(s.place == 4 for s in others), "place after a shared place is skipped")

    # Tied best options all count as best.
    for (event_id, code), result in content.results.items():
        if len(result.best_indices) > 1:
            c.check(all(result.values[i] == max(result.values) for i in result.best_indices),
                    "tied best options")

    # E pressed during the event card: the unfinished turn is dropped.
    state = GameState(content, 3)
    state.roll(4)
    state.end_now()
    c.check(state.phase == "finished" and not state.history and state.positions[state.codes[0]] == 4,
            "end_now during choose")

    # Undo is not possible after the next roll.
    state = GameState(content, 3)
    state.roll(2)
    state.choose(0)
    state.roll(1)
    c.check(state.undo() is None, "undo after the next roll must do nothing")

    # Singleplayer: one country, 6 rounds, saved and loaded with the one-country content.
    code = content.codes[2]
    solo = content.only(code)
    c.check(solo.codes == [code] and all(k[1] == code for k in solo.results), "one-country content")
    state = GameState(solo, 6)
    single_save = folder / "single.json"
    for turn in range(6):
        state.roll(1 + turn % 6)
        state.choose(turn % 3)
        persist(state, single_save, folder / "single.csv")
        if turn == 3:
            loaded = load_game(single_save, solo)
            c.check(loaded is not None and loaded.to_dict() == state.to_dict(), "singleplayer save/load")
            c.check(load_game(single_save, content) is None, "singleplayer save must not load as multiplayer")
    c.check(state.phase == "over" and len(state.history) == 6, "singleplayer plays 6 turns")
    c.check(state.scores[code] == sum(r.delta for r in state.history), "singleplayer score adds up")

    # Bad save files are refused.
    bad = folder / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    c.check(load_game(bad, content) is None, "corrupt save must be refused")
    c.check(load_game(folder / "missing.json", content) is None, "missing save must be refused")
    state = GameState(content, 3)
    state.roll(5)
    data = state.to_dict()
    data["codes"] = list(reversed(data["codes"]))
    bad.write_text(json.dumps(data), encoding="utf-8")
    c.check(load_game(bad, content) is None, "save for other countries must be refused")
    data = state.to_dict()
    data["scores"][state.codes[0]] = 99
    bad.write_text(json.dumps(data), encoding="utf-8")
    c.check(load_game(bad, content) is None, "save with wrong totals must be refused")
    c.check(delete_save(folder / "missing.json"), "deleting a missing save is fine")
