"""Shared screen pieces: buttons, cards, the answer box, the timer, the title and flags."""

import os

import pygame

from .config import (BORDER, FLAGS_DIR, FOUND, MAP_H, MISSED, OUTLINE, PANEL, TEXT, TEXT_DIM, WARNING_TIME,
                     WIDTH)


def fmt_date(iso):
    """Saved dates are YYYY-MM-DD; show them as MM/DD/YYYY."""
    y, m, d = (iso.split("-") + ["", "", ""])[:3]
    return f"{m}/{d}/{y}" if d else iso


def fmt_time(seconds):
    """m:ss, dropping any fraction of a second (like the on-screen clock), so 113.9 s is 1:53."""
    seconds = int(seconds)
    return f"{seconds // 60}:{seconds % 60:02d}"


class Button:
    def __init__(self, text, rect):
        self.text, self.rect = text, pygame.Rect(rect)

    def draw(self, screen, font):
        hover = self.rect.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(screen, (90, 98, 112) if hover else (70, 76, 88), self.rect, border_radius=6)
        label = font.render(self.text, True, TEXT)
        screen.blit(label, label.get_rect(center=self.rect.center))


class WidgetsMixin:
    """Drawing helpers used by every mode (part of App; uses its screen, fonts and current scope)."""

    def fit_text(self, font, text, colour, max_w):
        img = font.render(text, True, colour)
        if img.get_width() > max_w:
            img = pygame.transform.smoothscale_by(img, max_w / img.get_width())
        return img

    # ---------- flags ----------
    def flag_image(self, country, size):
        """The country's flag scaled to fit inside size=(w, h), keeping its shape."""
        key = (country.code, size)
        if key not in self.flag_cache:
            try:
                img = pygame.image.load(os.path.join(FLAGS_DIR, country.code + ".png")).convert_alpha()
                scale = min(size[0] / img.get_width(), size[1] / img.get_height())
                img = pygame.transform.smoothscale(img, (round(img.get_width() * scale),
                                                         round(img.get_height() * scale)))
            except (OSError, pygame.error):
                img = pygame.Surface((size[0], size[1] * 2 // 3))  # missing file: grey box with "?"
                img.fill((120, 125, 135))
                q = self.big.render("?", True, TEXT)
                img.blit(q, q.get_rect(center=img.get_rect().center))
            self.flag_cache[key] = img
        return self.flag_cache[key]

    def draw_flag(self, country, box):
        """Flag centred in a pygame.Rect, with a thin border."""
        img = self.flag_image(country, (box.w, box.h))
        rect = img.get_rect(center=box.center)
        self.screen.blit(img, rect)
        pygame.draw.rect(self.screen, BORDER, rect, 1)

    # ---------- cards next to the mouse (Learn modes) ----------
    def learn_card(self, h, w=300):
        """Rect for a Learn card of size (w, h) next to the mouse cursor, flipped to stay on the map."""
        card = pygame.Rect(0, 0, w, h)
        mx, my = pygame.mouse.get_pos()
        card.topleft = (mx + 18, my + 18)
        if card.right > WIDTH - 8:  # flip to the other side of the cursor near the edges
            card.right = mx - 18
        if card.bottom > MAP_H - 8:
            card.bottom = my - 18
        card.clamp_ip(pygame.Rect(0, 0, WIDTH, MAP_H))
        return card

    def draw_card_background(self, card):
        """See-through dark card with the same outline as the quiz answers."""
        pill = pygame.Surface(card.size, pygame.SRCALPHA)
        pygame.draw.rect(pill, (*PANEL, 235), pill.get_rect(), border_radius=10)
        self.screen.blit(pill, card)
        pygame.draw.rect(self.screen, OUTLINE, card, 2, border_radius=10)

    def draw_country_highlight(self, country, colour, view=None, dots=None):
        """Paint one country (and its dot, if it is tiny) on top of the map (the continent map by default)."""
        view = view or self.cont_view
        for ring in country.rings:
            pts = view.project_ring(ring)
            if len(pts) >= 3:
                pygame.draw.polygon(self.screen, colour, pts)
                pygame.draw.polygon(self.screen, BORDER, pts, 1)
        for x, y, c in self.continent_dots if dots is None else dots:
            if c is country:
                pygame.draw.circle(self.screen, colour, (x, y), 7)
                pygame.draw.circle(self.screen, BORDER, (x, y), 7, 1)

    # ---------- title, answer box, timer ----------
    def draw_title(self):
        title = self.title_font.render(self.md.title, True, TEXT)
        rect = title.get_rect(midtop=(WIDTH // 2, 14)).inflate(32, 12)
        pill = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(pill, (*PANEL, 215), pill.get_rect(), border_radius=10)
        self.screen.blit(pill, rect)
        self.screen.blit(title, title.get_rect(center=rect.center))

    def draw_text_box(self, box, message, locked=None):
        """Answer box; `locked` is the text shown in place of the input when typing is disabled."""
        if locked:
            pygame.draw.rect(self.screen, (95, 100, 112), box, border_radius=6)
            label = self.font.render(locked, True, (175, 180, 190))
            self.screen.blit(label, (box.x + 12, box.y + 8))
            self.screen.blit(self.small.render(message, True, TEXT), (box.x, box.bottom + 12))
            return
        pygame.draw.rect(self.screen, (250, 250, 250), box, border_radius=6)
        cursor = "|" if (pygame.time.get_ticks() // 500) % 2 else ""
        inner = box.inflate(-24, 0)  # text area, clipped so long names stay inside the box
        if not self.text:
            label = self.font.render(f"Type a {self.scope.noun} name…", True, (150, 150, 150))
            self.screen.blit(label, (inner.x + 4, box.y + 8), pygame.Rect(0, 0, inner.w - 4, box.h))
            if cursor:  # blinking cursor at the start, where typing begins
                pygame.draw.line(self.screen, (20, 20, 20), (inner.x + 1, box.y + 9), (inner.x + 1, box.bottom - 9), 2)
        else:
            typed = self.font.render(self.text, True, (20, 20, 20))
            self.screen.blit(typed, (inner.x, box.y + 8), pygame.Rect(0, 0, inner.w, box.h))
            x = inner.x + typed.get_width()
            matches = self.mode_obj.suggestions()
            if matches:
                # Grey "ghost" text completing the name; Tab accepts it.
                rest = matches[self.suggest_index % len(matches)][len(self.text):]
                more = f"  ({self.suggest_index % len(matches) + 1}/{len(matches)})" if len(matches) > 1 else ""
                ghost = self.font.render(rest + more, True, (165, 165, 165))
                self.screen.blit(ghost, (x, box.y + 8), pygame.Rect(0, 0, max(0, inner.right - x), box.h))
            if cursor and x < inner.right:
                pygame.draw.line(self.screen, (20, 20, 20), (x + 1, box.y + 9), (x + 1, box.bottom - 9), 2)
        # Clip long messages so they never run into the scores next to the box.
        msg = self.small.render(message, True, TEXT)
        self.screen.blit(msg, (box.x, box.bottom + 12), pygame.Rect(0, 0, box.w + 10, msg.get_height()))

    def draw_timer(self):
        overlay = pygame.Surface(self.timer_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(overlay, (*PANEL, 225), overlay.get_rect(), border_radius=8)
        self.screen.blit(overlay, self.timer_rect)
        # Counts up from 0:00 to the time limit, which is shown next to it.
        elapsed = self.scope.time_limit - self.time_left
        colour = MISSED if self.time_left <= WARNING_TIME else TEXT
        clock = self.big.render(fmt_time(elapsed), True, colour)
        limit = self.font.render(f" / {fmt_time(self.scope.time_limit)}", True, TEXT_DIM)
        row = pygame.Rect(0, 0, clock.get_width() + limit.get_width(), clock.get_height())
        row.midbottom = (self.timer_rect.centerx, self.timer_rect.bottom - 14)
        self.screen.blit(clock, row.topleft)
        self.screen.blit(limit, limit.get_rect(bottomleft=(row.x + clock.get_width(), row.bottom - 4)))
        # Progress bar towards the time limit.
        bar = pygame.Rect(self.timer_rect.x + 12, self.timer_rect.bottom - 10, self.timer_rect.w - 24, 4)
        pygame.draw.rect(self.screen, (80, 86, 98), bar, border_radius=2)
        pygame.draw.rect(self.screen, colour if self.time_left <= WARNING_TIME else FOUND,
                         (bar.x, bar.y, bar.w * elapsed / self.scope.time_limit, bar.h), border_radius=2)
        status = (self.over_label().rstrip("!").upper() if self.time_up else "PAUSED" if self.timer_paused()
                  else f"TIME ({self.scope.time_limit // 60} MIN MAX)" if self.timer_started else "STARTS ON 1ST ANSWER")
        tag = self.label_font.render(status, True, TEXT_DIM)
        if tag.get_width() > self.timer_rect.w - 12:
            tag = pygame.transform.smoothscale_by(tag, (self.timer_rect.w - 12) / tag.get_width())
        self.screen.blit(tag, tag.get_rect(midtop=(self.timer_rect.centerx, self.timer_rect.y + 7)))
