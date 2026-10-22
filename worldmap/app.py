"""The game window: main loop, maps (world and USA), zooming, switching modes and the shared buttons.

What happens in each mode (clicks, keys, colours, panels) lives in the classes in worldmap/modes.
"""

import math

import pygame

from .config import (BORDER, CONTINENT_VIEWS, FPS, HEIGHT, INSET_BOXES, LAND_OTHER, MAP_H, MODES, NE_VIEW, OCEAN,
                     PANEL, STATE_TIME_LIMIT, TIME_LIMIT, USA_VIEW, WIDTH, WORLD_VIEW, ZOOM_TIME,
                     CAPITAL_GUESS_SCORES_FILE, GUESS_SCORES_FILE, SCORES_FILE, STATE_SCORES_FILE, starting_scores)
from .data import State, load_countries, load_state_features
from .geo import View, draw_map
from .labels import LabelsMixin
from .menu import MenuMixin
from .modes import build_modes
from .scope import Scope, scope_attributes
from .scoreboard import ScoreboardMixin
from .storage import load_progress, save_progress
from .ui import Button, WidgetsMixin


@scope_attributes  # app.continent, app.time_left, ... are the current scope's (see scope.SCOPE_ATTRS)
class App(WidgetsMixin, LabelsMixin, ScoreboardMixin, MenuMixin):
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

        state_features = load_state_features()
        self.scopes = {
            "world": Scope("world", load_countries(), CONTINENT_VIEWS, "country", "countries", TIME_LIMIT,
                           (SCORES_FILE, starting_scores("scores.json")), "Top 10 Scores"),
            "usa": Scope("usa", [State(f) for f in state_features], {"USA": USA_VIEW}, "state", "states",
                         STATE_TIME_LIMIT, (STATE_SCORES_FILE, starting_scores("state_scores.json")),
                         "Top 10 State Scores"),
            # Its own copy of the states, so its green/red states and timer don't mix with the States game.
            "guess": Scope("guess", [State(f) for f in state_features], {"USA": USA_VIEW}, "state", "states",
                           STATE_TIME_LIMIT, (GUESS_SCORES_FILE, starting_scores("guess_scores.json")),
                           "Top 10 Guess the State", score_label="Correct"),
            "guess_capital": Scope("guess_capital", [State(f) for f in state_features], {"USA": USA_VIEW},
                                   "capital", "capitals", STATE_TIME_LIMIT,
                                   (CAPITAL_GUESS_SCORES_FILE, starting_scores("capital_guess_scores.json")),
                                   "Top 10 Guess the Capital", score_label="Correct"),
        }
        self.scope = self.scopes["world"]

        self.world_view = View(WORLD_VIEW)
        self.hover = None  # country under the mouse (on the globe: lights up its continent)
        self.text = ""  # the answer box
        self.suggest_index = 0  # which autocomplete match is shown (Up/Down to cycle)
        self.message = ""
        self.anim = None  # (start_time, from_rect, to_rect, zooming_in)
        self.timer_rect = pygame.Rect(WIDTH - 200, 14, 180, 80)
        self.reset_btn = Button("Start over", (WIDTH - 200, 102, 180, 36))  # timed games: resets everything
        self.reset_confirm_until = 0  # resets need a second click within a few seconds
        card = pygame.Rect(0, 0, 620, 560)  # the scoreboard / name entry card
        card.center = (WIDTH // 2, MAP_H // 2 + 20)
        self.card = card
        self.save_btn = Button("Save score", (card.centerx - 150, card.y + 250, 140, 40))
        self.skip_btn = Button("Skip", (card.centerx + 10, card.y + 250, 140, 40))
        self.again_btn = Button("Play again", (card.centerx - 150, card.bottom - 60, 140, 40))
        self.close_btn = Button("View map", (card.centerx + 10, card.bottom - 60, 140, 40))
        self.reset_game_state()

        self.mode = "countries"  # a key of config.MODES
        self.modes = build_modes(self)
        self.mode_obj = self.modes[self.mode]
        self.menu_open = False
        self.menu_group = None  # menu group expanded to show Learn / Game (a group key in MENU)
        self.modes_btn = Button("Modes", (20, 14, 130, 40))
        self.leaderboard_btn = Button("Leaderboard", (160, 14, 160, 40))  # timed games only
        self.lb_close_btn = Button("Close", (self.card.centerx - 70, self.card.bottom - 60, 140, 40))
        self.flag_reset_btn = Button("Reset", (WIDTH - 200, 14, 180, 40))  # flag / capital games
        self.perfect = load_progress()  # continents with every flag / capital right: green on the map
        self.flag_cache = {}

        self.render_world()

    @property
    def md(self):
        """The current mode's settings (scope, subject, kind, titles)."""
        return MODES[self.mode]

    @property
    def quiz(self):
        """The running multiple-choice quiz, if any."""
        return self.mode_obj.quiz

    # ---------- game state of the current map ----------
    def reset_game_state(self):
        self.time_left = self.scope.time_limit
        self.timer_started = False
        self.time_up = False  # True once the game has ended (time ran out or every country/state named)
        self.modal = None  # None, "name" (enter your name), "scores" or "leaderboard" (scoreboard)
        self.result = None  # this game's score, once it's over
        self.new_score = None  # the saved entry to highlight on the scoreboard

    def quiz_countries(self):
        """Countries that can be named right now: one continent when zoomed in, else all."""
        return [c for c in self.countries
                if c.in_quiz and c.continent in self.scope.views
                and (self.continent is None or c.continent == self.continent)]

    def total_found(self):
        return sum(c.found for c in self.countries if c.in_quiz and c.continent in self.scope.views)

    def total_countries(self):
        return sum(1 for c in self.countries if c.in_quiz and c.continent in self.scope.views)

    def place(self):
        """The current continent's name for messages ("Africa", "the USA")."""
        return self.continent if self.scope.has_world else "the USA"

    def heading(self):
        """Big heading in the bottom-left panel when zoomed in: the continent, or the mode's title on the USA map."""
        return self.continent if self.scope.has_world else self.md.title

    def ne_zoomed(self):
        """Zoomed into the Northeast (Guess the State / Capital)."""
        return self.cont_view.box == NE_VIEW

    # ---------- timer ----------
    def over_label(self):
        """Shown when a timed game has ended: ran out of time, or finished everything in time."""
        return "Time's up!" if self.time_left <= 0 else "Finished!"

    def game_started(self):
        """True once there is progress to throw away (a country named, a "Give up", or the game over)."""
        return self.timer_started or self.time_up or bool(self.gave_up)

    def timer_paused(self):
        # The clock stops while the missed countries' names are on screen, or in the untimed modes.
        return (not self.mode_obj.timed or self.modal == "leaderboard"
                or (self.continent is not None and self.show_missed))

    def update_timer(self, dt):
        if not self.timer_started or self.time_up or self.timer_paused():
            return
        self.time_left -= dt
        if self.time_left <= 0:
            self.time_left = 0
            self.mode_obj.end_game()

    # ---------- drawing the maps ----------
    def render_world(self):
        if not self.scope.has_world:  # the USA map has no globe: it's always "zoomed in"
            self.render_continent()
            return
        hover_cont = self.hover.continent if self.hover and self.mode_obj.hover_shows_continent else None
        self.world_surf, self.world_dots = draw_map(self.countries, self.world_view,
                                                    lambda c: self.mode_obj.world_colour(c, hover_cont))

    def render_continent(self):
        def colour(c):
            if c.continent != self.continent or not c.in_quiz:
                return LAND_OTHER
            return self.mode_obj.continent_colour(c)

        self.continent_surf, self.continent_dots = draw_map(self.countries, self.cont_view, colour)
        if not self.scope.has_world:  # frames around the Alaska and Hawaii insets
            for box in INSET_BOXES:
                pygame.draw.rect(self.continent_surf, BORDER, self.cont_view.screen_rect(box), 1, border_radius=6)

    def rerender(self):
        if self.continent is None:
            self.render_world()
        else:
            self.render_continent()

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

    # ---------- zooming ----------
    def zoom_in(self, continent):
        self.continent = continent
        self.show_missed = False
        self.cont_view = View(self.scope.views[continent])
        self.render_continent()
        self.text = ""
        self.message = f"Name the {self.scope.nouns} of {continent}!"
        self.hover = None
        self.mode_obj.reset()
        full = pygame.Rect(0, 0, WIDTH, MAP_H)
        self.anim = (pygame.time.get_ticks(), full, self.world_view.screen_rect(self.scope.views[continent]), True)
        self.mode_obj.on_zoom_in()

    def zoom_out(self, message=""):
        """Back to the globe. On the USA map (nothing to zoom out to) it only leaves the current quiz/selection."""
        if not self.scope.has_world:
            self.hover = None
            self.mode_obj.reset()
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
        self.mode_obj.reset()
        self.render_world()

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

    # ---------- switching modes ----------
    def set_mode(self, mode):
        """Switch game mode, staying zoomed into the current continent if there is one.

        Each map (world, USA) keeps its own game in progress; the timer pauses in the other modes.
        """
        self.menu_open = False
        if mode == self.mode:
            return
        self.mode = mode
        self.mode_obj = self.modes[mode]
        self.scope = self.scopes[self.md.scope]
        self.mode_obj.reset()
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
            self.mode_obj.enter()

    # ---------- main loop ----------
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                self.handle_event(event)
            self.update()
            self.draw()
            self.update_timer(self.clock.tick(FPS) / 1000)

    def frame(self, dt):
        """One frame without input (the main loop's body; also used by tests)."""
        self.update()
        self.draw()
        self.update_timer(dt)

    def update(self):
        self.mode_obj.update()

    def handle_event(self, event):
        if self.modal:
            self.handle_modal_event(event)
            return
        if self.anim:
            return
        if self.handle_menu_event(event) or self.handle_top_button(event):
            return
        if self.continent is None:
            self.mode_obj.handle_world_event(event)
        else:
            self.mode_obj.handle_event(event)

    def handle_top_button(self, event):
        """Leaderboard (timed games) and Reset (flag / capital games) buttons. True if clicked."""
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.mode_obj.timed and self.leaderboard_btn.rect.collidepoint(event.pos):
            self.modal = "leaderboard"
            return True
        if self.mode_obj.show_reset() and self.flag_reset_btn.rect.collidepoint(event.pos):
            # Needs a second click to confirm, like "Start over". Only resets this game's continents.
            if pygame.time.get_ticks() < self.reset_confirm_until:
                self.reset_confirm_until = 0
                self.perfect[self.mode_obj.progress_key()].clear()
                save_progress(self.perfect)
                self.rerender()
            else:
                self.reset_confirm_until = pygame.time.get_ticks() + 3000
            return True
        return False

    def draw(self):
        self.screen.fill(PANEL)
        if self.anim:
            self.draw_animation()
        elif self.continent is None:
            self.screen.blit(self.world_surf, (0, 0))
            self.mode_obj.draw_world()
        else:
            self.screen.blit(self.continent_surf, (0, 0))
            self.mode_obj.draw_zoomed()
        if not self.anim and self.continent is not None and not self.quiz:
            self.draw_title()  # zoomed in / USA map (a running flag or capital quiz shows its question there instead)
        if not self.anim and not self.modal:
            if self.mode_obj.timed:
                self.leaderboard_btn.draw(self.screen, self.font)
            elif self.mode_obj.show_reset():
                confirm = pygame.time.get_ticks() < self.reset_confirm_until
                self.flag_reset_btn.text = "Confirm?" if confirm else "Reset"
                self.flag_reset_btn.draw(self.screen, self.font)
            self.draw_modes_menu()
        if not self.anim and self.mode_obj.timed:
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
