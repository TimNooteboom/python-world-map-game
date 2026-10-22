"""The Modes menu in the top-left corner."""

import pygame

from .config import FOUND, MENU, PANEL, TEXT, TEXT_DIM


class MenuMixin:
    """Part of App: self.menu_open, self.menu_group (the group showing its Learn / Game entries)."""

    def mode_group(self):
        """The MENU group the current mode is in."""
        for _, groups in MENU:
            for group, _, modes in groups:
                if any(key == self.mode for key, _ in modes):
                    return group

    def menu_items(self):
        """(key, label, rect, kind) for each visible row of the open Modes menu; kind: header, group or mode."""
        rows = []
        for section, groups in MENU:
            rows.append((section, section.upper(), "header"))
            for group, label, modes in groups:
                rows.append((group, label, "group"))
                if self.menu_group == group:
                    rows += [(key, sub_label, "mode") for key, sub_label in modes]
        x, y = self.modes_btn.rect.x, self.modes_btn.rect.bottom + 6
        items = []
        for key, label, kind in rows:
            h = 30 if kind == "header" else 40
            items.append((key, label, pygame.Rect(x, y, 230, h), kind))
            y += h
        return items

    def handle_menu_event(self, event):
        """Clicks on the Modes button / menu. Returns True if the event was used up."""
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE and self.menu_open:
            self.menu_open = False
            return True
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return False
        if self.modes_btn.rect.collidepoint(event.pos):
            self.menu_open = not self.menu_open
            self.menu_group = self.mode_group()  # open on the current mode's group
            return True
        if not self.menu_open:
            return False
        for key, _, rect, kind in self.menu_items():
            if rect.collidepoint(event.pos):
                if kind == "group":
                    self.menu_group = None if self.menu_group == key else key
                elif kind == "mode":
                    self.set_mode(key)
                return True
        self.menu_open = False  # clicked elsewhere: just close the menu
        return True

    def draw_modes_menu(self):
        self.modes_btn.draw(self.screen, self.font)
        if not self.menu_open:
            return
        items = self.menu_items()
        frame = items[0][2].unionall([r for _, _, r, _ in items]).inflate(8, 8)
        pygame.draw.rect(self.screen, PANEL, frame, border_radius=8)
        mouse = pygame.mouse.get_pos()
        for key, label, rect, kind in items:
            if kind == "header":  # section name, not clickable
                text = self.label_font.render(label, True, TEXT_DIM)
                self.screen.blit(text, text.get_rect(midleft=(rect.x + 12, rect.centery + 3)))
                continue
            if rect.collidepoint(mouse):
                pygame.draw.rect(self.screen, (70, 76, 88), rect, border_radius=6)
            text = self.font.render(label, True, TEXT)
            self.screen.blit(text, text.get_rect(midleft=(rect.x + (16 if kind == "group" else 44), rect.centery)))
            # Green dot on the current mode (on its group while the group is closed).
            if kind == "mode" and key == self.mode:
                pygame.draw.circle(self.screen, FOUND, (rect.x + 30, rect.centery), 5)
            elif kind == "group" and key == self.mode_group() and self.menu_group != key:
                pygame.draw.circle(self.screen, FOUND, (rect.right - 12, rect.centery), 5)
            if kind == "group":  # little arrow: right when closed, down when open
                cx, cy = rect.right - 34, rect.centery
                pts = ([(cx - 5, cy - 3), (cx + 5, cy - 3), (cx, cy + 4)] if self.menu_group == key
                       else [(cx - 3, cy - 5), (cx - 3, cy + 5), (cx + 4, cy)])
                pygame.draw.polygon(self.screen, TEXT_DIM, pts)
