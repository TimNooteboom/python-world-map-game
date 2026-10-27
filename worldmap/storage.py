"""Saving and loading scoreboards and flag/capital progress.

Files that are missing or damaged are treated as empty, and a file that can't be written is skipped,
so a problem with a save file never stops the game.
"""

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


def top_10(scores):
    return sorted(scores, key=rank_key)[:10]


def makes_top_10(result, scores):
    """True if result would get onto a board that currently has these scores (beating 10th place)."""
    top = top_10(scores)
    return len(top) < 10 or rank_key(result) < rank_key(top[-1])


def _read_json(path):
    """The file's JSON object, or {} if it's missing, unreadable or not an object."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json(path, data, **options):
    """Write data to path; False if it couldn't be written (e.g. no permission)."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, **options)
    except OSError:
        return False
    return True


def _valid_score(score):
    return (isinstance(score, dict) and isinstance(score.get("name"), str)
            and isinstance(score.get("seconds"), (int, float))
            and any(isinstance(score.get(k), int) for k in SCORE_FIELDS))


def load_scores(path, starting=None):
    """(top 10 scores, last name typed) for a board.

    The player's saved scores are merged with the bundled starting scores, so a new version of the
    game brings its newest starting scores to players who already have scores of their own.
    """
    saved = _read_json(path) if path else {}
    bundled = _read_json(starting) if starting else {}
    merged, seen = [], set()
    for data in (saved, bundled):
        scores = data.get("scores")
        for score in scores if isinstance(scores, list) else []:
            if not _valid_score(score):
                continue  # skip damaged entries
            key = (score.get("name"), score_count(score), score.get("seconds"), score.get("date"))
            if key not in seen:  # the same score can be in both files
                seen.add(key)
                merged.append(score)
    # Only the player's own last-typed name is pre-filled, never the starting scores' names.
    last_name = saved.get("last_name")
    return top_10(merged), last_name if isinstance(last_name, str) else ""


def save_scores(path, scores, last_name):
    """Save the top 10 of scores; False if the file couldn't be written."""
    return _write_json(path, {"scores": top_10(scores), "last_name": last_name}, ensure_ascii=False)


def load_progress():
    """{game: set of continents done without a miss} for the flag and capital games (world and USA)."""
    data = _read_json(FLAG_PROGRESS_FILE)
    data["flags"] = data.get("perfect", [])  # world flags were saved as "perfect" before the other games
    return {key: set(data[key]) if isinstance(data.get(key), list) else set() for key in PROGRESS_KEYS}


def save_progress(perfect):
    """Save the green continents; False if the file couldn't be written."""
    data = {key: sorted(perfect[key]) for key in PROGRESS_KEYS}
    data["perfect"] = data.pop("flags")
    return _write_json(FLAG_PROGRESS_FILE, data)
