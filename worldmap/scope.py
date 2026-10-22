"""A scope is one map you can play on (the world, or the USA) with its own game in progress."""


class Scope:
    """One map you can play on (the world or the USA): its countries/states, game in progress and scores."""

    def __init__(self, key, countries, views, noun, nouns, time_limit, score_files, board_title, score_label=None):
        self.key, self.countries, self.views = key, countries, views
        self.has_world = key == "world"  # the world has a globe view with continents to zoom into
        self.noun, self.nouns = noun, nouns  # "country"/"countries" or "state"/"states"
        self.time_limit, self.score_files, self.board_title = time_limit, score_files, board_title
        self.score_label = score_label or nouns.title()  # scoreboard column: "Countries", "States", "Correct"
        # Key a saved score uses for the count: "countries", "states" (States game, Guess the State) or "capitals".
        self.score_field = {"world": "countries", "guess_capital": "capitals"}.get(key, "states")
        self.progress_prefix = "" if self.has_world else "us_"
        # Game in progress (see App.reset_game_state), kept while you play other modes.
        self.continent = None  # None = world view
        self.cont_view = None
        self.world_surf = self.continent_surf = None
        self.world_dots, self.continent_dots = [], []
        self.label_cache = (None, [])  # (state key, placed labels) so labels aren't re-laid out every frame
        self.time_left = time_limit
        self.timer_started = self.time_up = False
        self.result = self.new_score = None
        self.gave_up = set()
        self.show_missed = False  # names of missed countries shown on the map after "Give up"
        self.auto_zoom_out_at = None  # time to move on after finishing a continent
        self.guess_order, self.guess_index = [], 0  # Guess the State: states in the order they're asked


# App attributes that belong to the current Scope (see App.scope); App reads and writes them there.
SCOPE_ATTRS = ("countries", "continent", "cont_view", "world_surf", "continent_surf", "world_dots",
               "continent_dots", "label_cache", "time_left", "timer_started", "time_up", "result",
               "new_score", "gave_up", "show_missed", "auto_zoom_out_at", "guess_order", "guess_index")


def scope_attributes(cls):
    """Class decorator: app.continent etc. read and write the current scope's value (app.scope.continent)."""
    for name in SCOPE_ATTRS:
        setattr(cls, name, property(lambda self, n=name: getattr(self.scope, n),
                                    lambda self, value, n=name: setattr(self.scope, n, value)))
    return cls
