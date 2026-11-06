"""What the timed games share: typing answers with autocomplete, Start over, the end of the game."""

import math

import pygame

from ..config import LAND_HOVER, TEXT, TEXT_DIM
from ..data import fold
from ..storage import load_scores, makes_top_10
from .base import Mode


class TimedMode(Mode):
    """Base for the Countries / States game and Guess the State / Capital."""

    timed = True
    highlight_hint = True  # light up the country a hint is for (the guess games' state is already blue)

    def __init__(self, app, key):
        super().__init__(app, key)
        self.hint = None  # the country / state you clicked: its first letter is shown
        self.hover_hint = None  # the one under the mouse that a hint is available for
        self.close_rect = None  # the hint card's close (x) button, while the card is on screen

    # ---------- hints: click a country / state to see its first letter ----------
    def hintable(self, c):
        """True if clicking c would show a hint."""
        return False

    def hint_answer(self, c):
        """What the hint is the first letter of."""
        return c.name

    def hints_available(self):
        """Hints only once the game has started, and not while the answers are showing."""
        app = self.app
        return app.timer_started and not app.time_up and not app.show_missed

    def hint_at(self, pos):
        app = self.app
        c = app.country_at(pos, app.cont_view, app.continent_dots)
        return c if c is not None and self.hints_available() and self.hintable(c) else None

    def over_hintable(self):
        """The mouse is over a country / state you can click for a hint."""
        c = self.hover_hint
        return c is not None and self.hints_available() and self.hintable(c)

    def over_close(self, pos=None):
        """The mouse (or pos) is on the hint card's close (x) button."""
        return self.close_rect is not None and self.close_rect.collidepoint(pos or pygame.mouse.get_pos())

    def wants_hand(self):
        """Show the hand cursor over anything clickable: a country with a hint, or the hint's close button."""
        return self.over_hintable() or self.over_close()

    def click_for_hint(self, pos):
        """Clicking a country shows its hint. Clicking it again, anywhere else, or the card's x hides it."""
        if self.over_close(pos):
            self.hint = self.close_rect = None
            return
        c = self.hint_at(pos)
        self.hint = c if c is not None and c is not self.hint else None

    def reset(self):
        super().reset()
        self.hint = self.hover_hint = self.close_rect = None

    def draw_hint(self):
        """"Starts with K" next to the clicked country, or "Click to see a hint" by the mouse: one card at a time.

        Over another country you could click, the tooltip shows (the open hint's card steps aside); anywhere
        else, the open hint's card shows. The hinted country stays lit up either way."""
        app, c = self.app, self.hint
        hint_open = c is not None and self.hints_available() and self.hintable(c)
        if hint_open and self.highlight_hint:
            app.draw_country_highlight(c, LAND_HOVER)
        on_card = self.over_close()  # don't swap the card for the tooltip while aiming at its x
        self.close_rect = None
        if self.over_hintable() and self.hover_hint is not c and not on_card:
            self.draw_tag("Click to see a hint", small=True)
        elif hint_open:
            answer = self.hint_answer(c)
            answer = answer[4:] if answer.startswith("The ") else answer
            card = self.draw_tag(f"Starts with {answer[0].upper()}",
                                 near=app.cont_view.project_ring([c.label_pt])[0], close_button=True)
            self.close_rect = pygame.Rect(0, 0, 22, 22)
            self.close_rect.midright = (card.right - 8, card.centery)
            self.draw_close_button(self.close_rect)

    def draw_tag(self, text, near=None, small=False, close_button=False):
        """A small card with text, next to the mouse (or the point near); room for an x on the right if asked."""
        app = self.app
        img = (app.small if small else app.font).render(text, True, TEXT)
        extra = 30 if close_button else 0
        card = app.learn_card(img.get_height() + (12 if small else 16), img.get_width() + 28 + extra, near=near)
        app.draw_card_background(card)
        app.screen.blit(img, img.get_rect(midleft=(card.x + 14, card.centery)))
        return card

    def draw_close_button(self, rect):
        """An x, brighter with a light background while the mouse is on it."""
        app = self.app
        hover = rect.collidepoint(pygame.mouse.get_pos())
        if hover:
            pygame.draw.rect(app.screen, (90, 98, 112), rect, border_radius=5)
        color = TEXT if hover else TEXT_DIM
        a, b = rect.inflate(-12, -12).topleft, rect.inflate(-12, -12).bottomright
        pygame.draw.line(app.screen, color, a, b, 2)
        pygame.draw.line(app.screen, color, (a[0], b[1]), (b[0], a[1]), 2)

    def answer_names(self, c):
        """What autocomplete can suggest for c."""
        return [c.name]

    def add_letter(self, text, letter):
        """The answer box after typing a letter (the naming game can start afresh after a kept answer)."""
        return text + letter

    def check_answer(self, submitted):
        """Check the answer box; `submitted` is True when Enter was pressed."""
        raise NotImplementedError

    def accept_suggestion(self):
        """Tab / → filled in the autocomplete suggestion."""
        self.check_answer(submitted=False)

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
                self.accept_suggestion()
            elif event.key in (pygame.K_DOWN, pygame.K_UP) and matches:
                app.suggest_index += 1 if event.key == pygame.K_DOWN else -1
        elif event.type == pygame.TEXTINPUT and event.text.isprintable():
            if len(app.text) < 40:
                app.text = self.add_letter(app.text, event.text)
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
            if c.found or c.missed:
                continue
            for name in self.answer_names(c):
                for option in (name, name[4:] if name.startswith("The ") else None):
                    if option and len(option) > len(typed) and fold(option).startswith(typed):
                        matches.add(option)
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
        if makes_top_10(app.result, scores):
            app.name_text = last_name
            app.modal = "name"  # made the top 10: ask for a name
        else:
            app.new_score = dict(app.result)  # not saved; the scoreboard says it didn't make the top 10
            app.modal = "scores"

    def on_game_over(self):
        """Called when the game ends, before the scoreboard: everything not answered turns red, like a miss."""
        app = self.app
        for c in app.countries:
            if c.in_quiz and c.continent in app.scope.views and not c.found:
                c.missed = True
        app.rerender()

    def end_message(self, done):
        raise NotImplementedError

    def result_text(self, result):
        """(title, score line) for the "enter your name" card."""
        raise NotImplementedError
