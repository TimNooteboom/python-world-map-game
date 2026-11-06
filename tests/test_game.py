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

    def found(self, *names):
        return [place(self.a, n).found for n in names]

    def test_a_short_name_counts_straight_away(self):
        a = self.a
        type_text(a, "Niger")
        self.assertEqual(self.found("Niger"), [True])
        type_text(a, "Kenya")  # straight on to the next country
        self.assertEqual(self.found("Niger", "Kenya", "Nigeria"), [True, True, False])
        type_text(a, "UK")
        press(a, pygame.K_RETURN)
        self.assertEqual(self.found("United Kingdom", "Ukraine"), [True, False])
        self.assertEqual(a.text, "")

    def test_typing_the_longer_name_does_not_count_the_short_one(self):
        type_text(self.a, "Nigeria")
        self.assertEqual(self.found("Niger", "Nigeria"), [False, True])
        type_text(self.a, "Ukraine")
        self.assertEqual(self.found("United Kingdom", "Ukraine"), [False, True])

    def test_autofill_from_the_end_of_a_name(self):
        type_text(self.a, "mic")
        self.assertEqual(self.a.mode_obj.suggestions(), ["Micronesia"])
        press(self.a, pygame.K_TAB)
        self.assertEqual(self.found("Federated States of Micronesia"), [True])

    def test_clicking_an_unnamed_country_gives_a_hint_once_started_and_zoomed_in(self):
        a, m = self.a, self.a.mode_obj

        def click(name):
            pos = (a.cont_view if a.continent else a.world_view).to_screen(*place(a, name).label_pt)
            a.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

        a.zoom_in("Africa")
        a.anim = None
        click("Kenya")
        self.assertIsNone(m.hint)  # not started yet
        self.assertIn("first country", a.message)
        type_text(a, "Egypt")  # starts the game
        click("Kenya")
        self.assertIs(m.hint, place(a, "Kenya"))
        click("Kenya")
        self.assertIsNone(m.hint)  # clicking again hides it
        click("Egypt")
        self.assertIsNone(m.hint)  # already named: no hint
        a.frame(0.016)
        a.zoom_out()
        a.anim = None
        self.assertIsNone(m.hint)

    def test_typing_every_country_one_after_another_counts_them_all(self):
        a = self.a
        for continent in config.CONTINENT_VIEWS:
            for backwards in (False, True):
                a.mode_obj.reset_all()
                a.zoom_in(continent)
                a.anim = None
                for c in sorted((c for c in a.countries if c.in_quiz and c.continent == continent),
                                key=lambda c: c.name, reverse=backwards):
                    type_text(a, c.name)  # straight on, without pressing Enter
                    a.auto_zoom_out_at = None
                missing = [c.name for c in a.countries if c.in_quiz and c.continent == continent and not c.found]
                self.assertEqual((missing, a.text), ([], ""), continent)
                a.zoom_out()
                a.anim = None
        a.mode_obj.reset_all()

    def test_hand_cursor_only_where_a_hint_is_available(self):
        a, m = self.a, self.a.mode_obj

        def hover(name):
            pos = a.cont_view.to_screen(*place(a, name).label_pt)
            a.handle_event(pygame.event.Event(pygame.MOUSEMOTION, pos=pos, rel=(0, 0), buttons=(0, 0, 0)))
            return m.wants_hand()

        a.zoom_in("Africa")
        a.anim = None
        self.assertFalse(hover("Kenya"))  # the game hasn't started
        type_text(a, "Egypt")
        self.assertTrue(hover("Kenya"))
        self.assertFalse(hover("Egypt"))  # already named
        a.zoom_out()
        a.anim = None

    def test_the_hint_card_has_an_x_to_close_it(self):
        a, m = self.a, self.a.mode_obj
        a.zoom_in("Africa")
        a.anim = None
        type_text(a, "Egypt")
        pos = a.cont_view.to_screen(*place(a, "Kenya").label_pt)
        a.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
        a.frame(0.016)  # draws the card and its x
        self.assertIs(m.hint, place(a, "Kenya"))
        a.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=m.close_rect.center))
        self.assertIsNone(m.hint)
        a.zoom_out()
        a.anim = None

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
        # Every state not named is shown in red, like a wrong answer.
        self.assertTrue(place(a, "Texas").found)
        self.assertTrue(all(c.missed for c in a.countries if c.in_quiz and not c.found))
        a.modal = None
        a.mode_obj.reset_all()
        self.assertFalse(any(c.missed for c in a.countries))

    def test_guess_games_show_what_was_left_when_time_runs_out(self):
        a = app()
        for key in ("us_guess", "us_guess_capital"):
            a.set_mode(key)
            a.mode_obj.reset_all()
            m = a.mode_obj
            first = m.target()
            type_text(a, first.capital if key == "us_guess_capital" else first.name)
            a.frame(config.STATE_TIME_LIMIT + 1)
            self.assertTrue(first.found)
            self.assertIsNone(m.target())  # nothing highlighted any more
            self.assertEqual(sum(c.missed for c in a.countries), a.total_countries() - 1)
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

    def test_tiny_countries_get_their_tag_in_the_sea(self):
        a = app()
        a.set_mode("countries")
        if a.continent is not None:
            a.zoom_out()
        a.anim = None
        a.zoom_in("Europe")
        a.anim = None
        slots = a.callout_slots(a.cont_view, a.quiz_countries())
        self.assertIn("Monaco", slots)  # tiny: in a column
        self.assertNotIn("France", slots)  # big enough to hold its own tag
        ys = sorted(y for x, y, align in slots.values() if x == slots["Monaco"][0])
        self.assertTrue(all(b - a >= 26 for a, b in zip(ys, ys[1:])))  # tags in a column don't overlap
        a.zoom_out()
        a.anim = None

    def test_name_tag_lines_do_not_cross(self):
        from worldmap.labels import line_end, lines_cross
        a = app()
        a.set_mode("countries")
        for continent in ("Europe", "Africa", "North America"):
            if a.continent is not None:
                a.zoom_out()
            a.anim = None
            a.zoom_in(continent)
            a.anim = None
            a.gave_up.add(continent)
            a.show_missed = True  # every name showing
            a.frame(0.016)
            lines = [((ax, ay), line_end(r, (ax, ay))) for r, _, (ax, ay), _ in a.label_cache[1]
                     if not r.collidepoint(ax, ay)]
            crossings = [(p, q) for i, p in enumerate(lines) for q in lines[i + 1:] if lines_cross(*p, *q)]
            self.assertEqual(crossings, [], continent)
            a.show_missed = False
            a.mode_obj.reset_all()

    def test_guess_games_hint_at_the_highlighted_state(self):
        a = app()
        for key in ("us_guess", "us_guess_capital"):
            a.set_mode(key)
            a.mode_obj.reset_all()
            m = a.mode_obj
            capital = key == "us_guess_capital"
            first = m.target()
            pos = a.cont_view.to_screen(*first.label_pt)
            a.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
            self.assertIs(m.hint, first)  # hints work from the very first state
            type_text(a, first.capital if capital else first.name)
            target = m.target()
            other = next(c for c in a.countries if c.in_quiz and c is not target and not c.found)
            for c, expected in ((other, None), (target, target)):
                pos = a.cont_view.to_screen(*c.label_pt)
                a.handle_event(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))
                self.assertIs(m.hint, expected)
            a.frame(0.016)  # draws "Starts with ..."
            type_text(a, target.capital if capital else target.name)
            self.assertIsNone(m.hint)  # the next state needs its own hint
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
