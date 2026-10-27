"""The Learn modes: hover over a country or state to see its name, flag and capital."""

import pygame

from ..config import LAND_HOVER, MAP_H, MISSED, PANEL, SELECTED, TEXT, TEXT_DIM, WIDTH
from ..ui import Button
from .base import Mode
from .quiz import FactMode


class CountryLearnMode(Mode):
    """Countries / States Learn: a card with the name and flag follows the mouse."""

    hover_shows_continent = False  # the country under the mouse lights up, not its continent

    def __init__(self, app, key):
        super().__init__(app, key)
        self.back_btn = Button("Back", (WIDTH - 150, MAP_H + 20, 130, 36))

    def handle_world_event(self, event):
        app = self.app
        if event.type == pygame.MOUSEMOTION:
            app.hover = app.country_at(event.pos, app.world_view, app.world_dots)
        else:
            super().handle_world_event(event)

    def handle_event(self, event):
        """Zoomed into a continent: hover shows names, Back/Esc returns."""
        app = self.app
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            app.zoom_out()
        elif event.type == pygame.MOUSEMOTION:
            app.hover = app.country_at(event.pos, app.cont_view, app.continent_dots)
        elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and app.scope.has_world
              and self.back_btn.rect.collidepoint(event.pos)):
            app.zoom_out()

    def draw_world(self):
        app = self.app
        self.draw_hover_card(app.world_view, app.world_dots)
        app.draw_title()
        self.draw_panel()

    def draw_zoomed(self):
        app = self.app
        self.draw_hover_card(app.cont_view, app.continent_dots)
        self.draw_panel()

    def draw_hover_card(self, view, dots):
        """Highlight the country under the mouse and show its name and flag next to the cursor."""
        app = self.app
        c = app.hover
        if not c or not c.in_quiz or c.continent not in app.scope.views:
            return
        if app.continent is not None and c.continent != app.continent:
            return
        app.draw_country_highlight(c, LAND_HOVER, view, dots)
        name = app.fit_text(app.name_font, c.name, TEXT, 260)
        card = app.learn_card(172, max(200, name.get_width() + 32))
        app.draw_card_background(card)
        app.draw_flag(c, pygame.Rect(card.x + 16, card.y + 14, card.w - 32, 106))
        app.screen.blit(name, name.get_rect(midbottom=(card.centerx, card.bottom - 12)))

    def draw_panel(self):
        app = self.app
        if app.continent is None:
            app.screen.blit(app.big.render(self.info.label, True, TEXT), (24, MAP_H + 14))
            hint = "Hover over a country to see its name and flag. Click a continent to zoom in."
        else:
            app.screen.blit(app.big.render(app.heading(), True, TEXT), (24, MAP_H + 14))
            hint = f"Hover over a {app.scope.noun} to see its name and flag."
            if app.scope.has_world:
                self.back_btn.draw(app.screen, app.font)
        app.screen.blit(app.font.render(hint, True, TEXT_DIM), (24, MAP_H + 62))


class FactLearnMode(FactMode):
    """Flags / Capitals Learn (world and USA): hover to see a flag or capital; Practice test quizzes you."""

    def __init__(self, app, key):
        super().__init__(app, key)
        self.selected = None  # country under the mouse whose flag / capital is shown
        self.back_btn = Button("Back", (WIDTH - 320, MAP_H + 20, 100, 36))
        self.practice_btn = Button("Practice test", (WIDTH - 200, MAP_H + 20, 180, 36))

    def reset(self):
        super().reset()
        self.selected = None

    def handle_explore_event(self, event):
        app = self.app
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            app.zoom_out()
        elif event.type == pygame.MOUSEMOTION:
            # Hovering a country shows its flag / capital, like Countries Learn.
            app.hover = self.selected = self.learn_country_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_btn.rect.collidepoint(event.pos) and app.scope.has_world:
                app.zoom_out()
            elif self.practice_btn.rect.collidepoint(event.pos):
                self.start_quiz("practice")

    def draw_explore(self):
        app = self.app
        c = self.selected  # the country under the mouse
        if c:
            app.draw_country_highlight(c, SELECTED)
        if self.subject == "capitals":
            self.draw_capitals(c)
            return
        if not c:
            return
        card = app.learn_card(248)
        app.draw_card_background(card)
        app.draw_flag(c, pygame.Rect(card.x + 16, card.y + 16, card.w - 32, 170))
        name = app.fit_text(app.name_font, c.name, TEXT, card.w - 24)
        app.screen.blit(name, name.get_rect(midbottom=(card.centerx, card.bottom - 16)))

    def draw_capitals(self, selected):
        """Capitals Learn: a dot on every capital, and a card + label for the selected country."""
        app = self.app
        for c in app.quiz_countries():
            x, y = app.cont_view.project_ring([c.capital_pt])[0]
            pygame.draw.circle(app.screen, PANEL, (x, y), 4)
        if not selected:
            return
        x, y = app.cont_view.project_ring([selected.capital_pt])[0]
        pygame.draw.circle(app.screen, MISSED, (x, y), 8)
        pygame.draw.circle(app.screen, TEXT, (x, y), 8, 2)
        tag = app.label_font.render(selected.capital, True, TEXT)
        rect = tag.get_rect(midbottom=(x, y - 12)).inflate(12, 6)
        rect.clamp_ip(pygame.Rect(4, 4, WIDTH - 8, MAP_H - 8))
        pygame.draw.rect(app.screen, PANEL, rect, border_radius=5)
        app.screen.blit(tag, tag.get_rect(center=rect.center))
        card = app.learn_card(236)
        app.draw_card_background(card)
        app.draw_flag(selected, pygame.Rect(card.x + 16, card.y + 16, card.w - 32, 90))
        lines = [(app.name_font, selected.name, TEXT), (app.small, "Capital", TEXT_DIM),
                 (app.name_font, selected.capital, LAND_HOVER)]
        y = card.y + 120
        for font, text, color in lines:
            img = app.fit_text(font, text, color, card.w - 24)
            app.screen.blit(img, img.get_rect(midtop=(card.centerx, y)))
            y += img.get_height() + 8

    def idle_panel(self):
        app = self.app
        if app.scope.has_world:
            self.back_btn.draw(app.screen, app.font)
        self.practice_btn.draw(app.screen, app.font)
        return f"Hover over a {app.scope.noun} to see its {self.thing}, or take the practice test."

    def world_hint(self):
        return f"Click a continent, then hover over any country to see its {self.thing}."
