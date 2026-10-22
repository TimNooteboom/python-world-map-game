"""What the timed games share: typing answers with autocomplete, Start over, the end of the game."""

import math

import pygame

from ..data import fold
from ..storage import load_scores, rank_key
from .base import Mode


class TimedMode(Mode):
    """Base for the Countries / States game and Guess the State / Capital."""

    timed = True

    def answer_name(self, c):
        """What you type for c (used by autocomplete)."""
        return c.name

    def check_answer(self, submitted):
        """Check the answer box; `submitted` is True when Enter was pressed."""
        raise NotImplementedError

    # ---------- typing ----------
    def handle_typing(self, event):
        """Typing into the answer box (works on both the world map and continent views)."""
        app = self.app
        if app.time_up:
            return
        if event.type == pygame.KEYDOWN:
            matches = self.suggestions()
            if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.check_answer(submitted=True)
            elif event.key == pygame.K_BACKSPACE:
                app.text = app.text[:-1]
                app.suggest_index = 0
            elif event.key in (pygame.K_TAB, pygame.K_RIGHT) and matches:
                app.text = matches[app.suggest_index % len(matches)]
                app.suggest_index = 0
                self.check_answer(submitted=False)
            elif event.key in (pygame.K_DOWN, pygame.K_UP) and matches:
                app.suggest_index += 1 if event.key == pygame.K_DOWN else -1
        elif event.type == pygame.TEXTINPUT and event.text.isprintable():
            if len(app.text) < 40:
                app.text += event.text
                app.suggest_index = 0
                self.check_answer(submitted=False)  # turn green as soon as it's spelled right

    def suggestions(self):
        """Autocomplete matches for the typed text (after 3 letters) from answers not yet given.

        Zoomed in, only the current continent's countries are suggested; on the world map, all of them.
        """
        typed = fold(self.app.text)
        if len(typed.strip()) < 3:
            return []
        matches = set()
        for c in self.app.quiz_countries():
            if c.found or getattr(c, "missed", False):
                continue
            name = self.answer_name(c)
            for name in (name, name[4:] if name.startswith("The ") else None):
                if name and len(name) > len(typed) and fold(name).startswith(typed):
                    matches.add(name)
        return sorted(matches, key=lambda n: (len(n), n))

    # ---------- start over / end ----------
    def click_start_over(self):
        """Start over (both views). Needs a second click unless the time has already run out."""
        app = self.app
        if app.time_up or pygame.time.get_ticks() < app.reset_confirm_until:
            app.reset_confirm_until = 0
            if app.continent is not None:
                app.zoom_out()
            self.reset_all()
        else:
            app.reset_confirm_until = pygame.time.get_ticks() + 3000
            app.message = "Click again to start over."

    def reset_all(self):
        """Wipe all progress on this map and the timer."""
        app = self.app
        for c in app.countries:
            c.found = c.missed = False
        app.gave_up.clear()
        app.reset_game_state()
        app.text = ""
        app.message = f"Progress reset. The timer starts with your first {app.scope.noun}."
        self.after_reset()
        app.render_world()

    def after_reset(self):
        """Extra things to reset (Guess the State: a new order of states)."""

    def end_game(self):
        """Lock the game and ask for a name to put on the scoreboard (if the score makes the top 10)."""
        app = self.app
        app.time_up = True
        app.text = ""
        done = app.total_found()
        # Saved to a tenth of a second (cut off, not rounded, so it never shows more than the clock did).
        elapsed = app.scope.time_limit - app.time_left
        app.result = {app.scope.score_field: done, "seconds": math.floor(elapsed * 10) / 10}
        self.on_game_over()
        app.message = self.end_message(done)
        scores, last_name = load_scores(*app.scope.score_files)
        top = sorted(scores, key=rank_key)[:10]
        if len(top) < 10 or rank_key(app.result) < rank_key(top[-1]):
            app.name_text = last_name
            app.modal = "name"  # made the top 10: ask for a name
        else:
            app.new_score = dict(app.result)  # not saved; the scoreboard says it didn't make the top 10
            app.modal = "scores"

    def on_game_over(self):
        """Called when the game ends, before the scoreboard (Guess the Capital reveals the answers)."""

    def end_message(self, done):
        raise NotImplementedError

    def result_text(self, result):
        """(title, score line) for the "enter your name" card."""
        raise NotImplementedError
