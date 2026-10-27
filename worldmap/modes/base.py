"""The base class every mode builds on. A mode decides how the map is colored, what clicks and keys do,
and what is drawn on top of the map and in the bottom panel."""

import pygame

from ..config import LAND, LAND_HOVER, MODES


class Mode:
    timed = False  # timer, Start over and Leaderboard (Countries, States, Guess the State / Capital)
    hover_shows_continent = True  # on the globe, hovering lights up the whole continent

    def __init__(self, app, key):
        self.app = app
        self.key = key
        self.info = MODES[key]  # scope, subject, kind, title, label
        self.quiz = None  # a running multiple-choice quiz (flag and capital modes only)

    @property
    def subject(self):
        """What the mode is about: "countries" (or states), "flags", "capitals", "guess", "guess_capital"."""
        return self.info.subject

    # ---------- switching ----------
    def reset(self):
        """Forget per-visit things (a running quiz, a selection): called on switching modes and zooming."""
        self.quiz = None

    def enter(self):
        """Called after switching to this mode while zoomed into a continent (or on the USA map)."""

    def on_zoom_in(self):
        """Called after zooming into a continent from the globe."""

    def update(self):
        """Called every frame before drawing."""

    # ---------- map colors ----------
    def world_color(self, c, hover_continent):
        return LAND_HOVER if c.continent == hover_continent else LAND

    def continent_color(self, c):
        """Color of a country in the zoomed-in continent (other continents are always gray)."""
        return LAND

    # ---------- input ----------
    def handle_world_event(self, event):
        """On the globe: hovering lights up a continent, clicking zooms into it."""
        app = self.app
        if event.type == pygame.MOUSEMOTION:
            hit = app.country_at(event.pos, app.world_view, app.world_dots)
            if (hit.continent if hit else None) != (app.hover.continent if app.hover else None):
                app.hover = hit
                app.render_world()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            hit = app.country_at(event.pos, app.world_view, app.world_dots)
            if hit and hit.continent in app.scope.views:
                app.zoom_in(hit.continent)

    def handle_event(self, event):
        """Zoomed into a continent (or on the USA map)."""

    # ---------- drawing ----------
    def draw_world(self):
        """On top of the globe, plus the bottom panel."""

    def draw_zoomed(self):
        """On top of the zoomed-in map, plus the bottom panel."""

    def label_text(self, c):
        """Text of the name tag on a found / missed country."""
        return c.short_name

    def ne_callouts(self):
        """True if the small northeastern states' tags go in the column off the coast."""
        return False

    def show_reset(self):
        """True if the top-right Reset button (flag and capital games) is showing."""
        return False

    def reset_progress(self):
        """What the Reset button does (only called when show_reset() is True)."""
