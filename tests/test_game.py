"""Automated checks for the game. Run from the project folder with:

    python -m unittest discover tests

The game runs without a window, and saves go to a temporary folder (not your real scores).
"""

import json
import os
import stat
import sys
import tempfile
import unittest

SAVE_DIR = tempfile.mkdtemp(prefix="world_map_test_")
os.environ["WORLD_MAP_SAVE_DIR"] = SAVE_DIR  # must be set before the game is imported
os.environ["SDL_VIDEODRIVER"] = "dummy"  # no window
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pygame  # noqa: E402

from worldmap import config, storage  # noqa: E402
from worldmap.app import App  # noqa: E402
from worldmap.data import normalize  # noqa: E402

APP = None


def app():
    """One game window shared by the tests (opening one is slow); each test starts from the globe."""
    global APP
    if APP is None:
        APP = App()
    return APP


def place(a, name):
    return next(c for c in a.countries if c.name == name)


def type_text(a, text):
    for ch in text:
        a.handle_event(pygame.event.Event(pygame.TEXTINPUT, text=ch))


def press(a, key):
    a.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode="", scancode=0))


class StorageTests(unittest.TestCase):
    def path(self, name):
        return os.path.join(SAVE_DIR, name)

    def test_damaged_or_missing_files_are_treated_as_empty(self):
        for content in ("not json", "[]", '{"scores": "oops"}', '{"scores": [{"countries": 3, "name": "x"}]}'):
            with open(self.path("bad.json"), "w") as f:
                f.write(content)
            self.assertEqual(storage.load_scores(self.path("bad.json")), ([], ""))
        self.assertEqual(storage.load_scores(self.path("missing.json")), ([], ""))

    def test_damaged_progress_file_does_not_stop_the_game(self):
        with open(config.FLAG_PROGRESS_FILE, "w") as f:
            f.write("[]")
        self.assertEqual(storage.load_progress(), {key: set() for key in storage.PROGRESS_KEYS})
        os.remove(config.FLAG_PROGRESS_FILE)

    def test_a_file_that_cannot_be_written_is_reported_not_raised(self):
        path = self.path("readonly.json")
        with open(path, "w") as f:
            f.write("{}")
        os.chmod(path, stat.S_IRUSR)
        try:
            self.assertFalse(storage.save_scores(path, [], "x"))
        finally:
            os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)

    def test_only_the_top_10_are_kept_and_bundled_scores_are_merged(self):
        mine = [{"states": 50, "seconds": 100 + i, "name": "me", "date": "2026-01-01"} for i in range(8)]
        theirs = [{"states": 50, "seconds": 90 + i, "name": "them", "date": "2026-01-01"} for i in range(5)]
        storage.save_scores(self.path("mine.json"), mine, "me")
        with open(self.path("bundled.json"), "w") as f:
            json.dump({"scores": theirs + mine[:2]}, f)  # overlaps with mine: no duplicates
        top, last_name = storage.load_scores(self.path("mine.json"), self.path("bundled.json"))
        self.assertEqual(last_name, "me")
        self.assertEqual([s["seconds"] for s in top], [90, 91, 92, 93, 94, 100, 101, 102, 103, 104])
        self.assertTrue(storage.makes_top_10({"states": 50, "seconds": 99}, top))
        self.assertFalse(storage.makes_top_10({"states": 50, "seconds": 104}, top))  # a tie keeps the old one
        self.assertFalse(storage.makes_top_10({"states": 49, "seconds": 1}, top))


class NameTests(unittest.TestCase):
    def setUp(self):
        self.a = app()
        self.a.set_mode("countries_learn")  # leave and re-enter the Countries Game for a clean start
        self.a.set_mode("countries")
        if self.a.continent is not None:
            self.a.zoom_out()
            self.a.anim = None
        self.a.mode_obj.reset_all()

    def test_normalize(self):
        self.assertEqual(normalize("Côte d'Ivoire"), "cote divoire")
        self.assertEqual(normalize("St. Kitts"), "saint kitts")
        self.assertEqual(normalize("The Gambia"), "gambia")

    def test_a_name_that_starts_another_waits_for_enter(self):
        a = self.a
        type_text(a, "Niger")
        self.assertFalse(place(a, "Niger").found)
        type_text(a, "ia")
        self.assertTrue(place(a, "Nigeria").found)
        self.assertFalse(place(a, "Niger").found)
        type_text(a, "Uk")
        press(a, pygame.K_RETURN)
        self.assertTrue(place(a, "United Kingdom").found)
        self.assertFalse(place(a, "Ukraine").found)

    def test_saint_kitts_spellings(self):
        for spelling in ("st kitts", "Saint Kitts", "St. Kitts and Nevis"):
            place(self.a, "Saint Kitts and Nevis").found = False
            self.a.text = ""
            type_text(self.a, spelling)
            self.assertTrue(place(self.a, "Saint Kitts and Nevis").found, spelling)


class ModeTests(unittest.TestCase):
    def test_every_mode_draws_on_the_globe_and_every_continent(self):
        a = app()
        for key, info in config.MODES.items():
            a.set_mode(key)
            if info.scope == "world":
                if a.continent is not None:
                    a.zoom_out()
                a.anim = None
                a.frame(0.016)
                for continent in config.CONTINENT_VIEWS:
                    a.zoom_in(continent)
                    a.anim = None
                    a.frame(0.016)
                    a.zoom_out()
                    a.anim = None
            a.frame(0.016)

    def test_running_out_of_time_ends_the_game(self):
        a = app()
        a.set_mode("states")
        a.mode_obj.reset_all()
        type_text(a, "Texas")
        a.frame(config.STATE_TIME_LIMIT + 1)
        self.assertTrue(a.time_up)
        self.assertIn(a.modal, ("name", "scores"))
        a.modal = None
        a.mode_obj.reset_all()

    def test_guess_the_state(self):
        a = app()
        a.set_mode("us_guess")
        a.mode_obj.reset_all()
        m = a.mode_obj
        first = m.target()
        type_text(a, first.name)
        self.assertTrue(first.found)
        second = m.target()
        type_text(a, " ")  # come back to it later
        self.assertIsNot(m.target(), second)
        self.assertIs(a.guess_order[-1], second)
        wrong = next(c for c in a.countries if c.in_quiz and c is not m.target() and not c.found)
        target = m.target()
        type_text(a, wrong.name)
        press(a, pygame.K_RETURN)
        self.assertTrue(target.missed)
        a.mode_obj.reset_all()

    def test_a_perfect_flag_round_turns_the_continent_green_and_reset_clears_it(self):
        a = app()
        a.set_mode("flags_game")
        if a.continent is not None:
            a.zoom_out()
        a.anim = None
        a.zoom_in("Oceania")
        a.anim = None
        m = a.mode_obj
        while not m.quiz.done:
            m.pick(m.quiz.choices.index(m.quiz.answer))
            m.next_question()
        self.assertIn("Oceania", a.perfect["flags"])
        m.reset_progress()
        self.assertEqual(a.perfect["flags"], set())
        a.zoom_out()
        a.anim = None


if __name__ == "__main__":
    unittest.main()
