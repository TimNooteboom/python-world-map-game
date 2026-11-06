"""Name tags on the map: on found (black) and missed (red / dark) countries and states."""

import math

import pygame

from .config import (CALLOUT_COLUMNS, CALLOUT_STEP, FOUND_LABEL, MAP_H, MISSED, NE_CALLOUT_ORDER, NE_CALLOUT_STEP,
                     NE_CALLOUT_TOP, NE_CALLOUT_X, PANEL, TEXT, TINY_COUNTRY_PX, WIDTH)


def lines_cross(a1, a2, b1, b2):
    """True if the line from a1 to a2 crosses the line from b1 to b2."""
    def side(p, q, r):
        return (q[0] - p[0]) * (r[1] - p[1]) - (q[1] - p[1]) * (r[0] - p[0])
    return side(a1, a2, b1) * side(a1, a2, b2) < 0 and side(b1, b2, a1) * side(b1, b2, a2) < 0


def line_end(rect, point):
    """Where a tag's line meets the tag: the point of rect nearest to the country's label point."""
    return min(max(point[0], rect.left), rect.right), min(max(point[1], rect.top), rect.bottom)


def crosses_lines(rect, point, lines):
    """True if the line from a tag at rect back to point would cross any of these (start, end) lines.
    (A tag may sit over a line: keeping tags off every line pushes big countries' tags far away.)"""
    if rect.collidepoint(point):
        return False  # the tag is on its country: no line
    end = line_end(rect, point)
    return any(lines_cross(point, end, start, stop) for start, stop in lines)


class LabelsMixin:
    """Part of App: lays out and draws the name tags for the current map."""

    def draw_labels(self):
        """Name tags on the map: black on countries you've named, red on missed ones, dark after "Give up"."""
        key = (self.continent, self.cont_view.box if self.cont_view else None, self.show_missed,
               tuple((c.found, c.missed) for c in self.countries))
        if self.label_cache[0] != key:
            self.label_cache = (key, self.place_labels())
        placed = self.label_cache[1]

        for rect, text, (ax, ay), bg in placed:
            if not rect.collidepoint(ax, ay):  # label was moved: point back to the country
                pygame.draw.line(self.screen, bg, (ax, ay), line_end(rect, (ax, ay)), 1)
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
                 if c.found or c.missed or (zoomed and self.show_missed)]
        # Place the smallest countries first, so they get the spots closest to them.
        shown.sort(key=lambda c: (c.bbox[2] - c.bbox[0]) * (c.bbox[3] - c.bbox[1]))
        bounds = pygame.Rect(4, 4, WIDTH - 8, MAP_H - 8)
        placed = []
        # Tiny countries (and the small northeastern states) get their tag in a column in the sea, joined by a
        # line, so the tags don't cover their neighbors. Placed first, so other tags keep clear of them.
        callouts = self.callout_slots(view, shown)
        shown.sort(key=lambda c: c.name not in callouts)
        lines = []  # (start, end) of the column tags' lines, which the other tags keep clear of
        for c in shown:
            ax, ay = view.project_ring([c.label_pt])[0]
            text = self.label_font.render(self.mode_obj.label_text(c), True, TEXT)
            rect = text.get_rect().inflate(10, 4)
            bg = FOUND_LABEL if c.found else MISSED if c.missed else PANEL
            if c.name in callouts:
                x, y, align = callouts[c.name]
                if align == "left":
                    rect.midleft = (x, y)
                else:
                    rect.midright = (x, y)
                placed.append((rect, text, (ax, ay), bg))
                lines.append(((ax, ay), line_end(rect, (ax, ay))))
                continue
            if zoomed:
                for dx, dy in self.label_offsets():
                    rect.center = (ax + dx, ay + dy)
                    rect.clamp_ip(bounds)
                    if not any(rect.colliderect(r) for r, *_ in placed) and not crosses_lines(rect, (ax, ay), lines):
                        break
            else:
                rect.center = (ax, ay)
                width_on_screen = (c.bbox[2] - c.bbox[0]) * view.k * view.scale
                if rect.w > width_on_screen * 1.3 or any(rect.colliderect(r) for r, *_ in placed):
                    continue
            placed.append((rect.copy(), text, (ax, ay), bg))
        return placed

    def callout_slots(self, view, shown):
        """{name: (x, y, align)} for the tags that go in a column in the sea instead of on the map."""
        slots = {name: (x, y, "left") for name, (x, y) in self.ne_callout_slots().items()}
        columns = CALLOUT_COLUMNS.get(self.continent) if self.scope.has_world else None
        if not columns:
            return slots
        sized = []  # (size on screen, label point on screen, country)
        for c in shown:
            pts = [p for ring in c.rings for p in view.project_ring(ring)]
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            sized.append((max(max(xs) - min(xs), max(ys) - min(ys)), view.project_ring([c.label_pt])[0], c))
        for col in columns:
            tiny = col.get("max_px", TINY_COUNTRY_PX)  # countries smaller than this can't hold their tag
            items = sorted(((pt, c) for size, pt, c in sized if size < tiny and col["x_from"] <= pt[0] < col["x_to"]),
                           key=lambda item: item[0][1])
            ys = self.column_ys(col, [pt for pt, _ in items])
            # Swap any two tags whose lines cross (e.g. Monaco / Andorra / Vatican City), until none do.
            for _ in range(len(items) ** 2):
                pair = next(((i, j) for i in range(len(items)) for j in range(i + 1, len(items))
                             if lines_cross(items[i][0], (col["x"], ys[i]), items[j][0], (col["x"], ys[j]))), None)
                if pair is None:
                    break
                i, j = pair
                items[i], items[j] = items[j], items[i]
                ys = self.column_ys(col, [pt for pt, _ in items])
            for (pt, c), y in zip(items, ys):
                slots[c.name] = (col["x"], y, col["align"])
        return slots

    @staticmethod
    def column_ys(col, points):
        """y of each tag in a column, top to bottom: as level with its country as possible, below the tag
        above, and leaving room for the ones below."""
        ys = []
        for i, (_, ay) in enumerate(points):
            lowest = col["top"] if i == 0 else ys[-1] + CALLOUT_STEP
            highest = col["bottom"] - (len(points) - 1 - i) * CALLOUT_STEP
            ys.append(min(max(ay, lowest), highest))
        return ys

    def ne_callout_slots(self):
        """{state name: (x, y) where its tag starts} for the small NE states, if this mode puts them off the coast.

        One fixed slot per state, in a column in the ocean, in NE_CALLOUT_ORDER (full USA map only).
        """
        if not self.mode_obj.ne_callouts() or self.ne_zoomed():
            return {}
        return {name: (NE_CALLOUT_X, NE_CALLOUT_TOP + i * NE_CALLOUT_STEP) for i, name in enumerate(NE_CALLOUT_ORDER)}

    @staticmethod
    def label_offsets():
        """Candidate label positions: the spot itself, then rings further and further out."""
        yield 0, 0
        for r in range(16, 400, 16):
            for i in range(16):
                a = 2 * math.pi * i / 16
                yield r * math.cos(a) * 1.8, r * math.sin(a)  # wider than tall, like the labels
