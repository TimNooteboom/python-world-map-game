"""Settings: window size, colours, map views, time limits, file locations and the list of modes."""

import os
import sys
from collections import namedtuple

# The project folder (the one with world_map.py), whatever folder this package is in.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def save_dir():
    """Where scores and progress are saved: next to the script, or a per-user folder in the packaged app."""
    if not getattr(sys, "frozen", False):
        return HERE
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = os.path.join(base, "World Map Game")
    os.makedirs(path, exist_ok=True)
    return path


# Bundled data: next to the script, or unpacked by PyInstaller into sys._MEIPASS.
RESOURCES = getattr(sys, "_MEIPASS", HERE)
DATA_FILE = os.path.join(RESOURCES, "countries.geojson")
STATES_FILE = os.path.join(RESOURCES, "us_states.geojson")  # Natural Earth states + capitals (and DC)
CAPITALS_FILE = os.path.join(RESOURCES, "capitals.json")  # country name -> capital and its lat/lon (Natural Earth)
FLAGS_DIR = os.path.join(RESOURCES, "flags")  # <iso code>.png, downloaded from flagcdn.com
# Leaderboards a new player starts with: snapshots of each scores file, bundled with the app.
STARTING_SCORES_DIR = os.path.join(RESOURCES, "starting_scores")

# Saved by the game (each player keeps their own).
SCORES_FILE = os.path.join(save_dir(), "scores.json")  # Countries game
STATE_SCORES_FILE = os.path.join(save_dir(), "state_scores.json")  # States game
GUESS_SCORES_FILE = os.path.join(save_dir(), "guess_scores.json")  # Guess the State
CAPITAL_GUESS_SCORES_FILE = os.path.join(save_dir(), "capital_guess_scores.json")  # Guess the Capital
FLAG_PROGRESS_FILE = os.path.join(save_dir(), "flag_progress.json")  # continents done perfectly


def starting_scores(name):
    return os.path.join(STARTING_SCORES_DIR, name)


WIDTH, HEIGHT = 1280, 800
PANEL_H = 120  # bottom panel with the input box
MAP_H = HEIGHT - PANEL_H
FPS = 60
ZOOM_TIME = 0.6  # seconds
TIME_LIMIT = 15 * 60  # seconds; the clock starts with the first correct answer
STATE_TIME_LIMIT = 5 * 60  # the same for the States game
WARNING_TIME = 30  # seconds left when the clock and its bar turn red

# Colours
OCEAN = (170, 205, 230)
LAND = (236, 228, 205)
LAND_HOVER = (250, 214, 140)
LAND_OTHER = (205, 205, 200)  # countries outside the selected continent
BORDER = (110, 110, 110)
FOUND = (70, 175, 90)
FOUND_LABEL = (0, 0, 0)  # background of the name tag on a found country (black)
OUTLINE = (140, 148, 165)  # border of quiz answers and Learn cards
SELECTED = (95, 145, 215)  # country whose flag is shown in Flags > Learn
MISSED = (215, 80, 80)
PANEL = (40, 44, 52)
TEXT = (240, 240, 240)
TEXT_DIM = (160, 165, 175)

# The view (lon/lat box) used when zooming into each continent.
# The tops leave room for the title, so it doesn't cover any countries.
CONTINENT_VIEWS = {
    "Africa": (-26, -37, 60, 47),
    "Europe": (-25, 34, 45, 76),
    "Asia": (25, -12, 150, 64),
    "North America": (-170, 6, -50, 75),
    "South America": (-92, -57, -30, 22),
    "Oceania": (110, -50, 210, 16),  # extends past the date line
}
WORLD_VIEW = (-180, -60, 180, 85)
# The USA map: the lower 48, with Alaska and Hawaii moved and scaled into insets in the bottom-left.
USA_VIEW = (-128, 15.5, -60, 54.5)  # room at the top for the title
INSETS = {
    "AK": lambda lon, lat: (-127 + (lon + 179) * 0.3, 17 + (lat - 51) * 0.53),
    "HI": lambda lon, lat: (-110 + (lon + 160.3), 17 + (lat - 18.9) * 0.88),
}
INSET_BOXES = [(-127.6, 16.3, -111.6, 28.6), (-110.8, 16.3, -103.8, 20.8)]  # frames drawn around them
# Guess the State can zoom into the Northeast when one of its small states is highlighted.
NE_VIEW = (-80.5, 37.3, -66.5, 47.6)
NE_SMALL = {"Rhode Island", "Delaware", "Connecticut", "New Jersey", "Massachusetts", "New Hampshire",
            "Vermont", "Maryland"}
# Top-to-bottom order of their tags in the column off the coast (States game and guess games).
NE_CALLOUT_ORDER = ["Vermont", "New Hampshire", "Massachusetts", "Rhode Island", "Connecticut", "New Jersey",
                    "Delaware", "Maryland"]

# Finishing a continent in the country game moves you on to the next unfinished one, in this order.
CONTINENT_ORDER = ["North America", "South America", "Europe", "Africa", "Asia", "Oceania"]

# Every mode: which map (scope) it uses, what it's about (subject), learn or game, and its titles.
Mode = namedtuple("Mode", "scope subject kind title label")
MODES = {
    "countries": Mode("world", "countries", "game", "Countries Game", "Countries: Game"),
    "countries_learn": Mode("world", "countries", "learn", "Countries Learn", "Countries: Learn"),
    "flags_learn": Mode("world", "flags", "learn", "Flags Learn", "Flags: Learn"),
    "flags_game": Mode("world", "flags", "game", "Flags Game", "Flags: Game"),
    "capitals_learn": Mode("world", "capitals", "learn", "Capitals Learn", "Capitals: Learn"),
    "capitals_game": Mode("world", "capitals", "game", "Capitals Game", "Capitals: Game"),
    "states": Mode("usa", "countries", "game", "States Game", "States: Game"),
    "states_learn": Mode("usa", "countries", "learn", "States Learn", "States: Learn"),
    "us_guess": Mode("guess", "guess", "game", "Guess the State", "Guess the State"),
    "us_guess_capital": Mode("guess_capital", "guess_capital", "game", "Guess the Capital", "Guess the Capital"),
    "us_flags_learn": Mode("usa", "flags", "learn", "State Flags Learn", "State Flags: Learn"),
    "us_flags_game": Mode("usa", "flags", "game", "State Flags Game", "State Flags: Game"),
    "us_capitals_learn": Mode("usa", "capitals", "learn", "State Capitals Learn", "State Capitals: Learn"),
    "us_capitals_game": Mode("usa", "capitals", "game", "State Capitals Game", "State Capitals: Game"),
}
# The Modes menu: sections, each with groups that open to show Learn / Game.
MENU = [("World", [("countries", "Countries", [("countries_learn", "Learn"), ("countries", "Game")]),
                   ("flags", "Flags", [("flags_learn", "Learn"), ("flags_game", "Game")]),
                   ("capitals", "Capitals", [("capitals_learn", "Learn"), ("capitals_game", "Game")])]),
        ("USA", [("states", "States", [("states_learn", "Learn"), ("states", "Game"), ("us_guess", "Guess the State")]),
                 ("us_flags", "State Flags", [("us_flags_learn", "Learn"), ("us_flags_game", "Game")]),
                 ("us_capitals", "State Capitals", [("us_capitals_learn", "Learn"), ("us_capitals_game", "Game"),
                                                    ("us_guess_capital", "Guess the Capital")])])]
