"""Turning lon/lat into screen pixels, and drawing a map of countries."""

import math

import pygame

from .config import BORDER, LAND_HOVER, MAP_H, OCEAN, WIDTH


class View:
    """Maps lon/lat to screen pixels for a given lon/lat box, keeping aspect ratio."""

    def __init__(self, box):
        self.box = box
        lon0, lat0, lon1, lat1 = box
        self.wrap = lon1 > 180
        self.k = math.cos(math.radians((lat0 + lat1) / 2))  # squash longitudes away from the equator
        w, h = (lon1 - lon0) * self.k, lat1 - lat0
        self.scale = min(WIDTH / w, MAP_H / h)
        self.cx = (lon0 + lon1) / 2 * self.k
        self.cy = (lat0 + lat1) / 2

    def project_ring(self, ring):
        # Shift whole rings that sit west of 0° so islands just past the date line
        # appear next to their Pacific neighbours (only in views that cross 180°).
        shift = 360 if self.wrap and all(lon <= 0 for lon, _ in ring) else 0
        return [self.to_screen(lon + shift, lat) for lon, lat in ring]

    def to_screen(self, lon, lat):
        return (WIDTH / 2 + (lon * self.k - self.cx) * self.scale,
                MAP_H / 2 - (lat - self.cy) * self.scale)

    def to_lonlat(self, x, y):
        return ((x - WIDTH / 2) / self.scale + self.cx) / self.k, self.cy - (y - MAP_H / 2) / self.scale

    def screen_rect(self, box):
        """Screen rectangle covering a lon/lat box (used for the zoom animation)."""
        x0, y0 = self.to_screen(box[0], box[3])
        x1, y1 = self.to_screen(box[2], box[1])
        return pygame.Rect(x0, y0, x1 - x0, y1 - y0)


def draw_map(countries, view, colour_for, highlight=None):
    """Draw the map; returns the surface and the [(x, y, country)] dots drawn for tiny countries."""
    surf = pygame.Surface((WIDTH, MAP_H))
    surf.fill(OCEAN)
    small = []
    for c in countries:
        colour = colour_for(c)
        if c is highlight:
            colour = LAND_HOVER
        rings = [view.project_ring(ring) for ring in c.rings]
        for pts in rings:
            xs = [p[0] for p in pts]
            if max(xs) < 0 or min(xs) > WIDTH:
                continue
            if len(pts) >= 3:
                pygame.draw.polygon(surf, colour, pts)
                pygame.draw.polygon(surf, BORDER, pts, 1)
        # Mark microstates / tiny islands with a dot so they are visible and clickable.
        # Spread-out island nations (e.g. Kiribati) get a dot on their biggest island.
        # Territories that aren't in the quiz (e.g. Bermuda) get no dot.
        if not c.in_quiz:
            continue

        def extent(pts):
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            return max(xs) - min(xs), max(ys) - min(ys), (max(xs) + min(xs)) / 2, (max(ys) + min(ys)) / 2

        sizes = [extent(pts) for pts in rings]
        all_pts = [p for pts in rings for p in pts]
        w, h, cx, cy = extent(all_pts)
        if w < 6 and h < 6:
            small.append((cx, cy, colour, c))
        elif all(sw < 4 and sh < 4 for sw, sh, _, _ in sizes):
            _, _, cx, cy = max(sizes, key=lambda e: e[0] * e[1])
            small.append((cx, cy, colour, c))
    for x, y, colour, _ in small:
        pygame.draw.circle(surf, colour, (x, y), 5)
        pygame.draw.circle(surf, BORDER, (x, y), 5, 1)
    return surf, [(x, y, c) for x, y, _, c in small]
