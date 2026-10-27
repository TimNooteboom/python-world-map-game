"""The end-of-game screens: "enter your name" and the Top 10 scoreboard (also opened by Leaderboard)."""

import time

import pygame

from .config import FOUND, HEIGHT, PANEL, TEXT, TEXT_DIM, WIDTH
from .storage import load_scores, save_scores, score_count
from .ui import fmt_date, fmt_time


class ScoreboardMixin:
    """Part of App: self.modal is None, "name", "scores" (after a game) or "leaderboard" (from the button)."""

    def handle_modal_event(self, event):
        if self.modal == "name":
            if event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                    self.submit_score(save=True)
                elif event.key == pygame.K_ESCAPE:
                    self.submit_score(save=False)
                elif event.key == pygame.K_BACKSPACE:
                    self.name_text = self.name_text[:-1]
            elif event.type == pygame.TEXTINPUT and event.text.isprintable() and len(self.name_text) < 15:
                self.name_text += event.text
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.save_btn.rect.collidepoint(event.pos):
                    self.submit_score(save=True)
                elif self.skip_btn.rect.collidepoint(event.pos):
                    self.submit_score(save=False)
        elif self.modal == "scores":
            again = event.type == pygame.KEYDOWN and event.key in (pygame.K_RETURN, pygame.K_KP_ENTER)
            clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            if again or (clicked and self.again_btn.rect.collidepoint(event.pos)):
                if self.continent is not None:
                    self.zoom_out()
                self.mode_obj.reset_all()
            elif clicked and self.close_btn.rect.collidepoint(event.pos):
                self.modal = None  # look at the final map; "Play again" still restarts
        elif self.modal == "leaderboard":
            key = event.type == pygame.KEYDOWN and event.key in (pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER)
            clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
            if key or (clicked and self.lb_close_btn.rect.collidepoint(event.pos)):
                self.modal = None

    def submit_score(self, save):
        if save and self.name_text.strip():
            scores, _ = load_scores(*self.scope.score_files)
            self.new_score = dict(self.result, name=self.name_text.strip(),
                                  date=time.strftime("%Y-%m-%d"))
            # Only the top 10 are kept; a score that doesn't make it is still shown as "didn't make the top 10".
            self.save_failed = not save_scores(self.scope.score_files[0], scores + [self.new_score],
                                               self.name_text.strip())
        self.modal = "scores"

    def draw_card(self, height):
        shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        shade.fill((0, 0, 0, 120))
        self.screen.blit(shade, (0, 0))
        card = pygame.Rect(self.card.x, self.card.y, self.card.w, height)
        pygame.draw.rect(self.screen, PANEL, card, border_radius=12)
        return card

    def draw_name_entry(self):
        card = self.draw_card(320)
        cx = card.centerx
        title, score = self.mode_obj.result_text(self.result)
        lines = [
            (self.big, title, TEXT),
            (self.font, score, FOUND),
            (self.small, "Enter your first name for the scoreboard:", TEXT_DIM),
        ]
        y = card.y + 28
        for font, text, color in lines:
            img = font.render(text, True, color)
            self.screen.blit(img, img.get_rect(midtop=(cx, y)))
            y += img.get_height() + 14
        box = pygame.Rect(cx - 150, card.y + 185, 300, 44)
        pygame.draw.rect(self.screen, (250, 250, 250), box, border_radius=6)
        cursor = "|" if (pygame.time.get_ticks() // 500) % 2 else ""
        name = self.font.render(self.name_text + cursor, True, (20, 20, 20))
        self.screen.blit(name, name.get_rect(midleft=(box.x + 12, box.centery)))
        self.save_btn.draw(self.screen, self.font)
        self.skip_btn.draw(self.screen, self.font)

    def draw_scoreboard(self):
        card = self.draw_card(self.card.h)
        top, _ = load_scores(*self.scope.score_files)
        title = self.big.render(self.scope.board_title, True, TEXT)
        self.screen.blit(title, title.get_rect(midtop=(card.centerx, card.y + 22)))

        cols = [(card.x + 40, "#"), (card.x + 90, "Name"), (card.x + 270, self.scope.score_label),
                (card.x + 385, "Time"), (card.x + 465, "Date")]
        y = card.y + 80
        for x, head in cols:
            self.screen.blit(self.small.render(head, True, TEXT_DIM), (x, y))
        y += 30
        if not top:
            msg = self.font.render("No scores saved yet.", True, TEXT_DIM)
            self.screen.blit(msg, msg.get_rect(midtop=(card.centerx, y + 20)))
        for i, sc in enumerate(top, 1):
            mine = sc == self.new_score
            if mine:
                pygame.draw.rect(self.screen, (60, 90, 70), (card.x + 28, y - 4, card.w - 56, 32), border_radius=6)
            values = [str(i), sc["name"], str(score_count(sc)), fmt_time(sc["seconds"]), fmt_date(sc.get("date", ""))]
            for (x, _), value in zip(cols, values):
                img = self.font.render(value, True, FOUND if mine else TEXT)
                self.screen.blit(img, (x, y), pygame.Rect(0, 0, 200, 30))
            y += 36
        if self.new_score and self.new_score not in top:
            score = f"{score_count(self.new_score)} in {fmt_time(self.new_score['seconds'])}"
            if self.save_failed:
                text = f"Your score ({score}) couldn't be saved: the game can't write to its folder."
            else:
                text = f"Your score ({score}) didn't make the top 10."
            note = self.small.render(text, True, TEXT_DIM)
            self.screen.blit(note, note.get_rect(midtop=(card.centerx, card.bottom - 92)))
        if self.modal == "leaderboard":  # opened from the Leaderboard button mid-game
            self.lb_close_btn.draw(self.screen, self.font)
        else:
            self.again_btn.draw(self.screen, self.font)
            self.close_btn.draw(self.screen, self.font)
