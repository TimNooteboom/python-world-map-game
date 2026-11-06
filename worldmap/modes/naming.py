"""Countries Game and States Game: type the names of every country (or state) against the clock."""

import pygame

from ..config import CONTINENT_ORDER, FOUND, LAND, LAND_HOVER, MAP_H, MISSED, TEXT, TEXT_DIM, WIDTH
from ..data import normalize
from ..storage import score_count
from ..ui import Button, fmt_time
from .timed import TimedMode


class NamingMode(TimedMode):
    def __init__(self, app, key):
        super().__init__(app, key)
        self.back_btn = Button("Back", (WIDTH - 260, MAP_H + 20, 100, 36))
        self.giveup_btn = Button("Give up", (WIDTH - 150, MAP_H + 20, 130, 36))
        # A counted answer left in the box because a longer name starts with it ("Niger" -> "Nigeria").
        self.kept_text = self.kept_country = None
        self.hint = None  # unnamed country you clicked: its first letter is shown as a hint

    # ---------- switching / per frame ----------
    def enter(self):
        app = self.app
        app.message = f"Name the {app.scope.nouns} of {app.place()}!"

    def update(self):
        app = self.app
        if app.auto_zoom_out_at and pygame.time.get_ticks() >= app.auto_zoom_out_at and not app.anim:
            self.next_continent()

    def next_continent(self):
        """After finishing a continent: go to the next unfinished one in CONTINENT_ORDER (or the world)."""
        app = self.app
        done = app.continent
        app.auto_zoom_out_at = None
        start = CONTINENT_ORDER.index(done)
        for cont in CONTINENT_ORDER[start + 1:] + CONTINENT_ORDER[:start]:
            if not all(c.found for c in app.countries if c.in_quiz and c.continent == cont):
                app.zoom_in(cont)
                app.message = f"{done} complete! Now name the countries of {cont}."
                return
        app.zoom_out(app.message)  # every continent is done

    # ---------- map ----------
    def world_color(self, c, hover_continent):
        if c.found:
            return FOUND
        if c.missed:  # not named before the time ran out
            return MISSED
        return super().world_color(c, hover_continent)

    def continent_color(self, c):
        if c.found:
            return FOUND
        if c.missed or self.app.continent in self.app.gave_up:
            return MISSED
        return LAND

    def ne_callouts(self):
        return self.app.continent == "USA"

    # ---------- input ----------
    def handle_world_event(self, event):
        app = self.app
        clicked = event.type == pygame.MOUSEBUTTONDOWN and event.button == 1
        if clicked and app.game_started() and app.reset_btn.rect.collidepoint(event.pos):
            self.click_start_over()
        elif event.type == pygame.MOUSEMOTION or clicked:
            super().handle_world_event(event)
        else:
            self.handle_typing(event)

    def click_for_hint(self, pos):
        """Zoomed in: clicking an unnamed country shows its first letter (once the game has started).
        Clicking it again, or anywhere else, hides the hint."""
        app = self.app
        if not app.timer_started:
            app.message = f"Hints start once you've named your first {app.scope.noun}."
            return
        hit = app.country_at(pos, app.cont_view, app.continent_dots)
        if hit and hit.in_quiz and not hit.found and hit.continent == app.continent and hit is not self.hint:
            self.hint = hit
        else:
            self.hint = None

    def reset(self):
        super().reset()
        self.hint = None

    def handle_event(self, event):
        app = self.app
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if app.scope.has_world:
                app.zoom_out()
        elif (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1 and app.game_started()
              and app.reset_btn.rect.collidepoint(event.pos)):
            self.click_start_over()
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.back_btn.rect.collidepoint(event.pos) and app.scope.has_world:
                app.zoom_out()
            elif self.giveup_btn.rect.collidepoint(event.pos):
                # First click gives up; later clicks show/hide the names again.
                app.show_missed = not app.show_missed if app.continent in app.gave_up else True
                app.gave_up.add(app.continent)
                missed = sum(not c.found for c in app.quiz_countries())
                app.text = ""
                if app.show_missed:
                    app.message = f"You missed {missed} {app.scope.nouns}. Hide the names to keep typing."
                else:
                    app.message = f"{missed} {app.scope.nouns} still missing (in red)."
                app.render_continent()
            elif not app.time_up and not app.show_missed:
                self.click_for_hint(event.pos)
        elif not app.show_missed:  # no typing while the answers are on screen
            self.handle_typing(event)

    def check_answer(self, submitted):
        app = self.app
        guess = normalize(app.text)
        if self.kept_text is not None and not app.text.startswith(self.kept_text):
            self.kept_text = self.kept_country = None  # the kept answer was left behind: it stays counted
        if not guess:
            return
        for c in app.quiz_countries():
            if guess in c.accepted:
                if c.found:
                    if c is self.kept_country:
                        # Still typing the rest of a counted name ("Marshall Is" -> "Marshall Islands"): clear
                        # the box once it's complete (or on Enter).
                        if submitted or not self.could_be_longer(guess, c):
                            self.kept_text = self.kept_country = None
                            app.text = ""
                    elif submitted:
                        app.message = f"You already named {c.name}."
                        app.text = ""
                    return
                # A name counts as soon as it matches ("Niger", "Marshall Is"), but stays in the box while a longer
                # name could still be coming ("Nigeria", "Marshall Islands").
                keep = not submitted and self.could_be_longer(guess, c)
                if self.kept_country is not None:
                    self.kept_country.found = False  # you were typing the longer name, not "Niger"
                c.found = True
                app.timer_started = True
                app.message = f"Correct: {c.name}!" if app.continent else f"Correct: {c.name} ({c.continent})!"
                app.text = app.text if keep else ""
                self.kept_text, self.kept_country = (app.text, c) if keep else (None, None)
                app.rerender()
                if all(q.found for q in app.quiz_countries()):
                    where = app.place() if app.continent else "the world"
                    app.message = f"You named every {app.scope.noun} in {where}!"
                    if app.continent and app.scope.has_world:
                        # Pause briefly so the last country can be seen turning green.
                        app.auto_zoom_out_at = pygame.time.get_ticks() + 1500
                if app.total_found() == app.total_countries():
                    self.end_game()
                return
        if submitted and self.kept_country is not None and self.could_be_longer(guess, self.kept_country):
            self.kept_text = self.kept_country = None  # Enter halfway through a counted name: just clear the box
            app.text = ""
            return
        if submitted:
            where = f"in {app.place()}" if app.continent else "on the map"
            app.message = f"'{app.text}' is not a {app.scope.noun} {where}."
            app.text = ""

    def could_be_longer(self, guess, country):
        """True if guess is the start of a longer name you might be typing: country's own name ("marshall is" ->
        "marshall islands") or the name of a country you still have to name ("niger" -> "nigeria").

        Only displayed names count, not formal ones from the map data ("Gabonese Republic"), or typing "Gabon"
        and then "Ethiopia" would look like the start of "gabone..."."""
        return any(len(name) > len(guess) and name.startswith(guess)
                   for name in self.names_in_progress(country))

    def names_in_progress(self, country):
        """Names the answer box could still be heading for: country's own and every country not named yet."""
        return [normalize(c.name) for c in self.app.quiz_countries() if c is country or not c.found]

    def accept_suggestion(self):
        # Picking a suggestion with Tab is a clear choice, even "Niger" while Nigeria is still left.
        self.check_answer(submitted=True)

    def after_reset(self):
        self.kept_text = self.kept_country = None

    def add_letter(self, text, letter):
        """After a kept answer ("Niger"), a letter that can't lead to another name starts the next answer."""
        if self.kept_text is not None and text == self.kept_text:
            prefix = normalize(text + letter)
            if not any(name.startswith(prefix) for name in self.names_in_progress(self.kept_country)):
                self.kept_text = self.kept_country = None  # moving on: the kept answer stays counted
                return letter
        return text + letter

    def answer_names(self, c):
        """The name, plus endings of it that are accepted too ("Micronesia" for Federated States of Micronesia)."""
        words = c.name.split()
        return [c.name] + [" ".join(words[i:]) for i in range(1, len(words))
                           if normalize(" ".join(words[i:])) in c.accepted]

    # ---------- end of game ----------
    def end_message(self, done):
        app = self.app
        sc = app.scope
        if app.time_left <= 0:
            return f"Time's up! You named {done} {sc.noun if done == 1 else sc.nouns}."
        return f"You named every {sc.noun} in {fmt_time(app.result['seconds'])}!"

    def result_text(self, result):
        app = self.app
        title = "Time's up!" if app.time_left <= 0 else f"You named every {app.scope.noun}!"
        return title, f"{score_count(result)} {app.scope.nouns} in {fmt_time(result['seconds'])}"

    # ---------- drawing ----------
    def draw_world(self):
        app = self.app
        app.draw_labels()
        app.draw_title()
        self.draw_world_panel()

    def draw_zoomed(self):
        self.app.draw_labels()
        self.draw_continent_panel()
        self.draw_hint()

    def draw_hint(self):
        """The clicked country lights up, with "Starts with K" next to it."""
        app, c = self.app, self.hint
        if c is None or c.found or app.time_up or app.show_missed:
            return
        app.draw_country_highlight(c, LAND_HOVER)
        name = c.name[4:] if c.name.startswith("The ") else c.name
        text = app.font.render(f"Starts with {name[0].upper()}", True, TEXT)
        near = app.cont_view.project_ring([c.label_pt])[0]
        card = app.learn_card(text.get_height() + 16, text.get_width() + 28, near=near)
        app.draw_card_background(card)
        app.screen.blit(text, text.get_rect(center=card.center))

    def draw_world_panel(self):
        app = self.app
        hint = "Type a country, or click a continent"
        if app.hover and app.hover.continent in app.scope.views:
            hint = f"{app.hover.continent} — click to zoom in"
        app.draw_text_box(pygame.Rect(24, MAP_H + 20, 310, 40), app.message or hint,
                          locked=app.over_label() if app.time_up else None)
        # Progress per continent
        x = 380
        total_done = total = 0
        for cont in app.scope.views:
            qs = [c for c in app.countries if c.continent == cont and c.in_quiz]
            done = sum(c.found for c in qs)
            total_done += done
            total += len(qs)
            app.screen.blit(app.small.render(cont, True, TEXT_DIM), (x, MAP_H + 30))
            app.screen.blit(app.font.render(f"{done}/{len(qs)}", True, TEXT), (x, MAP_H + 55))
            x += 125
        # Overall total, separated from the per-continent scores
        pygame.draw.line(app.screen, TEXT_DIM, (x - 15, MAP_H + 28), (x - 15, MAP_H + 85))
        app.screen.blit(app.small.render("Total", True, TEXT_DIM), (x, MAP_H + 30))
        app.screen.blit(app.big.render(f"{total_done}/{total}", True, FOUND), (x, MAP_H + 50))

    def draw_continent_panel(self):
        app = self.app
        qs = app.quiz_countries()
        done = sum(c.found for c in qs)
        app.screen.blit(app.big.render(app.heading(), True, TEXT), (24, MAP_H + 14))
        app.screen.blit(app.font.render(f"{done} / {len(qs)} {app.scope.nouns}", True, TEXT_DIM), (24, MAP_H + 60))
        if app.scope.has_world:
            app.screen.blit(app.small.render(f"Total: {app.total_found()} / {app.total_countries()} worldwide",
                                             True, TEXT_DIM), (24, MAP_H + 90))

        app.draw_text_box(pygame.Rect(330, MAP_H + 20, 520, 40), app.message,
                          locked=app.over_label() if app.time_up else "Answers are showing" if app.show_missed else None)

        if app.continent in app.gave_up:
            self.giveup_btn.text = "Hide names" if app.show_missed else "Show names"
        else:
            self.giveup_btn.text = "Give up"
        if app.scope.has_world:
            self.back_btn.draw(app.screen, app.font)
        self.giveup_btn.draw(app.screen, app.font)
