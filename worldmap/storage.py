"""Saving and loading scoreboards and flag/capital progress."""

import json

from .config import FLAG_PROGRESS_FILE

SCORE_FIELDS = ("countries", "states", "capitals")  # what a saved score counts, depending on the board
PROGRESS_KEYS = ("flags", "capitals", "us_flags", "us_capitals")


def score_count(score):
    """How many countries / states / capitals a saved score got."""
    return next((score[k] for k in SCORE_FIELDS if k in score), 0)


def rank_key(score):
    # Most countries first; ties go to whoever was faster.
    return (-score_count(score), score["seconds"])


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
