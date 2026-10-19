"""Interactive world map quiz.

Click a continent to zoom in, then type the names of its countries.
Each correctly named country turns green.

Controls (continent view):
    Type + Enter / auto-check  name a country
    Esc / "Back" button        return to the world map
    "Give up" button           reveal the countries you missed (in red)

The "Modes" menu (top left) switches between modes:
    Countries > Learn  hover over a country to see its name and flag
    Countries > Game   the country-naming game above
    Flags > Learn   click a continent, then hover over a country to see its flag; "Practice test" quizzes you
    Flags > Game    pick the right flag for every country in a continent; all right turns it green
    Capitals > Learn / Game   the same, for capital cities

The USA section of the menu has the same modes for the 50 states (States, State Flags, State Capitals),
on a map of the USA with Alaska and Hawaii as insets, and its own scoreboard. "Guess the State" highlights
one state at a time to name (one try each), timed, with its own scoreboard too; "Guess the Capital" is the
same game where you type the highlighted state's capital.
"""

import json
import math
import os
import random
import sys
import time
from collections import namedtuple
import unicodedata

import pygame

HERE = os.path.dirname(os.path.abspath(__file__))


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
SCORES_FILE = os.path.join(save_dir(), "scores.json")  # saved high scores (kept between games)
# Leaderboards a new player starts with: snapshots of each scores file, bundled with the app.
STARTING_SCORES_DIR = os.path.join(RESOURCES, "starting_scores")


def starting_scores(name):
    return os.path.join(STARTING_SCORES_DIR, name)
STATE_SCORES_FILE = os.path.join(save_dir(), "state_scores.json")  # scoreboard of the States game
GUESS_SCORES_FILE = os.path.join(save_dir(), "guess_scores.json")  # scoreboard of Guess the State
CAPITAL_GUESS_SCORES_FILE = os.path.join(save_dir(), "capital_guess_scores.json")  # ... of Guess the Capital
STATES_FILE = os.path.join(RESOURCES, "us_states.geojson")  # Natural Earth states + capitals (and DC)
# Continents done perfectly in Flags > Game ("perfect") and Capitals > Game ("capitals").
FLAG_PROGRESS_FILE = os.path.join(save_dir(), "flag_progress.json")
CAPITALS_FILE = os.path.join(RESOURCES, "capitals.json")  # country name -> capital and its lat/lon (Natural Earth)
FLAGS_DIR = os.path.join(RESOURCES, "flags")  # <iso code>.png, downloaded from flagcdn.com

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

# Island nations that Natural Earth files under "Seven seas (open ocean)", plus Cyprus (filed under Asia).
CONTINENT_FIXES = {"Seychelles": "Africa", "Mauritius": "Africa", "Maldives": "Asia",
                   "Cyprus": "Europe", "N. Cyprus": "Europe"}

# Partially recognised states that are drawn but not part of the quiz.
NOT_IN_QUIZ = {"Somaliland", "Northern Cyprus"}

# Extra accepted spellings, keyed by the Natural Earth ADMIN name.
ALIASES = {
    "United States of America": ["usa", "us", "united states", "america"],
    "United Kingdom": ["uk", "great britain", "britain", "england"],
    "Democratic Republic of the Congo": ["drc", "dr congo", "congo kinshasa"],
    "Republic of the Congo": ["congo", "congo brazzaville", "republic of congo"],
    "Ivory Coast": ["cote divoire"],
    "Czechia": ["czech republic"],
    "eSwatini": ["swaziland", "eswatini"],
    "Myanmar": ["burma"],
    "North Macedonia": ["macedonia"],
    "Timor-Leste": ["east timor"],
    "Cabo Verde": ["cape verde"],
    "Turkey": ["turkiye"],
    "United Republic of Tanzania": ["tanzania"],
    "Republic of Serbia": ["serbia"],
    "The Bahamas": ["bahamas"],
    "Federated States of Micronesia": ["micronesia"],
    "Vatican": ["vatican city", "holy see"],
    "South Korea": ["korea", "republic of korea"],
    "North Korea": ["dprk"],
    "Bosnia and Herzegovina": ["bosnia"],
    "Palestine": ["palestinian territories", "state of palestine"],
    "Russia": ["russian federation"],
    "Laos": ["lao"],
    "Guinea-Bissau": ["guinea bissau"],
    "Saint Kitts and Nevis": ["st kitts and nevis"],
    "Saint Lucia": ["st lucia"],
    "Saint Vincent and the Grenadines": ["st vincent and the grenadines", "st vincent"],
    "Sao Tome and Principe": ["sao tome"],
    "Trinidad and Tobago": ["trinidad"],
    "Antigua and Barbuda": ["antigua"],
    "United Arab Emirates": ["uae"],
    "Central African Republic": ["car"],
}


def normalise(name):
    """Lowercase, strip accents and punctuation so 'Côte d'Ivoire' == 'cote divoire'."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.lower().replace("&", " and ").replace("'", "")
    name = "".join(c if c.isalnum() else " " for c in name)
    words = name.split()
    if words and words[0] == "the":
        words = words[1:]
    words = ["saint" if w == "st" else w for w in words]
    return " ".join(words)


def fold(text):
    """Lowercase and strip accents character by character (keeps the length the same)."""
    return "".join(unicodedata.normalize("NFKD", ch)[0].lower() for ch in text)


class Country:
    def __init__(self, feature):
        p = feature["properties"]
        self.name = p["NAME"] if p["ADMIN"] == "China" else (p["NAME_EN"] or p["ADMIN"])
        self.admin = p["ADMIN"]
        self.continent = CONTINENT_FIXES.get(p["NAME"], p["CONTINENT"])
        # Only independent countries count (not e.g. Greenland, Puerto Rico, Hong Kong).
        self.in_quiz = self.admin == "Palestine" or (
            p["SOVEREIGNT"] == p["ADMIN"] and p["TYPE"] != "Indeterminate" and self.admin not in NOT_IN_QUIZ
        )

        geom = feature["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        self.rings = [poly[0] for poly in polys]  # outer rings only (holes are rare/tiny)
        lons = [pt[0] for r in self.rings for pt in r]
        lats = [pt[1] for r in self.rings for pt in r]
        self.bbox = (min(lons), min(lats), max(lons), max(lats))
        self.label_pt = (p["LABEL_X"], p["LABEL_Y"])  # good spot to write the name
        # Long names use the map's abbreviation (e.g. "Dem. Rep. Congo") to save space.
        self.short_name = p["NAME"] if len(p["NAME_EN"] or "") > 18 else (p["NAME_EN"] or p["NAME"])

        names = {p["NAME"], p["NAME_LONG"], p["ADMIN"], p["NAME_EN"], p["NAME_SORT"],
                 p.get("NAME_CIAWF") or "", p.get("FORMAL_EN") or ""}
        names.update(ALIASES.get(p["ADMIN"], []))
        self.accepted = {normalise(n) for n in names if n}

        self.code = p["ISO_A2_EH"].lower()  # two-letter code, used for the flag image
        self.found = False

    def contains(self, lon, lat):
        """Point-in-polygon test on the country's outer rings."""
        x0, y0, x1, y1 = self.bbox
        if not (x0 <= lon <= x1 and y0 <= lat <= y1):
            return False
        for ring in self.rings:
            inside = False
            j = len(ring) - 1
            for i in range(len(ring)):
                xi, yi = ring[i]
                xj, yj = ring[j]
                if (yi > lat) != (yj > lat) and lon < (xj - xi) * (lat - yi) / (yj - yi) + xi:
                    inside = not inside
                j = i
            if inside:
                return True
        return False


class State(Country):
    """A US state, with the same attributes as a Country so every mode works with it."""

    def __init__(self, feature):
        p = feature["properties"]
        self.name = self.short_name = self.admin = p["name"]
        self.continent = "USA"
        self.in_quiz = p["postal"] != "DC"  # DC is drawn but isn't a state
        self.code = "us-" + p["postal"].lower()  # flag file, e.g. us-tx.png
        move = INSETS.get(p["postal"], lambda lon, lat: (lon, lat))
        geom = feature["geometry"]
        polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
        self.rings = [[move(lon, lat) for lon, lat in poly[0]] for poly in polys]
        lons = [pt[0] for r in self.rings for pt in r]
        lats = [pt[1] for r in self.rings for pt in r]
        self.bbox = (min(lons), min(lats), max(lons), max(lats))
        self.label_pt = move(p["label_lon"], p["label_lat"])
        self.capital = p["capital"]
        self.capital_pt = move(p["capital_lon"], p["capital_lat"])
        self.accepted = {normalise(self.name)}
        self.found = False
        self.missed = False  # Guess the State: answered wrong or skipped


class View:
    """Maps lon/lat to screen pixels for a given lon/lat box, keeping aspect ratio."""

    def __init__(self, box):
        self.box = box
        lon0, lat0, lon1, lat1 = box
        self.wrap = lon1 > 180
        self.k = math.cos(math.radians((lat0 + lat1) / 2))  # squash longitudes away from the equator
        w, h = (lon1 - lon0) * self.k, lat1 - lat0
        self.scale = min(WIDTH / w, MAP_H / h)
        self.cx = (lon0 + lon1) / 2 * self.k
        self.cy = (lat0 + lat1) / 2

    def project_ring(self, ring):
        # Shift whole rings that sit west of 0° so islands just past the date line
        # appear next to their Pacific neighbours (only in views that cross 180°).
        shift = 360 if self.wrap and all(lon <= 0 for lon, _ in ring) else 0
        return [self.to_screen(lon + shift, lat) for lon, lat in ring]

    def to_screen(self, lon, lat):
        return (WIDTH / 2 + (lon * self.k - self.cx) * self.scale,
                MAP_H / 2 - (lat - self.cy) * self.scale)

    def to_lonlat(self, x, y):
        return ((x - WIDTH / 2) / self.scale + self.cx) / self.k, self.cy - (y - MAP_H / 2) / self.scale

    def screen_rect(self, box):
        """Screen rectangle covering a lon/lat box (used for the zoom animation)."""
        x0, y0 = self.to_screen(box[0], box[3])
        x1, y1 = self.to_screen(box[2], box[1])
        return pygame.Rect(x0, y0, x1 - x0, y1 - y0)


def draw_map(countries, view, colour_for, highlight=None):
    """Draw the map; returns the surface and the [(x, y, country)] dots drawn for tiny countries."""
    surf = pygame.Surface((WIDTH, MAP_H))
    surf.fill(OCEAN)
    small = []
    for c in countries:
        colour = colour_for(c)
        if c is highlight:
            colour = LAND_HOVER
        rings = [view.project_ring(ring) for ring in c.rings]
        for pts in rings:
            xs = [p[0] for p in pts]
            if max(xs) < 0 or min(xs) > WIDTH:
                continue
            if len(pts) >= 3:
                pygame.draw.polygon(surf, colour, pts)
                pygame.draw.polygon(surf, BORDER, pts, 1)
        # Mark microstates / tiny islands with a dot so they are visible and clickable.
        # Spread-out island nations (e.g. Kiribati) get a dot on their biggest island.
        # Territories that aren't in the quiz (e.g. Bermuda) get no dot.
        if not c.in_quiz:
            continue

        def extent(pts):
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            return max(xs) - min(xs), max(ys) - min(ys), (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

        sizes = [extent(pts) for pts in rings]
        all_pts = [p for pts in rings for p in pts]
        w, h, cx, cy = extent(all_pts)
        if w < 6 and h < 6:
            small.append((cx, cy, colour, c))
        elif all(sw < 4 and sh < 4 for sw, sh, _, _ in sizes):
            _, _, cx, cy = max(sizes, key=lambda e: e[0] * e[1])
            small.append((cx, cy, colour, c))
    for x, y, colour, _ in small:
        pygame.draw.circle(surf, colour, (x, y), 5)
        pygame.draw.circle(surf, BORDER, (x, y), 5, 1)
    return surf, [(x, y, c) for x, y, _, c in small]


def load_scores(path, starting=None):
    """(top 10 scores, last name typed) for a board.

    The player's saved scores are merged with the bundled starting scores, so a new version of the
    game brings its newest starting scores to players who already have scores of their own.
    """
    def read(p):
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, ValueError, TypeError):
            return {}

    saved = read(path) if path else {}
    bundled = read(starting) if starting else {}
    merged, seen = [], set()
    for score in saved.get("scores", []) + bundled.get("scores", []):
        key = (score.get("name"), score_count(score), score.get("seconds"), score.get("date"))
        if key not in seen:  # the same score can be in both files
            seen.add(key)
            merged.append(score)
    # Only the player's own last-typed name is pre-filled, never the starting scores' names.
    return sorted(merged, key=rank_key)[:10], saved.get("last_name", "")


def save_scores(path, scores, last_name):
    with open(path, "w", encoding="utf-8") as f:
        json.dump({"scores": scores, "last_name": last_name}, f, indent=2, ensure_ascii=False)


PROGRESS_KEYS = ("flags", "capitals", "us_flags", "us_capitals")


def load_progress():
    """{game: set of continents done without a miss} for the flag and capital games (world and USA)."""
    try:
        with open(FLAG_PROGRESS_FILE, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data["flags"] = data.get("perfect", [])  # world flags were saved as "perfect" before the other games
    return {key: set(data.get(key, [])) for key in PROGRESS_KEYS}


def save_progress(perfect):
    data = {key: sorted(perfect[key]) for key in PROGRESS_KEYS}
    data["perfect"] = data.pop("flags")
    with open(FLAG_PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


SCORE_FIELDS = ("countries", "states", "capitals")  # what a saved score counts, depending on the board


def score_count(score):
    """How many countries / states / capitals a saved score got."""
    return next((score[k] for k in SCORE_FIELDS if k in score), 0)


def rank_key(score):
    # Most countries first; ties go to whoever was faster.
    return (-score_count(score), score["seconds"])


def fmt_date(iso):
    """Saved dates are YYYY-MM-DD; show them as MM/DD/YYYY."""
    y, m, d = (iso.split("-") + ["", "", ""])[:3]
    return f"{m}/{d}/{y}" if d else iso


def fmt_time(seconds):
    """m:ss, dropping any fraction of a second (like the on-screen clock), so 113.9 s is 1:53."""
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


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


class Scope:
    """One map you can play on (the world or the USA): its countries/states, game in progress and scores."""

    def __init__(self, key, countries, views, noun, nouns, time_limit, score_files, board_title, score_label=None):
        self.key, self.countries, self.views = key, countries, views
        self.has_world = key == "world"  # the world has a globe view with continents to zoom into
        self.noun, self.nouns = noun, nouns  # "country"/"countries" or "state"/"states"
        self.time_limit, self.score_files, self.board_title = time_limit, score_files, board_title
        self.score_label = score_label or nouns.title()  # scoreboard column: "Countries", "States", "Correct"
        # Key a saved score uses for the count: "countries", "states" (States game, Guess the State) or "capitals".
        self.score_field = {"world": "countries", "guess_capital": "capitals"}.get(key, "states")
        self.progress_prefix = "" if self.has_world else "us_"
        # Game in progress (see App.reset_game_state), kept while you play other modes.
        self.continent = None  # None = world view
        self.cont_view = None
        self.world_surf = self.continent_surf = None
        self.world_dots, self.continent_dots = [], []
        self.label_cache = (None, [])  # (state key, placed labels) so labels aren't re-laid out every frame
        self.time_left = time_limit
        self.timer_started = self.time_up = False
        self.result = self.new_score = None
        self.gave_up = set()
        self.show_missed = False  # names of missed countries shown on the map after "Give up"
        self.auto_zoom_out_at = None  # time to move on after finishing a continent
        self.guess_order, self.guess_index = [], 0  # Guess the State: states in the order they're asked


# App attributes that belong to the current Scope (see App.scope); App reads and writes them there.
SCOPE_ATTRS = ("countries", "continent", "cont_view", "world_surf", "continent_surf", "world_dots",
               "continent_dots", "label_cache", "time_left", "timer_started", "time_up", "result",
               "new_score", "gave_up", "show_missed", "auto_zoom_out_at", "guess_order", "guess_index")


class Button:
    def __init__(self, text, rect):
        self.text, self.rect = text, pygame.Rect(rect)

    def draw(self, screen, font):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, (90, 98, 112) if hover else (70, 76, 88), self.rect, border_radius=6)
        label = font.render(self.text, True, TEXT)
        screen.blit(label, label.get_rect(center=self.rect.center))


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("World Map Game")
        pygame.key.set_repeat(400, 35)  # holding a key (e.g. backspace) repeats it
        # SCALED: draw at WIDTH x HEIGHT and let pygame stretch it to the window (mouse is mapped too).
        self.screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.SysFont("helveticaneue,arial", 22)
        self.big = pygame.font.SysFont("helveticaneue,arial", 34, bold=True)
        self.small = pygame.font.SysFont("helveticaneue,arial", 16)
        self.label_font = pygame.font.SysFont("helveticaneue,arial", 13, bold=True)
        self.title_font = pygame.font.SysFont("helveticaneue,arial", 40, bold=True)
        self.name_font = pygame.font.SysFont("helveticaneue,arial", 26, bold=True)

        with open(DATA_FILE, encoding="utf-8") as f:
            features = json.load(f)["features"]
        countries = [Country(f) for f in features if f["properties"]["CONTINENT"] != "Antarctica"]
        try:
            with open(CAPITALS_FILE, encoding="utf-8") as f:
                capitals = json.load(f)
        except (OSError, ValueError):
            capitals = {}
        for c in countries:
            info = capitals.get(c.name)
            c.capital = info["capital"] if info else "?"
            c.capital_pt = (info["lon"], info["lat"]) if info else c.label_pt
        with open(STATES_FILE, encoding="utf-8") as f:
            state_features = json.load(f)["features"]
        states = [State(f) for f in state_features]
        self.scopes = {
            "world": Scope("world", countries, CONTINENT_VIEWS, "country", "countries", TIME_LIMIT,
                           (SCORES_FILE, starting_scores("scores.json")), "Top 10 Scores"),
            "usa": Scope("usa", states, {"USA": USA_VIEW}, "state", "states", STATE_TIME_LIMIT,
                         (STATE_SCORES_FILE, starting_scores("state_scores.json")), "Top 10 State Scores"),
            # Its own copy of the states, so its green/red states and timer don't mix with the States game.
            "guess": Scope("guess", [State(f) for f in state_features], {"USA": USA_VIEW}, "state", "states",
                           STATE_TIME_LIMIT, (GUESS_SCORES_FILE, starting_scores("guess_scores.json")),
                           "Top 10 Guess the State",
                           score_label="Correct"),
            "guess_capital": Scope("guess_capital", [State(f) for f in state_features], {"USA": USA_VIEW},
                                   "capital", "capitals", STATE_TIME_LIMIT,
                                   (CAPITAL_GUESS_SCORES_FILE, starting_scores("capital_guess_scores.json")),
                                   "Top 10 Guess the Capital", score_label="Correct"),
        }
        self.scope = self.scopes["world"]

        self.world_view = View(WORLD_VIEW)
        self.hover = None
        self.text = ""
        self.suggest_index = 0  # which autocomplete match is shown (Up/Down to cycle)
        self.message = ""
        self.anim = None  # (start_time, from_rect, to_rect, zooming_in)
        self.back_btn = Button("Back", (WIDTH - 260, MAP_H + 20, 100, 36))
        self.giveup_btn = Button("Give up", (WIDTH - 150, MAP_H + 20, 130, 36))
        self.timer_rect = pygame.Rect(WIDTH - 200, 14, 180, 80)
        self.reset_btn = Button("Start over", (WIDTH - 200, 102, 180, 36))  # resets everything
        self.reset_confirm_until = 0  # reset needs a second click within a few seconds
        card = pygame.Rect(0, 0, 620, 560)
        card.center = (WIDTH // 2, MAP_H // 2 + 20)
        self.card = card
        self.save_btn = Button("Save score", (card.centerx - 150, card.y + 250, 140, 40))
        self.skip_btn = Button("Skip", (card.centerx + 10, card.y + 250, 140, 40))
        self.again_btn = Button("Play again", (card.centerx - 150, card.bottom - 60, 140, 40))
        self.close_btn = Button("View map", (card.centerx + 10, card.bottom - 60, 140, 40))
        self.reset_game_state()

        # Modes menu and the flag modes.
        self.mode = "countries"  # a key of MODES
        self.menu_open = False
        self.menu_group = None  # menu group expanded to show Learn / Game (a group key in MENU)
        self.modes_btn = Button("Modes", (20, 14, 130, 40))
        self.leaderboard_btn = Button("Leaderboard", (160, 14, 160, 40))  # countries / states game only
        self.lb_close_btn = Button("Close", (self.card.centerx - 70, self.card.bottom - 60, 140, 40))
        self.flag_reset_btn = Button("Reset", (WIDTH - 200, 14, 180, 40))  # Flags > Game, world view
        self.cl_back_btn = Button("Back", (WIDTH - 150, MAP_H + 20, 130, 36))  # Countries > Learn, zoomed in
        self.perfect = load_progress()  # continents with every flag / capital right: green on the globe
        self.flag_cache = {}
        self.learn_selected = None  # country under the mouse whose flag / capital is shown in Learn
        self.quiz = None  # running flag quiz (practice test or game), see start_flag_quiz
        self.learn_back_btn = Button("Back", (WIDTH - 320, MAP_H + 20, 100, 36))
        self.practice_btn = Button("Practice test", (WIDTH - 200, MAP_H + 20, 180, 36))
        self.stop_btn = Button("Stop test", (WIDTH - 200, MAP_H + 20, 180, 36))
        self.quit_btn = Button("Back to globe", (WIDTH - 200, MAP_H + 20, 180, 36))
        self.start_btn = Button("Start game", (WIDTH - 200, MAP_H + 20, 180, 36))  # USA flag/capital games
        self.skip_btn_guess = Button("Skip", (WIDTH - 150, MAP_H + 20, 130, 36))  # Guess the State
        self.zoom_ne_btn = Button("Zoom in", (WIDTH - 300, MAP_H + 20, 140, 36))  # small northeastern states
        self.done_card = pygame.Rect(0, 0, 540, 280)
        self.done_card.center = (WIDTH // 2, MAP_H // 2)
        self.replay_btn = Button("Play again", (WIDTH // 2 - 190, self.done_card.bottom - 70, 180, 40))
        self.done_globe_btn = Button("Back to globe", (WIDTH // 2 + 10, self.done_card.bottom - 70, 180, 40))

        self.render_world()

    @property
    def md(self):
        """The current Mode (scope, subject, kind, titles)."""
        return MODES[self.mode]

    def subject(self):
        """What the current mode is about: "countries" (or states), "flags" or "capitals"."""
        return self.md.subject

    def naming_game(self):
        """The type-the-names game with the timer and scoreboard (Countries Game or States Game)."""
        return self.md.subject == "countries" and self.md.kind == "game"

    def country_learn(self):
        return self.md.subject == "countries" and self.md.kind == "learn"

    def quiz_game(self):
        """A multiple-choice flag or capital game (not the practice test)."""
        return self.md.subject in ("flags", "capitals") and self.md.kind == "game"

    def guess_game(self):
        """Guess the State or Guess the Capital: one highlighted state at a time, timed."""
        return self.md.subject in ("guess", "guess_capital")

    def capital_guess(self):
        return self.md.subject == "guess_capital"

    def answer_of(self, c):
        """What you type for state c in the current guess game: its name, or its capital."""
        return c.capital if self.capital_guess() else c.name

    def answers(self, c):
        return {normalise(c.capital)} if self.capital_guess() else c.accepted

    def timed_game(self):
        """A game with the timer, Start over and a leaderboard: Countries, States or Guess the State."""
        return self.naming_game() or self.guess_game()

    def progress_key(self):
        return self.scope.progress_prefix + self.subject()

    def place(self):
        """The current continent's name for messages ("Africa", "the USA")."""
        return self.continent if self.scope.has_world else "the USA"

    def heading(self):
        """Big heading in the bottom-left panel when zoomed in: the continent, or the mode's title on the USA map."""
        return self.continent if self.scope.has_world else self.md.title

    def reset_game_state(self):
        self.time_left = self.scope.time_limit
        self.timer_started = False
        self.time_up = False  # True once the game has ended (time ran out or every country/state named)
        self.modal = None  # None, "name" (enter your name) or "scores" (scoreboard)
        self.result = None  # this game's score, once it's over
        self.new_score = None  # the saved entry to highlight on the scoreboard

    def total_found(self):
        return sum(c.found for c in self.countries if c.in_quiz and c.continent in self.scope.views)

    def total_countries(self):
        return sum(1 for c in self.countries if c.in_quiz and c.continent in self.scope.views)

    def end_game(self):
        """Lock the game and ask for a name to put on the scoreboard."""
        self.time_up = True
        self.text = ""
        done = self.total_found()
        # Saved to a tenth of a second (cut off, not rounded, so it never shows more than the clock did).
        elapsed = self.scope.time_limit - self.time_left
        self.result = {self.scope.score_field: done, "seconds": math.floor(elapsed * 10) / 10}
        if self.capital_guess():
            # Reveal the capitals that weren't reached before time ran out, in red like the misses.
            for c in self.guess_order[self.guess_index:]:
                c.missed = True
            self.guess_index = len(self.guess_order)
            self.cont_view = View(USA_VIEW)
            self.render_continent()
        sc = self.scope
        if self.guess_game():
            start = "Time's up" if self.time_left <= 0 else "Done"
            self.message = f"{start}! {done} / 50 correct."
        elif self.time_left <= 0:
            self.message = f"Time's up! You named {done} {sc.noun if done == 1 else sc.nouns}."
        else:
            self.message = f"You named every {sc.noun} in {fmt_time(self.result['seconds'])}!"
        scores, last_name = load_scores(*self.scope.score_files)
        top = sorted(scores, key=rank_key)[:10]
        if len(top) < 10 or rank_key(self.result) < rank_key(top[-1]):
            self.name_text = last_name
            self.modal = "name"  # made the top 10: ask for a name
        else:
            self.new_score = dict(self.result)  # not saved; the scoreboard says it didn't make the top 10
            self.modal = "scores"

    def submit_score(self, save):
        if save and self.name_text.strip():
            scores, _ = load_scores(*self.scope.score_files)
            self.new_score = dict(self.result, name=self.name_text.strip(),
                                  date=time.strftime("%Y-%m-%d"))
            scores.append(self.new_score)
            # Only the top 10 are kept; a score that doesn't make it is still shown as "didn't make the top 10".
            top = sorted(scores, key=rank_key)[:10]
            save_scores(self.scope.score_files[0], top, self.name_text.strip())
        self.modal = "scores"

    def reset_all(self):
        """World-view "Give up": wipe all progress and the timer."""
        for c in self.countries:
            c.found = c.missed = False
        self.gave_up.clear()
        self.reset_game_state()
        self.text = ""
        self.message = f"Progress reset. The timer starts with your first {self.scope.noun}."
        if self.guess_game():
            self.new_guess_order()
            self.cont_view = View(USA_VIEW)
        self.render_world()

    def over_label(self):
        """Shown when a timed game has ended: ran out of time, or finished everything in time."""
        return "Time's up!" if self.time_left <= 0 else "Finished!"

    def game_started(self):
        """True once there is progress to throw away (a country named, a "Give up", or the game over)."""
        return self.timer_started or self.time_up or bool(self.gave_up)

    def timer_paused(self):
        # The clock stops while the missed countries' names are on screen, or in the flag modes.
        return (not self.timed_game() or self.modal == "leaderboard"
                or (self.continent is not None and self.show_missed))

    def update_timer(self, dt):
        if not self.timer_started or self.time_up or self.timer_paused():
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self.time_left = 0
            self.end_game()

    # ---------- rendering helpers ----------
    def render_world(self):
        if not self.scope.has_world:  # the USA map has no globe: it's always "zoomed in"
            self.render_continent()
            return
        hover_cont = self.hover.continent if self.hover and not self.country_learn() else None

        def colour(c):
            if c.found and self.naming_game():
                return FOUND
            if self.quiz_game() and c.in_quiz and c.continent in self.perfect[self.progress_key()]:
                return FOUND
            return LAND_HOVER if c.continent == hover_cont else LAND

        self.world_surf, self.world_dots = draw_map(self.countries, self.world_view, colour)

    def render_continent(self):
        def colour(c):
            if c.continent != self.continent or not c.in_quiz:
                return LAND_OTHER
            if self.guess_game():
                return (FOUND if c.found else MISSED if c.missed else
                        SELECTED if c is self.guess_target() else LAND)
            if self.quiz_game() and self.continent in self.perfect[self.progress_key()]:
                return FOUND
            if not self.naming_game():
                return LAND
            if c.found:
                return FOUND
            if self.continent in self.gave_up:
                return MISSED
            return LAND

        self.continent_surf, self.continent_dots = draw_map(self.countries, self.cont_view, colour)
        if not self.scope.has_world:  # frames around the Alaska and Hawaii insets
            for box in INSET_BOXES:
                pygame.draw.rect(self.continent_surf, BORDER, self.cont_view.screen_rect(box), 1, border_radius=6)

    def quiz_countries(self):
        """Countries that can be named right now: one continent when zoomed in, else all."""
        return [c for c in self.countries
                if c.in_quiz and c.continent in self.scope.views
                and (self.continent is None or c.continent == self.continent)]

    def rerender(self):
        if self.continent is None:
            self.render_world()
        else:
            self.render_continent()

    # ---------- state changes ----------
    def zoom_in(self, continent):
        self.continent = continent
        self.show_missed = False
        self.cont_view = View(self.scope.views[continent])
        self.render_continent()
        self.text = ""
        self.message = f"Name the {self.scope.nouns} of {continent}!"
        self.hover = None
        self.learn_selected = None
        self.quiz = None
        full = pygame.Rect(0, 0, WIDTH, MAP_H)
        self.anim = (pygame.time.get_ticks(), full, self.world_view.screen_rect(self.scope.views[continent]), True)
        if self.quiz_game():
            self.start_flag_quiz("game")  # the flags appear as soon as the zoom finishes

    def zoom_out(self, message=""):
        """Back to the globe. On the USA map (nothing to zoom out to) it only leaves the current quiz/selection."""
        if not self.scope.has_world:
            self.hover = self.learn_selected = self.quiz = None
            self.text, self.message = "", message
            self.render_continent()
            return
        full = pygame.Rect(0, 0, WIDTH, MAP_H)
        self.anim = (pygame.time.get_ticks(), self.world_view.screen_rect(self.scope.views[self.continent]), full, False)
        self.continent = None
        self.show_missed = False
        self.hover = None
        self.text = ""
        self.message = message
        self.auto_zoom_out_at = None
        self.learn_selected = None
        self.quiz = None
        self.render_world()

    def next_continent(self):
        """After finishing a continent: go to the next unfinished one in CONTINENT_ORDER (or the world)."""
        done = self.continent
        self.auto_zoom_out_at = None
        start = CONTINENT_ORDER.index(done)
        for cont in CONTINENT_ORDER[start + 1:] + CONTINENT_ORDER[:start]:
            if not all(c.found for c in self.countries if c.in_quiz and c.continent == cont):
                self.zoom_in(cont)
                self.message = f"{done} complete! Now name the countries of {cont}."
                return
        self.zoom_out(self.message)  # every continent is done

    # ---------- Guess the State ----------
    def new_guess_order(self):
        self.guess_order = self.quiz_countries()
        random.shuffle(self.guess_order)
        self.guess_index = 0

    def guess_target(self):
        """The highlighted state to name (None once all 50 are answered)."""
        if self.guess_index < len(self.guess_order):
            return self.guess_order[self.guess_index]
        return None

    def check_guess(self, submitted):
        """Typing turns the state green as soon as it's right; Enter with another state's name (or capital) is a miss."""
        target = self.guess_target()
        guess = normalise(self.text)
        if not guess or target is None:
            return
        if guess in self.answers(target):
            target.found = True
            self.message = f"Correct: {self.answer_of(target)}!"
            if self.ne_zoomed():  # a right answer always goes back to the whole map
                self.cont_view = View(USA_VIEW)
        elif not submitted:
            return
        elif any(guess in self.answers(c) for c in self.countries if c.in_quiz):
            target.missed = True
            self.message = self.reveal("No")
        else:
            self.message = f"'{self.text}' is not a {'state capital' if self.capital_guess() else 'state'}."
            self.text = ""
            return
        self.next_guess()

    def reveal(self, start):
        """Message giving the right answer after a miss or skip."""
        target = self.guess_target()
        if self.capital_guess():
            return f"{start}: the capital of {target.name} is {target.capital}."
        return f"{start}, that was {target.name}." if start == "No" else f"{start}: that was {target.name}."

    def next_guess(self, skipped=False):
        target = self.guess_target()
        if skipped:
            target.missed = True
            self.message = self.reveal("Skipped")
        self.timer_started = True
        self.text = ""
        self.guess_index += 1
        self.update_ne_zoom()
        self.render_continent()
        if self.guess_target() is None:
            self.end_game()

    def handle_guess_event(self, event):
        clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        if clicked and self.game_started() and self.reset_btn.rect.collidepoint(event.pos):
            self.click_start_over()
        elif clicked and self.skip_btn_guess.rect.collidepoint(event.pos):
            if not self.time_up:
                self.next_guess(skipped=True)
        elif clicked and self.ne_zoom_available() and self.zoom_ne_btn.rect.collidepoint(event.pos):
            self.set_ne_zoom(not self.ne_zoomed())
        elif event.type == pygame.TEXTINPUT and event.text == " " and not self.text:
            # Space before typing anything: come back to this state later (spaces inside names still work).
            if not self.time_up:
                self.defer_guess()
        else:
            self.handle_typing(event)

    def defer_guess(self):
        """Move the highlighted state to the end of the queue, with no penalty."""
        if self.guess_index >= len(self.guess_order) - 1:
            self.message = "That's the last one left!"
            return
        target = self.guess_order.pop(self.guess_index)
        self.guess_order.append(target)
        self.message = "Coming back to that one later."
        self.update_ne_zoom()
        self.render_continent()

    def ne_zoom_available(self):
        target = self.guess_target()
        return not self.time_up and (self.ne_zoomed() or (target is not None and target.name in NE_SMALL))

    def ne_zoomed(self):
        return self.cont_view.box == NE_VIEW

    def set_ne_zoom(self, on):
        self.cont_view = View(NE_VIEW if on else USA_VIEW)
        self.render_continent()

    def update_ne_zoom(self):
        """Back to the whole map when the next state isn't one of the small northeastern ones."""
        target = self.guess_target()
        if self.ne_zoomed() and (target is None or target.name not in NE_SMALL):
            self.cont_view = View(USA_VIEW)

    def draw_guess_panel(self):
        right = sum(c.found for c in self.countries)
        wrong = sum(c.missed for c in self.countries)
        self.screen.blit(self.big.render(self.md.title, True, TEXT), (24, MAP_H + 14))
        info = f"{right} correct  ·  {wrong} missed  ·  {50 - right - wrong} left"
        self.screen.blit(self.font.render(info, True, TEXT_DIM), (24, MAP_H + 60))
        self.draw_text_box(pygame.Rect(390, MAP_H + 20, 500, 40), self.message,
                           locked=self.over_label() if self.time_up else None)
        if not self.time_up:
            self.skip_btn_guess.draw(self.screen, self.font)
        if self.ne_zoom_available():
            self.zoom_ne_btn.text = "Zoom out" if self.ne_zoomed() else "Zoom in"
            self.zoom_ne_btn.draw(self.screen, self.font)
        target = self.guess_target()
        if self.capital_guess() and target is not None and not self.time_up:
            # The state is named too: this game is about capitals, not finding the state.
            ask = self.font.render("What is the capital of", True, TEXT_DIM)
            name = self.title_font.render(target.name, True, TEXT)
            banner = pygame.Rect(0, 0, max(ask.get_width(), name.get_width()) + 48, 92)
            # In the ocean, clear of the states: below the map, or off the coast when zoomed into the Northeast.
            if self.ne_zoomed():
                banner.bottomright = (WIDTH - 24, MAP_H - 14)
            else:
                banner.midbottom = (WIDTH // 2 + 70, MAP_H - 14)
            pygame.draw.rect(self.screen, PANEL, banner, border_radius=10)
            self.screen.blit(ask, ask.get_rect(midtop=(banner.centerx, banner.y + 8)))
            self.screen.blit(name, name.get_rect(midbottom=(banner.centerx, banner.bottom - 8)))

    def check_answer(self, submitted):
        if self.guess_game():
            self.check_guess(submitted)
            return
        guess = normalise(self.text)
        if not guess:
            return
        for c in self.quiz_countries():
            if guess in c.accepted:
                if c.found:
                    if submitted:
                        self.message = f"You already named {c.name}."
                        self.text = ""
                    return
                c.found = True
                self.timer_started = True
                self.message = f"Correct: {c.name}!" if self.continent else f"Correct: {c.name} ({c.continent})!"
                self.text = ""
                self.rerender()
                if all(q.found for q in self.quiz_countries()):
                    where = self.place() if self.continent else "the world"
                    self.message = f"You named every {self.scope.noun} in {where}!"
                    if self.continent and self.scope.has_world:
                        # Pause briefly so the last country can be seen turning green.
                        self.auto_zoom_out_at = pygame.time.get_ticks() + 1500
                if self.total_found() == self.total_countries():
                    self.end_game()
                return
        if submitted:
            where = f"in {self.place()}" if self.continent else "on the map"
            self.message = f"'{self.text}' is not a {self.scope.noun} {where}."
            self.text = ""

    # ---------- main loop ----------
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if self.modal:
                    self.handle_modal_event(event)
                    continue
                if self.anim:
                    continue
                if self.handle_menu_event(event) or self.handle_top_button(event):
                    continue
                if self.continent is None:
                    self.handle_world_event(event)
                elif self.naming_game():
                    self.handle_continent_event(event)
                elif self.guess_game():
                    self.handle_guess_event(event)
                elif self.country_learn():
                    self.handle_country_learn_event(event)
                elif self.quiz:
                    self.handle_quiz_event(event)
                else:
                    self.handle_learn_event(event)
            if self.auto_zoom_out_at and pygame.time.get_ticks() >= self.auto_zoom_out_at and not self.anim:
                self.next_continent()
            if self.quiz and self.quiz["advance_at"] and pygame.time.get_ticks() >= self.quiz["advance_at"]:
                self.next_question()
            self.draw()
            self.update_timer(self.clock.tick(FPS) / 1000)

    def handle_world_event(self, event):
        if event.type == pygame.MOUSEMOTION and self.country_learn():
            self.hover = self.country_at(event.pos, self.world_view, self.world_dots)
        elif event.type == pygame.MOUSEMOTION:
            hit = self.country_at(event.pos, self.world_view, self.world_dots)
            if (hit.continent if hit else None) != (self.hover.continent if self.hover else None):
                self.hover = hit
                self.render_world()
        elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.naming_game()
              and self.game_started() and self.reset_btn.rect.collidepoint(event.pos)):
            self.click_start_over()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = self.country_at(event.pos, self.world_view, self.world_dots)
            if hit and hit.continent in self.scope.views:
                self.zoom_in(hit.continent)
        elif self.naming_game():
            self.handle_typing(event)

    def handle_typing(self, event):
        """Typing into the answer box (works on both the world map and continent views)."""
        if self.time_up:
            return
        if event.type == pygame.KEYDOWN:
            matches = self.suggestions()
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.check_answer(submitted=True)
            elif event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
                self.suggest_index = 0
            elif event.key in (pygame.K_TAB, pygame.K_RIGHT) and matches:
                self.text = matches[self.suggest_index % len(matches)]
                self.suggest_index = 0
                self.check_answer(submitted=False)
            elif event.key in (pygame.K_DOWN, pygame.K_UP) and matches:
                self.suggest_index += 1 if event.key == pygame.K_DOWN else -1
        elif event.type == pygame.TEXTINPUT and event.text.isprintable():
            if len(self.text) < 40:
                self.text += event.text
                self.suggest_index = 0
                self.check_answer(submitted=False)  # turn green as soon as it's spelled right

    def suggestions(self):
        """Autocomplete matches for the typed text (after 3 letters) from countries not yet named.

        Zoomed in, only the current continent's countries are suggested; on the world map, all of them.
        """
        typed = fold(self.text)
        if len(typed.strip()) < 3:
            return []
        matches = set()
        for c in self.quiz_countries():
            if c.found or getattr(c, "missed", False):
                continue
            name = self.answer_of(c) if self.guess_game() else c.name
            for name in (name, name[4:] if name.startswith("The ") else None):
                if name and len(name) > len(typed) and fold(name).startswith(typed):
                    matches.add(name)
        return sorted(matches, key=lambda n: (len(n), n))

    def handle_modal_event(self, event):
        if self.modal == "name":
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.submit_score(save=True)
                elif event.key == pygame.K_ESCAPE:
                    self.submit_score(save=False)
                elif event.key == pygame.K_BACKSPACE:
                    self.name_text = self.name_text[:-1]
            elif event.type == pygame.TEXTINPUT and event.text.isprintable() and len(self.name_text) < 15:
                self.name_text += event.text
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.save_btn.rect.collidepoint(event.pos):
                    self.submit_score(save=True)
                elif self.skip_btn.rect.collidepoint(event.pos):
                    self.submit_score(save=False)
        elif self.modal == "scores":
            again = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
            clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            if again or (clicked and self.again_btn.rect.collidepoint(event.pos)):
                if self.continent is not None:
                    self.zoom_out()
                self.reset_all()
            elif clicked and self.close_btn.rect.collidepoint(event.pos):
                self.modal = None  # look at the final map; "Play again" still restarts
        elif self.modal == "leaderboard":
            key = event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER)
            clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            if key or (clicked and self.lb_close_btn.rect.collidepoint(event.pos)):
                self.modal = None

    def click_start_over(self):
        """Start over (both views). Needs a second click unless the time has already run out."""
        if self.time_up or pygame.time.get_ticks() < self.reset_confirm_until:
            self.reset_confirm_until = 0
            if self.continent is not None:
                self.zoom_out()
            self.reset_all()
        else:
            self.reset_confirm_until = pygame.time.get_ticks() + 3000
            self.message = "Click again to start over."

    def handle_continent_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if self.scope.has_world:
                self.zoom_out()
        elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.game_started()
              and self.reset_btn.rect.collidepoint(event.pos)):
            self.click_start_over()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_btn.rect.collidepoint(event.pos) and self.scope.has_world:
                self.zoom_out()
            elif self.giveup_btn.rect.collidepoint(event.pos):
                # First click gives up; later clicks show/hide the names again.
                self.show_missed = not self.show_missed if self.continent in self.gave_up else True
                self.gave_up.add(self.continent)
                missed = sum(not c.found for c in self.quiz_countries())
                self.text = ""
                if self.show_missed:
                    self.message = f"You missed {missed} {self.scope.nouns}. Hide the names to keep typing."
                else:
                    self.message = f"{missed} {self.scope.nouns} still missing (in red)."
                self.render_continent()
        elif not self.show_missed:  # no typing while the answers are on screen
            self.handle_typing(event)

    def country_at(self, pos, view, dots=()):
        if pos[1] >= MAP_H:
            return None
        # Tiny countries are drawn as dots: a click near one counts.
        near = [(math.dist(pos, (x, y)), c) for x, y, c in dots if math.dist(pos, (x, y)) <= 8]
        if near:
            return min(near, key=lambda n: n[0])[1]
        lon, lat = view.to_lonlat(*pos)
        for c in self.countries:
            if c.contains(lon, lat):
                return c
        return None

    def draw(self):
        self.screen.fill(PANEL)
        if self.anim:
            self.draw_animation()
        elif self.continent is None:
            self.screen.blit(self.world_surf, (0, 0))
            if self.naming_game():
                self.draw_labels()
                self.draw_title()
                self.draw_world_panel()
            elif self.country_learn():
                self.draw_hover_card(self.world_view, self.world_dots)
                self.draw_title()
                self.draw_country_learn_panel()
            else:
                self.draw_title()
                self.draw_flags_world_panel()
        elif self.naming_game():
            self.screen.blit(self.continent_surf, (0, 0))
            self.draw_labels()
            self.draw_continent_panel()
        elif self.guess_game():
            self.screen.blit(self.continent_surf, (0, 0))
            self.draw_labels()
            self.draw_guess_panel()
        elif self.country_learn():
            self.screen.blit(self.continent_surf, (0, 0))
            self.draw_hover_card(self.cont_view, self.continent_dots)
            self.draw_country_learn_panel()
        else:
            self.screen.blit(self.continent_surf, (0, 0))
            if self.quiz:
                self.draw_flag_quiz()
            else:
                self.draw_learn_view()
            self.draw_flags_continent_panel()
        if not self.anim and self.continent is not None and not self.quiz:
            self.draw_title()  # zoomed in / USA map (a running flag or capital quiz shows its question there instead)
        if not self.anim and not self.modal:
            if self.timed_game():
                self.leaderboard_btn.draw(self.screen, self.font)
            elif self.show_flag_reset():
                confirm = pygame.time.get_ticks() < self.reset_confirm_until
                self.flag_reset_btn.text = "Confirm?" if confirm else "Reset"
                self.flag_reset_btn.draw(self.screen, self.font)
            self.draw_modes_menu()
        if not self.anim and self.timed_game():
            self.draw_timer()
            if self.time_up:
                self.reset_btn.text = "Play again"
            elif pygame.time.get_ticks() < self.reset_confirm_until:
                self.reset_btn.text = "Confirm?"
            else:
                self.reset_btn.text = "Start over"
            if self.game_started():  # nothing to start over before the first answer
                self.reset_btn.draw(self.screen, self.font)
        if self.modal == "name":
            self.draw_name_entry()
        elif self.modal in ("scores", "leaderboard"):
            self.draw_scoreboard()
        pygame.display.flip()

    def draw_card(self, height):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        self.screen.blit(shade, (0, 0))
        card = pygame.Rect(self.card.x, self.card.y, self.card.w, height)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=12)
        return card

    def draw_name_entry(self):
        card = self.draw_card(320)
        cx = card.centerx
        r = self.result
        if self.guess_game():
            title = "Time's up!" if self.time_left <= 0 else "All 50 answered!"
            score = f"{score_count(r)} / 50 correct in {fmt_time(r['seconds'])}"
        else:
            title = "Time's up!" if self.time_left <= 0 else f"You named every {self.scope.noun}!"
            score = f"{score_count(r)} {self.scope.nouns} in {fmt_time(r['seconds'])}"
        lines = [
            (self.big, title, TEXT),
            (self.font, score, FOUND),
            (self.small, "Enter your first name for the scoreboard:", TEXT_DIM),
        ]
        y = card.y + 28
        for font, text, colour in lines:
            img = font.render(text, True, colour)
            self.screen.blit(img, img.get_rect(midtop=(cx, y)))
            y += img.get_height() + 14
        box = pygame.Rect(cx - 150, card.y + 185, 300, 44)
        pygame.draw.rect(self.screen, (250, 250, 250), box, border_radius=6)
        cursor = "|" if (pygame.time.get_ticks() // 500) % 2 else ""
        name = self.font.render(self.name_text + cursor, True, (20, 20, 20))
        self.screen.blit(name, name.get_rect(midleft=(box.x + 12, box.centery)))
        self.save_btn.draw(self.screen, self.font)
        self.skip_btn.draw(self.screen, self.font)

    def draw_scoreboard(self):
        card = self.draw_card(self.card.h)
        scores, _ = load_scores(*self.scope.score_files)
        top = sorted(scores, key=rank_key)[:10]
        title = self.big.render(self.scope.board_title, True, TEXT)
        self.screen.blit(title, title.get_rect(midtop=(card.centerx, card.y + 22)))

        cols = [(card.x + 40, "#"), (card.x + 90, "Name"), (card.x + 270, self.scope.score_label),
                (card.x + 385, "Time"), (card.x + 465, "Date")]
        y = card.y + 80
        for x, head in cols:
            self.screen.blit(self.small.render(head, True, TEXT_DIM), (x, y))
        y += 30
        if not top:
            msg = self.font.render("No scores saved yet.", True, TEXT_DIM)
            self.screen.blit(msg, msg.get_rect(midtop=(card.centerx, y + 20)))
        for i, sc in enumerate(top, 1):
            mine = sc == self.new_score
            if mine:
                pygame.draw.rect(self.screen, (60, 90, 70), (card.x + 28, y - 4, card.w - 56, 32), border_radius=6)
            values = [str(i), sc["name"], str(score_count(sc)), fmt_time(sc["seconds"]), fmt_date(sc.get("date", ""))]
            for (x, _), value in zip(cols, values):
                img = self.font.render(value, True, FOUND if mine else TEXT)
                self.screen.blit(img, (x, y), pygame.Rect(0, 0, 200, 30))
            y += 36
        if self.new_score and self.new_score not in top:
            note = self.small.render(f"Your score ({score_count(self.new_score)} in "
                                     f"{fmt_time(self.new_score['seconds'])}) didn't make the top 10.", True, TEXT_DIM)
            self.screen.blit(note, note.get_rect(midtop=(card.centerx, card.bottom - 92)))
        if self.modal == "leaderboard":  # opened from the Leaderboard button mid-game
            self.lb_close_btn.draw(self.screen, self.font)
        else:
            self.again_btn.draw(self.screen, self.font)
            self.close_btn.draw(self.screen, self.font)

    def draw_timer(self):
        overlay = pygame.Surface(self.timer_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(overlay, (*PANEL, 225), overlay.get_rect(), border_radius=8)
        self.screen.blit(overlay, self.timer_rect)
        # Counts up from 0:00 to the time limit, which is shown next to it.
        elapsed = self.scope.time_limit - self.time_left
        colour = MISSED if self.time_left <= WARNING_TIME else TEXT
        clock = self.big.render(fmt_time(elapsed), True, colour)
        limit = self.font.render(f" / {fmt_time(self.scope.time_limit)}", True, TEXT_DIM)
        row = pygame.Rect(0, 0, clock.get_width() + limit.get_width(), clock.get_height())
        row.midbottom = (self.timer_rect.centerx, self.timer_rect.bottom - 14)
        self.screen.blit(clock, row.topleft)
        self.screen.blit(limit, limit.get_rect(bottomleft=(row.x + clock.get_width(), row.bottom - 4)))
        # Progress bar towards the time limit.
        bar = pygame.Rect(self.timer_rect.x + 12, self.timer_rect.bottom - 10, self.timer_rect.w - 24, 4)
        pygame.draw.rect(self.screen, (80, 86, 98), bar, border_radius=2)
        pygame.draw.rect(self.screen, colour if self.time_left <= WARNING_TIME else FOUND,
                         (bar.x, bar.y, bar.w * elapsed / self.scope.time_limit, bar.h), border_radius=2)
        status = (self.over_label().rstrip("!").upper() if self.time_up else "PAUSED" if self.timer_paused()
                  else f"TIME ({self.scope.time_limit // 60} MIN MAX)" if self.timer_started else "STARTS ON 1ST ANSWER")
        tag = self.label_font.render(status, True, TEXT_DIM)
        if tag.get_width() > self.timer_rect.w - 12:
            tag = pygame.transform.smoothscale_by(tag, (self.timer_rect.w - 12) / tag.get_width())
        self.screen.blit(tag, tag.get_rect(midtop=(self.timer_rect.centerx, self.timer_rect.y + 7)))

    def draw_title(self):
        title = self.title_font.render(self.md.title, True, TEXT)
        rect = title.get_rect(midtop=(WIDTH // 2, 14)).inflate(32, 12)
        pill = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(pill, (*PANEL, 215), pill.get_rect(), border_radius=10)
        self.screen.blit(pill, rect)
        self.screen.blit(title, title.get_rect(center=rect.center))

    def draw_labels(self):
        """Name tags on the map: green for countries you've named, dark for missed ones after "Give up"."""
        key = (self.continent, self.cont_view.box if self.cont_view else None, self.show_missed, tuple((c.found, getattr(c, "missed", False)) for c in self.countries))
        if self.label_cache[0] != key:
            self.label_cache = (key, self.place_labels())
        placed = self.label_cache[1]

        for rect, text, (ax, ay), bg in placed:
            if not rect.collidepoint(ax, ay):  # label was moved: point back to the country
                end = (min(max(ax, rect.left), rect.right), min(max(ay, rect.top), rect.bottom))
                pygame.draw.line(self.screen, bg, (ax, ay), end, 1)
                pygame.draw.circle(self.screen, bg, (ax, ay), 2)
        for rect, text, _, bg in placed:
            pill = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(pill, (*bg, 215), pill.get_rect(), border_radius=5)
            self.screen.blit(pill, rect)
            self.screen.blit(text, text.get_rect(center=rect.center))

    def place_labels(self):
        """Work out where each name tag goes, nudging them apart so they don't overlap.

        Zoomed in, every tag is shown (moved aside with a pointer line if needed). On the
        crowded world map a tag is only shown if it fits on its country without moving.
        """
        zoomed = self.continent is not None
        view = self.cont_view if zoomed else self.world_view
        shown = [c for c in self.quiz_countries()
                 if c.found or getattr(c, "missed", False) or (zoomed and self.show_missed)]
        # Place the smallest countries first, so they get the spots closest to them.
        shown.sort(key=lambda c: (c.bbox[2] - c.bbox[0]) * (c.bbox[3] - c.bbox[1]))
        bounds = pygame.Rect(4, 4, WIDTH - 8, MAP_H - 8)
        placed = []
        # States game / guess games: the small northeastern states get their tag out in the Atlantic, joined by a line,
        # so the tags don't cover their neighbours. Placed first, so other tags keep clear of them.
        callouts = self.ne_callout_slots(view)
        shown.sort(key=lambda c: c.name not in callouts)
        for c in shown:
            ax, ay = view.project_ring([c.label_pt])[0]
            if c.name in callouts:
                text = self.label_font.render(c.capital if self.capital_guess() else c.short_name, True, TEXT)
                rect = text.get_rect().inflate(10, 4)
                rect.midleft = callouts[c.name]
                bg = FOUND_LABEL if c.found else MISSED if getattr(c, "missed", False) else PANEL
                placed.append((rect, text, (ax, ay), bg))
                continue
            # Guess the Capital labels states with their capital.
            text = self.label_font.render(c.capital if self.capital_guess() else c.short_name, True, TEXT)
            rect = text.get_rect().inflate(10, 4)
            if zoomed:
                for dx, dy in self.label_offsets():
                    rect.center = (ax + dx, ay + dy)
                    rect.clamp_ip(bounds)
                    if not any(rect.colliderect(r) for r, *_ in placed):
                        break
            else:
                rect.center = (ax, ay)
                width_on_screen = (c.bbox[2] - c.bbox[0]) * view.k * view.scale
                if rect.w > width_on_screen * 1.3 or any(rect.colliderect(r) for r, *_ in placed):
                    continue
            bg = FOUND_LABEL if c.found else MISSED if getattr(c, "missed", False) else PANEL
            placed.append((rect.copy(), text, (ax, ay), bg))
        return placed

    def ne_callout_slots(self, view):
        """{state name: (x, y) where its tag starts} for the NE_SMALL states in the States game and guess games.

        One fixed slot per state, in a column in the ocean, in NE_CALLOUT_ORDER.
        """
        states_game = self.naming_game() and self.continent == "USA"
        if not (states_game or self.guess_game()) or self.ne_zoomed():  # full USA map only
            return {}
        return {name: (1060, 205 + i * 30) for i, name in enumerate(NE_CALLOUT_ORDER)}

    @staticmethod
    def label_offsets():
        """Candidate label positions: the spot itself, then rings further and further out."""
        yield 0, 0
        for r in range(16, 400, 16):
            for i in range(16):
                a = 2 * math.pi * i / 16
                yield r * math.cos(a) * 1.8, r * math.sin(a)  # wider than tall, like the labels

    def draw_animation(self):
        start, r0, r1, zooming_in = self.anim
        t = min(1.0, (pygame.time.get_ticks() - start) / 1000 / ZOOM_TIME)
        t = t * t * (3 - 2 * t)  # ease in/out
        # Interpolate the part of the world image that fills the screen.
        rect = pygame.Rect(
            r0.x + (r1.x - r0.x) * t, r0.y + (r1.y - r0.y) * t,
            max(1, r0.w + (r1.w - r0.w) * t), max(1, r0.h + (r1.h - r0.h) * t),
        )
        # Keep aspect ratio of the screen so the image isn't stretched.
        aspect = WIDTH / MAP_H
        if rect.w / rect.h > aspect:
            rect.inflate_ip(0, rect.w / aspect - rect.h)
        else:
            rect.inflate_ip(rect.h * aspect - rect.w, 0)
        canvas = pygame.Surface((WIDTH, MAP_H))
        canvas.fill(OCEAN)
        sx, sy = WIDTH / rect.w, MAP_H / rect.h
        scaled = pygame.transform.smoothscale(self.world_surf, (int(WIDTH * sx), int(MAP_H * sy)))
        canvas.blit(scaled, (-rect.x * sx, -rect.y * sy))
        self.screen.blit(canvas, (0, 0))
        if pygame.time.get_ticks() - start >= ZOOM_TIME * 1000:
            self.anim = None

    def draw_world_panel(self):
        hint = "Type a country, or click a continent"
        if self.hover and self.hover.continent in self.scope.views:
            hint = f"{self.hover.continent} — click to zoom in"
        self.draw_text_box(pygame.Rect(24, MAP_H + 20, 310, 40), self.message or hint,
                           locked=self.over_label() if self.time_up else None)
        # Progress per continent
        x = 380
        total_done = total = 0
        for cont in self.scope.views:
            qs = [c for c in self.countries if c.continent == cont and c.in_quiz]
            done = sum(c.found for c in qs)
            total_done += done
            total += len(qs)
            self.screen.blit(self.small.render(cont, True, TEXT_DIM), (x, MAP_H + 30))
            self.screen.blit(self.font.render(f"{done}/{len(qs)}", True, TEXT), (x, MAP_H + 55))
            x += 125
        # Overall total, separated from the per-continent scores
        pygame.draw.line(self.screen, TEXT_DIM, (x - 15, MAP_H + 28), (x - 15, MAP_H + 85))
        self.screen.blit(self.small.render("Total", True, TEXT_DIM), (x, MAP_H + 30))
        self.screen.blit(self.big.render(f"{total_done}/{total}", True, FOUND), (x, MAP_H + 50))

    def draw_continent_panel(self):
        qs = self.quiz_countries()
        done = sum(c.found for c in qs)
        self.screen.blit(self.big.render(self.heading(), True, TEXT), (24, MAP_H + 14))
        self.screen.blit(self.font.render(f"{done} / {len(qs)} {self.scope.nouns}", True, TEXT_DIM), (24, MAP_H + 60))
        if self.scope.has_world:
            self.screen.blit(self.small.render(f"Total: {self.total_found()} / {self.total_countries()} worldwide",
                                               True, TEXT_DIM), (24, MAP_H + 90))

        self.draw_text_box(pygame.Rect(330, MAP_H + 20, 520, 40), self.message, 
                           locked=self.over_label() if self.time_up else "Answers are showing" if self.show_missed else None)

        if self.continent in self.gave_up:
            self.giveup_btn.text = "Hide names" if self.show_missed else "Show names"
        else:
            self.giveup_btn.text = "Give up"
        if self.scope.has_world:
            self.back_btn.draw(self.screen, self.font)
        self.giveup_btn.draw(self.screen, self.font)

    def draw_text_box(self, box, message, locked=None):
        """Answer box; `locked` is the text shown in place of the input when typing is disabled."""
        if locked:
            pygame.draw.rect(self.screen, (95, 100, 112), box, border_radius=6)
            label = self.font.render(locked, True, (175, 180, 190))
            self.screen.blit(label, (box.x + 12, box.y + 8))
            self.screen.blit(self.small.render(message, True, TEXT), (box.x, box.bottom + 12))
            return
        pygame.draw.rect(self.screen, (250, 250, 250), box, border_radius=6)
        cursor = "|" if (pygame.time.get_ticks() // 500) % 2 else ""
        inner = box.inflate(-24, 0)  # text area, clipped so long names stay inside the box
        if not self.text:
            label = self.font.render(f"Type a {self.scope.noun} name…", True, (150, 150, 150))
            self.screen.blit(label, (inner.x + 4, box.y + 8), pygame.Rect(0, 0, inner.w - 4, box.h))
            if cursor:  # blinking cursor at the start, where typing begins
                pygame.draw.line(self.screen, (20, 20, 20), (inner.x + 1, box.y + 9), (inner.x + 1, box.bottom - 9), 2)
        else:
            typed = self.font.render(self.text, True, (20, 20, 20))
            self.screen.blit(typed, (inner.x, box.y + 8), pygame.Rect(0, 0, inner.w, box.h))
            x = inner.x + typed.get_width()
            matches = self.suggestions()
            if matches:
                # Grey "ghost" text completing the name; Tab accepts it.
                rest = matches[self.suggest_index % len(matches)][len(self.text):]
                more = f"  ({self.suggest_index % len(matches) + 1}/{len(matches)})" if len(matches) > 1 else ""
                ghost = self.font.render(rest + more, True, (165, 165, 165))
                self.screen.blit(ghost, (x, box.y + 8), pygame.Rect(0, 0, max(0, inner.right - x), box.h))
            if cursor and x < inner.right:
                pygame.draw.line(self.screen, (20, 20, 20), (x + 1, box.y + 9), (x + 1, box.bottom - 9), 2)
        # Clip long messages so they never run into the scores next to the box.
        msg = self.small.render(message, True, TEXT)
        self.screen.blit(msg, (box.x, box.bottom + 12), pygame.Rect(0, 0, box.w + 10, msg.get_height()))

    # ---------- Modes menu ----------
    def mode_group(self):
        """The MENU group the current mode is in."""
        for _, groups in MENU:
            for group, _, modes in groups:
                if any(key == self.mode for key, _ in modes):
                    return group

    def menu_items(self):
        """(key, label, rect, kind) for each visible row of the open Modes menu; kind: header, group or mode."""
        rows = []
        for section, groups in MENU:
            rows.append((section, section.upper(), "header"))
            for group, label, modes in groups:
                rows.append((group, label, "group"))
                if self.menu_group == group:
                    rows += [(key, sub_label, "mode") for key, sub_label in modes]
        x, y = self.modes_btn.rect.x, self.modes_btn.rect.bottom + 6
        items = []
        for key, label, kind in rows:
            h = 30 if kind == "header" else 40
            items.append((key, label, pygame.Rect(x, y, 230, h), kind))
            y += h
        return items

    def handle_menu_event(self, event):
        """Clicks on the Modes button / menu. Returns True if the event was used up."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.menu_open:
            self.menu_open = False
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.modes_btn.rect.collidepoint(event.pos):
            self.menu_open = not self.menu_open
            self.menu_group = self.mode_group()  # open on the current mode's group
            return True
        if not self.menu_open:
            return False
        for key, _, rect, kind in self.menu_items():
            if rect.collidepoint(event.pos):
                if kind == "group":
                    self.menu_group = None if self.menu_group == key else key
                elif kind == "mode":
                    self.set_mode(key)
                return True
        self.menu_open = False  # clicked elsewhere: just close the menu
        return True

    def handle_top_button(self, event):
        """Leaderboard (countries / states game) and Reset (flag / capital games) buttons. True if clicked."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.timed_game() and self.leaderboard_btn.rect.collidepoint(event.pos):
            self.modal = "leaderboard"
            return True
        if self.show_flag_reset() and self.flag_reset_btn.rect.collidepoint(event.pos):
            # Needs a second click to confirm, like "Start over". Only resets this game's continents.
            if pygame.time.get_ticks() < self.reset_confirm_until:
                self.reset_confirm_until = 0
                self.perfect[self.progress_key()].clear()
                save_progress(self.perfect)
                self.rerender()
            else:
                self.reset_confirm_until = pygame.time.get_ticks() + 3000
            return True
        return False

    def show_flag_reset(self):
        """The Reset button of the flag / capital games: on the globe, or the USA map when no game is running."""
        return self.quiz_game() and (self.continent is None or (not self.scope.has_world and not self.quiz))

    def set_mode(self, mode):
        """Switch game mode, staying zoomed into the current continent if there is one.

        Each map (world, USA) keeps its own game in progress; the timer pauses in the other modes.
        """
        self.menu_open = False
        if mode == self.mode:
            return
        self.mode = mode
        self.scope = self.scopes[self.md.scope]
        self.quiz = None
        self.learn_selected = None
        self.hover = None
        self.text = ""
        self.message = ""
        self.show_missed = False
        self.auto_zoom_out_at = None
        if not self.scope.has_world and self.continent is None:  # first visit to the USA map
            self.continent = "USA"
            self.cont_view = View(USA_VIEW)
        self.render_world()
        if self.continent is not None:
            self.render_continent()
            if self.naming_game():
                self.message = f"Name the {self.scope.nouns} of {self.place()}!"
            elif self.guess_game():
                if not self.guess_order:
                    self.new_guess_order()
                    self.render_continent()
                what = "capital" if self.capital_guess() else "name"
                self.message = f"Type the blue state's {what}. Press Space to come back to it later."
            elif self.quiz_game():
                self.start_flag_quiz("game")  # straight into this continent's (or the USA's) game

    def draw_modes_menu(self):
        self.modes_btn.draw(self.screen, self.font)
        if not self.menu_open:
            return
        items = self.menu_items()
        frame = items[0][2].unionall([r for _, _, r, _ in items]).inflate(8, 8)
        pygame.draw.rect(self.screen, PANEL, frame, border_radius=8)
        mouse = pygame.mouse.get_pos()
        for key, label, rect, kind in items:
            if kind == "header":  # section name, not clickable
                text = self.label_font.render(label, True, TEXT_DIM)
                self.screen.blit(text, text.get_rect(midleft=(rect.x + 12, rect.centery + 3)))
                continue
            if rect.collidepoint(mouse):
                pygame.draw.rect(self.screen, (70, 76, 88), rect, border_radius=6)
            text = self.font.render(label, True, TEXT)
            self.screen.blit(text, text.get_rect(midleft=(rect.x + (16 if kind == "group" else 44), rect.centery)))
            # Green dot on the current mode (on its group while the group is closed).
            if kind == "mode" and key == self.mode:
                pygame.draw.circle(self.screen, FOUND, (rect.x + 30, rect.centery), 5)
            elif kind == "group" and key == self.mode_group() and self.menu_group != key:
                pygame.draw.circle(self.screen, FOUND, (rect.right - 12, rect.centery), 5)
            if kind == "group":  # little arrow: right when closed, down when open
                cx, cy = rect.right - 34, rect.centery
                pts = ([(cx - 5, cy - 3), (cx + 5, cy - 3), (cx, cy + 4)] if self.menu_group == key
                       else [(cx - 3, cy - 5), (cx - 3, cy + 5), (cx + 4, cy)])
                pygame.draw.polygon(self.screen, TEXT_DIM, pts)

    # ---------- flags ----------
    def flag_image(self, country, size):
        """The country's flag scaled to fit inside size=(w, h), keeping its shape."""
        key = (country.code, size)
        if key not in self.flag_cache:
            try:
                img = pygame.image.load(os.path.join(FLAGS_DIR, country.code + ".png")).convert_alpha()
                scale = min(size[0] / img.get_width(), size[1] / img.get_height())
                img = pygame.transform.smoothscale(img, (round(img.get_width() * scale),
                                                         round(img.get_height() * scale)))
            except (OSError, pygame.error):
                img = pygame.Surface((size[0], size[1] * 2 // 3))  # missing file: grey box with "?"
                img.fill((120, 125, 135))
                q = self.big.render("?", True, TEXT)
                img.blit(q, q.get_rect(center=img.get_rect().center))
            self.flag_cache[key] = img
        return self.flag_cache[key]

    def draw_flag(self, country, box):
        """Flag centred in a pygame.Rect, with a thin border."""
        img = self.flag_image(country, (box.w, box.h))
        rect = img.get_rect(center=box.center)
        self.screen.blit(img, rect)
        pygame.draw.rect(self.screen, BORDER, rect, 1)

    def fit_text(self, font, text, colour, max_w):
        img = font.render(text, True, colour)
        if img.get_width() > max_w:
            img = pygame.transform.smoothscale_by(img, max_w / img.get_width())
        return img

    def draw_country_highlight(self, country, colour, view=None, dots=None):
        """Paint one country (and its dot, if it is tiny) on top of the map (the continent map by default)."""
        view = view or self.cont_view
        for ring in country.rings:
            pts = view.project_ring(ring)
            if len(pts) >= 3:
                pygame.draw.polygon(self.screen, colour, pts)
                pygame.draw.polygon(self.screen, BORDER, pts, 1)
        for x, y, c in self.continent_dots if dots is None else dots:
            if c is country:
                pygame.draw.circle(self.screen, colour, (x, y), 7)
                pygame.draw.circle(self.screen, BORDER, (x, y), 7, 1)

    def draw_flags_world_panel(self):
        self.screen.blit(self.big.render(self.md.label, True, TEXT), (24, MAP_H + 14))
        thing = "flag" if self.subject() == "flags" else "capital"
        if not self.quiz_game():
            hint = f"Click a continent, then hover over any country to see its {thing}."
        else:
            done = len(self.perfect[self.progress_key()])
            hint = (f"Click a continent, then pick the right {thing} for each country. Get them all right "
                    f"to turn it green!  ({done} / {len(self.scope.views)} done)")
        self.screen.blit(self.font.render(hint, True, TEXT_DIM), (24, MAP_H + 62))
        if self.hover and self.hover.continent in self.scope.views:
            label = self.big.render(f"{self.hover.continent}  ›", True, LAND_HOVER)
            self.screen.blit(label, label.get_rect(topright=(WIDTH - 24, MAP_H + 14)))

    # ---------- Countries > Learn ----------
    def handle_country_learn_event(self, event):
        """Zoomed into a continent in Countries > Learn: hover shows names, Back/Esc returns."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.zoom_out()
        elif event.type == pygame.MOUSEMOTION:
            self.hover = self.country_at(event.pos, self.cont_view, self.continent_dots)
        elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and self.scope.has_world
              and self.cl_back_btn.rect.collidepoint(event.pos)):
            self.zoom_out()

    def draw_hover_card(self, view, dots):
        """Highlight the country under the mouse and show its name and flag next to the cursor."""
        c = self.hover
        if not c or not c.in_quiz or c.continent not in self.scope.views:
            return
        if self.continent is not None and c.continent != self.continent:
            return
        self.draw_country_highlight(c, LAND_HOVER, view, dots)
        name = self.fit_text(self.name_font, c.name, TEXT, 260)
        card = self.learn_card(172, max(200, name.get_width() + 32))
        pill = pygame.Surface(card.size, pygame.SRCALPHA)
        pygame.draw.rect(pill, (*PANEL, 235), pill.get_rect(), border_radius=10)
        self.screen.blit(pill, card)
        pygame.draw.rect(self.screen, OUTLINE, card, 2, border_radius=10)
        self.draw_flag(c, pygame.Rect(card.x + 16, card.y + 14, card.w - 32, 106))
        self.screen.blit(name, name.get_rect(midbottom=(card.centerx, card.bottom - 12)))

    def draw_country_learn_panel(self):
        if self.continent is None:
            self.screen.blit(self.big.render("Countries: Learn", True, TEXT), (24, MAP_H + 14))
            hint = "Hover over a country to see its name and flag. Click a continent to zoom in."
        else:
            self.screen.blit(self.big.render(self.heading(), True, TEXT), (24, MAP_H + 14))
            hint = f"Hover over a {self.scope.noun} to see its name and flag."
            if self.scope.has_world:
                self.cl_back_btn.draw(self.screen, self.font)
        self.screen.blit(self.font.render(hint, True, TEXT_DIM), (24, MAP_H + 62))

    # ---------- Flags > Learn ----------
    def handle_learn_event(self, event):
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.zoom_out()
        elif event.type == pygame.MOUSEMOTION:
            # Hovering a country shows its flag / capital, like Countries Learn.
            self.hover = self.learn_selected = self.learn_country_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.quiz_game():  # USA map between games: only the Start button
                if self.start_btn.rect.collidepoint(event.pos):
                    self.start_flag_quiz("game")
            elif self.learn_back_btn.rect.collidepoint(event.pos) and self.scope.has_world:
                self.zoom_out()
            elif self.practice_btn.rect.collidepoint(event.pos):
                self.start_flag_quiz("practice")

    def learn_country_at(self, pos):
        hit = self.country_at(pos, self.cont_view, self.continent_dots)
        return hit if hit and hit.in_quiz and hit.continent == self.continent else None

    def learn_card(self, h, w=300):
        """Rect for a Learn card of size (w, h) next to the mouse cursor, flipped to stay on the map."""
        card = pygame.Rect(0, 0, w, h)
        mx, my = pygame.mouse.get_pos()
        card.topleft = (mx + 18, my + 18)
        if card.right > WIDTH - 8:  # flip to the other side of the cursor near the edges
            card.right = mx - 18
        if card.bottom > MAP_H - 8:
            card.bottom = my - 18
        card.clamp_ip(pygame.Rect(0, 0, WIDTH, MAP_H))
        return card

    def draw_learn_view(self):
        if self.quiz_game():  # USA map between games: nothing to explore
            return
        if self.hover and self.hover is not self.learn_selected:
            self.draw_country_highlight(self.hover, LAND_HOVER)
        c = self.learn_selected
        if c:
            self.draw_country_highlight(c, SELECTED)
        if self.subject() == "capitals":
            self.draw_capitals_learn(c)
            return
        if not c:
            return
        card = self.learn_card(248)
        pill = pygame.Surface(card.size, pygame.SRCALPHA)
        pygame.draw.rect(pill, (*PANEL, 235), pill.get_rect(), border_radius=10)
        self.screen.blit(pill, card)
        pygame.draw.rect(self.screen, OUTLINE, card, 2, border_radius=10)
        self.draw_flag(c, pygame.Rect(card.x + 16, card.y + 16, card.w - 32, 170))
        name = self.fit_text(self.name_font, c.name, TEXT, card.w - 24)
        self.screen.blit(name, name.get_rect(midbottom=(card.centerx, card.bottom - 16)))

    def draw_capitals_learn(self, selected):
        """Capitals > Learn: a dot on every capital, and a card + label for the selected country."""
        for c in self.quiz_countries():
            x, y = self.cont_view.project_ring([c.capital_pt])[0]
            pygame.draw.circle(self.screen, PANEL, (x, y), 4)
        if not selected:
            return
        x, y = self.cont_view.project_ring([selected.capital_pt])[0]
        pygame.draw.circle(self.screen, MISSED, (x, y), 8)
        pygame.draw.circle(self.screen, TEXT, (x, y), 8, 2)
        tag = self.label_font.render(selected.capital, True, TEXT)
        rect = tag.get_rect(midbottom=(x, y - 12)).inflate(12, 6)
        rect.clamp_ip(pygame.Rect(4, 4, WIDTH - 8, MAP_H - 8))
        pygame.draw.rect(self.screen, PANEL, rect, border_radius=5)
        self.screen.blit(tag, tag.get_rect(center=rect.center))
        card = self.learn_card(236)
        pill = pygame.Surface(card.size, pygame.SRCALPHA)
        pygame.draw.rect(pill, (*PANEL, 235), pill.get_rect(), border_radius=10)
        self.screen.blit(pill, card)
        pygame.draw.rect(self.screen, OUTLINE, card, 2, border_radius=10)
        self.draw_flag(selected, pygame.Rect(card.x + 16, card.y + 16, card.w - 32, 90))
        lines = [(self.name_font, selected.name, TEXT), (self.small, "Capital", TEXT_DIM),
                 (self.name_font, selected.capital, LAND_HOVER)]
        y = card.y + 120
        for font, text, colour in lines:
            img = self.fit_text(font, text, colour, card.w - 24)
            self.screen.blit(img, img.get_rect(midtop=(card.centerx, y)))
            y += img.get_height() + 8

    def draw_flags_continent_panel(self):
        self.screen.blit(self.big.render(self.heading(), True, TEXT), (24, MAP_H + 14))
        self.quit_btn.text = "Back to globe" if self.scope.has_world else "Stop game"
        q = self.quiz
        if q and q["kind"] == "practice":
            info = f"Practice test  ·  {q['score']} / {q['asked']} correct"
            self.stop_btn.draw(self.screen, self.font)
        elif q:
            word = "Flag" if self.subject() == "flags" else "Capital"
            info = f"{word} {min(q['index'], len(q['order']))} of {len(q['order'])}  ·  {q['score']} correct"
            self.quit_btn.draw(self.screen, self.font)
        elif self.quiz_game():  # USA map between games
            thing = "flag" if self.subject() == "flags" else "capital"
            info = f"Pick the right {thing} for every state. Get them all right to turn the map green!"
            self.start_btn.draw(self.screen, self.font)
        else:
            thing = "flag" if self.subject() == "flags" else "capital"
            info = f"Hover over a {self.scope.noun} to see its {thing}, or take the practice test."
            if self.scope.has_world:
                self.learn_back_btn.draw(self.screen, self.font)
            self.practice_btn.draw(self.screen, self.font)
        self.screen.blit(self.font.render(info, True, TEXT_DIM), (24, MAP_H + 62))

    # ---------- multiple-choice quiz: flags or capitals (Learn > Practice test, and Game) ----------
    def start_flag_quiz(self, kind):
        """kind = "practice" (endless) or "game" (each country once). Both move on by themselves."""
        order = self.quiz_countries()
        random.shuffle(order)
        self.quiz = {"kind": kind, "order": order, "index": 0, "score": 0, "asked": 0,
                     "answer": None, "choices": [], "picked": None, "advance_at": None,
                     "done": False}
        self.hover = None
        self.next_question()

    def next_question(self):
        q = self.quiz
        q["picked"], q["advance_at"] = None, None
        if q["index"] >= len(q["order"]):
            if q["kind"] == "game":
                q["done"] = True
                perfect = self.perfect[self.progress_key()]
                if q["score"] == len(q["order"]) and self.continent not in perfect:
                    perfect.add(self.continent)
                    save_progress(self.perfect)
                return
            last = q["order"][-1]  # practice: go round again, without repeating the last country
            random.shuffle(q["order"])
            if q["order"][0] is last:
                q["order"].append(q["order"].pop(0))
            q["index"] = 0
        q["answer"] = q["order"][q["index"]]
        q["index"] += 1
        others = [c for c in q["order"] if c is not q["answer"]]
        q["choices"] = random.sample(others, 3) + [q["answer"]]
        random.shuffle(q["choices"])

    def pick_flag(self, i):
        q = self.quiz
        if q["picked"] is not None or q["done"]:
            return
        q["picked"] = i
        q["asked"] += 1
        now = pygame.time.get_ticks()
        if q["choices"][i] is q["answer"]:
            q["score"] += 1
            q["advance_at"] = now + 1000
        else:
            q["advance_at"] = now + 2500  # a bit longer, to see the right answer

    def choice_rects(self):
        if self.subject() == "capitals":  # text answers: shorter boxes
            w, h, gap_x, gap_y, y0 = 320, 120, 24, 24, 170
        else:
            w, h, gap_x, gap_y, y0 = 290, 200, 24, 24, 120
        x0 = WIDTH // 2 - w - gap_x // 2
        return [pygame.Rect(x0 + (i % 2) * (w + gap_x), y0 + (i // 2) * (h + gap_y), w, h) for i in range(4)]

    def handle_quiz_event(self, event):
        q = self.quiz
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.end_flag_quiz()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and q["done"]:
                self.start_flag_quiz("game")
            elif pygame.K_1 <= event.key <= pygame.K_4:
                self.pick_flag(event.key - pygame.K_1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if q["done"]:
                if self.replay_btn.rect.collidepoint(pos):
                    self.start_flag_quiz("game")
                elif self.done_globe_btn.rect.collidepoint(pos):
                    self.zoom_out()
            elif (self.stop_btn if q["kind"] == "practice" else self.quit_btn).rect.collidepoint(pos):
                self.end_flag_quiz()
            else:
                for i, rect in enumerate(self.choice_rects()):
                    if rect.collidepoint(pos):
                        self.pick_flag(i)

    def end_flag_quiz(self):
        """Practice test: back to exploring the continent. Game: back to the globe (USA: to the map)."""
        if self.quiz["kind"] == "practice":
            self.quiz = None
        else:
            self.zoom_out()

    def draw_flag_quiz(self):
        q = self.quiz
        shade = pygame.Surface((WIDTH, MAP_H), pygame.SRCALPHA)
        shade.fill((20, 22, 28, 110))  # dims the map, but keeps it visible behind the question
        self.screen.blit(shade, (0, 0))
        if q["done"]:
            self.draw_flag_game_done()
            return

        # The country to find, at the top of the screen.
        capitals = self.subject() == "capitals"
        ask = self.font.render("What is the capital of" if capitals else "Which flag belongs to", True, TEXT_DIM)
        name = self.fit_text(self.title_font, q["answer"].name, TEXT, 700)
        banner = pygame.Rect(0, 0, max(ask.get_width(), name.get_width()) + 48, 92)
        banner.midtop = (WIDTH // 2, 12)
        pygame.draw.rect(self.screen, PANEL, banner, border_radius=10)
        self.screen.blit(ask, ask.get_rect(midtop=(banner.centerx, banner.y + 8)))
        self.screen.blit(name, name.get_rect(midbottom=(banner.centerx, banner.bottom - 8)))

        mouse = pygame.mouse.get_pos()
        answered = q["picked"] is not None
        for i, (rect, c) in enumerate(zip(self.choice_rects(), q["choices"])):
            pygame.draw.rect(self.screen, (66, 72, 86), rect, border_radius=10)
            pygame.draw.rect(self.screen, OUTLINE, rect, 2, border_radius=10)  # outline on every answer
            # Room for the name underneath is always kept, so nothing moves when the answer is shown.
            if capitals:
                city = self.fit_text(self.name_font, c.capital, TEXT, rect.w - 24)
                self.screen.blit(city, city.get_rect(center=(rect.centerx, rect.centery - 10)))
            else:
                flag_box = pygame.Rect(rect.x + 14, rect.y + 14, rect.w - 28, rect.h - 54)
                self.draw_flag(c, flag_box)
            if answered:  # show whose flag / capital each one is, to learn from
                label = self.fit_text(self.small, c.name, TEXT, rect.w - 20)
                self.screen.blit(label, label.get_rect(midbottom=(rect.centerx, rect.bottom - 10)))
            border = None
            if answered and c is q["answer"]:
                border = FOUND
            elif answered and i == q["picked"]:
                border = MISSED
            elif not answered and rect.collidepoint(mouse):
                border = LAND_HOVER
            if border:
                pygame.draw.rect(self.screen, border, rect, 5, border_radius=10)

        if answered:
            right = q["choices"][q["picked"]] is q["answer"]
            wrong = q["choices"][q["picked"]]
            if right:
                text = "Correct!"
            elif capitals:
                text = f"Incorrect. {wrong.capital} is the capital of {wrong.name}. The right answer is in green."
            else:
                text = f"Incorrect. That's {wrong.name}. The right flag is in green."
            msg = self.fit_text(self.big if right else self.name_font, text, FOUND if right else MISSED, WIDTH - 120)
            box = msg.get_rect(midtop=(WIDTH // 2, 560)).inflate(32, 12)
            pygame.draw.rect(self.screen, PANEL, box, border_radius=8)
            self.screen.blit(msg, msg.get_rect(center=box.center))

    def draw_flag_game_done(self):
        q = self.quiz
        card = self.done_card
        pygame.draw.rect(self.screen, PANEL, card, border_radius=12)
        n = len(q["order"])
        perfect = q["score"] == n
        title = "Perfect!" if perfect else "Finished!"
        world = self.scope.has_world
        what = f"{self.subject()} of {self.continent}" if world else f"state {self.subject()}"
        where = "globe" if world else "map"
        lines = [(self.title_font, title, FOUND if perfect else TEXT),
                 (self.font, f"{q['score']} / {n} {what} correct", TEXT),
                 (self.small, f"All of them right! {self.place()[0].upper() + self.place()[1:]} is now green "
                              f"on the {where}." if perfect
                  else f"Get them all right to turn {'the continent' if world else 'the map'} green.", TEXT_DIM)]
        self.done_globe_btn.text = "Back to globe" if world else "Close"
        y = card.y + 30
        for font, text, colour in lines:
            img = font.render(text, True, colour)
            self.screen.blit(img, img.get_rect(midtop=(card.centerx, y)))
            y += img.get_height() + 14
        self.replay_btn.draw(self.screen, self.font)
        self.done_globe_btn.draw(self.screen, self.font)


for _name in SCOPE_ATTRS:
    setattr(App, _name, property(lambda self, n=_name: getattr(self.scope, n),
                                 lambda self, value, n=_name: setattr(self.scope, n, value)))


if __name__ == "__main__":
    App().run()
