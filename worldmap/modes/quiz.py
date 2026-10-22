"""Multiple-choice flag and capital quizzes: the games, and the practice test in the Learn modes."""

import random

import pygame

from ..config import (FOUND, LAND_HOVER, MAP_H, MISSED, OUTLINE, PANEL, TEXT, TEXT_DIM, WIDTH)
from ..storage import save_progress
from ..ui import Button
from .base import Mode


class Quiz:
    """A running quiz: kind is "practice" (endless) or "game" (each country once)."""

    def __init__(self, kind, order):
        self.kind, self.order = kind, order
        self.index = self.score = self.asked = 0
        self.answer, self.choices = None, []
        self.picked = None  # index of the choice clicked, once answered
        self.advance_at = None  # time to move on to the next question
        self.done = False


class FactMode(Mode):
    """Base for the flag and capital modes (Learn and Game): the quiz, and the panels they share."""

    def __init__(self, app, key):
        super().__init__(app, key)
        self.stop_btn = Button("Stop test", (WIDTH - 200, MAP_H + 20, 180, 36))
        self.quit_btn = Button("Back to globe", (WIDTH - 200, MAP_H + 20, 180, 36))
        self.done_card = pygame.Rect(0, 0, 540, 280)
        self.done_card.center = (WIDTH // 2, MAP_H // 2)
        self.replay_btn = Button("Play again", (WIDTH // 2 - 190, self.done_card.bottom - 70, 180, 40))
        self.done_globe_btn = Button("Back to globe", (WIDTH // 2 + 10, self.done_card.bottom - 70, 180, 40))

    @property
    def thing(self):
        return "flag" if self.subject == "flags" else "capital"

    def learn_country_at(self, pos):
        app = self.app
        hit = app.country_at(pos, app.cont_view, app.continent_dots)
        return hit if hit and hit.in_quiz and hit.continent == app.continent else None

    # ---------- per frame / input ----------
    def update(self):
        q = self.quiz
        if q and q.advance_at and pygame.time.get_ticks() >= q.advance_at:
            self.next_question()

    def handle_event(self, event):
        if self.quiz:
            self.handle_quiz_event(event)
        else:
            self.handle_explore_event(event)

    def handle_explore_event(self, event):
        """Zoomed in with no quiz running."""

    # ---------- the quiz ----------
    def start_quiz(self, kind):
        """kind = "practice" (endless) or "game" (each country once). Both move on by themselves."""
        order = self.app.quiz_countries()
        random.shuffle(order)
        self.quiz = Quiz(kind, order)
        self.app.hover = None
        self.next_question()

    def next_question(self):
        q = self.quiz
        q.picked, q.advance_at = None, None
        if q.index >= len(q.order):
            if q.kind == "game":
                q.done = True
                self.on_game_done()
                return
            last = q.order[-1]  # practice: go round again, without repeating the last country
            random.shuffle(q.order)
            if q.order[0] is last:
                q.order.append(q.order.pop(0))
            q.index = 0
        q.answer = q.order[q.index]
        q.index += 1
        others = [c for c in q.order if c is not q.answer]
        q.choices = random.sample(others, 3) + [q.answer]
        random.shuffle(q.choices)

    def on_game_done(self):
        """Called when a game has asked every country."""

    def pick(self, i):
        q = self.quiz
        if q.picked is not None or q.done:
            return
        q.picked = i
        q.asked += 1
        now = pygame.time.get_ticks()
        if q.choices[i] is q.answer:
            q.score += 1
            q.advance_at = now + 1000
        else:
            q.advance_at = now + 2500  # a bit longer, to see the right answer

    def choice_rects(self):
        if self.subject == "capitals":  # text answers: shorter boxes
            w, h, gap_x, gap_y, y0 = 320, 120, 24, 24, 170
        else:
            w, h, gap_x, gap_y, y0 = 290, 200, 24, 24, 120
        x0 = WIDTH // 2 - w - gap_x // 2
        return [pygame.Rect(x0 + (i % 2) * (w + gap_x), y0 + (i // 2) * (h + gap_y), w, h) for i in range(4)]

    def handle_quiz_event(self, event):
        q = self.quiz
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.end_quiz()
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and q.done:
                self.start_quiz("game")
            elif pygame.K_1 <= event.key <= pygame.K_4:
                self.pick(event.key - pygame.K_1)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos
            if q.done:
                if self.replay_btn.rect.collidepoint(pos):
                    self.start_quiz("game")
                elif self.done_globe_btn.rect.collidepoint(pos):
                    self.app.zoom_out()
            elif (self.stop_btn if q.kind == "practice" else self.quit_btn).rect.collidepoint(pos):
                self.end_quiz()
            else:
                for i, rect in enumerate(self.choice_rects()):
                    if rect.collidepoint(pos):
                        self.pick(i)

    def end_quiz(self):
        """Practice test: back to exploring the continent. Game: back to the globe (USA: to the map)."""
        if self.quiz.kind == "practice":
            self.quiz = None
        else:
            self.app.zoom_out()

    # ---------- drawing ----------
    def draw_world(self):
        app = self.app
        app.draw_title()
        app.screen.blit(app.big.render(self.info.label, True, TEXT), (24, MAP_H + 14))
        app.screen.blit(app.font.render(self.world_hint(), True, TEXT_DIM), (24, MAP_H + 62))
        if app.hover and app.hover.continent in app.scope.views:
            label = app.big.render(f"{app.hover.continent}  ›", True, LAND_HOVER)
            app.screen.blit(label, label.get_rect(topright=(WIDTH - 24, MAP_H + 14)))

    def world_hint(self):
        raise NotImplementedError

    def draw_zoomed(self):
        if self.quiz:
            self.draw_quiz()
        else:
            self.draw_explore()
        self.draw_panel()

    def draw_explore(self):
        """Zoomed in with no quiz running."""

    def draw_panel(self):
        app = self.app
        app.screen.blit(app.big.render(app.heading(), True, TEXT), (24, MAP_H + 14))
        self.quit_btn.text = "Back to globe" if app.scope.has_world else "Stop game"
        q = self.quiz
        if q and q.kind == "practice":
            info = f"Practice test  ·  {q.score} / {q.asked} correct"
            self.stop_btn.draw(app.screen, app.font)
        elif q:
            word = "Flag" if self.subject == "flags" else "Capital"
            info = f"{word} {min(q.index, len(q.order))} of {len(q.order)}  ·  {q.score} correct"
            self.quit_btn.draw(app.screen, app.font)
        else:
            info = self.idle_panel()
        app.screen.blit(app.font.render(info, True, TEXT_DIM), (24, MAP_H + 62))

    def idle_panel(self):
        """Draw the panel buttons for when no quiz is running; return the panel's info text."""
        raise NotImplementedError

    def draw_quiz(self):
        app, q = self.app, self.quiz
        shade = pygame.Surface((WIDTH, MAP_H), pygame.SRCALPHA)
        shade.fill((20, 22, 28, 110))  # dims the map, but keeps it visible behind the question
        app.screen.blit(shade, (0, 0))
        if q.done:
            self.draw_done()
            return

        # The country to find, at the top of the screen.
        capitals = self.subject == "capitals"
        ask = app.font.render("What is the capital of" if capitals else "Which flag belongs to", True, TEXT_DIM)
        name = app.fit_text(app.title_font, q.answer.name, TEXT, 700)
        banner = pygame.Rect(0, 0, max(ask.get_width(), name.get_width()) + 48, 92)
        banner.midtop = (WIDTH // 2, 12)
        pygame.draw.rect(app.screen, PANEL, banner, border_radius=10)
        app.screen.blit(ask, ask.get_rect(midtop=(banner.centerx, banner.y + 8)))
        app.screen.blit(name, name.get_rect(midbottom=(banner.centerx, banner.bottom - 8)))

        mouse = pygame.mouse.get_pos()
        answered = q.picked is not None
        for i, (rect, c) in enumerate(zip(self.choice_rects(), q.choices)):
            pygame.draw.rect(app.screen, (66, 72, 86), rect, border_radius=10)
            pygame.draw.rect(app.screen, OUTLINE, rect, 2, border_radius=10)  # outline on every answer
            # Room for the name underneath is always kept, so nothing moves when the answer is shown.
            if capitals:
                city = app.fit_text(app.name_font, c.capital, TEXT, rect.w - 24)
                app.screen.blit(city, city.get_rect(center=(rect.centerx, rect.centery - 10)))
            else:
                flag_box = pygame.Rect(rect.x + 14, rect.y + 14, rect.w - 28, rect.h - 54)
                app.draw_flag(c, flag_box)
            if answered:  # show whose flag / capital each one is, to learn from
                label = app.fit_text(app.small, c.name, TEXT, rect.w - 20)
                app.screen.blit(label, label.get_rect(midbottom=(rect.centerx, rect.bottom - 10)))
            border = None
            if answered and c is q.answer:
                border = FOUND
            elif answered and i == q.picked:
                border = MISSED
            elif not answered and rect.collidepoint(mouse):
                border = LAND_HOVER
            if border:
                pygame.draw.rect(app.screen, border, rect, 5, border_radius=10)

        if answered:
            right = q.choices[q.picked] is q.answer
            wrong = q.choices[q.picked]
            if right:
                text = "Correct!"
            elif capitals:
                text = f"Incorrect. {wrong.capital} is the capital of {wrong.name}. The right answer is in green."
            else:
                text = f"Incorrect. That's {wrong.name}. The right flag is in green."
            msg = app.fit_text(app.big if right else app.name_font, text, FOUND if right else MISSED, WIDTH - 120)
            box = msg.get_rect(midtop=(WIDTH // 2, 560)).inflate(32, 12)
            pygame.draw.rect(app.screen, PANEL, box, border_radius=8)
            app.screen.blit(msg, msg.get_rect(center=box.center))

    def draw_done(self):
        app, q = self.app, self.quiz
        card = self.done_card
        pygame.draw.rect(app.screen, PANEL, card, border_radius=12)
        n = len(q.order)
        perfect = q.score == n
        title = "Perfect!" if perfect else "Finished!"
        world = app.scope.has_world
        what = f"{self.subject} of {app.continent}" if world else f"state {self.subject}"
        where = "globe" if world else "map"
        place = app.place()
        lines = [(app.title_font, title, FOUND if perfect else TEXT),
                 (app.font, f"{q.score} / {n} {what} correct", TEXT),
                 (app.small, f"All of them right! {place[0].upper() + place[1:]} is now green on the {where}."
                  if perfect else f"Get them all right to turn {'the continent' if world else 'the map'} green.",
                  TEXT_DIM)]
        self.done_globe_btn.text = "Back to globe" if world else "Close"
        y = card.y + 30
        for font, text, colour in lines:
            img = font.render(text, True, colour)
            app.screen.blit(img, img.get_rect(midtop=(card.centerx, y)))
            y += img.get_height() + 14
        self.replay_btn.draw(app.screen, app.font)
        self.done_globe_btn.draw(app.screen, app.font)


class QuizGameMode(FactMode):
    """Flags / Capitals Game (world and USA): every country once; all right turns the continent green."""

    def __init__(self, app, key):
        super().__init__(app, key)
        self.start_btn = Button("Start game", (WIDTH - 200, MAP_H + 20, 180, 36))  # USA map between games

    def progress_key(self):
        return self.app.scope.progress_prefix + self.subject

    def perfect(self):
        """Continents (or "USA") done without a miss in this game."""
        return self.app.perfect[self.progress_key()]

    # ---------- switching ----------
    def enter(self):
        self.start_quiz("game")  # straight into this continent's (or the USA's) game

    def on_zoom_in(self):
        self.start_quiz("game")  # the flags appear as soon as the zoom finishes

    def on_game_done(self):
        app, q = self.app, self.quiz
        perfect = self.perfect()
        if q.score == len(q.order) and app.continent not in perfect:
            perfect.add(app.continent)
            save_progress(app.perfect)

    def show_reset(self):
        """The Reset button: on the globe, or the USA map when no game is running."""
        app = self.app
        return app.continent is None or (not app.scope.has_world and not self.quiz)

    # ---------- map ----------
    def world_colour(self, c, hover_continent):
        if c.in_quiz and c.continent in self.perfect():
            return FOUND
        return super().world_colour(c, hover_continent)

    def continent_colour(self, c):
        if self.app.continent in self.perfect():
            return FOUND
        return super().continent_colour(c)

    # ---------- USA map between games ----------
    def handle_explore_event(self, event):
        app = self.app
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            app.zoom_out()
        elif event.type == pygame.MOUSEMOTION:
            app.hover = self.learn_country_at(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.start_btn.rect.collidepoint(event.pos):
                self.start_quiz("game")

    def idle_panel(self):
        self.start_btn.draw(self.app.screen, self.app.font)
        return f"Pick the right {self.thing} for every state. Get them all right to turn the map green!"

    def world_hint(self):
        done = len(self.perfect())
        return (f"Click a continent, then pick the right {self.thing} for each country. Get them all right "
                f"to turn it green!  ({done} / {len(self.app.scope.views)} done)")
