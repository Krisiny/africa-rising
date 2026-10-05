"""Settings and all on-screen text for Africa Rising.

To translate the game (for example to Slovak), edit only the TEXT dictionary
below and the texts in content.xlsx. Words in {curly braces} are filled in by
the game, so keep them, but you can move them around in the sentence.
"""

GAME_TITLE = "Africa Rising"
ROUNDS = 3
TIMER_SECONDS = 0        # seconds to answer; 0 = no timer (unlimited time)
SHOW_COUNTRY_CARD = True
FULLSCREEN = True
DISPLAY_INDEX = 0        # which screen to use if the projector is a second screen
SOUND_ON = True
MUSIC_VOLUME = 0.3        # background music, quieter than the sound effects (0 to 1)
CONTENT_FILE = "content.xlsx"
ANIMATION_SPEED = 1.0    # 2.0 = twice as fast


TEXT = {
    # Resume check
    "resume_found": "Unfinished game found.",
    "resume_prompt": "Press R to resume or N to start a new game.",

    # Title screen
    "subtitle": "Run a country. Grow its economy.",
    "press_start": "Press space to start",

    # How to play
    "how_title": "How to play",
    "how_step_1": "Roll the die and move.",
    "how_step_2": "Something happens in your country. Pick one of three options in {seconds} seconds.",
    "how_step_2_no_timer": "Something happens in your country. Pick one of three options.",
    "how_step_3": "Smart choices grow your GDP. The highest growth after {rounds} rounds wins.",
    "how_teams": "Teams",
    "how_continue": "Space to begin",

    # Board
    "round": "Round {round} of {rounds}",
    "turn": "{name}'s turn",
    "space_to_roll": "Space to roll",
    "start": "Start",
    "scoreboard_title": "GDP growth",

    # Event card
    "seconds_left": "{seconds} s",
    "times_up": "Time's up, pick now",
    "paused": "Paused",

    # Reveal
    "chose": "{name} chose {option}",
    "best_move": "Best move!",
    "best_for": "Best for {name}: {options} ({value})",
    "options_join": " or ",
    "best_tag": "best",
    "space_continue": "Space to continue",

    # Final results
    "final_title": "Final results",
    "winner": "{name} wins!",
    "winners": "{names} win!",
    "names_join": " and ",
    "best_moves": "{best} of {turns} best moves",
    "place": "{place}.",
    "play_again": "Press space to play again or Esc to quit.",
    "final_continue": "Press space to continue",
    "download_log": "Press L to download the game log",
    "log_downloaded": "Game log downloaded",
    "log_missing": "No game log yet",

    # Sound check before the game starts
    "sound_title": "SOUND ON!!!",
    "sound_continue": "Press space to play",

    # Credits after the final results: (photo in assets/images/, text under it)
    "credits": [
        ("kristof.jpg", "The Programmer"),
        ("andrej.jpg", "The CEO"),
    ],

    # Short messages at the bottom of the screen
    "press_e_again": "Press E again to end the game",
    "press_esc_again": "Press Esc again to quit",
    "sound_off": "Sound off",
    "sound_on": "Sound on",

    # Controls overlay (H)
    "controls_title": "Controls",
    "controls": [
        ("Space or Enter", "Start, roll, continue, skip"),
        ("1 to 6", "Enter a real die roll"),
        ("1, 2, 3 or click", "Pick an option"),
        ("U or Backspace", "Undo the last choice"),
        ("P", "Pause or resume the timer"),
        ("C", "Show or hide the country card"),
        ("M", "Mute or unmute"),
        ("F11", "Fullscreen or window"),
        ("H", "Show or hide this help"),
        ("E twice", "End the game now"),
        ("Esc twice", "Quit (the game is saved)"),
        ("L", "Download the game log (web, final screen)"),
    ],

    # Content error screen
    "error_title": "There is a problem with content.xlsx",
    "error_fix_hint": "Fix the file in Excel, save it, and start the game again.",
    "error_more": "...and {count} more. Run python main.py --check to see them all.",
    "error_quit": "Press Esc to quit.",

    # Unexpected error screen (last-resort safety net)
    "crash_title": "Something went wrong",
    "crash_body": "The game was saved. Start it again and press R to resume.",

    # Web version: shown after Esc twice (a web page can't close its own tab)
    "closed_title": "The game is saved",
    "closed_body": "You can close this browser tab now.",
    "closed_resume": "Press R to keep playing.",
}
