"""Name tags on the map: on found (black) and missed (red / dark) countries and states."""

import math

import pygame

from .config import FOUND_LABEL, MAP_H, MISSED, NE_CALLOUT_ORDER, PANEL, TEXT, WIDTH


class LabelsMixin:
    """Part of App: lays out and draws the name tags for the current map."""

    def draw_labels(self):
        """Name tags on the map: green for countries you've named, dark for missed ones after "Give up"."""
        key = (self.continent, self.cont_view.box if self.cont_view else None, self.show_missed,
               tuple((c.found, getattr(c, "missed", False)) for c in self.countries))
        if self.label_cache[0] != key:
            self.label_cache = (key, self.place_labels())
        placed = self.label_cache[1]

        for rect, text, (ax, ay), bg in placed:
            if not rect.collidepoint(ax, ay):  # label was moved: point back to the country
                end = (min(max(ax, rect.left), rect.right), min(max(ay, rect.top), rect.bottom))
                pygame.draw.line(self.screen, bg, (ax, ay), end, 1)
                pygame.draw.circle(self.screen, bg, (ax, ay), 2)
        for rect, text, _, bg in placed:
            pill = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(pill, (*bg, 215), pill.get_rect(), border_radius=5)
            self.screen.blit(pill, rect)
            self.screen.blit(text, text.get_rect(center=rect.center))

    def place_labels(self):
        """Work out where each name tag goes, nudging them apart so they don't overlap.

        Zoomed in, every tag is shown (moved aside with a pointer line if needed). On the
        crowded world map a tag is only shown if it fits on its country without moving.
        """
        zoomed = self.continent is not None
        view = self.cont_view if zoomed else self.world_view
        shown = [c for c in self.quiz_countries()
                 if c.found or getattr(c, "missed", False) or (zoomed and self.show_missed)]
        # Place the smallest countries first, so they get the spots closest to them.
        shown.sort(key=lambda c: (c.bbox[2] - c.bbox[0]) * (c.bbox[3] - c.bbox[1]))
        bounds = pygame.Rect(4, 4, WIDTH - 8, MAP_H - 8)
        placed = []
        # States game / guess games: the small northeastern states get their tag out in the Atlantic, joined by
        # a line, so the tags don't cover their neighbours. Placed first, so other tags keep clear of them.
        callouts = self.ne_callout_slots()
        shown.sort(key=lambda c: c.name not in callouts)
        for c in shown:
            ax, ay = view.project_ring([c.label_pt])[0]
            text = self.label_font.render(self.mode_obj.label_text(c), True, TEXT)
            rect = text.get_rect().inflate(10, 4)
            bg = FOUND_LABEL if c.found else MISSED if getattr(c, "missed", False) else PANEL
            if c.name in callouts:
                rect.midleft = callouts[c.name]
                placed.append((rect, text, (ax, ay), bg))
                continue
            if zoomed:
                for dx, dy in self.label_offsets():
                    rect.center = (ax + dx, ay + dy)
                    rect.clamp_ip(bounds)
                    if not any(rect.colliderect(r) for r, *_ in placed):
                        break
            else:
                rect.center = (ax, ay)
                width_on_screen = (c.bbox[2] - c.bbox[0]) * view.k * view.scale
                if rect.w > width_on_screen * 1.3 or any(rect.colliderect(r) for r, *_ in placed):
                    continue
            placed.append((rect.copy(), text, (ax, ay), bg))
        return placed

    def ne_callout_slots(self):
        """{state name: (x, y) where its tag starts} for the small NE states, if this mode puts them off the coast.

        One fixed slot per state, in a column in the ocean, in NE_CALLOUT_ORDER (full USA map only).
        """
        if not self.mode_obj.ne_callouts() or self.ne_zoomed():
            return {}
        return {name: (1060, 205 + i * 30) for i, name in enumerate(NE_CALLOUT_ORDER)}

    @staticmethod
    def label_offsets():
        """Candidate label positions: the spot itself, then rings further and further out."""
        yield 0, 0
        for r in range(16, 400, 16):
            for i in range(16):
                a = 2 * math.pi * i / 16
                yield r * math.cos(a) * 1.8, r * math.sin(a)  # wider than tall, like the labels
