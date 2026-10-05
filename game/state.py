"""Game rules for Africa Rising: moving, scoring, undo, ranking, autosave and the log.

No pygame in this file, so the rules can be tested without a window
(`python main.py --simulate`). Read this file to learn the rules:

* Every team starts on Start (position 0), just before tile 1.
* Phase "roll": the current team rolls a die and moves 1 to 6 tiles forward.
  After the last tile comes tile 1 again; Start is never landed on again.
  Then the phase is "choose".
* Phase "choose": the team picks option 1, 2 or 3 of the event on its tile.
  Its GDP growth changes by that option's value for its country. If no other
  option is worth more, it is a best move (tied options all count as best).
  Then it is the next team's turn.
* After every team has played `rounds` times the phase is "over". The last
  choice can still be undone. finish() makes the phase "finished": the
  results are final.
* Undo takes back the last choice until the next roll. The team is back on
  the same event card and its token does not move back.
* Ranking: highest GDP growth first, then most best moves. Teams that are
  still equal share a place (1, 1, 3).

Saving: persist() appends turns that can no longer be undone to game_log.csv
(each one exactly once) and writes savegame.json after every step.
"""

from __future__ import annotations

import csv
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

from game.content import Content, Event

START = 0                  # position of the Start marker, just before tile 1
DIE_SIDES = 6
OPTIONS = 3                # every event has three options (0, 1 and 2 in code)
SAVE_VERSION = 1
LOG_HEADER = ["round", "country", "event", "choice", "gdp_change", "best_move"]


def move(position: int, steps: int, n_tiles: int) -> list[int]:
    """Return the tiles a token visits when it moves `steps` forward from `position`.

    Position 0 is Start and the tiles are 1..n_tiles. The board is a loop: after
    the last tile comes tile 1 again (never Start). The last tile in the list is
    where the token lands. Example with 8 tiles: move(7, 3, 8) == [8, 1, 2].
    """
    return [(position + k - 1) % n_tiles + 1 for k in range(1, steps + 1)]


def _is_whole(value) -> bool:
    """True for a real whole number (True and False don't count)."""
    return isinstance(value, int) and not isinstance(value, bool)


@dataclass(frozen=True)
class TurnRecord:
    """One played turn: what a team rolled, where it landed and what it chose."""
    round: int            # 1-based round number
    code: str             # the team's country code, e.g. "KE"
    tile: int             # tile it landed on (1..n_tiles)
    event_id: str         # the event on that tile
    choice: int           # 0-based option index (0, 1 or 2)
    delta: int            # GDP change in percentage points
    best: bool            # True if no option was worth more for this country
    roll: int             # die value 1..6
    start_position: int   # where the token stood before the roll (0 = Start)


@dataclass(frozen=True)
class Standing:
    """One row of the final results."""
    place: int            # 1 = winner; equal teams share a place (1, 1, 3)
    code: str
    score: int            # GDP growth in %
    best_moves: int
    turns: int


class GameState:
    """Everything about one game. Change it only through the methods below."""

    def __init__(self, content: Content, rounds: int):
        if not content.countries or not content.events:
            raise ValueError("The content needs at least one country and one event.")
        if not _is_whole(rounds) or rounds < 1:
            raise ValueError(f"rounds must be a whole number of at least 1, not {rounds!r}.")
        self.content = content                  # used for lookups, never saved
        self.codes: list[str] = list(content.codes)   # turn order
        self.n_tiles: int = content.n_tiles
        self.rounds: int = rounds
        self.round: int = 1                     # becomes rounds + 1 when the game is over
        self.turn: int = 0                      # index into codes: whose turn it is
        self.phase: str = "roll"                # "roll", "choose", "over" or "finished"
        self.tile: int | None = None            # tile of the open event card ("choose" only)
        self.positions = {code: START for code in self.codes}
        self.scores = {code: 0 for code in self.codes}        # GDP growth in %
        self.best_moves = {code: 0 for code in self.codes}
        self.turns_played = {code: 0 for code in self.codes}
        self.history: list[TurnRecord] = []
        self.can_undo: bool = False             # True after a choice, until the next roll
        self.logged: int = 0                    # how many history records are in the log
        self.last_roll: int | None = None

    # ----- Looking at the game -------------------------------------------

    @property
    def current_team(self) -> str:
        """Code of the team whose turn it is.

        Right after choose() this is already the NEXT team; use last_record for
        the turn that was just played (reveal and score screens).
        """
        return self.codes[self.turn]

    @property
    def current_event(self) -> Event | None:
        """The open event card in phase "choose", otherwise None."""
        if self.phase != "choose":
            return None
        return self.content.event_at_tile(self.tile)

    @property
    def last_record(self) -> TurnRecord | None:
        """The most recent turn, or None before the first choice."""
        return self.history[-1] if self.history else None

    @property
    def display_round(self) -> int:
        """Round number for the header ("Round 3 of 3"), never above rounds."""
        return min(self.round, self.rounds)

    # ----- Playing --------------------------------------------------------

    def roll(self, value: int) -> list[int]:
        """Move the current team `value` tiles (1 to 6) and open the event there.

        The previous choice can't be undone any more. Returns the tiles the token
        hops over; the last one is where it lands.
        """
        self._require("roll", "roll")
        if not _is_whole(value) or not 1 <= value <= DIE_SIDES:
            raise ValueError(f"roll(): a die shows 1 to {DIE_SIDES}, not {value!r}.")
        code = self.current_team
        path = move(self.positions[code], value, self.n_tiles)
        self.positions[code] = path[-1]
        self.tile = path[-1]
        self.last_roll = value
        self.phase = "choose"
        self.can_undo = False
        return path

    def choose(self, option: int) -> TurnRecord:
        """The current team picks option 0, 1 or 2 of the open event card."""
        self._require("choose", "choose")
        if not _is_whole(option) or not 0 <= option < OPTIONS:
            raise ValueError(f"choose(): option must be 0, 1 or 2, not {option!r}.")
        code = self.current_team
        event = self.current_event
        result = self.content.result(event.id, code)
        record = TurnRecord(
            round=self.round,
            code=code,
            tile=self.tile,
            event_id=event.id,
            choice=option,
            delta=result.values[option],
            best=option in result.best_indices,
            roll=self.last_roll,
            start_position=self._position_before_roll(code),
        )
        self.scores[code] += record.delta
        self.best_moves[code] += 1 if record.best else 0
        self.turns_played[code] += 1
        self.history.append(record)
        self.can_undo = True
        self._next_turn()
        return record

    def undo(self) -> TurnRecord | None:
        """Take back the last choice (possible until the next roll).

        The team is back on the same event card: same tile, and its token stays
        there. Returns the record that was taken back, or None if there is
        nothing to undo.
        """
        if not self.can_undo:
            return None
        self._require("undo", "roll", "over")
        record = self.history.pop()
        self.scores[record.code] -= record.delta
        self.best_moves[record.code] -= 1 if record.best else 0
        self.turns_played[record.code] -= 1
        self.round = record.round
        self.turn = self.codes.index(record.code)
        self.tile = record.tile
        self.last_roll = record.roll
        self.phase = "choose"
        self.can_undo = False
        return record

    def end_now(self) -> None:
        """End the game early (E pressed twice) and make the results final.

        A turn that was rolled but not chosen yet is dropped: the token stays
        where it landed and no score changes.
        """
        if self.phase == "finished":
            raise ValueError("end_now(): the game is already finished.")
        self._close()

    def finish(self) -> None:
        """Make the results final after the last turn: no more undo.

        Calling it again on a finished game does nothing.
        """
        self._require("finish", "over", "finished")
        self._close()

    # ----- Results ----------------------------------------------------------

    def ranking(self) -> list[Standing]:
        """All teams from first to last.

        Highest GDP growth first, then most best moves, then turn order.
        A team's place is 1 + the number of teams that did strictly better,
        so equal teams share a place and the next place is skipped (1, 1, 3).
        """
        def strength(code: str) -> tuple[int, int]:
            return (self.scores[code], self.best_moves[code])

        # sorted() keeps the original (turn) order for equal teams.
        order = sorted(self.codes, key=strength, reverse=True)
        standings = []
        for code in order:
            better = sum(1 for other in self.codes if strength(other) > strength(code))
            standings.append(Standing(place=1 + better, code=code, score=self.scores[code],
                                      best_moves=self.best_moves[code],
                                      turns=self.turns_played[code]))
        return standings

    def winners(self) -> list[str]:
        """Codes of the team(s) in first place."""
        return [s.code for s in self.ranking() if s.place == 1]

    def final_records(self) -> list[TurnRecord]:
        """Turns that can't be undone any more. Only these go into the log."""
        if self.can_undo:
            return self.history[:-1]
        return list(self.history)

    # ----- Saving -----------------------------------------------------------

    def to_dict(self) -> dict:
        """The whole game as plain data for savegame.json (the content is not included)."""
        return {
            "version": SAVE_VERSION,
            "codes": list(self.codes),
            "n_tiles": self.n_tiles,
            "rounds": self.rounds,
            "round": self.round,
            "turn": self.turn,
            "phase": self.phase,
            "tile": self.tile,
            "positions": dict(self.positions),
            "scores": dict(self.scores),
            "best_moves": dict(self.best_moves),
            "turns_played": dict(self.turns_played),
            "history": [asdict(record) for record in self.history],
            "can_undo": self.can_undo,
            "logged": self.logged,
            "last_roll": self.last_roll,
        }

    @classmethod
    def from_dict(cls, data: dict, content: Content) -> GameState:
        """Rebuild a saved game. Raises ValueError if it doesn't fit the content.

        The check is simple: play the saved rolls and choices again with the
        rules above. The result must be exactly the saved game, so a save for
        other countries or events, or with numbers that don't add up, is refused.
        """
        try:
            return cls._replay(data, content)
        except ValueError:
            raise
        except (KeyError, TypeError, IndexError, AttributeError) as error:
            raise ValueError(f"The saved game is damaged ({type(error).__name__}: {error}).") from error

    @classmethod
    def _replay(cls, data: dict, content: Content) -> GameState:
        if not isinstance(data, dict) or data.get("version") != SAVE_VERSION:
            raise ValueError("This is not a saved game this version can read.")
        if data["codes"] != content.codes:
            raise ValueError("The saved game is for other countries or another turn order.")
        if data["n_tiles"] != content.n_tiles:
            raise ValueError("The saved game is for a board with a different number of tiles.")

        state = cls(content, data["rounds"])
        try:
            for saved in data["history"]:          # play every saved turn again
                state.roll(saved["roll"])
                state.choose(saved["choice"])
            if data["phase"] == "choose":          # the team had rolled but not chosen yet
                state.roll(data["last_roll"])
            elif data["phase"] == "finished":      # ended early, maybe right after a roll
                if data["positions"] != state.positions or data["last_roll"] != state.last_roll:
                    state.roll(data["last_roll"])
                state.end_now()
        except ValueError as error:
            raise ValueError(f"The saved game breaks the rules: {error}") from error

        logged = data["logged"]
        if not _is_whole(logged) or not 0 <= logged <= len(state.final_records()):
            raise ValueError("The saved game has a wrong number of logged turns.")
        state.logged = logged

        expected = state.to_dict()
        wrong = [key for key in expected if data.get(key) != expected[key]]
        wrong += [key for key in data if key not in expected]
        if wrong:
            raise ValueError(f"The saved game doesn't add up: {', '.join(wrong)}.")
        return state

    # ----- Helpers ------------------------------------------------------------

    def _require(self, action: str, *phases: str) -> None:
        """Raise a clear error when a method is used in the wrong phase (a bug in the UI)."""
        if self.phase not in phases:
            allowed = " or ".join(repr(p) for p in phases)
            raise ValueError(f"{action}() is only allowed in phase {allowed}, "
                             f"but the phase is {self.phase!r}.")

    def _position_before_roll(self, code: str) -> int:
        """Where a team stood before its current roll: its last tile, or Start."""
        for record in reversed(self.history):
            if record.code == code:
                return record.tile
        return START

    def _next_turn(self) -> None:
        """Hand the die to the next team; after the last team a new round starts."""
        self.tile = None
        self.turn += 1
        if self.turn == len(self.codes):
            self.turn = 0
            self.round += 1
        self.phase = "over" if self.round > self.rounds else "roll"

    def _close(self) -> None:
        self.phase = "finished"
        self.tile = None
        self.can_undo = False


# ----- Files: savegame.json and game_log.csv ----------------------------------

def save_game(state: GameState, path: Path) -> None:
    """Write the game to `path` safely (may raise OSError).

    It first writes a temporary file and then swaps it in, so a crash halfway
    never leaves a broken save behind.
    """
    path = Path(path)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(state.to_dict(), indent=2), encoding="utf-8")
    os.replace(temp, path)


def load_game(path: Path, content: Content) -> GameState | None:
    """Return the saved game, or None if there is none or it can't be used.

    None also when the file is damaged, belongs to other content, or holds a
    game that is already finished. Never raises.
    """
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        state = GameState.from_dict(data, content)
    except Exception:          # missing, locked, damaged or for other content
        return None
    if state.phase == "finished":
        return None            # nothing left to resume
    return state


def delete_save(path: Path) -> bool:
    """Delete the save file if there is one. Returns False if that failed. Never raises."""
    try:
        Path(path).unlink(missing_ok=True)
        return True
    except Exception:
        return False


def append_log(path: Path, records: list[TurnRecord], content: Content) -> bool:
    """Add one CSV row per record, with the header first if the file is new.

    Returns False if writing failed (for example the file is open in Excel),
    so the caller can try again later. Never raises.
    """
    if not records:
        return True
    try:
        path = Path(path)
        is_new = not path.exists() or path.stat().st_size == 0
        rows = [_log_row(record, content) for record in records]
        # utf-8-sig lets Excel show accented letters correctly.
        with path.open("a", encoding="utf-8-sig", newline="") as file:
            writer = csv.writer(file)
            if is_new:
                writer.writerow(LOG_HEADER)
            writer.writerows(rows)
        return True
    except Exception:
        return False


def _log_row(record: TurnRecord, content: Content) -> list:
    event = content.event_by_id(record.event_id)
    return [
        record.round,
        content.country(record.code).name,
        event.title,
        event.options[record.choice],
        record.delta,
        "yes" if record.best else "no",
    ]


def persist(state: GameState, save_path: Path, log_path: Path) -> bool:
    """Write the game to disk. The app calls this after every change. Never raises.

    1. Append the turns that became final to the log (each one exactly once).
    2. Save the game, or delete the save once the game is finished.
    Returns True if both worked. Anything that failed is tried again next time.
    """
    try:
        new_records = state.final_records()[state.logged:]
        logged_ok = append_log(log_path, new_records, state.content)
        if logged_ok:
            state.logged += len(new_records)
        if state.phase == "finished":
            saved_ok = delete_save(save_path)
        else:
            save_game(state, save_path)
            saved_ok = True
        return logged_ok and saved_ok
    except Exception:
        return False
