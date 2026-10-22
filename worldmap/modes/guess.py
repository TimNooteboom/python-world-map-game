"""Guess the State and Guess the Capital: one highlighted state at a time, one try each, against the clock."""

import random

import pygame

from ..config import (FOUND, LAND, MAP_H, MISSED, NE_SMALL, NE_VIEW, PANEL, SELECTED, TEXT, TEXT_DIM, USA_VIEW,
                      WIDTH)
from ..data import normalise
from ..geo import View
from ..storage import score_count
from ..ui import Button, fmt_time
from .timed import TimedMode


class GuessMode(TimedMode):
    def __init__(self, app, key):
        super().__init__(app, key)
        self.capital = self.subject == "guess_capital"  # Guess the Capital: type the capital, not the name
        self.skip_btn = Button("Skip", (WIDTH - 150, MAP_H + 20, 130, 36))
        self.zoom_btn = Button("Zoom in", (WIDTH - 300, MAP_H + 20, 140, 36))  # small northeastern states

    # ---------- answers ----------
    def answer_of(self, c):
        """What you type for state c: its name, or its capital."""
        return c.capital if self.capital else c.name

    answer_name = answer_of  # for autocomplete

    def answers(self, c):
        return {normalise(c.capital)} if self.capital else c.accepted

    def label_text(self, c):
        return c.capital if self.capital else c.short_name  # Guess the Capital labels states with their capital

    def ne_callouts(self):
        return True

    # ---------- the queue of states ----------
    def enter(self):
        app = self.app
        if not app.guess_order:
            self.new_order()
            app.render_continent()
        what = "capital" if self.capital else "name"
        app.message = f"Type the blue state's {what}. Press Space to come back to it later."

    def new_order(self):
        app = self.app
        app.guess_order = app.quiz_countries()
        random.shuffle(app.guess_order)
        app.guess_index = 0

    def after_reset(self):
        self.new_order()
        self.app.cont_view = View(USA_VIEW)

    def target(self):
        """The highlighted state to name (None once all 50 are answered)."""
        app = self.app
        if app.guess_index < len(app.guess_order):
            return app.guess_order[app.guess_index]
        return None

    def continent_colour(self, c):
        return FOUND if c.found else MISSED if c.missed else SELECTED if c is self.target() else LAND

    def check_answer(self, submitted):
        """Typing turns the state green as soon as it's right; Enter with another state's name (or capital) is a miss."""
        app = self.app
        target = self.target()
        guess = normalise(app.text)
        if not guess or target is None:
            return
        if guess in self.answers(target):
            target.found = True
            app.message = f"Correct: {self.answer_of(target)}!"
            if app.ne_zoomed():  # a right answer always goes back to the whole map
                app.cont_view = View(USA_VIEW)
        elif not submitted:
            return
        elif any(guess in self.answers(c) for c in app.countries if c.in_quiz):
            target.missed = True
            app.message = self.reveal("No")
        else:
            app.message = f"'{app.text}' is not a {'state capital' if self.capital else 'state'}."
            app.text = ""
            return
        self.next_guess()

    def reveal(self, start):
        """Message giving the right answer after a miss or skip."""
        target = self.target()
        if self.capital:
            return f"{start}: the capital of {target.name} is {target.capital}."
        return f"{start}, that was {target.name}." if start == "No" else f"{start}: that was {target.name}."

    def next_guess(self, skipped=False):
        app = self.app
        target = self.target()
        if skipped:
            target.missed = True
            app.message = self.reveal("Skipped")
        app.timer_started = True
        app.text = ""
        app.guess_index += 1
        self.update_ne_zoom()
        app.render_continent()
        if self.target() is None:
            self.end_game()

    def defer(self):
        """Move the highlighted state to the end of the queue, with no penalty."""
        app = self.app
        if app.guess_index >= len(app.guess_order) - 1:
            app.message = "That's the last one left!"
            return
        target = app.guess_order.pop(app.guess_index)
        app.guess_order.append(target)
        app.message = "Coming back to that one later."
        self.update_ne_zoom()
        app.render_continent()

    # ---------- Northeast zoom ----------
    def ne_zoom_available(self):
        target = self.target()
        return not self.app.time_up and (self.app.ne_zoomed() or (target is not None and target.name in NE_SMALL))

    def set_ne_zoom(self, on):
        self.app.cont_view = View(NE_VIEW if on else USA_VIEW)
        self.app.render_continent()

    def update_ne_zoom(self):
        """Back to the whole map when the next state isn't one of the small northeastern ones."""
        target = self.target()
        if self.app.ne_zoomed() and (target is None or target.name not in NE_SMALL):
            self.app.cont_view = View(USA_VIEW)

    # ---------- input ----------
    def handle_event(self, event):
        app = self.app
        clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        if clicked and app.game_started() and app.reset_btn.rect.collidepoint(event.pos):
            self.click_start_over()
        elif clicked and self.skip_btn.rect.collidepoint(event.pos):
            if not app.time_up:
                self.next_guess(skipped=True)
        elif clicked and self.ne_zoom_available() and self.zoom_btn.rect.collidepoint(event.pos):
            self.set_ne_zoom(not app.ne_zoomed())
        elif event.type == pygame.TEXTINPUT and event.text == " " and not app.text:
            # Space before typing anything: come back to this state later (spaces inside names still work).
            if not app.time_up:
                self.defer()
        else:
            self.handle_typing(event)

    # ---------- end of game ----------
    def on_game_over(self):
        app = self.app
        if self.capital:
            # Reveal the capitals that weren't reached before time ran out, in red like the misses.
            for c in app.guess_order[app.guess_index:]:
                c.missed = True
            app.guess_index = len(app.guess_order)
            app.cont_view = View(USA_VIEW)
            app.render_continent()

    def end_message(self, done):
        start = "Time's up" if self.app.time_left <= 0 else "Done"
        return f"{start}! {done} / 50 correct."

    def result_text(self, result):
        title = "Time's up!" if self.app.time_left <= 0 else "All 50 answered!"
        return title, f"{score_count(result)} / 50 correct in {fmt_time(result['seconds'])}"

    # ---------- drawing ----------
    def draw_zoomed(self):
        self.app.draw_labels()
        self.draw_panel()

    def draw_panel(self):
        app = self.app
        right = sum(c.found for c in app.countries)
        wrong = sum(c.missed for c in app.countries)
        app.screen.blit(app.big.render(self.info.title, True, TEXT), (24, MAP_H + 14))
        info = f"{right} correct  ·  {wrong} missed  ·  {50 - right - wrong} left"
        app.screen.blit(app.font.render(info, True, TEXT_DIM), (24, MAP_H + 60))
        app.draw_text_box(pygame.Rect(390, MAP_H + 20, 500, 40), app.message,
                          locked=app.over_label() if app.time_up else None)
        if not app.time_up:
            self.skip_btn.draw(app.screen, app.font)
        if self.ne_zoom_available():
            self.zoom_btn.text = "Zoom out" if app.ne_zoomed() else "Zoom in"
            self.zoom_btn.draw(app.screen, app.font)
        target = self.target()
        if self.capital and target is not None and not app.time_up:
            # The state is named too: this game is about capitals, not finding the state.
            ask = app.font.render("What is the capital of", True, TEXT_DIM)
            name = app.title_font.render(target.name, True, TEXT)
            banner = pygame.Rect(0, 0, max(ask.get_width(), name.get_width()) + 48, 92)
            # In the ocean, clear of the states: below the map, or off the coast when zoomed into the Northeast.
            if app.ne_zoomed():
                banner.bottomright = (WIDTH - 24, MAP_H - 14)
            else:
                banner.midbottom = (WIDTH // 2 + 70, MAP_H - 14)
            pygame.draw.rect(app.screen, PANEL, banner, border_radius=10)
            app.screen.blit(ask, ask.get_rect(midtop=(banner.centerx, banner.y + 8)))
            app.screen.blit(name, name.get_rect(midbottom=(banner.centerx, banner.bottom - 8)))
