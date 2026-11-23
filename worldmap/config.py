"""Settings: window size, colors, map views, time limits, file locations and the list of modes."""

import os
import sys
from collections import namedtuple

# The project folder (the one with world_map.py), whatever folder this package is in.
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def save_dir():
    """Where scores and progress are saved: next to the script, or a per-user folder in the packaged app.

    The WORLD_MAP_SAVE_DIR environment variable overrides it (the tests use a temporary folder).
    """
    if os.environ.get("WORLD_MAP_SAVE_DIR"):
        return os.environ["WORLD_MAP_SAVE_DIR"]
    if not getattr(sys, "frozen", False):
        return HERE
    if sys.platform == "darwin":
        base = os.path.expanduser("~/Library/Application Support")
    elif sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
    path = os.path.join(base, "World Map Game")  # the game's old name: kept so saved scores carry over
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
STATE_FLAG_SCORES_FILE = os.path.join(save_dir(), "state_flag_scores.json")  # State Flags game
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

# Colors
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
NE_CALLOUT_X, NE_CALLOUT_TOP, NE_CALLOUT_STEP = 1060, 205, 30  # where that column is on screen

# Zoomed into Europe or Africa, countries smaller than TINY_COUNTRY_PX on screen get their tag in a column in
# the sea, joined by a line. In each column the tags line up on x (align "right": they end there, "left": they
# start there), between top and bottom; it takes the tiny countries whose label point is between x_from and x_to
# ("max_px" overrides what counts as tiny for that column).
TINY_COUNTRY_PX = 30
CALLOUT_STEP = 26  # gap between tags in a column
CALLOUT_COLUMNS = {
    "Europe": [dict(x=420, align="right", top=380, bottom=660, x_from=0, x_to=720),  # the Atlantic
               dict(x=900, align="left", top=555, bottom=665, x_from=720, x_to=WIDTH)],  # over Turkey
    "Africa": [dict(x=330, align="right", top=200, bottom=470, x_from=0, x_to=600),  # the Atlantic
               dict(x=960, align="left", top=260, bottom=660, x_from=600, x_to=WIDTH)],  # the Indian Ocean
    # Central America is a narrow strip, so all of it goes out into the Pacific, west of Mexico.
    "North America": [dict(x=600, align="right", top=464, bottom=664, x_from=0, x_to=870, max_px=50),
                      dict(x=1100, align="left", top=374, bottom=664, x_from=870, x_to=WIDTH)],  # the Atlantic
}

# State flags with the state's name written on them: where the name is, so the flag quizzes can paint over it
# (otherwise the flag gives the answer away). Only the name goes: other words ("Republic", "State of") stay. Positions are percentages of the flag's width and height:
#   box   (left, top, right, bottom)
#   ring  (center x, center y, inner radius, outer radius), radii in % of the height, for text written in a circle
#         (with a box too: only the part of the ring inside the box)
#   angles (from, to) the part of the ring the name is in, in degrees clockwise from the top
#   fill  a point on the background around the name; the text's pixels are repainted that color
#   color the background color itself (r, g, b), instead of fill
#   text  the letters' color, where it isn't simply the most common other color in the area
#   outline  the color of an outline around the letters, painted over where it touches them
#   keep  paint the whole area with the background except this color (for letters on a ribbon too busy to pick
#         out: the field around the ribbon is kept)
FLAG_NAME_COVERS = {
    "us-ar": [dict(box=(30, 40, 70, 52), fill=(50, 37))],
    "us-ca": [dict(box=(14, 65, 53.5, 80), fill=(8, 72))],  # "California" (not "Republic")
    "us-fl": [dict(ring=(49.5, 50, 17.5, 24.5), angles=(60.5, 115), color=(255, 185, 0), text=(169, 5, 52))],
    "us-ia": [dict(box=(38, 73, 62, 89), fill=(34, 80))],
    "us-id": [dict(box=(52.7, 73, 66, 84), fill=(50, 82.5), text=(252, 200, 3)),  # the ribbon's "Idaho"
              dict(ring=(49.8, 47.7, 14.6, 19.2), angles=(80, 138), color=(252, 209, 0), text=(1, 1, 0))],  # seal
    "us-il": [dict(box=(35, 80, 65, 91), fill=(30, 85))],
    "us-in": [dict(ring=(50, 27, 9, 15.5), box=(42.3, 10, 57.8, 23), color=(0, 15, 93), text=(255, 185, 0))],
    "us-ks": [dict(box=(23, 77, 77, 95), fill=(12, 85))],
    "us-ky": [dict(ring=(50.3, 50, 25.5, 35), angles=(23, 84), color=(0, 0, 102), text=(240, 192, 8))],
    "us-me": [dict(box=(41, 69.4, 59, 74.8), color=(158, 217, 255), keep=(0, 38, 100))],  # the ribbon
    "us-mt": [dict(box=(10, 11, 90, 29), fill=(5, 20))],
    # "Nebraska" around the seal (it sits a little farther out toward its end).
    "us-ne": [dict(ring=(50, 48, 29.9, 35.3), angles=(58, 96), color=(0, 42, 134), keep=(0, 42, 134)),
              dict(ring=(50, 48, 29.9, 35.9), angles=(96, 126), color=(0, 42, 134), keep=(0, 42, 134))],
    "us-nd": [dict(box=(28, 75, 72, 93), fill=(48, 90), text=(255, 255, 255))],  # on the red ribbon
    # "New Hampshire" around the seal, inside its gold circle: "New" sits a little nearer the middle.
    "us-nh": [dict(ring=(50.5, 46.8, 19.8, 24.8), angles=(26, 63), color=(0, 42, 134), text=(239, 174, 14)),
              dict(ring=(50.5, 46.8, 21.6, 26), angles=(63, 158), color=(0, 42, 134), text=(239, 174, 14))],
    "us-nv": [dict(box=(16, 33, 26, 38.3), color=(0, 51, 171), text=(171, 113, 11), outline=(80, 72, 62)),
              dict(box=(16, 33, 26, 38.3), color=(0, 51, 171), text=(250, 185, 0))],  # under the star
    "us-ok": [dict(box=(24, 75, 76, 90), fill=(12, 82))],
    "us-or": [dict(box=(53, 6, 90, 25.5), fill=(95, 15)),  # "Oregon" (not "State of"), clear of the eagle
              dict(box=(63, 25, 90, 29), fill=(95, 27))],
    "us-sd": [dict(ring=(49.6, 50, 27.5, 39.5), angles=(294, 60), fill=(10, 50)),  # around the sun
              dict(ring=(50, 49.8, 16.3, 21.2), angles=(341, 61), color=(255, 255, 255), text=(3, 42, 105))],  # seal
    # Over the seal's figure, in parts that keep clear of her helmet.
    "us-va": [dict(ring=(50.5, 60.4, 33, 38.8), box=(38, 15, 63, 27.3), color=(255, 255, 255), text=(125, 80, 35)),
              dict(ring=(50.5, 60.4, 33, 38.8), box=(38, 27.3, 45.6, 34), color=(255, 255, 255), text=(125, 80, 35)),
              dict(ring=(50.5, 60.4, 33, 38.8), box=(50.6, 27.3, 63, 34), color=(255, 255, 255), text=(125, 80, 35))],
    "us-wa": [dict(ring=(50, 49.5, 25.6, 31.3), angles=(55, 156), color=(255, 213, 32), text=(0, 0, 0))],  # seal
    "us-wi": [dict(box=(21, 4, 79, 21), fill=(10, 12))],
    "us-wv": [dict(box=(46.9, 16, 66, 27.5), color=(189, 12, 61), text=(72, 3, 22)),  # "West Virginia" on the
              dict(box=(46.9, 16, 66, 27.5), color=(189, 12, 61), text=(15, 0, 5))],  # ribbon (not "State of")
}

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
