# Africa Rising

Run a country. Grow its economy. A 15-minute classroom board game for five
teams, played on one laptop and a projector.

## Install (once)

1. Install Python 3.10 or newer from python.org (tick "Add Python to PATH").
2. Open a terminal in this folder and run:

   ```
   python -m pip install -r requirements.txt
   ```

   This installs pygame-ce (the maintained version of pygame; classic pygame
   has no build for the newest Python) and openpyxl (reads the Excel file).

## Run

- Windows: double-click `run_game.bat`.
- Or in a terminal:

  | Command | What it does |
  |---|---|
  | `python main.py` | Play fullscreen |
  | `python main.py --windowed` | Play in a window |
  | `python main.py --check` | Check content.xlsx and list every problem |
  | `python main.py --simulate` | Play 200 random games without a window to test the rules |

The game runs fully offline. Settings (rounds, timer, fullscreen, which screen
to use for the projector, volume, animation speed) are in `config.py`.

## Web version (play from a link)

The game also runs in a web browser, so it can be opened from a link without
installing anything: https://krisiny.github.io/africa-rising/

- Click once on the page to start (browsers only allow sound after a click),
  then use the keyboard as usual. F11 makes the browser fullscreen.
- The autosave is kept in the browser, so resume works after a reload.
- On the final results screen, press L to download game_log.csv.
- Esc twice saves the game and says you can close the tab (a web page can't
  close its own tab).
- Sound starts after the first click. Browsers need .ogg audio, so
  make_web.py converts .mp3/.wav music and sounds to .ogg automatically.
- After changing the game or content.xlsx, rebuild and publish it:

  ```
  python -m pip install pygbag soundfile
  python make_web.py
  ```

  This writes the website into `docs/`. Upload the change to GitHub (for
  example with GitHub Desktop: commit, then push) and the link shows the new
  version a minute later.

## Windows version without Python (USB backup)

```
python -m pip install pyinstaller
python make_exe.py
```

This makes `dist/Africa Rising/` and `dist/Africa Rising (Windows).zip`
(about 18 MB). Copy the folder or the zip to a USB stick; on any Windows PC,
unzip it and double-click `Africa Rising.exe`. Nothing needs to be installed.
Windows may say "Windows protected your PC" because the file isn't signed:
click "More info" and then "Run anyway". `content.xlsx` and `assets/` sit next
to the .exe, so they can still be edited or swapped there.

## Game styles

After "How to play" the game asks for a game style:

- **1 = Singleplayer**: pick one country (keys 1 to 5), then play
  SINGLE_ROUNDS turns (6, set in config.py) with just that country. The end
  screen shows "Your final progress": the GDP growth counting up and a bar
  that fills green to the right (gain) or red to the left (loss).
  A cartoon lion (game/mascot.py) reacts as the number counts up: it gets
  fatter and more surprised with gains, floats like a balloon above +5% and
  fills the screen at the maximum; with losses it gets thin and sad, and at
  -5% or lower only its skeleton is left.
- **2 = Multiplayer**: the classroom game with all teams, ROUNDS rounds (3).

Both end with the credits screen.

## Controls (presenter)

| Key | Action |
|---|---|
| Space or Enter | Start, roll the die, continue, skip an animation |
| 1 to 6 (roll screen) | Use a real die: type what it showed |
| 1, 2, 3 or click (event card) | Pick an option |
| U or Backspace | Undo the last choice (until the next roll) |
| P | Pause or resume the timer |
| C | Show or hide the country card |
| M | Mute or unmute |
| F11 | Fullscreen or window |
| H | Show or hide the controls |
| E twice | End the game now and show the results |
| Esc twice | Quit (the game is saved) |

Keys are ignored for 0.4 s after every screen change, so a double press can't
skip a screen by accident.

## Editing the content

All text and numbers are in `content.xlsx` (sheets `countries`, `events` and
`results`). Edit it in Excel, save, then run `python main.py --check`. It lists
every problem with sheet, row and column and says how to fix it. The game
shows the same list on screen instead of starting if something is wrong.

- Values are GDP changes in whole percentage points (+2, 0, -1).
- The best option is the one with the highest value; ties all count as best.
- The number of tiles on the board equals the number of events (4 to 12).
- `python make_content.py --force` rebuilds content.xlsx from the original
  data. Without `--force` it never overwrites your edited file.

## Adding sounds, music, flags and fonts

Everything in `assets/` is optional; the game runs without it.

- `assets/backgrounds/`: full-screen photos, one per screen: `title.jpg`,
  `howto.jpg`, `mode.jpg` (game style), `country.jpg` (singleplayer country
  choice), `sound.jpg` (sound check), `board.jpg`, `event.jpg` (question
  card) and `reveal.jpg` (answer). Replace any of them with another photo;
  other sizes are cropped to fill the screen. A missing photo just means a
  plain background on that screen.
- `assets/images/`: `sound.png` (the speaker on the sound check screen) and
  the credits photos `kristof.jpg` and `andrej.jpg`. The credits list (photo
  and the text under it) is `credits` in the TEXT dictionary in config.py.

- `assets/sounds/`: dice.wav, step.wav, good.wav, bad.wav, best.wav, tick.wav,
  win.wav, select.wav (a country is chosen in singleplayer) (.ogg also works). Missing sounds are replaced by simple beeps.
- `assets/music/background1.mp3`, `background2.mp3`, `background3.mp3`: the
  background playlist. The songs play one after another in name order, then
  start again, quietly throughout the game (volume: MUSIC_VOLUME in
  config.py). To add, remove or reorder songs, rename or add files that
  start with "background" (1 to 9 keeps the order simple).
- `assets/music/`: one loop per country named by its code (NG, EG, KE, ZA, CD)
  plus `title` for the title and final screens, as .ogg, .wav or .mp3, e.g.
  `KE.ogg`. Drop the files in; nothing else to change. Each team's loop plays
  quietly during its turn (volume: MUSIC_VOLUME in config.py).
- `assets/flags/`: NG.png and so on, shown next to the country names.
- `assets/fonts/`: Big Shoulders Display and Atkinson Hyperlegible are
  included (SIL Open Font License, see the OFL files). Without them the game
  uses Segoe UI or Arial.

## Files the game writes

- `savegame.json`: autosave after every turn. If the game is closed early, the
  next start offers to resume. Deleted when a game finishes or a new one starts.
- `game_log.csv`: one row per turn (round, country, event, choice, GDP change,
  best move) for discussing the results afterwards. Undone choices are not
  logged. Close it in Excel while playing, or new rows wait until it's closed.
- `error_log.txt`: only if something unexpected goes wrong.

## Translating

All on-screen text is in the `TEXT` dictionary in `config.py`; all game content
is in `content.xlsx`. Translate those two and the game is translated.

## Code

| File | What's in it |
|---|---|
| `main.py` | Entry point and command-line options |
| `config.py` | Settings and all on-screen text |
| `make_content.py` | Creates content.xlsx |
| `make_web.py` | Builds the web version into docs/ |
| `make_exe.py` | Builds the Windows version into dist/ |
| `game/content.py` | Loads and checks content.xlsx |
| `game/state.py` | The rules: moving, scoring, undo, ranking, saving (no pygame) |
| `game/simulate.py` | The `--simulate` test |
| `game/app.py` | Window, screens order, keys and timer |
| `game/screens.py` | Drawing of every screen |
| `game/board.py` | Board layout, tokens and scoreboard |
| `game/ui.py` | Colors, fonts, text, buttons and effects |
| `game/audio.py` | Sounds and music |
| `game/mascot.py` | The lion (singleplayer end screen) and the hippo with headphones (sound check) |
| `game/webstore.py` | Keeps the autosave in the browser (web version) |
