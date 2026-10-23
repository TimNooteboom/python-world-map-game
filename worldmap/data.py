"""Countries and US states: loading them, their accepted names, and point-in-shape tests."""

import json
import unicodedata

from .config import CAPITALS_FILE, DATA_FILE, INSETS, STATES_FILE

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
    "Saint Kitts and Nevis": ["st kitts and nevis", "saint kitts"],  # "st kitts" works too: st -> saint
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


def load_countries():
    """All countries except Antarctica, each with its capital (or "?" if unknown)."""
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
    return countries


def load_state_features():
    """The raw state shapes; each game that needs its own states makes them with [State(f) for f in ...]."""
    with open(STATES_FILE, encoding="utf-8") as f:
        return json.load(f)["features"]
