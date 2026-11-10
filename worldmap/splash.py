"""The start screen: two tiles, the world (Countries Game) and the USA (Guess the State). Click one to play."""

import pygame

from .config import (BORDER, HEIGHT, INSET_BOXES, LAND, LAND_HOVER, LAND_OTHER, OUTLINE, PANEL, SELECTED,
                     STATE_TIME_LIMIT, TEXT, TEXT_DIM, TIME_LIMIT, USA_VIEW, WIDTH, WORLD_VIEW)
from .geo import View, draw_map

TILE_W, TILE_H, TILE_GAP, TILE_TOP = 500, 380, 60, 225
THUMB_PAD = 14  # space around the map picture inside a tile


class SplashMixin:
    """Part of App: the start screen shown when the game opens."""

    def setup_splash(self):
        self.splash = True
        left = (WIDTH - 2 * TILE_W - TILE_GAP) // 2
        world, usa = self.scopes["world"], self.scopes["usa"]
        n_countries = sum(c.in_quiz for c in world.countries)
        n_states = sum(c.in_quiz for c in usa.countries)
        # (mode it starts, title, subtitle, tile rect, {hover: map picture})
        self.splash_tiles = [
            ("countries", "World", f"Name all {n_countries} countries in {TIME_LIMIT // 60} minutes",
             pygame.Rect(left, TILE_TOP, TILE_W, TILE_H), self.splash_thumbs(world.countries, WORLD_VIEW)),
            ("us_guess", "USA", f"Guess the State: {n_states} states in {STATE_TIME_LIMIT // 60} minutes",
             pygame.Rect(left + TILE_W + TILE_GAP, TILE_TOP, TILE_W, TILE_H),
             self.splash_thumbs(usa.countries, USA_VIEW, INSET_BOXES)),
        ]

    @staticmethod
    def splash_thumbs(places, box, frames=()):
        """{hover: small picture of the map}: plain, and lit up for when the mouse is over the tile."""
        view = View(box)
        thumbs = {}
        for hover in (False, True):
            land = LAND_HOVER if hover else LAND
            surf, _ = draw_map(places, view, lambda c: land if c.in_quiz else LAND_OTHER)
            for frame in frames:  # the Alaska and Hawaii insets
                pygame.draw.rect(surf, BORDER, view.screen_rect(frame), 1, border_radius=6)
            w = TILE_W - 2 * THUMB_PAD
            thumbs[hover] = pygame.transform.smoothscale(surf, (w, round(w * surf.get_height() / surf.get_width())))
        return thumbs

    def splash_tile_at(self, pos):
        return next((tile for tile in self.splash_tiles if tile[3].collidepoint(pos)), None)

    def handle_splash_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            tile = self.splash_tile_at(event.pos)
            if tile:
                self.splash = False
                self.set_mode(tile[0])

    def draw_splash(self):
        self.screen.fill(PANEL)
        title = self.title_font.render("Map Game", True, TEXT)
        self.screen.blit(title, title.get_rect(midtop=(WIDTH // 2, 100)))
        sub = self.font.render("Pick a map to play", True, TEXT_DIM)
        self.screen.blit(sub, sub.get_rect(midtop=(WIDTH // 2, 156)))

        hovered = self.splash_tile_at(pygame.mouse.get_pos())
        for tile in self.splash_tiles:
            _, name, blurb, rect, thumbs = tile
            hover = tile is hovered
            pygame.draw.rect(self.screen, (58, 63, 74) if hover else (48, 52, 62), rect, border_radius=12)
            pygame.draw.rect(self.screen, SELECTED if hover else OUTLINE, rect, 3 if hover else 2, border_radius=12)
            thumb = thumbs[hover]
            thumb_rect = thumb.get_rect(midtop=(rect.centerx, rect.y + THUMB_PAD))
            self.screen.blit(thumb, thumb_rect)
            pygame.draw.rect(self.screen, BORDER, thumb_rect, 1)
            label = self.big.render(name, True, TEXT)
            self.screen.blit(label, label.get_rect(midtop=(rect.centerx, thumb_rect.bottom + 22)))
            text = self.small.render(blurb, True, TEXT_DIM)
            self.screen.blit(text, text.get_rect(midtop=(rect.centerx, thumb_rect.bottom + 70)))

        note = self.small.render("Flags, capitals and more are in the Modes menu once you're in.", True, TEXT_DIM)
        self.screen.blit(note, note.get_rect(midbottom=(WIDTH // 2, HEIGHT - 80)))

    def go_home(self):
        """Back to the start screen. The game in progress is kept (its clock pauses) for when you come back."""
        self.menu_open = False
        self.text = ""
        self.mode_obj.reset()
        self.splash = True

    def splash_wants_hand(self):
        return self.splash_tile_at(pygame.mouse.get_pos()) is not None
